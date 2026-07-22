# TF1-53 [AIOps-W2] - Doc trang thai pod THAT tu K8s API (CHI DOC - get/list/watch,
# KHONG co quyen ghi/xoa). Bo sung cho detector: rule log-based khong bao gio khop voi
# OOM dot ngot (kernel SIGKILL container truoc khi no kip ghi log ve cai chet cua chinh
# no - xac nhan qua chaos test that 17/07, xem ADR-012 addendum). K8s tu ghi nhan
# containerStatuses[].lastState.terminated ngay ca khi app khong log duoc gi.
#
# Code nay TRUNG LAP co chu dich voi aiops/remediation/k8s_actions.find_oom_pods() -
# chap nhan trung lap ~25 dong thay vi import cheo giua 2 module (detector khong duoc
# phep co code path nao dan toi hanh dong ghi, giu ranh gioi detect-only ro rang).
import logging
import time

try:
    from kubernetes import client as k8s_client
    from kubernetes import config as k8s_config
except ImportError:
    k8s_client = None
    k8s_config = None

log = logging.getLogger("aiops.detector.k8s_status")


def load_k8s_client():
    """Nap kubeconfig: in-cluster khi chay tren pod that, ~/.kube/config khi dev/test tay."""
    if k8s_config is None or k8s_client is None:
        log.warning("Thu vien kubernetes chua duoc cai dat. Bo qua K8s status checking.")
        return None
    try:
        k8s_config.load_incluster_config()
    except Exception:
        try:
            k8s_config.load_kube_config()
        except Exception:
            return None
    return k8s_client.CoreV1Api()


def find_oom_pods(core_v1, namespace, service_label_key, since_seconds=300):
    if not core_v1:
        return []
    now = time.time()
    found = []
    pods = core_v1.list_namespaced_pod(namespace=namespace)
    for pod in pods.items:
        pod_name = pod.metadata.name
        service_label = (pod.metadata.labels or {}).get(service_label_key, "unknown")
        statuses = pod.status.container_statuses or []
        for cs in statuses:
            terminated = cs.last_state.terminated if cs.last_state else None
            if terminated and terminated.reason == "OOMKilled" and terminated.finished_at:
                age = now - terminated.finished_at.timestamp()
                if age <= since_seconds:
                    found.append({
                        "pod_name": pod_name,
                        "service_label": service_label,
                        "container_name": cs.name,
                        "terminated_at": terminated.finished_at,
                    })
    return found
