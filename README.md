# Ask Bot - Универсальный чат-бот для Jira

Умный бот для интеграции с Jira в Mattermost с поддержкой аналитики, визуализации и RAG-системы.

## 🚀 Возможности

- **🤖 Интеллектуальное понимание запросов** - обработка естественного языка с помощью локальной LLM
- **📊 Автоматическая аналитика** - генерация JQL запросов и анализ данных Jira
- **📈 Визуализация данных** - создание графиков и диаграмм по запросу
- **🔐 Безопасная авторизация** - поддержка ролевого доступа к Jira
- **⚡ Кеширование** - быстрые ответы на частые запросы через Redis
- **🧠 RAG-система** - контекстное понимание клиентов, проектов и шаблонов
- **💬 Slash-команды** - удобное взаимодействие через Mattermost

## 🏗️ Архитектура

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Mattermost    │────│   FastAPI Bot    │────│      Jira       │
│  (Slash команды)│    │   (Middleware)   │    │   (REST API)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ├── Redis (Кеш)
                              ├── SQLite (RAG база)
                              ├── LLM Прокси
                              └── Plotly (Графики)
```

## 📋 Требования

- Python 3.8+ (скрипты автоматически проверят версию)
- Redis Server (опционально, можно запустить через Docker)
- Доступ к Jira (API Token)
- Доступ к Mattermost (Bot Token)
- Локальная LLM через прокси (Ollama, OpenAI-совместимый API)

## 🛠️ Быстрый запуск

### 🚀 Автоматический запуск (рекомендуется)

```bash
# Клонирование репозитория
git clone https://github.com/chastnik/Ask_bot.git
cd Ask_bot

# Быстрый запуск для демонстрации
./scripts/quick-start.sh

# Или полная настройка с проверкой зависимостей
./scripts/run.sh
```

**Скрипты автоматически:**
- ✅ Проверят и установят Python 3.8+
- ✅ Создадут виртуальное окружение
- ✅ Установят все зависимости
- ✅ Настроят конфигурацию из шаблона
- ✅ Инициализируют базу данных с примерами
- ✅ Запустят приложение

### 🪟 Для Windows

```cmd
# Запуск из командной строки
scripts\run.bat
```

### 🐳 Docker Compose (продакшн)

```bash
docker-compose up -d
```

## 🔧 Ручная установка

### 1. Клонирование репозитория

```bash
git clone https://github.com/chastnik/Ask_bot.git
cd Ask_bot
```

### 2. Установка зависимостей

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# или venv\Scripts\activate.bat для Windows

pip install -r requirements.txt
```

### 3. Настройка переменных окружения

Создайте файл `.env` на основе `env.example`:

```bash
# Mattermost настройки
MATTERMOST_URL=https://mm.1bit.support
MATTERMOST_TOKEN=your_mattermost_bot_token
BOT_NAME=ask_bot
MATTERMOST_TEAM_ID=your_team_id
MATTERMOST_SSL_VERIFY=false

# Jira настройки  
JIRA_URL=https://jira.1solution.ru

# LLM настройки
LLM_PROXY_TOKEN=your_llm_proxy_token
LLM_BASE_URL=https://llm.1bitai.ru
LLM_MODEL=qwen3:14b

# База данных
DATABASE_URL=sqlite:///./askbot.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Общие настройки
LOG_LEVEL=INFO
SECRET_KEY=your-secret-key-here
DEBUG=false

# Настройки приложения  
HOST=0.0.0.0
PORT=8000

# RAG настройки
EMBEDDING_MODEL=all-MiniLM-L6-v2
MAX_CONTEXT_LENGTH=4000

# График настройки
CHART_SAVE_PATH=./charts/
CHART_URL_PREFIX=http://localhost:8000/charts/
```

### 4. Инициализация базы данных

```bash
# Автоматическая инициализация с примерами данных
python scripts/init_db.py

# Или вручную
cp env.example .env
# Отредактируйте .env файл своими настройками
```

### 5. Запуск приложения

```bash
# Запуск с автоперезагрузкой
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

📚 **Подробная документация по скриптам:** [scripts/README.md](scripts/README.md)

### 🔗 После запуска доступно:

- 🌐 **API**: http://localhost:8000
- 📚 **Документация API**: http://localhost:8000/docs
- 💓 **Health Check**: http://localhost:8000/health
- 📊 **Статистика кеша**: http://localhost:8000/cache/stats
- 🔧 **Debug LLM**: http://localhost:8000/debug/llm/test
- 🎫 **Debug Jira**: http://localhost:8000/debug/jira/test

## 🐳 Docker развертывание

### Быстрый запуск

```bash
docker-compose up -d
```

### Ручная сборка

```bash
# Сборка образа
docker build -t ask-bot .

# Запуск контейнера
docker run -d \
  --name ask-bot \
  -p 8000:8000 \
  -v $(pwd)/askbot.db:/app/askbot.db \
  -v $(pwd)/charts:/app/charts \
  --env-file .env \
  ask-bot
```

## 🎯 Использование

### Первая настройка в Mattermost

1. **Создание бота в Mattermost:**
   - Перейдите в System Console → Integrations → Bot Accounts
   - Создайте нового бота с именем `ask_bot`
   - Скопируйте токен в переменную `MATTERMOST_TOKEN`

2. **Настройка Slash команды:**
   - Перейдите в Team Settings → Integrations → Slash Commands
   - Создайте команду `/jira` с URL: `http://your-server:8000/webhooks/slash`

3. **Первый запуск:**
   ```
   /jira help
   ```

### Авторизация в Jira

При первом использовании бот запросит учетные данные Jira:

```
/jira auth
```

Бот предложит ввести:
- Имя пользователя Jira
- API Token (рекомендуется) или пароль

### Примеры запросов

#### 📊 Аналитические запросы

```
/jira Сколько задач было создано по клиенту Иль-Де-Ботэ в июле?
/jira Какие задачи сейчас в статусе 'In Progress' у команды сопровождения?
/jira Сколько часов списали все сотрудники по проекту Visiology в мае?
```

#### 📈 Запросы с визуализацией

```
/jira Покажи график списания часов по Сергею Журавлёву за последние 3 месяца
/jira Диаграмма задач по статусам по клиенту Бургер-Кинг за июнь
/jira Распределение задач по типам (Bug, Task, Epic) в июле
```

#### 🔍 Поисковые запросы

```
/jira Были ли просроченные задачи по проекту Битрикс в июне?
/jira Какие задачи были открыты более 30 дней назад и до сих пор не решены?
/jira Кто из сотрудников в июне работал больше всего над задачами клиента Летуаль?
```

#### ⚡ Команды управления

```
/jira help           # Справка по командам
/jira auth           # Настройка авторизации Jira
/jira status         # Статус сервисов
/jira cache clear    # Очистка кеша
/jira projects       # Список доступных проектов
```

## 🎨 Типы графиков

Бот автоматически выбирает подходящий тип графика или вы можете указать явно:

- **📊 Столбчатые диаграммы** - для сравнения количественных данных
- **📈 Линейные графики** - для временных рядов
- **🥧 Круговые диаграммы** - для распределения по категориям
- **📝 Таблицы** - для детальных данных
- **📍 Точечные диаграммы** - для корреляционного анализа

## 🔧 Продвинутые настройки

### RAG-система

Бот использует базу знаний для лучшего понимания контекста:

```python
# Добавление клиента в базу знаний
from app.models.database import Client
from sqlalchemy.orm import Session

client = Client(
    name="Новый Клиент",
    jira_key="NC",
    description="Описание проекта клиента"
)
```

### Шаблоны запросов

Создание готовых шаблонов для частых запросов:

```python
from app.models.database import QueryTemplate

template = QueryTemplate(
    name="Задачи по клиенту за месяц",
    description="Получить все задачи клиента за указанный месяц",
    template='project = "{project}" AND created >= "{start_date}" AND created <= "{end_date}"',
    category="analytics",
    chart_type="bar"
)
```

### Кастомизация графиков

```python
# Настройка цветовой схемы
chart_config = {
    "color_scheme": "jira",  # jira, professional, warm, cool
    "show_values": True,
    "height": 600,
    "width": 1000
}
```

## 📊 Мониторинг и отладка

### Логи

```bash
# Просмотр логов
tail -f logs/askbot.log

# Уровень логирования в .env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

### Метрики кеша

```
/jira cache stats
```

### Проверка сервисов

```
/jira status
```

## 🛡️ Безопасность

### Шифрование паролей

Пароли и токены пользователей шифруются перед сохранением в базе данных.

### Ограничения доступа

- Каждый пользователь видит только те проекты, к которым у него есть доступ в Jira
- Кеш изолирован по пользователям
- Логи не содержат чувствительной информации

### Рекомендации

1. Используйте API токены Jira вместо паролей
2. Настройте HTTPS для продакшн развертывания
3. Регулярно обновляйте зависимости
4. Ограничьте сетевой доступ к Redis

## 🔄 Обновление

```bash
# Остановка сервиса
docker-compose down

# Обновление кода
git pull origin main

# Обновление зависимостей
pip install -r requirements.txt

# Миграция базы данных (при необходимости)
# python migrations/migrate.py

# Перезапуск
docker-compose up -d
```

## 🐛 Устранение неполадок

### Частые проблемы

1. **Ошибка подключения к Redis**
   ```bash
   # Проверить статус Redis
   redis-cli ping
   # Ответ должен быть: PONG
   ```

2. **Ошибка авторизации Jira**
   ```
   /jira auth  # Повторная настройка
   ```

3. **LLM не отвечает**
   - Проверьте доступность LLM прокси
   - Убедитесь в корректности токена

4. **Графики не создаются**
   - Проверьте права на запись в директорию `charts/`
   - Установите `kaleido` для Plotly

### Логи отладки

```bash
# Включить подробные логи
export LOG_LEVEL=DEBUG

# Просмотр логов FastAPI
uvicorn app.main:app --log-level debug
```

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменения (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 📞 Поддержка

- **Документация:** [Wiki](https://github.com/your-repo/wiki)
- **Issues:** [GitHub Issues](https://github.com/your-repo/issues)
- **Чат поддержки:** [Mattermost Channel]

## 🙏 Благодарности

- [FastAPI](https://fastapi.tiangolo.com/) - веб-фреймворк
- [Plotly](https://plotly.com/python/) - визуализация данных
- [Jira REST API](https://developer.atlassian.com/server/jira/platform/rest-apis/)
- [Mattermost API](https://api.mattermost.com/)

---

**Ask Bot** - делаем работу с Jira проще и нагляднее! 🚀 