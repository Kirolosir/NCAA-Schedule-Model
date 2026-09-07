"""Reconcile older scoreboards with NCAA records, then reconstruct season ratings."""

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from import_season import ROOT, export_rows
from npi_model.division_npi import DivisionGame, iterate_division_npi

ALIASES = {"SUNY Cortland": "Cortland", "Gust. Adolphus": "Gustavus Adolphus", "CMSV": "UMSV",
           "Cobleskill St.": "SUNY Cobleskill", "NVU-Johnson": "VTSU-Johnson", "NVU-Lyndon": "VTSU Lyndon",
           "Castleton": "VTSU Castleton", "Batten": "Va. Wesleyan", "IIT": "Illinois Tech"}


def name(value):
    value = re.sub(r"^(?:@\s*|#\d+\s+)", "", value.strip())
    return ALIASES.get(value.strip(), value.strip())


def build(year, workbook):
    rows = export_rows(workbook)
    export_records = {name(r["Team"].rsplit(" (", 1)[0]): [int(r[k]) for k in ("Won", "Loss", "Tied")] for r in rows}
    records = dict(export_records)
    discrepancies = []
    if year == 2022:
        if records["Earlham"] != [4, 12, 1]:
            raise ValueError("Recheck Earlham: ranking export has changed")
        records["Earlham"] = [3, 12, 1]
        discrepancies.append({"team": "Earlham", "export_record": [4, 12, 1], "schedule_record": [3, 12, 1],
                              "source": "https://stats.ncaa.org/teams/541825",
                              "reason": "NCAA team page and 16 distinct results show 3-12-1. The ranking export says 4-12-1; the daily archive contains the Asbury win twice. Count each match once."})
    cache = ROOT / f"local_data/{year}/scoreboards"
    games, corrections, missing = {}, [], []
    for path in sorted(cache.glob("*.json")):
        data = json.loads(path.read_text())
        if data.get("archive_missing"):
            missing.append(path.stem)
        for wrapper in data["games"]:
            g = wrapper["game"]
            if path.stem < f"{year}-09-01" or g["gameState"] != "final" or not all(g[s]["score"].isdigit() for s in ("away", "home")):
                continue
            a, b = [name(g[s]["names"]["short"]) for s in ("away", "home")]
            sa, sb = [int(g[s]["score"]) for s in ("away", "home")]
            key = (path.stem, *sorted((a, b)))
            row = [g["url"].rsplit("/", 1)[-1] or g["gameID"], path.stem, a, b, "win" if sa > sb else "loss" if sa < sb else "tie"]
            if key in games and games[key][2:] != row[2:]:
                raise ValueError(f"Duplicate/conflicting game: {key}")
            games[key] = row
    pages = json.loads((ROOT / "local_data/2025/stats_pages.json").read_text())
    for page in pages.values():
        if page.get("kind") != "team_schedule" or page["academic_year"] != f"{year}-{str(year+1)[2:]}":
            continue
        team = name(page["team"])
        official = []
        for r in page["rows"]:
            if "*" in r["result"]:
                continue
            match = re.fullmatch(r"([WLT])\s+(\d+)-(\d+)(?:\s+.*)?", r["result"])
            if not match:
                continue
            opponent = name(r["opponent"])
            month, day, season = r["date"][:10].split("/")
            day = f"{season}-{month}-{day}"
            result = {"W": "win", "L": "loss", "T": "tie"}[match[1]]
            official.append((day, opponent, result, r.get("box_url")))
        expected = records[team]
        actual = [sum(r[2] == outcome for r in official) for outcome in ("win", "loss", "tie")]
        if actual != expected:
            raise ValueError(f"Team schedule parser mismatch for {year} {team}: {actual} vs {expected}")
        for key in [k for k, g in games.items() if team in g[2:4]]:
            del games[key]
        for day, opponent, result, url in official:
            key = (day, *sorted((team, opponent)))
            games[key] = [(url or f"{team}:{day}").split("/")[-2] if url else f"{team}:{day}", day, team, opponent, result]
        corrections.append({"team": team, "source": page["url"],
                            "sha256": sha256(json.dumps(page, sort_keys=True).encode()).hexdigest()})
    counts = defaultdict(lambda: [0, 0, 0])
    for _, _, a, b, r in games.values():
        counts[a][("win", "loss", "tie").index(r)] += 1
        counts[b][("loss", "win", "tie").index(r)] += 1
    mismatch = {t: [counts[t], expected] for t, expected in records.items() if counts[t] != expected}
    print(year, "record mismatches:", json.dumps(mismatch), flush=True)
    if mismatch:
        raise ValueError("Historical records must reconcile before use")
    eligible_games = [g for g in games.values() if g[2] in records and g[3] in records]
    graph = [DivisionGame(a, b, r) for _, _, a, b, r in eligible_games]
    result = iterate_division_npi(graph, eligible_teams=records)
    fixture = {"source": {"season": str(year), "cutoff": f"{year}-12-0{4 if year == 2022 else 3}",
                         "rating_kind": "retrospective_npi", "snapshot": "Final results",
                         "url": f"https://stats.ncaa.org/rankings/national_ranking?academic_year={year+1}.0&division=3.0&ranking_period={48 if year == 2022 else 57}.0&sport_code=MSO&stat_seq=33.0",
                         "workbook_sha256": sha256(Path(workbook).read_bytes()).hexdigest(),
                         "scoreboard_url_template": "https://data.ncaa.com/casablanca/scoreboard/soccer-men/d3/YYYY/MM/DD/scoreboard.json",
                         "archive_sha256": sha256(b"".join(p.read_bytes() for p in sorted(cache.glob('*.json')))).hexdigest(),
                         "missing_archive_dates": missing, "schedule_reconciliations": corrections,
                         "eligible_npi_teams": len(records), "eligible_npi_games": len(graph),
                         "validation": {"records_matched": len(records)-len(discrepancies), "records_reconciled": len(records),
                                        "record_discrepancies": discrepancies, "iterations": result.iterations,
                                        "published_npi_available": False},
                         "note": "Retrospective application of the 2024/2025 NPI rules to historical games, not an official NCAA NPI. Team scope is the NCAA season WLT table; unlisted provisional teams are excluded."},
               "teams": [[t, result.ratings[t], "-".join(map(str, records[t])), None] for t in sorted(records)],
               "games": sorted(eligible_games, key=lambda g: (g[1],g[0])), "all_results_records": records,
               "export_records": export_records, "all_games": sorted(games.values(), key=lambda g: (g[1],g[0]))}
    path = ROOT / f"tests/data/ncaa_{year}_historical_division.json"
    path.write_text(json.dumps(fixture, indent=2)+"\n")
    print(f"Saved {year}: {len(records)} teams, {len(graph)} games, {result.iterations} iterations", flush=True)


if __name__ == "__main__":
    build(int(sys.argv[1]), sys.argv[2])
