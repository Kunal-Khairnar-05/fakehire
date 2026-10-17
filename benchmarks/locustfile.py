"""Benchmarks B and C: load test POST /api/v1/check through Nginx.

Before the timer starts, a small pool of throwaway accounts (loadtest-...@example.com)
is created ONCE and logged in; all simulated users share those tokens. Signing up
200 users during the test would measure bcrypt (deliberately slow, ~0.25 s CPU per
hash), not /check, and in our first attempt it overloaded a single replica.

SCENARIO=hit   every request is the SAME posting -> after the first one, all cache hits
SCENARIO=miss  every request is a NEW posting    -> every one goes to ml-service

Run headless (no web UI) from the project root, e.g. in PowerShell:
    $env:SCENARIO="hit"
    python -m locust -f benchmarks/locustfile.py --host http://localhost --headless -u 50 -r 10 -t 60s `
           --csv benchmarks/results/hit_api3_u50

Clean up the test accounts afterwards (deletes their checks too, via ON DELETE CASCADE):
    DELETE FROM users WHERE email LIKE 'loadtest-%';
"""
import os
import random
import uuid

import requests
from locust import HttpUser, between, events, task

SCENARIO = os.getenv("SCENARIO", "hit")
ACCOUNTS = 10
PASSWORD = "loadtest-password-1"
POSTING = {
    "title": "Data Entry Work From Home",
    "description": "No interview needed! Earn Rs 30000 per month from home. Pay a registration fee "
                   "of Rs 1999 to confirm your seat. Message HR on WhatsApp 9876543210.",
}
TOKENS: list[str] = []


@events.test_start.add_listener
def create_accounts(environment, **_kwargs):
    """Runs once, before any simulated user starts: sign up + log in the account pool."""
    print(f"Creating {ACCOUNTS} load-test accounts (not part of the measurements)...")
    for _ in range(ACCOUNTS):
        email = f"loadtest-{uuid.uuid4().hex[:12]}@example.com"
        requests.post(f"{environment.host}/api/v1/auth/register",
                      json={"email": email, "password": PASSWORD}, timeout=30).raise_for_status()
        login = requests.post(f"{environment.host}/api/v1/auth/login",
                              data={"username": email, "password": PASSWORD}, timeout=30)
        login.raise_for_status()
        TOKENS.append(login.json()["access_token"])
    print(f"Ready. Scenario: {SCENARIO}")


class Applicant(HttpUser):
    # Each simulated user waits 50-150 ms between requests (a fast but human-ish pace)
    wait_time = between(0.05, 0.15)

    def on_start(self):
        self.headers = {"Authorization": f"Bearer {random.choice(TOKENS)}"}

    @task
    def check_posting(self):
        posting = POSTING
        if SCENARIO == "miss":
            # A unique word changes the SHA-256, so the cache can never answer it
            posting = {**POSTING, "description": f"{POSTING['description']} ref {uuid.uuid4().hex}"}

        with self.client.post("/api/v1/check", json=posting, headers=self.headers,
                              name=f"POST /check [{SCENARIO}]", catch_response=True) as r:
            # (In the hit scenario the very first request is a MISS; that's expected, not a failure.)
            if r.status_code != 200:
                r.failure(f"HTTP {r.status_code}")
            elif SCENARIO == "miss" and r.headers.get("X-Cache") != "MISS":
                r.failure("expected a cache MISS")
