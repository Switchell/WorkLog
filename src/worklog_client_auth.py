"""Пароли клиентского портала из .env (с опциональными дефолтами для разработки)."""
from __future__ import annotations

import os
from typing import Dict, Optional


def get_client_passwords() -> Optional[Dict[str, str]]:
    """
    Возвращает map client_key -> password.
    Если AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS выключен — оба пароля должны быть в .env.
    """
    kwork = os.getenv("AXIS_CLIENT_KWORK_PASSWORD", "").strip()
    freelance = os.getenv("AXIS_CLIENT_FREELANCE_PASSWORD", "").strip()
    allow_defaults = os.getenv("AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS", "1").lower() in (
        "1",
        "true",
        "yes",
    )

    if kwork and freelance:
        return {"client_kwork": kwork, "client_freelance": freelance}

    if allow_defaults:
        return {
            "client_kwork": kwork or "kwork123",
            "client_freelance": freelance or "free456",
        }
    return None
