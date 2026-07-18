# Develop GitOps

This directory is a self-contained GitOps entry point for the EKS cluster in AWS account `458580846647`.

## Why Product-like cannot consume it

The Product-like root application scans only `platform/gitops/applications`. The Develop bootstrap applies `bootstrap/root-app.yaml`, which scans only `platform/gitops/environments/develop/applications`. No Product-like Application or Sandbox values file was edited or referenced by this Develop tree.

The shared pieces are intentional:

- application chart: `platform/charts/application`;
- public third-party Helm charts;
- the application image registry will be selected in a later phase.

Environment-specific applications, values, namespace, IAM role ARNs, Karpenter selectors and root application are all copied under this directory. Develop does not reference `environments/sandbox`.

## Initial safety posture

- ArgoCD automated sync, prune and self-heal are disabled on the root and every child Application.
- No Argo resource finalizers are configured in this tree.
- Application namespace is `techx-develop`, not `techx-tf1`.
- The shared frontend ALB Ingress remains disabled, so the Product-like ACM certificate and hostname cannot be rendered. Develop instead prepares a separate HTTP-only NLB Service under `public-exposure/`.
- Application Deployments inherit one replica and every currently enabled HPA is disabled.
- Image tags are a Develop snapshot. Product-like CI does not update this copy.
- External Secrets reads only prefix `ecommerce-develop-dev` through the Develop-account IRSA role.
- The dedicated observability scheduling rules remain because the EKS module creates an observability node group.
- Karpenter CRDs, controller and NodePool are excluded from `develop-root` during the initial phase. The Terraform IAM scaffold remains dormant and does not provision EC2 nodes by itself.

## First sync order

After the workflow registers `develop-root`, inspect its diff and manually sync it to create the child Applications. Then inspect and sync children in this order:

1. `develop-external-secrets`, `develop-metrics-server` and `develop-aws-load-balancer-controller`;
2. wait for the AWS Load Balancer Controller Pod to become Ready, then optionally sync `develop-frontend-proxy-nlb` to create only the public NLB Service;
3. do not sync `develop-techx-corp` until the registry, image pull access and required Secrets Manager entries are ready.

The resulting NLB accepts plain HTTP on port `80` and targets the
`frontend-proxy` Pods directly on port `8080`. Until the later application
phase creates matching Pods, the Service has no endpoints and the NLB has no
healthy targets. This phase does not add an image, change Envoy routes or make
Grafana, Jaeger, Locust or Argo CD public.

To enable Karpenter in a later phase, first complete the registry decision and
image-pull access, then remove the Karpenter exclusion from
`bootstrap/root-app.yaml` and review the three dormant child Applications
before syncing them.
