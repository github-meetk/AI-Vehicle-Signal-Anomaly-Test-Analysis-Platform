"""Deterministic anomaly detection — rules, statistics, temporal, relationships."""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.signal_registry import (
    RELATIONSHIP_MAP,
    SIGNAL_COLUMNS,
    SIGNAL_REGISTRY,
    AnomalyType,
    DetectionMethod,
    Severity,
)
from app.models.schemas import AnomalyEventSchema


class AnomalyDetector:
    """Combined deterministic anomaly detector (source of truth)."""

    def __init__(
        self,
        z_threshold: float | None = None,
        temp_threshold: float | None = None,
        window_seconds: float | None = None,
        methods: set[str] | None = None,
    ):
        self.z_threshold = z_threshold or settings.z_score_threshold
        self.temp_threshold = temp_threshold or settings.battery_temp_threshold
        self.window_seconds = window_seconds or settings.anomaly_window_seconds
        # methods: "rule", "statistical", "temporal", "relationship", or "all"
        self.methods = methods or {"rule", "statistical", "temporal", "relationship"}

    def detect(self, df: pd.DataFrame, scenario_id: str) -> list[AnomalyEventSchema]:
        events: list[AnomalyEventSchema] = []
        if "rule" in self.methods:
            events.extend(self._rule_based(df, scenario_id))
        if "statistical" in self.methods:
            events.extend(self._statistical(df, scenario_id))
        if "temporal" in self.methods:
            events.extend(self._temporal(df, scenario_id))
        if "relationship" in self.methods:
            events.extend(self._relationship(df, scenario_id))
        return self._deduplicate(events)

    def _rule_based(self, df: pd.DataFrame, scenario_id: str) -> list[AnomalyEventSchema]:
        events = []
        # Battery temperature threshold
        mask = df["battery_temperature"] > self.temp_threshold
        for idx in df.index[mask]:
            row = df.loc[idx]
            events.append(
                self._make_event(
                    scenario_id=scenario_id,
                    signal="battery_temperature",
                    anomaly_type=AnomalyType.THRESHOLD_VIOLATION,
                    timestamp=float(row["timestamp"]),
                    observed=float(row["battery_temperature"]),
                    expected_max=self.temp_threshold,
                    method=DetectionMethod.RULE,
                    evidence={
                        "rule": f"battery_temperature > {self.temp_threshold}",
                        "observed_value": float(row["battery_temperature"]),
                        "threshold": self.temp_threshold,
                    },
                    severity=self._temp_severity(float(row["battery_temperature"])),
                )
            )

        # Thermal warning mismatch
        warn_mask = (df["thermal_warning"] == 1) & (df["battery_temperature"] < 70)
        for idx in df.index[warn_mask]:
            row = df.loc[idx]
            events.append(
                self._make_event(
                    scenario_id=scenario_id,
                    signal="thermal_warning",
                    anomaly_type=AnomalyType.THERMAL_WARNING,
                    timestamp=float(row["timestamp"]),
                    observed=float(row["thermal_warning"]),
                    expected_max=0.0,
                    method=DetectionMethod.RULE,
                    evidence={
                        "thermal_warning": 1,
                        "battery_temperature": float(row["battery_temperature"]),
                        "note": "Warning active below expected temperature",
                    },
                    severity=Severity.MEDIUM,
                )
            )

        # Out of range per signal registry
        for sig, sig_def in SIGNAL_REGISTRY.items():
            if sig not in df.columns:
                continue
            oor = (df[sig] < sig_def.min_value) | (df[sig] > sig_def.max_value)
            for idx in df.index[oor & df[sig].notna()]:
                row = df.loc[idx]
                events.append(
                    self._make_event(
                        scenario_id=scenario_id,
                        signal=sig,
                        anomaly_type=AnomalyType.THRESHOLD_VIOLATION,
                        timestamp=float(row["timestamp"]),
                        observed=float(row[sig]),
                        expected_max=sig_def.max_value,
                        method=DetectionMethod.RULE,
                        evidence={
                            "observed": float(row[sig]),
                            "min": sig_def.min_value,
                            "max": sig_def.max_value,
                        },
                        severity=Severity.HIGH,
                    )
                )
        return events

    def _statistical(self, df: pd.DataFrame, scenario_id: str) -> list[AnomalyEventSchema]:
        events = []
        window = max(5, int(self.window_seconds))

        for sig in ["battery_current", "battery_temperature", "battery_voltage"]:
            if sig not in df.columns:
                continue
            series = df[sig].astype(float)
            rolling_mean = series.rolling(window=window, min_periods=3).mean()
            rolling_std = series.rolling(window=window, min_periods=3).std().replace(0, 1e-6)
            z_scores = (series - rolling_mean) / rolling_std

            for idx in df.index[z_scores.abs() > self.z_threshold]:
                if pd.isna(z_scores[idx]):
                    continue
                row = df.loc[idx]
                events.append(
                    self._make_event(
                        scenario_id=scenario_id,
                        signal=sig,
                        anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                        timestamp=float(row["timestamp"]),
                        observed=float(row[sig]),
                        expected_max=float(rolling_mean[idx] + self.z_threshold * rolling_std[idx]),
                        method=DetectionMethod.STATISTICAL,
                        evidence={
                            "z_score": float(z_scores[idx]),
                            "rolling_mean": float(rolling_mean[idx]),
                            "rolling_std": float(rolling_std[idx]),
                            "threshold": self.z_threshold,
                        },
                        severity=Severity.MEDIUM if abs(z_scores[idx]) < 4 else Severity.HIGH,
                        confidence=min(0.95, 0.6 + abs(z_scores[idx]) * 0.05),
                    )
                )
        return events

    def _temporal(self, df: pd.DataFrame, scenario_id: str) -> list[AnomalyEventSchema]:
        events = []
        for sig in SIGNAL_COLUMNS:
            if sig not in df.columns:
                continue
            series = df[sig]
            # Missing signal
            for idx in df.index[series.isna()]:
                row = df.loc[idx]
                events.append(
                    self._make_event(
                        scenario_id=scenario_id,
                        signal=sig,
                        anomaly_type=AnomalyType.MISSING_SIGNAL,
                        timestamp=float(row["timestamp"]),
                        observed=0.0,
                        expected_max=0.0,
                        method=DetectionMethod.TEMPORAL,
                        evidence={"missing_signal": sig},
                        severity=Severity.HIGH,
                    )
                )

            # Rate of change spikes (significant signals only)
            if sig in ("battery_current", "battery_temperature", "battery_voltage") and series.notna().sum() > 3:
                roc = series.diff().abs()
                threshold = roc.quantile(0.995) if roc.notna().sum() > 20 else roc.max()
                if threshold and threshold > 0:
                    for idx in df.index[roc > threshold * 2.5]:
                        if pd.isna(roc[idx]):
                            continue
                        row = df.loc[idx]
                        events.append(
                            self._make_event(
                                scenario_id=scenario_id,
                                signal=sig,
                                anomaly_type=AnomalyType.RATE_OF_CHANGE,
                                timestamp=float(row["timestamp"]),
                                observed=float(row[sig]) if pd.notna(row[sig]) else 0.0,
                                expected_max=float(threshold),
                                method=DetectionMethod.TEMPORAL,
                                evidence={
                                    "rate_of_change": float(roc[idx]),
                                    "threshold": float(threshold * 1.5),
                                },
                                severity=Severity.MEDIUM,
                            )
                        )

            # Stuck sensor: only on key signals where drift is unexpected
            if sig in ("battery_temperature", "battery_current", "battery_voltage") and len(
                series.dropna()
            ) > 35:
                stuck_window = 40
                for i in range(stuck_window, len(series)):
                    window_vals = series.iloc[i - stuck_window : i]
                    if (
                        window_vals.notna().all()
                        and window_vals.std() < 1e-8
                        and i > stuck_window + 60  # skip initial stabilization
                    ):
                        row = df.iloc[i]
                        events.append(
                            self._make_event(
                                scenario_id=scenario_id,
                                signal=sig,
                                anomaly_type=AnomalyType.STUCK_VALUE,
                                timestamp=float(row["timestamp"]),
                                observed=float(row[sig]),
                                expected_max=float(window_vals.iloc[0]),
                                method=DetectionMethod.TEMPORAL,
                                evidence={
                                    "stuck_value": float(window_vals.iloc[0]),
                                    "duration_samples": stuck_window,
                                },
                                severity=Severity.MEDIUM,
                                confidence=0.75,
                            )
                        )
                        break  # one stuck event per signal
        return events

    def _relationship(self, df: pd.DataFrame, scenario_id: str) -> list[AnomalyEventSchema]:
        events = []
        if "battery_current" not in df.columns or "battery_temperature" not in df.columns:
            return events

        current_roc = df["battery_current"].diff()
        temp_roc = df["battery_temperature"].diff()

        # High current increase but no temperature response (stronger thresholds)
        mask = (
            (current_roc > 50)
            & (temp_roc.abs() < 0.05)
            & (df["battery_current"] > 100)
            & (df["battery_temperature"] > 40)
        )
        for idx in df.index[mask]:
            row = df.loc[idx]
            events.append(
                self._make_event(
                    scenario_id=scenario_id,
                    signal="battery_temperature",
                    anomaly_type=AnomalyType.RELATIONSHIP_VIOLATION,
                    timestamp=float(row["timestamp"]),
                    observed=float(row["battery_temperature"]),
                    expected_max=float(row["battery_temperature"]) + 5,
                    method=DetectionMethod.RELATIONSHIP,
                    evidence={
                        "battery_current": float(row["battery_current"]),
                        "current_increase": float(current_roc[idx]),
                        "temperature_change": float(temp_roc[idx]),
                        "related_signals": RELATIONSHIP_MAP.get("battery_temperature", []),
                    },
                    severity=Severity.HIGH,
                    confidence=0.8,
                )
            )

        # Impossible: high discharge current but temperature drops significantly
        impossible = (df["battery_current"] > 150) & (temp_roc < -2)
        for idx in df.index[impossible]:
            row = df.loc[idx]
            events.append(
                self._make_event(
                    scenario_id=scenario_id,
                    signal="battery_current",
                    anomaly_type=AnomalyType.IMPOSSIBLE_COMBINATION,
                    timestamp=float(row["timestamp"]),
                    observed=float(row["battery_current"]),
                    expected_max=200.0,
                    method=DetectionMethod.RELATIONSHIP,
                    evidence={
                        "battery_current": float(row["battery_current"]),
                        "battery_temperature_change": float(temp_roc[idx]),
                        "note": "High current with decreasing temperature",
                    },
                    severity=Severity.CRITICAL,
                    confidence=0.85,
                )
            )

        # Cooling failure: high batt temp rising, flat coolant (stricter)
        if "coolant_temperature" in df.columns:
            cool_roc = df["coolant_temperature"].diff().abs()
            batt_roc = df["battery_temperature"].diff()
            cooling_fail = (
                (df["battery_temperature"] > 70)
                & (cool_roc < 0.02)
                & (batt_roc > 1.0)
                & (df["battery_current"] > 60)
            )
            for idx in df.index[cooling_fail]:
                row = df.loc[idx]
                events.append(
                    self._make_event(
                        scenario_id=scenario_id,
                        signal="coolant_temperature",
                        anomaly_type=AnomalyType.RELATIONSHIP_VIOLATION,
                        timestamp=float(row["timestamp"]),
                        observed=float(row["coolant_temperature"]),
                        expected_max=float(row["battery_temperature"]) - 5,
                        method=DetectionMethod.RELATIONSHIP,
                        evidence={
                            "battery_temperature": float(row["battery_temperature"]),
                            "coolant_temperature": float(row["coolant_temperature"]),
                            "note": "Battery heating without coolant response",
                        },
                        severity=Severity.CRITICAL,
                        confidence=0.82,
                    )
                )
        return events

    def _make_event(
        self,
        scenario_id: str,
        signal: str,
        anomaly_type: AnomalyType,
        timestamp: float,
        observed: float,
        expected_max: float,
        method: DetectionMethod,
        evidence: dict[str, Any],
        severity: Severity,
        confidence: float = 0.7,
    ) -> AnomalyEventSchema:
        return AnomalyEventSchema(
            id=str(uuid.uuid4()),
            scenario_id=scenario_id,
            signal=signal,
            anomaly_type=anomaly_type,
            start_time=timestamp,
            end_time=timestamp,
            severity=severity,
            observed_value=observed,
            expected_range={"min": 0.0, "max": expected_max},
            detection_method=method,
            evidence=evidence,
            confidence=confidence,
        )

    @staticmethod
    def _temp_severity(temp: float) -> Severity:
        if temp >= 95:
            return Severity.CRITICAL
        if temp >= 88:
            return Severity.HIGH
        if temp >= 82:
            return Severity.MEDIUM
        return Severity.LOW

    @staticmethod
    def _deduplicate(events: list[AnomalyEventSchema]) -> list[AnomalyEventSchema]:
        seen: set[tuple] = set()
        unique = []
        for e in events:
            key = (e.scenario_id, e.signal, e.anomaly_type, round(e.start_time, 1))
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique


class ThresholdOnlyDetector(AnomalyDetector):
    def __init__(self):
        super().__init__(methods={"rule"})


class StatisticalOnlyDetector(AnomalyDetector):
    def __init__(self):
        super().__init__(methods={"statistical"}, z_threshold=2.5)
