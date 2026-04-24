"""Резервные хелперы графиков, если в образе старый worklog_charts.py (частичный деплой)."""

from __future__ import annotations

import inspect

import plotly.graph_objects as go

PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "worklog_chart"},
}


def show_plotly_chart(fig: go.Figure) -> None:
    import streamlit as st

    kwargs: dict = dict(use_container_width=True, config=PLOTLY_CONFIG)
    if "theme" in inspect.signature(st.plotly_chart).parameters:
        kwargs["theme"] = None
    st.plotly_chart(fig, **kwargs)


def project_label_for_axis(text: object, *, max_line: int = 22, max_lines: int = 4) -> str:
    raw = " ".join(str(text).strip().split()) if text is not None else ""
    if not raw:
        return "—"
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        parts = [raw]
    lines: list[str] = []
    buf = parts[0]
    for p in parts[1:]:
        if len(buf) + 2 + len(p) <= max_line:
            buf = f"{buf}, {p}"
        else:
            if len(buf) > max_line:
                buf = buf[: max_line - 1] + "…"
            lines.append(buf)
            buf = p
            if len(lines) >= max_lines:
                lines.append("…")
                return "<br>".join(lines[:max_lines])
    if buf:
        if len(buf) > max_line:
            buf = buf[: max_line - 1] + "…"
        lines.append(buf)
    lines = lines[:max_lines]
    return "<br>".join(lines) if lines else "—"


def bar_height_wrapped(n_rows: int, display_labels: list) -> int:
    if n_rows <= 0:
        return 300
    extra = max((str(s).count("<br>") for s in display_labels), default=0)
    row_h = 36 + extra * 20
    return max(300, min(960, 48 + int(n_rows) * row_h))
