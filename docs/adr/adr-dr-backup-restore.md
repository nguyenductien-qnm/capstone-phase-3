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
- **Policy Scope:** Denies `rds:DeleteDBSnapshot`, `rds:DeleteDBClusterSnapshot`, `backup:DeleteRecoveryPoint`, `backup:DeleteBackupVault`, `backup:DeleteBackupPlan`, `ec2:DeleteSnapshot`, `elasticache:DeleteSnapshot` across standard operator roles.

### 3.3 ElastiCache Valkey Cadence Justification
- **Decision:** Configure daily snapshot window (`03:00-04:00` UTC) with 7-day retention limit.
- **Rationale:** Redis/Valkey does not support continuous WAL log shipping like relational databases. Daily snapshots provide a reliable fallback while keeping operational overhead low for transient cart data.

---

## 4. Verification & Drill Execution

Drills are conducted exclusively in `develop` environment (`ecommerce-dev-postgres-primary`) using schema `drill_m20`.

1. **Seeding ($T_0$):** Synthetic records are inserted and MD5 state checksum computed.
2. **Simulation ($T_1$):** `DROP SCHEMA drill_m20 CASCADE` simulates corruption/loss.
3. **Restore:** `aws rds restore-db-instance-to-point-in-time` restores DB to $T_0$ into `ecommerce-dev-postgres-primary-drill-temp`.
4. **Validation:** Row count and MD5 checksum on restored target must match $T_0$ baseline 100%.

---

## 5. Status & Compliance

- [x] IaC backup coverage wired for RDS & Valkey on develop environment.
- [x] Dedicated KMS CMK & IAM Deny Guardrail policy created in Terraform.
- [x] DR Seed, Loss Simulation, and Cleanup scripts created.
- [x] PITR Runbook published under `docs/runbook/dr-restore.md`.
