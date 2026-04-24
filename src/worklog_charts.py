"""Единое оформление графиков Plotly для дашбордов WorkLog."""

from __future__ import annotations

import inspect
from typing import Literal

import plotly.graph_objects as go

FONT_STACK = "'Segoe UI', 'Inter', system-ui, sans-serif"

# Светлая тема
L_TITLE = dict(size=17, color="#0f172a", family=FONT_STACK)
L_GRID = "#e2e8f0"
L_PLOT_BG = "#f8fafc"
L_TEXT = "#475569"
L_TICK = "#64748b"
L_BAR = "#2563eb"
L_PIE_LINE = "#ffffff"

# Тёмная тема (рядом с фоном Streamlit dark)
D_TITLE = dict(size=17, color="#f1f5f9", family=FONT_STACK)
D_GRID = "rgba(148,163,184,0.22)"
D_PLOT_BG = "rgba(255,255,255,0.05)"
D_TEXT = "#cbd5e1"
D_TICK = "#94a3b8"
D_BAR = "#60a5fa"
D_PIE_LINE = "rgba(15,23,42,0.85)"

PLOTLY_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "worklog_chart"},
}


def _streamlit_ui_dark() -> bool:
    """Тёмная тема: из контекста страницы или .streamlit/config.toml."""
    try:
        import streamlit as st

        ctx = getattr(st, "context", None)
        if ctx is not None:
            theme = getattr(ctx, "theme", None)
            if theme is not None:
                return getattr(theme, "base", "light") == "dark"
    except Exception:
        pass
    try:
        from streamlit import config as st_config

        return st_config.get_option("theme.base") == "dark"
    except Exception:
        return False


def show_plotly_chart(fig: go.Figure) -> None:
    """Рендер Plotly: без встроенной панели Streamlit (сохраняем displayModeBar: false)."""
    import streamlit as st

    kwargs: dict = dict(use_container_width=True, config=PLOTLY_CONFIG)
    if "theme" in inspect.signature(st.plotly_chart).parameters:
        kwargs["theme"] = None
    st.plotly_chart(fig, **kwargs)


def project_label_for_axis(text: object, *, max_line: int = 22, max_lines: int = 4) -> str:
    """Подпись для оси проектов: перенос по запятым, обрезка длинных строк (часто CSV в поле Proect)."""
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


def bar_height_horizontal(n_rows: int) -> int:
    """Высота горизонтального bar (краткие подписи, напр. сотрудники)."""
    return max(300, min(620, 56 + int(n_rows) * 34))


def bar_height_wrapped(n_rows: int, display_labels: list[str]) -> int:
    """Высота при многострочных подписях по оси Y (проекты)."""
    if n_rows <= 0:
        return 300
    extra = max((s.count("<br>") for s in display_labels), default=0)
    row_h = 36 + extra * 20
    return max(300, min(960, 48 + int(n_rows) * row_h))


def theme_figure(
    fig: go.Figure,
    *,
    chart: Literal["bar_v", "bar_h", "pie"],
    height: int | None = None,
    dark: bool | None = None,
) -> go.Figure:
    if dark is None:
        dark = _streamlit_ui_dark()

    if dark:
        title_font = D_TITLE
        grid = D_GRID
        plot_bg = D_PLOT_BG
        text_c = D_TEXT
        tick_c = D_TICK
        bar_fill = D_BAR
        template = "plotly_dark"
        pie_line = D_PIE_LINE
    else:
        title_font = L_TITLE
        grid = L_GRID
        plot_bg = L_PLOT_BG
        text_c = L_TEXT
        tick_c = L_TICK
        bar_fill = L_BAR
        template = "plotly_white"
        pie_line = L_PIE_LINE

    margin = dict(l=4, r=8, t=48, b=8)
    if chart == "pie":
        margin = dict(l=4, r=8, t=48, b=64)

    fig.update_layout(
        template=template,
        font=dict(family=FONT_STACK, size=13, color=text_c),
        title=dict(font=title_font, x=0, xanchor="left", pad=dict(b=6)),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=plot_bg,
        margin=margin,
        xaxis_title=None,
        yaxis_title=None,
    )
    if height is not None:
        fig.update_layout(height=height)

    if chart == "pie":
        fig.update_layout(
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=11, family=FONT_STACK, color=tick_c),
                itemsizing="constant",
                itemwidth=28,
            ),
        )
        fig.update_traces(
            hole=0.5,
            textinfo="percent",
            textposition="inside",
            insidetextorientation="auto",
            textfont=dict(size=11, color="#f8fafc", family=FONT_STACK),
            marker=dict(line=dict(color=pie_line, width=1.5)),
        )
        fig.update_layout(margin=dict(l=4, r=200, t=48, b=48))
    else:
        fig.update_layout(showlegend=False, bargap=0.42)
        fig.update_xaxes(
            title_text="",
            automargin=True,
            tickfont=dict(size=12, color=tick_c),
        )
        fig.update_yaxes(
            title_text="",
            automargin=True,
            tickfont=dict(size=11, color=tick_c),
        )
        if chart == "bar_v":
            fig.update_xaxes(
                showgrid=False,
                showline=False,
                tickangle=0,
            )
            fig.update_yaxes(
                showgrid=True,
                gridcolor=grid,
                zeroline=False,
                showline=False,
            )
        else:
            fig.update_xaxes(
                showgrid=True,
                gridcolor=grid,
                zeroline=False,
                showline=False,
                tickangle=0,
                tickformat=",.0f",
                separatethousands=True,
            )
            fig.update_yaxes(
                showgrid=False,
                showline=False,
                autorange="reversed",
                side="left",
            )
        fig.update_traces(
            marker=dict(color=bar_fill, line=dict(width=0)),
            opacity=0.9,
        )

    return fig
