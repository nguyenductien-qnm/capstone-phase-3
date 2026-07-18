# AIOps Closed-loop Auto-remediation — TF1-72 [AIOps-W2]

Vòng khép kín xử lý sự cố tự động: nhận tín hiệu từ [`aiops/detector/`](../detector/) (rule `oom-detected`), qua các lớp an toàn, rồi hành động. Đây là "Engine" trong sơ đồ closed-loop của [`docs/ai/03_specs/anomaly_remediation.md`](../../docs/ai/03_specs/anomaly_remediation.md).

> **Phạm vi MVP:** CHỈ 1 action (`k8s_restart_pod`) cho CHỈ 1 kịch bản (OOM). Không làm `scale`/`clear cache` — không có trong spec đã duyệt. Không sửa `aiops/detector/` — tự poll OpenSearch riêng.

## Vì sao tách riêng khỏi detector

`aiops/detector/` chạy với **0 quyền Kubernetes** (không ServiceAccount, không Role) — cố tình, vì nó chỉ detect+alert. Remediation cần quyền **ghi** lên pod (xoá để restart) nên phải là component riêng, ServiceAccount/RBAC riêng, tối thiểu quyền (`pods: get/list/watch/delete`, không hơn) — xem [`deploy/rbac.yaml`](deploy/rbac.yaml).

## Vòng khép kín (5 lớp an toàn, `remediation_policy.yaml`)

```
oom-detected (rule cua detector, tai dung qua OpenSearchClient)
   │
   ▼
find_oom_pods() ── xac nhan qua K8s API that (khong doan qua text log)
   │
   ├─ Circuit breaker dang MO? ──yes──► tu choi + escalate
   ├─ Error budget can (>0.5% loi)? ──yes──► Halt + Page Human
   ├─ Blast-radius vuot (>1 pod/namespace/gio)? ──yes──► tu choi + escalate
   ├─ dry_run=true? ──yes──► chi log + alert info, KHONG goi K8s
   │
   ▼
restart_pod() ── xoa pod, ReplicaSet tu tao lai
   │
   ▼
verify_oom_recovery() ── poll 120s/lần 20s, pass = Ready ổn định + không OOM mới
   │
   ├─ PASS ──► reset circuit breaker, alert info
   └─ FAIL ──► tăng circuit breaker (KHÔNG "rollback" giả — action restart-pod
               không đổi config gì để mà hoàn tác); mở CB sau 3 lần liên tiếp
```

**Ràng buộc sinh tử (RULES.md §8):** không module nào ở đây được đọc/gọi flagd, kể cả "phòng thủ" — có test tường minh (`test_no_flagd_or_helm_reference_anywhere_in_remediation_module`) canh việc này.

## Chạy (local/dev)

```sh
pip install -r requirements.txt

export PROM_URL=http://localhost:9090
export OPENSEARCH_URL=http://localhost:9200
export KUBECONFIG=~/.kube/config          # hoặc port-forward + context đúng cluster
export REMEDIATION_DRY_RUN=true           # AN TOÀN mặc định — đổi "false" mới act thật

python remediation.py --once --dry-run    # 1 vòng, ép dry-run tuyệt đối
python remediation.py                     # chạy liên tục theo poll_interval_seconds
```

## Test

```sh
pytest -q   # 14 test: blast-radius, circuit-breaker (đơn vị), process_oom_policy
            # (tích hợp, mock K8s/Prometheus/OpenSearch), guard test flagd/helm
```

## Deploy in-cluster

```sh
# Build context PHẢI là aiops/ (cha của detector/ và remediation/) — xem Dockerfile
docker buildx build -f aiops/remediation/Dockerfile \
  -t <ECR>/techx-corp:1.0-aiops-remediation --push aiops

kubectl -n techx-tf1 apply -f deploy/rbac.yaml
kubectl -n techx-tf1 apply -f deploy/deployment.yaml   # khởi động với dry_run=true
```

## Số liệu — GIẢ ĐỊNH ban đầu, cần đo thật (TF1-72 Done criteria)

`remediation_policy.yaml` hiện dùng 3 số từ spec (chưa validate bằng chaos test thật trên EKS):

| Số | Giá trị hiện tại | Nguồn |
|---|---|---|
| Verify timeout | 120s, poll mỗi 20s | `anomaly_remediation.md` §4.4 |
| Circuit breaker | mở sau 3 fail liên tiếp, tự đóng sau 24h | `anomaly_remediation.md` §4.5 |
| Blast radius | 1 pod / namespace / 1 giờ | `anomaly_remediation.md` §4.3 |

Kế hoạch đo thật: bật flag `emailMemoryLeak` trên EKS → OOM thật service `email` → chạy remediation live → đo timing thật → cập nhật bảng trên + ghi báo cáo `report/` (mẫu `report/flagd1/postmortem-INC-01.md`).

## Ranh giới với các task AIOps khác

| Task | Quan hệ |
|---|---|
| TF1-53 Detector | Nguồn tín hiệu (`oom-detected`) — remediation tự poll riêng, không sửa code detector |
| TF1-52 Drain3 Log Clustering | Chưa tích hợp — ngoài scope MVP này |
| TF1-49 Golden Signal (EWMA) | `error_budget_check` tái dùng query 5xx-ratio đã có, chưa dùng EWMA riêng |
