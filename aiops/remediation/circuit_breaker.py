# TF1-72 [AIOps-W2] - Cau dao an toan (Circuit Breaker, spec Sec4.5): mo sau N lan
# verify that BAI LIEN TIEP cho cung 1 su co, tu dong dong lai sau reset_timeout.
#
# QUAN TRONG (RULES.md Sec8, bai hoc tu vu circuit-breaker LLM/product-reviews tung
# bi cham VI PHAM LUAT vi doc co flagd de tu quyet dinh hanh vi): breaker nay CHI
# duoc cap nhat tu ket qua verify THAT (verifier.py), KHONG BAO GIO doc bat ky co
# flagd nao o day hay o bat ky module remediation nao khac.
import time


class CircuitBreaker:
    def __init__(self, max_consecutive_failures=3, reset_timeout_seconds=86400):
        self.max_consecutive_failures = max_consecutive_failures
        self.reset_timeout_seconds = reset_timeout_seconds
        self._fail_count = {}      # key -> so lan fail lien tiep
        self._opened_at = {}       # key -> epoch giay luc mo (None = dang dong)

    def is_open(self, key):
        opened_at = self._opened_at.get(key)
        if opened_at is None:
            return False
        if time.time() - opened_at >= self.reset_timeout_seconds:
            # Het han freeze - tu dong dong lai, reset dem fail (spec: "reset_timeout").
            self._opened_at[key] = None
            self._fail_count[key] = 0
            return False
        return True

    def record_success(self, key):
        self._fail_count[key] = 0
        self._opened_at[key] = None

    def record_failure(self, key):
        """Tra ve True neu lan fail nay lam breaker VUA MO (de ban escalate alert)."""
        count = self._fail_count.get(key, 0) + 1
        self._fail_count[key] = count
        if count >= self.max_consecutive_failures and self._opened_at.get(key) is None:
            self._opened_at[key] = time.time()
            return True
        return False
