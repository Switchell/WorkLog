import streamlit as st
import pandas as pd
import os, time, telebot, subprocess, io
from datetime import datetime
from typing import Union, Tuple
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from fpdf import FPDF
import plotly.express as px
import bcrypt

load_dotenv(override=True)

# ==========================================================
# БЛОК: [LOGGING-SYSTEM] v1.0
# ==========================================================
LOG_FILE = os.getenv("LOG_FILE", "axis_errors.log")

def log_error(message: str) -> None:
    """Записывает ошибку в файл с timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] ERROR: {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass

def log_info(message: str) -> None:
    """Записывает информацию в файл"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] INFO: {message}\n"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass

st.set_page_config(page_title="AXIS ERP PRO", layout="wide", page_icon="💎")

# ==========================================================
# БЛОК: [SECURITY-LOCK] v6.0 (С ХЕШИРОВАНИЕМ)
# ==========================================================

def hash_password(password: str) -> str:
    """Генерирует bcrypt-хеш пароля"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    """Проверяет пароль против хеша"""
    return bcrypt.checkpw(password.encode(), hashed.encode())

USERS = {
    "admin": {"hash": "$2b$12$kULF9uKSNlV8Q3OTy02o9.ElMYQytN5tyXvnvmuyXrG.GXsmIy6oe", "role": "admin"},
}

user_list_env = os.getenv("ADDITIONAL_USERS", "")
if user_list_env:
    for user_spec in user_list_env.split(";"):
        parts = user_spec.strip().split(":")
        if len(parts) == 3:
            uname, uhash, urole = parts
            USERS[uname] = {"hash": uhash, "role": urole}

def check_password():
    if st.session_state.get("authenticated"):
        return True

    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    
    with col2:
        st.header("🔐 Вход в AXIS")
        login = st.text_input("Логин", key="login_input")
        pwd = st.text_input("Пароль", type="password", key="pwd_input")
        
        if st.button("Войти", width='stretch'):
            if login in USERS and verify_password(pwd, USERS[login]["hash"]):
                st.session_state.authenticated = True
                st.session_state.user_role = USERS[login]["role"]
                st.session_state.user_name = login
                st.rerun()
            else:
                st.error("❌ Неверные данные")
    return False

if not check_password():
    st.stop()

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
# БЛОК: [CORE-DB-ENGINE] v2.5
# ==========================================================
url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

@st.cache_resource
def init_connection():
    eng = create_engine(url, pool_size=15, max_overflow=25)
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

def bump_db_version():
    st.session_state.db_version += 1

# ==========================================================
# БЛОК: [UI-NAVIGATION-TABS] v3.0 (С УЧЁТОМ РОЛЕЙ)
# ==========================================================
if USER_ROLE == "admin":
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Аналитика", 
        "📥 Загрузка данных", 
        "⚙️ Ставки и Люди",
        "🗄️ Управление данными",
        "🛠 Системные функции"
    ])
else:
    tab1, tab2 = st.tabs(["📊 Мои данные", "📥 Загрузка данных"])

# ==========================================================
# БЛОК: [DATA-CORE-ENGINE] v6.1 (С КЭШИРОВАНИЕМ)
# ==========================================================
@st.cache_data(ttl=300, show_spinner=False)
def get_logs(v_trigger: int, filter_user: Union[str, None] = None) -> pd.DataFrame:
    try:
        with engine.connect() as conn:
            if filter_user and USER_ROLE != "admin":
                df = pd.read_sql(
                    text('SELECT * FROM work_logs WHERE "Sotrudnik" = :user ORDER BY "Date" DESC'),
                    conn,
                    params={"user": filter_user}
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

def validate_data(df: pd.DataFrame, d_c: str, f_c: str, h_c: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    temp_date = pd.to_datetime(df[d_c], errors='coerce')
    temp_hour = pd.to_numeric(df[h_c], errors='coerce')
    
    bad_mask = temp_date.isna() | temp_hour.isna() | df[f_c].isna()
    
    bad_df = df[bad_mask].copy()
    clean_df = df[~bad_mask].copy()
    
    clean_df[d_c] = temp_date[~bad_mask].dt.date
    clean_df[h_c] = temp_hour[~bad_mask]
    
    return clean_df, bad_df

def run_data_import(df: pd.DataFrame, d_col: str, f_col: str, p_col: str, h_col: str, mode: str = "UPSERT") -> int:
    try:
        clean_df, bad_df = validate_data(df, d_col, f_col, h_col)
        
        if clean_df.empty:
            st.warning("Нет валидных данных для импорта")
            return 0
        
        to_db = pd.DataFrame()
        to_db['Date'] = pd.to_datetime(clean_df[d_col]).dt.date
        to_db['Sotrudnik'] = clean_df[f_col].astype(str).str.strip()
        to_db['Proect'] = clean_df[p_col] if p_col != "НЕТ" else "Без проекта"
        to_db['Time'] = pd.to_numeric(clean_df[h_col], errors='coerce').fillna(0)

        def is_real_name(val):
            v = str(val).lower()
            if v.isdigit() or any(char in v for char in ['-', ':', '/']) or len(v) < 2:
                return False
            return True
        
        to_db = to_db[to_db['Sotrudnik'].apply(is_real_name)]
        
        # Группируем по ДАТА + СОТРУДНИК (суммируем часы, проекты объединяем)
        agg_df = to_db.groupby(['Date', 'Sotrudnik'], as_index=False).agg({
            'Time': 'sum',
            'Proect': lambda x: ', '.join(sorted(set(x)))  # Объединяем проекты через запятую
        })
        
        # Автодобавление новых сотрудников в справочник
        new_workers = agg_df['Sotrudnik'].unique()
        if len(new_workers) > 0:
            try:
                with engine.connect() as conn:
                    for worker in new_workers:
                        conn.execute(
                            text('INSERT INTO employee_rates ("Sotrudnik") VALUES (:w) ON CONFLICT DO NOTHING'),
                            {"w": worker}
                        )
            except Exception:
                pass

        with engine.begin() as conn:
            if "REPLACE" in mode:
                if USER_ROLE != "admin":
                    conn.execute(
                        text('DELETE FROM work_logs WHERE "Sotrudnik" = :user'),
                        {"user": USER_NAME}
                    )
                else:
                    conn.execute(text("DELETE FROM work_logs"))
            
            for _, row in agg_df.iterrows():
                conn.execute(text("""
                    INSERT INTO work_logs ("Date", "Sotrudnik", "Proect", "Time")
                    VALUES (:d, :s, :p, :t)
                    ON CONFLICT ("Date", "Sotrudnik") 
                    DO UPDATE SET "Time" = EXCLUDED."Time", "Proect" = EXCLUDED."Proect";
                """), {
                    "d": row['Date'], "s": row['Sotrudnik'], "p": row['Proect'], "t": row['Time']
                })
        
        bump_db_version()
        return len(to_db)
    except Exception as e:
        st.error(f"Ошибка движка импорта: {e}")
        log_error(f"run_data_import: {str(e)}")
        return 0

def delete_record(date, sotrudnik: str, proect: str) -> bool:
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                DELETE FROM work_logs 
                WHERE "Date" = :d AND "Sotrudnik" = :s AND "Proect" = :p
            """), {"d": date, "s": sotrudnik, "p": proect})
        bump_db_version()
        return True
    except Exception as e:
        st.error(f"Ошибка удаления: {e}")
        log_error(f"delete_record: {str(e)}")
        return False

# ==========================================================
# БЛОК: [SYS-TG-NOTIFIER] v3.3 (TYPE HINTS)
# ==========================================================
def send_telegram_summary(df: pd.DataFrame) -> None:
    load_dotenv(override=True)
    token = str(os.getenv("TG_TOKEN", "")).strip().replace('"', '').replace("'", "")
    chat_id = str(os.getenv("TG_ADMIN_ID", "")).strip().replace('"', '').replace("'", "")
    
    if ":" not in token:
        st.error("Ошибка: Токен Telegram не найден в .env или неверный.")
        return
    
    try:
        with engine.connect() as conn:
            rates_df = pd.read_sql("SELECT * FROM employee_rates", conn)
        
        calc_df = df.copy()
        if 'Sotrudnik' not in calc_df.columns and 'Сотрудник' in calc_df.columns:
            calc_df = calc_df.rename(columns={'Сотрудник': 'Sotrudnik'})
        if 'Time' not in calc_df.columns and 'Часы' in calc_df.columns:
            calc_df = calc_df.rename(columns={'Часы': 'Time'})

        temp_df = calc_df.merge(rates_df, on="Sotrudnik", how="left")
        
        for col in ['Rate', 'Client_Rate']:
            if col not in temp_df.columns:
                temp_df[col] = 0
            else:
                temp_df[col] = pd.to_numeric(temp_df[col], errors='coerce').fillna(0)
        
        temp_df['Time'] = pd.to_numeric(temp_df['Time'], errors='coerce').fillna(0)
        
        total_h = temp_df['Time'].sum()
        revenue = (temp_df['Time'] * temp_df['Client_Rate']).sum()
        cost = (temp_df['Time'] * temp_df['Rate']).sum()
        profit = revenue - cost
        
        bot = telebot.TeleBot(token)
        msg = (
            f"🚀 *ОТЧЕТ AXIS*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏱ *Часов:* {total_h:.1f}\n"
            f"💰 *Прибыль:* {int(profit):,} р."
        )
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        st.toast("✅ Отчет отправлен в Telegram")
        log_info(f"Telegram отчёт отправлен: {int(profit)} р.")
        
    except Exception as e:
        st.error(f"Ошибка API Telegram: {e}")
        log_error(f"send_telegram: {str(e)}")

# ==========================================================
# БЛОК: [FINANCES-CALCULATOR] v1.0
# ==========================================================
def calculate_finances(logs_df: pd.DataFrame, rates_df: pd.DataFrame) -> pd.DataFrame:
    if logs_df.empty:
        return pd.DataFrame()
    
    f_df = logs_df.copy()
    f_df['Sotrudnik'] = f_df['Sotrudnik'].astype(str).str.strip()
    
    f_df = f_df.merge(rates_df, on="Sotrudnik", how="left")
    
    f_df['Rate'] = pd.to_numeric(f_df['Rate'], errors='coerce').fillna(0)
    f_df['Client_Rate'] = pd.to_numeric(f_df['Client_Rate'], errors='coerce').fillna(0)
    f_df['Time'] = pd.to_numeric(f_df['Time'], errors='coerce').fillna(0)
    
    f_df['Revenue'] = f_df['Time'] * f_df['Client_Rate']
    f_df['Cost'] = f_df['Time'] * f_df['Rate']
    f_df['Profit'] = f_df['Revenue'] - f_df['Cost']
    
    f_df['Date'] = pd.to_datetime(f_df['Date'])
    return f_df

# ==========================================================
# PDF GENERATOR
# ==========================================================
def create_pdf_report(df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    def clean_txt(text):
        text = str(text)
        chars = {"А":"A","Б":"B","В":"V","Г":"G","Д":"D","Е":"E","Ё":"E","Ж":"Zh","З":"Z","И":"I","Й":"Y",
                 "К":"K","Л":"L","М":"M","Н":"N","О":"O","П":"P","Р":"R","С":"S","Т":"T","У":"U","Ф":"F",
                 "Х":"H","Ц":"Ts","Ч":"Ch","Ш":"Sh","Щ":"Sch","Ъ":"","Ы":"y","Ь":"","Э":"E","Ю":"Yu","Я":"Ya",
                 "а":"a","б":"b","в":"v","г":"g","д":"d","е":"e","ё":"e","ж":"zh","з":"z","и":"i","й":"y",
                 "к":"k","л":"l","м":"m","н":"n","о":"o","п":"p","р":"r","с":"s","т":"t","у":"u","ф":"f",
                 "х":"h","ц":"ts","ч":"ch","ш":"sh","щ":"sch","ъ":"","ы":"y","ь":"","э":"e","ю":"yu","я":"ya"}
        for k, v in chars.items():
            text = text.replace(k, v)
        return text.encode('ascii', 'ignore').decode('ascii')

    pdf.cell(200, 10, "WORK REPORT", new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(10)

    pdf.set_font("Helvetica", 'B', 10)
    pdf.cell(80, 10, "Employee", border=1)
    pdf.cell(40, 10, "Hours", border=1)
    pdf.cell(50, 10, "Profit", border=1)
    pdf.ln()

    pdf.set_font("Helvetica", size=10)
    report_df = df.groupby('Sotrudnik').agg({'Time': 'sum', 'Profit': 'sum'}).reset_index()
    
    for _, row in report_df.iterrows():
        name = clean_txt(row['Sotrudnik'])
        if not name.strip(): name = "Unknown"
        pdf.cell(80, 10, name, border=1)
        pdf.cell(40, 10, f"{row['Time']:.1f}", border=1)
        pdf.cell(50, 10, f"{int(row['Profit'])}", border=1)
        pdf.ln()
        
    return bytes(pdf.output())

# ==========================================================
# БЛОК: [UI-TAB-IMPORT] v5.4
# ==========================================================
with tab2:
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
                    count = run_data_import(df, d_c, f_c, p_c, h_c)
                    
                    if count > 0:
                        import_df = df[[d_c, f_c, h_c]].rename(columns={d_c: 'Date', f_c: 'Sotrudnik', h_c: 'Time'})
                        import_df['Date'] = pd.to_datetime(import_df['Date'])
                        import_df['Time'] = pd.to_numeric(import_df['Time'], errors='coerce').fillna(0)
                        
                        send_telegram_summary(import_df)
                        
                        if "df_temp" in st.session_state:
                            del st.session_state.df_temp
                        st.session_state.ready_to_map = False
                        
                        st.success(f"Импорт завершен! Добавлено/обновлено строк: {count}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Данные не были загружены. Проверьте формат колонок.")

# ==========================================================
# БЛОК: [UI-MAIN-DASHBOARD] v5.9
# ==========================================================
with tab1:
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
                send_telegram_summary(f_data[(f_data['Date'] >= pd.Timestamp(start_d)) & (f_data['Date'] <= pd.Timestamp(end_d))])

        df_f = f_data.loc[(f_data['Date'] >= pd.Timestamp(start_d)) & (f_data['Date'] <= pd.Timestamp(end_d))]

        if not df_f.empty:
            st.write("### Итоговые показатели")
            m1, m2, m3, m4 = st.columns(4)
            m1.markdown(f"**Всего часов**\n### {df_f['Time'].sum():,.1f}")
            m2.markdown(f"**Выручка**\n### {int(df_f['Revenue'].sum()):,} р.")
            m3.markdown(f"**Затраты**\n### {int(df_f['Cost'].sum()):,} р.")
            m4.markdown(f"**Прибыль**\n### {int(df_f['Profit'].sum()):,} р.")

            st.divider()

            c1, c2 = st.columns(2)
            with c1:
                u_stats = df_f.groupby('Sotrudnik')['Time'].sum().sort_values(ascending=True).reset_index()
                fig_u = px.bar(u_stats, x='Time', y='Sotrudnik', orientation='h', title="Часы")
                st.plotly_chart(fig_u, width='stretch')
            
            with c2:
                p_stats = df_f.groupby('Proect')['Profit'].sum().reset_index()
                fig_p = px.pie(p_stats, values='Profit', names='Proect', title="Прибыль")
                st.plotly_chart(fig_p, width='stretch')
            
            pdf_data = create_pdf_report(df_f)
            st.download_button(
                label="📄 Скачать PDF-отчет",
                data=pdf_data,
                file_name="work_report.pdf",
                mime="application/pdf",
                width='stretch'
            )
        else:
            st.warning("Нет данных за выбранный период.")
    else:
        st.info("Данные не найдены. Загрузите файл во вкладке 'Загрузка данных'.")

# ==========================================================
# БЛОК: [UI-TAB-RATES] v6.0 (УЛУЧШЕННЫЙ)
# ==========================================================
if USER_ROLE == "admin":
    with tab3:
        st.header("⚙️ Настройка стоимости работ")
        
        current_logs = get_logs(st.session_state.db_version)
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
                    bump_db_version()
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
                    time.sleep(1)
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
                        time.sleep(1)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Ошибка: {e}")
        
    # ==========================================================
    # БЛОК: [UI-TAB-DATA-MANAGEMENT] v2.0 (ПАГИНАЦИЯ)
    # ==========================================================
    with tab4:
        st.header("🗄️ Управление данными")
        st.caption("Просмотр и удаление записей из базы")
        
        logs_df = get_logs(st.session_state.db_version)
        
        if not logs_df.empty:
            st.subheader("Фильтры")
            col_f1, col_f2, col_f3, col_exp = st.columns([1, 1, 1, 1])
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
                logs_df['Date'] = pd.to_datetime(logs_df['Date'])
                min_date = logs_df['Date'].min().date()
                max_date = logs_df['Date'].max().date()
                start_date = st.date_input("С", min_date, key="filter_start")
                end_date = st.date_input("По", max_date, key="filter_end")
            
            filtered_df = logs_df.copy()
            if filter_worker != "Все":
                filtered_df = filtered_df[filtered_df['Sotrudnik'] == filter_worker]
            if filter_project != "Все":
                filtered_df = filtered_df[filtered_df['Proect'].str.contains(filter_project, na=False)]
            filtered_df = filtered_df[(filtered_df['Date'].dt.date >= start_date) & (filtered_df['Date'].dt.date <= end_date)]
            
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
                    if delete_record(del_date, del_worker, del_proect):
                        st.success("Запись удалена!")
                        time.sleep(1)
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
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("База данных пуста.")

    # ==========================================================
    # БЛОК: [UI-SYSTEM-TOOLS] v5.4 (ТОЛЬКО АДМИН)
    # ==========================================================
    with tab5:
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
                if init_connection():
                    bump_db_version()
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
                        log_info(f"Бэкап создан: {filename}")
                        st.success(f"✅ Бэкап сохранён: {filename}")
                    except Exception as e:
                        st.error(f"❌ Ошибка бэкапа: {e}")
                        log_error(f"Backup failed: {e}")
        
        with col_b2:
            st.write("Последние бэкапы:")
            backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.sql')], reverse=True)[:5]
            if backups:
                for b in backups:
                    st.caption(f"📄 {b}")
            else:
                st.caption("Нет бэкапов")

        st.divider()
        
        # ==================== ВОССТАНОВЛЕНИЕ ====================
        st.subheader("♻️ Восстановление из бэкапа")
        
        col_r1, col_r2 = st.columns(2)
        
        with col_r1:
            st.info("📤 Загрузить бэкап-файл (.sql)")
            uploaded_backup = st.file_uploader("Выберите файл", type=['sql'], key="restore_upload")
            
            if uploaded_backup:
                st.caption(f"Файл: {uploaded_backup.name} ({uploaded_backup.size / 1024:.1f} KB)")
                confirm_restore = st.checkbox("✅ Подтверждаю восстановление")
                
                if st.button("♻️ ВОССТАНОВИТЬ", type="primary", width='stretch', 
                            disabled=not confirm_restore, key="restore_btn"):
                    with st.spinner("Восстановление..."):
                        try:
                            temp_path = os.path.join(backup_dir, "temp_restore.sql")
                            with open(temp_path, 'wb') as f:
                                f.write(uploaded_backup.getvalue())
                            
                            env = os.environ.copy()
                            env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")
                            
                            result = subprocess.run(
                                ['psql', '-h', os.getenv("DB_HOST", "db"), '-U', 
                                 os.getenv("DB_USER", "user"), '-d', os.getenv("DB_NAME", "workday_db"), 
                                 '-f', temp_path],
                                env=env,
                                capture_output=True,
                                text=True
                            )
                            
                            os.remove(temp_path)
                            
                            if result.returncode == 0:
                                bump_db_version()
                                st.success("✅ База данных восстановлена!")
                                log_info(f"Restore completed from uploaded file")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ Ошибка: {result.stderr}")
                        except Exception as e:
                            st.error(f"❌ Ошибка восстановления: {e}")
                            log_error(f"Restore failed: {e}")
        
        with col_r2:
            st.info("📁 Или выбрать из существующих")
            existing_backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.sql')], reverse=True)
            
            if existing_backups:
                selected_backup = st.selectbox("Бэкап:", existing_backups, key="restore_select")
                file_size = os.path.getsize(os.path.join(backup_dir, selected_backup)) / 1024
                st.caption(f"Размер: {file_size:.1f} KB")
                confirm_existing = st.checkbox("✅ Подтверждаю восстановление", key="confirm_existing")
                
                if st.button("♻️ ВОССТАНОВИТЬ", width='stretch', disabled=not confirm_existing, key="restore_existing_btn"):
                    with st.spinner("Восстановление..."):
                        try:
                            filepath = os.path.join(backup_dir, selected_backup)
                            
                            env = os.environ.copy()
                            env["PGPASSWORD"] = os.getenv("DB_PASSWORD", "")
                            
                            result = subprocess.run(
                                ['psql', '-h', os.getenv("DB_HOST", "db"), '-U', 
                                 os.getenv("DB_USER", "user"), '-d', os.getenv("DB_NAME", "workday_db"), 
                                 '-f', filepath],
                                env=env,
                                capture_output=True,
                                text=True
                            )
                            
                            if result.returncode == 0:
                                bump_db_version()
                                st.success("✅ База данных восстановлена!")
                                log_info(f"Restore completed: {selected_backup}")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(f"❌ Ошибка: {result.stderr}")
                        except Exception as e:
                            st.error(f"❌ Ошибка восстановления: {e}")
                            log_error(f"Restore failed: {e}")
            else:
                st.warning("Нет доступных бэкапов")
        
        st.divider()

        st.subheader("🛑 Опасная зона")
        st.error("⚠️ ВНИМАНИЕ! Действия ниже необратимы!")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.info("Удаление всех рабочих часов")
            confirm_logs = st.checkbox("✅ Я понимаю, что удалю ВСЕ логи")
            if st.button("🧨 ОЧИСТИТЬ ВСЕ ЛОГИ", type="primary", width='stretch', disabled=not confirm_logs):
                with engine.begin() as conn:
                    conn.execute(text("TRUNCATE TABLE work_logs RESTART IDENTITY"))
                bump_db_version()
                st.success("Логи работы удалены")
                time.sleep(1)
                st.rerun()

        with c2:
            st.warning("Удаление справочника сотрудников и цен")
            confirm_rates = st.checkbox("✅ Я понимаю, что удалю справочник")
            if st.button("🗑️ ОБНУЛИТЬ СПРАВОЧНИК", width='stretch', disabled=not confirm_rates):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM employee_rates"))
                bump_db_version()
                st.success("Справочник цен очищен")
                time.sleep(1)
                st.rerun()