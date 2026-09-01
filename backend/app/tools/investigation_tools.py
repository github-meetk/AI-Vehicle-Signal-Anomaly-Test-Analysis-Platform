"""Deterministic tools for the AI investigation agent."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.analysis.signal_analyzer import SignalAnalyzer
from app.core.signal_registry import SIGNAL_REGISTRY, get_signal_definition
from app.database.models import AnomalyDB
from app.services.requirements import (
    REQUIREMENTS,
    TESTS,
    get_requirements_for_signal,
    get_tests_for_requirement,
)
from app.services.scenario_service import ScenarioService


class InvestigationTools:
    """Tool implementations — all deterministic, structured I/O."""

    def __init__(self, db: Session):
        self.db = db
        self.scenario_service = ScenarioService(db)
        self.analyzer = SignalAnalyzer()
        self._trace: list[dict] = []

    def get_trace(self) -> list[dict]:
        return self._trace

    def _log(self, tool: str, inp: dict, output: Any, status: str, latency_ms: float):
        summary = str(output)[:200] if output else ""
        self._trace.append(
            {
                "tool": tool,
                "input": inp,
                "output_summary": summary,
                "status": status,
                "latency_ms": latency_ms,
            }
        )

    def get_anomaly(self, anomaly_id: str) -> dict:
        start = time.time()
        a = self.db.query(AnomalyDB).filter(AnomalyDB.id == anomaly_id).first()
        if not a:
            result = {"error": f"Anomaly {anomaly_id} not found"}
            self._log("get_anomaly", {"anomaly_id": anomaly_id}, result, "error", 0)
            return result
        result = {
            "id": a.id,
            "scenario_id": a.scenario_id,
            "signal": a.signal,
            "anomaly_type": a.anomaly_type,
            "start_time": a.start_time,
            "severity": a.severity,
            "observed_value": a.observed_value,
            "expected_range": a.expected_range,
            "detection_method": a.detection_method,
            "evidence": a.evidence,
            "confidence": a.confidence,
        }
        self._log("get_anomaly", {"anomaly_id": anomaly_id}, result, "success", (time.time() - start) * 1000)
        return result

    def get_signal_window(
        self, scenario_id: str, center_time: float, window_seconds: float = 10.0
    ) -> dict:
        start = time.time()
        df = self.scenario_service.get_scenario_df(scenario_id)
        if df.empty:
            result = {"error": "No signal data"}
            self._log("get_signal_window", locals(), result, "error", 0)
            return result
        window = self.analyzer.get_window(df, center_time, window_seconds)
        result = {"records": window.to_dict(orient="records"), "count": len(window)}
        self._log("get_signal_window", {"scenario_id": scenario_id, "center_time": center_time}, result, "success", (time.time() - start) * 1000)
        return result

    def get_signal_statistics(
        self, scenario_id: str, signal: str, center_time: float | None = None, window: float = 10.0
    ) -> dict:
        start = time.time()
        df = self.scenario_service.get_scenario_df(scenario_id)
        if center_time is not None:
            df = self.analyzer.get_window(df, center_time, window)
        result = self.analyzer.get_statistics(df, signal)
        self._log("get_signal_statistics", {"scenario_id": scenario_id, "signal": signal}, result, "success", (time.time() - start) * 1000)
        return result

    def get_related_signals(self, signal: str) -> dict:
        start = time.time()
        related = self.analyzer.get_related_signals(signal)
        definitions = []
        for s in related:
            d = get_signal_definition(s)
            if d:
                definitions.append(
                    {
                        "name": d.name,
                        "unit": d.unit,
                        "description": d.description,
                    }
                )
        result = {"primary_signal": signal, "related_signals": related, "definitions": definitions}
        self._log("get_related_signals", {"signal": signal}, result, "success", (time.time() - start) * 1000)
        return result

    def get_signal_definition(self, signal: str) -> dict:
        start = time.time()
        d = get_signal_definition(signal)
        if not d:
            result = {"error": f"Unknown signal: {signal}"}
            self._log("get_signal_definition", {"signal": signal}, result, "error", 0)
            return result
        result = {
            "name": d.name,
            "unit": d.unit,
            "min_value": d.min_value,
            "max_value": d.max_value,
            "description": d.description,
            "expected_behavior": d.expected_behavior,
            "related_signals": d.related_signals,
        }
        self._log("get_signal_definition", {"signal": signal}, result, "success", (time.time() - start) * 1000)
        return result

    def get_requirement_context(self, signal: str) -> dict:
        start = time.time()
        reqs = get_requirements_for_signal(signal)
        result = {
            "signal": signal,
            "requirements": [r.model_dump() for r in reqs],
        }
        self._log("get_requirement_context", {"signal": signal}, result, "success", (time.time() - start) * 1000)
        return result

    def get_test_history(self, requirement_id: str | None = None) -> dict:
        start = time.time()
        if requirement_id:
            tests = get_tests_for_requirement(requirement_id)
        else:
            tests = TESTS
        result = {"tests": [t.model_dump() for t in tests]}
        self._log("get_test_history", {"requirement_id": requirement_id}, result, "success", (time.time() - start) * 1000)
        return result

    def compare_with_baseline(
        self, scenario_id: str, signal: str, center_time: float
    ) -> dict:
        start = time.time()
        df = self.scenario_service.get_scenario_df(scenario_id)
        from app.database.models import ScenarioDB

        scenario = self.db.query(ScenarioDB).filter_by(id=scenario_id).first()

        # Generate normal baseline with same type
        from app.core.signal_registry import ScenarioType
        from app.simulator.generate import ScenarioGenerator

        stype = ScenarioType(scenario.scenario_type) if scenario else ScenarioType.NORMAL_DRIVING
        baseline_gen = ScenarioGenerator(seed=42)
        baseline_df, _ = baseline_gen.generate(
            scenario_id=f"BASELINE-{scenario_id}",
            scenario_type=stype,
        )
        window = self.analyzer.get_window(df, center_time)
        base_window = self.analyzer.get_window(baseline_df, center_time)
        result = self.analyzer.compare_with_baseline(window, base_window, signal)
        self._log("compare_with_baseline", {"scenario_id": scenario_id, "signal": signal}, result, "success", (time.time() - start) * 1000)
        return result

    def generate_followup_test(self, anomaly_id: str) -> dict:
        start = time.time()
        a = self.db.query(AnomalyDB).filter(AnomalyDB.id == anomaly_id).first()
        if not a:
            result = {"error": "Anomaly not found"}
            self._log("generate_followup_test", {"anomaly_id": anomaly_id}, result, "error", 0)
            return result

        suggestions = []
        if a.signal == "battery_temperature" or "temperature" in a.anomaly_type.lower():
            suggestions.append(
                {
                    "test_name": "Repeat high-load scenario with cooling monitoring",
                    "reason": "Determine if anomaly correlates with insufficient cooling response",
                    "scenario_type": "high_load",
                }
            )
        if a.anomaly_type == "RELATIONSHIP_VIOLATION":
            suggestions.append(
                {
                    "test_name": "Signal correlation validation under controlled load steps",
                    "reason": "Verify sensor consistency between current and temperature",
                    "scenario_type": "acceleration",
                }
            )
        if a.anomaly_type == "MISSING_SIGNAL":
            suggestions.append(
                {
                    "test_name": "Communication integrity test",
                    "reason": "Investigate signal dropout on CAN/Ethernet interface",
                    "scenario_type": "normal_driving",
                }
            )
        if not suggestions:
            suggestions.append(
                {
                    "test_name": f"Reproduce scenario {a.scenario_id} with extended logging",
                    "reason": f"Investigate {a.anomaly_type} on {a.signal}",
                    "scenario_type": "high_load",
                }
            )
        result = {"anomaly_id": anomaly_id, "suggestions": suggestions}
        self._log("generate_followup_test", {"anomaly_id": anomaly_id}, result, "success", (time.time() - start) * 1000)
        return result

    def collect_all_evidence(self, anomaly_id: str) -> dict:
        """Gather all evidence deterministically for mock/LLM investigation."""
        anomaly = self.get_anomaly(anomaly_id)
        if "error" in anomaly:
            return anomaly

        scenario_id = anomaly["scenario_id"]
        center = anomaly["start_time"]
        signal = anomaly["signal"]

        window = self.get_signal_window(scenario_id, center)
        related = self.get_related_signals(signal)
        stats_primary = self.get_signal_statistics(scenario_id, signal, center)
        requirements = self.get_requirement_context(signal)
        baseline = self.compare_with_baseline(scenario_id, signal, center)
        followup = self.generate_followup_test(anomaly_id)

        related_stats = {}
        for rs in related.get("related_signals", []):
            related_stats[rs] = self.get_signal_statistics(scenario_id, rs, center)

        return {
            "anomaly": anomaly,
            "window": window,
            "primary_statistics": stats_primary,
            "related_statistics": related_stats,
            "requirements": requirements,
            "baseline_comparison": baseline,
            "followup_suggestions": followup,
        }
