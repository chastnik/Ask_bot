#!/usr/bin/env python3
"""Простой тест для диагностики"""

import asyncio
import sys

async def simple_test():
    print("🧪 Простой тест Ask Bot")
    print("=" * 30)
    
    try:
        from app.services.message_processor import MessageProcessor
        print("✅ MessageProcessor импортирован")
        
        processor = MessageProcessor()
        print("✅ MessageProcessor создан")
        
        # Простой тест команды помощи
        response = await processor.process_message("test_user", "помощь")
        print(f"✅ Команда помощи выполнена")
        print(f"📝 Длина ответа: {len(response)} символов")
        
        if "Ask Bot" in response:
            print("✅ Ответ содержит 'Ask Bot'")
            return True
        else:
            print("❌ Ответ НЕ содержит 'Ask Bot'")
            print(f"Ответ: {response[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(simple_test())
        print()
        if result:
            print("🎉 Простой тест ПРОШЕЛ")
            sys.exit(0)
        else:
            print("❌ Простой тест ПРОВАЛИЛСЯ")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
