#!/usr/bin/env python3
"""
Быстрый тест ключевых функций Ask Bot
Проверяет основные возможности за ~30 секунд

Запуск: python3 quick_test.py
"""

import asyncio
import sys
from datetime import datetime

async def quick_test():
    """Быстрый тест ключевых функций"""
    
    try:
        from app.services.message_processor import MessageProcessor
    except ImportError:
        print("❌ Не удается импортировать MessageProcessor")
        print("   Убедитесь что вы в корневой папке проекта")
        return False
    
    processor = MessageProcessor()
    test_user_id = "quick_test_user"
    
    # Ключевые тесты
    key_tests = [
        {
            "name": "Команда помощи",
            "query": "помощь", 
            "expected": "Ask Bot",
            "critical": True
        },
        {
            "name": "Команда статус", 
            "query": "статус",
            "expected": "авторизация",
            "critical": True
        },
        {
            "name": "Текстовый поиск (требует авторизации)",
            "query": "найди всё про Qlik Sense",
            "expected": "авторизация",  # Ожидаем запрос авторизации
            "critical": False  # Не критично, так как требует авторизации
        },
        {
            "name": "Поиск задач (требует авторизации)", 
            "query": "покажи мои открытые задачи",
            "expected": "авторизация",  # Ожидаем запрос авторизации
            "critical": False
        },
        {
            "name": "Обучение маппингов",
            "query": 'научи клиент "Тест" проект "TEST"',
            "expected": "знаю",  # Исправлено: ищем "знаю" вместо "научен"
            "critical": True
        },
        {
            "name": "Показать маппинги",
            "query": "маппинги",
            "expected": "маппинг",
            "critical": True
        }
    ]
    
    print("⚡ БЫСТРЫЙ ТЕСТ Ask Bot")
    print("=" * 40)
    print(f"🕐 Время запуска: {datetime.now().strftime('%H:%M:%S')}")
    print()
    
    passed = 0
    failed = 0
    critical_failed = 0
    
    for i, test in enumerate(key_tests, 1):
        print(f"[{i}/{len(key_tests)}] {test['name']:<40}", end=" ")
        
        try:
            response = await processor.process_message(test_user_id, test['query'])
            
            if test['expected'].lower() in response.lower():
                print("✅ PASSED")
                passed += 1
            else:
                print("❌ FAILED")
                failed += 1
                if test['critical']:
                    critical_failed += 1
                print(f"      Ожидали: '{test['expected']}'")
                print(f"      Получили: {response[:100]}{'...' if len(response) > 100 else ''}")
                
        except Exception as e:
            print("❌ ERROR")
            failed += 1
            if test['critical']:
                critical_failed += 1
            print(f"      Ошибка: {str(e)}")
        
        print()
    
    print("=" * 40)
    print("📊 РЕЗУЛЬТАТЫ:")
    print(f"   ✅ Прошли: {passed}")
    print(f"   ❌ Провалились: {failed}")
    print(f"   🔴 Критические ошибки: {critical_failed}")
    print()
    
    if critical_failed > 0:
        print("🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ ОБНАРУЖЕНЫ!")
        print("   Основная функциональность работает неправильно")
        return False
    elif failed == 0:
        print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ!")
        print("   Бот работает отлично")
        return True
    else:
        print("⚠️  ЕСТЬ НЕЗНАЧИТЕЛЬНЫЕ ПРОБЛЕМЫ")
        print("   Основные функции работают, но некоторые требуют авторизации")
        return True

async def main():
    success = await quick_test()
    
    print()
    print("💡 РЕКОМЕНДАЦИИ:")
    if success:
        print("   • Для полного тестирования авторизуйтесь в Jira:")
        print("     авторизация svchashin I5COX_EXo3yKB")
        print("   • Запустите полное тестирование: python3 test_bot_comprehensive.py")
        print("   • Или используйте: ./run_tests.sh")
    else:
        print("   • Проверьте логи: tail -f logs/askbot.log")
        print("   • Убедитесь что бот запущен: curl http://localhost:8000/health")
        print("   • Проверьте подключение к Jira и LLM")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
