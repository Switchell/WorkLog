#!/bin/bash
# AXIS ERP PRO - Остановка

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
cd "$SCRIPT_DIR"

echo "🛑 Остановка AXIS ERP PRO..."

# Создание бэкапа перед остановкой
if [ -d "backups" ]; then
    echo "📦 Создаю резервную копию базы..."
    mkdir -p backups
    docker-compose -f docker/docker-compose.yml exec -T db pg_dump -U user workday_db > "backups/backup_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null
    echo "✅ Бэкап сохранён в папку backups/"
fi

# Остановка
docker-compose -f docker/docker-compose.yml down

echo ""
echo "✅ AXIS остановлен!"
echo "   Данные сохранены в volumes"
echo "   Для запуска: ./scripts/start.sh"
