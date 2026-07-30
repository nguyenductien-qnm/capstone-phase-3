# TF1-72 [AIOps-W2] - Gioi han pham vi tac dong (Blast Radius, spec Sec4.3): toi da
# N hanh dong / scope / time_window. State RAM don gian, cung tinh than voi dedup +
# cooldown cua aiops/detector/alerter.py (khong can DB rieng cho MVP nay).
import time


class BlastRadiusGuard:
    def __init__(self, max_actions=1, time_window_seconds=3600):
        self.max_actions = max_actions
        self.time_window_seconds = time_window_seconds
        self._history = {}  # scope_key -> list[epoch giay da hanh dong]

    def allow(self, scope_key):
        """True neu con duoc phep hanh dong tren scope_key (vd 1 namespace) trong
        cua so thoi gian hien tai. KHONG tu dong ghi nhan - goi record() rieng sau
        khi da chac chan se hanh dong that (tranh dem hut khi bi tu choi o buoc khac)."""
        now = time.time()
        recent = [t for t in self._history.get(scope_key, []) if now - t < self.time_window_seconds]
        self._history[scope_key] = recent
        return len(recent) < self.max_actions

    def record(self, scope_key):
        now = time.time()
        self._history.setdefault(scope_key, []).append(now)
