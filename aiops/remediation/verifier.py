# TF1-72 [AIOps-W2] - Xac minh sau khi hanh dong (Verify, spec Sec4.4): poll lap lai
# trong `duration_seconds`, moi `poll_interval_seconds` (mac dinh 120s/20s = ~6 poll,
# thoa toi thieu 3 poll/60s cua spec). Pattern phong theo wait_count_increase() trong
# docs/ai/evals/measure_detection_pipeline.py nhung DAO dieu kien: PASS khi da hoi
# phuc (khong phai "da tang").
#
# Cho kich ban OOM: verify PASS khi (a) pod moi cung service da Ready that su, VA
# (b) khong co OOMKilled MOI nao phat sinh them trong luc cho. Khong phu thuoc
# memory-saturation-high (rule DRAFT, can kube-state-metrics chua xac nhan co tren
# cluster) - check Prometheus chi la best-effort neu duoc cau hinh.
import logging
import time

from k8s_actions import find_oom_pods, is_service_ready

log = logging.getLogger("aiops.remediation.verifier")


def verify_oom_recovery(core_v1, namespace, service_label_key, service_label,
                         old_pod_name, duration_seconds=120, poll_interval_seconds=20):
    """Poll toi da `duration_seconds`, tra ve True ngay khi pod moi Ready ON DINH
    (2 lan poll lien tiep Ready, khong chi 1 lan thoang qua) VA khong co OOMKilled
    moi. False neu het thoi gian ma chua dat."""
    deadline = time.time() + duration_seconds
    consecutive_ready = 0
    while time.time() < deadline:
        new_oom = find_oom_pods(core_v1, namespace, service_label_key, since_seconds=poll_interval_seconds * 2)
        # Loai tru chinh pod cu (da biet no OOM roi, khong tinh la "moi").
        new_oom = [p for p in new_oom if p["pod_name"] != old_pod_name]
        if new_oom:
            log.warning("verify: phat hien OOMKilled MOI trong luc cho hoi phuc: %s", new_oom)
            return False

        if is_service_ready(core_v1, namespace, service_label_key, service_label, old_pod_name):
            consecutive_ready += 1
            if consecutive_ready >= 2:
                log.info("verify: service %s da Ready on dinh, PASS", service_label)
                return True
        else:
            consecutive_ready = 0

        time.sleep(poll_interval_seconds)

    log.warning("verify: het %ss ma pod van chua Ready on dinh, FAIL", duration_seconds)
    return False
