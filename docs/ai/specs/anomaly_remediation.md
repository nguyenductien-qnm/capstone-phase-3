# Spec Anomaly Detection & Auto-Remediation (AIOps)

## 1. Closed-loop Safety Pattern
```mermaid
sequenceDiagram
    participant Monitor as AIOps Detector
    participant Engine as Remediation Engine
    participant K8s as Kubernetes API
    participant Verify as Telemetry Verifier

    Monitor->>Engine: Anomaly Alert (e.g., Latency Spike / Memory OOM)
    Engine->>Engine: Check Blast-Radius (Limits affected nodes)
    alt Within Limits
        Engine->>Engine: Run Dry-run Checks
        Engine->>K8s: Execute Action (e.g., Restart Pod / Rollback Config)
        Note over K8s: Action Executed
        Engine->>Verify: Start Verification (Timeout: 120s)
        Verify->>Verify: Query Prometheus (Latency / Error Rate)
        alt Verify Fails
            Verify->>Engine: Alert: Verification Failed
            Engine->>K8s: Auto Rollback to Previous State
            Engine->>Engine: Increment Circuit Breaker Failure
        else Verify Passes
            Verify->>Engine: Status: Healthy
            Engine->>Engine: Reset Circuit Breaker
        end
    else Exceeds Blast-Radius
        Engine->>Engine: Halt Automation & Escalation (Page Human)
    end
```

## 2. Detection Configuration (EWMA / Drain3)
- **Metric anomaly:** Theo dõi `http_request_duration_seconds` (p95) qua EWMA (alpha = 0.2, threshold = 3 standard deviations).
- **Log mining:** Lọc log qua bộ gom cụm **Drain3**. Gửi cảnh báo Slack khi phát hiện log template mới chứa từ khóa `ERROR`, `CRITICAL`, hoặc `OOM`.

## 3. Safety Boundaries (Blast-radius)
- **Max Pods affected:** Tối đa 1 pod/namespace được restart tự động mỗi giờ.
- **Circuit Breaker:** 3 lần khôi phục thất bại liên tiếp sẽ khóa chặt luồng tự động sửa lỗi và chuyển sang chế độ thủ công (Page On-call).
