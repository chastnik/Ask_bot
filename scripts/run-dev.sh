#!/bin/bash

# Ask Bot - запуск в режиме разработки с автоперезагрузкой
# ВНИМАНИЕ: Используйте только для разработки! Может вызывать циклы перезагрузки.

set -e

echo "🚧 Запуск Ask Bot в режиме разработки..."
echo "⚠️  ВНИМАНИЕ: Этот режим предназначен только для разработки"
echo "⚠️  При проблемах используйте ./scripts/run.sh"
echo

# Активируем виртуальное окружение
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Виртуальное окружение активировано"
else
    echo "❌ Виртуальное окружение не найдено! Запустите ./scripts/run.sh"
    exit 1
fi

# Запуск с автоперезагрузкой
echo "🚀 Запуск с автоперезагрузкой..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
    --reload-dir="app" \
    --reload-exclude="venv/**/*" \
    --reload-exclude=".venv/**/*" \
    --reload-exclude="*.egg-info/**/*" \
    --reload-exclude="__pycache__/**/*"
