import threading
import time
import unittest

from npi_model.app_server import AppState

try:
    from npi_model.hosted_app import create_app
except ModuleNotFoundError:
    create_app = None


@unittest.skipIf(create_app is None, "Install requirements.txt for hosted API tests")
class TestHostedApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.origin = "https://schedule.example"
        cls.state = AppState()
        cls.app = create_app(state=cls.state, public_origin=cls.origin)
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()

    def get(self, path, client=None):
        return (client or self.client).get(path, base_url=self.origin)

    def post(self, path, data, client=None, **kwargs):
        return (client or self.client).post(path, json=data, base_url=self.origin,
                                            headers={"Origin": self.origin}, **kwargs)

    def test_bootstrap_and_cookie(self):
        response = self.get("/api/bootstrap")
        data = response.get_json()
        self.assertEqual(len(data["teams"]), 407)
        self.assertEqual(data["config"]["samples"], 4)
        self.assertTrue(data["deployment"]["hosted"])
        self.assertIsNone(data["report"])
        cookie = response.headers["Set-Cookie"]
        for flag in ("Secure", "HttpOnly", "SameSite=Lax"):
            self.assertIn(flag, cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_host_and_origin_checks(self):
        self.assertEqual(self.client.get("/api/bootstrap", base_url="https://wrong.example").status_code, 400)
        for origin in (None, "https://wrong.example", "null"):
            response = self.client.post("/api/jobs", json={}, base_url=self.origin,
                                        headers={} if origin is None else {"Origin": origin})
            self.assertEqual(response.status_code, 403)
        response = self.client.post("/api/jobs", json={}, base_url=self.origin,
                                    headers={"Origin": self.origin, "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(response.status_code, 403)

    def test_validation_and_real_explorer(self):
        self.assertEqual(self.post("/api/validate", {}).get_json()["combinations"], 21)
        raw = {"opponent_npi": 54.000000001}
        self.assertEqual(self.post("/api/explore", raw).get_json(), self.state.explore(raw))
        self.assertEqual(self.post("/api/validate", {"samples": True}).status_code, 400)

    def test_bad_payloads(self):
        for body, content_type, status in [("{}", "text/plain", 415), ("{bad", "application/json", 400),
                                            ('{"samples":NaN}', "application/json", 400),
                                            (" "*100001, "application/json", 413)]:
            response = self.client.post("/api/validate", data=body, content_type=content_type,
                                        base_url=self.origin, headers={"Origin": self.origin})
            self.assertEqual(response.status_code, status)

    def test_private_files_and_missing_jobs(self):
        for path in ("/.git/config", "/NCAA%20Statistics.xlsx", "/reports/amherst-default.json",
                     "/assets/", "/../README.md", "/api/unknown", "/api/jobs/not-a-job"):
            self.assertEqual(self.get(path).status_code, 404, path)
            self.assertEqual(self.client.head(path, base_url=self.origin).status_code, 404, path)

    def test_jobs_are_owned_by_one_browser_session(self):
        entered, release = threading.Event(), threading.Event()
        original = self.state.ranker
        def ranker(games, ratings, config, progress):
            entered.set()
            release.wait(3)
            progress("Scored 1/1")
            return {"config": config}
        self.state.ranker = ranker
        job_id = None
        try:
            response = self.post("/api/jobs", {})
            self.assertEqual(response.status_code, 202)
            job_id = response.get_json()["id"]
            self.assertTrue(entered.wait(2))
            other = self.app.test_client()
            self.assertEqual(self.get("/api/jobs/"+job_id, other).status_code, 404)
            self.assertEqual(self.post("/api/jobs/"+job_id+"/cancel", {}, other).status_code, 404)
            self.assertEqual(self.post("/api/jobs", {}, other).status_code, 409)
            self.assertEqual(self.get("/api/jobs/"+job_id).status_code, 200)
            self.assertNotIn("owner", self.get("/api/jobs/"+job_id).get_json())
            self.assertEqual(self.post("/api/jobs/"+job_id+"/cancel", {}).status_code, 200)
        finally:
            release.set()
            deadline = time.monotonic()+4
            while self.state.active and time.monotonic() < deadline:
                time.sleep(.02)
            self.state.ranker = original
        self.assertIsNone(self.state.active)
        self.assertEqual(self.get("/api/jobs/"+job_id).get_json()["status"], "cancelled")

    def test_requires_an_https_origin(self):
        for origin in ("http://schedule.example", "https://schedule.example/path", "https://user@host", "https://host?q=1"):
            with self.assertRaises(ValueError):
                create_app(state=self.state, public_origin=origin)


class TestHostedJobDeadline(unittest.TestCase):
    def test_expired_job_reports_error_and_releases_slot(self):
        def ranker(games, ratings, config, progress):
            time.sleep(.02)
            progress("Scored 1/1")
        state = AppState(ranker=ranker, max_job_seconds=.001)
        job = state.start({})["id"]
        deadline = time.monotonic()+3
        while state.active and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertEqual(state.job(job)["status"], "error")
        self.assertIn("Time limit", state.job(job)["message"])
        self.assertIsNone(state.active)
