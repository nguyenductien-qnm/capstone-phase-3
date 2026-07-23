# ADR — Data-transfer endpoints for Mandate 18

- Status: Proposed; implementation validated locally, not rolled out.
- Date: 2026-07-22.
- Scope: `ecommerce-dev-vpc`, private app/MQ egress routes only.

## Context

The VPC has one public NAT gateway. Five private app/MQ subnets share one private route table with `0.0.0.0/0` routed to that NAT. There is no S3/ECR AWS service endpoint and no VPC Flow Log, so per-destination NAT bytes cannot be directly measured.

The workload uses 35 regional private/AWS ECR images plus three public ECR images. Amazon ECR stores image layers in S3, making an S3 route relevant even when the registry/API remains on ECR endpoints.

Baseline and scope limitations are recorded in [`../logs/07-data-transfer-prompt5.txt`](../logs/07-data-transfer-prompt5.txt).

## Decision

Add one regional S3 **Gateway** Endpoint through a reusable Terraform module and associate it only with private workload egress route tables.

- Keep NAT and its default route for third-party registries and general Internet egress.
- Do not associate the endpoint with the public route table.
- In the current NAT-enabled topology, do not associate the isolated data route table.
- Use the default endpoint policy so existing IAM and bucket policies remain authoritative. This does not grant S3 permissions by itself.
- Security groups and private DNS are not configured because they do not apply to Gateway endpoints.

AWS states that S3 Gateway Endpoints have no additional charge and allow S3 access without a NAT device: https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html

## Why ECR interface endpoints are not added

AWS documents that private ECR pulls use `ecr.api`, `ecr.dkr`, and S3 for image layers: https://docs.aws.amazon.com/AmazonECR/latest/userguide/vpc-endpoints.html

For a three-AZ HA deployment, `ecr.api` plus `ecr.dkr` would create six billed endpoint-AZ hours. Using the published first-tier PrivateLink example rate of `$0.01/hour` and `$0.01/GB`, the fixed footprint is approximately `$43.80/month` before data processing: https://aws.amazon.com/privatelink/pricing/

Because NAT remains required, the estimated processing-only break-even is roughly `1251 GB/month` of traffic attributable specifically to those interfaces. Account-wide NAT usage extrapolates to roughly `232.4 GB/month`, and only a subset is ECR API/registry traffic. Interface endpoints would therefore increase the fixed bill at the measured scale.

Do not add Secrets Manager, STS, EC2, SSM or CloudWatch interface endpoints until VPC Flow Logs or an equivalent measurement attributes sufficient traffic to each service.

## Route, SG and DNS scope

- S3 route: AWS-managed S3 prefix list → gateway endpoint, injected only into supplied private egress route tables.
- Public storefront: unchanged; public route table and NLB are outside module inputs.
- NAT route: retained for non-S3 destinations.
- SG: none for Gateway endpoint.
- Private DNS: none for Gateway endpoint.
- Future interface endpoint: require private DNS enabled and TCP/443 ingress restricted to the EKS node security group or approved private workload CIDRs; deploy in each required AZ only after the cost gate passes.

## Risks

- Creating or deleting a gateway endpoint changes the S3 route and can reset existing S3 TCP connections.
- Bucket policies using `aws:SourceIp` may behave differently through a VPC endpoint; review before rollout.
- Without Flow Logs, the exact S3 share of NAT bytes remains unknown.
- A full root plan is not available. Earlier local planning lacked protected
  tfvars; the Prompt 8 rerun with current SSO credentials is blocked earlier by
  `S3 HeadObject 403` on the remote state object. Rollout is not authorized.

## Rollout gate

1. Run a full protected-environment plan.
2. Require exactly one S3 gateway endpoint create plus expected output/route association; zero unexpected update/delete/replace.
3. Confirm the selected route table is the private app/MQ egress route table.
4. Apply during an observed window and verify endpoint `available`, prefix-list route, image pull, AWS API access and SLO.

## Rollback

Disable/remove the module only after a plan shows deletion of the S3 endpoint and no other resource action. The existing NAT default route remains present, so new S3 connections return to NAT. Repeat image pull/API/SLO verification after rollback.
