from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class FaultType(str, Enum):
    NONE = "NONE"
    BATTERY_VOLTAGE_DROP = "BATTERY_VOLTAGE_DROP"
    CURRENT_SPIKE = "CURRENT_SPIKE"
    TEMPERATURE_SPIKE = "TEMPERATURE_SPIKE"
    TEMPERATURE_SENSOR_DRIFT = "TEMPERATURE_SENSOR_DRIFT"
    STUCK_SENSOR = "STUCK_SENSOR"
    MISSING_SIGNAL = "MISSING_SIGNAL"
    COOLING_FAILURE = "COOLING_FAILURE"
    IMPOSSIBLE_SIGNAL_COMBINATION = "IMPOSSIBLE_SIGNAL_COMBINATION"
    THERMAL_THRESHOLD_VIOLATION = "THERMAL_THRESHOLD_VIOLATION"


class ScenarioType(str, Enum):
    NORMAL_DRIVING = "normal_driving"
    ACCELERATION = "acceleration"
    DECELERATION = "deceleration"
    IDLE = "idle"
    HIGH_LOAD = "high_load"
    CHARGING = "charging"
    COOLING_CYCLE = "cooling_cycle"


class AnomalyType(str, Enum):
    THRESHOLD_VIOLATION = "THRESHOLD_VIOLATION"
    STATISTICAL_OUTLIER = "STATISTICAL_OUTLIER"
    RATE_OF_CHANGE = "RATE_OF_CHANGE"
    STUCK_VALUE = "STUCK_VALUE"
    MISSING_SIGNAL = "MISSING_SIGNAL"
    RELATIONSHIP_VIOLATION = "RELATIONSHIP_VIOLATION"
    IMPOSSIBLE_COMBINATION = "IMPOSSIBLE_COMBINATION"
    THERMAL_WARNING = "THERMAL_WARNING"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectionMethod(str, Enum):
    RULE = "RULE"
    STATISTICAL = "STATISTICAL"
    TEMPORAL = "TEMPORAL"
    RELATIONSHIP = "RELATIONSHIP"


@dataclass
class SignalDefinition:
    name: str
    unit: str
    min_value: float
    max_value: float
    description: str
    expected_behavior: str
    related_signals: list[str] = field(default_factory=list)


SIGNAL_REGISTRY: dict[str, SignalDefinition] = {
    "battery_voltage": SignalDefinition(
        name="battery_voltage",
        unit="V",
        min_value=0.0,
        max_value=20.0,
        description="Battery terminal voltage",
        expected_behavior="Stable 12-14V during operation; drops under high load",
        related_signals=["battery_current", "state_of_charge", "battery_temperature"],
    ),
    "battery_current": SignalDefinition(
        name="battery_current",
        unit="A",
        min_value=-300.0,
        max_value=300.0,
        description="Battery current (positive=discharge, negative=charge)",
        expected_behavior="Increases with acceleration/load; negative during charging",
        related_signals=["battery_voltage", "battery_temperature", "vehicle_speed", "state_of_charge"],
    ),
    "battery_temperature": SignalDefinition(
        name="battery_temperature",
        unit="°C",
        min_value=-20.0,
        max_value=120.0,
        description="Battery pack temperature",
        expected_behavior="Rises with current; cooling stabilizes temperature below 80°C",
        related_signals=["battery_current", "coolant_temperature", "ambient_temperature", "vehicle_speed"],
    ),
    "coolant_temperature": SignalDefinition(
        name="coolant_temperature",
        unit="°C",
        min_value=-20.0,
        max_value=120.0,
        description="Coolant loop temperature",
        expected_behavior="Responds to battery temperature; activates cooling when hot",
        related_signals=["battery_temperature", "ambient_temperature"],
    ),
    "state_of_charge": SignalDefinition(
        name="state_of_charge",
        unit="%",
        min_value=0.0,
        max_value=100.0,
        description="Battery state of charge",
        expected_behavior="Decreases during discharge; increases during charging",
        related_signals=["battery_current", "battery_voltage"],
    ),
    "vehicle_speed": SignalDefinition(
        name="vehicle_speed",
        unit="km/h",
        min_value=0.0,
        max_value=250.0,
        description="Vehicle speed",
        expected_behavior="Correlates with current demand during driving",
        related_signals=["battery_current"],
    ),
    "ambient_temperature": SignalDefinition(
        name="ambient_temperature",
        unit="°C",
        min_value=-40.0,
        max_value=60.0,
        description="Ambient air temperature",
        expected_behavior="Slowly varying; influences thermal baseline",
        related_signals=["battery_temperature", "coolant_temperature"],
    ),
    "thermal_warning": SignalDefinition(
        name="thermal_warning",
        unit="bool",
        min_value=0.0,
        max_value=1.0,
        description="Thermal warning flag (0=off, 1=on)",
        expected_behavior="Activates when battery temperature exceeds threshold",
        related_signals=["battery_temperature"],
    ),
}

SIGNAL_COLUMNS = list(SIGNAL_REGISTRY.keys())

RELATIONSHIP_MAP: dict[str, list[str]] = {
    sig.name: sig.related_signals for sig in SIGNAL_REGISTRY.values()
}


def get_signal_definition(name: str) -> Optional[SignalDefinition]:
    return SIGNAL_REGISTRY.get(name)
