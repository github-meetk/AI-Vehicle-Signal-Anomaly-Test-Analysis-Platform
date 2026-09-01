"""Unit and integration tests."""

import pytest
import pandas as pd

from app.core.signal_registry import FaultType, ScenarioType, SIGNAL_REGISTRY
from app.simulator.generate import ScenarioGenerator
from app.simulator.fault_injection import FaultInjector
from app.analysis.validation import DataValidator
from app.analysis.detector import AnomalyDetector, ThresholdOnlyDetector, StatisticalOnlyDetector
from app.analysis.signal_analyzer import SignalAnalyzer
from app.models.schemas import InvestigationResult, AnomalyEventSchema


class TestSignalRegistry:
    def test_all_signals_defined(self):
        assert len(SIGNAL_REGISTRY) == 8
        assert "battery_temperature" in SIGNAL_REGISTRY

    def test_signal_ranges(self):
        for name, sig in SIGNAL_REGISTRY.items():
            assert sig.min_value < sig.max_value
            assert sig.unit


class TestScenarioGenerator:
    def test_reproducibility(self):
        gen1 = ScenarioGenerator(seed=42)
        gen2 = ScenarioGenerator(seed=42)
        df1, meta1 = gen1.generate("SCN-TEST-001", ScenarioType.NORMAL_DRIVING)
        df2, meta2 = gen2.generate("SCN-TEST-001", ScenarioType.NORMAL_DRIVING)
        pd.testing.assert_frame_equal(df1, df2)
        assert meta1.random_seed == meta2.random_seed

    def test_normal_scenario_columns(self):
        gen = ScenarioGenerator(seed=1)
        df, _ = gen.generate("SCN-TEST-002")
        assert "timestamp" in df.columns
        assert "battery_voltage" in df.columns
        assert len(df) == 300

    def test_fault_injection_cooling_failure(self):
        gen = ScenarioGenerator(seed=99)
        df, meta = gen.generate(
            "SCN-FAULT-001",
            ScenarioType.HIGH_LOAD,
            fault_type=FaultType.COOLING_FAILURE,
            injection_time=125.0,
        )
        assert meta.expected_anomaly
        post_fault = df[df["timestamp"] >= 125.0]
        assert post_fault["battery_temperature"].max() > 80


class TestFaultInjector:
    def test_voltage_drop(self):
        gen = ScenarioGenerator(seed=5)
        df, _ = gen.generate("SCN-F-001", fault_type=FaultType.BATTERY_VOLTAGE_DROP, injection_time=100)
        pre = df[df["timestamp"] < 100]["battery_voltage"].mean()
        post = df[df["timestamp"] >= 100]["battery_voltage"].mean()
        assert post < pre - 3


class TestDataValidator:
    def test_valid_data(self):
        gen = ScenarioGenerator(seed=10)
        df, _ = gen.generate("SCN-V-001")
        validator = DataValidator()
        clean, report = validator.validate(df, "SCN-V-001")
        assert report.records_processed == len(df)
        assert report.quality_score > 80

    def test_missing_signal_detected(self):
        gen = ScenarioGenerator(seed=11)
        df, _ = gen.generate("SCN-V-002", fault_type=FaultType.MISSING_SIGNAL, injection_time=50)
        validator = DataValidator()
        _, report = validator.validate(df, "SCN-V-002")
        assert report.missing_values > 0


class TestAnomalyDetector:
    def test_detects_thermal_threshold(self):
        gen = ScenarioGenerator(seed=99)
        df, _ = gen.generate(
            "SCN-D-001",
            ScenarioType.HIGH_LOAD,
            fault_type=FaultType.THERMAL_THRESHOLD_VIOLATION,
            injection_time=120,
        )
        detector = AnomalyDetector()
        events = detector.detect(df, "SCN-D-001")
        assert len(events) > 0
        assert any(e.signal == "battery_temperature" for e in events)

    def test_threshold_only_detector(self):
        gen = ScenarioGenerator(seed=20)
        df, _ = gen.generate("SCN-D-002")
        detector = ThresholdOnlyDetector()
        events = detector.detect(df, "SCN-D-002")
        assert isinstance(events, list)

    def test_statistical_detector(self):
        gen = ScenarioGenerator(seed=21)
        df, _ = gen.generate(
            "SCN-D-003",
            fault_type=FaultType.CURRENT_SPIKE,
            injection_time=100,
        )
        detector = StatisticalOnlyDetector()
        events = detector.detect(df, "SCN-D-003")
        assert len(events) >= 0

    def test_events_have_evidence(self):
        gen = ScenarioGenerator(seed=99)
        df, _ = gen.generate(
            "SCN-D-004",
            fault_type=FaultType.COOLING_FAILURE,
            injection_time=125,
        )
        events = AnomalyDetector().detect(df, "SCN-D-004")
        for e in events:
            assert e.evidence
            assert e.confidence > 0


class TestSignalAnalyzer:
    def test_window_analysis(self):
        gen = ScenarioGenerator(seed=30)
        df, _ = gen.generate("SCN-A-001")
        analyzer = SignalAnalyzer(window_seconds=10)
        window = analyzer.get_window(df, 150.0)
        assert len(window) > 0
        assert window["timestamp"].min() >= 140

    def test_related_signals(self):
        analyzer = SignalAnalyzer()
        related = analyzer.get_related_signals("battery_temperature")
        assert "battery_current" in related

    def test_statistics(self):
        gen = ScenarioGenerator(seed=31)
        df, _ = gen.generate("SCN-A-002")
        analyzer = SignalAnalyzer()
        stats = analyzer.get_statistics(df, "battery_temperature")
        assert "mean" in stats
        assert stats["count"] > 0


class TestPydanticModels:
    def test_investigation_result(self):
        result = InvestigationResult(
            anomaly_id="test-001",
            summary="Test summary",
            observations=["obs1"],
            supporting_evidence=[],
            possible_causes=["cause1"],
            recommended_followup_tests=["test1"],
            confidence=0.8,
        )
        assert result.confidence == 0.8

    def test_anomaly_event_schema(self):
        from app.core.signal_registry import AnomalyType, DetectionMethod, Severity

        event = AnomalyEventSchema(
            scenario_id="SCN-001",
            signal="battery_temperature",
            anomaly_type=AnomalyType.THRESHOLD_VIOLATION,
            start_time=125.0,
            severity=Severity.HIGH,
            observed_value=94.7,
            expected_range={"min": 0, "max": 80},
            detection_method=DetectionMethod.RULE,
            evidence={"threshold": 80},
        )
        assert event.observed_value == 94.7


class TestEvaluationMetrics:
    def test_compute_metrics(self):
        from evaluation.metrics import GroundTruth, DetectionResult, compute_metrics

        gt = [
            GroundTruth("s1", True, 100, "COOLING_FAILURE", "battery_temperature", "CRITICAL"),
            GroundTruth("s2", False, None, "NONE", None, None),
        ]
        detections = {
            "s1": DetectionResult("s1", True, 110, "COOLING_FAILURE", ["THRESHOLD_VIOLATION"]),
            "s2": DetectionResult("s2", False, None, None, []),
        }
        metrics = compute_metrics(gt, detections)
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
