# Участие и локальный запуск

## Запуск в Docker

Из **корня репозитория** (рядом с `.env`):

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

Или на Linux/macOS: `./scripts/start.sh` (подставляет `.env` и те же флаги).

Остановка: `./scripts/stop.sh` или `docker compose --env-file .env -f docker/docker-compose.yml down`.

Без файла `.env` compose использует значения по умолчанию в YAML (`user` / `password` / `workday_db`).

Сервисы **admin** и **client** в `docker-compose.yml` принудительно получают `DB_HOST=db` (DNS-имя сервиса Postgres в сети compose). Ошибочное значение вроде `axis_db` в `.env` на подключение из контейнеров не влияет.

## База данных и смена пароля

Том `postgres_data` хранит пользователя и пароль, заданные **при первом** создании контейнера `db`. Если поменять только `DB_PASSWORD` в `.env`, **существующий** Postgres не сменит пароль сам.

- Для новой установки: задайте `DB_USER` / `DB_PASSWORD` / `DB_NAME` в `.env` **до** первого `up`.
- Для уже работающей БД: меняйте пароль через `ALTER USER` внутри Postgres или поднимайте новый том (с бэкапом).

Grafana читает те же `DB_*` из окружения контейнера (см. `docker/grafana/provisioning/datasources/datasources.yml`).

## Клиентский портал

Пароли задаются в `.env`: `AXIS_CLIENT_KWORK_PASSWORD`, `AXIS_CLIENT_FREELANCE_PASSWORD`.

- В **проде** выставьте `AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS=0` и оба пароля явно.
- Для **локалки** по умолчанию `AXIS_ALLOW_DEFAULT_CLIENT_PASSWORDS=1` оставляет прежние дефолты `kwork123` / `free456`, если переменные пустые.

## Тесты

```bash
pip install -r docker/requirements-dev.txt
set PYTHONPATH=src
pytest tests
```

На Unix: `PYTHONPATH=src pytest tests`.

## Структура модулей `src/`

| Файл | Назначение |
|------|------------|
| `app.py` | Админ Streamlit (вкладки, UI) |
| `app_client.py` | Клиентский портал |
| `worklog_db.py` | URL и engine SQLAlchemy |
| `worklog_logging.py` | `log_error` / `log_info` |
| `worklog_auth.py` | Вход админки, bcrypt |
| `worklog_client_auth.py` | Пароли клиентов из env |
| `worklog_import_db.py` | Валидация и импорт Excel, удаление записи |
| `worklog_finance.py` | Расчёт выручки / затрат / прибыли |
| `worklog_pdf.py` | PDF-отчёт |
| `worklog_telegram_reports.py` | Сводка в Telegram из датафрейма |
| `worklog_telegram.py` | HTTP-клиент Telegram Bot API |

Подробный контекст: `docs/КОНТЕКСТ_ПРОЕКТА.md`.
