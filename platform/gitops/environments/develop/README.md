# Develop GitOps

This directory is a self-contained GitOps entry point for the EKS cluster in AWS account `458580846647`.

## Why Product-like cannot consume it

The Product-like root application scans only `platform/gitops/applications`. The Develop bootstrap applies `bootstrap/root-app.yaml`, which scans only `platform/gitops/environments/develop/applications`. No Product-like Application or Sandbox values file was edited or referenced by this Develop tree.

The shared pieces are intentional:

- application chart: `platform/charts/application`;
- public third-party Helm charts;
- image repository in ECR account `804372444787`.

Environment-specific applications, values, namespace, IAM role ARNs, Karpenter selectors and root application are all copied under this directory. Develop does not reference `environments/sandbox`.

## Initial safety posture

- ArgoCD automated sync, prune and self-heal are disabled on the root and every child Application.
- No Argo resource finalizers are configured in this tree.
- Application namespace is `techx-develop`, not `techx-tf1`.
- Public frontend ingress is disabled, so the Product-like ACM certificate and hostname cannot be rendered.
- Application Deployments inherit one replica and every currently enabled HPA is disabled.
- Image tags are a Develop snapshot. Product-like CI does not update this copy.
- External Secrets reads only prefix `ecommerce-develop-dev` through the Develop-account IRSA role.
- The dedicated observability scheduling rules remain because the EKS module creates an observability node group.

## First sync order

After the workflow registers `develop-root`, inspect its diff and manually sync it to create the child Applications. Then inspect and sync children in this order:

1. `develop-karpenter-crd`;
2. `develop-karpenter`;
3. `develop-karpenter-nodepool`;
4. `develop-external-secrets` and `develop-metrics-server`;
5. `develop-techx-corp` only after both Develop node roles can pull from the shared ECR and the expected Secrets Manager entries exist.

Before the application sync, verify the shared ECR repository policy contains only these Develop principals:

- `arn:aws:iam::458580846647:role/ecommerce-develop-dev-eks-node-role`;
- `arn:aws:iam::458580846647:role/ecommerce-develop-dev-eks-karpenter-node`.

A missing ECR resource policy or missing NAT/VPC endpoint path will result in `ImagePullBackOff`; IAM permission alone is not sufficient.
