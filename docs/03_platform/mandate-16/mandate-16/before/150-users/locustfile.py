#!/usr/bin/python
"""Simplified load generator for Phase 3 baseline testing.
No OpenTelemetry instrumentation - just HTTP load generation.
"""

import json
import os
import random
import uuid

from locust import HttpUser, task, between

categories = [
    "binoculars",
    "telescopes",
    "accessories",
    "assembly",
    "travel",
    "books",
    None,
]

products = [
    "0PUK6V6EV0",
    "1YMWWN1N4O",
    "2ZYFJ3GM2N",
    "66VCHSJNUP",
    "6E92ZMYYFZ",
    "9SIQT8TOJO",
    "L9ECAV7KIM",
    "LS4PSXUNUM",
    "OLJCESPC7Z",
    "HQTGWGPNH4",
]

people_file_path = os.path.join(
    os.path.dirname(__file__),
    '..',
    'xbrain-cap2-cdo5',
    'techx-corp-platform',
    'src',
    'load-generator',
    'people.json',
)
people_file = open(people_file_path)
people = json.load(people_file)


class WebsiteUser(HttpUser):
    wait_time = between(1, 10)

    @task(1)
    def index(self):
        self.client.get("/")

    @task(10)
    def browse_product(self):
        product = random.choice(products)
        self.client.get("/api/products/" + product)

    @task(3)
    def get_recommendations(self):
        product = random.choice(products)
        params = {"productIds": [product]}
        self.client.get("/api/recommendations", params=params)

    @task(2)
    def get_product_reviews(self):
        product = random.choice(products)
        self.client.get("/api/product-reviews/" + product)

    @task(3)
    def get_ads(self):
        category = random.choice(categories)
        params = {"contextKeys": [category]}
        self.client.get("/api/data/", params=params)

    @task(3)
    def view_cart(self):
        self.client.get("/api/cart")

    @task(2)
    def add_to_cart(self, user=""):
        if user == "":
            user = str(uuid.uuid1())
        product = random.choice(products)
        quantity = random.choice([1, 2, 3, 4, 5, 10])
        self.client.get("/api/products/" + product)
        cart_item = {
            "item": {"productId": product, "quantity": quantity},
            "userId": user,
        }
        self.client.post("/api/cart", json=cart_item)

    @task(1)
    def checkout(self):
        user = str(uuid.uuid1())
        self.add_to_cart(user=user)
        checkout_person = random.choice(people)
        checkout_person["userId"] = user
        self.client.post("/api/checkout", json=checkout_person)

    @task(1)
    def checkout_multi(self):
        user = str(uuid.uuid1())
        item_count = random.choice([2, 3, 4])
        for i in range(item_count):
            self.add_to_cart(user=user)
        checkout_person = random.choice(people)
        checkout_person["userId"] = user
        self.client.post("/api/checkout", json=checkout_person)

    def on_start(self):
        session_id = str(uuid.uuid4())
        self.index()
