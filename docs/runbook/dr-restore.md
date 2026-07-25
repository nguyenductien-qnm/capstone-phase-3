# Runbook: Disaster Recovery Point-in-Time Restore (PITR) Drill

> **Mandate 20 (CDO-248 / CDO-264)**  
> **Target Environment:** `develop` (`ecommerce-dev-postgres-primary`)  
> **Isolated Restore Target:** `ecommerce-dev-postgres-primary-drill`  
> **Target Store:** RDS PostgreSQL (`accounting` database)

---

## 1. Overview & Objectives

This runbook outlines the step-by-step procedure for conducting a Point-in-Time Restore (PITR) drill for PostgreSQL on AWS RDS without disrupting live customer operations or overwriting production/develop databases.

### Core Guardrails
- **Isolation:** Restore target MUST be created as a separate DB instance with `-drill` suffix.
- **Safety:** NEVER overwrite live RDS primary instances (`ecommerce-dev-postgres-primary`).
- **Measurement:** Record RTO (Recovery Time Objective) from data loss detection to query verification, and RPO (Recovery Point Objective) against the target timestamp $T_0$.

---

## 2. Prerequisites & Preparation

1. **AWS CLI & PostgreSQL Client (`psql`):** Verify access to target AWS account and DB endpoints.
2. **Retrieve Primary RDS Identifier & Restorable Time Window:**
   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier ecommerce-dev-postgres-primary \
     --query 'DBInstances[0].[DBInstanceIdentifier,LatestRestorableTime,DeletionProtection]' \
     --region us-east-1
   ```
   *Verify `DeletionProtection: true` on primary.*

---

## 3. Execution Steps

### Step 1: Seed Test Data ($T_0$ Baseline)

Run the seeding script to populate the `drill_m20.orders_audit` table with synthetic records and calculate the initial state hash:

```bash
./scripts/dr/seed-drill-data.sh <PGHOST> 5432 postgres accounting <PGPASSWORD>
```

**Output to record:**
- **$T_0$ UTC Timestamp:** e.g., `2026-07-25T16:00:00Z`
- **Expected Row Count:** e.g., `5`
- **T0 MD5 Checksum:** e.g., `a1b2c3d4e5f6...`

---

### Step 2: Simulate Data Loss Event ($T_1$)

Simulate a data corruption / accidental drop event at timestamp $T_1$ ($T_1 > T_0$):

```bash
./scripts/dr/simulate-data-loss.sh <PGHOST> 5432 postgres accounting <PGPASSWORD> --force
```

**Output to record:**
- **$T_1$ UTC Timestamp:** e.g., `2026-07-25T16:05:00Z` (Data Loss Event)
- **Start RTO Timer:** Record exact start time $T_{\text{start\_rto}}$.

---

### Step 3: Trigger Point-in-Time Restore (PITR) to Isolated Target

Restore the database to timestamp $T_0$ (prior to $T_1$) into a newly provisioned, isolated instance:

```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier ecommerce-dev-postgres-primary \
  --target-db-instance-identifier ecommerce-dev-postgres-primary-drill \
  --restore-time "2026-07-25T16:00:00Z" \
  --no-multi-az \
  --publicly-accessible \
  --region us-east-1
```

Wait until the restored DB instance becomes `available`:

```bash
aws rds wait db-instance-available \
  --db-instance-identifier ecommerce-dev-postgres-primary-drill \
  --region us-east-1
```

---

### Step 4: Verification & Stop RTO Clock (CDO-265)

Retrieve endpoint of the drill instance:
```bash
DRILL_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier ecommerce-dev-postgres-primary-drill \
  --query 'DBInstances[0].Endpoint.Address' --output text --region us-east-1)
```

Connect to `ecommerce-dev-postgres-primary-drill` and execute two-way integrity verification:

```bash
# 1. Verify schema and table presence
psql -h "$DRILL_ENDPOINT" -U postgres -d accounting -c "
SELECT count(*), md5(string_agg(id::text || order_id || amount::text || status, ',' ORDER BY id)) 
FROM drill_m20.orders_audit;
"
```

**Validation Criteria:**
1. **Positive Check:** Restored Row Count and MD5 Checksum match $T_0$ baseline EXACTLY.
2. **Negative Check:** No mutations or drop events after $T_0$ exist in the restored instance.

**Record RTO Timer Stop:** $T_{\text{end\_rto}}$  
$$\text{RTO} = T_{\text{end\_rto}} - T_{\text{start\_rto}}$$

---

### Step 5: Post-Drill Cleanup (CDO-271)

Clean up the temporary restore instance using the safety-guarded script:

```bash
./scripts/dr/destroy-drill-env.sh ecommerce-dev-postgres-primary-drill us-east-1
```

---

## 4. Evidence Checklist

- [ ] Command log of `seed-drill-data.sh` showing $T_0$ timestamp & MD5 hash.
- [ ] Command log of `simulate-data-loss.sh` showing $T_1$ drop event.
- [ ] AWS CLI output of `restore-db-instance-to-point-in-time`.
- [ ] Verification query output matching $T_0$ row count and hash on drill instance.
- [ ] Cleanup log showing deletion of `ecommerce-dev-postgres-primary-drill`.
