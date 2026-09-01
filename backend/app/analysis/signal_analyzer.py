"""Time-window and related-signal analysis for anomaly investigation."""

from __future__ import annotations

import pandas as pd

from app.core.config import settings
from app.core.signal_registry import RELATIONSHIP_MAP, SIGNAL_REGISTRY


class SignalAnalyzer:
    """Analyze signals around anomaly events."""

    def __init__(self, window_seconds: float | None = None):
        self.window_seconds = window_seconds or settings.anomaly_window_seconds

    def get_window(
        self, df: pd.DataFrame, center_time: float, window: float | None = None
    ) -> pd.DataFrame:
        w = window or self.window_seconds
        mask = (df["timestamp"] >= center_time - w) & (df["timestamp"] <= center_time + w)
        return df.loc[mask].copy()

    def get_related_signals(self, signal: str) -> list[str]:
        return RELATIONSHIP_MAP.get(signal, [])

    def get_statistics(self, df: pd.DataFrame, signal: str) -> dict:
        if signal not in df.columns:
            return {"error": f"Signal {signal} not found"}
        series = df[signal].dropna()
        if series.empty:
            return {"error": "No data"}
        return {
            "signal": signal,
            "count": len(series),
            "mean": float(series.mean()),
            "std": float(series.std()) if len(series) > 1 else 0.0,
            "min": float(series.min()),
            "max": float(series.max()),
            "first": float(series.iloc[0]),
            "last": float(series.iloc[-1]),
            "unit": SIGNAL_REGISTRY[signal].unit if signal in SIGNAL_REGISTRY else "",
        }

    def compare_with_baseline(
        self, anomaly_df: pd.DataFrame, baseline_df: pd.DataFrame, signal: str
    ) -> dict:
        anom_stats = self.get_statistics(anomaly_df, signal)
        base_stats = self.get_statistics(baseline_df, signal)
        if "error" in anom_stats or "error" in base_stats:
            return {"signal": signal, "comparison": "insufficient data"}
        return {
            "signal": signal,
            "anomaly_mean": anom_stats["mean"],
            "baseline_mean": base_stats["mean"],
            "delta": anom_stats["mean"] - base_stats["mean"],
            "anomaly_max": anom_stats["max"],
            "baseline_max": base_stats["max"],
            "unit": anom_stats.get("unit", ""),
        }

    def extract_window_evidence(
        self, df: pd.DataFrame, center_time: float, primary_signal: str
    ) -> list[dict]:
        window_df = self.get_window(df, center_time)
        evidence = []
        signals = [primary_signal] + self.get_related_signals(primary_signal)
        for sig in signals:
            if sig not in window_df.columns:
                continue
            stats = self.get_statistics(window_df, sig)
            if "error" not in stats:
                evidence.append(
                    {
                        "signal": sig,
                        "statistics": stats,
                        "time_range": [
                            float(window_df["timestamp"].min()),
                            float(window_df["timestamp"].max()),
                        ],
                    }
                )
        return evidence
