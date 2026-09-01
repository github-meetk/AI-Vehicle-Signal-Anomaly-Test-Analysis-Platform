"""Evaluation metrics computation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DetectionResult:
    scenario_id: str
    detected: bool
    detection_time: float | None
    fault_type: str | None
    anomaly_types: list[str]


@dataclass
class GroundTruth:
    scenario_id: str
    expected_anomaly: bool
    injection_time: float | None
    fault_type: str
    affected_signal: str | None
    severity: str | None


def compute_metrics(
    ground_truth: list[GroundTruth],
    detections: dict[str, DetectionResult],
) -> dict:
    tp = fp = fn = tn = 0
    latencies: list[float] = []
    type_correct = 0
    type_total = 0

    for gt in ground_truth:
        det = detections.get(gt.scenario_id)
        if gt.expected_anomaly:
            if det and det.detected:
                tp += 1
                if gt.injection_time and det.detection_time:
                    latencies.append(max(0, det.detection_time - gt.injection_time))
                if det.fault_type and gt.fault_type:
                    type_total += 1
                    if _fault_matches(gt.fault_type, det.anomaly_types):
                        type_correct += 1
            else:
                fn += 1
        else:
            if det and det.detected:
                fp += 1
            else:
                tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
    type_acc = type_correct / type_total if type_total > 0 else None

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "avg_detection_latency": round(avg_latency, 2),
        "fault_type_accuracy": round(type_acc, 4) if type_acc is not None else None,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def _fault_matches(fault_type: str, anomaly_types: list[str]) -> bool:
    mapping = {
        "BATTERY_VOLTAGE_DROP": ["THRESHOLD_VIOLATION", "STATISTICAL_OUTLIER"],
        "CURRENT_SPIKE": ["STATISTICAL_OUTLIER", "RATE_OF_CHANGE"],
        "TEMPERATURE_SPIKE": ["THRESHOLD_VIOLATION", "STATISTICAL_OUTLIER", "RATE_OF_CHANGE"],
        "TEMPERATURE_SENSOR_DRIFT": ["STATISTICAL_OUTLIER", "STUCK_VALUE"],
        "STUCK_SENSOR": ["STUCK_VALUE"],
        "MISSING_SIGNAL": ["MISSING_SIGNAL"],
        "COOLING_FAILURE": ["THRESHOLD_VIOLATION", "RELATIONSHIP_VIOLATION", "THERMAL_WARNING"],
        "IMPOSSIBLE_SIGNAL_COMBINATION": ["IMPOSSIBLE_COMBINATION", "RELATIONSHIP_VIOLATION"],
        "THERMAL_THRESHOLD_VIOLATION": ["THRESHOLD_VIOLATION", "THERMAL_WARNING"],
    }
    expected = mapping.get(fault_type, [])
    return any(at in expected for at in anomaly_types)
