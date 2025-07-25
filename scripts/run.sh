#!/bin/bash

# Ask Bot - автоматический запуск
# Проверяет зависимости и запускает приложение без вопросов

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
    echo "🤖 ==============================================="
    echo "   Ask Bot - Автоматический запуск"
    echo "===============================================${NC}"
    echo
}

# Проверка Python
check_python() {
    print_info "Проверяем наличие Python..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        print_success "Python найден: $PYTHON_VERSION"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
        PYTHON_VERSION=$(python --version | cut -d' ' -f2)
        print_success "Python найден: $PYTHON_VERSION"
    else
        print_error "Python не найден! Установите Python 3.8+ с https://python.org"
        exit 1
    fi
    
    # Проверяем минимальную версию
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Требуется Python 3.8+, найдена версия $PYTHON_VERSION"
        exit 1
    fi
}

# Создание и активация виртуального окружения
setup_venv() {
    print_info "Настраиваем виртуальное окружение..."
    
    if [ ! -d "venv" ]; then
        print_info "Создаем виртуальное окружение..."
        $PYTHON_CMD -m venv venv
        print_success "Виртуальное окружение создано"
    fi
    
    print_info "Активируем виртуальное окружение..."
    source venv/bin/activate
    print_success "Виртуальное окружение активировано"
}

# Установка зависимостей
install_dependencies() {
    print_info "Проверяем и устанавливаем зависимости..."
    
    # Обновляем pip и устанавливаем базовые пакеты
    print_info "Обновляем pip и базовые пакеты..."
    pip install --upgrade pip setuptools wheel --quiet
    
    # Устанавливаем зависимости
    if [ -f "requirements.txt" ]; then
        print_info "Устанавливаем пакеты из requirements.txt..."
        pip install -r requirements.txt --quiet
        print_success "Зависимости установлены"
    else
        print_error "Файл requirements.txt не найден!"
        exit 1
    fi
}

# Проверка конфигурации
check_config() {
    print_info "Проверяем конфигурацию..."
    
    if [ ! -f ".env" ]; then
        if [ -f "env.example" ]; then
            print_warning "Файл .env не найден, создаем из шаблона..."
            cp env.example .env
            print_success "Файл .env создан из шаблона"
            print_warning "⚠️  ВАЖНО: Отредактируйте .env файл с вашими настройками!"
        else
            print_error "Ни .env, ни env.example файлы не найдены!"
            exit 1
        fi
    else
        print_success "Файл .env найден"
    fi
}

# Завершение запущенных процессов
stop_running_processes() {
    print_info "Проверяем запущенные экземпляры..."
    
    # Завершаем процессы uvicorn с нашим приложением
    RUNNING_PIDS=$(ps aux | grep -E "uvicorn.*app\.main:app" | grep -v grep | awk '{print $2}' || true)
    
    if [ ! -z "$RUNNING_PIDS" ]; then
        print_info "Завершаем существующие экземпляры Ask Bot..."
        for pid in $RUNNING_PIDS; do
            kill -TERM $pid 2>/dev/null || true
        done
        sleep 2
        print_success "Существующие экземпляры завершены"
    fi
    
    # Освобождаем порт 8000
    if command -v lsof &> /dev/null; then
        PORT_PROCESS=$(lsof -ti :8000 2>/dev/null || true)
        if [ ! -z "$PORT_PROCESS" ]; then
            print_info "Освобождаем порт 8000..."
            kill -TERM $PORT_PROCESS 2>/dev/null || true
            sleep 1
            print_success "Порт 8000 освобожден"
        fi
    fi
}





# Запуск приложения
start_app() {
    print_info "Запускаем Ask Bot..."
    echo
    print_success "🚀 Приложение запускается..."
    print_info "API будет доступно на: http://localhost:8000"
    print_info "Документация API: http://localhost:8000/docs"
    print_info "Для остановки нажмите Ctrl+C"
    echo
    
    if command -v uvicorn &> /dev/null; then
        # Запуск в стабильном режиме
        print_info "Запуск в стабильном режиме..."
        uvicorn app.main:app --host 0.0.0.0 --port 8000
    else
        print_error "uvicorn не найден! Установите его: pip install uvicorn"
        exit 1
    fi
}

# Основная функция
main() {
    print_header
    
    # Проверяем, что мы в правильной директории
    if [ ! -f "app/main.py" ]; then
        print_error "Скрипт должен запускаться из корневой директории проекта Ask Bot"
        exit 1
    fi
    
    check_python
    setup_venv
    install_dependencies
    check_config
    stop_running_processes
    start_app
}

# Обработка сигналов
trap 'print_info "Получен сигнал завершения. Останавливаем приложение..."; exit 0' INT TERM

# Запуск
main "$@" 