"""Retrospective outcome probabilities; end-period ratings include the fitted results."""

from dataclasses import dataclass
from math import exp, fsum, isfinite, log

from .schedule_simulator import OutcomeProbabilities


def _probabilities(d, slope, tie_log_weight):
    logits = (slope*d/2, tie_log_weight, -slope*d/2)
    high = max(logits)
    values = [exp(x-high) for x in logits]
    total = fsum(values)
    return tuple(x/total for x in values)


def _loss(rows, slope, tie):
    return fsum(-(row[2] if len(row) == 3 else 1)*log(max(_probabilities(row[0], slope, tie)[row[1]], 1e-300))
                for row in rows)/fsum(row[2] if len(row) == 3 else 1 for row in rows)


def _fit(rows):
    # Fixed-step coordinate search keeps the convex likelihood fit deterministic.
    slope, tie, step = 1.0, -1.0, 1.0
    score = _loss(rows, slope, tie)
    while step > 1e-6:
        options = [(slope, tie), (max(0.0, slope-step), tie),
                   (min(30.0, slope+step), tie), (slope, max(-12.0, tie-step)),
                   (slope, min(5.0, tie+step))]
        scored = [(_loss(rows, b, a), b, a) for b, a in options]
        best, b, a = min(scored)
        if best < score-1e-14:
            score, slope, tie = best, b, a
        else:
            step /= 2
    return slope, tie


@dataclass(frozen=True)
class OutcomeModel:
    slope: float
    tie_log_weight: float
    sample_count: int
    fit_log_loss: float
    constant_baseline_log_loss: float
    retrospective_holdout_log_loss: float | None
    rating_min: float
    rating_max: float
    method: str = "same_period_retrospective"
    training_seasons: tuple[str, ...] = ()
    holdout_season: str | None = None
    out_of_time_log_loss: float | None = None

    @classmethod
    def fit(cls, games, ratings):
        if not games:
            raise ValueError("at least one training game is required")
        if any(not isfinite(x) or not 0 <= x <= 100 for x in ratings.values()):
            raise ValueError("training ratings must be finite and in 0–100")
        rows = []
        for game in games:
            if game.result_a not in ("win", "tie", "loss"):
                raise ValueError("invalid training outcome")
            d = (ratings[game.team_a]-ratings[game.team_b])/10
            rows.append((d, ("win", "tie", "loss").index(game.result_a)))
        b, a = _fit(rows)
        ties = sum(y == 1 for _, y in rows)
        tie_rate = min(1-1e-9, max(1e-9, ties/len(rows)))
        baseline_a = log(2*tie_rate/(1-tie_rate))
        # End-period ratings leak results into both halves of this split.
        train = [row for i, row in enumerate(rows) if i % 5]
        test = [row for i, row in enumerate(rows) if i % 5 == 0]
        hold_b, hold_a = _fit(train or rows)
        return cls(b, a, len(rows), _loss(rows, b, a),
                   _loss(rows, 0, baseline_a), _loss(test, hold_b, hold_a),
                   min(ratings.values()), max(ratings.values()))

    def predict(self, team_npi, opponent_npi):
        if any(not isfinite(x) or not 0 <= x <= 100 for x in (team_npi, opponent_npi)):
            raise ValueError("predictive NPIs must be finite and in 0–100")
        return OutcomeProbabilities(*_probabilities(
            (team_npi-opponent_npi)/10, self.slope, self.tie_log_weight))
