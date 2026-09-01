"""Synthetic requirement and test repository."""

from app.models.schemas import RequirementSchema, TestSchema

REQUIREMENTS: list[RequirementSchema] = [
    RequirementSchema(
        id="REQ-BAT-001",
        title="Battery Temperature Limit",
        description="Battery temperature shall remain below 80°C under defined operating conditions.",
        related_signals=["battery_temperature", "battery_current", "thermal_warning"],
        threshold={"max": 80.0, "unit": "°C"},
    ),
    RequirementSchema(
        id="REQ-BAT-002",
        title="Cooling System Response",
        description=(
            "Cooling response shall activate when battery temperature exceeds the configured threshold."
        ),
        related_signals=["coolant_temperature", "battery_temperature"],
        threshold={"activation": 55.0, "unit": "°C"},
    ),
    RequirementSchema(
        id="REQ-BAT-003",
        title="Voltage Stability",
        description="Battery voltage shall remain within 10-16V during normal operation.",
        related_signals=["battery_voltage", "battery_current", "state_of_charge"],
        threshold={"min": 10.0, "max": 16.0, "unit": "V"},
    ),
    RequirementSchema(
        id="REQ-BAT-004",
        title="Thermal Warning Activation",
        description="Thermal warning flag shall activate when battery temperature exceeds 80°C.",
        related_signals=["thermal_warning", "battery_temperature"],
        threshold={"activation": 80.0, "unit": "°C"},
    ),
    RequirementSchema(
        id="REQ-BAT-005",
        title="Signal Consistency",
        description=(
            "Battery current increases shall correlate with proportional battery temperature changes."
        ),
        related_signals=["battery_current", "battery_temperature"],
    ),
]

TESTS: list[TestSchema] = [
    TestSchema(
        id="TST-BAT-001",
        name="High-Load Thermal Test",
        description="Execute high-load driving scenario and verify battery temperature remains below 80°C.",
        requirement_ids=["REQ-BAT-001", "REQ-BAT-002"],
        scenario_type="high_load",
        status="defined",
    ),
    TestSchema(
        id="TST-BAT-002",
        name="Cooling Response Verification",
        description="Verify coolant temperature responds when battery temperature exceeds 55°C.",
        requirement_ids=["REQ-BAT-002"],
        scenario_type="cooling_cycle",
        status="defined",
    ),
    TestSchema(
        id="TST-BAT-003",
        name="Charging Thermal Test",
        description="Monitor thermal behavior during charging cycle.",
        requirement_ids=["REQ-BAT-001", "REQ-BAT-004"],
        scenario_type="charging",
        status="defined",
    ),
    TestSchema(
        id="TST-BAT-004",
        name="Voltage Stability Test",
        description="Verify battery voltage within limits during acceleration/deceleration.",
        requirement_ids=["REQ-BAT-003"],
        scenario_type="acceleration",
        status="defined",
    ),
    TestSchema(
        id="TST-BAT-005",
        name="Signal Correlation Test",
        description="Validate current-temperature correlation under varying load.",
        requirement_ids=["REQ-BAT-005"],
        scenario_type="normal_driving",
        status="defined",
    ),
]


def get_requirements_for_signal(signal: str) -> list[RequirementSchema]:
    return [r for r in REQUIREMENTS if signal in r.related_signals]


def get_tests_for_requirement(req_id: str) -> list[TestSchema]:
    return [t for t in TESTS if req_id in t.requirement_ids]
