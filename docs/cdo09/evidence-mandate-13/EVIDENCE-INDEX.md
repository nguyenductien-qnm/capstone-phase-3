# Mandate 13 — Evidence Index

Map từng dòng bằng chứng → file log/screenshot cụ thể. **Hiện tại `logs/` và `screenshots/` còn trống** — bảng dưới đây là khung để điền sau khi `terraform apply` + ArgoCD sync + live load-test/spot-kill đã chạy trên cluster thật (xem `README.md` §3 "Việc còn lại"). Không điền tên file chưa tồn tại vào đây trước khi có file thật — mục đích của file này là truy vết được, không phải liệt kê dự định.

## Biến môi trường dùng xuyên suốt

```bash
export DV=arn:aws:eks:us-east-1:458580846647:cluster/ecommerce-develop-dev-eks
export NS=techx-develop
```

## Bảng Evidence

| # | Yêu cầu Directive | Bằng chứng cần | Lệnh / Cách lấy | File dự kiến (điền khi có) |
|---|---|---|---|---|
| 1a | **#1** EC2 → Instances, cột Lifecycle/Instance type/Architecture, **BEFORE** | Screenshot EC2 console trước khi Karpenter chạy spot | AWS Console → EC2 → Instances → ⚙️ thêm cột Lifecycle, Instance type, Architecture → filter tag `karpenter.sh/cluster` | `screenshots/before-ec2-instances.png` |
| 1b | **#1** EC2 → Instances, cùng cột, **AFTER** (spot xuất hiện) | Screenshot EC2 console sau khi có spot node | Cùng màn hình, sau khi load test chạy + Karpenter tạo spot node | `screenshots/after-ec2-instances.png` |
| 2a | **#2** Cost Explorer Usage Quantity by Purchase Option, **BEFORE** | Screenshot CE trước khi đổi | AWS Console → Billing → Cost Explorer → Metric = Usage Quantity (Hours) → Filter Service = EC2 Compute → Group by Purchase Option | `screenshots/before-cost-explorer-usage.png` |
| 2b | **#2** Cost Explorer Usage Quantity by Purchase Option, **AFTER** | Screenshot CE sau (spot > 50%) | Cùng report, chạy sau 24h | `screenshots/after-cost-explorer-usage.png` |
| 2c | **#2** Cost Explorer Usage Quantity by Instance Type (x86 → Graviton) | N/A — Graviton ngoài phạm vi lần này | Xem ADR Decision 4 | — |
| 3a | **#2,#5** Grafana "Node Count and Scaling" live trong load curve | Video hoặc chuỗi screenshot tại 5 mốc (baseline, 40u, 80u, 40u, 10u) | Port-forward Grafana → dashboard `kubernetes-scaling.json` → quay OBS/screen recorder xuyên suốt 30 phút load test | `logs/grafana-node-count-loadcurve.mp4` hoặc `screenshots/grafana-node-*-{1..5}.png` |
| 3b | **#5** Grafana checkout success ≥99% + p95 <1s suốt bài test | Screenshot SLO dashboard | Grafana → SLO Dashboard → screenshot lúc đang có tải | `screenshots/slo-dashboard-during-loadtest.png` |
| 4 | **#3** Live-kill 1 spot node giữa lúc có tải — 0 request rớt | Terminal log + Grafana screenshot | `aws ec2 terminate-instances --instance-ids <id>` + `kubectl -n $NS get pods -w` (xem SUBMISSION-GUIDE §6 cho script đầy đủ) | `logs/live-spot-kill.txt` + video nếu quay được |
| 5a | **#1,#5** `kubectl get nodes` trước/sau | kubectl output text | `kubectl --context "$DV" get nodes -L karpenter.sh/capacity-type,kubernetes.io/arch,eks.amazonaws.com/capacityType` | `logs/nodes-before.txt`, `logs/nodes-after.txt` |
| 5b | **#5** `kubectl get nodeclaims -o wide` | kubectl output text | `kubectl --context "$DV" get nodeclaims -o wide` | `logs/nodeclaims.txt` |
| 5c | **#3** Karpenter interrupt log | Controller log grep | `kubectl --context "$DV" -n kube-system logs deploy/karpenter -c controller \| grep -i "interrupt\|drain\|evict"` | `logs/karpenter-interrupt-log.txt` |
| 5d | **#3** PDB status | kubectl output text | `kubectl --context "$DV" -n "$NS" get pdb` | `logs/pdb-status.txt` |
| 6 | **Environment isolation** Sandbox plan "No changes" | PR comment từ CI bot | Copy nội dung comment sandbox plan trên PR (xem EXECUTION-GUIDE §3) | `logs/sandbox-plan-no-changes.txt` |

## Checklist điền evidence

Sau khi hoàn tất các Phase trong SUBMISSION-GUIDE, kiểm tra:

- [ ] Tất cả file trong cột cuối tồn tại trong `screenshots/` và `logs/`
- [ ] Không có file placeholder/trống
- [ ] Mỗi screenshot có annotation (timestamp, cluster name) nếu cần
- [ ] `README.md` §0 đã cập nhật trạng thái từ 🟡 sang ✅/❌

Lệnh chạy tương ứng nằm ở `mandate-13/EXECUTION-GUIDE.md` (§4-§8) và `mandate-13/SUBMISSION-GUIDE.md` (§3-§7).
