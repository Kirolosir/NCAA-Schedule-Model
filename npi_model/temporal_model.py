"""Fit prior-season ratings to subsequent games; hold the newest season out."""

from dataclasses import asdict
from functools import lru_cache
from hashlib import sha256
import json
from math import fsum, log
from datetime import datetime

from .outcome_model import OutcomeModel, _fit, _loss, _probabilities
from .seasons import DATA, load_season, season_path

ARTIFACT = DATA / "historical_probability_models.json"


def transition_rows(outcome_season, weight=1.0):
    prior, ratings, _ = load_season(str(int(outcome_season)-1))
    current, _, games = load_season(outcome_season)
    def game_date(value):
        return datetime.strptime(value, "%Y-%m-%d" if value[:4].isdigit() else "%m-%d-%Y").date()
    if datetime.strptime(prior["source"]["cutoff"], "%Y-%m-%d").date() >= min(game_date(g[1]) for g in current["games"]):
        raise ValueError("Predictor snapshot must precede every outcome")
    rows = [((ratings[g.team_a]-ratings[g.team_b])/10, ("win", "tie", "loss").index(g.result_a), weight)
            for g in games if g.team_a in ratings and g.team_b in ratings]
    return rows, {"predictor_season": prior["source"]["season"], "predictor_cutoff": prior["source"]["cutoff"],
                  "outcome_season": outcome_season, "games": len(rows), "excluded_new_teams_games": len(games)-len(rows),
                  "weight_per_game": weight}


def fit_historical(season):
    if season not in ("2024", "2025"):
        raise ValueError("No earlier-season training pairs are available")
    training_seasons = [str(y) for y in range(2023, int(season))]
    rows, transitions = [], []
    for year in training_seasons:
        transition, source = transition_rows(year, .75 ** (int(season)-1-int(year)))
        rows.extend(transition)
        transitions.append(source)
    slope, tie = _fit(rows)
    test, holdout = transition_rows(season)
    tie_rate = fsum(w for _, y, w in rows if y == 1)/fsum(w for _, _, w in rows)
    baseline = log(2*tie_rate/(1-tie_rate))
    _, ratings, _ = load_season(season)
    score = _loss(test, slope, tie)
    model = OutcomeModel(slope, tie, len(rows), _loss(rows, slope, tie), _loss(rows, 0, baseline),
                         None, min(ratings.values()), max(ratings.values()), "prior_season_out_of_time",
                         tuple(training_seasons), season, score)
    recent_rows, _ = transition_rows(training_seasons[-1])
    recent_b, recent_a = _fit(recent_rows)
    diagnostics = {"training": transitions, "holdout": holdout, "holdout_log_loss": score,
                   "constant_holdout_log_loss": _loss(test, 0, baseline),
                   "recent_only_holdout_log_loss": _loss(test, recent_b, recent_a),
                   "recency_decay": .75,
                   "note": "Lower log loss is better. Holdout outcomes never enter fitting. Recency weighting is a planning choice, not a confidence guarantee; uncertainty intervals remain conditional on the model."}
    return {"model": asdict(model), "diagnostics": diagnostics,
            "source_hashes": {y: sha256(season_path(y).read_bytes()).hexdigest() for y in ("2022", "2023", "2024", "2025") if y <= season}}


@lru_cache(maxsize=2)
def historical_model(season):
    entry = json.loads(ARTIFACT.read_text())[season]
    for year, digest in entry["source_hashes"].items():
        if sha256(season_path(year).read_bytes()).hexdigest() != digest:
            raise ValueError("Season data changed; rebuild historical probability models")
    return OutcomeModel(**entry["model"]), entry["diagnostics"]


def score_predictions(rows, slope, tie):
    """Score untouched games; include both teams for win-chance calibration.

    The Brier score sums the three squared probability errors (0 is perfect).
    Accuracy splits credit evenly if two outcomes tie for most likely.
    """
    predictions = [(_probabilities(d, slope, tie), outcome) for d, outcome, *_ in rows]
    count = len(predictions)
    if not count:
        raise ValueError("Accuracy checks need at least one held-out game")
    brier = fsum(fsum((p-int(i == outcome))**2 for i, p in enumerate(probs))
                 for probs, outcome in predictions)/count
    accuracy = fsum((1/sum(p == max(probs) for p in probs)) if probs[outcome] == max(probs) else 0
                    for probs, outcome in predictions)/count
    forecasts = [(p[0], int(y == 0)) for p, y in predictions]
    forecasts += [(p[2], int(y == 2)) for p, y in predictions]
    calibration = []
    for index in range(5):
        low, high = index/5, (index+1)/5
        bucket = [(p, y) for p, y in forecasts if low <= p and (p < high or index == 4 and p == 1)]
        calibration.append({"lower": low, "upper": high, "count": len(bucket),
                            "predicted_win_rate": fsum(p for p, _ in bucket)/len(bucket) if bucket else None,
                            "actual_win_rate": fsum(y for _, y in bucket)/len(bucket) if bucket else None})
    return {"games": count, "log_loss": _loss(rows, slope, tie),
            "brier_score": brier, "accuracy": accuracy, "win_calibration": calibration}


@lru_cache(maxsize=4)
def historical_accuracy(season):
    if season not in ("2024", "2025"):
        return {"available": False, "reason": "No earlier-season training and separate test season are available for this view."}
    model, diagnostics = historical_model(season)
    test, source = transition_rows(season)
    # Baseline probabilities also use training outcomes only, never test outcomes.
    train = []
    for year in model.training_seasons:
        train.extend(transition_rows(year, .75 ** (int(season)-1-int(year)))[0])
    tie_rate = fsum(w for _, y, w in train if y == 1)/fsum(w for _, _, w in train)
    baseline_tie = log(2*tie_rate/(1-tie_rate))
    measured = score_predictions(test, model.slope, model.tie_log_weight)
    baseline = score_predictions(test, 0, baseline_tie)
    return {"available": True, "training_seasons": list(model.training_seasons),
            "holdout_season": season, "predictor_season": source["predictor_season"],
            "predictor_cutoff": source["predictor_cutoff"],
            "excluded_games": source["excluded_new_teams_games"],
            "model": measured, "baseline": baseline,
            "log_loss_improvement": baseline["log_loss"]-measured["log_loss"],
            "scope": "Tests the unadjusted probability model with prior-season ratings. Manual assumptions, strength overrides, and the planning blend are not validated by this check. Each game contributes two team perspectives to calibration; those perspectives are not independent games.",
            "note": diagnostics["note"]}


def planning_model(games, ratings, config):
    if config.get("probability_model") == "historical":
        return historical_model(config["season"])[0]
    return OutcomeModel.fit(games, ratings)


if __name__ == "__main__":
    entries = {season: fit_historical(season) for season in ("2024", "2025")}
    ARTIFACT.write_text(json.dumps(entries, indent=2, allow_nan=False)+"\n")
    for year, entry in entries.items():
        print(year, entry["diagnostics"])
