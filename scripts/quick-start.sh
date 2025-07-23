#!/bin/bash

# Ask Bot - Скрипт быстрого запуска
# Запускает приложение с минимальными настройками для тестирования

set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "🚀 ========================================"
    echo "   Ask Bot - Быстрый запуск"
    echo "========================================${NC}"
    echo
}

quick_setup() {
    print_header
    
    print_info "Быстрая настройка для тестирования Ask Bot..."
    print_warning "Это упрощенная версия для демонстрации функций"
    echo
    
    # Создаем минимальный .env файл
    if [ ! -f ".env" ]; then
        print_info "Создаем базовую конфигурацию..."
        cat > .env << EOF
# Ask Bot - Быстрая конфигурация
APP_MODE=development
SECRET_KEY=demo-secret-key-for-testing-only
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO

# Минимальные настройки для демо
MATTERMOST_URL=http://localhost:8065
MATTERMOST_TOKEN=demo-token
MATTERMOST_BOT_USERNAME=askbot

JIRA_BASE_URL=https://demo.atlassian.net

LLM_PROXY_URL=http://localhost:11434
LLM_MODEL_NAME=llama2
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE=0.3

DATABASE_URL=sqlite:///./askbot_demo.db
DATABASE_AUTO_CREATE=true

REDIS_URL=redis://localhost:6379/0
CACHE_TTL=3600

CHARTS_DIR=./charts
CHARTS_FORMAT=png

DEFAULT_TIMEZONE=Europe/Moscow
DEFAULT_LANGUAGE=ru
EOF
        print_success "Базовая конфигурация создана"
    fi
    
    # Устанавливаем зависимости
    print_info "Устанавливаем зависимости..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    print_info "Обновляем pip и базовые пакеты для Python 3.13+..."
    pip install --upgrade pip setuptools>=70.0.0 wheel>=0.42.0 > /dev/null 2>&1
    print_info "Устанавливаем зависимости проекта..."
    pip install -r requirements.txt > /dev/null 2>&1
    print_success "Зависимости установлены"
    
    # Инициализируем базу данных с примерами
    print_info "Инициализируем базу данных с примерами данных..."
    python scripts/init_db.py <<< "y"
    print_success "База данных готова"
    
    # Запускаем приложение
    print_info "Запускаем Ask Bot в режиме демонстрации..."
    echo
    print_success "🎉 Ask Bot запущен в демо-режиме!"
    print_info "API доступно на: http://localhost:8000"
    print_info "Документация: http://localhost:8000/docs"
    print_info "Health check: http://localhost:8000/health"
    echo
    print_warning "📝 Это демо-версия. Для продакшн используйте полную настройку:"
    print_warning "   1. Настройте Mattermost интеграцию"
    print_warning "   2. Подключите реальный Jira сервер"
    print_warning "   3. Настройте локальную LLM"
    print_warning "   4. Настройте Redis для кеширования"
    echo
    print_info "Для остановки нажмите Ctrl+C"
    
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
}

# Проверяем, что мы в правильной директории
if [ ! -f "app/main.py" ]; then
    echo "❌ Скрипт должен запускаться из корневой директории проекта Ask Bot"
    exit 1
fi

quick_setup 