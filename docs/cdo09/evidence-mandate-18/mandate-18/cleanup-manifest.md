# Mandate 18 — Target Group cleanup manifest

## Authorized sandbox cleanup executed 2026-07-23

The leader/owner authorization supplied by the user covered exactly
`123123321` and `89345789437843`. A fresh dependency audit and recreate backup
were captured before any mutation. Both resources satisfied every deletion
gate and were deleted sequentially; runtime health was verified after each.

| Target Group | Final classification | Action/result |
|---|---|---|
| `123123321` | `DELETE_CANDIDATE` | Deleted; absent in final inventory |
| `89345789437843` | `DELETE_CANDIDATE` | Deleted; absent in final inventory |
| `testt` | `UNKNOWN/HOLD` | Preserved; different VPC/project scope |
| `k8s-techxtf1-frontend-da03cf6043` | `KEEP` | Preserved; active NLB, controller binding and 2 healthy targets |

Current raw records:

- [`../logs/16-target-group-predelete-audit.txt`](../logs/16-target-group-predelete-audit.txt)
- [`../logs/17-target-group-cleanup-result.txt`](../logs/17-target-group-cleanup-result.txt)

The section below is the historical pre-authorization audit from 2026-07-22;
its `UNKNOWN/HOLD` result was correct at that capture time and is retained as
an audit trail.

Captured `2026-07-22T07:51:57Z`. This manifest is **audit-only**. It authorizes no deletion.

## Decision summary

| Target Group | VPC scope | Owner signal | Classification | Deletion authorized |
|---|---|---|---|---|
| `123123321` | `ecommerce-dev-vpc` | No TG tags; created 15/07 by another SSO user | `UNKNOWN/HOLD` | No |
| `89345789437843` | `ecommerce-dev-vpc` | No TG tags; created 15/07 by another SSO user | `UNKNOWN/HOLD` | No |
| `testt` | Default VPC, outside project | No tags; created 15/07 by another SSO user | `UNKNOWN/HOLD` | No |

`DELETE_CANDIDATE`: **none**.

Raw dependency evidence: [`../logs/03-orphan-dependency-audit.txt`](../logs/03-orphan-dependency-audit.txt).

## 123123321

- ARN: `arn:aws:elasticloadbalancing:us-east-1:<ACCOUNT_ID_REDACTED>:targetgroup/123123321/37ba213574e8eb88`.
- Region/VPC: `us-east-1` / `vpc-06d4c34ec03f55c6d` (`ecommerce-dev-vpc`).
- Runtime: no LB/listener/rule association and no registered target.
- IaC/dependency: no exact repository, Terraform state, CloudFormation or Kubernetes reference.
- CloudTrail: created `2026-07-15T14:44:39+07:00` by `<OTHER_SSO_USER_REDACTED>`.
- Classification: `UNKNOWN/HOLD` because owner is unconfirmed and creation is recent.
- Blast radius if wrong: a future deployment owned by another member could lose its expected ARN/config; recreation produces a new ARN.

Backup/recreate specification:

```text
name=123123321 protocol=HTTP port=80 target-type=instance ip-address-type=ipv4 protocol-version=HTTP1
health-check: protocol=HTTP port=traffic-port path=/ interval=30 timeout=5 healthy=5 unhealthy=2 matcher=200
attributes: deregistration_delay=300, stickiness=false/lb_cookie, slow_start=0,
round_robin, anomaly_mitigation=off, cross_zone=use_load_balancer_configuration,
unhealthy-routing count=1/percentage=off, dns-failover count=1/percentage=off
```

Inert delete command — **DO NOT RUN**:

```text
# NOT AUTHORIZED
# aws elbv2 delete-target-group --target-group-arn "arn:aws:elasticloadbalancing:us-east-1:<ACCOUNT_ID_REDACTED>:targetgroup/123123321/37ba213574e8eb88"
```

## 89345789437843

- ARN: `arn:aws:elasticloadbalancing:us-east-1:<ACCOUNT_ID_REDACTED>:targetgroup/89345789437843/4d3b6e02d57da2ab`.
- Region/VPC: `us-east-1` / `vpc-06d4c34ec03f55c6d` (`ecommerce-dev-vpc`).
- Runtime: no LB/listener/rule association and no registered target.
- IaC/dependency: no exact repository, Terraform state, CloudFormation or Kubernetes reference.
- CloudTrail: created `2026-07-15T14:47:08+07:00` by `<OTHER_SSO_USER_REDACTED>`.
- Classification: `UNKNOWN/HOLD` because owner is unconfirmed and creation is recent.
- Blast radius if wrong: a future NLB/TCP deployment may depend on this configuration or expected ARN.

Backup/recreate specification:

```text
name=89345789437843 protocol=TCP port=80 target-type=instance ip-address-type=ipv4
health-check: protocol=HTTP port=traffic-port path=/ interval=30 timeout=6 healthy=5 unhealthy=2 matcher=200-399
attributes: deregistration_delay=300, proxy_protocol_v2=false, stickiness=false/source_ip,
preserve_client_ip=true, cross_zone=use_load_balancer_configuration,
unhealthy connection termination=true, unhealthy draining interval=0,
deregistration connection termination=false,
unhealthy-routing count=1/percentage=off, dns-failover count=1/percentage=off
```

Inert delete command — **DO NOT RUN**:

```text
# NOT AUTHORIZED
# aws elbv2 delete-target-group --target-group-arn "arn:aws:elasticloadbalancing:us-east-1:<ACCOUNT_ID_REDACTED>:targetgroup/89345789437843/4d3b6e02d57da2ab"
```

## testt

- ARN: `arn:aws:elasticloadbalancing:us-east-1:<ACCOUNT_ID_REDACTED>:targetgroup/testt/64259b99fc3ea8be`.
- Region/VPC: `us-east-1` / `vpc-0e75d763a56d0aa38` (default VPC, outside project scope).
- Runtime: no LB/listener/rule association and no registered target.
- IaC/dependency: no exact repository, Terraform state, CloudFormation or Kubernetes reference.
- CloudTrail: created `2026-07-15T10:09:59+07:00` by `<OTHER_SSO_USER_REDACTED>`.
- Classification: `UNKNOWN/HOLD`; explicit owner and cross-project approval are mandatory.
- Blast radius if wrong: deletion could remove another member/project's staged resource.

Backup/recreate specification:

```text
name=testt protocol=HTTP port=80 target-type=instance ip-address-type=ipv4 protocol-version=HTTP1
health-check: protocol=HTTP port=traffic-port path=/ interval=30 timeout=5 healthy=5 unhealthy=2 matcher=200
attributes: same HTTP attribute backup recorded for 123123321 in the raw audit
```

Inert delete command — **DO NOT RUN**:

```text
# NOT AUTHORIZED
# aws elbv2 delete-target-group --target-group-arn "arn:aws:elasticloadbalancing:us-east-1:<ACCOUNT_ID_REDACTED>:targetgroup/testt/64259b99fc3ea8be"
```

## Mandatory recheck before any future cleanup

1. Obtain explicit owner confirmation for each exact full ARN.
2. Reverify SSO account, `us-east-1`, ARN and VPC immediately before deletion.
3. Repeat listener/rule, target-health, tags, CloudTrail, Terraform state, CloudFormation and Kubernetes checks.
4. Stop if any state differs from this manifest or any new dependency appears.
5. Save before evidence and full recreate configuration.
6. Delete only an individually approved full ARN; never delete by copied list or name-only matching.
7. Repeat the same inventory query and capture after evidence.
8. Verify storefront/SLO and controller health; restore by recreating configuration and updating any dependency if required.

## Approval gate

No approval can be produced from this manifest because all resources are `UNKNOWN/HOLD`. A future approval must name one exact, newly reverified full ARN and must come after owner confirmation.
