"""Business logic services."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.analysis.detector import AnomalyDetector
from app.analysis.signal_analyzer import SignalAnalyzer
from app.analysis.validation import DataValidator
from app.core.signal_registry import SIGNAL_REGISTRY, FaultType, ScenarioType
from app.database.models import (
    AnomalyDB,
    AuditLogDB,
    ScenarioDB,
    SignalDefinitionDB,
    SignalObservationDB,
)
from app.models.schemas import AnomalyEventSchema, DashboardSummary, ScenarioMetadata
from app.services.requirements import REQUIREMENTS, TESTS
from app.simulator.generate import ScenarioGenerator


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db
        self.validator = DataValidator()
        self.detector = AnomalyDetector()

    def seed_signal_definitions(self):
        if self.db.query(SignalDefinitionDB).count() > 0:
            return
        for name, sig in SIGNAL_REGISTRY.items():
            self.db.add(
                SignalDefinitionDB(
                    name=name,
                    unit=sig.unit,
                    min_value=sig.min_value,
                    max_value=sig.max_value,
                    description=sig.description,
                    expected_behavior=sig.expected_behavior,
                    related_signals=sig.related_signals,
                )
            )
        self.db.commit()

    def generate_scenario(
        self,
        scenario_type: ScenarioType = ScenarioType.HIGH_LOAD,
        fault_type: FaultType = FaultType.NONE,
        injection_time: float | None = None,
        seed: int | None = None,
        duration: float = 300.0,
    ) -> dict[str, Any]:
        scenario_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
        gen_seed = seed if seed is not None else hash(scenario_id) % 1_000_000
        gen = ScenarioGenerator(seed=gen_seed)

        df, meta = gen.generate(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            duration_seconds=duration,
            fault_type=fault_type,
            injection_time=injection_time,
        )

        df_clean, quality = self.validator.validate(df, scenario_id)

        # Store scenario
        scenario_db = ScenarioDB(
            id=scenario_id,
            scenario_type=meta.scenario_type.value,
            random_seed=meta.random_seed,
            fault_type=meta.fault_type.value,
            injection_time=meta.injection_time,
            affected_signal=meta.affected_signal,
            expected_anomaly=meta.expected_anomaly,
            expected_severity=meta.expected_severity.value if meta.expected_severity else None,
            duration_seconds=meta.duration_seconds,
            sample_rate_hz=meta.sample_rate_hz,
            generator_version=meta.generator_version,
            quality_score=quality.quality_score,
        )
        self.db.add(scenario_db)

        # Store observations
        for _, row in df_clean.iterrows():
            self.db.add(
                SignalObservationDB(
                    scenario_id=scenario_id,
                    timestamp=float(row["timestamp"]),
                    battery_voltage=_safe_float(row.get("battery_voltage")),
                    battery_current=_safe_float(row.get("battery_current")),
                    battery_temperature=_safe_float(row.get("battery_temperature")),
                    coolant_temperature=_safe_float(row.get("coolant_temperature")),
                    state_of_charge=_safe_float(row.get("state_of_charge")),
                    vehicle_speed=_safe_float(row.get("vehicle_speed")),
                    ambient_temperature=_safe_float(row.get("ambient_temperature")),
                    thermal_warning=_safe_float(row.get("thermal_warning")),
                )
            )

        # Detect anomalies
        anomalies = self.detector.detect(df_clean, scenario_id)
        for a in anomalies:
            self._store_anomaly(a)

        self.db.add(
            AuditLogDB(
                entity_type="scenario",
                entity_id=scenario_id,
                action="generated",
                details={
                    "fault_type": meta.fault_type.value,
                    "anomalies_detected": len(anomalies),
                    "quality_score": quality.quality_score,
                },
            )
        )
        self.db.commit()

        return {
            "scenario": meta.model_dump(),
            "quality": quality.model_dump(),
            "anomalies_count": len(anomalies),
            "anomalies": [a.model_dump() for a in anomalies[:20]],
        }

    def _store_anomaly(self, event: AnomalyEventSchema):
        self.db.add(
            AnomalyDB(
                id=event.id or str(uuid.uuid4()),
                scenario_id=event.scenario_id,
                signal=event.signal,
                anomaly_type=event.anomaly_type.value,
                start_time=event.start_time,
                end_time=event.end_time,
                severity=event.severity.value,
                observed_value=event.observed_value,
                expected_range=event.expected_range,
                detection_method=event.detection_method.value,
                evidence=event.evidence,
                confidence=event.confidence,
            )
        )

    def get_scenario_df(self, scenario_id: str) -> pd.DataFrame:
        rows = (
            self.db.query(SignalObservationDB)
            .filter(SignalObservationDB.scenario_id == scenario_id)
            .order_by(SignalObservationDB.timestamp)
            .all()
        )
        if not rows:
            return pd.DataFrame()
        data = []
        for r in rows:
            data.append(
                {
                    "timestamp": r.timestamp,
                    "scenario_id": r.scenario_id,
                    "battery_voltage": r.battery_voltage,
                    "battery_current": r.battery_current,
                    "battery_temperature": r.battery_temperature,
                    "coolant_temperature": r.coolant_temperature,
                    "state_of_charge": r.state_of_charge,
                    "vehicle_speed": r.vehicle_speed,
                    "ambient_temperature": r.ambient_temperature,
                    "thermal_warning": r.thermal_warning,
                }
            )
        return pd.DataFrame(data)

    def list_scenarios(self) -> list[dict]:
        scenarios = self.db.query(ScenarioDB).order_by(ScenarioDB.created_at.desc()).all()
        return [
            {
                "id": s.id,
                "scenario_type": s.scenario_type,
                "fault_type": s.fault_type,
                "expected_anomaly": s.expected_anomaly,
                "quality_score": s.quality_score,
                "injection_time": s.injection_time,
            }
            for s in scenarios
        ]

    def get_dashboard_summary(self) -> DashboardSummary:
        scenarios = self.db.query(ScenarioDB).count()
        anomalies = self.db.query(AnomalyDB).count()
        high_crit = (
            self.db.query(AnomalyDB)
            .filter(AnomalyDB.severity.in_(["HIGH", "CRITICAL"]))
            .count()
        )
        signals = self.db.query(SignalObservationDB).count()

        # Load evaluation results if available
        precision = recall = None
        results_path = Path("evaluation/results/latest_metrics.json")
        if results_path.exists():
            with open(results_path) as f:
                metrics = json.load(f)
                combined = next(
                    (m for m in metrics if m.get("method") == "combined"), None
                )
                if combined:
                    precision = combined.get("precision")
                    recall = combined.get("recall")

        avg_quality = self.db.query(ScenarioDB).filter(
            ScenarioDB.quality_score.isnot(None)
        )
        quality_scores = [s.quality_score for s in avg_quality.all() if s.quality_score]
        dq_score = sum(quality_scores) / len(quality_scores) if quality_scores else None

        return DashboardSummary(
            signals_analyzed=signals,
            scenarios=scenarios,
            anomalies=anomalies,
            high_critical_anomalies=high_crit,
            detection_precision=precision,
            detection_recall=recall,
            data_quality_score=round(dq_score, 2) if dq_score else None,
        )


class AnomalyService:
    def __init__(self, db: Session):
        self.db = db
        self.analyzer = SignalAnalyzer()

    def list_anomalies(self, scenario_id: str | None = None) -> list[dict]:
        q = self.db.query(AnomalyDB)
        if scenario_id:
            q = q.filter(AnomalyDB.scenario_id == scenario_id)
        anomalies = q.order_by(AnomalyDB.start_time).all()
        return [self._to_dict(a) for a in anomalies]

    def get_anomaly(self, anomaly_id: str) -> dict | None:
        a = self.db.query(AnomalyDB).filter(AnomalyDB.id == anomaly_id).first()
        return self._to_dict(a) if a else None

    def get_anomaly_signals(
        self, anomaly_id: str, scenario_service: ScenarioService
    ) -> dict:
        a = self.db.query(AnomalyDB).filter(AnomalyDB.id == anomaly_id).first()
        if not a:
            return {"error": "Anomaly not found"}
        df = scenario_service.get_scenario_df(a.scenario_id)
        window = self.analyzer.get_window(df, a.start_time)
        related = self.analyzer.get_related_signals(a.signal)
        evidence = self.analyzer.extract_window_evidence(df, a.start_time, a.signal)
        return {
            "anomaly": self._to_dict(a),
            "window_data": window.to_dict(orient="records"),
            "related_signals": related,
            "evidence": evidence,
        }

    @staticmethod
    def _to_dict(a: AnomalyDB) -> dict:
        return {
            "id": a.id,
            "scenario_id": a.scenario_id,
            "signal": a.signal,
            "anomaly_type": a.anomaly_type,
            "start_time": a.start_time,
            "end_time": a.end_time,
            "severity": a.severity,
            "observed_value": a.observed_value,
            "expected_range": a.expected_range,
            "detection_method": a.detection_method,
            "evidence": a.evidence,
            "confidence": a.confidence,
        }


def _safe_float(val) -> float | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return float(val)
