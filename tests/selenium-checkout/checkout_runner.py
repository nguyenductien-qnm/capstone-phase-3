#!/usr/bin/env python3

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Exercise checkout through the browser so the React client owns idempotency."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as expected
from selenium.webdriver.support.ui import WebDriverWait


PRODUCT_CARD = '[data-cy="product-card"]'
ADD_TO_CART = '[data-cy="product-add-to-cart"]'
PLACE_ORDER = '[data-cy="checkout-place-order"]'
CHECKOUT_ITEM = '[data-cy="checkout-item"]'


@dataclass(frozen=True)
class CheckoutResult:
    worker: int
    iteration: int
    success: bool
    latency_ms: int
    order_id: str = ""
    idempotency_key: str = ""
    error: str = ""


def chrome_options(headless: bool) -> webdriver.ChromeOptions:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1440,1200")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return options


def create_driver(remote_url: str, headless: bool) -> webdriver.Remote:
    options = chrome_options(headless)
    if remote_url:
        return webdriver.Remote(command_executor=remote_url, options=options)
    return webdriver.Chrome(options=options)


def reset_browser_session(driver: webdriver.Remote, base_url: str) -> None:
    driver.get(base_url)
    driver.delete_all_cookies()
    driver.execute_script("window.localStorage.clear(); window.sessionStorage.clear();")
    driver.refresh()


def header_value(headers: dict[str, object], name: str) -> str:
    for header_name, value in headers.items():
        if header_name.lower() == name.lower():
            return str(value)
    return ""


def wait_for_checkout_idempotency_key(
    driver: webdriver.Remote,
    timeout_seconds: float,
) -> str:
    checkout_request_ids: set[str] = set()
    headers_by_request: dict[str, dict[str, object]] = {}
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        for entry in driver.get_log("performance"):
            message = json.loads(entry["message"])["message"]
            method = message.get("method")
            params = message.get("params", {})
            request_id = str(params.get("requestId", ""))

            if method == "Network.requestWillBeSent":
                request = params.get("request", {})
                request_path = urlparse(str(request.get("url", ""))).path
                if request.get("method") == "POST" and request_path == "/api/checkout":
                    checkout_request_ids.add(request_id)
                    headers_by_request.setdefault(request_id, {}).update(request.get("headers", {}))
            elif method == "Network.requestWillBeSentExtraInfo":
                headers_by_request.setdefault(request_id, {}).update(params.get("headers", {}))

        for request_id in checkout_request_ids:
            key = header_value(headers_by_request.get(request_id, {}), "Idempotency-Key")
            if key:
                return key
        time.sleep(0.1)
    return ""


def run_checkout(
    driver: webdriver.Remote,
    wait: WebDriverWait,
    timeout_seconds: float,
    base_url: str,
    worker: int,
    iteration: int,
) -> CheckoutResult:
    started = time.perf_counter()
    try:
        reset_browser_session(driver, base_url)
        cards = wait.until(expected.presence_of_all_elements_located((By.CSS_SELECTOR, PRODUCT_CARD)))
        if not cards:
            raise RuntimeError("storefront returned no product cards")
        cards[(worker + iteration) % len(cards)].click()

        wait.until(expected.element_to_be_clickable((By.CSS_SELECTOR, ADD_TO_CART))).click()
        wait.until(lambda current: urlparse(current.current_url).path == "/cart")
        wait.until(expected.element_to_be_clickable((By.CSS_SELECTOR, PLACE_ORDER)))

        # Discard navigation noise so the captured request belongs to this checkout.
        driver.get_log("performance")
        driver.find_element(By.CSS_SELECTOR, PLACE_ORDER).click()
        wait.until(lambda current: "/cart/checkout/" in urlparse(current.current_url).path)
        wait.until(expected.presence_of_element_located((By.CSS_SELECTOR, CHECKOUT_ITEM)))

        path = urlparse(driver.current_url).path
        order_id = path.rstrip("/").rsplit("/", 1)[-1]
        key = wait_for_checkout_idempotency_key(driver, min(5, timeout_seconds))
        if not key:
            raise RuntimeError("browser checkout request did not contain Idempotency-Key")
        uuid.UUID(key)
        if not order_id:
            raise RuntimeError("checkout result URL did not contain an order ID")

        return CheckoutResult(
            worker=worker,
            iteration=iteration,
            success=True,
            latency_ms=round((time.perf_counter() - started) * 1000),
            order_id=order_id,
            idempotency_key=key,
        )
    except Exception as error:
        return CheckoutResult(
            worker=worker,
            iteration=iteration,
            success=False,
            latency_ms=round((time.perf_counter() - started) * 1000),
            error=f"{type(error).__name__}: {error}",
        )


def run_worker(
    worker: int,
    iterations: int,
    base_url: str,
    remote_url: str,
    headless: bool,
    timeout_seconds: float,
) -> list[CheckoutResult]:
    driver = create_driver(remote_url, headless)
    driver.set_page_load_timeout(timeout_seconds)
    wait = WebDriverWait(driver, timeout_seconds)
    try:
        return [
            run_checkout(driver, wait, timeout_seconds, base_url, worker, iteration)
            for iteration in range(1, iterations + 1)
        ]
    finally:
        driver.quit()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run concurrent checkout journeys through Chrome/Selenium.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("SELENIUM_BASE_URL", "http://localhost:8080"),
        help="Storefront URL (default: SELENIUM_BASE_URL or http://localhost:8080).",
    )
    parser.add_argument(
        "--remote-url",
        default=os.getenv("SELENIUM_REMOTE_URL", ""),
        help="Optional Selenium Grid URL, for example http://localhost:4444/wd/hub.",
    )
    parser.add_argument("--workers", type=int, default=1, help="Concurrent browser sessions.")
    parser.add_argument("--iterations", type=int, default=1, help="Checkouts per browser session.")
    parser.add_argument("--timeout", type=float, default=30, help="Per-step timeout in seconds.")
    parser.add_argument("--headed", action="store_true", help="Show local Chrome instead of running headless.")
    parser.add_argument("--output", type=Path, help="Optional JSON result path.")
    args = parser.parse_args()
    if args.workers < 1 or args.iterations < 1 or args.timeout <= 0:
        parser.error("workers, iterations, and timeout must be positive")
    return args


def main() -> int:
    args = parse_args()
    results: list[CheckoutResult] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                run_worker,
                worker,
                args.iterations,
                args.base_url.rstrip("/"),
                args.remote_url,
                not args.headed,
                args.timeout,
            )
            for worker in range(1, args.workers + 1)
        ]
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as error:
                print(f"worker failed before checkout: {type(error).__name__}: {error}", file=sys.stderr)

    results.sort(key=lambda item: (item.worker, item.iteration))
    successful = [result for result in results if result.success]
    failed = [result for result in results if not result.success]
    summary = {
        "base_url": args.base_url,
        "workers": args.workers,
        "iterations_per_worker": args.iterations,
        "attempted": args.workers * args.iterations,
        "recorded": len(results),
        "succeeded": len(successful),
        "failed": args.workers * args.iterations - len(successful),
        "latency_ms": {
            "min": min((result.latency_ms for result in successful), default=None),
            "median": statistics.median((result.latency_ms for result in successful)) if successful else None,
            "max": max((result.latency_ms for result in successful), default=None),
        },
        "results": [asdict(result) for result in results],
    }
    rendered = json.dumps(summary, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if failed or len(results) != args.workers * args.iterations else 0


if __name__ == "__main__":
    raise SystemExit(main())
