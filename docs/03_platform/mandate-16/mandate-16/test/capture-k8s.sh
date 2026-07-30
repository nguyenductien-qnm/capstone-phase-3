#!/usr/bin/env bash

set -euo pipefail

NAMESPACE="${NAMESPACE:-techx-develop}"
OUTPUT_DIR="${1:-k8s-snapshot}"

mkdir -p "$OUTPUT_DIR"
date --iso-8601=seconds > "$OUTPUT_DIR/captured-at.txt"
kubectl -n "$NAMESPACE" get deployments -o wide > "$OUTPUT_DIR/deployments.txt"
kubectl -n "$NAMESPACE" get deployments -o yaml > "$OUTPUT_DIR/deployments.yaml"
kubectl -n "$NAMESPACE" get hpa -o wide > "$OUTPUT_DIR/hpa.txt"
kubectl -n "$NAMESPACE" get hpa -o yaml > "$OUTPUT_DIR/hpa.yaml"
kubectl -n "$NAMESPACE" get pods -o wide > "$OUTPUT_DIR/pods.txt"
kubectl -n "$NAMESPACE" top pods > "$OUTPUT_DIR/top-pods.txt"
kubectl get nodes -o wide > "$OUTPUT_DIR/nodes.txt"
kubectl top nodes > "$OUTPUT_DIR/top-nodes.txt"
kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp > "$OUTPUT_DIR/events.txt"

echo "Kubernetes evidence captured in $OUTPUT_DIR"
