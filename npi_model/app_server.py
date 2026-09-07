"""Loopback-only dashboard API. Calls the existing Python model, never a JS copy."""

import argparse
from dataclasses import asdict, replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from math import comb, isfinite
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
from uuid import uuid4

from .game_value import calculate_game_value
from .outcome_model import OutcomeModel
from .planning import default_config, parse_plan
from .schedule_optimizer import rank_schedules
from .season_npi import SeasonGame, calculate_season_npi
from .seasons import DEFAULT_SEASON, catalog, load_season, team_history
from .temporal_model import historical_model

ROOT = Path(__file__).resolve().parents[1]


def number(value, label, lower, upper, *, integer=False):
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if integer and type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    if not lower <= value <= upper:
        raise ValueError(f"{label} must be between {lower} and {upper}")
    return value


def validate_config(raw, ratings):
    if not isinstance(raw, dict):
        raise ValueError("The plan must be a JSON object")
    season = raw.get("season", DEFAULT_SEASON)
    config = default_config(season)
    unknown = set(raw)-set(config)-{"target_recent_npi"}
    if unknown:
        raise ValueError(f"Unknown plan setting: {sorted(unknown)[0]}")
    config.update(raw)
    if config["analysis_mode"] not in ("quick", "standard", "thorough"):
        raise ValueError("analysis_mode must be quick, standard, or thorough")
    if type(config["include_standalone_insights"]) is not bool:
        raise ValueError("include_standalone_insights must be true or false")
    if config["probability_model"] not in ("historical", "retrospective"):
        raise ValueError("Choose the historical or retrospective probability model")
    if config["probability_model"] == "historical" and season not in ("2024", "2025"):
        raise ValueError("The historical probability model requires at least one prior-season transition")
    for key in ("fixed_games", "candidates", "bands", "required", "excluded"):
        if not isinstance(config[key], list):
            raise ValueError(f"{key} must be a list")
    for key in ("required", "excluded"):
        if any(not isinstance(t, str) for t in config[key]):
            raise ValueError(f"{key} must contain team names")
    if not isinstance(config["target_team"], str):
        raise ValueError("Choose a target team")
    for key in ("fixed_games", "candidates"):
        if len(config[key]) > 40:
            raise ValueError(f"{key} may contain at most 40 opponents")
        for row in config[key]:
            if not isinstance(row, dict) or not isinstance(row.get("team"), str):
                raise ValueError(f"Each entry in {key} needs a team name")
            allowed = {"team", "category", "result", "probabilities"} if key == "fixed_games" else {"team", "recent_npi", "probabilities"}
            if set(row)-allowed:
                raise ValueError(f"Unknown opponent setting for {row['team']}")
            if "recent_npi" in row:
                number(row["recent_npi"], "Recent NPI", 0, 100)
            if row.get("probabilities") is not None:
                p = row["probabilities"]
                if not isinstance(p, dict) or set(p) != {"win", "tie", "loss"}:
                    raise ValueError("Probabilities need win, tie, and loss")
                for outcome, value in p.items():
                    number(value, f"{outcome} probability", 0, 1)
    if len(config["bands"]) > 20:
        raise ValueError("Use at most 20 bands")
    for band in config["bands"]:
        if not isinstance(band, dict) or not isinstance(band.get("label"), str):
            raise ValueError("Each band needs a label")
        if set(band)-{"label", "lower", "upper"}:
            raise ValueError("Unknown band setting")
        for key in ("lower", "upper"):
            if band.get(key) is not None:
                number(band[key], f"Band {key}", 0, 10000)
    for key, low, high in (("open_slots", 1, 12), ("samples", 2, 64),
                           ("validation_samples", 2, 256), ("insight_samples", 2, 32),
                           ("top_n", 1, 5), ("max_combinations", 1, 500),
                           ("representatives_per_band", 1, 8), ("seed", 0, 2**53-1)):
        number(config[key], key, low, high, integer=True)
    number(config["probability_slope_scale"], "Probability strength", .05, 2)
    number(config["convergence_tolerance"], "Convergence tolerance", 1e-12, 1e-6)
    if "target_recent_npi" in config:
        number(config["target_recent_npi"], "Target recent NPI", 0, 100)
    target, fixed, candidates, bands = parse_plan(config, ratings)
    required = set(config["required"])
    if not required <= {c.team for c in candidates}:
        raise ValueError("Required opponents must be in the active candidate pool")
    slots = config["open_slots"]
    if len(required) > slots:
        raise ValueError("More opponents are required than there are open slots")
    if len(candidates) < slots:
        raise ValueError(f"Choose at least {slots} candidates; this pool has {len(candidates)}")
    combinations = comb(len(candidates)-len(required), slots-len(required))
    if combinations > config["max_combinations"]:
        raise ValueError(f"This pool creates {combinations:,} schedules. Narrow it or require opponents (limit {config['max_combinations']}).")
    return config, {"target": target, "fixed_count": len(fixed), "candidate_count": len(candidates),
                    "combinations": combinations, "bands": bands,
                    "candidates": [asdict(c) for c in candidates]}


class CalculationCancelled(Exception):
    pass


class AppState:
    def __init__(self, *, ranker=rank_schedules, max_job_seconds=None):
        self.data, self.ratings, self.games = load_season(DEFAULT_SEASON)
        self.models = {}
        self.model = self.model_for(DEFAULT_SEASON, "historical")
        self.ranker = ranker
        self.max_job_seconds = max_job_seconds
        self.lock = threading.Lock()
        self.jobs = {}
        self.active = None
        self.reference = None
        reference_path = ROOT/"reports/amherst-default.json"
        if reference_path.exists():
            try:
                report = json.loads(reference_path.read_text())
                if (report.get("source", {}).get("workbook_sha256") == self.data["source"]["workbook_sha256"]
                        and report.get("config") == default_config()):
                    self.reference = report
            except (ValueError, OSError):
                pass

    def model_for(self, season, method):
        key = (season, method)
        if key not in self.models:
            _, ratings, games = load_season(season)
            if method == "historical":
                self.models[key] = historical_model(season)[0]
            else:
                self.models[key] = OutcomeModel.fit(games, ratings)
        return self.models[key]

    def bootstrap(self, season=DEFAULT_SEASON):
        data, ratings, _ = load_season(season)
        config = default_config(season)
        model = self.model_for(season, config["probability_model"])
        diagnostics = historical_model(season)[1] if config["probability_model"] == "historical" else None
        ordered = sorted(ratings, key=lambda t: (-ratings[t], t))
        records = {row[0]: row[2] for row in data["teams"]}
        return {"config": config, "source": data["source"], "seasons": catalog(),
                "teams": [{"name": t, "npi": ratings[t], "rank": i+1, "record": records[t],
                           "history": team_history(t)}
                          for i, t in enumerate(ordered)],
                "model": asdict(model), "model_diagnostics": diagnostics,
                "rating_range": [min(ratings.values()), max(ratings.values())],
                "report": self.reference if season == DEFAULT_SEASON else None}

    def validate(self, raw):
        season = raw.get("season", DEFAULT_SEASON) if isinstance(raw, dict) else DEFAULT_SEASON
        _, ratings, _ = load_season(season)
        return validate_config(raw, ratings)

    def explore(self, request):
        if not isinstance(request, dict):
            raise ValueError("Exploration needs an object")
        value = number(request.get("opponent_npi"), "Opponent NPI", 0, 100)
        raw = request.get("config", default_config())
        season = raw.get("season", DEFAULT_SEASON) if isinstance(raw, dict) else DEFAULT_SEASON
        data, ratings, _ = load_season(season)
        # A temporary real candidate lets the explorer accept an incomplete pool.
        config = dict(raw)
        fixed_names = {g.get("team") for g in config.get("fixed_games", []) if isinstance(g, dict)}
        spare = next(t for t in ratings if t not in fixed_names and t != config.get("target_team", "Amherst"))
        config.update(mode="teams", candidates=[{"team": spare}], required=[], excluded=[], open_slots=1)
        config, _ = validate_config(config, ratings)
        target, fixed, _, _ = parse_plan(config, ratings)
        base_model = self.model_for(season, config["probability_model"])
        model = replace(base_model, slope=base_model.slope*config["probability_slope_scale"])
        strength = config.get("target_recent_npi", ratings[target])
        baseline_games = []
        assumptions = []
        for game in fixed:
            probabilities = game.probabilities or model.predict(strength, ratings[game.team])
            outcome = game.result or max(probabilities.as_items(), key=lambda row: row[1])[0]
            baseline_games.append(SeasonGame(game.team, ratings[game.team], outcome))
            assumptions.append({"team": game.team, "result": outcome, "locked": game.result is not None})
        baseline = calculate_season_npi(baseline_games)
        def evaluate(npi):
            rows = {}
            for outcome in ("win", "tie", "loss"):
                result = calculate_season_npi(baseline_games+[SeasonGame("probe", npi, outcome)])
                rows[outcome] = {"npi": result.npi, "impact": result.npi-baseline.npi,
                                 "retained_wins": result.retained_win_weight,
                                 "retained_losses": result.retained_loss_weight}
                if outcome != "tie":
                    rows[outcome]["game_value"] = asdict(calculate_game_value(outcome, npi))
            return rows
        return {"opponent_npi": value, "baseline_npi": baseline.npi,
                "outcomes": evaluate(value), "probabilities": asdict(model.predict(strength, value)),
                "curve": [{"npi": npi, "outcomes": evaluate(npi)} for npi in range(30, 81)],
                "assumptions": assumptions, "method": "fixed_ratings_modal_outcomes", "season": season,
                "rating_range": [min(ratings.values()), max(ratings.values())]}

    def start(self, raw, *, owner=None):
        season = raw.get("season", DEFAULT_SEASON) if isinstance(raw, dict) else DEFAULT_SEASON
        data, ratings, games = load_season(season)
        config, summary = validate_config(raw, ratings)
        with self.lock:
            if self.active:
                raise RuntimeError("A comparison is already running. Finish or cancel it first.")
            while len(self.jobs) >= 8:
                del self.jobs[next(iter(self.jobs))]
            job_id = uuid4().hex
            job = {"id": job_id, "status": "running", "message": "Preparing division model", "progress": 0,
                   "started": time.time(), "config": config, "summary": summary, "season": season,
                   "owner": owner, "cancel": threading.Event()}
            self.jobs[job_id] = job
            self.active = job_id
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return {"id": job_id}

    def _run(self, job_id):
        job = self.jobs[job_id]
        started = time.monotonic()
        def progress(message):
            if job["cancel"].is_set():
                raise CalculationCancelled()
            if self.max_job_seconds and time.monotonic()-started > self.max_job_seconds:
                raise TimeoutError("Time limit reached. Try fewer candidates or Quick exploration.")
            match = re.search(r"(\d+)/(\d+)", message)
            fraction = int(match[1])/int(match[2]) if match else 0
            level = job["progress"]
            if message.startswith("Scored"):
                level = .08+.48*fraction
            elif message.startswith("Validated"):
                level = .56+.20*fraction
            elif message.startswith("Explained"):
                level = .76+.14*fraction
            elif message.startswith("Evaluated"):
                level = min(.99, level+.005)
            with self.lock:
                job.update(message=message, progress=level)
        try:
            data, ratings, games = load_season(job["season"])
            report = self.ranker(games, ratings, job["config"], progress=progress)
            if job["cancel"].is_set():
                raise CalculationCancelled()
            report["source"] = data["source"]
            with self.lock:
                job.update(status="complete", progress=1, message="Comparison complete", report=report)
        except CalculationCancelled:
            with self.lock:
                job.update(status="cancelled", message="Comparison cancelled. Your inputs are unchanged.")
        except Exception as error:
            with self.lock:
                job.update(status="error", message=f"Calculation stopped: {error}")
        finally:
            with self.lock:
                job["finished"] = time.time()
                self.active = None

    def job(self, job_id, *, cancel=False, owner=None):
        with self.lock:
            if job_id not in self.jobs or self.jobs[job_id].get("owner") != owner:
                raise KeyError("Comparison not found; it may have expired after restarting the app")
            job = self.jobs[job_id]
            if cancel and job["status"] == "running":
                job["cancel"].set()
                job.update(status="cancelling", message="Stopping after the current calculation…")
            return {k: v for k, v in job.items() if k not in {"cancel", "owner"}}


class Handler(SimpleHTTPRequestHandler):
    server_version = "ScheduleLab/1.0"

    def __init__(self, *args, state, directory, **kwargs):
        self.state = state
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, fmt, *args):
        # Request bodies / coach inputs are never logged.
        pass

    def reply(self, value, status=200):
        body = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Fast slider edits can abort an obsolete browser request.

    def trusted_request(self):
        host = self.headers.get("Host", "")
        allowed_hosts = {f"{h}:{p}" for h in ("localhost", "127.0.0.1") for p in (self.server.server_port, 5173)}
        if host not in allowed_hosts:
            return False
        origin = self.headers.get("Origin")
        return not origin or origin in {f"http://{h}" for h in allowed_hosts}

    def do_GET(self):
        if not self.trusted_request():
            return self.reply({"error": "Only this local app may access the model"}, 403)
        path = urlparse(self.path).path
        if path == "/api/bootstrap":
            query = urlparse(self.path).query
            season = next((part.split("=", 1)[1] for part in query.split("&") if part.startswith("season=")), DEFAULT_SEASON)
            try:
                return self.reply(self.state.bootstrap(season))
            except ValueError as error:
                return self.reply({"error": str(error)}, 400)
        if path == "/api/health":
            return self.reply({"status": "ok", "app": "ncaa-schedule-lab", "teams": len(self.state.ratings)})
        if path.startswith("/api/jobs/"):
            try:
                return self.reply(self.state.job(path.rsplit("/", 1)[-1]))
            except KeyError as error:
                return self.reply({"error": str(error)}, 404)
        if path.startswith("/api/"):
            return self.reply({"error": "Endpoint not found"}, 404)
        # Never expose the project, reports, raw export or directory listings.
        target = Path(self.translate_path(self.path)).resolve()
        root = Path(self.directory).resolve()
        if not target.is_relative_to(root) or any(p.startswith(".") for p in target.relative_to(root).parts):
            return self.reply({"error": "Not found"}, 404)
        if target.is_dir() and not (target/"index.html").exists():
            return self.reply({"error": "App not built. Use the local development launcher."}, 404)
        return super().do_GET()

    def do_POST(self):
        if not self.trusted_request():
            return self.reply({"error": "Only this local app may change a plan"}, 403)
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply({"error": "Expected application/json"}, 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 100000:
                return self.reply({"error": "Request must be between 1 byte and 100 KB"}, 413)
            data = json.loads(self.rfile.read(size), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON number")))
            path = urlparse(self.path).path
            if path == "/api/validate":
                config, summary = self.state.validate(data)
                return self.reply({"config": config, **summary})
            if path == "/api/explore":
                return self.reply(self.state.explore(data))
            if path == "/api/jobs":
                return self.reply(self.state.start(data), 202)
            if path.startswith("/api/jobs/") and path.endswith("/cancel"):
                return self.reply(self.state.job(path.split("/")[-2], cancel=True))
            return self.reply({"error": "Endpoint not found"}, 404)
        except (ValueError, TypeError, KeyError, StopIteration) as error:
            return self.reply({"error": str(error) or "Check the plan inputs"}, 400)
        except RuntimeError as error:
            return self.reply({"error": str(error)}, 409)


def main():
    parser = argparse.ArgumentParser(description="Local Schedule Lab model server")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    state = AppState()
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                partial(Handler, state=state, directory=ROOT/"web/dist/client"))
    print(f"Schedule Lab model: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
