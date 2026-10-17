"""Replay the planner's default probability inputs before a held-out season.

This evaluates probability forecasts, not counterfactual schedule choices or
the NPI of a future division whose other games have not been played yet.
"""

from datetime import datetime
from functools import lru_cache
import json

from .seasons import PLANNING_WEIGHTS, load_season, planning_ratings
from .temporal_model import historical_accuracy, historical_model, score_predictions


def planning_test_rows(season):
    prior = str(int(season)-1)
    strengths = planning_ratings(prior)  # The same blend and missing-team rules as the app.
    current, _, games = load_season(season)
    years = [str(int(prior)-i) for i in range(3)] if prior in ('2024', '2025') else [prior]
    weights = PLANNING_WEIGHTS if len(years) == 3 else (1.0,)
    sources = [{'season': year, 'weight': weight,
                'cutoff': load_season(year)[0]['source']['cutoff']}
               for year, weight in zip(years, weights)]
    dates = [datetime.strptime(row[1], '%Y-%m-%d' if row[1][:4].isdigit() else '%m-%d-%Y').date()
             for row in current['games']]
    first_game = min(dates)
    if any(datetime.fromisoformat(source['cutoff']).date() >= first_game for source in sources):
        raise ValueError('Every planning input must be available before the first test game')
    rows = [((strengths[g.team_a]-strengths[g.team_b])/10,
             ('win', 'tie', 'loss').index(g.result_a), 1.0)
            for g in games if g.team_a in strengths and g.team_b in strengths]
    return rows, sources, len(games)-len(rows)


@lru_cache(maxsize=4)
def planning_backtest(season):
    if season not in ('2024', '2025'):
        return {'available': False, 'reason': 'A prior training period and a later test season are required. Choose 2024 or 2025.'}
    model, _ = historical_model(season)
    if any(int(year) >= int(season) for year in model.training_seasons):
        raise ValueError('Test-season outcomes cannot enter probability fitting')
    rows, sources, excluded = planning_test_rows(season)
    comparison = historical_accuracy(season)
    scores = score_predictions(rows, model.slope, model.tie_log_weight)
    return {'available': True, 'holdout_season': season,
            'as_of_season': str(int(season)-1), 'training_seasons': list(model.training_seasons),
            'strength_sources': sources, 'complete_three_season_blend': len(sources) == 3,
            'excluded_games': excluded, 'model': scores,
            'single_season_model': comparison['model'], 'baseline': comparison['baseline'],
            'log_loss_improvement': comparison['baseline']['log_loss']-scores['log_loss'],
            'scope': 'Uses the same strength-building function and probability parameters as the planner at 1.00×, anchored before the test season. Missing-team weights are renormalized by that same function. No manual outcomes, strength overrides, or test-season ratings enter these predictions.',
            'limitations': 'Checks game probabilities only. It does not validate the NPI of unplayed schedules, scheduling choices, roster changes, or user assumptions. Each calibration game has two team perspectives; these are not independent games. The 2024 replay uses the app’s one-snapshot fallback because the earlier blend is unavailable.'}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Read-only planning probability backtest')
    parser.add_argument('--season', choices=['2024', '2025'], default='2025')
    print(json.dumps(planning_backtest(parser.parse_args().season), indent=2, allow_nan=False))
