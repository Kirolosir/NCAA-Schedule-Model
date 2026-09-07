"""Human-readable planning report; rounding happens only in this display layer."""


def render_report(report):
    c = report["config"]
    fit = report["probability_model"]["fit"]
    cutoff = report.get("source", {}).get("cutoff", "unspecified date")
    lines = [f"# {report['target_team']} scheduling comparison", "",
             f"Illustrative planning replay using the supplied division graph (cutoff: {cutoff}).", "",
             f"{len(c['fixed_games'])} fixed opponents + {c['open_slots']} open slots; "
             f"{len(report['candidates'])} candidate profiles. "
             f"{len(report['screening'])} combinations screened with {c['samples']} draws each. "
             f"{len(report['validated_finalists'])} finalists validated with {c['validation_samples']} independent draws each.", "",
             "Schedules below are ordered by the validated mean. P10–P90 is simulated season spread; "
             "SE is sampling error in the mean. Close estimates can change order with more samples or different probabilities.", "",
             "| Order | Nonconference opponents | Mean NPI | P10–P90 | Mean SE | Lift vs fixed slate |",
             "|---:|---|---:|---:|---:|---:|"]
    for row in report["top_schedules"]:
        p = row["projection"]
        lines.append(f"| {row['rank']} | {', '.join(row['opponents'])} | {p['mean']:.3f} | "
                     f"{p['p10']:.3f}–{p['p90']:.3f} | {p['mean_standard_error']:.3f} | "
                     f"{row['impact_vs_fixed_slate']['mean']:+.3f} |")
    for row in report["top_schedules"]:
        lines += ["", f"## Schedule {row['rank']}: where the value and risk sit", "",
                  *row["reasoning"], "",
                  f"All unlocked results forced to wins: {row['stress_all_unlocked_wins']:.3f}; "
                  f"forced to losses: {row['stress_all_unlocked_losses']:.3f}. "
                  "These are stress cases, not mathematical bounds.", "",
                  "| Opponent | P(win/tie/loss) | NPI if win | Win lift | Tie lift | Loss lift | Win–loss swing |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for risk in row["opponent_impacts"]:
            p = risk["probabilities"]
            lines.append(f"| {risk['team']} | {p['win']:.1%}/{p['tie']:.1%}/{p['loss']:.1%} | "
                         f"{risk['win']['npi']['mean']:.3f} | {risk['win']['impact']['mean']:+.3f} | "
                         f"{risk['tie']['impact']['mean']:+.3f} | {risk['loss']['impact']['mean']:+.3f} | "
                         f"{risk['swing_win_minus_loss']:.3f} |")
        gap = row["paired_gap_from_leader"]
        lines += ["", f"Paired gap below leader: {gap['mean']:.3f} "
                  f"(sampling SE {gap['mean_standard_error']:.3f}). "
                  f"Opponent impacts use {c['insight_samples']} common draws against the same slate with that game omitted."]
        if row["rank"] > 1 and gap["mean_ci95"][0] <= 0 <= gap["mean_ci95"][1]:
            lines += ["", "The paired Monte Carlo interval includes zero: this run does not clearly separate "
                      "this schedule from the leader. The interval is descriptive, not adjusted for selecting the finalists."]
    lines += ["", "## Requested bands and named historical profiles", "",
              f"Band scale: **{c['band_scale']}**. Intervals include the lower boundary and exclude the upper boundary. "
              "Rank mode uses ordinal positions sorted by published rating, with alphabetical ties; lower ranks are stronger.", "",
              "| Band | Eligible profiles, excluding fixed opponents | Named representatives | Graph projection status |",
              "|---|---:|---|---|"]
    for band in report["bands"]:
        lines.append(f"| {band['label']} | {band['member_count']} | "
                     f"{', '.join(band['representatives']) or 'None'} | {band['projection_status']} |")
    lines += ["", "Full-division marginal lift across the selected representatives (not a population interval or band average):", "",
              "| Band | Win lift range | Loss lift range |", "|---|---:|---:|"]
    by_team = {row["team"]: row for row in report["standalone_opponents"]}
    for band in report["bands"]:
        rows = [by_team[t] for t in band["representatives"]]
        ranges = []
        for outcome in ("win", "loss"):
            values = [row[outcome]["impact"]["mean"] for row in rows]
            ranges.append(f"{min(values):+.3f} to {max(values):+.3f}" if values else "Unavailable")
        lines.append(f"| {band['label']} | {' | '.join(ranges)} |")
    lines += ["", "The representatives below each add one game to the fixed slate. "
              "These are actual historical graph profiles, not promises of availability. "
              "Negative win lift means a win lowered season NPI in that context; small loss lift exposes low downside.", "",
              "| Named opponent | Expected lift | Win lift | Tie lift | Loss lift |",
              "|---|---:|---:|---:|---:|"]
    for row in report["standalone_opponents"]:
        lines.append(f"| {row['team']} | {row['expected_impact']['mean']:+.3f} | "
                     f"{row['win']['impact']['mean']:+.3f} | {row['tie']['impact']['mean']:+.3f} | "
                     f"{row['loss']['impact']['mean']:+.3f} |")
    probes = [(b, p) for b in report["bands"] for p in b["arithmetic_probes"]]
    if probes:
        lines += ["", "## Rating-value arithmetic only", "",
                  "These probes hold all opponent NPIs fixed and use modal outcomes for unlocked fixed games. "
                  "They are conditional season arithmetic, not division-converged projections. "
                  "Upper endpoints are limit probes and may belong to the next band. "
                  "Above-100 inputs are outside the verified calculator's domain; no open-ended-band midpoint is invented.", "",
                  "| Band | Opponent NPI | Win game value | Loss game value | Conditional season if win | If loss | Win/loss lift |",
                  "|---|---:|---:|---:|---:|---:|---:|"]
        for band, p in probes:
            w, loss = p["win"], p["loss"]
            lines.append(f"| {band['label']} | {p['opponent_npi']:.3f} | {w['game_value']:.3f} | "
                         f"{loss['game_value']:.3f} | {w['conditional_season_npi']:.3f} | "
                         f"{loss['conditional_season_npi']:.3f} | {w['impact']:+.3f}/{loss['impact']:+.3f} |")
    if fit.get("method") == "prior_season_out_of_time":
        fit_text = (f"Prior-season fit: {fit['sample_count']} weighted game observations from {', '.join(fit['training_seasons'])}; "
                    f"training log loss {fit['fit_log_loss']:.3f}; {fit['holdout_season']} out-of-time log loss "
                    f"{fit['out_of_time_log_loss']:.3f}. The holdout outcomes did not enter fitting.")
    else:
        fit_text = (f"Same-season retrospective fit: {fit['sample_count']} games; log loss {fit['fit_log_loss']:.3f}; "
                    f"constant-probability baseline {fit['constant_baseline_log_loss']:.3f}. The ratings contain the outcomes being predicted.")
    lines += ["", "## Assumptions and probability sensitivity", "", fit_text, "",
              f"The fitted strength coefficient is multiplied by {c['probability_slope_scale']}. "
              "Rerun with 0.5 and 1.0, or supply per-game probabilities, to test whether recommendations depend on that assumption.", ""]
    lines += [f"- {note}" for note in report["limitations"]]
    lines += ["", "Graph provenance is retained in the companion JSON. The default Amherst conference opponent list comes from "
              "[Amherst's 2024 schedule](https://athletics.amherst.edu/schedule.aspx?path=msoc&season=2024); "
              "custom inputs may replace that list. No current-season availability is inferred.", "",
              f"Full-division solves performed: {report['division_solves']}. "
              "The companion JSON retains full numerical precision.", ""]
    return "\n".join(lines)
