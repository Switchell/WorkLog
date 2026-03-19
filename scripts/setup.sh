#!/bin/bash
# AXIS ERP PRO - Установка на сервер
# Запускать: chmod +x setup.sh && ./setup.sh

set -e

echo "=========================================="
echo "AXIS ERP PRO - Установка"
echo "=========================================="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Устанавливаю..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
fi

# Проверка Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен."
    sudo apt update
    sudo apt install -y docker-compose
fi

# Проверка .env
if [ ! -f .env ]; then
    echo "⚠️ Файл .env не найден. Создаю..."
    cat > .env << 'EOF'
# AXIS ERP - Настройки

# База данных
DB_USER=user
DB_PASSWORD=CHANGE_THIS_PASSWORD
DB_NAME=workday_db
DB_HOST=db
DB_PORT=5432

# Telegram
TG_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
TG_ADMIN_ID=YOUR_CHAT_ID
LOG_FILE=axis_errors.log

# Дополнительные пользователи (логин:хеш:роль)
# ADDITIONAL_USERS=ivanov:$2b$12$xxx:user
EOF
    echo "✅ Файл .env создан. ОТРЕДАКТИРУЙТЕ ЕГО!"
fi

# Проверка паролей
source .env 2>/dev/null || true
if [ "$DB_PASSWORD" = "CHANGE_THIS_PASSWORD" ] || [ "$DB_PASSWORD" = "password" ]; then
    echo "⚠️ ВНИМАНИЕ: Используются стандартные пароли!"
    echo "   Измените пароли в файле .env"
fi

echo ""
echo "=========================================="
echo "✅ Установка завершена!"
echo "=========================================="
echo ""
echo "Далее:"
echo "1. Отредактируйте .env файл"
echo "2. Запустите: ./start.sh"
echo "3. Откройте: http://ваш_сервер:8501"
echo ""
