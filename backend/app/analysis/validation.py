"""Data quality validation layer."""

from __future__ import annotations

import pandas as pd

from app.core.signal_registry import SIGNAL_COLUMNS, SIGNAL_REGISTRY
from app.models.schemas import DataQualityIssue, DataQualityReport


class DataValidator:
    """Validate ingested signal data and record quality issues."""

    def validate(self, df: pd.DataFrame, scenario_id: str) -> tuple[pd.DataFrame, DataQualityReport]:
        issues: list[DataQualityIssue] = []
        records = len(df)

        # Missing timestamps
        missing_ts = int(df["timestamp"].isna().sum())
        if missing_ts:
            issues.append(
                DataQualityIssue(
                    issue_type="missing_timestamps",
                    count=missing_ts,
                    description=f"{missing_ts} rows with missing timestamps",
                )
            )

        # Duplicate timestamps
        dup_ts = int(df["timestamp"].duplicated().sum())
        if dup_ts:
            issues.append(
                DataQualityIssue(
                    issue_type="duplicate_timestamps",
                    count=dup_ts,
                    description=f"{dup_ts} duplicate timestamp entries",
                )
            )

        # Non-monotonic timestamps
        non_mono = bool((df["timestamp"].diff().dropna() < 0).any())
        if non_mono:
            issues.append(
                DataQualityIssue(
                    issue_type="non_monotonic_timestamps",
                    count=1,
                    description="Timestamps are not monotonically increasing",
                    severity="error",
                )
            )

        missing_values = 0
        invalid_values = 0
        out_of_range = 0

        for col in SIGNAL_COLUMNS:
            if col not in df.columns:
                issues.append(
                    DataQualityIssue(
                        issue_type="missing_signal",
                        signal=col,
                        count=records,
                        description=f"Signal column '{col}' is missing",
                        severity="error",
                    )
                )
                continue

            mv = int(df[col].isna().sum())
            missing_values += mv
            if mv:
                issues.append(
                    DataQualityIssue(
                        issue_type="missing_values",
                        signal=col,
                        count=mv,
                        description=f"{mv} missing values in {col}",
                    )
                )

            sig_def = SIGNAL_REGISTRY[col]
            valid = df[col].dropna()
            if len(valid):
                oor = int(
                    ((valid < sig_def.min_value) | (valid > sig_def.max_value)).sum()
                )
                out_of_range += oor
                if oor:
                    issues.append(
                        DataQualityIssue(
                            issue_type="out_of_range",
                            signal=col,
                            count=oor,
                            description=(
                                f"{oor} values outside [{sig_def.min_value}, {sig_def.max_value}]"
                            ),
                        )
                    )

        # Sort by timestamp
        df_clean = df.sort_values("timestamp").reset_index(drop=True)

        # Quality score: penalize issues proportionally
        penalty = (
            missing_values * 0.5
            + invalid_values
            + out_of_range * 2
            + dup_ts * 3
            + (10 if non_mono else 0)
        )
        max_penalty = max(records * len(SIGNAL_COLUMNS) * 0.1, 1)
        quality_score = max(0.0, min(100.0, 100.0 - (penalty / max_penalty) * 100))

        report = DataQualityReport(
            scenario_id=scenario_id,
            records_processed=records,
            missing_values=missing_values,
            invalid_values=invalid_values,
            duplicate_timestamps=dup_ts,
            out_of_range_values=out_of_range,
            non_monotonic=non_mono,
            issues=issues,
            quality_score=round(quality_score, 2),
        )
        return df_clean, report
