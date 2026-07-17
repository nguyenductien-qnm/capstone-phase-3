#!/usr/bin/env python3
import math
import json

# Synthetic ground-truth dataset generator
def generate_synthetic_metrics():
    # Normal variation around 0.15s (std dev ≈ 0.02)
    # Step 30 to 45: gradual degradation (latency increases to 1.2s)
    # Step 70: sudden spike (latency 2.5s)
    data = []
    
    # Ground truth labels
    # We define anomalies as step 36-45 (gradual latency escalation) and step 70 (sudden peak)
    for step in range(100):
        val = 0.15 + 0.02 * math.sin(step)
        is_anomaly = False
        
        if 30 <= step <= 45:
            # Gradual ramp-up
            val += 0.07 * (step - 29)
            if step >= 35:  # Consider it anomaly after it starts violating SLO or baseline significantly
                is_anomaly = True
        elif step == 70:
            val = 2.5
            is_anomaly = True
            
        data.append({"step": step, "value": val, "is_anomaly": is_anomaly})
    return data

def run_evaluation():
    dataset = generate_synthetic_metrics()
    
    # Detector configurations
    static_threshold = 1.0  # static SLO breach
    metric_history = []
    
    tp_static, fp_static, fn_static, tn_static = 0, 0, 0, 0
    tp_3sigma, fp_3sigma, fn_3sigma, tn_3sigma = 0, 0, 0, 0
    tp_hybrid, fp_hybrid, fn_hybrid, tn_hybrid = 0, 0, 0, 0
    
    ttd_static = None
    ttd_3sigma = None
    ttd_hybrid = None
    
    gradual_remediation_start = 30  # Actual fault injection start
    
    for item in dataset:
        val = item["value"]
        actual_anomaly = item["is_anomaly"]
        step = item["step"]
        
        # 1. Static Rule Fired
        static_fired = val > static_threshold
        
        # 2. 3-Sigma Dynamic Rule Fired
        dynamic_fired = False
        if len(metric_history) >= 5:
            mean = sum(metric_history) / len(metric_history)
            variance = sum((x - mean) ** 2 for x in metric_history) / len(metric_history)
            std_dev = math.sqrt(variance)
            dynamic_th = mean + 3 * std_dev
            if val > dynamic_th and (val - mean) > 0.01:
                dynamic_fired = True
                
        # Update history
        metric_history.append(val)
        if len(metric_history) > 30:
            metric_history.pop(0)
            
        # Hybrid Fired (either static or dynamic)
        hybrid_fired = static_fired or dynamic_fired
        
        # Metrics accumulation for Static
        if static_fired and actual_anomaly:
            tp_static += 1
            if ttd_static is None and step >= gradual_remediation_start and step <= 45:
                ttd_static = step - gradual_remediation_start
        elif static_fired and not actual_anomaly:
            fp_static += 1
        elif not static_fired and actual_anomaly:
            fn_static += 1
        elif not static_fired and not actual_anomaly:
            tn_static += 1
            
        # Metrics accumulation for 3-Sigma
        if dynamic_fired and actual_anomaly:
            tp_3sigma += 1
            if ttd_3sigma is None and step >= gradual_remediation_start and step <= 45:
                ttd_3sigma = step - gradual_remediation_start
        elif dynamic_fired and not actual_anomaly:
            fp_3sigma += 1
        elif not dynamic_fired and actual_anomaly:
            fn_3sigma += 1
        elif not dynamic_fired and not actual_anomaly:
            tn_3sigma += 1
            
        # Metrics accumulation for Hybrid
        if hybrid_fired and actual_anomaly:
            tp_hybrid += 1
            if ttd_hybrid is None and step >= gradual_remediation_start and step <= 45:
                ttd_hybrid = step - gradual_remediation_start
        elif hybrid_fired and not actual_anomaly:
            fp_hybrid += 1
        elif not hybrid_fired and actual_anomaly:
            fn_hybrid += 1
        elif not hybrid_fired and not actual_anomaly:
            tn_hybrid += 1

    # Calculating rates
    def calculate_metrics(tp, fp, fn, tn):
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        return precision, recall, f1

    p_stat, r_stat, f1_stat = calculate_metrics(tp_static, fp_static, fn_static, tn_static)
    p_3sig, r_3sig, f1_3sig = calculate_metrics(tp_3sigma, fp_3sigma, fn_3sigma, tn_3sigma)
    p_hyb, r_hyb, f1_hyb = calculate_metrics(tp_hybrid, fp_hybrid, fn_hybrid, tn_hybrid)

    results = {
        "static": {
            "precision": p_stat,
            "recall": r_stat,
            "f1_score": f1_stat,
            "ttd_steps": ttd_static or -1
        },
        "3_sigma": {
            "precision": p_3sig,
            "recall": r_3sig,
            "f1_score": f1_3sig,
            "ttd_steps": ttd_3sigma or -1
        },
        "hybrid": {
            "precision": p_hyb,
            "recall": r_hyb,
            "f1_score": f1_hyb,
            "ttd_steps": ttd_hybrid or -1
        }
    }
    
    print("=== AIOps Detector Performance Evaluation ===")
    print(f"Ground truth dataset: 100 steps. Gradual anomaly at steps 30-45. Sudden spike at step 70.")
    print("\n--- Static Threshold Detector (Threshold = 1.0) ---")
    print(f"Precision : {p_stat:.2%}")
    print(f"Recall    : {r_stat:.2%}")
    print(f"F1 Score  : {f1_stat:.2%}")
    print(f"TTD (Time To Detection): {ttd_static} steps (detec at step {gradual_remediation_start + ttd_static if ttd_static is not None else 'N/A'})")
    
    print("\n--- 3-Sigma Dynamic Detector ---")
    print(f"Precision : {p_3sig:.2%}")
    print(f"Recall    : {r_3sig:.2%}")
    print(f"F1 Score  : {f1_3sig:.2%}")
    print(f"TTD (Time To Detection): {ttd_3sigma} steps (detec at step {gradual_remediation_start + ttd_3sigma if ttd_3sigma is not None else 'N/A'})")

    print("\n--- Hybrid Detector (Static OR 3-Sigma) ---")
    print(f"Precision : {p_hyb:.2%}")
    print(f"Recall    : {r_hyb:.2%}")
    print(f"F1 Score  : {f1_hyb:.2%}")
    print(f"TTD (Time To Detection): {ttd_hybrid} steps (detec at step {gradual_remediation_start + ttd_hybrid if ttd_hybrid is not None else 'N/A'})")

    with open("detector_kpi_metrics.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nKPI metrics exported to detector_kpi_metrics.json")

if __name__ == "__main__":
    run_evaluation()
