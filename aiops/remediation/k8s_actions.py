# TF1-72 [AIOps-W2] - Lop mong boc Kubernetes API cho remediation engine.
# CHI 2 hanh dong: tim pod bi OOMKilled that + xoa pod (K8s tu tao lai = "restart").
# Khong co action nao khac (scale/clear-cache khong thuoc scope lan nay).
import logging
import time

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

log = logging.getLogger("aiops.remediation.k8s")


def load_k8s_client():
    """Nap kubeconfig: in-cluster khi chay tren pod that, ~/.kube/config khi dev/test tay."""
    try:
        k8s_config.load_incluster_config()
    except k8s_config.ConfigException:
        k8s_config.load_kube_config()
    return k8s_client.CoreV1Api()


def find_oom_pods(core_v1, namespace, service_label_key, since_seconds=300):
    """Tim pod trong `namespace` co container bi OOMKilled trong `since_seconds` gan nhat.

    Doc THAT tu status.containerStatuses[].lastState.terminated (K8s tu ghi nhan,
    khong doan qua text log) - dang tin cay hon parse chuoi log OpenSearch vi log
    body khong co san field ten pod/namespace trong sources.py hien tai.

    Return: list dict {pod_name, service_label, container_name, terminated_at}.
    """
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


def restart_pod(core_v1, namespace, pod_name, grace_period_seconds=30):
    """Xoa pod - ReplicaSet/Deployment tu tao pod moi thay the (= "restart").
    Khong co API "restart" rieng trong K8s cho 1 pod don le."""
    log.info("restart_pod: xoa pod %s/%s (grace=%ss)", namespace, pod_name, grace_period_seconds)
    core_v1.delete_namespaced_pod(
        name=pod_name,
        namespace=namespace,
        grace_period_seconds=grace_period_seconds,
    )


def is_service_ready(core_v1, namespace, service_label_key, service_label, exclude_pod_name):
    """True neu CO IT NHAT 1 pod cung service (label service_label_key=service_label),
    KHAC pod cu da bi xoa (exclude_pod_name), dang Ready that su (readiness gate -
    spec Sec4.2, tranh doi traffic vao pod chua san sang, bai hoc INC-3)."""
    pods = core_v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"{service_label_key}={service_label}",
    )
    for pod in pods.items:
        if pod.metadata.name == exclude_pod_name:
            continue
        conditions = pod.status.conditions or []
        for cond in conditions:
            if cond.type == "Ready" and cond.status == "True":
                return True
    return False
