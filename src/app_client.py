import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import text

from worklog_charts import bar_height_horizontal, theme_figure

try:
    from worklog_charts import (
        bar_height_wrapped,
        project_label_for_axis,
        show_plotly_chart,
    )
except ImportError:
    from worklog_charts_fallbacks import (
        bar_height_wrapped,
        project_label_for_axis,
        show_plotly_chart,
    )
try:
    from worklog_finance import rollup_project_metric
except ImportError:
    from worklog_project_rollup import rollup_project_metric
from worklog_db import create_worklog_engine
from worklog_client_auth import get_client_passwords

load_dotenv(override=True)

st.set_page_config(page_title="AXIS Client Portal", layout="wide", page_icon="👁️")


@st.cache_resource
def _engine():
    return create_worklog_engine()


@st.cache_data(ttl=40, show_spinner=False)
def _load_logs_and_rates() -> tuple:
    eng = _engine()
    try:
        with eng.connect() as conn:
            logs_df = pd.read_sql(
                text('SELECT * FROM work_logs ORDER BY "Date" DESC'),
                conn,
            )
            rates_df = pd.read_sql(text("SELECT * FROM employee_rates"), conn)
        if not logs_df.empty:
            logs_df["Date"] = pd.to_datetime(logs_df["Date"]).dt.date
        return logs_df, rates_df
    except Exception:
        return pd.DataFrame(), pd.DataFrame()


CLIENT_PASSWORDS = get_client_passwords()
if CLIENT_PASSWORDS is None:
    st.error(
        "Задайте в .env оба пароля: **AXIS_CLIENT_KWORK_PASSWORD** и **AXIS_CLIENT_FREELANCE_PASSWORD**, "
        "либо временно включите dev-режим: **AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS=1** (см. .env.example)."
    )
    st.stop()

if "client_auth" not in st.session_state:
    st.session_state.client_auth = False
if "client_name" not in st.session_state:
    st.session_state.client_name = ""

if not st.session_state.client_auth:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.header("👁️ AXIS Client Portal")
        st.info("Введите пароль клиента")
        pwd = st.text_input("Пароль", type="password", key="client_pwd")
        if st.button("Войти", width="stretch"):
            matched = [k for k, v in CLIENT_PASSWORDS.items() if v == pwd]
            if matched:
                st.session_state.client_auth = True
                key = matched[0]
                st.session_state.client_name = key.replace("client_", "").upper()
                st.rerun()
            else:
                st.error("❌ Неверный пароль")
    st.stop()

st.sidebar.header(f"👤 Клиент: {st.session_state.client_name}")
st.sidebar.success("Режим просмотра")
if st.sidebar.button("Выйти"):
    st.session_state.client_auth = False
    st.rerun()

if st.sidebar.button("Обновить данные"):
    _load_logs_and_rates.clear()
    st.rerun()

st.header(f"📊 Dashboard — {st.session_state.client_name}")

logs_df, rates_df = _load_logs_and_rates()

if logs_df.empty:
    st.info("Нет данных для отображения")
else:
    all_projects = ["Все"] + sorted(
        set(
            p
            for proects in logs_df["Proect"].dropna()
            for p in str(proects).split(", ")
        )
    )

    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        selected_project = st.selectbox("Проект", all_projects)

    if selected_project != "Все":
        filtered_df = logs_df[logs_df["Proect"].str.contains(selected_project, na=False)].copy()
    else:
        filtered_df = logs_df.copy()

    if not filtered_df.empty:
        filtered_df = filtered_df.merge(rates_df, on="Sotrudnik", how="left")
        filtered_df["Client_Rate"] = pd.to_numeric(filtered_df["Client_Rate"], errors="coerce").fillna(0)
        filtered_df["Time"] = pd.to_numeric(filtered_df["Time"], errors="coerce").fillna(0)
        filtered_df["Revenue"] = filtered_df["Time"] * filtered_df["Client_Rate"]

        total_hours = filtered_df["Time"].sum()
        total_revenue = filtered_df["Revenue"].sum()

        m1, m2, m3 = st.columns(3, gap="large")
        m1.metric("Всего часов", f"{total_hours:.1f}")
        m2.metric("Выручка", f"{int(total_revenue):,} р.")
        m3.metric("Записей", len(filtered_df))

        st.divider()

        c1, c2 = st.columns(2, gap="medium")
        with c1:
            monthly = filtered_df.copy()
            monthly["Date"] = pd.to_datetime(monthly["Date"])
            monthly["Месяц"] = monthly["Date"].dt.to_period("M").astype(str)
            monthly_h = monthly.groupby("Месяц")["Time"].sum().reset_index().sort_values("Месяц")
            fig_h = px.bar(
                monthly_h,
                x="Месяц",
                y="Time",
                title="Часы по месяцам",
                labels={"Месяц": "", "Time": ""},
            )
            theme_figure(fig_h, chart="bar_v", height=max(320, min(420, 260 + len(monthly_h) * 14)))
            show_plotly_chart(fig_h)

        with c2:
            proj_stats = rollup_project_metric(filtered_df, "Revenue", top_n=25)
            proj_stats["_pro_label"] = proj_stats["Proect"].map(project_label_for_axis)
            disp = proj_stats["_pro_label"].tolist()
            fig_r = px.bar(
                proj_stats,
                x="Revenue",
                y="_pro_label",
                orientation="h",
                title="Выручка по проектам",
                labels={"Revenue": "", "_pro_label": ""},
            )
            theme_figure(
                fig_r,
                chart="bar_h",
                height=bar_height_wrapped(len(proj_stats), disp),
            )
            fig_r.update_traces(
                customdata=proj_stats["Proect"],
                hovertemplate="<b>%{customdata}</b><br>Выручка: %{x:,.0f} р.<extra></extra>",
            )
            show_plotly_chart(fig_r)

        st.divider()
        st.subheader("📋 Детализация")
        display_df = filtered_df.copy()
        display_df["Date"] = pd.to_datetime(display_df["Date"]).dt.strftime("%Y-%m-%d")
        st.dataframe(
            display_df[["Date", "Sotrudnik", "Proect", "Time", "Revenue"]].rename(
                columns={
                    "Date": "Дата",
                    "Sotrudnik": "Сотрудник",
                    "Proect": "Проект",
                    "Time": "Часы",
                    "Revenue": "Выручка",
                }
            ),
            width="stretch",
        )
    else:
        st.info("Нет данных по выбранному проекту")
