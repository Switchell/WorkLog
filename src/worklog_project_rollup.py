"""Разбиение поля Proect (CSV) и свёртка метрик по одиночным проектам + топ-N."""

from __future__ import annotations

import pandas as pd


def _split_proect_cell(cell: object) -> list[str]:
    names = [p.strip() for p in str(cell).split(",") if p.strip()]
    return names if names else ["(без проекта)"]


def explode_proect_share_amounts(
    df: pd.DataFrame,
    *,
    project_col: str = "Proect",
    amount_cols: tuple[str, ...],
) -> pd.DataFrame:
    """Строки с несколькими проектами в поле `{project_col}` делят указанные суммы поровну."""
    if df.empty:
        return df.copy()
    d = df.copy()
    d["_plist"] = d[project_col].map(_split_proect_cell)
    d["_n"] = d["_plist"].apply(len)
    d = d.explode("_plist").reset_index(drop=True)
    d[project_col] = d["_plist"]
    for c in amount_cols:
        if c not in d.columns:
            continue
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0) / d["_n"]
    d = d.drop(columns=["_plist", "_n"])
    return d


def rollup_project_metric(
    df: pd.DataFrame,
    value_col: str,
    *,
    project_col: str = "Proect",
    top_n: int = 25,
    other_label_tpl: str = "Прочее ({n} пр.)",
) -> pd.DataFrame:
    """Сумма по одиночным проектам после разбиения CSV; топ `top_n`, хвост — одна строка «Прочее»."""
    if df.empty or value_col not in df.columns:
        return pd.DataFrame(columns=[project_col, value_col])
    exploded = explode_proect_share_amounts(
        df,
        project_col=project_col,
        amount_cols=(value_col,),
    )
    g = exploded.groupby(project_col, as_index=False)[value_col].sum()
    g = g.sort_values(value_col, ascending=False, ignore_index=True)
    if top_n <= 0 or len(g) <= top_n:
        return g.sort_values(value_col, ascending=True, ignore_index=True)
    head = g.head(top_n)
    tail = g.iloc[top_n:]
    other_row = pd.DataFrame(
        {
            project_col: [other_label_tpl.format(n=len(tail))],
            value_col: [tail[value_col].sum()],
        }
    )
    out = pd.concat([head, other_row], ignore_index=True)
    return out.sort_values(value_col, ascending=True, ignore_index=True)
