"""Synthetic vehicle signal data generator with controlled fault injection.

The dataset is synthetic and designed to reproduce representative signal
relationships for an AI/validation PoC; it is not a physical battery model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.config import settings
from app.core.signal_registry import FaultType, ScenarioType
from app.models.schemas import ScenarioMetadata
from app.simulator.fault_injection import FaultInjector
from app.simulator.physics import SignalPhysics

GENERATOR_VERSION = settings.generator_version


class ScenarioGenerator:
    """Deterministic synthetic E/E battery/thermal signal generator."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.physics = SignalPhysics(self.rng)
        self.fault_injector = FaultInjector()

    def generate(
        self,
        scenario_id: str,
        scenario_type: ScenarioType = ScenarioType.NORMAL_DRIVING,
        duration_seconds: float = 300.0,
        sample_rate_hz: float = 1.0,
        fault_type: FaultType = FaultType.NONE,
        injection_time: float | None = None,
        affected_signal: str | None = None,
    ) -> tuple[pd.DataFrame, ScenarioMetadata]:
        n_samples = int(duration_seconds * sample_rate_hz)
        timestamps = np.arange(0, duration_seconds, 1.0 / sample_rate_hz)[:n_samples]

        ambient = 22.0 + self.rng.normal(0, 0.5)
        soc = 75.0 + self.rng.uniform(-5, 5)

        data = self.physics.simulate_scenario(
            timestamps=timestamps,
            scenario_type=scenario_type,
            ambient_temp=ambient,
            initial_soc=soc,
        )

        df = pd.DataFrame(data)
        df.insert(0, "timestamp", timestamps)
        df.insert(1, "scenario_id", scenario_id)

        meta = ScenarioMetadata(
            scenario_id=scenario_id,
            scenario_type=scenario_type,
            random_seed=self.seed,
            fault_type=fault_type,
            duration_seconds=duration_seconds,
            sample_rate_hz=sample_rate_hz,
            generator_version=GENERATOR_VERSION,
        )

        if fault_type != FaultType.NONE:
            inj_time = injection_time if injection_time is not None else duration_seconds * 0.4
            affected = affected_signal or self._default_affected_signal(fault_type)
            df = self.fault_injector.inject(
                df=df,
                fault_type=fault_type,
                injection_time=inj_time,
                affected_signal=affected,
            )
            meta.injection_time = inj_time
            meta.affected_signal = affected
            meta.expected_anomaly = True
            meta.expected_severity = self.fault_injector.expected_severity(fault_type)

        return df, meta

    @staticmethod
    def _default_affected_signal(fault_type: FaultType) -> str:
        mapping = {
            FaultType.BATTERY_VOLTAGE_DROP: "battery_voltage",
            FaultType.CURRENT_SPIKE: "battery_current",
            FaultType.TEMPERATURE_SPIKE: "battery_temperature",
            FaultType.TEMPERATURE_SENSOR_DRIFT: "battery_temperature",
            FaultType.STUCK_SENSOR: "battery_temperature",
            FaultType.MISSING_SIGNAL: "battery_current",
            FaultType.COOLING_FAILURE: "coolant_temperature",
            FaultType.IMPOSSIBLE_SIGNAL_COMBINATION: "battery_current",
            FaultType.THERMAL_THRESHOLD_VIOLATION: "battery_temperature",
        }
        return mapping.get(fault_type, "battery_temperature")


def generate_benchmark(
    n_scenarios: int = 150,
    seed: int = 42,
    output_dir: Path | None = None,
) -> tuple[list[ScenarioMetadata], pd.DataFrame]:
    output_dir = output_dir or Path("data/benchmark")
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    scenario_types = list(ScenarioType)
    fault_types = [FaultType.NONE] + [f for f in FaultType if f != FaultType.NONE]

    # ~30% fault scenarios
    fault_probs = [0.7] + [0.3 / (len(fault_types) - 1)] * (len(fault_types) - 1)

    all_meta: list[ScenarioMetadata] = []
    all_dfs: list[pd.DataFrame] = []
    ground_truth: list[dict] = []

    for i in range(n_scenarios):
        scenario_seed = int(rng.integers(0, 1_000_000))
        gen = ScenarioGenerator(seed=scenario_seed)
        scenario_id = f"SCN-{seed:04d}-{i:04d}"
        stype = scenario_types[i % len(scenario_types)]
        ftype = fault_types[rng.choice(len(fault_types), p=fault_probs)]

        df, meta = gen.generate(
            scenario_id=scenario_id,
            scenario_type=stype,
            duration_seconds=300.0,
            fault_type=ftype,
            injection_time=120.0 + rng.uniform(0, 60) if ftype != FaultType.NONE else None,
        )
        all_meta.append(meta)
        all_dfs.append(df)
        ground_truth.append(
            {
                "scenario_id": scenario_id,
                "fault_type": ftype.value,
                "affected_signal": meta.affected_signal,
                "injection_time": meta.injection_time,
                "expected_anomaly": meta.expected_anomaly,
                "severity": meta.expected_severity.value if meta.expected_severity else None,
                "random_seed": scenario_seed,
                "generator_version": GENERATOR_VERSION,
            }
        )

    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_parquet(output_dir / "benchmark_signals.parquet", index=False)
    combined.to_csv(output_dir / "benchmark_signals.csv", index=False)

    with open(output_dir / "ground_truth.json", "w") as f:
        json.dump(ground_truth, f, indent=2)

    meta_path = output_dir / "scenario_metadata.json"
    with open(meta_path, "w") as f:
        json.dump([m.model_dump() for m in all_meta], f, indent=2, default=str)

    return all_meta, combined


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic vehicle signal scenarios")
    parser.add_argument("--scenarios", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default="data/benchmark")
    args = parser.parse_args()

    meta, df = generate_benchmark(args.scenarios, args.seed, Path(args.output))
    print(f"Generated {len(meta)} scenarios, {len(df)} signal records -> {args.output}")


if __name__ == "__main__":
    main()
