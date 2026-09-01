from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.signal_registry import AnomalyType, DetectionMethod, FaultType, ScenarioType, Severity


class EvidenceItem(BaseModel):
    signal: str
    description: str
    value: Optional[float] = None
    timestamp: Optional[float] = None
    unit: Optional[str] = None


class AnomalyEventSchema(BaseModel):
    id: Optional[str] = None
    scenario_id: str
    signal: str
    anomaly_type: AnomalyType
    start_time: float
    end_time: Optional[float] = None
    severity: Severity
    observed_value: float
    expected_range: dict[str, float]
    detection_method: DetectionMethod
    evidence: dict[str, Any]
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class InvestigationResult(BaseModel):
    anomaly_id: str
    summary: str
    observations: list[str]
    supporting_evidence: list[EvidenceItem]
    possible_causes: list[str]
    related_requirements: list[str] = Field(default_factory=list)
    recommended_followup_tests: list[str]
    confidence: float = Field(ge=0.0, le=1.0)


class DataQualityIssue(BaseModel):
    issue_type: str
    signal: Optional[str] = None
    count: int = 0
    description: str
    severity: str = "warning"


class DataQualityReport(BaseModel):
    scenario_id: str
    records_processed: int
    missing_values: int
    invalid_values: int
    duplicate_timestamps: int
    out_of_range_values: int
    non_monotonic: bool = False
    issues: list[DataQualityIssue]
    quality_score: float = Field(ge=0.0, le=100.0)


class ScenarioMetadata(BaseModel):
    scenario_id: str
    scenario_type: ScenarioType
    random_seed: int
    fault_type: FaultType = FaultType.NONE
    injection_time: Optional[float] = None
    affected_signal: Optional[str] = None
    expected_anomaly: bool = False
    expected_severity: Optional[Severity] = None
    duration_seconds: float = 300.0
    sample_rate_hz: float = 1.0
    generator_version: str = "1.0.0"


class RequirementSchema(BaseModel):
    id: str
    title: str
    description: str
    related_signals: list[str]
    threshold: Optional[dict[str, Any]] = None


class TestSchema(BaseModel):
    id: str
    name: str
    description: str
    requirement_ids: list[str]
    scenario_type: str
    status: str = "defined"


class SignalDataPoint(BaseModel):
    timestamp: float
    scenario_id: str
    battery_voltage: Optional[float] = None
    battery_current: Optional[float] = None
    battery_temperature: Optional[float] = None
    coolant_temperature: Optional[float] = None
    state_of_charge: Optional[float] = None
    vehicle_speed: Optional[float] = None
    ambient_temperature: Optional[float] = None
    thermal_warning: Optional[float] = None


class DashboardSummary(BaseModel):
    signals_analyzed: int
    scenarios: int
    anomalies: int
    high_critical_anomalies: int
    false_positives: int = 0
    detection_precision: Optional[float] = None
    detection_recall: Optional[float] = None
    data_quality_score: Optional[float] = None


class EvaluationMetrics(BaseModel):
    method: str
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    avg_detection_latency: float
    fault_type_accuracy: Optional[float] = None


class AgentTraceStep(BaseModel):
    timestamp: datetime
    tool: str
    input: dict[str, Any]
    output_summary: str
    status: str
    latency_ms: float


class InvestigationTrace(BaseModel):
    investigation_id: str
    anomaly_id: str
    steps: list[AgentTraceStep]
    status: str
