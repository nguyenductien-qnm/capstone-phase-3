# EKS module

This module provisions:

- an EKS control plane using private application subnets;
- a managed node group with IMDSv2 and encrypted gp3 volumes;
- EKS control-plane logs in CloudWatch;
- an EKS workload OIDC provider for IRSA;
- API-mode EKS Access Entries for SSO and narrowly scoped automation roles;
- CoreDNS, kube-proxy, VPC CNI and Pod Identity Agent managed add-ons.

It deliberately does not install Argo CD, observability workloads, autoscalers
or application resources. Those remain under `platform/` and GitOps.

## Node-role boundary

The node role only receives the EKS worker, VPC CNI and ECR pull policies.
CloudWatch, X-Ray, autoscaler, application and AWS data-service permissions must
be assigned to dedicated Kubernetes service accounts through IRSA or EKS Pod
Identity.

The node group's desired size remains Terraform-managed until an autoscaler is
actually installed. Add an explicit lifecycle strategy only when that ownership
changes; otherwise Terraform would silently ignore intentional capacity edits.

## Human access

`bootstrap_cluster_creator_admin_permissions` is disabled. At least one
explicit `access_entries` item is required. AWS IAM Identity Center users must
provide the underlying `AWSReservedSSO_...` IAM role ARN, never the temporary
STS assumed-role session ARN.
