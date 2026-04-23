
# WorkLog

Учёт рабочего времени для фриланса и небольших команд: **Streamlit**, **PostgreSQL**, **Grafana**, **Docker**, отчёты и импорт из Excel.

**Репозиторий:** [github.com/Switchell/WorkLog](https://github.com/Switchell/WorkLog)
<img width="1557" height="1200" alt="Screenshot_2" src="https://github.com/user-attachments/assets/04fb8cf7-964b-4141-8f9f-8c3fb726cfe2" />
## Кому подойдёт / не подойдёт

| Подойдёт | Не подойдёт |
|----------|-------------|
| Фриланс и **маленькие команды**, учёт часов, отчёты, **Excel** | Крупный **HR enterprise** из коробки |
| **Свой сервер** (Docker), Grafana, Telegram-отчёты | SaaS без установки с готовым облаком под ключ |
| Кто готов читать `docs/` и настроить `.env` | «Установил и не трогал» без Docker |

## Три шага до первого результата

1. `cp .env.example .env` — пароли БД, при желании Telegram.  
2. `docker compose --env-file .env -f docker/docker-compose.yml up -d`.  
3. Открыть URL из **[docs/README.md](docs/README.md)** (nginx / админка / Grafana).

## Документация

| Файл | Содержание |
|------|------------|
| [docs/README.md](docs/README.md) | Обзор, возможности, быстрый старт, стек |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Развёртывание на сервере, SSL |
| [docs/КОНТЕКСТ_ПРОЕКТА.md](docs/КОНТЕКСТ_ПРОЕКТА.md) | Docker, БД, Grafana, нюансы |
| [docs/СОСТОЯНИЕ_И_ROADMAP.md](docs/СОСТОЯНИЕ_И_ROADMAP.md) | Аудит и план |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Локальный запуск, тесты, разработка |

## Минимальный запуск

```bash
cp .env.example .env
# задайте пароли и при необходимости Telegram в .env

docker compose --env-file .env -f docker/docker-compose.yml up -d
```

Порты (nginx, админка, клиент, Grafana) и учётные записи — в **[docs/README.md](docs/README.md)**.

## Лицензия

[MIT](LICENSE)
