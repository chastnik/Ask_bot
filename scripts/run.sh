#!/bin/bash

# Ask Bot - скрипт запуска для Unix систем (Linux/macOS)
# Проверяет и устанавливает все зависимости, настраивает окружение

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
    echo "   Ask Bot - Универсальный чат-бот для Jira"
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
    
    # Обновляем pip и устанавливаем базовые пакеты (критично для Python 3.13+)
    print_info "Обновляем pip и базовые пакеты для Python 3.13+..."
    pip install --upgrade pip setuptools>=70.0.0 wheel>=0.42.0
    
    # Проверяем успешность установки
    if [ $? -ne 0 ]; then
        print_error "Ошибка установки базовых пакетов"
        exit 1
    fi
    
    # Устанавливаем зависимости
    if [ -f "requirements.txt" ]; then
        print_info "Устанавливаем пакеты из requirements.txt..."
        pip install -r requirements.txt
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
            print_warning "Файл .env не найден"
            echo -n "Создать .env файл из шаблона? (y/N): "
            read -r create_env
            if [[ $create_env =~ ^[Yy]$ ]]; then
                cp env.example .env
                print_success "Файл .env создан из шаблона"
                print_warning "⚠️  ВАЖНО: Отредактируйте .env файл с вашими настройками!"
                echo "   Особенно важны:"
                echo "   - MATTERMOST_URL и MATTERMOST_TOKEN"
                echo "   - JIRA_BASE_URL"
                echo "   - LLM_PROXY_URL"
                echo
            else
                print_warning "Приложение может не работать без .env конфигурации"
            fi
        else
            print_error "Ни .env, ни env.example файлы не найдены!"
        fi
    else
        print_success "Файл .env найден"
    fi
}

# Проверка внешних зависимостей
check_external_deps() {
    print_info "Проверяем внешние зависимости..."
    
    # Проверяем Redis (если не используется Docker)
    if ! command -v redis-server &> /dev/null && ! command -v docker &> /dev/null; then
        print_warning "Redis Server не найден. Убедитесь, что Redis запущен или используйте Docker"
    fi
    
    # Проверяем Docker
    if command -v docker &> /dev/null; then
        print_success "Docker найден"
        if command -v docker-compose &> /dev/null; then
            print_success "Docker Compose найден"
            echo -n "Запустить через Docker Compose? (y/N): "
            read -r use_docker
            if [[ $use_docker =~ ^[Yy]$ ]]; then
                print_info "Запускаем через Docker Compose..."
                docker-compose up -d
                print_success "Приложение запущено в Docker контейнерах"
                print_info "API доступно на: http://localhost:8000"
                print_info "Для остановки используйте: docker-compose down"
                exit 0
            fi
        fi
    fi
}

# Инициализация базы данных
init_database() {
    print_info "Проверяем состояние базы данных..."
    
    if [ -f "scripts/init_db.py" ]; then
        echo -n "Инициализировать базу данных? (y/N): "
        read -r init_db
        if [[ $init_db =~ ^[Yy]$ ]]; then
            print_info "Инициализируем базу данных..."
            $PYTHON_CMD scripts/init_db.py
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
    
    # Запускаем с автоперезагрузкой в режиме разработки
    if command -v uvicorn &> /dev/null; then
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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
    check_external_deps
    init_database
    start_app
}

# Обработка сигналов
trap 'print_info "Получен сигнал завершения. Останавливаем приложение..."; exit 0' INT TERM

# Запуск
main "$@" 