"""Production HTTP interface for the existing division model."""

import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.exceptions import HTTPException

from .app_server import AppState, ROOT


def create_app(*, state=None, public_origin=None):
    origin = public_origin or os.environ.get("PUBLIC_ORIGIN") or os.environ.get("RENDER_EXTERNAL_URL")
    if not origin:
        raise ValueError("Set PUBLIC_ORIGIN to the site's HTTPS address")
    origin = origin.rstrip("/")
    parsed = urlsplit(origin)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("PUBLIC_ORIGIN must be an HTTPS origin without a path")
    app = Flask(__name__, static_folder=None)
    app.config.update(SECRET_KEY=secrets.token_hex(32), MAX_CONTENT_LENGTH=100000,
                      TRUSTED_HOSTS=[parsed.hostname, "localhost", "127.0.0.1"],
                      SESSION_COOKIE_NAME="schedule_session", SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
    app.json.sort_keys = False
    model = state or AppState(max_job_seconds=1200)
    app.extensions["schedule_model"] = model
    public = (ROOT/"web/dist/client").resolve()

    @app.before_request
    def check_request():
        if request.method not in {"GET", "HEAD", "POST"}:
            return jsonify(error="Method not allowed"), 405
        if request.method == "POST":
            if request.headers.get("Origin") != origin or request.headers.get("Sec-Fetch-Site") == "cross-site":
                return jsonify(error="Use this site's app to submit a plan"), 403
            if request.mimetype != "application/json":
                return jsonify(error="Expected application/json"), 415
        if request.path.startswith("/api/") and request.path != "/api/health":
            session.setdefault("owner", secrets.token_hex(16))

    @app.after_request
    def security_headers(response):
        response.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
                                 "Referrer-Policy": "no-referrer", "Cache-Control": "no-store",
                                 "Strict-Transport-Security": "max-age=31536000",
                                 "X-Robots-Tag": "noindex, nofollow",
                                 "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'"})
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name), error.code

    def read_json():
        def invalid(_):
            raise ValueError("Nonfinite JSON number")
        return json.loads(request.get_data(), parse_constant=invalid)

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", app="ncaa-schedule-lab", teams=len(model.ratings))

    @app.get("/api/bootstrap")
    def bootstrap():
        try:
            data = model.bootstrap(request.args.get("season", "2025"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        data["config"].update(samples=4, validation_samples=4, insight_samples=2,
                              analysis_mode="quick", include_standalone_insights=False)
        data.update(report=None, deployment={"hosted": True, "max_job_minutes": 20})
        return jsonify(data)

    @app.get("/api/jobs/<job_id>")
    def job_status(job_id):
        try:
            return jsonify(model.job(job_id, owner=session["owner"]))
        except KeyError:
            return jsonify(error="Comparison not found; it may have expired"), 404

    @app.post("/api/<path:action>")
    def api_action(action):
        try:
            raw = read_json()
            if action == "validate":
                config, summary = model.validate(raw)
                return jsonify(config=config, **summary)
            if action == "explore":
                return jsonify(model.explore(raw))
            if action == "jobs":
                return jsonify(model.start(raw, owner=session["owner"])), 202
            if action.startswith("jobs/") and action.endswith("/cancel") and len(action.split("/")) == 3:
                return jsonify(model.job(action.split("/")[1], cancel=True, owner=session["owner"]))
            return jsonify(error="Endpoint not found"), 404
        except KeyError:
            return jsonify(error="Comparison not found or an input field is missing"), 404
        except (ValueError, TypeError, StopIteration) as error:
            return jsonify(error=str(error) or "Check the plan inputs"), 400
        except RuntimeError as error:
            return jsonify(error=str(error)), 409

    @app.get("/")
    @app.get("/<path:path>")
    def frontend(path="index.html"):
        target = (public/path).resolve()
        if (path.startswith("api/") or not target.is_relative_to(public)
                or any(part.startswith(".") for part in Path(path).parts) or not target.is_file()):
            return jsonify(error="Not found"), 404
        return send_from_directory(public, path)

    return app
