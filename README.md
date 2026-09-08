# NCAA Division III Men's Soccer Schedule Lab

Schedule Lab compares possible five-game nonconference schedules for Amherst
men's soccer. The ten NESCAC games stay fixed. Each proposed schedule is scored
by projecting wins, ties, and losses, then recalculating NPI across the whole
Division III schedule graph.

[Open the hosted app](https://ncaa-schedule-lab.onrender.com)

This is a planning tool, not a prediction guarantee. Availability, venue, dates,
travel, and cost can be entered as scheduling constraints, but they do not alter
matchup odds automatically. Injuries, roster changes, and future form are not modeled.

## What the app does

- Compares named opponents or NPI/rank bands.
- Shows the effect of a win, tie, or loss against one opponent.
- Ranks five-game schedules by projected season NPI.
- Tracks every schedule against an editable target NPI.
- Supports favorite, toss-up, underdog, and custom matchup outlooks.
- Filters by required, preferred, unavailable, date, travel, and cost inputs.
- Saves and reopens planning scenarios in the current browser.
- Starts with a conservative .500 NESCAC baseline: four wins, two ties, and four losses.
- Shows a likely range so a risky schedule does not look safer than it is.
- Allows two browser tabs to run independent comparisons and cancels a run immediately.
- Keeps 2025, 2024, 2023, and 2022 as separate historical reference seasons.
- Uses full precision internally and rounds only for display.

The 2025 and 2024 seasons use published NCAA NPI values. NPI was not used for
Division III selection in 2023 or 2022, so those seasons are retrospective
reconstructions under the later rules.

## Run locally

Requirements: Python 3.11+, Node.js 22.13+, and npm.

On macOS, double-click `Start Schedule Lab.command`. To start it manually:

```bash
cd web
npm ci
npm run build
cd ..
python3 scripts/launch_app.py
```

The app opens at `http://127.0.0.1:8765`.

For frontend development, run the API and Vite in separate terminals:

```bash
python3 -m npi_model.app_server
```

```bash
cd web
npm run dev
```

## NPI rules used

For one game:

```text
base value = 0.15 × result value + 0.85 × opponent NPI
quality win bonus = 0.75 × (opponent NPI − 54)
```

The result value is 100 for a win and 0 for a loss. The bonus only applies to a
win over an opponent above 54 NPI. A tie is split into half of a win component
and half of a loss component.

Season NPI is not a simple average. Win and loss components are sorted by game
value. Lowering wins must be retained until the team reaches ten retained
win-equivalents; after that, they can be excluded. A loss can be excluded when
keeping it would raise the rating. Winless teams use 85% of their lowest-rated
opponent's NPI.

Because every opponent's rating also depends on its opponents, the division
solver updates every team simultaneously until the largest change is below the
convergence tolerance.

## Historical data

The reviewed fixtures are stored in `tests/data/`:

| File | Use |
|---|---|
| `ncaa_2025_11_09_division.json` | 2025 selection-day division snapshot |
| `ncaa_2024_10_27_division.json` | 2024 published NPI snapshot |
| `ncaa_2023_historical_division.json` | 2023 retrospective reconstruction |
| `ncaa_2022_historical_division.json` | 2022 retrospective reconstruction |
| `historical_probability_models.json` | Saved cross-season outcome fit |

Raw Excel exports are intentionally ignored. The JSON fixtures contain public
team names, ratings, records, dates, results, source URLs, and provenance hashes.
They do not contain coach correspondence, private schedules, player information,
credentials, or secrets.

The 2025 fixture contains 402 rated teams and 3,528 eligible games. The division
solver reproduces every published NPI within 0.001 from several starting seeds.
The season aggregation tests also cover winning, losing, tied, and winless teams.

Older seasons are not mixed into the recursive NPI calculation. They are used to
estimate game-outcome probabilities. The newest season remains an out-of-time
check rather than part of the probability fitting sample.

## Comparison modes

- **Quick** screens the pool with short division passes, then fully converges the
  leading shortlist to well below the displayed 0.001 precision. This is the
  default for trying ideas.
- **Standard** uses a larger sample and shortlist.
- **Thorough** fully evaluates the widest set and is intended for a final review.

The instant opponent explorer holds the rest of the division fixed. Final
schedule projections always run through division-wide convergence. Individual
game effects should not be added together because NPI is recursive and the
season aggregation can exclude some results.

## Tests

```bash
python -m unittest discover -s tests -v
cd web && npm run build
```

The tests cover the game formula, season aggregation, division convergence,
schedule simulation, ranking, all four historical seasons, API validation,
session isolation, cancellation, and hosted security checks.

## Deployment

`render.yaml` and `Dockerfile` define the Render service. The production process
uses one Gunicorn worker because calculation jobs are kept in memory. Automatic
deploys are disabled so a push cannot interrupt a coach's active comparison.

The hosted version has no login or persistent database. Results belong to one
signed browser session and disappear after a service restart. Named planning
scenarios are stored in the browser that saved them; export any result that needs
to be shared elsewhere. Render's free service may also take about a minute to wake
after being idle.

Private planning inputs belong in `planning_inputs/`, generated reports in
`reports/`, and other local source material in `local_data/`. Those directories,
Excel files, environment files, credentials, dependencies, caches, and builds are
excluded by Git and the Docker build context.

## Project layout

```text
npi_model/   NPI calculation, simulation, optimization, and API
scripts/     data import, historical rebuild, and local launcher
tests/       regression tests and reviewed historical fixtures
web/         React interface
examples/    sample planner inputs
```
