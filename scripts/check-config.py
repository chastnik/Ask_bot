#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации Ask Bot

Проверяет:
- Наличие .env файла
- Заполненность обязательных настроек
- Доступность внешних сервисов
- Корректность настроек
"""

import os
import sys
import asyncio
from pathlib import Path

# Добавляем корневую директорию в путь для импорта
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from app.config import settings
from app.services.mattermost_service import MattermostService
from app.services.jira_service import JiraService

def print_section(title: str):
    """Печатает заголовок секции"""
    print(f"\n{'='*50}")
    print(f"🔍 {title}")
    print('='*50)

def print_success(message: str):
    """Печатает сообщение об успехе"""
    print(f"✅ {message}")

def print_error(message: str):
    """Печатает сообщение об ошибке"""
    print(f"❌ {message}")

def print_warning(message: str):
    """Печатает предупреждение"""
    print(f"⚠️  {message}")

def check_env_file():
    """Проверяет наличие .env файла"""
    print_section("Проверка .env файла")
    
    env_path = root_dir / ".env"
    env_example_path = root_dir / "env.example"
    
    if env_path.exists():
        print_success(f".env файл найден: {env_path}")
        
        # Проверяем размер файла
        file_size = env_path.stat().st_size
        if file_size < 100:
            print_warning(f".env файл очень мал ({file_size} байт). Возможно, он не заполнен.")
        else:
            print_success(f"Размер .env файла: {file_size} байт")
            
    else:
        print_error(f".env файл не найден: {env_path}")
        
        if env_example_path.exists():
            print_warning(f"Найден пример: {env_example_path}")
            print_warning("Скопируйте env.example в .env и заполните настройки:")
            print_warning(f"cp {env_example_path} {env_path}")
        else:
            print_error("Файл env.example тоже не найден!")
        
        return False
    
    return True

def check_required_settings():
    """Проверяет обязательные настройки"""
    print_section("Проверка обязательных настроек")
    
    required_settings = {
        'mattermost_url': ('URL Mattermost сервера', 'https://'),
        'mattermost_token': ('Токен Mattermost бота', None),
        'mattermost_team_id': ('ID команды в Mattermost', None),
        'jira_base_url': ('URL Jira сервера', 'https://'),
    }
    
    all_good = True
    
    for setting_name, (description, expected_prefix) in required_settings.items():
        value = getattr(settings, setting_name, '')
        
        if not value:
            print_error(f"{setting_name}: не задан ({description})")
            all_good = False
        elif expected_prefix and not value.startswith(expected_prefix):
            print_warning(f"{setting_name}: возможно неверный формат. Ожидается: {expected_prefix}...")
            print(f"   Текущее значение: {value[:50]}...")
        else:
            # Скрываем токены для безопасности
            if 'token' in setting_name.lower():
                display_value = value[:8] + '*' * (len(value) - 8) if len(value) > 8 else value
            else:
                display_value = value
            print_success(f"{setting_name}: {display_value}")
    
    return all_good

def check_optional_settings():
    """Проверяет опциональные настройки"""
    print_section("Проверка опциональных настроек")
    
    optional_settings = {
        'llm_proxy_url': 'URL LLM сервиса',
        'redis_url': 'URL Redis сервера',
        'database_url': 'URL базы данных',
    }
    
    for setting_name, description in optional_settings.items():
        value = getattr(settings, setting_name, '')
        if value:
            print_success(f"{setting_name}: {value}")
        else:
            print_warning(f"{setting_name}: не задан ({description})")

async def check_services():
    """Проверяет доступность внешних сервисов"""
    print_section("Проверка доступности сервисов")
    
    # Проверка Mattermost
    print("🔗 Проверка подключения к Mattermost...")
    try:
        mattermost = MattermostService()
        result = await mattermost.test_connection()
        if result:
            print_success("Mattermost: подключение успешно")
        else:
            print_error("Mattermost: ошибка подключения")
    except Exception as e:
        print_error(f"Mattermost: {str(e)}")
    
    # Проверка Jira (без учетных данных)
    print("🔗 Проверка доступности Jira...")
    try:
        jira = JiraService()
        # Простая проверка доступности URL
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.jira_base_url}/rest/api/2/serverInfo",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in [200, 401, 403]:  # 401/403 означают что сервер доступен
                    print_success("Jira: сервер доступен")
                else:
                    print_warning(f"Jira: неожиданный статус {response.status}")
    except Exception as e:
        print_error(f"Jira: {str(e)}")
    
    # Проверка Redis
    print("🔗 Проверка подключения к Redis...")
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        print_success("Redis: подключение успешно")
    except Exception as e:
        print_error(f"Redis: {str(e)}")

def check_directories():
    """Проверяет необходимые директории"""
    print_section("Проверка директорий")
    
    directories = {
        'charts': settings.charts_dir,
        'logs': './logs'
    }
    
    for dir_name, dir_path in directories.items():
        path = Path(dir_path)
        if path.exists():
            print_success(f"Директория {dir_name}: {path} (существует)")
        else:
            print_warning(f"Директория {dir_name}: {path} (будет создана автоматически)")

def print_summary(has_env: bool, has_required: bool):
    """Печатает итоговую сводку"""
    print_section("Итоговая сводка")
    
    if has_env and has_required:
        print_success("Конфигурация выглядит корректно!")
        print_success("Ask Bot готов к запуску.")
        print("\n🚀 Запустите бота командой:")
        print("   ./scripts/quick-start.sh")
        print("   или")
        print("   ./scripts/run.sh")
    else:
        print_error("Найдены проблемы с конфигурацией!")
        print("\n🔧 Что нужно сделать:")
        
        if not has_env:
            print("   1. Создайте .env файл из примера:")
            print("      cp env.example .env")
        
        if not has_required:
            print("   2. Заполните обязательные настройки в .env файле")
            print("   3. Получите токены для Mattermost и настройте Jira")
        
        print("\n📚 Подробные инструкции в README.md")

async def main():
    """Основная функция проверки"""
    print("🤖 Ask Bot - Проверка конфигурации")
    print(f"📁 Рабочая директория: {root_dir}")
    
    # Проверяем .env файл
    has_env = check_env_file()
    
    # Проверяем настройки
    has_required = check_required_settings()
    check_optional_settings()
    
    # Проверяем директории
    check_directories()
    
    # Проверяем сервисы (только если базовые настройки есть)
    if has_env and has_required:
        await check_services()
    
    # Итоговая сводка
    print_summary(has_env, has_required)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Проверка прервана пользователем")
    except Exception as e:
        print(f"\n\n❌ Неожиданная ошибка: {e}")
        sys.exit(1) 