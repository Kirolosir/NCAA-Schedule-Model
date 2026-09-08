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

    def _ordered_schedules(self, order):
        ranks = [0]*len(order)
        for rank, team in enumerate(order):
            ranks[team] = rank
        return [(tuple(sorted(wins, key=lambda item: ranks[item[0]])),
                 tuple(sorted(losses, key=lambda item: ranks[item[0]])))
                for wins, losses in self.schedules]

    def solve(self, initial_ratings, *, tolerance=1e-8, max_iterations=10000,
              minimum_retained_wins=10.0, exact=True, checkpoint=None):
        if not isfinite(tolerance) or tolerance <= 0:
            raise ValueError("tolerance must be finite and positive")
        if not isinstance(max_iterations, int) or max_iterations < 1:
            raise ValueError("max_iterations must be a positive integer")
        if not isfinite(minimum_retained_wins) or minimum_retained_wins < 0:
            raise ValueError("minimum_retained_wins must be finite and nonnegative")
        ratings = _validate_ratings(self.teams, initial_ratings, label="initial_ratings")
        previous = [ratings[t] for t in self.teams]
        if not exact:
            return self._solve_planning(previous, tolerance, max_iterations,
                                        minimum_retained_wins, checkpoint)
        history = []
        for iteration in range(1, max_iterations + 1):
            if checkpoint:
                checkpoint()
            win_values = [15.0 + .85*x + .75*max(x-54.0, 0.0) for x in previous]
            loss_values = [.85*x for x in previous]
            current = []
            for wins, losses in self.schedules:
                if not wins:
                    current.append(min(loss_values[i] for i, _ in losses))
                    continue
                w = sorted(((win_values[i], weight) for i, weight in wins),
                           key=lambda item: item[0], reverse=True)
                losses_sorted = sorted(((loss_values[i], weight) for i, weight in losses),
                                       key=lambda item: item[0], reverse=True)
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

    def _solve_planning(self, previous, tolerance, max_iterations,
                        minimum_retained_wins, checkpoint=None):
        history = []
        previous_order = None
        ordered_schedules = None
        for iteration in range(1, max_iterations + 1):
            if checkpoint:
                checkpoint()
            order = tuple(sorted(range(len(previous)), key=previous.__getitem__, reverse=True))
            if order != previous_order:
                ordered_schedules = self._ordered_schedules(order)
                previous_order = order
            current = self._planning_pass(previous, minimum_retained_wins, ordered_schedules)
            delta = max(abs(a-b) for a, b in zip(previous, current))
            history.append(delta)
            previous = current
            if delta <= tolerance:
                return DivisionNPIResult(dict(zip(self.teams, current)), iteration,
                                         delta, tolerance, tuple(history))
        raise NPIConvergenceError(f"no convergence in {max_iterations} iterations; delta={delta}")

    def estimate(self, initial_ratings, *, iterations=8,
                 minimum_retained_wins=10.0, checkpoint=None):
        if not isinstance(iterations, int) or iterations < 1:
            raise ValueError("iterations must be a positive integer")
        ratings = _validate_ratings(self.teams, initial_ratings, label="initial_ratings")
        previous = [ratings[t] for t in self.teams]
        previous_order = None
        ordered_schedules = None
        for _ in range(iterations):
            if checkpoint:
                checkpoint()
            order = tuple(sorted(range(len(previous)), key=previous.__getitem__, reverse=True))
            if order != previous_order:
                ordered_schedules = self._ordered_schedules(order)
                previous_order = order
            previous = self._planning_pass(previous, minimum_retained_wins, ordered_schedules)
        return dict(zip(self.teams, previous))

    def _planning_pass(self, previous, minimum_retained_wins, schedules=None):
        win_values = [15.0 + .85*x + .75*max(x-54.0, 0.0) for x in previous]
        loss_values = [.85*x for x in previous]
        current = []
        for wins, losses in schedules or self.schedules:
            if not wins:
                current.append(min(loss_values[i] for i, _ in losses))
                continue
            ordered_wins = wins if schedules else sorted(wins, key=lambda item: previous[item[0]], reverse=True)
            ordered_losses = losses if schedules else sorted(losses, key=lambda item: previous[item[0]], reverse=True)
            total = 0.0
            weight_sum = 0.0
            for i, weight in ordered_losses:
                total += loss_values[i]*weight
                weight_sum += weight
            npi = total/weight_sum if weight_sum else 0.0
            kept_wins = 0.0
            for i, weight in ordered_wins:
                value = win_values[i]
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
            for i, weight in ordered_losses:
                if weight_sum <= weight:
                    continue
                value = loss_values[i]
                candidate = (total-value*weight)/(weight_sum-weight)
                if candidate < npi:
                    total -= value*weight
                    weight_sum -= weight
                    npi = total/weight_sum
            current.append(npi)
        return current
