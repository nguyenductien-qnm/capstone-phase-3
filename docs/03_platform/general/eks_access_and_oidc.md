# EKS access: AWS SSO now, OIDC automation later

## Identity paths are separate

The platform uses three different identity mechanisms. They are not
interchangeable:

| Path | Purpose | Where authorization is defined |
|---|---|---|
| AWS IAM Identity Center (SSO) | Human operator access today | EKS Access Entry + EKS access policy |
| EKS cluster OIDC / IRSA | IAM permissions for Kubernetes service accounts | IAM role trust on the cluster issuer and `sub` claim |
| GitHub Actions OIDC | Short-lived AWS credentials for CI/CD later | IAM role trust on `token.actions.githubusercontent.com` |

## Current operator access with SSO

Authenticate normally:

```bash
aws sso login --profile <profile>
aws eks update-kubeconfig --profile <profile> --region <region> --name <cluster>
```

The Terraform access entry must use the IAM role ARN created for the permission
set, for example:

```text
arn:aws:iam::<account>:role/aws-reserved/sso.amazonaws.com/<region>/AWSReservedSSO_PlatformAdmin_<suffix>
```

Do not copy the temporary value returned by `aws sts get-caller-identity` when
it looks like this:

```text
arn:aws:sts::<account>:assumed-role/AWSReservedSSO_PlatformAdmin_<suffix>/<user>
```

EKS Access Entries require a persistent IAM role ARN. The module validates this
shape and disables implicit cluster-admin permission for the identity that ran
`terraform apply`.

## Workload permissions through IRSA

The EKS module creates the cluster OIDC provider and returns its ARN. Workloads
such as ADOT, External Secrets, Cluster Autoscaler or an S3 exporter should each
receive a dedicated role constrained to a service-account subject:

```text
system:serviceaccount:<namespace>:<service-account>
```

Do not add CloudWatch, X-Ray, S3, autoscaling or database permissions to the
managed-node role. Otherwise every pod capable of reaching node metadata may
inherit permissions unrelated to its job.

## Future GitHub Actions OIDC

GitHub Actions OIDC is an account-level IAM integration and is separate from
the EKS cluster issuer. Its trust policy must constrain both claims:

```text
aud = sts.amazonaws.com
sub = repo:<owner>/<repository>:environment:<environment>
```

Recommended roles:

1. `github-ecr-publisher`: build/push only to approved ECR repositories.
2. `github-infra-plan`: read and plan permissions, no apply.
3. `github-infra-apply`: protected GitHub Environment, reviewed apply and a
   service-specific permission boundary.

If Argo CD performs deployment, GitHub normally does not require Kubernetes
API access. CI updates an immutable image digest in Git, and Argo CD reconciles
it. If direct Kubernetes access is unavoidable, create a separate IAM role and
namespace-scoped `AmazonEKSEditPolicy`; do not reuse the SSO cluster-admin role.

## Public API endpoint

For SSO users running `kubectl` outside the VPC, the dev sandbox currently uses
a public endpoint with `0.0.0.0/0` as an explicit convenience tradeoff for the
distributed TF1 team. Authentication still requires SSO and an EKS Access
Entry. The module permits world-open CIDRs only when `environment = "dev"`;
staging and production must use restricted CIDRs or a private endpoint through
VPN, bastion or a runner inside the VPC.

## Control-plane logs are not application logs

The EKS `api`, `audit` and `authenticator` streams describe Kubernetes control
plane activity: API requests, Kubernetes audit events and IAM authentication.
They are sent directly by EKS to `/aws/eks/<cluster>/cluster` in CloudWatch.

They do not collect container stdout/stderr and do not replace the previously
discussed application-log pipeline. Application logs still require a separate
path such as:

```text
Application stdout -> ADOT/OTel -> CloudWatch Logs -> Firehose -> S3/Athena
```

OpenSearch remains an optional hot search/index backend during migration. The
control-plane logging setting neither installs nor removes OpenSearch.
