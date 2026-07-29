# 📊 AI Engineering Optimization Ledger

*Cập nhật lần cuối: 2026-07-29 16:30:15*

## Danh sách Variant đã thử nghiệm

| Variant ID | Min Sim | Rule Guard | Hit Rate | Latency (Hit p50) | False Hits | Hard Bar Pass? | Trạng thái |
|---|---|---|---|---|---|---|---|
| `v0_baseline_sim_0.85_guard` | 0.85 | ✅ | 37.5% | 1.08s | 0 | ✅ | 📌 BASELINE |
| `variant_sim_0.75_with_guard` | 0.75 | ✅ | 37.5% | 1.10s | 1 | ❌ | ❌ SAFETY FAIL |
| `variant_sim_0.75_no_guard` | 0.75 | ❌ | 50.0% | 1.10s | 2 | ❌ | ❌ SAFETY FAIL |
| `variant_sim_0.80_with_guard` | 0.8 | ✅ | 37.5% | 1.09s | 0 | ✅ | ⚠️ SUBOPTIMAL |
| `variant_sim_0.85_with_guard` | 0.85 | ✅ | 37.5% | 1.08s | 0 | ✅ | ⚠️ SUBOPTIMAL |
| `variant_sim_0.90_with_guard` | 0.9 | ✅ | 0.0% | 1.07s | 0 | ✅ | ⚠️ SUBOPTIMAL |
| `variant_sim_0.92_with_guard` | 0.92 | ✅ | 0.0% | 1.07s | 0 | ✅ | ⚠️ SUBOPTIMAL |
| `variant_sim_0.95_with_guard` | 0.95 | ✅ | 0.0% | 1.06s | 0 | ✅ | ⚠️ SUBOPTIMAL |

---
## 🏆 Variant Chiến Thắng Hiện Tại (Current Winner)

- **ID:** `v0_baseline_sim_0.85_guard`
- **Cấu hình:** `SEMANTIC_CACHE_MIN_SIM = 0.85`
- **Hit Rate:** `37.5%`
- **Latency Hit p50:** `1.08s`
- **False Hits:** `0`
- **Mô tả:** Recall: 75.0%, False Hits: 0