# 📖 Hướng Dẫn Chi Tiết Các Bước Kiểm Tra Mandate 20 — Môi Trường Sandbox (Production)

**Môi trường:** Sandbox  
**AWS Account ID:** `384511757667`  
**AWS CLI Profile:** `Mặc định / IAM User`  
**Region:** `us-east-1`  
**EKS Cluster:** `ecommerce-dev-eks` (VPC `vpc-0085623a1538f2129` / `10.0.0.0/16`)

---

## 📌 PHẦN 1: Kiểm Tra Cấu Hình ElastiCache Valkey Backup (CDO-253)

### Lệnh thực thi:
```bash
aws elasticache describe-replication-groups \
  --replication-group-id ecommerce-dev-valkey \
  --region us-east-1 \
  --query "ReplicationGroups[0].{SnapshotRetentionLimit: SnapshotRetentionLimit, SnapshotWindow: SnapshotWindow}"
```

### Kết quả kỳ vọng (PASSED):
- `SnapshotRetentionLimit`: `7` (giữ snapshot trong 7 ngày)
- `SnapshotWindow`: `"03:00-04:00"` (UTC)

---

## 📌 PHẦN 2: Kiểm Tra Cấu Cấu Hình RDS PostgreSQL (CDO-252)

### Lệnh thực thi:
```bash
aws rds describe-db-instances \
  --db-instance-identifier ecommerce-dev-postgres \
  --region us-east-1 \
  --query "DBInstances[0].{DeletionProtection: DeletionProtection, CopyTagsToSnapshot: CopyTagsToSnapshot, BackupRetentionPeriod: BackupRetentionPeriod, LatestRestorableTime: LatestRestorableTime}"
```

### Kết quả kỳ vọng (PASSED):
- `DeletionProtection`: `true` (chống xóa nhầm DB primary)
- `CopyTagsToSnapshot`: `true` (tự động sao chép tag sang snapshot)
- `BackupRetentionPeriod`: `7` (retention 7 ngày cho PITR)

---

## 📌 PHẦN 3: Kiểm Tra AWS Backup Vault, Plan & KMS Key (CDO-254 / CDO-259)

### 3.1 Kiểm tra Backup Vault & Vault Lock:
```bash
aws backup list-backup-vaults \
  --region us-east-1
```

### Kết quả kỳ vọng (PASSED):
- Tên Vault: `ecommerce-dev-backup-vault`
- `Locked`: `true` (Governance Mode)
- `MinRetentionDays`: `7`, `MaxRetentionDays`: `30`

### 3.2 Kiểm tra Backup Plan:
```bash
aws backup list-backup-plans \
  --region us-east-1
```

### Kết quả kỳ vọng (PASSED):
- Tên Plan: `ecommerce-dev-backup-plan`

---

## 📌 PHẦN 4: Kiểm Tra IAM Deny Policy (CDO-260)

### Lệnh thực thi:
```bash
aws iam list-policies \
  --scope Local \
  --query "Policies[?contains(PolicyName, 'backup-protection-deny')].{Name: PolicyName, Arn: Arn}"
```

### Kết quả kỳ vọng (PASSED):
- Tên Policy: `ecommerce-dev-dr-backup-protection-deny`
- ARN: `arn:aws:iam::384511757667:policy/ecommerce-dev-dr-backup-protection-deny`

---

## 📌 PHẦN 5: Kiểm Tra Kết Nối Cô Lập (CDO-269)

### Lệnh thực thi:
Kiểm tra cấu hình Security Group của RDS Sandbox để xác nhận port `5432` chỉ được phép nhận kết nối từ các cụm chỉ định:
```bash
aws ec2 describe-security-groups \
  --group-ids sg-03a3d1abd357b6ffa \
  --region us-east-1 \
  --query "SecurityGroups[0].{GroupId: GroupId, GroupName: GroupName, IngressRules: IpPermissions}"
```

---

## 📌 PHẦN 6: Thực Hiện PITR Drill Khôi Phục Dữ Liệu (Quy Trình Chuẩn EKS Inside-VPC)

> **⚠️ Nguyên tắc quan trọng:**  
> - RDS và EKS Sandbox nằm **CÙNG VPC** (`10.0.0.0/16`). Không mở IP công khai (`PubliclyAccessible=false`) hay gán rule `0.0.0.0/0`.  
> - Mật khẩu DB được load an toàn từ **Kubernetes Secret `db-secret`** trong namespace `techx-tf1` (không hardcode plaintext).

---

### Bước 6.1: Chuyển kubeconfig sang Cluster Sandbox (Production)
```bash
aws eks update-kubeconfig \
  --name ecommerce-dev-eks \
  --region us-east-1
```

---

### Bước 6.2: Tạo dữ liệu mẫu ($T_0$ Baseline)
Tạo file manifest `scripts/dr/pod_seed.yaml` và deploy vào cluster:

```bash
kubectl apply -f scripts/dr/pod_seed.yaml
```

*File mẫu `scripts/dr/pod_seed.yaml` (dùng namespace `techx-tf1`):*
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: psql-drill-seed
  namespace: techx-tf1
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 70
    runAsGroup: 70
    fsGroup: 70
  containers:
    - name: runner
      image: postgres:15-alpine
      resources:
        requests: { cpu: "100m", memory: "128Mi" }
        limits: { cpu: "200m", memory: "256Mi" }
      securityContext:
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
      env:
        - name: PGURL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: catalog-db-conn
      command:
        - sh
        - -c
        - |
          psql "$PGURL" <<'EOF'
          CREATE SCHEMA IF NOT EXISTS drill_m20;
          CREATE TABLE IF NOT EXISTS drill_m20.orders_audit (
              id SERIAL PRIMARY KEY, order_id VARCHAR(64) NOT NULL,
              customer_id VARCHAR(64) NOT NULL, amount NUMERIC(10, 2) NOT NULL,
              status VARCHAR(32) NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
          );
          INSERT INTO drill_m20.orders_audit (order_id, customer_id, amount, status, created_at)
          VALUES 
            ('ORD-DRILL-001', 'CUST-101', 199.99, 'COMPLETED', NOW() - INTERVAL '10 minutes'),
            ('ORD-DRILL-002', 'CUST-102', 49.50, 'COMPLETED', NOW() - INTERVAL '8 minutes'),
            ('ORD-DRILL-003', 'CUST-103', 1250.00, 'PROCESSING', NOW() - INTERVAL '5 minutes'),
            ('ORD-DRILL-004', 'CUST-104', 89.00, 'COMPLETED', NOW() - INTERVAL '3 minutes'),
            ('ORD-DRILL-005', 'CUST-105', 310.25, 'PENDING', NOW() - INTERVAL '1 minute');

          SELECT count(*) || '|' || md5(string_agg(id::text || order_id || amount::text || status, ',' ORDER BY id))
          FROM drill_m20.orders_audit;
          EOF
```

**Xem kết quả $T_0$ và Dọn dẹp Pod Seed:**
```bash
# Xem log lấy T0 Timestamp và MD5 Checksum
kubectl logs -n techx-tf1 psql-drill-seed

# Dọn dẹp pod sau khi seed xong
kubectl delete -f scripts/dr/pod_seed.yaml
```
> 📝 **GHI LẠI OUTPUT:**
> - `T0 UTC Timestamp`: e.g., `2026-07-28T10:00:00Z`
> - `MD5 Checksum`: `bc178e08178eafa1efd07da38e0ea875`

---

### Bước 6.3: Giả lập sự cố mất dữ liệu ($T_1$)
Deploy `pod_loss.yaml` để xóa schema `drill_m20`:

```bash
kubectl apply -f scripts/dr/pod_loss.yaml
```

*File mẫu `scripts/dr/pod_loss.yaml` (dùng namespace `techx-tf1`):*
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: psql-drill-loss
  namespace: techx-tf1
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 70
    runAsGroup: 70
    fsGroup: 70
  containers:
    - name: runner
      image: postgres:15-alpine
      resources:
        requests: { cpu: "100m", memory: "128Mi" }
        limits: { cpu: "200m", memory: "256Mi" }
      securityContext:
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
      env:
        - name: PGURL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: catalog-db-conn
      command:
        - sh
        - -c
        - |
          psql "$PGURL" -c "DROP SCHEMA IF EXISTS drill_m20 CASCADE;"
          echo "DATA_LOSS_EVENT_COMPLETED"
```

```bash
# Verify log và dọn dẹp pod
kubectl logs -n techx-tf1 psql-drill-loss
kubectl delete -f scripts/dr/pod_loss.yaml
```

---

### Bước 6.4: Chờ Timing & Chạy Lệnh Restore PITR
> ⚠️ **Bẫy Timing PITR:** Timestamp $T_0$ dùng để restore phải nhỏ hơn hoặc bằng `LatestRestorableTime` của RDS (log WAL trễ ~3-5 phút).

**Kiểm tra `LatestRestorableTime` đạt mốc $T_0$:**
```bash
aws rds describe-db-instances \
  --db-instance-identifier ecommerce-dev-postgres \
  --query "DBInstances[0].LatestRestorableTime" \
  --output text \
  --region us-east-1
```

Khi `LatestRestorableTime >= T0`, thực hiện khôi phục DB về mốc $T_0$ (thay giá trị `2026-07-28T10:00:00Z` bằng timestamp thực tế của bạn):

```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier ecommerce-dev-postgres \
  --target-db-instance-identifier ecommerce-dev-postgres-drill-temp \
  --db-subnet-group-name ecommerce-dev-rds-subnet-group \
  --vpc-security-group-ids "sg-03a3d1abd357b6ffa" \
  --restore-time "2026-07-28T10:00:00Z" \
  --no-multi-az \
  --no-publicly-accessible \
  --storage-type gp3 \
  --region us-east-1
```

---

### Bước 6.5: Chờ DB Tạm Sẵn Sàng & Kiểm Tra Toàn Vẹn Dữ Liệu

```bash
# Chờ DB khôi phục hoàn tất (chuyển sang trạng thái Available - khoảng 5-10 phút)
aws rds wait db-instance-available \
  --db-instance-identifier ecommerce-dev-postgres-drill-temp \
  --region us-east-1
```

> - Vì tên `--target-db-instance-identifier` trong kịch bản quy chuẩn là `ecommerce-dev-postgres-drill-temp`, AWS RDS sẽ sinh ra Endpoint theo định dạng:  
>   `ecommerce-dev-postgres-drill-temp.cw9k28a0os7t.us-east-1.rds.amazonaws.com`
> - File verify bên dưới sử dụng regex `sed` để tự động thay thế proxy host bằng endpoint khôi phục tạm này.

Deploy Pod Verify `pod_verify.yaml` để đếm Checksum trên DB khôi phục:
```bash
kubectl apply -f scripts/dr/pod_verify.yaml
```

*File mẫu `scripts/dr/pod_verify.yaml`:*
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: psql-drill-verify
  namespace: techx-tf1
spec:
  restartPolicy: Never
  securityContext:
    runAsNonRoot: true
    runAsUser: 70
    runAsGroup: 70
    fsGroup: 70
  containers:
    - name: runner
      image: postgres:15-alpine
      resources:
        requests: { cpu: "100m", memory: "128Mi" }
        limits: { cpu: "200m", memory: "256Mi" }
      securityContext:
        allowPrivilegeEscalation: false
        capabilities: { drop: ["ALL"] }
      env:
        - name: PGURL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: catalog-db-conn
      command:
        - sh
        - -c
        - |
          RESTORED_CONN=$(echo "$PGURL" | sed 's/ecommerce-dev-rds-proxy.proxy-cw9k28a0os7t.us-east-1.rds.amazonaws.com/ecommerce-dev-postgres-drill-temp.cw9k28a0os7t.us-east-1.rds.amazonaws.com/')
          psql "$RESTORED_CONN" -c "SELECT count(*), md5(string_agg(id::text || order_id || amount::text || status, ',' ORDER BY id)) FROM drill_m20.orders_audit;"
```

**Xem kết quả xác minh:**
```bash
kubectl logs -n techx-tf1 psql-drill-verify
```
> ✅ **KẾT QUẢ KỲ VỌNG:**  
> `count`: `5`  
> `md5`: `bc178e08178eafa1efd07da38e0ea875` (Khớp 100% với $T_0$)

---

### Bước 6.6: Dọn Dẹp Sạch Sẽ Sau Diễn Tập (BẮT BUỘC)

```bash
# 1. Xóa Pod Verify
kubectl delete -f scripts/dr/pod_verify.yaml

# 2. Xóa DB Instance tạm (Bằng script dọn dẹp hệ thống)
# LƯU Ý: Không cần export AWS_PROFILE vì đã đăng nhập bằng IAM User mặc định
./scripts/dr/destroy-drill-env.sh ecommerce-dev-postgres-drill-temp us-east-1
```
