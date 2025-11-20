#!/bin/bash

# Скрипт для запуска всех mock-сервисов
# Использование: ./run_mocks.sh

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Получаем директорию скрипта
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "🔍 Поиск mock-сервисов в папке services..."
echo "============================================================"

# Проверяем наличие uvicorn
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден!${NC}"
    exit 1
fi

# Экспортируем PYTHONPATH (добавляем корневую директорию проекта для ADK агента)
export PYTHONPATH="${SCRIPT_DIR}:${SCRIPT_DIR}/services:${PYTHONPATH}"

# Настройки ADK агента
ADK_AGENT_PATH="services/agent_for_ai_matching"
ADK_AGENT_PORT=8000  # Порт по умолчанию для ADK

# Массив для хранения PID процессов
PIDS=()

# Функция для остановки всех процессов
cleanup() {
    echo -e "\n\n${YELLOW}🛑 Останавливаю все сервисы...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait
    echo -e "${GREEN}✅ Все сервисы остановлены${NC}"
    exit 0
}

# Регистрируем обработчик сигналов
trap cleanup SIGINT SIGTERM

# Запускаем сервисы
start_service() {
    local service_name=$1
    local service_dir=$2
    local port=$3
    
    if [ "$port" -eq 80 ]; then
        echo -e "${YELLOW}⚠️  ВНИМАНИЕ: Порт 80 требует root-прав!${NC}"
    fi
    
    echo -e "${GREEN}🚀 Запускаю ${service_name} на порту ${port}...${NC}"
    
    cd "$service_dir"
    python3 -m uvicorn server:app --host 0.0.0.0 --port "$port" --reload > /tmp/mock_${service_name}.log 2>&1 &
    local pid=$!
    PIDS+=("$pid")
    cd "$SCRIPT_DIR"
    
    sleep 1
}

# Запускаем найденные сервисы
if [ -d "services/atsservice/ats_server" ]; then
    start_service "atsservice" "services/atsservice/ats_server" 80
fi

if [ -d "services/ai_matching_service/ai_matching_server" ]; then
    start_service "ai_matching_service" "services/ai_matching_service/ai_matching_server" 8001
fi

if [ -d "services/calling_agent" ]; then
    start_service "calling_agent" "services/calling_agent" 8002
fi

# Запускаем ADK агента (без указания порта - используется дефолтный 8000)
echo -e "${GREEN}🚀 Запускаю ADK агента (${ADK_AGENT_PATH})...${NC}"
echo -e "   Адрес: http://127.0.0.1:${ADK_AGENT_PORT} (по умолчанию)"
python3 -m adk api_server "${ADK_AGENT_PATH}" > /tmp/mock_adk_agent.log 2>&1 &
ADK_PID=$!
PIDS+=("$ADK_PID")
sleep 2

if [ ${#PIDS[@]} -eq 0 ]; then
    echo -e "${RED}❌ Сервисы не найдены!${NC}"
    exit 1
fi

echo ""
echo "============================================================"
echo -e "${GREEN}✅ Все сервисы запущены!${NC}"
echo "============================================================"
echo ""
echo "Запущенные сервисы:"
echo "  • atsservice: http://localhost:80"
echo "  • ai_matching_service: http://localhost:8001"
echo "  • calling_agent: http://localhost:8002"
echo "  • ADK Agent (${ADK_AGENT_PATH}): http://127.0.0.1:${ADK_AGENT_PORT}"
echo ""
echo "💡 Нажмите Ctrl+C для остановки всех сервисов"
echo "📋 Логи сохраняются в /tmp/mock_*.log"
echo ""

# Ждём завершения процессов
wait

