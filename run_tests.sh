#!/bin/bash

# Скрипт для запуска комплексного тестирования Ask Bot

echo "🚀 Ask Bot - Комплексное тестирование"
echo "======================================"
echo ""

# Показываем помощь если запрошена
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "📖 ИСПОЛЬЗОВАНИЕ:"
    echo "   ./run_tests.sh           - Интерактивный режим"
    echo "   ./run_tests.sh --auth    - С авторизацией в Jira" 
    echo "   ./run_tests.sh --no-auth - Без авторизации (базовые тесты)"
    echo ""
    echo "📋 ПРЯМОЙ ЗАПУСК:"
    echo "   python3 test_bot_comprehensive.py --auth"
    echo "   python3 test_bot_comprehensive.py --login user --password pass"
    echo "   python3 test_bot_comprehensive.py --no-auth"
    echo ""
    exit 0
fi

# Проверяем что виртуальная среда активна
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Виртуальная среда не активна. Активируем..."
    source venv/bin/activate
fi

# Проверяем что бот запущен
echo "🔍 Проверяем что бот запущен..."
curl -s http://localhost:8000/health > /dev/null
if [ $? -ne 0 ]; then
    echo "❌ Бот не запущен! Запустите бот командой:"
    echo "   ./scripts/run.sh"
    echo ""
    exit 1
fi

echo "✅ Бот работает"
echo ""

# Проверяем зависимости
echo "📦 Проверяем зависимости..."
python3 -c "import asyncio, json" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Отсутствуют зависимости"
    exit 1
fi

echo "✅ Зависимости готовы"
echo ""

# Запускаем тесты
echo "🧪 Запускаем комплексное тестирование..."
echo ""

# Проверяем аргументы
if [ "$1" = "--auth" ] || [ "$1" = "-a" ]; then
    echo "🔐 Запуск с авторизацией в Jira..."
    python3 test_bot_comprehensive.py --auth
elif [ "$1" = "--no-auth" ] || [ "$1" = "-n" ]; then
    echo "⚡ Запуск без авторизации (только базовые тесты)..."
    python3 test_bot_comprehensive.py --no-auth
else
    echo "💡 Запуск в интерактивном режиме..."
    python3 test_bot_comprehensive.py
fi

TEST_RESULT=$?

echo ""
echo "======================================"

if [ $TEST_RESULT -eq 0 ]; then
    echo "🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО!"
    echo "   Все тесты прошли ✅"
else
    echo "⚠️  ТЕСТИРОВАНИЕ ЗАВЕРШЕНО С ОШИБКАМИ"
    echo "   Некоторые тесты провалились ❌"
    echo ""
    echo "💡 Рекомендации:"
    echo "   • Проверьте логи: tail -f logs/askbot.log"
    echo "   • Убедитесь что вы авторизованы в Jira"
    echo "   • Проверьте результаты в test_results_*.json"
fi

echo ""
echo "📊 Файлы результатов:"
ls -la test_results_*.json 2>/dev/null | tail -3

exit $TEST_RESULT
