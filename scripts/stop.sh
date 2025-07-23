#!/bin/bash

# Ask Bot - скрипт остановки для Unix систем (Linux/macOS)
# Останавливает все запущенные экземпляры Ask Bot

set -e  # Остановить выполнение при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для цветного вывода
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "🛑 ==============================================="
    echo "   Ask Bot - Остановка приложения"
    echo "===============================================${NC}"
    echo
}

# Остановка экземпляров Ask Bot
stop_ask_bot() {
    print_info "Поиск запущенных экземпляров Ask Bot..."
    
    # Ищем процессы uvicorn с нашим приложением
    RUNNING_PIDS=$(ps aux | grep -E "uvicorn.*app\.main:app" | grep -v grep | awk '{print $2}')
    
    if [ -z "$RUNNING_PIDS" ]; then
        print_info "Запущенные экземпляры Ask Bot не найдены"
    else
        print_warning "Найдены запущенные экземпляры Ask Bot:"
        ps aux | grep -E "uvicorn.*app\.main:app" | grep -v grep | while read line; do
            echo "   $line"
        done
        echo
        
        echo -n "Остановить все найденные экземпляры? (Y/n): "
        read -r confirm_stop
        
        if [[ ! $confirm_stop =~ ^[Nn]$ ]]; then
            print_info "Останавливаем экземпляры Ask Bot..."
            
            for pid in $RUNNING_PIDS; do
                print_info "Отправляем SIGTERM процессу $pid..."
                kill -TERM $pid 2>/dev/null || true
            done
            
            # Ждем 5 секунд для корректного завершения
            print_info "Ожидаем корректного завершения процессов (5 сек)..."
            sleep 5
            
            # Проверяем, какие процессы еще работают
            STILL_RUNNING=$(ps aux | grep -E "uvicorn.*app\.main:app" | grep -v grep | awk '{print $2}')
            
            if [ ! -z "$STILL_RUNNING" ]; then
                print_warning "Некоторые процессы не завершились, принудительно останавливаем..."
                for pid in $STILL_RUNNING; do
                    print_info "Отправляем SIGKILL процессу $pid..."
                    kill -KILL $pid 2>/dev/null || true
                done
                sleep 1
            fi
            
            # Финальная проверка
            FINAL_CHECK=$(ps aux | grep -E "uvicorn.*app\.main:app" | grep -v grep | awk '{print $2}')
            if [ -z "$FINAL_CHECK" ]; then
                print_success "Все экземпляры Ask Bot успешно остановлены"
            else
                print_error "Не удалось остановить некоторые процессы: $FINAL_CHECK"
                exit 1
            fi
        else
            print_info "Остановка отменена пользователем"
        fi
    fi
}

# Остановка процессов на порту 8000
stop_port_8000() {
    print_info "Проверяем занятость порта 8000..."
    
    if command -v lsof &> /dev/null; then
        PORT_PROCESSES=$(lsof -ti :8000 2>/dev/null || true)
        
        if [ ! -z "$PORT_PROCESSES" ]; then
            print_warning "Найдены процессы на порту 8000:"
            lsof -i :8000 2>/dev/null || true
            echo
            
            echo -n "Остановить процессы на порту 8000? (Y/n): "
            read -r confirm_port
            
            if [[ ! $confirm_port =~ ^[Nn]$ ]]; then
                print_info "Останавливаем процессы на порту 8000..."
                
                for pid in $PORT_PROCESSES; do
                    print_info "Останавливаем процесс $pid..."
                    kill -TERM $pid 2>/dev/null || true
                    sleep 2
                    
                    if kill -0 $pid 2>/dev/null; then
                        print_warning "Принудительно останавливаем процесс $pid..."
                        kill -KILL $pid 2>/dev/null || true
                    fi
                done
                
                print_success "Процессы на порту 8000 остановлены"
            fi
        else
            print_success "Порт 8000 свободен"
        fi
    else
        print_warning "Команда lsof не найдена. Используйте 'netstat -ln | grep :8000' для проверки порта"
    fi
}

# Остановка Docker контейнеров
stop_docker() {
    if command -v docker-compose &> /dev/null && [ -f "docker-compose.yml" ]; then
        echo -n "Остановить Docker контейнеры Ask Bot? (y/N): "
        read -r stop_docker_containers
        
        if [[ $stop_docker_containers =~ ^[Yy]$ ]]; then
            print_info "Останавливаем Docker контейнеры..."
            docker-compose down
            print_success "Docker контейнеры остановлены"
        fi
    fi
}

# Показать статус
show_status() {
    print_info "Текущий статус Ask Bot:"
    echo
    
    # Проверяем процессы
    ASK_BOT_PROCESSES=$(ps aux | grep -E "uvicorn.*app\.main:app" | grep -v grep || true)
    if [ -z "$ASK_BOT_PROCESSES" ]; then
        print_success "Ask Bot процессы: не запущены"
    else
        print_warning "Ask Bot процессы: найдены запущенные экземпляры"
        echo "$ASK_BOT_PROCESSES"
    fi
    
    # Проверяем порт
    if command -v lsof &> /dev/null; then
        PORT_STATUS=$(lsof -i :8000 2>/dev/null || true)
        if [ -z "$PORT_STATUS" ]; then
            print_success "Порт 8000: свободен"
        else
            print_warning "Порт 8000: занят"
            echo "$PORT_STATUS"
        fi
    fi
    
    # Проверяем Docker
    if command -v docker-compose &> /dev/null && [ -f "docker-compose.yml" ]; then
        DOCKER_STATUS=$(docker-compose ps 2>/dev/null || true)
        if echo "$DOCKER_STATUS" | grep -q "Up"; then
            print_warning "Docker контейнеры: запущены"
            echo "$DOCKER_STATUS"
        else
            print_success "Docker контейнеры: остановлены"
        fi
    fi
}

# Основная функция
main() {
    print_header
    
    case "${1:-stop}" in
        "stop")
            stop_ask_bot
            stop_port_8000
            stop_docker
            echo
            print_success "🛑 Остановка завершена"
            ;;
        "status")
            show_status
            ;;
        "port")
            stop_port_8000
            ;;
        "docker")
            stop_docker
            ;;
        "help"|"-h"|"--help")
            echo "Использование: $0 [команда]"
            echo
            echo "Команды:"
            echo "  stop    - Остановить все экземпляры Ask Bot (по умолчанию)"
            echo "  status  - Показать статус запущенных процессов"
            echo "  port    - Остановить только процессы на порту 8000"
            echo "  docker  - Остановить только Docker контейнеры"
            echo "  help    - Показать эту справку"
            ;;
        *)
            print_error "Неизвестная команда: $1"
            print_info "Используйте '$0 help' для справки"
            exit 1
            ;;
    esac
}

# Запуск
main "$@" 