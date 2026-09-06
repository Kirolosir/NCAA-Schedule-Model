"""Allocation-light Jacobi solver, regression checked against division_npi."""

from math import fsum, isfinite

from .division_npi import (
    DivisionNPIResult, NPIConvergenceError, _build_schedules, _validate_ratings,
)


class CompiledDivision:
    def __init__(self, games, eligible_teams):
        self.teams, schedules = _build_schedules(games, eligible_teams)
        indices = {t: i for i, t in enumerate(self.teams)}
        self.schedules = []
        for team in self.teams:
            wins, losses = [], []
            for opponent, result in schedules[team]:
                i = indices[opponent]
                if result != "loss":
                    wins.append((i, 0.5 if result == "tie" else 1.0))
                if result != "win":
                    losses.append((i, 0.5 if result == "tie" else 1.0))
            self.schedules.append((wins, losses))

    def solve(self, initial_ratings, *, tolerance=1e-8, max_iterations=10000,
              minimum_retained_wins=10.0):
        if not isfinite(tolerance) or tolerance <= 0:
            raise ValueError("tolerance must be finite and positive")
        if not isinstance(max_iterations, int) or max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")
        if not isfinite(minimum_retained_wins) or minimum_retained_wins < 0:
            raise ValueError("minimum_retained_wins must be finite and nonnegative")
        ratings = _validate_ratings(self.teams, initial_ratings, label="initial_ratings")
        previous = [ratings[t] for t in self.teams]
        history = []
        for iteration in range(1, max_iterations + 1):
            win_values = [15.0 + .85*x + .75*max(x-54.0, 0.0) for x in previous]
            loss_values = [.85*x for x in previous]
            current = []
            for wins, losses in self.schedules:
                if not wins:
                    current.append(min(loss_values[i] for i, _ in losses))
                    continue
                # Stable sorting by value preserves the reference's order at ties.
                w = sorted(((win_values[i], weight) for i, weight in wins),
                           key=lambda x: x[0], reverse=True)
                losses_sorted = sorted(((loss_values[i], weight) for i, weight in losses),
                                       key=lambda x: x[0], reverse=True)
                total = fsum(v*weight for v, weight in losses_sorted)
                weight_sum = fsum(weight for _, weight in losses_sorted)
                npi = total/weight_sum if weight_sum else 0.0
                kept_wins = 0.0
                for value, weight in w:
                    candidate = (total + value*weight)/(weight_sum+weight)
                    if candidate >= npi or kept_wins+weight <= minimum_retained_wins:
                        retained = weight
                    elif kept_wins >= minimum_retained_wins:
                        retained = 0.0
                    else:
                        retained = minimum_retained_wins-kept_wins
                    if retained:
                        total += value*retained
                        weight_sum += retained
                        kept_wins += retained
                        npi = total/weight_sum
                for value, weight in losses_sorted:
                    if weight_sum <= weight:
                        continue
                    candidate = (total-value*weight)/(weight_sum-weight)
                    if candidate < npi:
                        total -= value*weight
                        weight_sum -= weight
                        npi = total/weight_sum
                current.append(npi)
            if any(not isfinite(x) or x < 0 or x > 100 for x in current):
                raise NPIConvergenceError("iteration left the supported 0–100 rating domain")
            delta = max(abs(a-b) for a, b in zip(previous, current))
            history.append(delta)
            previous = current
            if delta <= tolerance:
                return DivisionNPIResult(dict(zip(self.teams, current)), iteration,
                                         delta, tolerance, tuple(history))
        raise NPIConvergenceError(f"no convergence in {max_iterations} iterations; delta={delta}")
