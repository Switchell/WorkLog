"""Расчёт выручки, затрат и прибыли по логам и ставкам."""
from __future__ import annotations

import pandas as pd

__all__ = (
    "calculate_finances",
    "explode_proect_share_amounts",
    "rollup_project_metric",
)


def __getattr__(name: str):
    if name == "explode_proect_share_amounts":
        from worklog_project_rollup import explode_proect_share_amounts

        return explode_proect_share_amounts
    if name == "rollup_project_metric":
        from worklog_project_rollup import rollup_project_metric

        return rollup_project_metric
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def calculate_finances(logs_df: pd.DataFrame, rates_df: pd.DataFrame) -> pd.DataFrame:
    if logs_df.empty:
        return pd.DataFrame()

    f_df = logs_df.copy()
    f_df["Sotrudnik"] = f_df["Sotrudnik"].astype(str).str.strip()

    f_df = f_df.merge(rates_df, on="Sotrudnik", how="left")

    f_df["Rate"] = pd.to_numeric(f_df["Rate"], errors="coerce").fillna(0)
    f_df["Client_Rate"] = pd.to_numeric(f_df["Client_Rate"], errors="coerce").fillna(0)
    f_df["Time"] = pd.to_numeric(f_df["Time"], errors="coerce").fillna(0)

    f_df["Revenue"] = f_df["Time"] * f_df["Client_Rate"]
    f_df["Cost"] = f_df["Time"] * f_df["Rate"]
    f_df["Profit"] = f_df["Revenue"] - f_df["Cost"]

    f_df["Date"] = pd.to_datetime(f_df["Date"])
    return f_df
