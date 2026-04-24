#!/bin/bash
# AXIS ERP PRO - Остановка

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  . ./.env
  set +a
fi

echo "🛑 Остановка AXIS ERP PRO..."

# Создание бэкапа перед остановкой
if [ -d "backups" ]; then
    echo "📦 Создаю резервную копию базы..."
    mkdir -p backups
    if [ -f .env ]; then
      docker compose --env-file .env -f docker/docker-compose.yml exec -T db pg_dump -U "${DB_USER:-user}" "${DB_NAME:-workday_db}" > "backups/backup_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null
    else
      docker compose -f docker/docker-compose.yml exec -T db pg_dump -U user workday_db > "backups/backup_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null
    fi
    echo "✅ Бэкап сохранён в папку backups/"
fi

# Остановка
if [ -f .env ]; then
  docker compose --env-file .env -f docker/docker-compose.yml down
else
  docker compose -f docker/docker-compose.yml down
fi

echo ""
echo "✅ AXIS остановлен!"
echo "   Данные сохранены в volumes"
echo "   Для запуска: ./scripts/start.sh"
