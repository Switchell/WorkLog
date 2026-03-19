# Настройка Grafana для AXIS

## 1. Подключение к базе данных

1. Откройте Grafana: http://localhost:3001
2. Логин/пароль: `admin` / `admin`
3. Перейдите в **Configuration → Data Sources**
4. Нажмите **Add data source**
5. Выберите **PostgreSQL**
6. Заполните:
   - Host: `axis_db` (или `localhost` если с хоста)
   - Port: `5432`
   - Database: `workday_db`
   - User: `user`
   - Password: `password`
   - SSL Mode: `disable`
7. Нажмите **Save & Test**

Или импортируйте `datasource.json`:
- Configuration → Data Sources → **Import** → загрузите файл

---

## 2. Импорт дашборда

1. Перейдите в **+ → Import**
2. Загрузите файл `dashboard.json`
3. Выберите datasource `AXIS PostgreSQL`
4. Нажмите **Import**

---

## 3. Что показывает дашборд

| Панель | Описание |
|--------|----------|
| Всего часов | Общее количество часов |
| Сотрудников | Количество уникальных сотрудников |
| Выручка | Доход (Time × Client_Rate) |
| Затраты | Расходы (Time × Rate) |
| Часы по дням | График динамики |
| Часы по сотрудникам | Pie chart |
| Выручка vs Затраты | Сравнительный график |
| Таблица сотрудников | Детализация по людям |

---

## 4. Если нужно изменить

Отредактируйте `dashboard.json`:
- Время обновления: `refresh: "5m"`
- Период по умолчанию: `time: {"from": "now-30d", "to": "now"}`

---

## 5. Алерты (опционально)

Для уведомлений о проблемах:
1. Edit панели → **Alert**
2. Create alert rule
3. Настройте условия (например, часы < 0)
4. Добавьте канал уведомлений (Telegram, Email)
