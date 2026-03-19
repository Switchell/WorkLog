#!/bin/bash
# AXIS ERP PRO - Запуск

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Запуск AXIS ERP PRO..."

# Создание бэкапа перед запуском (опционально)
if [ -d "backups" ]; then
    echo "📦 Создаю резервную копию базы..."
    docker-compose -f docker/docker-compose.yml exec -T db pg_dump -U user workday_db > "backups/pre_start_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null || true
fi

# Запуск
docker-compose -f docker/docker-compose.yml up -d

echo ""
echo "✅ AXIS запущен!"
echo "   Основное приложение: http://localhost:8501"
echo "   Клиентский портал:   http://localhost:8502"
echo "   Grafana:            http://localhost:3001"
echo "   База данных:         localhost:5432"
echo ""
echo "Для остановки: ./scripts/stop.sh"
