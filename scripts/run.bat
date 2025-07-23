@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM Ask Bot - скрипт запуска для Windows
REM Проверяет и устанавливает все зависимости, настраивает окружение

title Ask Bot - Универсальный чат-бот для Jira

echo.
echo 🤖 ===============================================
echo    Ask Bot - Универсальный чат-бот для Jira
echo ===============================================
echo.

REM Проверяем, что мы в правильной директории
if not exist "app\main.py" (
    echo ❌ Скрипт должен запускаться из корневой директории проекта Ask Bot
    pause
    exit /b 1
)

REM Проверка Python
echo ℹ️  Проверяем наличие Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python не найден! Установите Python 3.8+ с https://python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python найден: %PYTHON_VERSION%

REM Проверяем версию Python
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if %PYTHON_MAJOR% lss 3 (
    echo ❌ Требуется Python 3.8+, найдена версия %PYTHON_VERSION%
    pause
    exit /b 1
)

if %PYTHON_MAJOR% equ 3 if %PYTHON_MINOR% lss 8 (
    echo ❌ Требуется Python 3.8+, найдена версия %PYTHON_VERSION%
    pause
    exit /b 1
)

REM Создание и активация виртуального окружения
echo ℹ️  Настраиваем виртуальное окружение...

if not exist "venv" (
    echo ℹ️  Создаем виртуальное окружение...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo ❌ Ошибка создания виртуального окружения
        pause
        exit /b 1
    )
    echo ✅ Виртуальное окружение создано
)

echo ℹ️  Активируем виртуальное окружение...
call venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo ❌ Ошибка активации виртуального окружения
    pause
    exit /b 1
)
echo ✅ Виртуальное окружение активировано

REM Установка зависимостей
echo ℹ️  Проверяем и устанавливаем зависимости...

REM Обновляем pip
python -m pip install --upgrade pip >nul 2>&1

REM Устанавливаем зависимости
if exist "requirements.txt" (
    echo ℹ️  Устанавливаем пакеты из requirements.txt...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ❌ Ошибка установки зависимостей
        pause
        exit /b 1
    )
    echo ✅ Зависимости установлены
) else (
    echo ❌ Файл requirements.txt не найден!
    pause
    exit /b 1
)

REM Проверка конфигурации
echo ℹ️  Проверяем конфигурацию...

if not exist ".env" (
    if exist "env.example" (
        echo ⚠️  Файл .env не найден
        set /p create_env="Создать .env файл из шаблона? (y/N): "
        if /i "!create_env!"=="y" (
            copy "env.example" ".env" >nul
            echo ✅ Файл .env создан из шаблона
            echo ⚠️  ВАЖНО: Отредактируйте .env файл с вашими настройками!
            echo    Особенно важны:
            echo    - MATTERMOST_URL и MATTERMOST_TOKEN
            echo    - JIRA_BASE_URL
            echo    - LLM_PROXY_URL
            echo.
        ) else (
            echo ⚠️  Приложение может не работать без .env конфигурации
        )
    ) else (
        echo ❌ Ни .env, ни env.example файлы не найдены!
    )
) else (
    echo ✅ Файл .env найден
)

REM Проверка внешних зависимостей
echo ℹ️  Проверяем внешние зависимости...

REM Проверяем Docker
docker --version >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Docker найден
    docker-compose --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Docker Compose найден
        set /p use_docker="Запустить через Docker Compose? (y/N): "
        if /i "!use_docker!"=="y" (
            echo ℹ️  Запускаем через Docker Compose...
            docker-compose up -d
            if %errorlevel% equ 0 (
                echo ✅ Приложение запущено в Docker контейнерах
                echo ℹ️  API доступно на: http://localhost:8000
                echo ℹ️  Для остановки используйте: docker-compose down
                pause
                exit /b 0
            )
        )
    )
) else (
    echo ⚠️  Docker не найден. Запускаем в обычном режиме...
)

REM Инициализация базы данных
echo ℹ️  Проверяем состояние базы данных...

if exist "scripts\init_db.py" (
    set /p init_db="Инициализировать базу данных? (y/N): "
    if /i "!init_db!"=="y" (
        echo ℹ️  Инициализируем базу данных...
        python scripts\init_db.py
    )
)

REM Запуск приложения
echo ℹ️  Запускаем Ask Bot...
echo.
echo ✅ 🚀 Приложение запускается...
echo ℹ️  API будет доступно на: http://localhost:8000
echo ℹ️  Документация API: http://localhost:8000/docs
echo ℹ️  Для остановки нажмите Ctrl+C
echo.

REM Проверяем наличие uvicorn
pip show uvicorn >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uvicorn не найден! Устанавливаем...
    pip install uvicorn
)

REM Запускаем с автоперезагрузкой в режиме разработки
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause 