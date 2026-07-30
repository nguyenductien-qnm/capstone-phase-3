#!/usr/bin/env bash
#
# CDO-83 — Verify end-to-end Deploy Safety (Mandate-03) + thu Evidence.
#
# Chay 3 kich ban va thu bang chung SLO khong tut:
#   KB1 drain node        -> PDB giu >=1 pod, autoscaler bu node (test DoNotSchedule + CDO-34)
#   KB2 bad deploy        -> readiness gate: pod hong KHONG vao endpoints, rollback duoc (INC-3)
#   KB3 rolling under load -> 0 request loi khi rollout (probe + graceful CDO-29/81)
#
# AN TOAN:
#   - Guard context: chi chay tren cluster sandbox mong doi (EXPECT_CONTEXT).
#   - DRY_RUN=1 (mac dinh): CHI snapshot + doc, KHONG drain/deploy/rollout gi.
#     Dat DRY_RUN=0 de thuc su chay kich ban (co the gay churn — chi lam tren sandbox).
#   - Trap: luon uncordon node da cordon khi thoat.
#
# Dung:
#   DRY_RUN=1 ./verify-deploy-safety.sh all           # xem truoc, khong dong gi
#   DRY_RUN=0 ./verify-deploy-safety.sh kb1            # chay rieng KB1
#   DRY_RUN=0 ./verify-deploy-safety.sh all            # chay ca 3
#
set -uo pipefail

# ------------------------------------------------------------------ config ----
NS="${NS:-techx-tf1}"
EXPECT_CONTEXT="${EXPECT_CONTEXT:-ecommerce-dev-eks}"   # substring phai co trong kubectl context
PROM_SVC="${PROM_SVC:-prometheus}"
PROM_PORT="${PROM_PORT:-9090}"
CRIT_SVCS=(checkout cart product-catalog frontend frontend-proxy)
FOCUS="${FOCUS:-checkout}"                              # service dung lam tam diem KB1/KB2
BAD_IMAGE="${BAD_IMAGE:-busybox:cdo83-doesnotexist}"    # tag chac chan pull fail cho KB2
DRY_RUN="${DRY_RUN:-1}"
STAMP="$(date +%Y%m%d-%H%M%S)"
EVID_DIR="${EVID_DIR:-$(cd "$(dirname "$0")/../.." && pwd)/docs/templates/cdo/evidence/cdo83-$STAMP}"
PF_PID=""
CORDONED_NODE=""

# ---------------------------------------------------------------- helpers -----
c_red=$'\e[31m'; c_grn=$'\e[32m'; c_yel=$'\e[33m'; c_rst=$'\e[0m'
log()  { echo "${c_grn}[CDO-83]${c_rst} $*"; }
warn() { echo "${c_yel}[CDO-83][warn]${c_rst} $*"; }
die()  { echo "${c_red}[CDO-83][FAIL]${c_rst} $*" >&2; exit 1; }
hr()   { printf '%.0s-' {1..70}; echo; }

# ghi vao ca stdout va file evidence
cap() {  # cap <ten-file> <lenh...>
  local name="$1"; shift
  local out="$EVID_DIR/$name.txt"
  { echo "\$ $*"; echo; "$@"; } 2>&1 | tee -a "$out"
  echo | tee -a "$out"
}

cleanup() {
  [[ -n "$PF_PID" ]] && kill "$PF_PID" 2>/dev/null
  if [[ -n "$CORDONED_NODE" ]]; then
    warn "uncordon $CORDONED_NODE (trap)"
    kubectl uncordon "$CORDONED_NODE" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

prom_pf() {
  kubectl -n "$NS" port-forward "svc/$PROM_SVC" "$PROM_PORT:$PROM_PORT" >/tmp/cdo83-pf.log 2>&1 &
  PF_PID=$!; sleep 5
}

# query instant -> in gia tri scalar
promq() {  # promq <expr>
  curl -s -G "http://localhost:$PROM_PORT/api/v1/query" --data-urlencode "query=$1" \
    | python -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'NA')" 2>/dev/null
}

slo_snapshot() {  # slo_snapshot <nhan>
  local tag="$1"
  local f="$EVID_DIR/slo-$tag.txt"
  {
    echo "# SLO snapshot [$tag] @ $(date -u +%FT%TZ)"
    for s in checkout frontend cart; do
      printf "%-16s success%%=%s\n" "$s" \
        "$(promq "100 * sum(rate(traces_span_metrics_calls_total{service_name=\"$s\",status_code!=\"STATUS_CODE_ERROR\"}[5m])) / clamp_min(sum(rate(traces_span_metrics_calls_total{service_name=\"$s\"}[5m])),1e-9)")"
    done
    printf "%-16s p95_ms=%s\n" "frontend" \
      "$(promq "histogram_quantile(0.95, sum(rate(traces_span_metrics_duration_milliseconds_bucket{service_name=\"frontend\"}[5m])) by (le))")"
    printf "%-16s reqps=%s\n" "total" \
      "$(promq "sum(rate(traces_span_metrics_calls_total{service_name=~\"frontend|cart|checkout\"}[5m]))")"
  } | tee "$f"
  echo
}

state_snapshot() {  # state_snapshot <nhan>
  local tag="$1"
  cap "state-$tag-pods"      kubectl -n "$NS" get pods -o wide
  cap "state-$tag-pdb"       kubectl -n "$NS" get pdb
  cap "state-$tag-endpoints" kubectl -n "$NS" get endpoints "${CRIT_SVCS[@]}"
  cap "state-$tag-nodes"     kubectl get nodes -o wide
}

guard() {
  command -v kubectl >/dev/null || die "kubectl khong co"
  command -v python  >/dev/null || die "python khong co (dung parse PromQL)"
  local ctx; ctx="$(kubectl config current-context 2>/dev/null || true)"
  [[ "$ctx" == *"$EXPECT_CONTEXT"* ]] || die "context '$ctx' khong khop EXPECT_CONTEXT='$EXPECT_CONTEXT' — TU CHOI de tranh cham nham cluster"
  kubectl -n "$NS" get deploy "$FOCUS" >/dev/null 2>&1 || die "khong thay deploy/$FOCUS trong ns/$NS"
  mkdir -p "$EVID_DIR"
  log "context=$ctx  ns=$NS  DRY_RUN=$DRY_RUN  evidence=$EVID_DIR"
}

# ------------------------------------------------------------------ KB1 --------
kb1_drain() {
  hr; log "KB1 — Node drain (yeu cau (1) + PDB, test INC-2 + DoNotSchedule)"
  cap "kb1-pdb-before" kubectl -n "$NS" get pdb
  cap "kb1-pods-before" kubectl -n "$NS" get pods -o wide -l app.kubernetes.io/component="$FOCUS"

  local node
  node="$(kubectl -n "$NS" get pod -l app.kubernetes.io/component="$FOCUS" \
          -o jsonpath='{.items[0].spec.nodeName}' 2>/dev/null)"
  [[ -n "$node" ]] || die "khong xac dinh duoc node cua $FOCUS"
  log "node muc tieu: $node"

  slo_snapshot "kb1-before"

  if [[ "$DRY_RUN" == "1" ]]; then
    warn "DRY_RUN=1 — se KHONG drain. Lenh se chay khi DRY_RUN=0:"
    echo "    kubectl cordon $node"
    echo "    kubectl drain $node --ignore-daemonsets --delete-emptydir-data --timeout=180s"
    return 0
  fi

  CORDONED_NODE="$node"
  cap "kb1-drain" kubectl drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout=180s
  log "theo doi endpoints $FOCUS luon co pod Ready trong khi drain..."
  cap "kb1-endpoints-during" kubectl -n "$NS" get endpoints "$FOCUS"
  cap "kb1-pods-during" kubectl -n "$NS" get pods -o wide -l app.kubernetes.io/component="$FOCUS"
  slo_snapshot "kb1-during"

  log "uncordon $node (tra node lai)"
  cap "kb1-uncordon" kubectl uncordon "$node"; CORDONED_NODE=""
  kubectl -n "$NS" rollout status deploy/"$FOCUS" --timeout=180s || warn "rollout status timeout"
  slo_snapshot "kb1-after"
  log "KB1 xong. Kiem: endpoints luon co pod Ready; SLO khong tut; neu 2 pod cung node truoc do -> DoNotSchedule ep rai."
}

# ------------------------------------------------------------------ KB2 --------
kb2_bad_deploy() {
  hr; log "KB2 — Bad deploy (yeu cau (3): pod hong khong nhan traffic, test INC-3)"
  local ctr; ctr="$(kubectl -n "$NS" get deploy "$FOCUS" -o jsonpath='{.spec.template.spec.containers[0].name}')"
  slo_snapshot "kb2-before"

  if [[ "$DRY_RUN" == "1" ]]; then
    warn "DRY_RUN=1 — se KHONG deploy hong. Lenh se chay khi DRY_RUN=0:"
    echo "    kubectl -n $NS set image deploy/$FOCUS $ctr=$BAD_IMAGE"
    echo "    kubectl -n $NS rollout status deploy/$FOCUS --timeout=60s   # ky vong: TREO"
    echo "    kubectl -n $NS get endpoints $FOCUS                          # pod hong KHONG vao"
    echo "    kubectl -n $NS rollout undo deploy/$FOCUS"
    return 0
  fi

  cap "kb2-setimage" kubectl -n "$NS" set image deploy/"$FOCUS" "$ctr=$BAD_IMAGE"
  log "cho rollout (ky vong TREO — pod moi khong Ready)..."
  kubectl -n "$NS" rollout status deploy/"$FOCUS" --timeout=60s 2>&1 | tee "$EVID_DIR/kb2-rollout.txt" || warn "rollout treo dung nhu ky vong"
  cap "kb2-pods" kubectl -n "$NS" get pods -o wide -l app.kubernetes.io/component="$FOCUS"
  cap "kb2-endpoints" kubectl -n "$NS" get endpoints "$FOCUS"
  slo_snapshot "kb2-during"

  log "rollback..."
  cap "kb2-undo" kubectl -n "$NS" rollout undo deploy/"$FOCUS"
  kubectl -n "$NS" rollout status deploy/"$FOCUS" --timeout=180s || warn "rollout status timeout"
  slo_snapshot "kb2-after"
  log "KB2 xong. Kiem: pod hong KHONG co trong endpoints; SLO khong tut; rollback sach."
}

# ------------------------------------------------------------------ KB3 --------
kb3_rolling() {
  hr; log "KB3 — Rolling deploy duoi tai (yeu cau (1) + graceful CDO-29/81)"
  slo_snapshot "kb3-before"

  if [[ "$DRY_RUN" == "1" ]]; then
    warn "DRY_RUN=1 — se KHONG rollout. Lenh se chay khi DRY_RUN=0:"
    echo "    kubectl -n $NS rollout restart deploy/${CRIT_SVCS[*]}"
    return 0
  fi

  cap "kb3-restart" kubectl -n "$NS" rollout restart deploy/"${CRIT_SVCS[@]}"
  log "lay mau SLO moi 15s trong khi rollout (6 lan)..."
  for i in $(seq 1 6); do
    slo_snapshot "kb3-during-$i"; sleep 15
  done
  for s in "${CRIT_SVCS[@]}"; do
    kubectl -n "$NS" rollout status deploy/"$s" --timeout=180s || warn "$s rollout timeout"
  done
  slo_snapshot "kb3-after"
  log "KB3 xong. Kiem: checkout success% giu ~100, p95<1000ms xuyen suot; 0 connection reset."
  warn "Connection reset that phai doi tu client (locust) — xem locust stats / 5xx panel, dan vao evidence."
}

# ------------------------------------------------------------------ main -------
main() {
  guard
  prom_pf
  log "baseline snapshot truoc khi test"
  state_snapshot "baseline"
  slo_snapshot   "baseline"

  case "${1:-all}" in
    kb1) kb1_drain ;;
    kb2) kb2_bad_deploy ;;
    kb3) kb3_rolling ;;
    all) kb1_drain; kb2_bad_deploy; kb3_rolling ;;
    *)   die "unknown scenario '$1' (dung: kb1|kb2|kb3|all)" ;;
  esac

  state_snapshot "final"
  hr
  log "HOAN TAT. Evidence pack: $EVID_DIR"
  log "Nho bo sung: screenshot Grafana SLO dashboard truoc/trong/sau + locust stats (5xx/reset)."
}

main "$@"
