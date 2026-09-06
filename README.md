# NCAA Division III Men's Soccer NPI Schedule Model

Schedule Lab compares nonconference schedules for Amherst men's soccer using
the NCAA National Power Index. It simulates game outcomes and recalculates NPI
across all 407 eligible teams in the October 27, 2024 dataset.

The calculations reproduce the published ratings within 0.001. Future game
probabilities are estimates; the results depend on the input assumptions.

## Interactive Schedule Lab

Double-click **Start Schedule Lab.command**, or run:

```bash
python3 scripts/launch_app.py
```

The app opens at `http://127.0.0.1:8765`. On a fresh checkout, install the
frontend dependencies first with `cd web && npm ci` (Node.js 22.13+ and npm).
The launcher builds the frontend if needed; subsequent launches reuse it.
After changing frontend source, run `npm run build` from `web/` and refresh.
The model/API uses only Python's standard library. No account, credentials,
remote repository, or hosted service is needed.

Start with **Opponent explorer**: select a real team or enter a rating to see
the separate win/tie/loss impacts against the conference slate. This instant
view holds opponent ratings fixed and uses the most probable unlocked conference
outcomes; it is a diagnostic, not a division-wide forecast.

In **Schedule planner**, add named candidates, click their names to edit recent
ratings or outcome probabilities, or switch to rating/rank bands. Check the
candidates to include and pin any must-play games. Set the open slots and
simulation detail, then choose **Compare schedules**. Every sampled season
converges the full division. Click the resulting schedule cards to compare
their means, P10–P90 season ranges, sampling uncertainty, and opponent risk/reward.
The calculation can be cancelled; changing inputs marks older results as stale.
Download results as full-precision JSON from the comparison panel.

This remains a **2024 historical planning replay**, not a current-season forecast.
Recent NPI inputs affect provisional pregame probabilities, not the fixed point
of the historical schedule graph. Rating and ordinal rank are different scales.
The real export's ratings span 35.321–62.061; higher rating bands have no real
profiles to simulate. See the app's **Model & assumptions** view before using
its rankings for decisions. Saved reference results are shown only when an
existing local report matches the reference inputs and source hash; otherwise
run a comparison to generate results.

The loopback-only server serves only the built frontend, never the project
directory. Plans and calculation jobs stay in memory; refreshing the browser
resets inputs. Logs and local reports are ignored by Git. For development,
run `python3 -m npi_model.app_server` from the project root and `npm run dev`
from `web/`; Vite proxies API requests to the Python model. The local build
uses Tailwind's pure-JavaScript compiler because the native CSS adapter stalled
on this host. Installed accessible Shadcn/Base UI primitives are retained.

Validation: the Python regression suite covers the real division and API logic;
the frontend build type-checks TypeScript. HTTP smoke checks cover static assets,
validation, exploration, a real comparison, cancellation, and origin restrictions.
Browser interaction and visual checks have not been performed.

## Render deployment

The repository includes `render.yaml` for a free Docker web service. In Render,
create a Blueprint from this repository and select `main`. The Docker build
compiles the frontend and runs the Python API with Gunicorn. The public address
comes from Render's `RENDER_EXTERNAL_URL`; no API key or model service is needed.
For another host, set `PUBLIC_ORIGIN` to the full HTTPS origin and provide `PORT`.

The hosted app is a public demo with session-separated results, not a private
login-protected site. A signed, secure cookie limits access to each browser's
jobs. The server keeps at most eight jobs in memory and runs one comparison at
a time. Jobs stop at the next progress update after twenty minutes. Reloads,
restarts, and free-service sleep can lose results; export anything worth keeping.
The app starts with Quick exploration settings on the hosted version.

Render's free service sleeps after fifteen minutes without traffic and can take
about a minute to start again. Large comparisons may be slow on shared free
compute. See [Render's free-service limits](https://render.com/docs/free).
Automatic deploys are disabled so a source push cannot interrupt a coach's run.

The image includes the reviewed division fixture, model code, and built frontend.
Raw Excel files, private inputs, local reports, credentials, and Git metadata are
excluded from the build context. The production process runs as a non-root user.
Host/origin checks, session ownership, and security headers are tested separately
from the mathematical model. No account registration or persistent storage is added.

Install the hosted dependencies and run the full tests with:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Use exactly one Gunicorn worker while jobs are stored in memory. Multiple workers
would have independent queues and sessions; horizontal scaling needs a shared job
store first.

## Single-game value

For a win, the result value is 100; for a loss, it is 0.

```text
base value = 0.15 × result value + 0.85 × opponent NPI

quality win bonus = 0.75 × (opponent NPI − 54)
                    only for a win when opponent NPI > 54

game value = base value + quality win bonus
```

The calculator returns each component and the total without rounding.

## Set up

The Python model requires Python 3.11 or later and has no third-party runtime
dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Run a calculation from the command line:

```bash
python -m npi_model game --result win --opponent-npi 55
```

Expected breakdown:

```text
Result component:       15.000
Opponent NPI component: 46.750
Quality win bonus:      0.750
Game value:             62.500
```

### Example values and precision

Using the rounded opponent NPIs in the examples:

| Result | Opponent NPI | Calculation | Game value |
|---|---:|---|---:|
| Loss | 66.0 | `0 + 0.85 × 66` | 56.100 |
| Win | 51.5 | `15 + 0.85 × 51.5` | 58.775 |
| Win | 55.0 | `15 + 0.85 × 55 + 0.75 × 1` | 62.500 |

The first two differ slightly from 56.08 and 58.757 because the opponent NPIs
were described approximately. Those observed values imply unrounded opponent
NPIs of about 65.9765 and 51.4788, respectively. Calculations use full precision;
rounding applies only to displayed values.

The arithmetic and schedule-forecasting code are in separate modules.

## Team-season aggregation

The NCAA does not simply average every game. Each result becomes one or two
weighted components:

| Result | Win component | Loss component |
|---|---:|---:|
| Win | 1.0 | 0.0 |
| Loss | 0.0 | 1.0 |
| Tie | 0.5 | 0.5 |

The win and loss halves of a tie are evaluated independently. The win half uses
the same win value and quality-win bonus as a full win, but at half weight. The
loss half uses the normal loss value at half weight.

Aggregation proceeds as follows:

1. Sort win components and loss components separately from highest unit game
   value to lowest.
2. Start with every loss component in the running weighted average.
3. Add win components in order. Retain a win if it raises the running NPI. A
   lowering win is still retained when needed to reach 10 win-equivalents; the
   boundary component can be partially retained.
4. Recheck loss components in order. Remove a loss if keeping it raises NPI.
   There is no minimum number of retained losses.
5. A team with no win component receives 85% of its lowest-rated opponent's
   NPI. The published adjusted record for this case is `0.0-0.0`.

A weak win can be excluded after the minimum is met. A loss to an exceptionally
strong opponent can also be excluded if including it would raise NPI.

The implementation is in `npi_model/season_npi.py`. Like the game-value module,
it performs no internal rounding.

### Verification against the NCAA export

The regression fixture was extracted from `NCAA Statistics.xlsx`, SHA-256
`40e308e6526b036cc797557b6e84774e93af5fd7a78373f7e2c8432b41c90a93`, and
combined with the schools' official schedules through October 27, 2024.

| Team | DIII record | Calculated NPI | Published NPI | Calculated adjusted W-L |
|---|---:|---:|---:|---:|
| Mary Washington | 15-0-1 | 62.061367 | 62.061 | 10.0-0.5 |
| Dickinson | 13-1-3 | 57.655069 | 57.655 | 10.5-2.5 |
| Rutgers-Newark | 8-6-4 | 52.573169 | 52.573 | 10.0-7.0 |
| Trinity (CT) | 2-12 | 47.614650 | 47.615 | 2.0-7.0 |
| Warren Wilson | 0-5 | 39.998450 | 39.999 | 0.0-0.0 |

Every reconstructed value is within `0.001` of the published value, and all
five adjusted records match exactly. The small NPI differences are expected:
the export exposes opponent NPIs to only three decimals, while the NCAA system
calculated with hidden full-precision values.

## Division-wide convergence

The implementation in `npi_model/division_npi.py` builds the full eligible-team
schedule graph and performs simultaneous (Jacobi) passes. During a pass, every
team uses only opponent NPIs from the previous pass. Newly calculated values are
not visible until the next pass, so the answer cannot depend on team ordering.

If no initial ratings are supplied, the solver uses the NCAA-style initial
seed: 85% of the mean adjusted win percentage of each team's opponents, with no
result component or quality-win bonus on that seed calculation. Custom seeds,
including the published ratings, can also be supplied. Iteration stops only
when the largest absolute change anywhere in the division is at or below the
requested tolerance. No value is rounded internally.

```python
from npi_model import DivisionGame, iterate_division_npi

games = [
    DivisionGame("Team A", "Team B", "win"),
    DivisionGame("Team B", "Team C", "tie"),
    DivisionGame("Team C", "Team A", "loss"),
]

result = iterate_division_npi(games, convergence_tolerance=1e-10)
print(result.ratings)
print(result.iterations)
```

Pass `eligible_teams=` when the source includes teams that have records but are
not NPI-eligible. A game is included only when both participants are in that
set.

### Full-division source reconciliation

The real-data fixture in
`tests/data/ncaa_2024_10_27_division.json` combines the supplied official export
with the archived NCAA daily Division III men's soccer scoreboards through
October 27, 2024.

- The workbook contains 409 teams and 3,160 D-III games after three archived
  scoreboard defects are reconciled against official team records.
- Carlow and Penn St Brandywine have D-III records but blank published NPIs.
  Excluding those two ineligible teams and all incident games leaves the actual
  NPI graph: 407 teams and 3,137 games.
- With the published opponent NPIs as one-pass inputs, all 407 calculated NPIs
  are within `0.001` and all 407 published adjusted W-L records match exactly.
- At a full-precision convergence tolerance of `1e-10`, all 407 stable ratings
  remain within `0.001` of the published values. The largest difference is
  `0.000499101` for TCNJ, consistent with the export's three-decimal display.

| Initial seed | Iterations to `1e-10` | Maximum difference from published NPI |
|---|---:|---:|
| Published three-decimal NPIs | 83 | 0.000499101 |
| Opponent win percentage (default) | 214 | 0.000499101 |
| Constant 50 | 185 | 0.000499101 |
| Constant 0 | 225 | 0.000499101 |

The four final vectors differ from one another by less than `1e-8`, so the
stable answer is not materially sensitive to these starting seeds. The seed
does affect only how quickly the iteration reaches the fixed point.

## Schedule simulation

`npi_model/schedule_simulator.py` projects a proposed schedule without freezing
opponent ratings:

1. Remove every background game involving the target team. Because each game
   is one shared graph edge, this also removes the reciprocal result from the
   opponent.
2. Insert the proposed conference and nonconference games for one explicit
   outcome scenario.
3. Reconverge all 407 eligible teams simultaneously.
4. Report the target NPI and iteration diagnostics. For multiple scenarios,
   also report the minimum, maximum, and probability-weighted expected NPI.

```python
from npi_model import (
    NamedScheduleScenario,
    ScheduledOpponent,
    project_schedule_scenarios,
)

candidate_name = "<one opponent from the coach-provided pool>"
schedule = [
    ScheduledOpponent("Williams", "conference"),
    ScheduledOpponent(candidate_name, "nonconference"),
]
scenarios = [
    NamedScheduleScenario("both wins", ("win", "win")),
    NamedScheduleScenario("both losses", ("loss", "loss")),
]

projection = project_schedule_scenarios(
    background_games,
    target_team="Amherst",
    scheduled_opponents=schedule,
    scenarios=scenarios,
    eligible_teams=eligible_teams,
    initial_ratings=published_ratings,
)
```

Independent win/tie/loss probabilities can be expanded with
`project_schedule_distribution`. This is exact rather than an approximation:
each joint result scenario reconverges the whole division, and expected NPI is
the probability-weighted mean of those converged scenarios. Because exact
enumeration grows exponentially, the API refuses expansions above a configurable
scenario limit. The schedule optimizer uses sampling for a 15-game future slate; it does not
substitute an average result into the nonlinear season calculation.

The real-data simulator regression removes Amherst's historical schedule from
the verified graph, reinserts the same opponents and results, reconverges the
division, and restores Amherst's published NPI within `0.001`.

## Schedule comparison

Run from this source checkout (the default graph is the reviewed fixture under
`tests/data`; an installed package needs an explicit `--graph` path):

```bash
python -m npi_model plan --output reports/amherst-default
```

This writes a readable Markdown report and full-precision JSON. Existing reports
are protected unless `--overwrite` is supplied. A default run makes hundreds of
division solves and can take several minutes. For an exploratory smoke run:

```bash
python -m npi_model plan --samples 4 --validation-samples 8 --insight-samples 2 --output reports/quick
```

Small sample counts check the workflow, not the reliability of the ordering.
`reports/` and `planning_inputs/` are ignored because actual coach plans may be private.

### Opponent strength

The demonstration is a **historical planning replay**, not a 2026 forecast. All
other teams' games/results come from the verified October 27, 2024 graph. Amherst's
old games are removed from both sides and replaced by the proposed slate.
Adding a game changes the opponent's schedule too, and every scenario reconverges
all 407 teams. We do not know which other game the opponent might remove to make
room; their other historical games are held fixed.

Ten conference opponents are fixed by default: Bates, Bowdoin, Colby, Connecticut
Col., Hamilton, Middlebury, Trinity (CT), Tufts, Wesleyan (CT), and Williams. These
come from [Amherst's 2024 schedule](https://athletics.amherst.edu/schedule.aspx?path=msoc&season=2024),
including Trinity after the export cutoff. “Fixed” locks the opponent, **not** a
win/loss result. All ten outcomes are uncertain unless explicitly supplied.
Nonconference choices remain open regardless of the current calendar date.

The default seven-team pool contains the five historical nonconference opponents
(Babson, Emerson, Manhattanville, Suffolk, WPI) plus Springfield and Western New
Eng. as illustrative regional alternatives with real division profiles. This is
not a coach-approved candidate list, and dates, travel, and availability are not
verified. Five slots produce `choose(7, 5) = 21` combinations.

A candidate's optional `recent_npi` changes **pregame win/tie/loss probabilities**.
It does not pin their final rating. A new starting seed alone cannot change the
historical graph's stable NPI. To project a genuinely different division season,
supply an updated division result graph using `--graph`. An unfamiliar team with
only an NPI number has no schedule profile in the division graph and is rejected.

### Outcome probabilities

The provisional outcome model is fitted to the real 3,137-game graph. Let
`d = (team NPI - opponent NPI) / 10`. Win, tie, and loss probabilities are the
normalized exponentials of `(b*d/2, a, -b*d/2)`. Swapping teams swaps win and loss
probabilities, while preserving the tie probability.

This fit uses end-period ratings that contain those same results. Its training
and retrospective holdout log-loss metrics therefore have **rating leakage**;
they are not evidence of prospective forecast accuracy. The default strength
coefficient is multiplied by `0.5` to soften this strong retrospective relationship.
That is an explicit heuristic, not a calibrated confidence interval. Coach-supplied
probabilities or pregame ratings from held-out seasons are preferable.

For each sampled season:

1. Independently draw win/tie/loss for each unlocked game.
2. Build the reciprocal division graph for those actual categorical outcomes.
3. Reconverge it using the verified season rule.
4. Save Amherst's resulting NPI without rounding.

Average the resulting NPIs, **not** the input game values. Retained-win thresholds,
excluded losses, ties, and recursive feedback make the season calculation nonlinear.
No injury, roster, travel, or shared team-form uncertainty is included yet.

### Ranking and uncertainty

Each opponent has a reproducible random stream derived from the run seed and
team name. Shared opponents receive the same random draws across candidate
schedules, reducing noise in paired differences. The default uses 24 screening
draws per schedule, independently checks the leading six with 64 new draws each,
then displays the leading three by validation mean. This is a sampled ranking,
not a certified global optimum; screening can miss an alternative.

The report distinguishes:

- **P10–P90:** the simulated season-outcome spread.
- **Mean standard error / approximate 95% interval:** Monte Carlo error in the
  estimated expectation, conditional on this model. Not model uncertainty.
- **Paired gap below the leader:** whether a small mean difference is large
  relative to its simulation noise. More draws can change close rankings.
- **All-unlocked-win / all-unlocked-loss stress cases:** useful scenarios, not
  proven extrema of this nonlinear system.

The fixed-only slate is a clearly labeled comparison baseline, not a recommendation
to play fewer games. Each opponent also receives forced win, tie, and loss
projections. Its marginal lift is measured against the **same schedule with that
game omitted**, holding other draws constant. These impacts depend on the rest of
the slate and are not additive. A negative win lift exposes a weak win that must
still be retained; a small loss lift exposes limited downside after aggregation.
Standalone one-slot impacts and five-slot contextual impacts are both reported.

### Named opponents and bands

The default tiers are sub-40, 40–55, 55–75, 75–100, and 100+. Intervals include
the lower boundary and exclude the upper boundary. Ratings in this export range
from 35.321 to 62.061, so the 75–100 and 100+ rating bands are empty.

```bash
python -m npi_model plan --mode bands --band-scale rating --output reports/rating-bands
python -m npi_model plan --mode bands --band-scale rank --output reports/rank-bands
```

Rating mode selects up to two actual profiles per nonempty tier (low/high endpoints
by default). Rank mode is a separate, explicit option: positions 75–99 mean the
75th through 99th teams, not NPI values of 75–99. Ranks are ordinal positions sorted
by displayed rating with alphabetical ties, not reconstructed hidden NCAA tie-breaks.
Changing the scale does not change the calculation; it changes which teams enter
the pool. With ten rank-band representatives, five slots create 252 combinations,
so a rank-band run takes longer than the seven-team demonstration.

Both modes show the bands, named representatives, and their individual win/loss
impacts. Representative impact ranges are not averages over all teams in a tier.
Unavailable rating bands additionally get clearly separated **fixed-rating
arithmetic probes**, not division forecasts. Inputs above 100 are outside the
verified calculator's domain; no value is invented for the open-ended 100+ tier.

### Custom inputs and sensitivity

Print the editable full defaults:

```bash
python -m npi_model planning-config
```

Save edited JSON in `planning_inputs/coach.json`, then run:

```bash
python -m npi_model plan --config planning_inputs/coach.json --output reports/coach
```

The JSON is merged with defaults at the **top level**; lists replace entire lists.
`examples/named-opponents.json` keeps the illustrative seven-team pool;
`examples/rank-band-75-100.json` compares three real profiles for one open slot
from ordinal positions 75–99. Both inherit the full ten-opponent conference slate.
For example:

```bash
python -m npi_model plan --config examples/rank-band-75-100.json --output reports/one-rank-band
```

Examples of individual list entries:

```json
{
  "fixed_games": [
    {"team": "Williams", "category": "conference", "result": "tie"},
    {"team": "Tufts", "category": "conference"}
  ],
  "candidates": [
    {"team": "Babson", "recent_npi": 55.123456789},
    {"team": "WPI", "probabilities": {"win": 0.5, "tie": 0.2, "loss": 0.3}}
  ],
  "open_slots": 1,
  "required": [],
  "excluded": []
}
```

This abbreviated example deliberately replaces the ten-game conference list;
keep all ten in the real configuration. Probabilities are from the target team's
perspective and must sum to one. A locked result cannot also have probabilities.
`required` forces candidates into every combination; `excluded` removes candidates.
An insufficient pool, duplicate opponent, unknown team, or combination count above
`max_combinations` fails explicitly; the optimizer never silently truncates the search.

To compare the softened assumption with the full retrospective strength fit:

```bash
python -m npi_model plan --slope-scale 0.5 --output reports/soft
python -m npi_model plan --slope-scale 1.0 --output reports/steep
```

Keep seeds and sample counts equal for useful comparisons. Raise `--samples`,
`--validation-samples`, and `--insight-samples` before making a consequential
decision. Once pre-season ratings and multiple seasons are available, validate
probabilities on entirely held-out seasons and model division-wide future outcomes.

### Code map and verification

| Module | Responsibility |
|---|---|
| `outcome_model.py` | Transparent provisional win/tie/loss probability fit |
| `planning.py` | Real graph loading, editable defaults, named and band inputs |
| `fast_division.py` | Allocation-light version of the verified simultaneous solver |
| `schedule_optimizer.py` | Full-division sampling, paired ranking and conditional impacts |
| `planning_report.py` | Human-readable output; display rounding only |
| `tests/test_schedule_optimizer.py` | Real-data solver equivalence, probabilities, input safeguards, ranking and sensitivity mechanics |

The fast solver reproduces every reference rating **exactly** on the unchanged
407-team graph at `1e-10`, including the 83 iterations from published seeds. Tests
also change a real Amherst result and compare all 407 ratings across multiple
seeds, check win/tie/loss conditional projections against the original solver,
and restore the historical Amherst NPI within `0.001`. Planning defaults stop
when the largest division-wide pass change is at most `1e-8`—well below display
precision. This stopping residual is not asserted to be a general error bound
for every conceivable modified graph. Nonconvergence raises an error.
