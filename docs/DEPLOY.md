# WorkLog - Инструкция по развёртыванию

## Быстрый старт

### 1. Настройка сервера

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo apt install -y docker-compose
```

### 2. Перенос файлов на сервер

```bash
# Скопировать папку проекта на сервер
scp -r ./work-tracker user@your-server:/home/user/
```

### 3. Настройка

```bash
cd work-tracker

# Редактировать .env
nano .env
```

**Обязательно изменить:**
- `DB_PASSWORD` — сложный пароль для базы
- `TG_TOKEN` — токен Telegram бота
- `TG_ADMIN_ID` — ваш Chat ID

### 4. Запуск

```bash
# Установка прав
chmod +x scripts/*.sh

# Запуск
./scripts/start.sh
```

---

## Структура проекта

```
work-tracker/
├── .env                     # Пароли и настройки
├── src/                     # Исходный код
│   ├── app.py              # Основное приложение
│   ├── app_client.py       # Клиентский портал
│   └── backup.py           # Бэкап базы
├── docker/                  # Docker конфигурация
│   ├── docker-compose.yml   # Конфигурация сервисов
│   ├── Dockerfile           # Docker образ admin
│   ├── Dockerfile_client   # Docker образ client
│   ├── nginx.conf          # Nginx конфиг
│   └── requirements.txt    # Python зависимости
├── scripts/                # Скрипты управления
│   ├── setup.sh           # Установка
│   ├── start.sh           # Запуск
│   └── stop.sh            # Остановка
├── docs/                   # Документация
│   └── ...
└── backups/               # Бэкапы базы
```

---

## Доступы

| Сервис | URL | Логин | Пароль |
|--------|-----|-------|--------|
| Основное приложение | http://SERVER/ | admin | 2213 |
| Клиентский портал | http://SERVER/client | kwork | kwork123 |
| Grafana | http://SERVER:3001 | admin | admin |
| База данных | localhost:5432 | user | из .env |

---

## Команды управления

```bash
# Запуск
./scripts/start.sh

# Остановка (с бэкапом)
./scripts/stop.sh

# Перезапуск
docker-compose -f docker/docker-compose.yml restart

# Просмотр логов
docker-compose -f docker/docker-compose.yml logs -f

# Обновление кода
docker-compose -f docker/docker-compose.yml down
# ...изменить код...
docker-compose -f docker/docker-compose.yml up -d --build
```

---

## SSL/HTTPS настройка (для продакшена)

### 1. Купить домен

Купите домен (например, erp.example.com) и настройте DNS:
- A запись: @ → IP вашего сервера
- A запись: www → IP вашего сервера

### 2. Получить SSL сертификат

```bash
# Зайти в контейнер certbot и получить сертификат
docker exec -it axis_certbot sh

# Внутри контейнера:
certbot certonly --webroot -w /usr/share/nginx/html -d your-domain.com

# Выйти из контейнера
exit
```

### 3. Раскомментировать HTTPS в nginx.conf

```bash
nano docker/nginx.conf
```

Убрать `#` перед строками HTTPS секции и заменить `your-domain.com` на ваш домен.

### 4. Перезапустить nginx

```bash
docker-compose -f docker/docker-compose.yml restart nginx
```

---

## Бэкап и восстановление

### Автоматический бэкап
```bash
# Из приложения: вкладка "Системные функции" → "Создать бэкап"
```

### Ручной бэкап
```bash
docker-compose -f docker/docker-compose.yml exec -T db pg_dump -U user workday_db > backup.sql
```

### Восстановление
```bash
cat backup.sql | docker-compose -f docker/docker-compose.yml exec -T db psql -U user -d workday_db
```

---

## Безопасность

### Что сделать обязательно:

1. **Сменить пароли в .env**
2. **Не хранить .env в публичном доступе**
3. **Настроить Firewall**
```bash
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

4. **Автопродление SSL** — certbot настроен на автоматическое продление каждые 6 часов

5. **Регулярные бэкапы**
```bash
# Добавить в crontab
0 2 * * * /home/user/work-tracker/scripts/stop.sh
```

---

## Возможные проблемы

### Контейнер не запускается
```bash
docker-compose -f docker/docker-compose.yml logs admin
```

### Нет доступа к базе
```bash
docker-compose -f docker/docker-compose.yml exec db psql -U user -d workday_db
```

### Nginx ошибка
```bash
docker-compose -f docker/docker-compose.yml logs nginx
```

### Очистка и перезапуск
```bash
docker-compose -f docker/docker-compose.yml down -v
docker-compose -f docker/docker-compose.yml up -d --build
```

---

## Контакты для поддержки

При возникновении проблем:
1. Проверить логи: `docker-compose -f docker/docker-compose.yml logs`
2. Проверить .env настройки
3. Перезапустить: `./scripts/stop.sh && ./scripts/start.sh`
