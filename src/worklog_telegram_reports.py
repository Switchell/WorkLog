"""Отчёт в Telegram из датафрейма (зависит от Streamlit UI)."""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy.engine import Engine

from worklog_logging import log_error, log_info
from worklog_telegram import (
    send_markdown_message,
    TelegramNetworkError,
    TelegramSendError,
    network_error_hint,
)


def send_telegram_summary(engine: Engine, df: pd.DataFrame) -> None:
    load_dotenv(override=True)
    token = str(os.getenv("TG_TOKEN", "")).strip().replace('"', "").replace("'", "")
    chat_id = str(os.getenv("TG_ADMIN_ID", "")).strip().replace('"', "").replace("'", "")

    if ":" not in token:
        st.error("Ошибка: Токен Telegram не найден в .env или неверный.")
        return

    try:
        with engine.connect() as conn:
            rates_df = pd.read_sql("SELECT * FROM employee_rates", conn)

        calc_df = df.copy()
        if "Sotrudnik" not in calc_df.columns and "Сотрудник" in calc_df.columns:
            calc_df = calc_df.rename(columns={"Сотрудник": "Sotrudnik"})
        if "Time" not in calc_df.columns and "Часы" in calc_df.columns:
            calc_df = calc_df.rename(columns={"Часы": "Time"})

        temp_df = calc_df.merge(rates_df, on="Sotrudnik", how="left")

        for col in ["Rate", "Client_Rate"]:
            if col not in temp_df.columns:
                temp_df[col] = 0
            else:
                temp_df[col] = pd.to_numeric(temp_df[col], errors="coerce").fillna(0)

        temp_df["Time"] = pd.to_numeric(temp_df["Time"], errors="coerce").fillna(0)

        total_h = temp_df["Time"].sum()
        revenue = (temp_df["Time"] * temp_df["Client_Rate"]).sum()
        cost = (temp_df["Time"] * temp_df["Rate"]).sum()
        profit = revenue - cost

        msg = (
            f"🚀 *ОТЧЕТ AXIS*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏱ *Часов:* {total_h:.1f}\n"
            f"💰 *Прибыль:* {int(profit):,} р."
        )
        send_markdown_message(token, chat_id, msg)
        st.toast("✅ Отчет отправлен в Telegram")
        log_info(f"Telegram отчёт отправлен: {int(profit)} р.")

    except TelegramNetworkError as e:
        st.warning(network_error_hint())
        log_error(f"send_telegram network: {e}")
    except TelegramSendError as e:
        st.error(f"Ошибка Telegram API: {e}")
        log_error(f"send_telegram api: {e}")
    except Exception as e:
        st.error(f"Ошибка при отправке в Telegram: {e}")
        log_error(f"send_telegram: {str(e)}")
