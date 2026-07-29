#!/usr/bin/python
# Mandate-19 CATALOG flow + built-in step-load shape. Headless, self-driving.
# Plan §7.1 (one flow=one class) + §5.4 step load. Emits CSV via --csv so we
# read per-step RPS/p95 without poking any web API.
import random
from locust import HttpUser, task, between, LoadTestShape

PRODUCTS = ["0PUK6V6EV0","1YMWWN1N4O","2ZYFJ3GM2N","66VCHSJNUP","6E92ZMYYFZ",
            "9SIQT8TOJO","L9ECAV7KIM","LS4PSXUNUM","OLJCESPC7Z","HQTGWGPNH4"]

class CatalogFlowUser(HttpUser):
    wait_time = between(1, 3)
    @task(3)
    def view_product(self):
        self.client.get(f"/api/products/{random.choice(PRODUCTS)}", name="/api/products/:id")
    @task(1)
    def list_products(self):
        self.client.get("/api/products", name="/api/products")

class StepShape(LoadTestShape):
    # (end_time_seconds, users, spawn_rate). Plan bậc 5/10/20/40, mỗi bậc 240s.
    # Idle handled by starting at t=0 with 5 users (idle baseline đo riêng trước khi chạy).
    stages = [
        (240,  5, 2),
        (480, 10, 2),
        (720, 20, 3),
        (960, 40, 4),
    ]
    def tick(self):
        t = self.get_run_time()
        for end, users, rate in self.stages:
            if t < end:
                return (users, rate)
        return None
