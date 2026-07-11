# Architecture Review

**Team Infra:** Đạt, Hoàng, Tiến, Kiên

## Diagrams

- [Infrastructure diagram](assets/cdo05-infra-diagram.png)
- [Architecture diagram](assets/cdo05-architecture-diagram.png)

## Architecture Trade-off Analysis

- [Regional NAT Gateway for public outbound egress](tradeoffs/nat-gateway-regional-vs-zonal.md)
- [NLB in front of Envoy frontend-proxy](tradeoffs/nlb-envoy-ingress.md)
- [Amazon RDS PostgreSQL vs PostgreSQL on EKS](tradeoffs/postgres-rds-vs-eks-statefulset.md)
- [RDS Proxy for runtime database traffic](tradeoffs/rds-proxy.md)
- [Amazon ElastiCache for Valkey](tradeoffs/elasticache-valkey.md)
- [Standard EKS with Karpenter for worker nodes](tradeoffs/eks-karpenter-vs-auto-mode.md)

## Note

Các tài liệu này là architecture trade-off analysis để mentor review. Chưa gọi là ADR vì ADR cần xác nhận theo decision log của nhóm/TF.
