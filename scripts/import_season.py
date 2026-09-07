"""Download public NCAA scoreboards and read the selection export without styles."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import time
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def export_rows(path):
    with ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(x.itertext()) for x in ET.fromstring(
                archive.read("xl/sharedStrings.xml")).findall("m:si", NS)]
        rows = []
        for row in ET.fromstring(archive.read("xl/worksheets/sheet1.xml")).findall(".//m:row", NS):
            values = []
            for cell in row:
                value, inline = cell.find("m:v", NS), cell.find("m:is", NS)
                text = value.text if value is not None else "".join(inline.itertext()) if inline is not None else ""
                values.append(shared[int(text)] if cell.get("t") == "s" else text)
            rows.append(values)
    return [dict(zip(rows[0], row)) for row in rows[1:]]


def fetch_day(day, cache):
    path = cache / f"{day}.json"
    if path.exists():
        return json.loads(path.read_text())
    url = f"https://data.ncaa.com/casablanca/scoreboard/soccer-men/d3/{day:%Y/%m/%d}/scoreboard.json"
    for attempt in range(4):
        try:
            response = subprocess.run(["curl", "--silent", "--show-error", "--max-time", "45", "-w", "\n%{http_code}", url],
                                      check=True, capture_output=True).stdout
            raw, status = response.rsplit(b"\n", 1)
            if status == b"404":
                data = {"games": [], "archive_missing": True, "url": url}
                path.write_text(json.dumps(data))
                return data
            if status != b"200":
                raise ValueError(f"HTTP {status.decode()}: {url}")
            data = json.loads(raw)
            if "games" not in data:
                raise ValueError(f"Missing games field: {url}")
            path.write_bytes(raw)
            return data
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def download(year, cutoff):
    cache = ROOT / "local_data" / str(year) / "scoreboards"
    cache.mkdir(parents=True, exist_ok=True)
    start, end = date(year, 8, 21), date.fromisoformat(cutoff)
    days = [start + timedelta(days=i) for i in range((end-start).days+1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, _ in enumerate(pool.map(lambda day: fetch_day(day, cache), days), 1):
            if i % 10 == 0:
                print(f"{year}: cached {i}/{len(days)} days", flush=True)
    digest = sha256(b"".join(path.read_bytes() for path in sorted(cache.glob("*.json")))).hexdigest()
    print(f"{year}: {len(days)} days, archive SHA256 {digest}", flush=True)


def record(value):
    values = [int(n) for n in value.split("-")]
    return values + [0] if len(values) == 2 else values


def build_2025(workbook, pages_path):
    from collections import defaultdict
    from npi_model.division_npi import DivisionGame, iterate_division_npi
    rows = export_rows(workbook)
    eligible = {r["Team"].removesuffix("(AQ)").strip(): r for r in rows if r.get("NPI")}
    pages = json.loads(Path(pages_path).read_text())
    games, used_pages = {}, []
    for page in pages.values():
        if page.get("title") != "2025-26 Men's Soccer D-III Scoreboard":
            continue
        month, day, year = page["date"].split("/")
        day = f"{year}-{month}-{day}"
        if not "2025-08-21" <= day <= "2025-11-09":
            continue
        used_pages.append(page)
        for g in page["games"]:
            if len(g["sides"]) != 2 or not (g["status"] == "final" or "\nFinal\n" in g["status"]):
                continue
            a, b = g["sides"]
            aliases = {"Batten": "Va. Wesleyan"}
            a, b = ({**s, "name": aliases.get(s["name"].strip(), s["name"].strip())} for s in (a, b))
            if a["name"] not in eligible or b["name"] not in eligible:
                continue
            sa, sb = int(a["score"]), int(b["score"])
            row = [g["id"], day, a["name"], b["name"], "win" if sa > sb else "loss" if sa < sb else "tie"]
            if g["id"] in games and games[g["id"]] != row:
                raise ValueError(f"Conflicting result: {g['id']}")
            games[g["id"]] = row
    counts = defaultdict(lambda: [0, 0, 0])
    for _, _, a, b, result in games.values():
        counts[a][("win", "loss", "tie").index(result)] += 1
        counts[b][("loss", "win", "tie").index(result)] += 1
    mismatches = {t: {"actual": counts[t], "expected": [a+b for a, b in zip(record(r["vAbove"]), record(r["vBelow"]))]}
                  for t, r in eligible.items() if counts[t] != [a+b for a, b in zip(record(r["vAbove"]), record(r["vBelow"]))]}
    print("2025 record mismatches:", json.dumps(mismatches, indent=2), flush=True)
    if mismatches:
        raise ValueError("2025 game records do not reconcile; no production fixture written")
    graph = [DivisionGame(a, b, r) for _, _, a, b, r in games.values()]
    result = iterate_division_npi(graph, eligible_teams=eligible)
    error = max(abs(result.ratings[t]-float(r["NPI"])) for t, r in eligible.items())
    print(f"2025 convergence: {result.iterations} iterations; max published error {error}", flush=True)
    if error >= .001:
        raise ValueError("2025 convergence differs from published NPI; no production fixture written")
    source = {"season": "2025", "cutoff": "2025-11-09", "rating_kind": "official_npi", "snapshot": "Selections",
              "url": "https://stats.ncaa.org/selection_rankings/nitty_gritties/46698",
              "workbook_sha256": sha256(Path(workbook).read_bytes()).hexdigest(),
              "results_source": "https://stats.ncaa.org/contests/livestream_scoreboards?season_division_id=18611",
              "results_sha256": sha256(json.dumps(sorted(used_pages, key=lambda p: p["date"]), sort_keys=True).encode()).hexdigest(),
              "name_aliases": {"Batten": "Va. Wesleyan"},
              "eligible_npi_teams": len(eligible), "eligible_npi_games": len(games),
              "validation": {"records_matched": len(eligible), "max_published_error": error, "iterations": result.iterations}}
    fixture = {"source": source, "teams": [[t, float(r["NPI"]), r["DIIIWL"], r["AdjW/L"]] for t, r in eligible.items()],
               "games": sorted(games.values(), key=lambda g: (g[1], g[0])),
               "eligible_records": dict(counts)}
    (ROOT / "tests/data/ncaa_2025_11_09_division.json").write_text(json.dumps(fixture, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("year", type=int)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--workbook")
    parser.add_argument("--pages")
    args = parser.parse_args()
    if args.pages and args.workbook:
        build_2025(args.workbook, args.pages)
    else:
        download(args.year, args.cutoff)
