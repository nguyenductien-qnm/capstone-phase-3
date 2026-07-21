# Chaos & Containment verification — Mandate 17

Bộ script chứng minh **Resilience & Containment** cho readout. **Không chạy tự động** — chạy thủ công khi có cluster + `kubectl` trỏ đúng context (staging/sandbox), không chạy trên production.

| Script | Yêu cầu | Chứng minh |
|--------|---------|-----------|
| `kill-dependency.sh <svc> [ns] [giây]` | R1 (CDO-224/235) | Giết `ad`/`recommendation` → luồng ra tiền vẫn giữ SLO nhờ circuit breaker + fallback ở frontend |
| `drain-az.sh <zone>` | R2 (CDO-227/235) | Mất trọn 1 AZ → pod dồn sang AZ còn lại, SLO giữ |
| `attacker-check.sh [ns]` | R3/R4 (CDO-231/234/236) | Pod attacker không quét sang service khác, không egress, không gọi K8s API |

## Chuẩn bị trước khi verify
1. **R1 đã có sẵn trong code frontend** (Ad/Recommendations gateway) — chỉ cần deploy image mới.
2. **R2**: chart đã bật zone spread + Karpenter `minValues:2` — deploy là có.
3. **R3**: bật NetworkPolicy: `helm upgrade ... --set networkPolicy.enabled=true` (đã review đồ thị `serviceIngress` trong `values.yaml`).
4. **R4**: `automountServiceAccountToken:false` là mặc định — deploy là có.

## Evidence pack (CDO-237)
Chụp/thu cho readout: dashboard Grafana SLO trong lúc chaos, output 3 script, `kubectl get pods -o wide` (phân bố AZ), kết quả `attacker-check`.

> ⚠️ Cần điền AZ thật cho `drain-az.sh`. Khôi phục node bằng `kubectl uncordon` sau khi đo.
