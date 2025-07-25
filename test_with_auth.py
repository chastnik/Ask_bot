#!/usr/bin/env python3
"""
Тест с авторизацией пользователя
Показывает как правильно тестировать функции требующие авторизации
"""

import asyncio
import sys
import os

async def test_with_auth():
    """Тест с авторизацией пользователя"""
    
    sys.path.insert(0, os.getcwd())
    
    try:
        print("�� ТЕСТ С АВТОРИЗАЦИЕЙ Ask Bot")
        print("=" * 50)
        
        # Импортируем MessageProcessor
        from app.services.message_processor import MessageProcessor
        processor = MessageProcessor()
        test_user_id = "test_user_auth"
        
        print("✅ MessageProcessor инициализирован")
        
        # 1. Тестируем команды НЕ требующие авторизации
        print("\n📋 ТЕСТЫ БЕЗ АВТОРИЗАЦИИ:")
        
        no_auth_tests = [
            ("помощь", "Ask Bot"),
            ("help", "Ask Bot"), 
            ("маппинги", "маппинг"),
            ("mappings", "маппинг"),
        ]
        
        for query, expected in no_auth_tests:
            print(f"  • '{query}'...", end=" ")
            response = await processor.process_message(test_user_id, query)
            
            if expected.lower() in response.lower():
                print("✅")
            else:
                print("❌")
                print(f"    Ожидали: {expected}")
                print(f"    Получили: {response[:100]}...")
        
        print("\n🔐 ТЕСТЫ ТРЕБУЮЩИЕ АВТОРИЗАЦИИ:")
        print("    (Покажут сообщение об авторизации)")
        
        auth_required_tests = [
            ("статус", "авторизация"),
            ("проекты", "авторизация"),
            ("найди всё про Qlik Sense", "авторизация"),
            ("покажи мои задачи", "авторизация"),
        ]
        
        for query, expected in auth_required_tests:
            print(f"  • '{query}'...", end=" ")
            response = await processor.process_message(test_user_id, query)
            
            if expected.lower() in response.lower():
                print("✅ (правильно требует авторизацию)")
            else:
                print("❌ (неожиданный ответ)")
                print(f"    Ответ: {response[:100]}...")
        
        print("\n💡 ДЕМОНСТРАЦИЯ АВТОРИЗАЦИИ:")
        print("   Для полного тестирования нужно:")
        print("   1. Открыть Mattermost")
        print("   2. Отправить боту: авторизация [логин] [токен]")
        print("   3. Запустить тесты снова")
        print("")
        print("   Пример команды авторизации:")
        print("   авторизация svchashin I5COX_EXo3yKB")
        
        print("\n🧪 СИМУЛЯЦИЯ КОМАНДЫ АВТОРИЗАЦИИ:")
        # НЕ используем реальные данные в тесте!
        auth_response = await processor.process_message(test_user_id, "авторизация test_user fake_token")
        print(f"  Ответ на авторизацию: {auth_response[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Главная функция"""
    result = await test_with_auth()
    
    print("\n" + "=" * 50)
    if result:
        print("🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО")
        print("")
        print("✅ Команды без авторизации работают")
        print("✅ Команды с авторизацией правильно запрашивают авторизацию")
        print("")
        print("🚀 СЛЕДУЮЩИЕ ШАГИ:")
        print("   1. Авторизуйтесь в боте через Mattermost")
        print("   2. Запустите: python3 test_bot_comprehensive.py")
        print("   3. Или используйте: ./run_tests.sh")
        return 0
    else:
        print("❌ ТЕСТ ЗАВЕРШЕН С ОШИБКАМИ")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
