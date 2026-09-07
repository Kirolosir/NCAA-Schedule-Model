"""Fit prior-season ratings to subsequent games; hold the newest season out."""

from dataclasses import asdict
from functools import lru_cache
from hashlib import sha256
import json
from math import fsum, log
from datetime import datetime

from .outcome_model import OutcomeModel, _fit, _loss
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


def planning_model(games, ratings, config):
    if config.get("probability_model") == "historical":
        return historical_model(config["season"])[0]
    return OutcomeModel.fit(games, ratings)


if __name__ == "__main__":
    entries = {season: fit_historical(season) for season in ("2024", "2025")}
    ARTIFACT.write_text(json.dumps(entries, indent=2, allow_nan=False)+"\n")
    for year, entry in entries.items():
        print(year, entry["diagnostics"])
