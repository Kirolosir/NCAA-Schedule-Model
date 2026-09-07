"""Full-division Monte Carlo scoring with paired schedule comparisons."""

from dataclasses import asdict, replace
from hashlib import sha256
from itertools import combinations
from math import comb, fsum, isfinite, sqrt
from random import Random
from statistics import mean, stdev

from .division_npi import DivisionGame
from .fast_division import CompiledDivision
from .game_value import calculate_game_value
from .outcome_model import OutcomeModel
from .temporal_model import planning_model
from .planning import Candidate, parse_plan
from .season_npi import SeasonGame, calculate_season_npi


def summarize(values):
    values = list(values)
    if not values:
        raise ValueError("at least one observation is required")
    ordered = sorted(values)
    def percentile(p):
        position = p*(len(ordered)-1)
        i = int(position)
        f = position-i
        return ordered[i]*(1-f) + ordered[min(i+1, len(ordered)-1)]*f
    center = fsum(values)/len(values)
    se = stdev(values)/sqrt(len(values)) if len(values) > 1 else None
    return {"mean": center, "p10": percentile(.1), "p90": percentile(.9),
            "sample_min": min(values), "sample_max": max(values),
            "mean_standard_error": se,
            "mean_ci95": [center-1.96*se, center+1.96*se] if se is not None else None,
            "samples": len(values)}


def _draw(probabilities, u):
    if u < probabilities.win:
        return "win"
    if u < probabilities.win+probabilities.tie:
        return "tie"
    return "loss"


def _uniforms(seed, team, count):
    digest = sha256(f"{seed}:{team}".encode()).digest()
    rng = Random(int.from_bytes(digest, "big"))
    return [rng.random() for _ in range(count)]


class ScheduleEvaluator:
    def __init__(self, games, ratings, target, fixed, candidates, model, *,
                 target_recent_npi=None, tolerance=1e-8):
        self.ratings = dict(ratings)
        self.target = target
        self.fixed = fixed
        self.background = [g for g in games if target not in (g.team_a, g.team_b)]
        self.tolerance = tolerance
        self.cache = {}
        self.screen_cache = {}
        self.solves = 0
        self._warm_ratings = self.ratings
        strength = ratings[target] if target_recent_npi is None else target_recent_npi
        self.probabilities = {
            c.team: c.probabilities or model.predict(strength, c.recent_npi) for c in candidates
        }
        self.probabilities.update({g.team: g.probabilities or model.predict(strength, ratings[g.team])
                                   for g in fixed})

    def solve(self, outcomes):
        key = tuple(sorted(outcomes))
        if key not in self.cache:
            games = self.background + [DivisionGame(self.target, t, r) for t, r in key]
            result = CompiledDivision(games, self.ratings).solve(
                self._warm_ratings, tolerance=self.tolerance, exact=False)
            self._warm_ratings = result.ratings
            self.cache[key] = result.ratings[self.target]
            self.solves += 1
        return self.cache[key]

    def estimate(self, outcomes, *, iterations=8):
        key = (iterations, tuple(sorted(outcomes)))
        if key not in self.screen_cache:
            games = self.background + [DivisionGame(self.target, t, r) for t, r in key[1]]
            ratings = CompiledDivision(games, self.ratings).estimate(
                self.ratings, iterations=iterations)
            self.screen_cache[key] = ratings[self.target]
        return self.screen_cache[key]

    def sample(self, teams, *, samples, seed, forced=None):
        forced = forced or {}
        names = [g.team for g in self.fixed] + list(teams)
        if not isinstance(samples, int) or samples < 1:
            raise ValueError("samples must be a positive integer")
        if len(set(names)) != len(names):
            raise ValueError("each opponent may appear only once")
        if not set(forced) <= set(names) or any(r not in ("win", "tie", "loss") for r in forced.values()):
            raise ValueError("forced results must name scheduled opponents and valid outcomes")
        draws = {t: _uniforms(seed, t, samples) for t in names}
        locked = {g.team: g.result for g in self.fixed if g.result is not None}
        if set(forced) & set(locked):
            raise ValueError("cannot override a locked result")
        results = []
        for i in range(samples):
            outcomes = [(t, locked.get(t) or forced.get(t) or
                         _draw(self.probabilities[t], draws[t][i])) for t in names]
            results.append(self.solve(outcomes))
        return results

    def approximate_sample(self, teams, *, samples, seed, forced=None):
        forced = forced or {}
        names = [g.team for g in self.fixed] + list(teams)
        draws = {t: _uniforms(seed, t, samples) for t in names}
        locked = {g.team: g.result for g in self.fixed if g.result is not None}
        results = []
        for i in range(samples):
            season = [SeasonGame(t, self.ratings[t], locked.get(t) or forced.get(t) or
                                 _draw(self.probabilities[t], draws[t][i])) for t in names]
            results.append(calculate_season_npi(season).npi)
        return results

    def screening_sample(self, teams, *, samples, seed, forced=None):
        forced = forced or {}
        names = [g.team for g in self.fixed] + list(teams)
        draws = {t: _uniforms(seed, t, samples) for t in names}
        locked = {g.team: g.result for g in self.fixed if g.result is not None}
        return [self.estimate([(t, locked.get(t) or forced.get(t) or
                               _draw(self.probabilities[t], draws[t][i])) for t in names])
                for i in range(samples)]

    def stress(self, teams, result):
        fixed = [(g.team, g.result or result) for g in self.fixed]
        return self.solve(fixed+[(t, result) for t in teams])


def risk_reward(evaluator, teams, *, samples, seed):
    """Paired marginal changes vs omitting the chosen game in this context."""
    rows = []
    for team in teams:
        without = tuple(t for t in teams if t != team)
        baseline = evaluator.sample(without, samples=samples, seed=seed)
        row = {"team": team, "baseline": "same slate with this game omitted",
               "probabilities": asdict(evaluator.probabilities[team])}
        for outcome in ("win", "tie", "loss"):
            values = evaluator.sample(teams, samples=samples, seed=seed, forced={team: outcome})
            row[outcome] = {"npi": summarize(values),
                            "impact": summarize([x-y for x, y in zip(values, baseline)])}
        expected = evaluator.sample(teams, samples=samples, seed=seed)
        row["expected_impact"] = summarize([x-y for x, y in zip(expected, baseline)])
        row["swing_win_minus_loss"] = row["win"]["npi"]["mean"]-row["loss"]["npi"]["mean"]
        rows.append(row)
    return rows


def approximate_risk_reward(evaluator, teams, *, samples, seed):
    rows = []
    for team in teams:
        without = tuple(t for t in teams if t != team)
        baseline = evaluator.approximate_sample(without, samples=samples, seed=seed)
        row = {"team": team, "baseline": "same slate with this game omitted",
               "probabilities": asdict(evaluator.probabilities[team])}
        for outcome in ("win", "tie", "loss"):
            values = evaluator.approximate_sample(teams, samples=samples, seed=seed,
                                                  forced={team: outcome})
            row[outcome] = {"npi": summarize(values),
                            "impact": summarize([x-y for x, y in zip(values, baseline)])}
        expected = evaluator.approximate_sample(teams, samples=samples, seed=seed)
        row["expected_impact"] = summarize([x-y for x, y in zip(expected, baseline)])
        row["swing_win_minus_loss"] = row["win"]["npi"]["mean"]-row["loss"]["npi"]["mean"]
        rows.append(row)
    return rows


def band_arithmetic(config, bands, fixed, ratings, model, target):
    """Diagnostic only: fixed opponent ratings and one added slot, not a graph forecast."""
    games = []
    strength = config.get("target_recent_npi", ratings[target])
    for g in fixed:
        p = g.probabilities or model.predict(strength, ratings[g.team])
        outcome = g.result or max(p.as_items(), key=lambda x: x[1])[0]
        games.append(SeasonGame(g.team, ratings[g.team], outcome))
    base = calculate_season_npi(games).npi
    result = []
    for band in bands:
        row = {**band, "scale": config.get("band_scale", "rating"), "arithmetic_probes": [],
               "projection_status": "historical representatives" if band["member_count"] else "no historical graph profiles"}
        if row["scale"] == "rating":
            low, high = band.get("lower"), band.get("upper")
            if high is not None and (low is None or low < 100):
                # Probe the upper boundary, though band membership excludes it.
                lo = max(0.0, float(low or 0))
                hi = min(100.0, float(high))
                for value in (lo, (lo+hi)/2, hi):
                    probes = {"opponent_npi": value, "baseline_npi": base}
                    for outcome in ("win", "loss"):
                        npi = calculate_season_npi(games+[SeasonGame("band probe", value, outcome)]).npi
                        probes[outcome] = {"game_value": calculate_game_value(outcome, value).total,
                                           "conditional_season_npi": npi, "impact": npi-base}
                    row["arithmetic_probes"].append(probes)
            elif low is not None and low >= 100:
                row["projection_status"] = "unsupported above 100 by verified calculator; no midpoint assumed"
        result.append(row)
    return result


def rank_schedules(games, ratings, config, *, progress=None):
    target, fixed, candidates, bands = parse_plan(config, ratings)
    for key in ("samples", "validation_samples", "insight_samples"):
        if not isinstance(config[key], int) or config[key] < 2:
            raise ValueError(f"{key} must be an integer >= 2")
    slots = config["open_slots"]
    if not isinstance(slots, int) or slots < 1 or slots > len(candidates):
        raise ValueError(f"open_slots={slots} needs at least that many candidates; found {len(candidates)}")
    top_n = config["top_n"]
    if not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be positive")
    scale = config["probability_slope_scale"]
    if not isfinite(scale) or not 0 < scale <= 2:
        raise ValueError("probability_slope_scale must be in (0, 2]")
    if not isinstance(config["seed"], int):
        raise ValueError("seed must be an integer")
    tolerance = config["convergence_tolerance"]
    if not isfinite(tolerance) or tolerance <= 0 or tolerance > 1e-6:
        raise ValueError("convergence_tolerance must be in (0, 1e-6]")
    required = set(config.get("required", []))
    names = {c.team for c in candidates}
    if not required <= names or len(required) > slots:
        raise ValueError("required teams must be eligible candidates and fit the open slots")
    total = comb(len(candidates)-len(required), slots-len(required))
    if not isinstance(config["max_combinations"], int) or config["max_combinations"] < 1:
        raise ValueError("max_combinations must be a positive integer")
    if total > config["max_combinations"]:
        raise ValueError(f"{total} combinations exceeds max_combinations; narrow the pool or raise the limit")
    if progress:
        progress("Loading outcome probabilities and division graph")
    fitted = planning_model(games, ratings, config)
    model = replace(fitted, slope=fitted.slope*scale)
    extra_names = {t for b in bands for t in b["representatives"]}-names
    extras = [Candidate(t, ratings[t]) for t in sorted(extra_names)]
    evaluator = ScheduleEvaluator(games, ratings, target, fixed, candidates+tuple(extras), model,
                                  target_recent_npi=config.get("target_recent_npi"), tolerance=tolerance)
    seed = config["seed"]
    fast = config.get("analysis_mode", "thorough") != "thorough"
    screening_sample = evaluator.screening_sample if fast else evaluator.sample
    baseline = screening_sample((), samples=config["samples"], seed=seed)
    screened = []
    for i, optional in enumerate(combinations(sorted(names-required), slots-len(required)), 1):
        teams = tuple(sorted(required | set(optional)))
        values = screening_sample(teams, samples=config["samples"], seed=seed)
        screened.append({"opponents": teams, "screening": summarize(values),
                         "screening_impact": summarize([x-y for x, y in zip(values, baseline)])})
        if progress:
            progress(f"Scored schedule {i}/{total}: mean NPI {mean(values):.3f}")
    screened.sort(key=lambda row: (-row["screening"]["mean"], row["opponents"]))
    # Validate extra finalists because sampling noise can change their order.
    finalist_count = top_n*2
    finalists = screened[:min(len(screened), max(finalist_count, top_n))]
    validation_seed = seed+1000003
    baseline_validation = evaluator.sample((), samples=config["validation_samples"], seed=validation_seed)
    for i, row in enumerate(finalists, 1):
        values = evaluator.sample(row["opponents"], samples=config["validation_samples"], seed=validation_seed)
        row["projection"] = summarize(values)
        row["impact_vs_fixed_slate"] = summarize([x-y for x, y in zip(values, baseline_validation)])
        row["_values"] = values
        if progress:
            progress(f"Validated finalist {i}/{len(finalists)} with independent samples")
    finalists.sort(key=lambda row: (-row["projection"]["mean"], row["opponents"]))
    best = finalists[0]["_values"]
    for row in finalists:
        row["paired_gap_from_leader"] = summarize([x-y for x, y in zip(best, row.pop("_values"))])
    top = finalists[:top_n]
    impact_evaluator = approximate_risk_reward if fast else risk_reward
    for i, row in enumerate(top, 1):
        row["rank"] = i
        row["stress_all_unlocked_wins"] = evaluator.stress(row["opponents"], "win")
        row["stress_all_unlocked_losses"] = evaluator.stress(row["opponents"], "loss")
        row["opponent_impacts"] = impact_evaluator(evaluator, row["opponents"], samples=config["insight_samples"], seed=seed+2000003)
        support = max(row["opponent_impacts"], key=lambda r: r["expected_impact"]["mean"])
        risk = min(row["opponent_impacts"], key=lambda r: r["loss"]["impact"]["mean"])
        row["reasoning"] = [
            f"Largest sampled marginal contribution: {support['team']}.",
            f"Largest conditional loss downside: {risk['team']}.",
            "Marginal impacts compare the full proposed slate to the same slate minus one game; they are not additive.",
        ]
        if progress:
            progress(f"Explained finalist {i}/{len(top)}: win/tie/loss impacts for every open opponent")
    standalone = []
    if config.get("include_standalone_insights", True):
        for t in sorted(names | extra_names):
            standalone.extend(impact_evaluator(evaluator, (t,), samples=config["insight_samples"], seed=seed+3000003))
            if progress:
                progress(f"Evaluated standalone risk/reward: {t}")
    probability_note = ("Probability fitting uses earlier-season ratings to predict later-season results. The newest season is held out from fitting."
                        if fitted.method == "prior_season_out_of_time" else
                        "Probability fitting uses same-period end ratings, including the outcomes being fitted. It is a retrospective comparison, not prospective validation.")
    return {
        "config": config, "target_team": target,
        "calculation": {"screening": "eight-pass division shortlist" if fast else "full-division",
                        "finalists": "full-division", "opponent_impacts":
                        "fixed-rating quick estimate" if fast else "full-division"},
        "background": {"teams": len(ratings), "games": len(games), "rating_min": min(ratings.values()),
                       "rating_max": max(ratings.values())},
        "probability_model": {"fit": asdict(fitted), "slope_scale": scale,
                               "used_slope": model.slope},
        "candidates": [{**asdict(c), "outcome_rating_extrapolation":
                        not fitted.rating_min <= c.recent_npi <= fitted.rating_max}
                       for c in candidates],
        "bands": band_arithmetic(config, bands, fixed, ratings, model, target),
        "screening": screened, "validated_finalists": finalists,
        "top_schedules": top, "standalone_opponents": standalone,
        "baseline_projection": summarize(baseline_validation), "division_solves": evaluator.solves,
        "limitations": [
            "Planning replay of the supplied division graph; other teams' historical games/results stay fixed. Not a validated future-season forecast.",
            "Old target games are removed reciprocally; proposed games are added to opponents' historical schedules. Opponents' replacement fixtures are unknown.",
            "Default candidates are historical/reference examples; availability, travel and dates are unverified.",
            "Fixed means opponent locked; outcomes remain uncertain unless result is supplied. All nonconference decisions are open by default.",
            "Recent NPI overrides affect pregame probabilities only. The historical result graph determines converged NPI; changing an iteration seed cannot change a fixed point.",
            probability_note,
            f"Probability slope scale={scale} is a planning sensitivity, not a calibrated uncertainty estimate. Override probabilities or vary this setting.",
            "Game outcomes are conditionally independent; no injury, roster, travel, date, or common team-form uncertainty is modeled.",
            "P10–P90 describes simulated season spread. Mean CI95 describes Monte Carlo error conditional on the model; neither includes model uncertainty.",
            "All-win/all-loss are stress scenarios, not proven global NPI extrema. Screening ranks all allowed combinations; independent validation covers only the displayed shortlist.",
            "Banded graph projections use selected real representatives. They do not evaluate every team or assume a uniform rating distribution within a band.",
            "Band arithmetic probes hold opponent ratings and modal fixed-game results constant; they are diagnostics, not division-converged forecasts.",
        ],
    }
