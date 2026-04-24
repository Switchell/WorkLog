#!/bin/bash
# AXIS ERP PRO - Запуск

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && cd .. && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  # shellcheck source=/dev/null
  . ./.env
  set +a
fi

echo "🚀 Запуск AXIS ERP PRO..."

# Создание бэкапа перед запуском (опционально)
if [ -d "backups" ]; then
    echo "📦 Создаю резервную копию базы..."
    if [ -f .env ]; then
      docker compose --env-file .env -f docker/docker-compose.yml exec -T db pg_dump -U "${DB_USER:-user}" "${DB_NAME:-workday_db}" > "backups/pre_start_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null || true
    else
      docker compose -f docker/docker-compose.yml exec -T db pg_dump -U user workday_db > "backups/pre_start_$(date +%Y%m%d_%H%M%S).sql" 2>/dev/null || true
    fi
fi

# Запуск (корневой .env — одинаковые DB_* для db, приложений и Grafana)
if [ -f .env ]; then
  docker compose --env-file .env -f docker/docker-compose.yml up -d
else
  docker compose -f docker/docker-compose.yml up -d
fi

echo ""
echo "✅ AXIS запущен!"
echo "   Основное приложение: http://localhost/   (и напрямую :8502)"
echo "   Клиентский портал:  http://localhost/client/"
echo "   Grafana:             http://localhost:3001"
echo "   База данных:         localhost:5432"
echo ""
echo "Для остановки: ./scripts/stop.sh"
