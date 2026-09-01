"""SQLAlchemy database models."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


class ScenarioDB(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True)
    scenario_type = Column(String, nullable=False)
    random_seed = Column(Integer, nullable=False)
    fault_type = Column(String, default="NONE")
    injection_time = Column(Float, nullable=True)
    affected_signal = Column(String, nullable=True)
    expected_anomaly = Column(Boolean, default=False)
    expected_severity = Column(String, nullable=True)
    duration_seconds = Column(Float, default=300.0)
    sample_rate_hz = Column(Float, default=1.0)
    generator_version = Column(String, default="1.0.0")
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SignalObservationDB(Base):
    __tablename__ = "signal_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String, nullable=False, index=True)
    timestamp = Column(Float, nullable=False)
    battery_voltage = Column(Float, nullable=True)
    battery_current = Column(Float, nullable=True)
    battery_temperature = Column(Float, nullable=True)
    coolant_temperature = Column(Float, nullable=True)
    state_of_charge = Column(Float, nullable=True)
    vehicle_speed = Column(Float, nullable=True)
    ambient_temperature = Column(Float, nullable=True)
    thermal_warning = Column(Float, nullable=True)


class SignalDefinitionDB(Base):
    __tablename__ = "signal_definitions"

    name = Column(String, primary_key=True)
    unit = Column(String)
    min_value = Column(Float)
    max_value = Column(Float)
    description = Column(Text)
    expected_behavior = Column(Text)
    related_signals = Column(JSON)


class AnomalyDB(Base):
    __tablename__ = "anomalies"

    id = Column(String, primary_key=True)
    scenario_id = Column(String, nullable=False, index=True)
    signal = Column(String, nullable=False)
    anomaly_type = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=True)
    severity = Column(String, nullable=False)
    observed_value = Column(Float)
    expected_range = Column(JSON)
    detection_method = Column(String)
    evidence = Column(JSON)
    confidence = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class RequirementDB(Base):
    __tablename__ = "requirements"

    id = Column(String, primary_key=True)
    title = Column(String)
    description = Column(Text)
    related_signals = Column(JSON)
    threshold = Column(JSON, nullable=True)


class TestDB(Base):
    __tablename__ = "tests"

    id = Column(String, primary_key=True)
    name = Column(String)
    description = Column(Text)
    requirement_ids = Column(JSON)
    scenario_type = Column(String)
    status = Column(String, default="defined")


class InvestigationDB(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True)
    anomaly_id = Column(String, nullable=False, index=True)
    summary = Column(Text)
    observations = Column(JSON)
    supporting_evidence = Column(JSON)
    possible_causes = Column(JSON)
    related_requirements = Column(JSON)
    recommended_followup_tests = Column(JSON)
    confidence = Column(Float)
    status = Column(String, default="completed")
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentRunDB(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True)
    investigation_id = Column(String, nullable=False)
    anomaly_id = Column(String, nullable=False)
    trace = Column(JSON)
    status = Column(String)
    latency_ms = Column(Float)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String)
    entity_id = Column(String)
    action = Column(String)
    details = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
