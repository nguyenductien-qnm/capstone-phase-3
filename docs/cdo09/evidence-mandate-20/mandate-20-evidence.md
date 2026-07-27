# Mandate 20 — DR Backup & Restore — EVIDENCE PACK

> **TF:** CDO-09 · **Người thực hiện:** Nguyen Dinh Thi (Reliability) · Mạnh Khang (AWS Backup / cleanup)
> **Môi trường test:** develop — RDS `ecommerce-develop-dev-postgres`, cluster `ecommerce-develop-dev-eks` (account 458580846647), namespace `techx-develop`, VPC `10.60.0.0/16`
> **PR:** feat/m20 (RDS/Valkey coverage + KMS/IAM + scripts) · #461 (pod manifest, Khang) — đã merge `develop`
> **Ngày test:** **27/07/2026**, ~17:20–17:55 UTC

---

## 0. Tóm tắt cho mentor

| Yêu cầu đề | Trạng thái | Bằng chứng |
|---|---|---|
| #1 — Không sót store nào trên luồng ra tiền | ✅ Pass | §1 (RDS, Valkey, EBS/vault, cluster state) |
| #2 — RPO/RTO rõ + cadence tương xứng | ✅ Pass | §2 + ADR |
| #3 — Point-in-time restore ra môi trường tách biệt | ✅ Pass | §3 |
| #4 — Tested restore drill, đo RTO thật (tâm điểm) | ✅ Pass — **RTO ≈ 20 phút** | §3 |
| #5 — Backup an toàn: mã hoá + tách quyền | ⚠️ Pass một phần | §4 — vault lock enforce ✅, mã hoá ✅, **deny policy chưa attach vào Permission Set** (nợ, đã ghi ADR) |

**Nguyên tắc:** mọi số/kết quả dưới đây là output THẬT từ AWS CLI / kubectl chạy trực tiếp trên develop.

### Vì sao phải chạy drill thật, không chỉ "đã bật backup"
Đề nói thẳng: chỗ hầu hết đội gãy là "đã bật backup nhưng chưa từng restore thử". Buổi này gây mất dữ liệu có kiểm soát rồi khôi phục thật — và lộ ra 3 thứ chỉ chạy thật mới thấy:
1. **PITR có độ trễ ~5 phút** (`LatestRestorableTime`) — không thể restore về mốc vừa mới ghi; phải chờ mốc đó nằm trong cửa sổ khôi phục. Nếu drill "seed → drop → restore" liền tay sẽ FAIL.
2. **Vault Lock enforce thật** — backup không set lifecycle bị **từ chối** vì vượt Max retention 30 ngày (không phải chỉ "đã bật lock").
3. **Deny policy tồn tại ≠ đang bảo vệ** — policy đúng nội dung nhưng **chưa gắn vào principal** nên operator vẫn xoá được backup. Chỉ probe từ role thật mới phát hiện.

---

## 1. Yêu cầu #1 — Không sót store nào (backup coverage)

### RDS PostgreSQL (CDO-252)
```bash
aws rds describe-db-instances --db-instance-identifier ecommerce-develop-dev-postgres \
  --query 'DBInstances[0].{DelProt:DeletionProtection,CopyTags:CopyTagsToSnapshot,Retention:BackupRetentionPeriod,LatestRestorable:LatestRestorableTime}' \
  --region us-east-1 --profile Phase3-CDO-PermissionSet-458580846647
```
**Kết quả:** `DeletionProtection=True  CopyTagsToSnapshot=True  BackupRetentionPeriod=7  LatestRestorableTime=2026-07-27T17:09:19Z` → automated backup + PITR active.

### ElastiCache Valkey — cart (CDO-253)
```bash
aws elasticache describe-replication-groups --replication-group-id ecommerce-develop-dev-valkey \
  --query 'ReplicationGroups[0].{Retention:SnapshotRetentionLimit,Window:SnapshotWindow}' ...
```
**Kết quả:** `SnapshotRetentionLimit=7  SnapshotWindow=03:00-04:00`. *(Trước Mandate 20: retention=0 — cart hoàn toàn không có backup.)*

### EBS/PV + AWS Backup (CDO-254/259)
```bash
aws backup list-backup-vaults  --query 'BackupVaultList[].{Name:BackupVaultName,Locked:Locked}'
aws backup list-backup-plans   --query 'BackupPlansList[].BackupPlanName'
aws backup get-backup-plan --backup-plan-id <id> --query 'BackupPlan.Rules[].{Schedule:ScheduleExpression}'
```
**Kết quả:** Vault `ecommerce-develop-dev-backup-vault` **Locked=True** (Governance) · Plan `ecommerce-develop-dev-backup-plan` · rule `daily-backup-rule` `cron(0 3 * * ? *)` · RDS đã gắn tag `Backup=true` → được selection bắt.

### Trạng thái cụm
GitOps (ArgoCD) + Terraform state trên S3 (versioning) → dựng lại được, không chỉ backup database. (Xem ADR §2.)

### MSK
Kênh vận chuyển; source of truth là RDS → tuyên bố ngoài phạm vi snapshot trong ADR §2 (có lập luận).

---

## 2. Yêu cầu #2 — RPO/RTO + cadence

| Tầng | RPO cam kết | RTO cam kết | Cadence | Đủ đạt RPO? |
|---|---|---|---|---|
| RDS | ≤ 5 phút | ≤ 45 phút | PITR liên tục, retention 7 ngày | ✅ (đo thật §3) |
| Valkey (cart) | 24 giờ | ≤ 30 phút | snapshot hằng ngày 03:00-04:00 | ✅ (Valkey không có PITR — cam kết đúng năng lực, mất giỏ hàng chấp nhận được) |
| EBS/PV | 24 giờ | ≤ 2 giờ | AWS Backup daily 03:00 | ✅ |
| Cluster state | 0 (Git) | ≤ 30 phút | mỗi commit | ✅ |

Chi tiết + lý do nghiệp vụ: `docs/adr/adr-dr-backup-restore.md`.

---

## 3. Yêu cầu #3 & #4 — Tested PITR restore drill (TÂM ĐIỂM)

Toàn bộ thao tác SQL chạy từ **Pod trong VPC** (ns `techx-develop`); restore ra **instance tách biệt** `-drill-temp` (SG cô lập `sg-028b54a0520f4455c`); **không** public access, **không** rule `0.0.0.0/0`.

### Bước 1 — Seed T0
```bash
kubectl -n techx-develop apply -f scripts/dr/pod_seed.yaml
kubectl -n techx-develop logs psql-drill-seed
```
**Kết quả:** `T0 = 2026-07-27T17:21:18Z` · `5|bc178e08178eafa1efd07da38e0ea875` (5 dòng + MD5 baseline).

### Bước 2 — Chờ PITR window (bài học độ trễ ~5 phút)
```bash
# poll LatestRestorableTime tới khi >= restore point 17:22:00Z
aws rds describe-db-instances ... --query 'DBInstances[0].LatestRestorableTime'
```
**Kết quả:** đứng ở `17:19:20Z` một lúc, đến `17:27:13Z` nhảy lên `17:24:20Z` (> 17:22:00) → đủ điều kiện restore. *(Nếu drop-restore liền tay lúc 17:22 sẽ FAIL "time not available".)*

### Bước 3 — Loss T1 + bấm giờ RTO + restore
```bash
kubectl -n techx-develop apply -f scripts/dr/pod_loss.yaml   # DROP SCHEMA drill_m20 CASCADE
# -> log: "DROP SCHEMA / DATA_LOSS_EVENT_COMPLETED"
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier ecommerce-develop-dev-postgres \
  --target-db-instance-identifier ecommerce-develop-dev-postgres-drill-temp \
  --restore-time 2026-07-27T17:22:00Z \
  --vpc-security-group-ids sg-028b54a0520f4455c --no-multi-az --no-publicly-accessible --storage-type gp3
aws ec2 authorize-security-group-ingress --group-id sg-028b54a0520f4455c \
  --protocol tcp --port 5432 --source-group sg-020a47c4e27b942ed   # mở tạm cho pod verify
```
**Kết quả:** `T1 / RTO_START = 2026-07-27T17:27:43Z` · restore `creating`.

### Bước 4 — Chờ available + verify + dừng giờ
```bash
aws rds wait db-instance-available --db-instance-identifier ecommerce-develop-dev-postgres-drill-temp
kubectl -n techx-develop apply -f scripts/dr/pod_verify.yaml   # sed đổi host proxy -> drill-temp
kubectl -n techx-develop logs psql-drill-verify
```
**Kết quả:** available lúc `17:47:08Z`; verify: `count=5  md5=bc178e08178eafa1efd07da38e0ea875` → **khớp 100% T0**. `RTO_STOP = 17:47:41Z`.

### 📊 Số đo
| | |
|---|---|
| **RTO thực đo** | 17:27:43Z → 17:47:41Z = **≈ 20 phút** (≤ 45 cam kết ✅) |
| **RPO** | mốc restore về giây; không ghi gì giữa restore point và loss → mất 0; trong ≤ 5 phút ✅ |
| Toàn vẹn dữ liệu | MD5 khớp 100% ✅ |
| Point-in-time proof | schema DROP ở T1 **có lại** sau restore về T0 → không phải restore bản mới nhất ✅ |
| Production | storefront phục vụ bình thường; blast radius gói trong schema `drill_m20` ✅ |

### Bước 5 — Cleanup (đo được)
```bash
kubectl -n techx-develop delete pod psql-drill-seed psql-drill-loss psql-drill-verify
aws rds delete-db-instance --db-instance-identifier ecommerce-develop-dev-postgres-drill-temp --skip-final-snapshot --delete-automated-backups
aws ec2 revoke-security-group-ingress --group-id sg-028b54a0520f4455c --protocol tcp --port 5432 --source-group sg-020a47c4e27b942ed
```
**Kết quả:** `describe-db-instances` không còn `-drill-temp`; drill SG về đúng 1 rule gốc `127.0.0.1/32`; 0 pod sót → **0 tài nguyên tạm còn lại**.

---

## 4. Yêu cầu #5 — Backup an toàn

### 4.1 Vault Lock enforce THẬT (không chỉ "đã bật")
```bash
# on-demand backup KHÔNG set lifecycle
aws backup start-backup-job --backup-vault-name ecommerce-develop-dev-backup-vault --resource-arn <rds> --iam-role-arn <role>
```
**Kết quả:** job `FAILED` — `"Backup job failed because the lifecycle is outside the valid range for backup vault"` (∞ retention > Max 30 ngày). Chạy lại với `--lifecycle DeleteAfterDays=14` (trong [7,30]) → `RUNNING` OK. → Governance Vault Lock đang ép retention thật.

### 4.2 Mã hoá at-rest
RDS `storage_encrypted=true`; vault gắn KMS CMK (module backup). Recovery point sinh ra được mã hoá.

### 4.3 Tách quyền (IAM Deny) — cơ chế ĐÚNG, **attach còn nợ**
Policy `ecommerce-develop-dev-dr-backup-protection-deny` deny 8 action xoá backup.

**Simulation:**
```bash
aws iam simulate-custom-policy --policy-input-list '<Allow *>' '<deny policy>' \
  --action-names rds:DeleteDBSnapshot backup:DeleteRecoveryPoint ... rds:CreateDBSnapshot
```
→ 5 action xoá = `explicitDeny`; `rds:CreateDBSnapshot` = `allowed`.

**Proof enforce thật (role tạm `m20-deny-test` = AmazonRDSFullAccess + deny policy, assume rồi probe):**
```
rds:DeleteDBSnapshot -> AccessDenied ... with an explicit deny in an identity-based policy:
  arn:aws:iam::458580846647:policy/ecommerce-develop-dev-dr-backup-protection-deny
rds:CreateDBSnapshot -> DBInstanceNotFound   (không bị chặn)
```
Role tạm đã xoá sau test.

**✅ ĐÃ ENFORCE (28/07):** SSO admin đã attach deny vào CDO Permission Set qua Identity Center, provision sang mọi account. Probe từ role CDO thật:
```bash
aws rds delete-db-snapshot --db-snapshot-identifier m20-deny-probe-nonexistent   # AWSReservedSSO_Phase3-CDO-PermissionSet
```
- **Account 458 (develop):** `DeleteDBSnapshot` → `AccessDenied ... explicit deny`; `backup:DeleteRecoveryPoint` → `AccessDenied ... explicit deny`; `CreateDBSnapshot` → `DBInstanceNotFound` (không bị chặn).
- **Account 804 (sandbox):** `DeleteDBSnapshot` → `AccessDenied ... explicit deny` (permission set provision cross-account, không hỏng provisioning).
- Trước attach cùng lệnh này ra `DBSnapshotNotFound` → chuyển thành `AccessDenied` chính là bằng chứng separation-of-duties đã enforce thật.

---

## 5. Việc còn treo (khai báo minh bạch)
- [x] Attach deny policy vào CDO Permission Set → probe lại `AccessDenied` trên cả 458 & 804 (§4.3).
- [x] Recovery point AWS Backup: job on-demand `COMPLETED`, recovery point `Encrypted=true`.
- [ ] Sandbox (production) coverage RDS/Valkey/vault: code đã wire (`feat/m20-sandbox-backup`), **chưa apply** — apply qua CI để bảo vệ data khách. (Deny guardrail đã live trên sandbox; backup resource chờ apply.)

> **Bài học mang đi:** "đã bật backup" và "khôi phục được trong RTO cam kết" là hai chuyện khác nhau — buổi drill này chứng minh vế thứ hai bằng số đo thật (RTO 20', integrity 100%), và đồng thời phát hiện guardrail deny đang treo dù policy trông đã đủ.
