# Mandate 20 — DR Backup & Restore — EVIDENCE PACK (nộp mentor)

> **TF:** CDO-09 · **Thực hiện:** Nguyen Dinh Thi (Reliability) · Mạnh Khang (AWS Backup / EBS)
> **Môi trường:**
> - **develop** (test) — account `458580846647`, cluster `ecommerce-develop-dev-eks`, ns `techx-develop`, VPC `10.60.0.0/16`
> - **sandbox** (production) — account `804372444787`, cluster `ecommerce-dev-eks`, ns `techx-tf1`, VPC `10.0.0.0/16`
> **Region:** `us-east-1` · **Ngày:** 27–28/07/2026
> **Nguyên tắc:** mọi số/kết quả bên dưới là output THẬT từ AWS CLI / kubectl chạy trực tiếp.

---

## 0. Tóm tắt cho mentor

| Yêu cầu đề | Trạng thái | Mục |
|---|---|---|
| #1 — Không sót store nào trên luồng ra tiền | ✅ Đạt (cả 2 env) | §1 |
| #2 — RPO/RTO rõ ràng + cadence tương xứng | ✅ Đạt | §2 |
| #3 — Point-in-time restore ra môi trường tách biệt | ✅ Đạt | §3 |
| #4 — Tested restore drill, đo RTO thật (tâm điểm) | ✅ Đạt — **RTO ≈ 20 phút, toàn vẹn 100%** | §3 |
| #5 — Backup an toàn: mã hoá + tách quyền | ✅ Đạt | §4 |

**Coverage được nhân đôi:** develop (chạy drill phá dữ liệu) và sandbox (production — chỉ bảo vệ, không phá). Backup mã hoá KMS, vault lock Governance đang enforce retention, và người vận hành thường bị chặn xoá backup ở **cả hai account**.

---

## 1. Yêu cầu #1 — Không sót store nào (backup coverage)

### 1.1 RDS PostgreSQL (orders/catalog/reviews)
```bash
aws rds describe-db-instances --db-instance-identifier ecommerce-develop-dev-postgres \
  --query 'DBInstances[0].{DelProt:DeletionProtection,CopyTags:CopyTagsToSnapshot,Retention:BackupRetentionPeriod,LatestRestorable:LatestRestorableTime}' \
  --output text --region us-east-1 --profile Phase3-CDO-PermissionSet-458580846647
```
**develop:** `DeletionProtection=True  CopyTagsToSnapshot=True  BackupRetentionPeriod=7  LatestRestorableTime=2026-07-27T17:09:19Z`
**sandbox** (`ecommerce-dev-postgres`, account 804): `DeletionProtection=True  CopyTagsToSnapshot=True  tag Backup=true`
→ Automated backup + PITR active; chống xoá nhầm primary.

### 1.2 ElastiCache Valkey (cart)
```bash
aws elasticache describe-replication-groups --replication-group-id ecommerce-develop-dev-valkey \
  --query 'ReplicationGroups[0].{Ret:SnapshotRetentionLimit,Win:SnapshotWindow}' --output text ...
```
**develop:** `7   03:00-04:00` · **sandbox** (`ecommerce-dev-valkey`): `7   03:00-04:00`
→ Snapshot hằng ngày cho giỏ hàng (trước Mandate 20: retention = 0, cart không có backup).

### 1.3 EBS Persistent Volumes (prometheus / opensearch)
StorageClass `gp3-observability` tự gắn tag `Backup=true` cho volume; volume hiện có cũng được gắn tag:
```bash
aws ec2 describe-volumes --filters "Name=tag:kubernetes.io/created-for/pvc/namespace,Values=techx-develop" \
  --query 'Volumes[].{Backup:Tags[?Key==`Backup`]|[0].Value,PVC:Tags[?Key==`kubernetes.io/created-for/pvc/name`]|[0].Value}' --output table ...
```
**develop & sandbox:** `Backup=true` cho `prometheus` và `opensearch`.

### 1.4 Trạng thái cụm & hạ tầng
GitOps (ArgoCD) quản toàn bộ manifest/Helm + Terraform state trên S3 (versioning) → dựng lại được cả cụm, không chỉ database.

### 1.5 Recovery point THẬT (đã sinh ra, không chỉ cấu hình)
```bash
aws backup list-recovery-points-by-backup-vault --backup-vault-name <vault> \
  --query 'RecoveryPoints[].{R:ResourceType,S:Status,Enc:IsEncrypted}' --output text ...
```
**develop** (`ecommerce-develop-dev-backup-vault`):
```
True  EBS  COMPLETED
True  EBS  COMPLETED
True  RDS  COMPLETED
True  RDS  COMPLETED
```
**sandbox** (`ecommerce-dev-backup-vault`):
```
True  EBS  COMPLETED
True  EBS  COMPLETED
```
→ Backup **thật sự sinh ra** recovery point (RDS + EBS), tất cả `Encrypted=true`. Không phải "đã bật nhưng chưa backup".

---

## 2. Yêu cầu #2 — RPO/RTO + cadence tương xứng

| Tầng | RPO cam kết | RTO cam kết | Cadence | Đủ đạt RPO? |
|---|---|---|---|---|
| RDS (orders/catalog/reviews) | ≤ 5 phút | ≤ 45 phút | PITR liên tục, retention 7 ngày | ✅ (đo thật §3) |
| Valkey (cart) | 24 giờ | ≤ 30 phút | snapshot hằng ngày 03:00-04:00 | ✅ (Valkey không có PITR — cam kết đúng năng lực) |
| EBS/PV (metrics) | 24 giờ | ≤ 2 giờ | AWS Backup daily `cron(0 3 * * ? *)` | ✅ |
| Trạng thái cụm | 0 (Git-driven) | ≤ 30 phút | mỗi commit | ✅ |

Backup plan (verify): `daily-backup-rule` `cron(0 3 * * ? *)`, selection theo tag `Backup=true`, `delete_after=7`. Chi tiết + lý do nghiệp vụ: ADR `docs/adr/adr-dr-backup-restore.md` (ký tên Thi + Khang).

---

## 3. Yêu cầu #3 & #4 — Tested PITR restore drill (TÂM ĐIỂM)

Chạy trên **develop**, schema thử nghiệm `drill_m20`. Mọi thao tác SQL qua **Pod trong VPC** (ns `techx-develop`); restore ra **instance tách biệt** `-drill-temp` (Security Group cô lập); **không** public access, **không** rule `0.0.0.0/0`.

### Bước 1 — Seed T0
```bash
kubectl -n techx-develop apply -f scripts/dr/pod_seed.yaml
kubectl -n techx-develop logs psql-drill-seed
```
→ `T0 = 2026-07-27T17:21:18Z` · `5|bc178e08178eafa1efd07da38e0ea875` (5 dòng + MD5 baseline).

### Bước 2 — Chờ cửa sổ PITR
```bash
aws rds describe-db-instances --db-instance-identifier ecommerce-develop-dev-postgres \
  --query 'DBInstances[0].LatestRestorableTime' --output text ...
```
→ `LatestRestorableTime` tiến tới `2026-07-27T17:24:20Z` (> mốc restore 17:22:00Z) → đủ điều kiện khôi phục chính xác về T0.

### Bước 3 — Giả lập mất dữ liệu (T1) + bấm giờ RTO + restore
```bash
kubectl -n techx-develop apply -f scripts/dr/pod_loss.yaml   # DROP SCHEMA drill_m20 CASCADE
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier ecommerce-develop-dev-postgres \
  --target-db-instance-identifier ecommerce-develop-dev-postgres-drill-temp \
  --restore-time 2026-07-27T17:22:00Z \
  --vpc-security-group-ids sg-028b54a0520f4455c --no-multi-az --no-publicly-accessible --storage-type gp3
```
→ `T1 / RTO_START = 2026-07-27T17:27:43Z`.

### Bước 4 — Chờ Available + kiểm tra toàn vẹn + dừng giờ
```bash
aws rds wait db-instance-available --db-instance-identifier ecommerce-develop-dev-postgres-drill-temp
kubectl -n techx-develop apply -f scripts/dr/pod_verify.yaml
kubectl -n techx-develop logs psql-drill-verify
```
→ verify: `count=5  md5=bc178e08178eafa1efd07da38e0ea875` — **khớp 100% T0**. `RTO_STOP = 2026-07-27T17:47:41Z`.

### 📊 Số đo
| | |
|---|---|
| **RTO thực đo** | 17:27:43Z → 17:47:41Z = **≈ 20 phút** (cam kết ≤ 45 ✅) |
| **RPO** | mốc restore chính xác đến giây; trong ≤ 5 phút ✅ |
| Toàn vẹn dữ liệu | MD5 khớp 100% ✅ |
| Point-in-time | schema DROP ở T1 **có lại** sau restore về T0 → đúng point-in-time, không phải restore bản mới nhất ✅ |
| Production | storefront phục vụ bình thường; blast radius gói trong schema `drill_m20` ✅ |
| Đồng hồ RTO | dừng khi **query ra đúng dữ liệu**, không phải khi DB vừa `Available` |

### Bước 5 — Cleanup sạch
```bash
kubectl -n techx-develop delete pod psql-drill-seed psql-drill-loss psql-drill-verify
aws rds delete-db-instance --db-instance-identifier ecommerce-develop-dev-postgres-drill-temp --skip-final-snapshot --delete-automated-backups
```
→ `describe-db-instances` không còn `-drill-temp`; SG cô lập trở lại nguyên trạng; 0 pod sót → **0 tài nguyên tạm còn lại**.

---

## 4. Yêu cầu #5 — Backup an toàn

### 4.1 Mã hoá at-rest (KMS CMK)
- RDS `storage_encrypted=true`; AWS Backup Vault mã hoá bằng KMS CMK riêng (key rotation bật, key policy chặn `ScheduleKeyDeletion`/`DisableKey`).
- **Mọi recovery point** ở §1.5 đều `Encrypted=true`.

### 4.2 Vault Lock (Governance) — enforce THẬT
```bash
aws backup describe-backup-vault --backup-vault-name ecommerce-dev-backup-vault \
  --query '{Locked:Locked,Min:MinRetentionDays,Max:MaxRetentionDays}' --output text ...
```
→ **sandbox:** `True  7  30` · **develop:** `Locked=True`.
Chứng minh enforce: backup on-demand **không** set lifecycle → job `FAILED` `"lifecycle is outside the valid range for backup vault"` (vượt Max 30 ngày); set `DeleteAfterDays=14` (trong `[7,30]`) → chạy thành công. → Vault Lock ép retention thật, không phải chỉ "đã bật".

### 4.3 Tách quyền — người vận hành KHÔNG xoá được backup (enforce cả 2 account)
Policy `dr-backup-protection-deny` deny 8 action xoá backup/snapshot, gắn vào Permission Set operator qua IAM Identity Center.

**Probe từ role vận hành THẬT** (`AWSReservedSSO_Phase3-CDO-PermissionSet`), thử xoá 1 snapshot không tồn tại (an toàn):
```bash
aws rds delete-db-snapshot --db-snapshot-identifier m20-deny-probe-nonexistent ...
```
- **develop (458):** `AccessDenied ... with an explicit deny in an identity-based policy: .../dr-backup-protection-deny`
- **sandbox (804):** `AccessDenied ... with an explicit deny in an identity-based policy: .../dr-backup-protection-deny`
- Đối chứng ngược: `rds:CreateDBSnapshot` → **không bị chặn** (không siết nhầm cơ chế tạo backup).

→ Tách quyền (separation-of-duties) enforce thật ở **cả develop và sandbox**: operator không xoá được backup, nhưng vẫn tạo được.

---

## 5. Bảng nghiệm thu tổng (đã kiểm chứng live)

| Hạng mục | develop (458) | sandbox (804) |
|---|---|---|
| RDS deletion_protection + copy_tags + PITR | ✅ | ✅ |
| Valkey snapshot 7 / 03:00-04:00 | ✅ | ✅ |
| AWS Backup Vault + Governance Lock `[7,30]` | ✅ | ✅ |
| Backup Plan daily `cron(0 3)` + selection tag | ✅ | ✅ |
| EBS/PV tag `Backup=true` | ✅ | ✅ |
| Recovery point (Encrypted) | RDS ✅ + EBS ✅ | EBS ✅ |
| IAM Deny xoá backup (probe AccessDenied) | ✅ | ✅ |
| Mã hoá KMS CMK | ✅ | ✅ |
| **Live PITR drill — RTO ≈ 20', toàn vẹn 100%** | ✅ | — (drill chỉ chạy ở test env theo đúng ràng buộc "không phá production") |

**Kết luận:** cả 5 yêu cầu của Mandate 20 đạt, có bằng chứng output thật. Trọng tâm — *tested restore drill* — đã chứng minh khôi phục dữ liệu về đúng mốc thời gian trước sự cố, trong RTO cam kết, dữ liệu toàn vẹn 100%, không ảnh hưởng production.

---

## Phụ lục — Tài liệu liên quan
- ADR ký tên: `docs/adr/adr-dr-backup-restore.md`
- Runbook restore: `docs/runbook/dr-restore.md`
- Script + Pod manifest drill: `scripts/dr/`
- IaC: `terraform/modules/{rds,elasticache,backup,backup_protection}`, `terraform/environments/{develop,sandbox}`
