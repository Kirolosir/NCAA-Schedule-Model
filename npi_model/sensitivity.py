"""Compare exactly the same shortlist under explicit team-form assumptions."""

from dataclasses import replace
from math import isfinite

from .planning import candidate_schedules, parse_plan
from .schedule_optimizer import ScheduleEvaluator, summarize
from .seasons import planning_ratings
from .temporal_model import planning_model


def validate_shortlist(config, ratings, schedules, shift):
    if type(shift) not in (int, float) or not isfinite(shift) or not .25 <= shift <= 10:
        raise ValueError('Strength change must be between 0.25 and 10 NPI points')
    if not isinstance(schedules, list) or not 1 <= len(schedules) <= 5:
        raise ValueError('Compare between one and five displayed schedules')
    _, _, candidates, _ = parse_plan(config, ratings)
    allowed = {plan['opponents'] for plan in candidate_schedules(
        candidates, config['open_slots'], config['required'], config['preferred'],
        max_travel_miles=config['max_total_travel_miles'], max_cost=config['max_total_cost'])}
    selected = []
    for schedule in schedules:
        if (not isinstance(schedule, (list, tuple)) or any(not isinstance(team, str) for team in schedule)
                or len(set(schedule)) != len(schedule) or tuple(sorted(schedule)) not in allowed):
            raise ValueError('Every sensitivity option must be a valid schedule for this plan')
        selected.append(tuple(sorted(schedule)))
    if len(set(selected)) != len(selected):
        raise ValueError('Sensitivity options must be distinct')
    return selected


def compare_assumptions(games, ratings, config, schedules, shift=3.0, *, progress=None):
    schedules = validate_shortlist(config, ratings, schedules, shift)
    target, fixed, candidates, _ = parse_plan(config, ratings)
    strengths = planning_ratings(config['season'])
    center = config.get('target_recent_npi', strengths[target])
    fitted = planning_model(games, ratings, config)
    model = replace(fitted, slope=fitted.slope*config['probability_slope_scale'])
    samples = max(8, config['validation_samples'])
    # Reuse the main finalist draws so the baseline is directly comparable.
    seed = config['seed']+1000003
    profiles, solves = [], 0
    checkpoint = getattr(progress, 'checkpoint', None)
    for index, (key, label, offset) in enumerate((('cautious', 'Lower team form', -shift),
                                               ('baseline', 'Entered assumptions', 0),
                                               ('optimistic', 'Higher team form', shift))):
        strength = min(100, max(0, center+offset))
        evaluator = ScheduleEvaluator(games, ratings, target, fixed, candidates, model,
                                      target_recent_npi=strength, probability_ratings=strengths,
                                      tolerance=config['convergence_tolerance'], checkpoint=checkpoint)
        values = [evaluator.sample(teams, samples=samples, seed=seed) for teams in schedules]
        means = [summarize(row)['mean'] for row in values]
        leader = max(range(len(means)), key=lambda i: means[i])
        order = sorted(range(len(means)), key=lambda i: (-means[i], i))
        rows = [{'option': i+1, 'opponents': list(teams), 'rank': order.index(i)+1,
                 'projection': summarize(values[i]),
                 'target_hit_rate': sum(value >= config['target_npi'] for value in values[i])/samples,
                 'gap_from_leader': summarize([a-b for a, b in zip(values[leader], values[i])])}
                for i, teams in enumerate(schedules)]
        profiles.append({'key': key, 'label': label, 'target_strength': strength,
                         'effective_shift': strength-center, 'schedules': rows})
        solves += evaluator.solves
        if progress:
            progress(f'Assumptions {index+1}/3: {label}')
    summary = []
    for i, teams in enumerate(schedules):
        rows = [profile['schedules'][i] for profile in profiles]
        summary.append({'option': i+1, 'opponents': list(teams),
                        'lowest_profile_mean': min(row['projection']['mean'] for row in rows),
                        'highest_profile_mean': max(row['projection']['mean'] for row in rows),
                        'largest_gap_to_leader': max(row['gap_from_leader']['mean'] for row in rows),
                        'first_place_profiles': sum(row['rank'] == 1 for row in rows)})
    consistent = min(summary, key=lambda row: (row['largest_gap_to_leader'], -row['lowest_profile_mean'], row['option']))
    return {'config': config, 'profiles': profiles, 'schedules': summary,
            'most_consistent_option': consistent['option'], 'samples_per_profile': samples,
            'strength_shift': shift, 'division_solves': solves,
            'scope': 'Compares this displayed shortlist only. Lower and higher form change inferred win/draw/loss chances by shifting team strength; the division NPI graph is unchanged. Locked results and every entered probability override stay fixed. The same random draws are paired across options and profiles.',
            'note': 'The profile range is a what-if range of mean estimates, not a confidence interval. Baseline draws reuse the main comparison seed; this check uses at least eight samples, so it can differ when the main run used fewer. Rankings can change with sampling noise. The paired 95% intervals measure simulation error only; these form assumptions are not learned uncertainty bounds.'}
