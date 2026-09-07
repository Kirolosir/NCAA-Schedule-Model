"""Command-line interface for the NPI model."""

import argparse
import json
from pathlib import Path
import sys

from .game_value import calculate_game_value


def main() -> None:
    parser = argparse.ArgumentParser(description="NCAA soccer NPI calculator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    game_parser = subparsers.add_parser("game", help="calculate one game value")
    game_parser.add_argument("--result", choices=("win", "loss"), required=True)
    game_parser.add_argument("--opponent-npi", type=float, required=True)

    subparsers.add_parser("planning-config", help="print editable default planning JSON")
    planning = subparsers.add_parser("plan", help="rank schedules by simulated division NPI")
    planning.add_argument("--season", choices=("2025", "2024", "2023", "2022"), help="historical division dataset")
    planning.add_argument("--config", type=Path, help="JSON inputs; omitted uses documented defaults")
    planning.add_argument("--graph", type=Path, help="replacement division fixture with the same schema")
    planning.add_argument("--mode", choices=("teams", "bands"))
    planning.add_argument("--band-scale", choices=("rating", "rank"))
    planning.add_argument("--samples", type=int)
    planning.add_argument("--validation-samples", type=int)
    planning.add_argument("--insight-samples", type=int)
    planning.add_argument("--top", type=int)
    planning.add_argument("--slope-scale", type=float)
    planning.add_argument("--output", type=Path, default=Path("reports/planning"),
                          help="output stem for .json and .md reports")
    planning.add_argument("--overwrite", action="store_true", help="replace existing reports")

    args = parser.parse_args()
    if args.command == "game":
        value = calculate_game_value(args.result, args.opponent_npi)
        print(f"Result component:       {value.result_component:.3f}")
        print(f"Opponent NPI component: {value.opponent_component:.3f}")
        print(f"Quality win bonus:      {value.quality_win_bonus:.3f}")
        print(f"Game value:             {value.total:.3f}")
    elif args.command == "planning-config":
        from .planning import default_config
        print(json.dumps(default_config(), indent=2))
    elif args.command == "plan":
        from .planning import default_config, load_graph
        from .planning_report import render_report
        from .schedule_optimizer import rank_schedules
        from .seasons import DEFAULT_SEASON, season_path
        supplied = json.loads(args.config.read_text()) if args.config else {}
        if args.season:
            supplied["season"] = args.season
        season = supplied.get("season", DEFAULT_SEASON)
        config = default_config(season)
        config.update(supplied)
        for arg, key in (("mode", "mode"), ("band_scale", "band_scale"),
                         ("samples", "samples"), ("validation_samples", "validation_samples"),
                         ("insight_samples", "insight_samples"), ("top", "top_n"),
                         ("slope_scale", "probability_slope_scale")):
            value = getattr(args, arg)
            if value is not None:
                config[key] = value
        json_path = args.output.with_suffix(".json")
        md_path = args.output.with_suffix(".md")
        if not args.overwrite and (json_path.exists() or md_path.exists()):
            parser.error("report exists; choose a new --output or explicitly pass --overwrite")
        try:
            data, ratings, games = load_graph(args.graph or season_path(season))
            report = rank_schedules(games, ratings, config,
                                    progress=lambda msg: print(msg, file=sys.stderr, flush=True))
            report["source"] = data["source"]
            json_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
            md_path.write_text(render_report(report))
        except (ValueError, KeyError) as error:
            parser.error(str(error))
        print(f"Report: {md_path.resolve()}")
        print(f"Full-precision data: {json_path.resolve()}")


if __name__ == "__main__":
    main()
