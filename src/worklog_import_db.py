"""Валидация и импорт Excel в work_logs (Streamlit UI)."""
from __future__ import annotations

from typing import Callable, Tuple

import pandas as pd
import streamlit as st
from sqlalchemy import text
from sqlalchemy.engine import Engine

from worklog_logging import log_error

__all__ = ["validate_data", "run_data_import", "delete_record"]


def validate_data(
    df: pd.DataFrame, d_c: str, f_c: str, h_c: str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    temp_date = pd.to_datetime(df[d_c], errors="coerce")
    temp_hour = pd.to_numeric(df[h_c], errors="coerce")

    bad_mask = temp_date.isna() | temp_hour.isna() | df[f_c].isna()

    bad_df = df[bad_mask].copy()
    clean_df = df[~bad_mask].copy()

    clean_df[d_c] = temp_date[~bad_mask].dt.date
    clean_df[h_c] = temp_hour[~bad_mask]

    return clean_df, bad_df


def run_data_import(
    engine: Engine,
    df: pd.DataFrame,
    d_col: str,
    f_col: str,
    p_col: str,
    h_col: str,
    *,
    user_role: str,
    user_name: str,
    bump_db_version: Callable[[], None],
    mode: str = "UPSERT",
) -> int:
    try:
        clean_df, bad_df = validate_data(df, d_col, f_col, h_col)

        if clean_df.empty:
            st.warning("Нет валидных данных для импорта")
            return 0

        to_db = pd.DataFrame()
        to_db["Date"] = pd.to_datetime(clean_df[d_col]).dt.date
        to_db["Sotrudnik"] = clean_df[f_col].astype(str).str.strip()
        to_db["Proect"] = clean_df[p_col] if p_col != "НЕТ" else "Без проекта"
        to_db["Time"] = pd.to_numeric(clean_df[h_col], errors="coerce").fillna(0)

        def is_real_name(val):
            v = str(val).lower()
            if v.isdigit() or any(char in v for char in ["-", ":", "/"]) or len(v) < 2:
                return False
            return True

        to_db = to_db[to_db["Sotrudnik"].apply(is_real_name)]

        agg_df = to_db.groupby(["Date", "Sotrudnik"], as_index=False).agg(
            {"Time": "sum", "Proect": lambda x: ", ".join(sorted(set(x)))}
        )

        new_workers = agg_df["Sotrudnik"].unique()
        worker_rows = [{"w": w} for w in new_workers.tolist()]
        if worker_rows:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            'INSERT INTO employee_rates ("Sotrudnik") VALUES (:w) ON CONFLICT DO NOTHING'
                        ),
                        worker_rows,
                    )
            except Exception:
                pass

        upsert_rows = [
            {"d": r.Date, "s": r.Sotrudnik, "p": r.Proect, "t": float(r.Time)}
            for r in agg_df.itertuples(index=False)
        ]
        with engine.begin() as conn:
            if "REPLACE" in mode:
                if user_role != "admin":
                    conn.execute(
                        text('DELETE FROM work_logs WHERE "Sotrudnik" = :user'),
                        {"user": user_name},
                    )
                else:
                    conn.execute(text("DELETE FROM work_logs"))

            if upsert_rows:
                conn.execute(
                    text("""
                        INSERT INTO work_logs ("Date", "Sotrudnik", "Proect", "Time")
                        VALUES (:d, :s, :p, :t)
                        ON CONFLICT ("Date", "Sotrudnik")
                        DO UPDATE SET "Time" = EXCLUDED."Time", "Proect" = EXCLUDED."Proect";
                    """),
                    upsert_rows,
                )

        bump_db_version()
        return len(to_db)
    except Exception as e:
        st.error(f"Ошибка движка импорта: {e}")
        log_error(f"run_data_import: {str(e)}")
        return 0


def delete_record(
    engine: Engine,
    date,
    sotrudnik: str,
    proect: str,
    bump_db_version: Callable[[], None],
) -> bool:
    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                DELETE FROM work_logs
                WHERE "Date" = :d AND "Sotrudnik" = :s AND "Proect" = :p
            """),
                {"d": date, "s": sotrudnik, "p": proect},
            )
        bump_db_version()
        return True
    except Exception as e:
        st.error(f"Ошибка удаления: {e}")
        log_error(f"delete_record: {str(e)}")
        return False
