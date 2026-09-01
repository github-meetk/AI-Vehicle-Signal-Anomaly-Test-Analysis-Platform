"""Simplified but internally consistent battery/thermal signal physics."""

from __future__ import annotations

import numpy as np

from app.core.signal_registry import ScenarioType


class SignalPhysics:
    """Simulate correlated E/E signals for battery/thermal monitoring."""

    COOLING_ACTIVATION_TEMP = 55.0
    THERMAL_WARNING_TEMP = 80.0

    def __init__(self, rng: np.random.Generator):
        self.rng = rng

    def simulate_scenario(
        self,
        timestamps: np.ndarray,
        scenario_type: ScenarioType,
        ambient_temp: float,
        initial_soc: float,
    ) -> dict[str, np.ndarray]:
        n = len(timestamps)
        speed = self._speed_profile(timestamps, scenario_type)
        current = self._current_from_speed(speed, scenario_type)
        soc = self._soc_profile(timestamps, current, initial_soc, scenario_type)
        voltage = self._voltage_from_soc_current(soc, current)
        batt_temp = self._battery_temperature(timestamps, current, ambient_temp, scenario_type)
        coolant = self._coolant_temperature(timestamps, batt_temp, ambient_temp)
        thermal_warn = (batt_temp >= self.THERMAL_WARNING_TEMP).astype(float)

        # Add small sensor noise
        voltage = voltage + self.rng.normal(0, 0.05, n)
        current = current + self.rng.normal(0, 2.0, n)
        batt_temp = batt_temp + self.rng.normal(0, 0.3, n)

        return {
            "battery_voltage": np.clip(voltage, 10.0, 16.0),
            "battery_current": np.clip(current, -200.0, 250.0),
            "battery_temperature": np.clip(batt_temp, ambient_temp, 95.0),
            "coolant_temperature": np.clip(coolant, ambient_temp - 5, 90.0),
            "state_of_charge": np.clip(soc, 5.0, 100.0),
            "vehicle_speed": np.clip(speed, 0.0, 200.0),
            "ambient_temperature": np.full(n, ambient_temp) + self.rng.normal(0, 0.1, n),
            "thermal_warning": thermal_warn,
        }

    def _speed_profile(self, t: np.ndarray, stype: ScenarioType) -> np.ndarray:
        if stype == ScenarioType.IDLE:
            return np.zeros_like(t) + self.rng.normal(0, 0.5, len(t))
        if stype == ScenarioType.ACCELERATION:
            return np.minimum(120.0, t * 2.5) + self.rng.normal(0, 1, len(t))
        if stype == ScenarioType.DECELERATION:
            return np.maximum(0.0, 100.0 - t * 1.5) + self.rng.normal(0, 1, len(t))
        if stype == ScenarioType.HIGH_LOAD:
            base = 80.0 + 20.0 * np.sin(t / 30.0)
            return np.clip(base + self.rng.normal(0, 2, len(t)), 0, 150)
        if stype == ScenarioType.CHARGING:
            return np.zeros_like(t)
        if stype == ScenarioType.COOLING_CYCLE:
            return 40.0 + 10.0 * np.sin(t / 50.0)
        # normal driving
        return 50.0 + 15.0 * np.sin(t / 40.0) + self.rng.normal(0, 2, len(t))

    def _current_from_speed(self, speed: np.ndarray, stype: ScenarioType) -> np.ndarray:
        if stype == ScenarioType.CHARGING:
            return -80.0 - 20.0 * np.sin(np.arange(len(speed)) / 20.0)
        base = speed * 1.2 + 15.0
        if stype == ScenarioType.HIGH_LOAD:
            base = base + 60.0
        if stype == ScenarioType.IDLE:
            base = 5.0 + self.rng.normal(0, 1, len(speed))
        return base

    def _soc_profile(
        self, t: np.ndarray, current: np.ndarray, initial_soc: float, stype: ScenarioType
    ) -> np.ndarray:
        dt = np.diff(t, prepend=t[0])
        # Rough SOC model: 1A for 1s ≈ 0.001% change (simplified)
        delta = -current * dt * 0.002
        soc = initial_soc + np.cumsum(delta)
        return soc

    def _voltage_from_soc_current(self, soc: np.ndarray, current: np.ndarray) -> np.ndarray:
        return 12.6 + (soc - 50) * 0.02 - current * 0.005

    def _battery_temperature(
        self,
        t: np.ndarray,
        current: np.ndarray,
        ambient: float,
        stype: ScenarioType,
    ) -> np.ndarray:
        temp = np.zeros(len(t))
        temp[0] = ambient + 15.0
        for i in range(1, len(t)):
            heating = current[i] * 0.08
            cooling = max(0, (temp[i - 1] - self.COOLING_ACTIVATION_TEMP)) * 0.15
            ambient_influence = (ambient - temp[i - 1]) * 0.01
            temp[i] = temp[i - 1] + heating * 0.05 - cooling * 0.1 + ambient_influence
            temp[i] = max(ambient, temp[i])
        return temp

    def _coolant_temperature(
        self, t: np.ndarray, batt_temp: np.ndarray, ambient: float
    ) -> np.ndarray:
        coolant = np.zeros(len(t))
        coolant[0] = ambient + 5.0
        for i in range(1, len(t)):
            if batt_temp[i] > self.COOLING_ACTIVATION_TEMP:
                target = batt_temp[i] - 10.0
                coolant[i] = coolant[i - 1] + (target - coolant[i - 1]) * 0.2
            else:
                coolant[i] = coolant[i - 1] + (ambient + 5 - coolant[i - 1]) * 0.05
        return coolant
