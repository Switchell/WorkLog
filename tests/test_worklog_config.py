import pytest

from worklog_db import database_url
from worklog_client_auth import get_client_passwords


def test_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_USER", "u")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("DB_HOST", "h")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "db")
    assert database_url() == "postgresql://u:p@h:5432/db"


def test_client_passwords_strict_missing_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AXIS_CLIENT_KWORK_PASSWORD", raising=False)
    monkeypatch.delenv("AXIS_CLIENT_FREELANCE_PASSWORD", raising=False)
    monkeypatch.setenv("AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS", "0")
    assert get_client_passwords() is None


def test_client_passwords_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AXIS_CLIENT_KWORK_PASSWORD", "secret_a")
    monkeypatch.setenv("AXIS_CLIENT_FREELANCE_PASSWORD", "secret_b")
    monkeypatch.setenv("AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS", "0")
    d = get_client_passwords()
    assert d == {"client_kwork": "secret_a", "client_freelance": "secret_b"}


def test_client_passwords_defaults_when_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AXIS_CLIENT_KWORK_PASSWORD", raising=False)
    monkeypatch.delenv("AXIS_CLIENT_FREELANCE_PASSWORD", raising=False)
    monkeypatch.setenv("AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS", "1")
    d = get_client_passwords()
    assert d == {"client_kwork": "kwork123", "client_freelance": "free456"}
