"""Deterministic experiment: does the bulkhead protect GetProductReviews?

Model of product_reviews_server.py: sync gRPC ThreadPoolExecutor(max_workers=10),
LLM calls guarded by threading.Semaphore. Fast task = GetProductReviews (~10ms DB read).

Scenarios:
  A) Semaphore(10), blocking acquire  -- current merged code
  B) Semaphore(6),  blocking acquire  -- "obvious" fix (semaphore < pool)
  C) Semaphore(6),  non-blocking acquire -> instant mock fallback
"""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

LLM_CALL_SECONDS = 2.0  # slow Bedrock call
N_LLM_REQUESTS = 12     # burst of Ask-AI requests (> pool size)


def run_scenario(name, sema_size, blocking):
    pool = ThreadPoolExecutor(max_workers=10)
    sema = threading.Semaphore(sema_size)

    def llm_task():
        if blocking:
            with sema:
                time.sleep(LLM_CALL_SECONDS)
            return "llm"
        else:
            if not sema.acquire(blocking=False):
                return "mock"  # fail-fast fallback, thread freed immediately
            try:
                time.sleep(LLM_CALL_SECONDS)
            finally:
                sema.release()
            return "llm"

    def fast_task():  # GetProductReviews stand-in
        time.sleep(0.01)
        return "reviews"

    for _ in range(N_LLM_REQUESTS):
        pool.submit(llm_task)
    time.sleep(0.1)  # storefront request arrives right after the burst

    t0 = time.monotonic()
    fut = pool.submit(fast_task)
    fut.result()
    latency = time.monotonic() - t0
    pool.shutdown(wait=True)
    print(f"{name}: GetProductReviews latency = {latency*1000:8.1f} ms")
    return latency


if __name__ == "__main__":
    a = run_scenario("A) sema=10, blocking (code hien tai)  ", 10, True)
    b = run_scenario("B) sema=6,  blocking (fix 'hien nhien')", 6, True)
    c = run_scenario("C) sema=6,  non-blocking -> mock       ", 6, False)
    print()
    print("Ket luan:")
    print(f"  A starved: {a > 1.0} | B starved: {b > 1.0} | C protected: {c < 0.5}")
