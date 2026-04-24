# WorkLog — AGENTS.md

> Система учёта рабочего времени. Python + Streamlit + PostgreSQL + Docker.
> Репозиторий: `C:\Users\Son\Desktop\Кодинг Проекты\WorkLog`

---

## 1. Структура проекта

```
WorkLog/
├── src/                          # Исходный код Streamlit-приложений
│   ├── app.py                    # Главная админка (точка входа)
│   ├── app_client.py             # Клиентский портал (readonly)
│   ├── worklog_auth.py           # bcrypt-аутентификация
│   ├── worklog_db.py             # Подключение к PostgreSQL (engine)
│   ├── worklog_charts.py         # Оформление Plotly-графиков
│   ├── worklog_charts_fallbacks.py
│   ├── worklog_finance.py        # Расчёт Revenue/Cost/Profit
│   ├── worklog_project_rollup.py # Агрегация по проектам (другое)
│   ├── worklog_import_db.py      # Импорт Excel → work_logs (UPSERT)
│   ├── worklog_logging.py        # Файловое логирование
│   ├── worklog_pdf.py            # Генерация PDF-отчётов
│   ├── worklog_telegram.py       # HTTP-отправка в Telegram
│   ├── worklog_telegram_reports.py
│   ├── worklog_client_auth.py    # Авторизация клиентского портала
│   └── backup.py                 # CLI-бэкап базы (pg_dump)
├── docker/
│   ├── docker-compose.yml        # 6 сервисов: db, admin, grafana, client, nginx, certbot
│   ├── Dockerfile                # Образ admin (python:3.9-slim + postgresql-client)
│   ├── Dockerfile_client         # Образ client
│   ├── nginx.conf                # Reverse proxy
│   ├── grafana/provisioning/     # Авто-настройка Grafana
│   └── requirements.txt          # Python-зависимости
├── tests/                        # pytest-тесты
│   ├── conftest.py               # sys.path += src/
│   ├── test_worklog_finance.py
│   ├── test_worklog_import.py
│   └── test_worklog_config.py
├── scripts/
│   ├── start.sh                  # Запуск с автобэкапом
│   ├── stop.sh                   # Остановка с автобэкапом
│   └── setup.sh                  # Первичная установка
└── docs/                         # КОНТЕКСТ_ПРОЕКТА, DEPLOY, СОСТОЯНИЕ_И_ROADMAP (аудит и план)
```

---

## 2. Команды

### Запуск / остановка
```bash
# Из корня WorkLog/
docker compose --env-file .env -f docker/docker-compose.yml up -d --build   # пересборка
docker compose --env-file .env -f docker/docker-compose.yml up -d            # быстрый старт
docker compose --env-file .env -f docker/docker-compose.yml down             # остановка
docker compose --env-file .env -f docker/docker-compose.yml logs -f admin    # логи
```

### Тесты
```bash
# Из корня WorkLog/ (pytest автоматически подхватывает src/ через conftest.py)
pytest tests/                               # все тесты
pytest tests/test_worklog_finance.py        # один файл
pytest tests/test_worklog_finance.py -k profit  # один тест
```

### Бэкап / восстановление
```bash
# Через UI: вкладка "Системные функции" → "Создать бэкап" / "Восстановление"
# CLI:
docker compose -f docker/docker-compose.yml exec admin python backup.py create
docker compose -f docker/docker-compose.yml exec admin python backup.py list
docker compose -f docker/docker-compose.yml exec admin python backup.py restore <file.sql>
```

---

## 3. Code style

### Импорт
- `from __future__ import annotations` — первый импорт во всех модулях
- Стандартные → третьи → локальные (`worklog_*`)
- Локальные модули префикс `worklog_` (flat namespace, без пакетов)

### Типизация
- Type hints обязательны для публичных функций
- Использовать `Union`, `Optional`, `Callable` из `typing`
- `pd.DataFrame` — без generics (pandas limitation)

### Именование
- Функции/переменные: `snake_case`
- Колонки БД: `"PascalCase"` в двойных кавычках (PostgreSQL, legacy)
- Константы темы: `UPPER_SNAKE_CASE` (`L_TITLE`, `D_GRID`)
- Модули: `worklog_<domain>.py`

### Обработка ошибок
- `try/except` с логированием через `worklog_logging.log_error()`
- Никогда не глотать исключения молча (минимум `pass` после `except Exception`)
- Telegram-ошибки: `TelegramSendError`, `TelegramNetworkError` с retry-логикой

### Streamlit-паттерны
- `st.session_state` для состояния между ререндерами
- `@st.cache_resource` для engine (singleton)
- `st.rerun()` после мутаций БД
- Формы: `st.form()` с уникальными `key`
- **Никакой пагинации** — данные показываются целиком с фильтрами

---

## 4. База данных

### Схема
```sql
employee_rates: "Sotrudnik" (PK), "Rate", "Client_Rate"
work_logs:      "Date", "Sotrudnik", "Proect", "Time"
                UNIQUE("Date", "Sotrudnik")  -- UPSERT по дате+сотрудник
```

### Важные правила
- `DB_HOST: db` — внутри Docker-сети (имя сервиса, не container_name)
- `pool_pre_ping=True` — проверка соединения перед запросом
- Миграции: `CREATE TABLE IF NOT EXISTS` при старте приложения
- Колонки в двойных кавычках — регистр важен!

---

## 5. Docker-безопасность

- **Всегда** указывать compose-файл: `-f docker/docker-compose.yml`
- **Никогда** не делать `docker system prune` без явного запроса
- Порты проекта: `80` (nginx), `443` (ssl), `3001` (grafana), `5432` (db), `8502` (admin прямой)
- Параллельно могут работать другие Docker-проекты — проверять контекст

---

## 6. Quality-gates

После изменений в WorkLog:
1. Проверить `docker/requirements.txt` (если новая зависимость)
2. Запустить `pytest tests/`
3. Smoke-тест: `docker compose -f docker/docker-compose.yml up -d`
4. Не коммитить `.env`, ключи, токены

---

## 7. Коммуникация

- Язык: русский, свободная форма
- Перед крупными правками: `Понял задачу как: ...`
- Ответы короткие: что сделано, где, как проверить
- При неоднозначности — максимум 1-2 уточняющих вопроса

---

## 8. Протокол безопасных изменений

1. Перед DB/импорт/восстановление — бэкап файла
2. Предупредить пользователя о рискованном изменении
3. После правки — проверка критичного сценария
4. При регрессии — немедленный откат
