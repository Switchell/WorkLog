"""Общие настройки подключения к PostgreSQL для Streamlit-приложений."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def database_url() -> str:
    return (
        f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
    )


def create_worklog_engine() -> Engine:
    return create_engine(
        database_url(),
        pool_pre_ping=True,
        pool_size=int(os.getenv("DB_POOL_SIZE", "8")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "12")),
    )
