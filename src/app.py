import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

st.set_page_config(page_title="AXIS ERP PRO", layout="wide", page_icon="💎")

from worklog_auth import check_password

if not check_password():
    st.stop()

import os
import subprocess
import io
from datetime import datetime
from typing import Union

import pandas as pd
from sqlalchemy import text
import plotly.express as px

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
from worklog_db import create_worklog_engine
from worklog_logging import log_error, log_info
from worklog_finance import calculate_finances

try:
    from worklog_finance import rollup_project_metric
except ImportError:
    from worklog_project_rollup import rollup_project_metric
from worklog_pdf import create_pdf_report
from worklog_import_db import run_data_import, delete_record
from worklog_telegram_reports import send_telegram_summary

USER_ROLE = st.session_state.get("user_role", "user")
USER_NAME = st.session_state.get("user_name", "")

with st.sidebar:
    st.caption(f"👤 {USER_NAME} ({USER_ROLE})")
    if USER_ROLE == "admin":
        st.success("🛡️ Режим администратора")
    else:
        st.info("👤 Режим сотрудника")

    if st.button("🚪 Выйти из аккаунта", width='stretch'):
        st.session_state.authenticated = False
        st.session_state.pop("user_role", None)
        st.session_state.pop("user_name", None)
        st.rerun()
    st.divider()

# ==========================================================
# БЛОК: [CORE-DB-ENGINE] v2.6 (pool_pre_ping, настраиваемый пул)
# ==========================================================
@st.cache_resource
def init_connection():
    eng = create_worklog_engine()
    with eng.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS employee_rates (
                "Sotrudnik" TEXT PRIMARY KEY,
                "Rate" NUMERIC DEFAULT 0,
                "Client_Rate" NUMERIC DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS work_logs (
                "Date" DATE,
                "Sotrudnik" TEXT,
                "Proect" TEXT,
                "Time" NUMERIC,
                UNIQUE("Date", "Sotrudnik")
            );
            ALTER TABLE employee_rates ADD COLUMN IF NOT EXISTS "Client_Rate" NUMERIC DEFAULT 0;
        """))
        # Миграция: удаляем старый UNIQUE constraint если есть
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'work_logs_date_sotrudnik_proect_key'
                ) THEN
                    ALTER TABLE work_logs DROP CONSTRAINT work_logs_date_sotrudnik_proect_key;
                END IF;
            END $$;
        """))
    return eng


engine = init_connection()

# ==========================================================
# БЛОК: [CORE-AUTH-SYSTEM] v3.0
# ==========================================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "checked" not in st.session_state:
    st.session_state.checked = False
if 'db_version' not in st.session_state:
    st.session_state.db_version = 0
if 'backup_version' not in st.session_state:
    st.session_state.backup_version = 0

def bump_db_version():
    st.session_state.db_version += 1


def bump_backup_version():
    st.session_state.backup_version += 1


def refresh_table_cache() -> None:
    """Сброс кэша чтения таблиц без записи в БД и без увеличения db_version."""
    get_logs.clear()
    get_rates.clear()


def restore_db_from_sql_file(sql_path: str) -> tuple[bool, str]:
    """Восстанавливает БД из SQL-файла и возвращает (ok, stderr_or_empty)."""
    env = os.environ.copy()
    env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")

    result = subprocess.run(
        [
            'psql',
            '-h', os.getenv("DB_HOST", "db"),
            '-U', os.getenv("DB_USER", "user"),
            '-d', os.getenv("DB_NAME", "workday_db"),
            '-f', sql_path,
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stderr.strip()


@st.cache_data(ttl=15, show_spinner=False)
def get_backup_index(v_trigger: int, backup_dir: str) -> tuple[list[str], dict[str, float]]:
    """Возвращает список backup-файлов и их размеры в KB; кэш короткий для быстрой UI-отрисовки."""
    names: list[str] = []
    sizes_kb: dict[str, float] = {}
    try:
        for entry in os.scandir(backup_dir):
            if entry.is_file() and entry.name.endswith(".sql"):
                names.append(entry.name)
                sizes_kb[entry.name] = entry.stat().st_size / 1024
    except FileNotFoundError:
        return [], {}
    names.sort(reverse=True)
    return names, sizes_kb


@st.fragment
def render_danger_zone_tools():
    """Галочки и кнопки «Опасной зоны» перезапускают только этот блок, не всю аналитику."""
    st.subheader("🛑 Опасная зона")
    st.error("⚠️ ВНИМАНИЕ! Действия ниже необратимы!")
    st.caption(
        "Галочки только включают кнопки: в PostgreSQL ничего не записывается, пока вы не нажмёте соответствующую кнопку очистки."
    )
    c1, c2 = st.columns(2)
    with c1:
        st.info("Удаление всех рабочих часов")
        confirm_logs = st.checkbox("✅ Я понимаю, что удалю ВСЕ логи")
        if st.button("🧨 ОЧИСТИТЬ ВСЕ ЛОГИ", type="primary", width='stretch', disabled=not confirm_logs):
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE work_logs RESTART IDENTITY"))
            bump_db_version()
            st.success("Логи работы удалены")
            st.rerun()
    with c2:
        st.warning("Удаление справочника сотрудников и цен")
        confirm_rates = st.checkbox("✅ Я понимаю, что удалю справочник")
        if st.button("🗑️ ОБНУЛИТЬ СПРАВОЧНИК", width='stretch', disabled=not confirm_rates):
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM employee_rates"))
            bump_db_version()
            st.success("Справочник цен очищен")
            st.rerun()


@st.fragment
def render_restore_tools(backup_dir: str, existing_backups: list[str], backup_sizes_kb: dict[str, float]) -> None:
    """Блок восстановления перезапускает только себя при изменении галочек/селектов."""
    st.subheader("♻️ Восстановление из бэкапа")

    col_r1, col_r2 = st.columns(2)

    with col_r1:
        st.info("📤 Загрузить бэкап-файл (.sql)")
        uploaded_backup = st.file_uploader("Выберите файл", type=['sql'], key="restore_upload")

        if uploaded_backup:
            st.caption(f"Файл: {uploaded_backup.name} ({uploaded_backup.size / 1024:.1f} KB)")
            confirm_restore = st.checkbox("✅ Подтверждаю восстановление", key="confirm_restore_upload")

            if st.button(
                "♻️ ВОССТАНОВИТЬ",
                type="primary",
                width='stretch',
                disabled=not confirm_restore,
                key="restore_btn",
            ):
                with st.spinner("Восстановление..."):
                    temp_path = os.path.join(backup_dir, "temp_restore.sql")
                    try:
                        with open(temp_path, 'wb') as f:
                            f.write(uploaded_backup.getvalue())

                        ok, err = restore_db_from_sql_file(temp_path)

                        if ok:
                            bump_db_version()
                            st.success("✅ База данных восстановлена!")
                            log_info("Restore completed from uploaded file")
                            st.rerun()
                        else:
                            st.error(f"❌ Ошибка: {err}")
                    except Exception as e:
                        st.error(f"❌ Ошибка восстановления: {e}")
                        log_error(f"Restore failed: {e}")
                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)

    with col_r2:
        st.info("📁 Или выбрать из существующих")

        if existing_backups:
            selected_backup = st.selectbox("Бэкап:", existing_backups, key="restore_select")
            file_size = backup_sizes_kb.get(selected_backup, 0.0)
            st.caption(f"Размер: {file_size:.1f} KB")
            confirm_existing = st.checkbox("✅ Подтверждаю восстановление", key="confirm_existing")

            if st.button("♻️ ВОССТАНОВИТЬ", width='stretch', disabled=not confirm_existing, key="restore_existing_btn"):
                with st.spinner("Восстановление..."):
                    try:
                        filepath = os.path.join(backup_dir, selected_backup)
                        ok, err = restore_db_from_sql_file(filepath)

                        if ok:
                            bump_db_version()
                            st.success("✅ База данных восстановлена!")
                            log_info(f"Restore completed: {selected_backup}")
                            st.rerun()
                        else:
                            st.error(f"❌ Ошибка: {err}")
                    except Exception as e:
                        st.error(f"❌ Ошибка восстановления: {e}")
                        log_error(f"Restore failed: {e}")
        else:
            st.warning("Нет доступных бэкапов")

# ==========================================================
# БЛОК: [UI-NAVIGATION-TABS] v3.0 (С УЧЁТОМ РОЛЕЙ)
# ==========================================================
if USER_ROLE == "admin":
    nav_options = [
        "📊 Аналитика", 
        "📥 Загрузка данных", 
        "⚙️ Ставки и Люди",
        "🗄️ Управление данными",
        "🛠 Системные функции"
    ]
else:
    nav_options = ["📊 Мои данные", "📥 Загрузка данных"]

if "active_section" not in st.session_state or st.session_state.active_section not in nav_options:
    st.session_state.active_section = nav_options[0]

current_section = st.segmented_control(
    "Раздел",
    options=nav_options,
    selection_mode="single",
    key="active_section",
)

# ==========================================================
# БЛОК: [DATA-CORE-ENGINE] v6.1 (С КЭШИРОВАНИЕМ)
# ==========================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_logs(v_trigger: int, filter_user: Union[str, None] = None) -> pd.DataFrame:
    """filter_user: если задан — только строки сотрудника; None — вся таблица (только для админ-вкладок)."""
    try:
        with engine.connect() as conn:
            if filter_user:
                df = pd.read_sql(
                    text('SELECT * FROM work_logs WHERE "Sotrudnik" = :user ORDER BY "Date" DESC'),
                    conn,
                    params={"user": filter_user},
                )
            else:
                df = pd.read_sql(text('SELECT * FROM work_logs ORDER BY "Date" DESC'), conn)
            
            if not df.empty:
                df['Date'] = pd.to_datetime(df['Date']).dt.date
                df['Sotrudnik'] = df['Sotrudnik'].astype(str).str.strip()
            return df
    except Exception as e:
        log_error(f"get_logs: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_rates(v_trigger: int) -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            df = pd.read_sql(text('SELECT * FROM employee_rates'), conn)
            if not df.empty:
                df['Sotrudnik'] = df['Sotrudnik'].astype(str).str.strip()
            return df
    except Exception as e:
        log_error(f"get_rates: {str(e)}")
        return pd.DataFrame(columns=["Sotrudnik", "Rate", "Client_Rate"])

# ==========================================================
# БЛОК: [UI-TAB-IMPORT] v5.4
# ==========================================================
if current_section == "📥 Загрузка данных":
    st.header("📥 Загрузка данных (Excel)")
    
    uploaded_file = st.file_uploader("Выберите файл .xlsx", type="xlsx", key="excel_main_up")
    
    if uploaded_file:
        if "df_temp" not in st.session_state:
            try:
                st.session_state.df_temp = pd.read_excel(uploaded_file)
                st.session_state.ready_to_map = False
                st.toast("Файл прочитан успешно!", icon="📄")
            except Exception as e:
                st.error(f"Ошибка чтения: {e}")
                log_error(f"read_excel: {str(e)}")

        if st.button("🔍 ПРОАНАЛИЗИРОВАТЬ ФАЙЛ", width='stretch'):
            st.session_state.ready_to_map = True

        if st.session_state.get("ready_to_map"):
            df = st.session_state.df_temp
            st.divider()
            st.subheader("Настройка колонок")
            
            cols = list(df.columns)
            def_d = cols.index("Дата") if "Дата" in cols else 0
            def_f = cols.index("Сотрудник") if "Сотрудник" in cols else 1
            def_h = cols.index("Часы") if "Часы" in cols else 2

            c1, c2, c3, c4 = st.columns(4)
            d_c = c1.selectbox("Дата", cols, index=def_d)
            f_c = c2.selectbox("Сотрудник", cols, index=def_f)
            p_c = c3.selectbox("Проект", ["НЕТ"] + cols, index=0)
            h_c = c4.selectbox("Часы", cols, index=def_h)

            st.write("---")
            
            if st.button("🚀 ЗАПУСТИТЬ УМНЫЙ ИМПОРТ", type="primary", width='stretch'):
                with st.spinner("Обработка и синхронизация с БД..."):
                    count = run_data_import(
                        engine,
                        df,
                        d_c,
                        f_c,
                        p_c,
                        h_c,
                        user_role=USER_ROLE,
                        user_name=USER_NAME,
                        bump_db_version=bump_db_version,
                    )
                    
                    if count > 0:
                        import_df = df[[d_c, f_c, h_c]].rename(columns={d_c: 'Date', f_c: 'Sotrudnik', h_c: 'Time'})
                        import_df['Date'] = pd.to_datetime(import_df['Date'])
                        import_df['Time'] = pd.to_numeric(import_df['Time'], errors='coerce').fillna(0)
                        
                        send_telegram_summary(engine, import_df)
                        
                        if "df_temp" in st.session_state:
                            del st.session_state.df_temp
                        st.session_state.ready_to_map = False
                        
                        st.success(f"Импорт завершен! Добавлено/обновлено строк: {count}")
                        st.rerun()
                    else:
                        st.error("Данные не были загружены. Проверьте формат колонок.")

# ==========================================================
# БЛОК: [UI-MAIN-DASHBOARD] v5.9
# ==========================================================
if current_section in ("📊 Аналитика", "📊 Мои данные"):
    if USER_ROLE == "admin":
        st.header("📊 Сводная аналитика (Все сотрудники)")
    else:
        st.header(f"📊 Мои данные ({USER_NAME})")
    
    logs_df = get_logs(st.session_state.db_version, filter_user=USER_NAME if USER_ROLE != "admin" else None)
    rates_df = get_rates(st.session_state.db_version)
    
    if not logs_df.empty:
        f_data = calculate_finances(logs_df, rates_df)
        
        col_f1, col_f2, col_f3 = st.columns([1, 1, 1])
        with col_f1:
            start_d = st.date_input("С", f_data['Date'].min(), key="a_start")
        with col_f2:
            end_d = st.date_input("По", f_data['Date'].max(), key="a_end")
        with col_f3:
            st.write("---")
            if USER_ROLE == "admin" and st.button("📲 ОТЧЕТ В TELEGRAM", width='stretch'):
                send_telegram_summary(
                    engine,
                    f_data[
                        (f_data["Date"] >= pd.Timestamp(start_d))
                        & (f_data["Date"] <= pd.Timestamp(end_d))
                    ],
                )

        df_f = f_data.loc[(f_data['Date'] >= pd.Timestamp(start_d)) & (f_data['Date'] <= pd.Timestamp(end_d))]

        if not df_f.empty:
            st.subheader("Итоговые показатели")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Всего часов", f"{df_f['Time'].sum():,.1f}".replace(",", " "))
            m2.metric("Выручка", f"{int(df_f['Revenue'].sum()):,} р.".replace(",", " "))
            m3.metric("Затраты", f"{int(df_f['Cost'].sum()):,} р.".replace(",", " "))
            m4.metric("Прибыль", f"{int(df_f['Profit'].sum()):,} р.".replace(",", " "))

            st.divider()

            c1, c2 = st.columns(2, gap="medium")
            with c1:
                u_stats = df_f.groupby('Sotrudnik')['Time'].sum().sort_values(ascending=True).reset_index()
                fig_u = px.bar(
                    u_stats,
                    x="Time",
                    y="Sotrudnik",
                    orientation="h",
                    title="Часы по сотрудникам",
                    labels={"Sotrudnik": "", "Time": ""},
                )
                theme_figure(
                    fig_u,
                    chart="bar_h",
                    height=bar_height_horizontal(len(u_stats)),
                )
                show_plotly_chart(fig_u)

            with c2:
                p_stats = rollup_project_metric(df_f, "Profit", top_n=25)
                p_stats["_pro_label"] = p_stats["Proect"].map(project_label_for_axis)
                disp = p_stats["_pro_label"].tolist()
                fig_p = px.bar(
                    p_stats,
                    x="Profit",
                    y="_pro_label",
                    orientation="h",
                    title="Прибыль по проектам",
                    labels={"Profit": "", "_pro_label": ""},
                )
                theme_figure(
                    fig_p,
                    chart="bar_h",
                    height=bar_height_wrapped(len(p_stats), disp),
                )
                fig_p.update_traces(
                    customdata=p_stats["Proect"],
                    hovertemplate="<b>%{customdata}</b><br>Прибыль: %{x:,.0f} р.<extra></extra>",
                )
                show_plotly_chart(fig_p)

            pdf_data = create_pdf_report(df_f)
            _, col_pdf, _ = st.columns([1, 1, 1])
            with col_pdf:
                st.download_button(
                    label="📄 Скачать PDF-отчет",
                    data=pdf_data,
                    file_name="work_report.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
        else:
            st.warning("Нет данных за выбранный период.")
    else:
        st.info("Данные не найдены. Загрузите файл во вкладке 'Загрузка данных'.")

# ==========================================================
# БЛОК: [UI-TAB-RATES] v6.0 (УЛУЧШЕННЫЙ)
# ==========================================================
if USER_ROLE == "admin" and current_section == "⚙️ Ставки и Люди":
        st.header("⚙️ Настройка стоимости работ")
        
        current_logs = get_logs(st.session_state.db_version, filter_user=None)
        current_rates = get_rates(st.session_state.db_version)
        
        # Получаем всех сотрудников из логов
        if not current_logs.empty:
            all_workers = sorted(current_logs['Sotrudnik'].unique())
        else:
            all_workers = []
        
        # Находим тех, кого нет в справочнике
        if not current_rates.empty:
            known_workers = set(current_rates['Sotrudnik'].values)
        else:
            known_workers = set()
        
        missing_workers = [w for w in all_workers if w not in known_workers]
        
        # Блок новых сотрудников
        if missing_workers:
            st.warning(f"⚠️ Новые сотрудники ({len(missing_workers)}): {', '.join(missing_workers[:5])}{'...' if len(missing_workers) > 5 else ''}")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button(f"➕ Добавить всех ({len(missing_workers)})", width='stretch'):
                    new_rows = pd.DataFrame({"Sotrudnik": missing_workers, "Rate": 0, "Client_Rate": 0})
                    if not current_rates.empty:
                        updated_rates = pd.concat([current_rates, new_rows], ignore_index=True)
                    else:
                        updated_rates = new_rows
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM employee_rates"))
                        updated_rates.to_sql('employee_rates', conn, if_exists='append', index=False)
                    bump_db_version()
                    st.rerun()
            with col_btn2:
                if st.button("🔄 Обновить список", width='stretch'):
                    refresh_table_cache()
                    st.rerun()
        else:
            if all_workers:
                st.success(f"✅ Все сотрудники ({len(all_workers)}) в справочнике")
            else:
                st.info("📋 Загрузите данные во вкладке 'Загрузка данных', чтобы сотрудники появились здесь")

        st.divider()
        
        # ==================== ТАБЛИЦА СТАВОК ====================
        st.subheader("📋 Справочник цен")
        
        with st.form("rates_editor_form"):
            edited_df = st.data_editor(
                current_rates,
                num_rows="dynamic",
                width='stretch',
                key=f"editor_v{st.session_state.db_version}"
            )
            
            save_btn = st.form_submit_button("💾 СОХРАНИТЬ ИЗМЕНЕНИЯ", type="primary", width='stretch')
            
            if save_btn:
                if edited_df is not None:
                    valid_df = edited_df.dropna(subset=['Sotrudnik'])
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM employee_rates"))
                        valid_df.to_sql('employee_rates', conn, if_exists='append', index=False)
                    
                    bump_db_version()
                    st.success("Данные в базе успешно обновлены!")
                    st.rerun()
        
        st.divider()
        
        # ==================== ЭКСПОРТ И ИМПОРТ ====================
        col_imp, col_exp = st.columns(2)
        
        with col_exp:
            st.subheader("📤 Экспорт справочника")
            if not current_rates.empty:
                export_df = current_rates.copy()
                export_buffer = io.BytesIO()
                with pd.ExcelWriter(export_buffer, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Ставки')
                
                st.download_button(
                    label="📥 Скачать Excel",
                    data=export_buffer.getvalue(),
                    file_name="employee_rates.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch'
                )
        
        with col_imp:
            st.subheader("📥 Импорт ставок из Excel")
            
            st.write("**Формат:** Сотрудник | Rate | Client_Rate")
            
            rates_file = st.file_uploader(
                "Выберите файл",
                type=["xlsx", "xls"],
                key="rates_excel_up"
            )
            
            if rates_file:
                try:
                    rates_df = pd.read_excel(rates_file)
                    cols = list(rates_df.columns)
                    
                    col_s, col_r, col_cr = st.columns(3)
                    name_col = col_s.selectbox("Сотрудник", cols, index=0)
                    rate_col = col_r.selectbox("Rate", [c for c in cols if 'rate' in c.lower() or 'ставк' in c.lower()], index=0)
                    client_rate_col = col_cr.selectbox("Client", [c for c in cols if 'client' in c.lower() or 'клиент' in c.lower()], index=0 if len(cols) > 1 else 1)
                    
                    if st.button("Импортировать", type="primary", width='stretch'):
                        import_df = pd.DataFrame()
                        import_df['Sotrudnik'] = rates_df[name_col].astype(str).str.strip()
                        import_df['Rate'] = pd.to_numeric(rates_df[rate_col], errors='coerce').fillna(0)
                        import_df['Client_Rate'] = pd.to_numeric(rates_df[client_rate_col], errors='coerce').fillna(0)
                        import_df = import_df.dropna(subset=['Sotrudnik'])
                        
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM employee_rates"))
                            import_df.to_sql('employee_rates', conn, if_exists='append', index=False)
                        
                        bump_db_version()
                        st.success(f"✅ Импортировано {len(import_df)} ставок!")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Ошибка: {e}")
        
    # ==========================================================
    # БЛОК: [UI-TAB-DATA-MANAGEMENT] v2.0 (ПАГИНАЦИЯ)
    # ==========================================================
if USER_ROLE == "admin" and current_section == "🗄️ Управление данными":
        st.header("🗄️ Управление данными")
        st.caption("Просмотр и удаление записей из базы")
        
        logs_df = get_logs(st.session_state.db_version, filter_user=None)
        
        if not logs_df.empty:
            st.subheader("Фильтры")
            col_f1, col_f2, col_f3, col_exp = st.columns([1, 1, 1, 1])
            if not pd.api.types.is_datetime64_any_dtype(logs_df['Date']):
                logs_df['Date'] = pd.to_datetime(logs_df['Date'], errors='coerce')
            logs_df = logs_df.dropna(subset=['Date'])
            with col_f1:
                filter_worker = st.selectbox(
                    "Сотрудник", 
                    ["Все"] + sorted(logs_df['Sotrudnik'].unique().tolist()),
                    key="filter_worker"
                )
            with col_f2:
                filter_project = st.selectbox(
                    "Проект", 
                    ["Все"] + sorted(logs_df['Proect'].unique().tolist()),
                    key="filter_project"
                )
            with col_f3:
                min_date = logs_df['Date'].min().date()
                max_date = logs_df['Date'].max().date()
                start_date = st.date_input("С", min_date, key="filter_start")
                end_date = st.date_input("По", max_date, key="filter_end")
            
            filtered_df = logs_df.copy()
            if filter_worker != "Все":
                filtered_df = filtered_df[filtered_df['Sotrudnik'] == filter_worker]
            if filter_project != "Все":
                project_series = filtered_df['Proect'].fillna('').astype(str)
                filtered_df = filtered_df[project_series.str.contains(filter_project, na=False, case=False, regex=False)]
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            filtered_df = filtered_df[(filtered_df['Date'] >= start_ts) & (filtered_df['Date'] <= end_ts)]
            
            with col_exp:
                total_rows = len(filtered_df)
                st.write(f"📊 {total_rows} записей")
            
            st.divider()
            
            if total_rows > 0:
                export_df = filtered_df.copy()
                export_df['Date'] = pd.to_datetime(export_df['Date']).dt.strftime('%Y-%m-%d')
                export_buffer = io.BytesIO()
                with pd.ExcelWriter(export_buffer, engine='openpyxl') as writer:
                    export_df.to_excel(writer, index=False, sheet_name='Логи')
                export_buffer.seek(0)
                st.download_button(
                    label="📥 Экспорт в Excel",
                    data=export_buffer,
                    file_name="work_logs_export.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch'
                )
            
            display_df = filtered_df.copy()
            display_df['Date'] = pd.to_datetime(display_df['Date']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                display_df[['Date', 'Sotrudnik', 'Proect', 'Time']], 
                width='stretch'
            )
            
            st.divider()
            st.subheader("🗑️ Удаление записи")
            
            with st.form("delete_record_form"):
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    del_worker = st.selectbox("Сотрудник", sorted(logs_df['Sotrudnik'].unique()))
                with col_d2:
                    worker_logs = logs_df[logs_df['Sotrudnik'] == del_worker]
                    del_date = st.selectbox("Дата", worker_logs['Date'].unique())
                
                proects = worker_logs[worker_logs['Date'] == del_date]['Proect'].unique()
                del_proect = st.selectbox("Проект", proects if len(proects) > 0 else ["Без проекта"])
                
                hours = worker_logs[(worker_logs['Date'] == del_date) & (worker_logs['Proect'] == del_proect)]['Time'].values
                if len(hours) > 0:
                    st.info(f"Часов: {round(float(hours[0]), 1)}")
                
                st.warning("⚠️ ВНИМАНИЕ! Это действие необратимо!")
                
                delete_btn = st.form_submit_button("🗑️ УДАЛИТЬ ЗАПИСЬ", type="primary", width='stretch')
                
                if delete_btn:
                    if delete_record(
                        engine,
                        del_date,
                        del_worker,
                        del_proect,
                        bump_db_version,
                    ):
                        st.success("Запись удалена!")
                        st.rerun()
            
            st.divider()
            
            with st.expander("🔍 Быстрое удаление по сотруднику"):
                st.error("🛑 УДАЛИТЬ ВСЕ ЗАПИСИ СОТРУДНИКА?")
                del_all_worker = st.selectbox("Сотрудник", sorted(logs_df['Sotrudnik'].unique()), key="del_all_worker")
                st.warning(f"Будут удалены ВСЕ записи сотрудника: {del_all_worker}")
                
                if st.button(f"⚠️ ДА, УДАЛИТЬ ВСЁ ДЛЯ {del_all_worker}", type="primary"):
                    with engine.begin() as conn:
                        conn.execute(text('DELETE FROM work_logs WHERE "Sotrudnik" = :s'), {"s": del_all_worker})
                    bump_db_version()
                    st.success(f"Все записи {del_all_worker} удалены!")
                    st.rerun()
        else:
            st.info("База данных пуста.")

    # ==========================================================
    # БЛОК: [UI-SYSTEM-TOOLS] v5.4 (ТОЛЬКО АДМИН)
    # ==========================================================
if USER_ROLE == "admin" and current_section == "🛠 Системные функции":
        st.header("🛠 Сервисное обслуживание")
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.subheader("Оптимизация")
            if st.button("🕵️ УДАЛИТЬ ДУБЛИКАТЫ", width='stretch'):
                with engine.begin() as conn:
                    conn.execute(text("""
                        DELETE FROM work_logs a USING work_logs b 
                        WHERE a.ctid < b.ctid 
                        AND a."Date" = b."Date" 
                        AND a."Sotrudnik" = b."Sotrudnik" 
                        AND a."Proect" = b."Proect" 
                        AND a."Time" = b."Time";
                    """))
                bump_db_version()
                st.success("Дубликаты удалены")
                st.rerun()

        with col_right:
            st.subheader("Структура")
            if st.button("🔧 ПОЧИНИТЬ ТАБЛИЦЫ", width='stretch'):
                init_connection.clear()
                refresh_table_cache()
                init_connection()
                st.success("База проверена и исправна!")
                st.rerun()

        st.divider()
        
        st.subheader("💾 Резервное копирование")
        
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            if st.button("💾 СОЗДАТЬ БЭКАП", width='stretch'):
                with st.spinner("Создание бэкапа..."):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"axis_backup_{timestamp}.sql"
                    filepath = os.path.join(backup_dir, filename)
                    
                    env = os.environ.copy()
                    env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")
                    
                    try:
                        with open(filepath, 'w', encoding='utf-8') as f:
                            subprocess.run(
                                ['pg_dump', '-h', os.getenv("DB_HOST", "db"), '-U', 
                                 os.getenv("DB_USER", "user"), '-d', os.getenv("DB_NAME", "workday_db"), '--clean'],
                                env=env,
                                stdout=f,
                                check=True
                            )
                        bump_backup_version()
                        log_info(f"Бэкап создан: {filename}")
                        st.success(f"✅ Бэкап сохранён: {filename}")
                    except Exception as e:
                        st.error(f"❌ Ошибка бэкапа: {e}")
                        log_error(f"Backup failed: {e}")
        
        backup_names, backup_sizes_kb = get_backup_index(st.session_state.backup_version, backup_dir)

        with col_b2:
            st.write("Последние бэкапы:")
            backups = backup_names[:5]
            if backups:
                for b in backups:
                    st.caption(f"📄 {b}")
            else:
                st.caption("Нет бэкапов")

        st.divider()
        
        # ==================== ВОССТАНОВЛЕНИЕ ====================
        render_restore_tools(backup_dir, backup_names, backup_sizes_kb)
        
        st.divider()

        render_danger_zone_tools()