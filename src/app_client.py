import streamlit as st
import pandas as pd
import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import plotly.express as px

load_dotenv(override=True)

st.set_page_config(page_title="AXIS Client Portal", layout="wide", page_icon="👁️")

url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(url)

CLIENT_PASSWORDS = {
    "client_kwork": "kwork123",
    "client_freelance": "free456",
}

def get_logs_for_client(project_filter: str = "Все") -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text('SELECT * FROM work_logs ORDER BY "Date" DESC'), conn)
            if not df.empty:
                df['Date'] = pd.to_datetime(df['Date']).dt.date
            return df
    except:
        return pd.DataFrame()

def get_rates_for_client() -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text('SELECT * FROM employee_rates'), conn)
            return df
    except:
        return pd.DataFrame()

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
        if st.button("Войти", width='stretch'):
            if pwd in CLIENT_PASSWORDS.values():
                st.session_state.client_auth = True
                st.session_state.client_name = [k for k, v in CLIENT_PASSWORDS.items() if v == pwd][0].replace("client_", "").upper()
                st.rerun()
            else:
                st.error("❌ Неверный пароль")
    st.stop()

st.sidebar.header(f"👤 Клиент: {st.session_state.client_name}")
st.sidebar.success("Режим просмотра")
if st.sidebar.button("Выйти"):
    st.session_state.client_auth = False
    st.rerun()

st.header(f"📊 Dashboard — {st.session_state.client_name}")

rates_df = get_rates_for_client()
logs_df = get_logs_for_client()

if logs_df.empty:
    st.info("Нет данных для отображения")
else:
    all_projects = ["Все"] + sorted(set(p for proects in logs_df['Proect'].dropna() for p in proects.split(', ')))
    
    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        selected_project = st.selectbox("Проект", all_projects)
    
    if selected_project != "Все":
        filtered_df = logs_df[logs_df['Proect'].str.contains(selected_project, na=False)].copy()
    else:
        filtered_df = logs_df.copy()
    
    if not filtered_df.empty:
        filtered_df = filtered_df.merge(rates_df, on="Sotrudnik", how="left")
        filtered_df['Client_Rate'] = pd.to_numeric(filtered_df['Client_Rate'], errors='coerce').fillna(0)
        filtered_df['Revenue'] = filtered_df['Time'] * filtered_df['Client_Rate']
        
        total_hours = filtered_df['Time'].sum()
        total_revenue = filtered_df['Revenue'].sum()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Всего часов", f"{total_hours:.1f}")
        m2.metric("Выручка", f"{int(total_revenue):,} р.")
        m3.metric("Записей", len(filtered_df))
        
        st.divider()
        
        c1, c2 = st.columns(2)
        with c1:
            monthly = filtered_df.copy()
            monthly['Date'] = pd.to_datetime(monthly['Date'])
            monthly['Месяц'] = monthly['Date'].dt.to_period('M').astype(str)
            monthly_h = monthly.groupby('Месяц')['Time'].sum().reset_index()
            fig_h = px.bar(monthly_h, x='Месяц', y='Time', title="Часы по месяцам")
            st.plotly_chart(fig_h)
        
        with c2:
            proj_stats = filtered_df.groupby('Proect')['Revenue'].sum().reset_index()
            fig_r = px.pie(proj_stats, values='Revenue', names='Proect', title="Выручка по проектам")
            st.plotly_chart(fig_r)
        
        st.divider()
        st.subheader("📋 Детализация")
        filtered_df['Date'] = pd.to_datetime(filtered_df['Date']).dt.strftime('%Y-%m-%d')
        st.dataframe(
            filtered_df[['Date', 'Sotrudnik', 'Proect', 'Time', 'Revenue']].rename(columns={
                'Date': 'Дата', 'Sotrudnik': 'Сотрудник', 'Proect': 'Проект', 'Time': 'Часы', 'Revenue': 'Выручка'
            }),
            width='stretch'
        )
    else:
        st.info("Нет данных по выбранному проекту")
