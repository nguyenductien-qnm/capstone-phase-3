"""Continuous stepped load shape for the Mandate 16 after benchmark."""

from locust import LoadTestShape

# Reuse the production-like workload without modifying locustfile.py.
from locustfile import WebsiteUser  # noqa: F401


class Mandate16AfterShape(LoadTestShape):
    """100 users/5m -> 200 users/5m -> 300 users/15m, without pauses."""

    stages = (
        {"duration": 5 * 60, "users": 100, "spawn_rate": 25},
        {"duration": 10 * 60, "users": 200, "spawn_rate": 50},
        {"duration": 25 * 60, "users": 300, "spawn_rate": 75},
    )

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
