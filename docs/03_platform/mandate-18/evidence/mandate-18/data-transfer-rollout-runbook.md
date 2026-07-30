# Mandate 18 — S3 Gateway Endpoint rollout runbook

Status: **not executed**. Do not run the apply section until the protected full plan passes review.

## Before

1. Verify SSO account, `us-east-1`, VPC and cluster against Prompt 1.
2. Save `logs/07-data-transfer-prompt5.txt` and screenshot NAT/Cost Explorer baseline.
3. Confirm NAT remains `available` and the private route table has its default NAT route.
4. Confirm storefront SLO, all pods and ExternalSecret status are healthy.
5. Run protected `terraform plan`; reject any unexpected update/delete/replace.

## Expected plan

- Create: `module.vpc_endpoints.aws_vpc_endpoint.s3[0]` only.
- Output addition: `s3_gateway_endpoint_id`.
- Route association: current private app/MQ egress route table only.
- No NAT, IGW, public route table, NLB, EKS, database, cache or messaging changes.

## Apply gate

Apply requires explicit approval of the saved full plan. No targeted apply and no AWS CLI endpoint creation.

## After

1. `aws ec2 describe-vpc-endpoints`: endpoint type `Gateway`, service `com.amazonaws.us-east-1.s3`, state `available`.
2. `aws ec2 describe-route-tables`: S3 managed prefix-list route points to the endpoint on the private egress route table; NAT default route remains.
3. Pull one existing private ECR image through a controlled, approved canary. Do not restart all workloads.
4. Verify External Secrets, Karpenter/EBS CSI and other required AWS API clients show no new errors.
5. Verify Checkout/Browse/Cart SLI and storefront p95 with active request volume.
6. Repeat NAT CloudWatch and Cost Explorer queries using the same duration/workload after sufficient observation time.
7. Save real after evidence only then.

## Rollback

1. Disable/remove the S3 endpoint module in a reviewed change.
2. Require a plan deleting only the endpoint/output association.
3. Apply; verify S3 traffic resumes through the retained NAT default route.
4. Repeat canary image pull, AWS API access and SLO checks.

## Screenshot names

- `07a-nat-cloudwatch-before.png`
- `07b-network-usage-before.png`
- `08a-s3-endpoint-plan.png`
- `08b-s3-endpoint-available.png`
- `08c-s3-prefix-route.png`
- `08d-image-pull-api-access.png`
- `11-slo-after-s3-endpoint.png`
- `13-network-usage-after.png`
