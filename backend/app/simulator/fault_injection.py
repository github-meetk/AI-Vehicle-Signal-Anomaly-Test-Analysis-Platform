"""Controlled fault injection for reproducible anomaly scenarios."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.signal_registry import FaultType, Severity


class FaultInjector:
    """Inject deterministic faults into synthetic signal traces."""

    def inject(
        self,
        df: pd.DataFrame,
        fault_type: FaultType,
        injection_time: float,
        affected_signal: str,
    ) -> pd.DataFrame:
        df = df.copy()
        mask = df["timestamp"] >= injection_time

        if fault_type == FaultType.BATTERY_VOLTAGE_DROP:
            df.loc[mask, "battery_voltage"] = df.loc[mask, "battery_voltage"] - 4.0

        elif fault_type == FaultType.CURRENT_SPIKE:
            spike_mask = (df["timestamp"] >= injection_time) & (
                df["timestamp"] <= injection_time + 15
            )
            df.loc[spike_mask, "battery_current"] = df.loc[spike_mask, "battery_current"] + 120.0

        elif fault_type == FaultType.TEMPERATURE_SPIKE:
            spike_mask = (df["timestamp"] >= injection_time) & (
                df["timestamp"] <= injection_time + 20
            )
            df.loc[spike_mask, "battery_temperature"] = (
                df.loc[spike_mask, "battery_temperature"] + 25.0
            )

        elif fault_type == FaultType.TEMPERATURE_SENSOR_DRIFT:
            drift = np.linspace(0, 15, mask.sum())
            df.loc[mask, "battery_temperature"] = df.loc[mask, "battery_temperature"].values + drift

        elif fault_type == FaultType.STUCK_SENSOR:
            stuck_val = df.loc[df["timestamp"] < injection_time, affected_signal].iloc[-1]
            df.loc[mask, affected_signal] = stuck_val

        elif fault_type == FaultType.MISSING_SIGNAL:
            df.loc[mask, affected_signal] = np.nan

        elif fault_type == FaultType.COOLING_FAILURE:
            # Battery temp rises; coolant does not respond
            df.loc[mask, "coolant_temperature"] = df.loc[mask, "coolant_temperature"].iloc[0]
            rise = np.linspace(0, 30, mask.sum())
            df.loc[mask, "battery_temperature"] = (
                df.loc[mask, "battery_temperature"].values + rise
            )
            df.loc[mask, "thermal_warning"] = 1.0

        elif fault_type == FaultType.IMPOSSIBLE_SIGNAL_COMBINATION:
            # High current but temperature drops (physically inconsistent)
            df.loc[mask, "battery_current"] = 200.0
            df.loc[mask, "battery_temperature"] = (
                df.loc[mask, "battery_temperature"] - 20.0
            ).clip(lower=0)

        elif fault_type == FaultType.THERMAL_THRESHOLD_VIOLATION:
            df.loc[mask, "battery_temperature"] = 85.0 + np.linspace(0, 10, mask.sum())
            df.loc[mask, "thermal_warning"] = 1.0

        return df

    @staticmethod
    def expected_severity(fault_type: FaultType) -> Severity:
        mapping = {
            FaultType.BATTERY_VOLTAGE_DROP: Severity.HIGH,
            FaultType.CURRENT_SPIKE: Severity.MEDIUM,
            FaultType.TEMPERATURE_SPIKE: Severity.HIGH,
            FaultType.TEMPERATURE_SENSOR_DRIFT: Severity.MEDIUM,
            FaultType.STUCK_SENSOR: Severity.MEDIUM,
            FaultType.MISSING_SIGNAL: Severity.HIGH,
            FaultType.COOLING_FAILURE: Severity.CRITICAL,
            FaultType.IMPOSSIBLE_SIGNAL_COMBINATION: Severity.HIGH,
            FaultType.THERMAL_THRESHOLD_VIOLATION: Severity.CRITICAL,
            FaultType.NONE: Severity.INFO,
        }
        return mapping.get(fault_type, Severity.MEDIUM)
