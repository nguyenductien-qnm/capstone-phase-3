# ADR: Disaster Recovery Backup & Restore Strategy (Mandate 20)

- **Status:** Accepted
- **Deciders:** Thi (Reliability Lead), Khang (Platform Infrastructure)
- **Date:** 2026-07-25
- **Context Jira:** CDO-139 / Mandate 20 (CDO-245 - CDO-250)

---

## 1. Context & Problem Statement

The platform requires a comprehensive Disaster Recovery (DR) and backup protection strategy across all transactional and stateful data stores serving the money flow (browse, cart, checkout, order processing). Prior to Mandate 20, backup coverage suffered from critical gaps:
1. ElastiCache Valkey (`cart` service) had no daily backup snapshots configured (`snapshot_retention_limit = 0`).
2. Primary RDS PostgreSQL lacked deletion protection (`deletion_protection = false`) and tag copying (`copy_tags_to_snapshot = false`).
3. No explicit IAM Deny policies existed to prevent operator accounts from accidentally deleting DB snapshots or recovery points.

---

## 2. Store Inventory & Strategy

| Stateful Store | Associated Services | Data Classification | DR Strategy / Mechanism | RPO SLA Target | RTO SLA Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RDS PostgreSQL** | `accounting`, `product-catalog`, `product-reviews` | Transactional Orders & Catalog (Critical) | Automated Backups (7-day retention) + Continuous WAL Point-in-Time Restore (PITR) | $\le 5$ minutes | $\le 45$ minutes |
| **ElastiCache Valkey** | `cart` | Session & Shopping Cart (Transient) | Automated Daily Snapshots (`snapshot_retention_limit = 7`, window `03:00-04:00` UTC) | 24 hours | $\le 30$ minutes |
| **EBS Persistent Volumes** | `prometheus` (20Gi), `grafana` (10Gi) | Observability Metrics & Dashboards (Non-critical) | AWS Backup Vault + Daily Backup Plan | 24 hours | $\le 2$ hours |
| **Cluster State** | Kubernetes manifests & Helm charts | Declarative Configuration | Git-driven (ArgoCD GitOps) + S3 Versioning on Terraform state bucket | 0 (Git-driven) | $\le 30$ minutes |
| **MSK Kafka** | `checkout` queue | In-flight event streaming | Stream buffer transient data; source of truth persisted in RDS. Out of direct DR snapshot scope. | N/A | N/A |

---

## 3. Decision Drivers & Architecture Choices

### 3.1 Point-in-Time Restore (PITR) to Isolated Environment
- **Decision:** All database drills must perform PITR to a newly provisioned, isolated RDS instance named `<instance-name>-drill-temp`.
- **Rationale:** Restoring directly over live production or develop instances risks catastrophic data loss. Restoring to isolated target instances ensures live workloads are unaffected and allows verification prior to traffic cutover.

### 3.2 Backup Anti-Deletion Guardrails (CDO-247)
- **Decision:** Provision a dedicated KMS Customer Managed Key (CMK) for DR backups alongside an explicit IAM Deny Policy (`dr-backup-protection-deny`).
- **Policy Scope:** Denies `rds:DeleteDBSnapshot`, `rds:DeleteDBClusterSnapshot`, `backup:DeleteRecoveryPoint`, `backup:DeleteBackupVault`, `backup:DeleteBackupVaultAccessPolicy`, `backup:DeleteBackupPlan`, `ec2:DeleteSnapshot`, `elasticache:DeleteSnapshot`.
- **⚠️ Open debt — enforcement:** the operator permission sets are IAM Identity Center (SSO) permission sets, not standalone IAM roles. Terraform (`audit_operator_role_names`) is intentionally left empty because attaching customer-managed policies directly to `AWSReservedSSO_*` roles is reverted on the next SSO provisioning. **Required production step (SSO admin):** attach the customer-managed policy `ecommerce-develop-dev-dr-backup-protection-deny` to the CDO (and AIO) permission set via Identity Center and provision. Cross-account caveat: a policy of the same name must exist in every account the permission set is provisioned to (e.g. sandbox) or provisioning fails — so wire the deny policy in `environments/sandbox` before attaching org-wide. Until this is done, separation-of-duties is defined but not enforced (see 4.3).

### 3.3 ElastiCache Valkey Cadence Justification
- **Decision:** Configure daily snapshot window (`03:00-04:00` UTC) with 7-day retention limit.
- **Rationale:** Redis/Valkey does not support continuous WAL log shipping like relational databases. Daily snapshots provide a reliable fallback while keeping operational overhead low for transient cart data.

---

## 4. Verification & Drill Execution

Drills are conducted exclusively in `develop` (source instance `ecommerce-develop-dev-postgres`, cluster `ecommerce-develop-dev-eks` ns `techx-develop`) using schema `drill_m20`. All SQL runs from Pods inside the VPC (`10.60.0.0/16`); no public access or `0.0.0.0/0` rule is used.

Procedure: **Seed ($T_0$)** → **Simulate loss ($T_1$, start RTO clock)** → **PITR restore to isolated `-drill-temp`** → **Verify row count + MD5** (stop RTO clock when data verified, not when DB merely `Available`) → **Cleanup**.

### 4.1 Measured Results — Drill executed 2026-07-27 (develop)

| Metric | Value |
| :--- | :--- |
| $T_0$ seed | `2026-07-27T17:21:18Z` — 5 rows, MD5 `bc178e08178eafa1efd07da38e0ea875` |
| PITR restore point | `2026-07-27T17:22:00Z` |
| $T_1$ loss / RTO start | `2026-07-27T17:27:43Z` (`DROP SCHEMA drill_m20 CASCADE`) |
| Data verified / RTO stop | `2026-07-27T17:47:41Z` |
| **RTO (measured)** | **≈ 20 minutes** — within `≤ 45 min` SLA ✅ |
| **RPO (measured)** | Restore granularity to the second; no data written between restore point and loss → effective loss 0. Within `≤ 5 min` RDS PITR SLA ✅ |
| Data integrity | Restored target: count=5, MD5 `bc178e08178eafa1efd07da38e0ea875` — **100% match** ✅ |
| Point-in-time proof | Schema dropped at $T_1$ reappears after restore to $T_0$ → genuine PITR, not latest-snapshot restore ✅ |
| Cleanup | `-drill-temp` instance deleted, temporary EKS→drill-SG ingress revoked, drill pods removed → 0 leftover ✅ |
| Production impact | None — storefront served normally; blast radius confined to schema `drill_m20` ✅ |

### 4.2 Vault Lock Enforcement (proven, not just "enabled")

On-demand backup **without** a lifecycle → job **FAILED** `"lifecycle is outside the valid range for backup vault"` (infinite retention exceeds `MaxRetentionDays=30`). Same backup with `DeleteAfterDays=14` (inside `[7,30]`) → accepted and ran. This demonstrates the Governance-mode Vault Lock actively enforces retention bounds.

### 4.3 IAM Deny Policy — mechanism proven end-to-end; **production attachment pending**

- **Simulation:** `aws iam simulate-custom-policy` (broad `Allow *` + the deny policy) → all 8 delete actions `explicitDeny`; `rds:CreateDBSnapshot` `allowed`.
- **Real enforcement proof (2026-07-27):** a throwaway role `m20-deny-test` with `AmazonRDSFullAccess` + the deny policy was assumed and probed:
  - `rds:DeleteDBSnapshot` → `AccessDenied ... with an explicit deny in an identity-based policy: .../ecommerce-develop-dev-dr-backup-protection-deny` — deny overrides full access ✅
  - `rds:CreateDBSnapshot` → `DBInstanceNotFound` (not denied) — creation still allowed ✅
  - Test role deleted after the probe.
- **Remaining production step:** the deny policy is not yet attached to the live CDO operator permission set (live probe from the SSO operator role returns `DBSnapshotNotFound`, not `AccessDenied`). Attach via IAM Identity Center per Section 3.2. The mechanism is proven; only the org-wide attachment (an SSO-admin action with the cross-account prerequisite) is outstanding.

---

## 5. Status & Compliance

- [x] IaC backup coverage wired for RDS & Valkey on **develop** — verified live (RDS `DeletionProtection=true`/`CopyTagsToSnapshot=true`/retention=7/PITR active; Valkey `SnapshotRetentionLimit=7`, window `03:00-04:00`).
- [x] Dedicated KMS CMK & AWS Backup Vault (Governance Vault Lock, `[7,30]` days) created — lock enforcement proven (4.2).
- [x] IAM Deny Guardrail policy created; content verified via policy simulation (4.3).
- [x] DR Seed, Loss Simulation, Verify (Pod manifests) & Cleanup scripts created; PITR Runbook at `docs/runbook/dr-restore.md`.
- [x] **Live PITR restore drill executed on develop — RTO ≈ 20 min, data integrity 100%** (4.1).
- [ ] **IAM Deny policy attached to operator permission set (SSO) — PENDING** (3.2 debt). Separation-of-duties not yet enforced.
- [ ] Sandbox (production) backup coverage wired + verified — PENDING (separate PR; do **not** run destructive drill on sandbox).
- [ ] AWS Backup recovery point produced (on-demand job with 14-day lifecycle running at time of writing).

---

## 6. Sign-off

| Role | Name | Date |
| :--- | :--- | :--- |
| Reliability Lead | Thi | 2026-07-27 |
| Platform Infrastructure | Khang | 2026-07-27 |
