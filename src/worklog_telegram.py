"""
Отправка отчётов в Telegram (прямой HTTP, без pyTelegramBotAPI).
В регионах без прямого доступа к api.telegram.org нужен VPN/прокси.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import requests


class TelegramSendError(Exception):
    """Ошибка ответа Telegram API (не сеть)."""


class TelegramNetworkError(Exception):
    """Таймаут или обрыв связи с api.telegram.org."""


def send_markdown_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    connect_s = int(os.getenv("TG_CONNECT_TIMEOUT", "20"))
    read_s = int(os.getenv("TG_READ_TIMEOUT", "90"))
    max_attempts = int(os.getenv("TG_SEND_RETRIES", "4"))
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    last_err: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=(connect_s, read_s),
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return
                desc = data.get("description", resp.text)
                raise TelegramSendError(f"Telegram API: {desc}")
            last_err = TelegramSendError(f"HTTP {resp.status_code}: {resp.text[:500]}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_err = TelegramNetworkError(str(e))
        except TelegramSendError as e:
            last_err = e
        if attempt < max_attempts:
            time.sleep(min(2**attempt, 30))
    if last_err:
        raise last_err
    raise TelegramNetworkError("Не удалось отправить сообщение")


def network_error_hint() -> str:
    return (
        "Не удалось достичь api.telegram.org (таймаут или нет сети). "
        "Часто для Telegram нужен VPN или прокси. "
        "Данные в приложении сохранены — повторите отправку после включения VPN."
    )
