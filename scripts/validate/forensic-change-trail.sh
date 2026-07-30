#!/usr/bin/env bash
set -euo pipefail
TARGET="" REVISION="" APP=""
usage(){ echo "Usage: $0 --target FILE_OR_K8S_RESOURCE [--revision SHA] [--argocd-application NAME]"; }
while [[ $# -gt 0 ]]; do case "$1" in --target) TARGET="$2";shift 2;; --revision) REVISION="$2";shift 2;; --argocd-application) APP="$2";shift 2;; -h|--help) usage;exit 0;; *) echo "Unknown: $1";exit 2;; esac; done
[[ -n "$TARGET" ]] || { usage; exit 2; }
echo "Correlation path: Kubernetes audit event -> ArgoCD revision -> Git commit -> Pull Request -> Jira"
if [[ -n "$APP" ]]; then echo "kubectl -n argocd get application '$APP' -o jsonpath='{.status.sync.revision}'"; fi
if [[ -f "$TARGET" ]]; then
  git log --date=iso-strict --format='%h %ad %an %s' -- "$TARGET" | head -20
  echo "git blame --date=iso '$TARGET'"
else
  echo "Use forensic-k8s-audit.sh with --resource-name '$TARGET', then identify objectRef and userAgent."
fi
if [[ -n "$REVISION" ]]; then git show --stat --oneline "$REVISION"; echo "git log --decorate --oneline '$REVISION'^..'$REVISION'"; else echo "Provide --revision from ArgoCD status.sync.revision for git show."; fi
echo "PR/Jira: inspect the commit's GitHub PR association and require the Jira field in that PR/change record."
echo "Supported evidence includes Helm values, Terraform files, image-tag files, and team-owned flag configuration; this script never modifies central flagd configuration."
