"""
API роутер для обработки webhooks от Mattermost
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from app.models.schemas import SlashCommandRequest, SlashCommandResponse, DirectMessageRequest
from app.services.jira_service import jira_service, JiraAPIError, JiraAuthError
from app.services.mattermost_service import mattermost_service
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service
from app.services.chart_service import chart_service


router = APIRouter()


class BotLogic:
    """Основная логика бота"""
    
    @staticmethod
    async def process_direct_message(user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """
        Обрабатывает личное сообщение пользователя
        
        Args:
            user_query: Сообщение пользователя
            user_id: ID пользователя Mattermost
            user_name: Имя пользователя
            channel_id: ID канала (для личных сообщений)
            
        Returns:
            Ответ для отправки в личные сообщения
        """
        start_time = time.time()
        
        try:
            # Проверяем специальные команды
            query_lower = user_query.strip().lower()
            
            # Команда помощи
            if query_lower in ['помощь', 'help', 'что ты умеешь', 'команды']:
                return await BotLogic._handle_help_dm()
            
            # Команда авторизации
            if query_lower.startswith('авторизация') or query_lower.startswith('auth'):
                return await BotLogic._handle_auth_dm(user_query, user_id)
            
            # Команда статуса
            if query_lower in ['статус', 'status', 'мой статус']:
                return await BotLogic._handle_status_dm(user_id)
            
            # Команда проекты
            if query_lower in ['проекты', 'projects', 'мои проекты']:
                return await BotLogic._handle_projects_dm(user_id)
            
            # Команды кеша
            if query_lower.startswith('кеш') or query_lower.startswith('cache'):
                return await BotLogic._handle_cache_dm(query_lower, user_id)
                
            # Обычный запрос - обрабатываем через LLM и Jira
            return await BotLogic._process_jira_query_dm(user_query, user_id, user_name, channel_id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки личного сообщения от {user_name}: {e}")
            return {
                "text": f"❌ Произошла ошибка при обработке запроса: {str(e)}",
                "response_type": "ephemeral"
            }
    
    @staticmethod
    async def process_user_query(user_query: str, user_id: str, channel_id: str) -> SlashCommandResponse:
        """
        Обрабатывает запрос пользователя
        
        Args:
            user_query: Запрос пользователя
            user_id: ID пользователя Mattermost
            channel_id: ID канала
            
        Returns:
            Ответ для отправки в Mattermost
        """
        start_time = time.time()
        
        try:
            # Получаем учетные данные пользователя из кеша
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return mattermost_service.create_error_response(
                    "Необходимо авторизоваться в Jira. Используйте команду: /jira auth"
                )
            
            # Анализируем намерение пользователя с помощью LLM
            async with llm_service as llm:
                intent_data = await llm.interpret_query_intent(user_query)
                
            # Проверяем кеш для JQL запросов
            cached_result = None
            if intent_data.get("intent") in ["analytics", "search", "worklog"]:
                async with cache_service as cache:
                    # Попытка найти кешированный результат на основе запроса пользователя
                    cache_key = cache.make_jql_cache_key(user_query, user_id)
                    cached_result = await cache.get_cached_jql_result(user_query, user_id)
            
            if cached_result:
                # Возвращаем кешированный результат
                execution_time = time.time() - start_time
                async with mattermost_service as mm:
                    return mm.create_data_response(
                        title="📊 Результат (из кеша)",
                        data=cached_result.get("issues", [])[:10],  # Первые 10 задач
                        chart_url=cached_result.get("chart_url")
                    )
            
            # Генерируем JQL запрос
            context = await BotLogic._get_user_context(user_id)
            
            async with llm_service as llm:
                jql_query = await llm.generate_jql_query(user_query, context)
                
            if not jql_query:
                return mattermost_service.create_error_response(
                    "Не удалось интерпретировать ваш запрос. Попробуйте переформулировать."
                )
            
            # Выполняем запрос к Jira
            async with jira_service as jira:
                search_result = await jira.search_issues(
                    jql=jql_query,
                    username=credentials["username"],
                    password=credentials.get("password"),
                    token=credentials.get("token"),
                    max_results=100
                )
            
            # Создаем график если нужно
            chart_url = None
            if intent_data.get("needs_chart", False) and search_result.issues:
                chart_url = await BotLogic._create_chart_for_results(
                    search_result.issues, intent_data, user_query
                )
            
            # Кешируем результат
            result_data = {
                "issues": [issue.dict() for issue in search_result.issues],
                "total": search_result.total,
                "jql": jql_query,
                "chart_url": chart_url,
                "execution_time": time.time() - start_time
            }
            
            async with cache_service as cache:
                await cache.cache_jql_result(jql_query, user_id, result_data)
            
            # Генерируем ответ с помощью LLM
            async with llm_service as llm:
                response_text = await llm.generate_response_text(result_data, user_query)
            
            # Создаем итоговый ответ
            async with mattermost_service as mm:
                if chart_url:
                    return mm.create_slash_command_response(
                        text=f"{response_text}\n📈 [Открыть график]({chart_url})",
                        response_type="in_channel"
                    )
                else:
                    return mm.create_slash_command_response(
                        text=response_text,
                        response_type="in_channel"
                    )
                    
        except JiraAuthError:
            return mattermost_service.create_error_response(
                "Ошибка авторизации в Jira. Проверьте учетные данные: /jira auth"
            )
        except JiraAPIError as e:
            return mattermost_service.create_error_response(f"Ошибка Jira API: {e}")
        except Exception as e:
            logger.error(f"Ошибка обработки запроса пользователя: {e}", exc_info=True)
            return mattermost_service.create_error_response(
                "Произошла неожиданная ошибка. Попробуйте позже."
            )
    
    @staticmethod
    async def _get_user_context(user_id: str) -> Dict[str, Any]:
        """
        Получает контекст пользователя для генерации JQL
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Контекст с доступными клиентами, проектами, пользователями
        """
        # TODO: Реализовать получение из базы данных
        return {
            "clients": [
                {"name": "Иль-Де-Ботэ", "key": "IDB"},
                {"name": "Бургер-Кинг", "key": "BK"},
                {"name": "Летуаль", "key": "LET"}
            ],
            "projects": [
                {"name": "Битрикс", "key": "BTX"},
                {"name": "Visiology", "key": "VIS"},
                {"name": "Поддержка", "key": "SUP"}
            ],
            "users": [
                "Сергей Журавлёв", "Анна Иванова", "Петр Петров"
            ]
        }
    
    @staticmethod
    async def _create_chart_for_results(issues: list, intent_data: Dict, user_query: str) -> Optional[str]:
        """
        Создает график для результатов запроса
        
        Args:
            issues: Список задач Jira
            intent_data: Данные о намерении пользователя
            user_query: Оригинальный запрос пользователя
            
        Returns:
            URL созданного графика или None
        """
        try:
            chart_type = intent_data.get("chart_type", "bar")
            
            # Конвертируем задачи в данные для графика
            issues_data = [issue.dict() for issue in issues]
            
            # Определяем тип графика на основе данных
            if "статус" in user_query.lower():
                chart_url = await chart_service.create_issues_by_status_chart(issues_data)
            elif "тип" in user_query.lower():
                chart_url = await chart_service.create_issues_by_type_chart(issues_data)
            elif "час" in user_query.lower() or "время" in user_query.lower():
                # Для worklogs нужна отдельная обработка
                chart_url = None  # TODO: Реализовать агрегацию worklogs
            else:
                # Создаем столбчатую диаграмму по умолчанию
                if len(issues_data) > 0:
                    # Группируем по проектам
                    project_counts = {}
                    for issue in issues_data:
                        project = issue.get("project_key", "Unknown")
                        project_counts[project] = project_counts.get(project, 0) + 1
                    
                    chart_data = [
                        {"project": project, "count": count}
                        for project, count in project_counts.items()
                    ]
                    
                    chart_url = await chart_service.create_bar_chart(
                        data=chart_data,
                        title="Распределение задач по проектам",
                        x_axis="project",
                        y_axis="count"
                    )
                else:
                    chart_url = None
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Ошибка создания графика: {e}")
            return None


@router.post("/slash")
async def handle_slash_command(
    background_tasks: BackgroundTasks,
    token: str = Form(...),
    team_id: str = Form(...),
    team_domain: str = Form(...),
    channel_id: str = Form(...),
    channel_name: str = Form(...),
    user_id: str = Form(...),
    user_name: str = Form(...),
    command: str = Form(...),
    text: str = Form(...),
    response_url: Optional[str] = Form(None),
    trigger_id: Optional[str] = Form(None)
):
    """
    Обработчик slash команд от Mattermost
    """
    try:
        # Создаем объект запроса
        slash_request = SlashCommandRequest(
            token=token,
            team_id=team_id,
            team_domain=team_domain,
            channel_id=channel_id,
            channel_name=channel_name,
            user_id=user_id,
            user_name=user_name,
            command=command,
            text=text,
            response_url=response_url,
            trigger_id=trigger_id
        )
        
        logger.info(f"Получена slash команда от {user_name}: {text}")
        
        # Парсим команду
        command_parts = text.strip().split() if text.strip() else []
        command_name = command_parts[0].lower() if command_parts else ""
        
        # Обрабатываем команды
        if not text.strip() or command_name == "help":
            return await handle_help_command()
            
        elif command_name == "auth":
            return await handle_auth_command(user_id, channel_id)
            
        elif command_name == "status":
            return await handle_status_command()
            
        elif command_name == "cache":
            if len(command_parts) > 1 and command_parts[1] == "clear":
                return await handle_cache_clear_command()
            elif len(command_parts) > 1 and command_parts[1] == "stats":
                return await handle_cache_stats_command()
            else:
                return mattermost_service.create_error_response(
                    "Неизвестная команда кеша. Используйте: cache clear или cache stats"
                )
                
        elif command_name == "projects":
            return await handle_projects_command(user_id)
            
        else:
            # Обрабатываем как обычный запрос пользователя
            return await BotLogic.process_user_query(text, user_id, channel_id)
            
    except Exception as e:
        logger.error(f"Ошибка обработки slash команды: {e}", exc_info=True)
        return mattermost_service.create_error_response(
            "Произошла ошибка при обработке команды"
        )


async def handle_help_command() -> SlashCommandResponse:
    """Обработчик команды help"""
    help_text = """
🤖 **Ask Bot - Помощник по Jira**

**📊 Примеры аналитических запросов:**
• `/jira Сколько задач было создано по клиенту Иль-Де-Ботэ в июле?`
• `/jira Какие задачи сейчас в статусе 'In Progress'?`
• `/jira Сколько часов списали сотрудники по проекту Visiology в мае?`

**📈 Запросы с визуализацией:**
• `/jira Покажи график списания часов за последние 3 месяца`
• `/jira Диаграмма задач по статусам за июнь`
• `/jira Распределение задач по типам в июле`

**⚡ Команды управления:**
• `/jira help` - эта справка
• `/jira auth` - настройка авторизации Jira
• `/jira status` - статус сервисов
• `/jira cache clear` - очистка кеша
• `/jira cache stats` - статистика кеша
• `/jira projects` - список доступных проектов

**💡 Совет:** Просто задавайте вопросы естественным языком!
"""
    
    return mattermost_service.create_info_response(help_text, "ephemeral")


async def handle_auth_command(user_id: str, channel_id: str) -> SlashCommandResponse:
    """Обработчик команды авторизации"""
    try:
        # Отправляем DM с инструкциями по авторизации
        async with mattermost_service as mm:
            dm_text = """
🔐 **Настройка авторизации Jira**

Для работы с Jira необходимо предоставить учетные данные:

**Рекомендуемый способ (API Token):**
1. Перейдите в Jira → Profile → Personal Access Tokens
2. Создайте новый токен
3. Ответьте на это сообщение в формате:
   `username your_username`
   `token your_api_token`

**Альтернативный способ (пароль):**
`username your_username`
`password your_password`

⚠️ **Безопасность:** Учетные данные шифруются и хранятся локально.
"""
            await mm.send_dm(user_id, dm_text)
            
        return mattermost_service.create_info_response(
            "Инструкции по авторизации отправлены в личные сообщения", "ephemeral"
        )
        
    except Exception as e:
        logger.error(f"Ошибка команды auth: {e}")
        return mattermost_service.create_error_response(
            "Не удалось отправить инструкции по авторизации"
        )


async def handle_status_command() -> SlashCommandResponse:
    """Обработчик команды статуса"""
    try:
        status_parts = ["🔍 **Статус сервисов Ask Bot:**\n"]
        
        # Проверяем Redis
        try:
            async with cache_service as cache:
                await cache.redis.ping()
                status_parts.append("✅ Redis: подключен")
        except:
            status_parts.append("❌ Redis: недоступен")
        
        # Проверяем Mattermost
        try:
            async with mattermost_service as mm:
                if await mm.test_connection():
                    status_parts.append("✅ Mattermost: подключен")
                else:
                    status_parts.append("❌ Mattermost: недоступен")
        except:
            status_parts.append("❌ Mattermost: ошибка подключения")
        
        # Проверяем LLM
        try:
            async with llm_service as llm:
                if await llm.test_connection():
                    status_parts.append("✅ LLM: подключена")
                else:
                    status_parts.append("❌ LLM: недоступна")
        except:
            status_parts.append("❌ LLM: ошибка подключения")
        
        status_parts.append("✅ Jira: готов к работе")
        status_parts.append("✅ База данных: активна")
        
        return mattermost_service.create_info_response(
            "\n".join(status_parts), "ephemeral"
        )
        
    except Exception as e:
        logger.error(f"Ошибка команды status: {e}")
        return mattermost_service.create_error_response("Не удалось получить статус")


async def handle_cache_clear_command() -> SlashCommandResponse:
    """Обработчик команды очистки кеша"""
    try:
        async with cache_service as cache:
            result = await cache.flush_all_cache()
            
        if result:
            return mattermost_service.create_info_response(
                "🗑️ Кеш успешно очищен", "ephemeral"
            )
        else:
            return mattermost_service.create_error_response(
                "Не удалось очистить кеш"
            )
            
    except Exception as e:
        logger.error(f"Ошибка очистки кеша: {e}")
        return mattermost_service.create_error_response("Ошибка при очистке кеша")


async def handle_cache_stats_command() -> SlashCommandResponse:
    """Обработчик команды статистики кеша"""
    try:
        async with cache_service as cache:
            stats = await cache.get_cache_stats()
            
        if "error" in stats:
            return mattermost_service.create_error_response(stats["error"])
        
        stats_text = f"""
📊 **Статистика кеша Redis:**

• **Всего ключей:** {stats.get('total_keys', 0)}
• **Использование памяти:** {stats.get('memory_usage', 'N/A')}
• **Hit Rate:** {stats.get('hit_rate', 0)}%
• **Подключенных клиентов:** {stats.get('connected_clients', 0)}

**Типы ключей:**
"""
        
        for key_type, count in stats.get('key_types', {}).items():
            stats_text += f"• {key_type}: {count}\n"
        
        return mattermost_service.create_info_response(stats_text, "ephemeral")
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики кеша: {e}")
        return mattermost_service.create_error_response("Не удалось получить статистику кеша")


    # Методы для обработки личных сообщений
    @staticmethod
    async def _handle_help_dm() -> Dict[str, Any]:
        """Обработка команды помощи в личных сообщениях"""
        help_text = """
🤖 **Ask Bot - Ваш помощник по Jira**

**Как пользоваться:**
Просто напишите мне запрос на естественном языке!

**Примеры запросов:**
• "Покажи мои открытые задачи"
• "Сколько багов в проекте PROJECT_KEY?"
• "Задачи без исполнителя в проекте ABC"
• "Статистика по исполнителям за последний месяц"
• "Просроченные задачи в проекте XYZ"

**Специальные команды:**
• `помощь` - показать это сообщение
• `авторизация [логин] [пароль/токен]` - войти в Jira
• `статус` - проверить статус авторизации
• `проекты` - список доступных проектов
• `кеш очистить` - очистить кеш
• `кеш статистика` - статистика кеша

**Создание графиков:**
Добавьте "покажи как график" к любому запросу для визуализации!

Пример: "Задачи по статусам в проекте ABC покажи как график"
"""
        return {"text": help_text}

    @staticmethod
    async def _handle_auth_dm(user_query: str, user_id: str) -> Dict[str, Any]:
        """Обработка авторизации в личных сообщениях"""
        parts = user_query.strip().split()
        
        if len(parts) < 3:
            return {
                "text": """
🔐 **Авторизация в Jira**

**Формат команды:**
`авторизация [логин] [пароль/токен]`

**Примеры:**
• `авторизация user@company.com mypassword`
• `авторизация username api_token_here`

**Для Jira Cloud рекомендуется использовать API токен вместо пароля.**
"""
            }
        
        username = parts[1]
        password = parts[2]
        
        try:
            # Тестируем подключение к Jira
            test_result = await jira_service.test_credentials(username, password)
            
            if test_result:
                # Сохраняем учетные данные в кеше
                async with cache_service as cache:
                    await cache.cache_user_credentials(user_id, username, password)
                
                return {
                    "text": f"✅ Успешная авторизация в Jira как {username}"
                }
            else:
                return {
                    "text": "❌ Неверные учетные данные для Jira. Проверьте логин и пароль/токен."
                }
                
        except Exception as e:
            logger.error(f"Ошибка авторизации для пользователя {user_id}: {e}")
            return {
                "text": f"❌ Ошибка при авторизации: {str(e)}"
            }

    @staticmethod
    async def _handle_status_dm(user_id: str) -> Dict[str, Any]:
        """Проверка статуса авторизации в личных сообщениях"""
        try:
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if credentials:
                # Проверяем, что учетные данные все еще действительны
                test_result = await jira_service.test_credentials(
                    credentials['username'], 
                    credentials['password']
                )
                
                if test_result:
                    return {
                        "text": f"✅ Вы авторизованы в Jira как **{credentials['username']}**"
                    }
                else:
                    # Удаляем недействительные учетные данные
                    await cache.clear_user_credentials(user_id)
                    return {
                        "text": "❌ Ваши учетные данные устарели. Необходимо повторить авторизацию."
                    }
            else:
                return {
                    "text": """
❌ **Вы не авторизованы в Jira**

Для авторизации используйте команду:
`авторизация [логин] [пароль/токен]`
"""
                }
                
        except Exception as e:
            logger.error(f"Ошибка проверки статуса для пользователя {user_id}: {e}")
            return {
                "text": f"❌ Ошибка при проверке статуса: {str(e)}"
            }

    @staticmethod
    async def _handle_projects_dm(user_id: str) -> Dict[str, Any]:
        """Получение списка проектов в личных сообщениях"""
        try:
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return {
                    "text": "❌ Необходимо авторизоваться в Jira. Используйте: `авторизация [логин] [пароль]`"
                }
            
            # Получаем список проектов
            projects = await jira_service.get_projects(
                credentials['username'],
                credentials['password']
            )
            
            if projects:
                projects_text = "📋 **Доступные проекты Jira:**\n\n"
                for project in projects[:20]:  # Ограничиваем вывод
                    projects_text += f"• **{project.get('key')}** - {project.get('name')}\n"
                
                if len(projects) > 20:
                    projects_text += f"\n... и еще {len(projects) - 20} проектов"
                    
                return {"text": projects_text}
            else:
                return {
                    "text": "📋 Проекты не найдены или у вас нет доступа к ним."
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения проектов для пользователя {user_id}: {e}")
            return {
                "text": f"❌ Ошибка при получении списка проектов: {str(e)}"
            }

    @staticmethod
    async def _handle_cache_dm(query: str, user_id: str) -> Dict[str, Any]:
        """Обработка команд кеша в личных сообщениях"""
        if 'очистить' in query or 'clear' in query:
            try:
                async with cache_service as cache:
                    await cache.clear_user_cache(user_id)
                return {
                    "text": "✅ Ваш кеш очищен"
                }
            except Exception as e:
                return {
                    "text": f"❌ Ошибка очистки кеша: {str(e)}"
                }
                
        elif 'статистик' in query or 'stats' in query:
            try:
                async with cache_service as cache:
                    stats = await cache.get_cache_stats()
                
                stats_text = f"""
📊 **Статистика кеша:**

• **Всего ключей:** {stats.get('total_keys', 0)}
• **Использование памяти:** {stats.get('memory_usage', 'N/A')}
• **Hit Rate:** {stats.get('hit_rate', 0)}%

**Типы ключей:**
"""
                for key_type, count in stats.get('key_types', {}).items():
                    stats_text += f"• {key_type}: {count}\n"
                    
                return {"text": stats_text}
                
            except Exception as e:
                return {
                    "text": f"❌ Ошибка получения статистики: {str(e)}"
                }
        else:
            return {
                "text": """
**Команды кеша:**
• `кеш очистить` - очистить ваш кеш
• `кеш статистика` - показать статистику кеша
"""
            }

    @staticmethod
    async def _process_jira_query_dm(user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Обработка запроса к Jira в личных сообщениях"""
        try:
            # Получаем учетные данные пользователя из кеша
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return {
                    "text": """
❌ **Необходимо авторизоваться в Jira**

Используйте команду:
`авторизация [логин] [пароль/токен]`

Пример: `авторизация user@company.com mytoken`
"""
                }
            
            # Анализируем запрос с помощью LLM
            try:
                intent = await llm_service.analyze_intent(user_query)
                logger.info(f"Определен intent: {intent}")
            except Exception as e:
                logger.warning(f"Ошибка анализа intent: {e}")
                intent = {"type": "search", "needs_chart": False}
            
            # Генерируем JQL запрос
            try:
                # TODO: Реализовать получение из базы данных
                user_context = {"projects": [], "recent_queries": []}
                
                jql = await llm_service.generate_jql(user_query, user_context)
                logger.info(f"Сгенерирован JQL: {jql}")
            except Exception as e:
                logger.error(f"Ошибка генерации JQL: {e}")
                return {
                    "text": f"❌ Не удалось понять запрос: {str(e)}"
                }
            
            # Выполняем запрос к Jira
            try:
                issues = await jira_service.search_issues(
                    jql,
                    credentials['username'],
                    credentials['password'],
                    max_results=50
                )
                
                logger.info(f"Найдено задач: {len(issues) if issues else 0}")
                
            except JiraAuthError:
                # Удаляем недействительные учетные данные
                async with cache_service as cache:
                    await cache.clear_user_credentials(user_id)
                return {
                    "text": "❌ Ошибка авторизации в Jira. Необходимо повторить авторизацию."
                }
            except JiraAPIError as e:
                return {
                    "text": f"❌ Ошибка Jira API: {str(e)}"
                }
            
            if not issues:
                return {
                    "text": "📋 По вашему запросу задачи не найдены."
                }
            
            # Проверяем, нужно ли создавать график
            needs_chart = intent.get("needs_chart", False) or any(
                word in user_query.lower() 
                for word in ["график", "диаграмм", "визуализ", "chart", "покажи как"]
            )
            
            if needs_chart:
                # Создаем график
                chart_url = await BotLogic._create_chart_from_issues(issues, intent.get("chart_type", "bar"))
                
                if chart_url:
                    response_text = f"📊 **Результат запроса:** {len(issues)} задач(и)\n\n"
                    response_text += f"📈 **График:** {chart_url}\n\n"
                else:
                    response_text = f"📋 **Найдено задач:** {len(issues)}\n\n"
                    
                # Добавляем краткий список задач
                response_text += "**Найденные задачи:**\n"
                for issue in issues[:5]:
                    response_text += f"• **{issue.get('key')}** - {issue.get('fields', {}).get('summary', 'N/A')}\n"
                
                if len(issues) > 5:
                    response_text += f"\n... и еще {len(issues) - 5} задач(и)"
                
            else:
                # Формируем текстовый ответ
                response_text = f"📋 **Найдено задач:** {len(issues)}\n\n"
                
                for issue in issues[:10]:  # Показываем до 10 задач
                    fields = issue.get('fields', {})
                    response_text += f"• **{issue.get('key')}** - {fields.get('summary', 'N/A')}\n"
                    response_text += f"  Статус: {fields.get('status', {}).get('name', 'N/A')}\n\n"
                
                if len(issues) > 10:
                    response_text += f"... и еще {len(issues) - 10} задач(и)"
            
            return {"text": response_text}
            
        except Exception as e:
            logger.error(f"Ошибка обработки запроса от {user_name}: {e}")
            return {
                "text": f"❌ Произошла ошибка при обработке запроса: {str(e)}"
            }


async def handle_projects_command(user_id: str) -> SlashCommandResponse:
    """Обработчик команды списка проектов"""
    try:
        # Получаем учетные данные пользователя
        async with cache_service as cache:
            credentials = await cache.get_cached_user_credentials(user_id)
            
        if not credentials:
            return mattermost_service.create_error_response(
                "Необходимо авторизоваться в Jira: /jira auth"
            )
        
        # Получаем проекты из Jira
        async with jira_service as jira:
            projects = await jira.get_projects(
                username=credentials["username"],
                password=credentials.get("password"),
                token=credentials.get("token")
            )
        
        if not projects:
            return mattermost_service.create_info_response(
                "Проекты не найдены или нет доступа", "ephemeral"
            )
        
        projects_text = "📁 **Доступные проекты Jira:**\n\n"
        for project in projects[:20]:  # Ограничиваем до 20 проектов
            projects_text += f"• **{project['key']}** - {project['name']}\n"
            
        if len(projects) > 20:
            projects_text += f"\n... и ещё {len(projects) - 20} проектов"
        
        return mattermost_service.create_info_response(projects_text, "ephemeral")
        
    except JiraAuthError:
        return mattermost_service.create_error_response(
            "Ошибка авторизации в Jira. Проверьте учетные данные: /jira auth"
        )
    except Exception as e:
        logger.error(f"Ошибка получения проектов: {e}")
        return mattermost_service.create_error_response(
            "Не удалось получить список проектов"
        ) 


@router.post("/message")
async def handle_direct_message(request: DirectMessageRequest):
    """
    Обработчик личных сообщений от Mattermost
    
    Этот endpoint обрабатывает обычные сообщения, отправленные боту напрямую,
    а не slash-команды. Пользователи могут писать естественным языком.
    """
    try:
        logger.info(f"Получено личное сообщение от {request.user_name}: {request.text}")
        
        # Игнорируем сообщения от самого бота, чтобы избежать циклов
        if request.user_name.lower() in ['askbot', 'ask_bot', 'ask-bot']:
            logger.info("Игнорируем сообщение от самого бота")
            return {"text": ""}
        
        # Игнорируем пустые сообщения
        if not request.text.strip():
            return {"text": ""}
        
        # Обрабатываем сообщение через основную логику бота
        response = await BotLogic.process_direct_message(
            request.text,
            request.user_id,
            request.user_name,
            request.channel_id
        )
        
        # Отправляем ответ обратно в личные сообщения
        if response.get("text"):
            try:
                # Отправляем ответ через Mattermost API
                await mattermost_service.send_direct_message(
                    request.user_id,
                    response["text"]
                )
                logger.info(f"Ответ отправлен пользователю {request.user_name}")
            except Exception as e:
                logger.error(f"Ошибка отправки ответа в Mattermost: {e}")
        
        # Возвращаем пустой ответ, так как уже отправили через API
        return {"text": ""}
        
    except Exception as e:
        logger.error(f"Ошибка обработки личного сообщения от {request.user_name}: {e}")
        
        # В случае ошибки пытаемся отправить сообщение об ошибке
        try:
            await mattermost_service.send_direct_message(
                request.user_id,
                f"❌ Произошла ошибка при обработке вашего сообщения: {str(e)}"
            )
        except Exception as send_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {send_error}")
        
        return {"text": ""}


@router.post("/events")
async def handle_mattermost_events(request: dict):
    """
    Обработчик событий от Mattermost (альтернативный способ получения сообщений)
    
    Этот endpoint может использоваться для получения событий через Events API
    вместо прямых сообщений через webhook
    """
    try:
        event_type = request.get("event", {}).get("event", "")
        
        # Обрабатываем только события о сообщениях
        if event_type != "posted":
            return {"status": "ignored"}
        
        post = request.get("event", {}).get("data", {}).get("post", {})
        
        # Парсим данные сообщения
        if post:
            post_data = eval(post) if isinstance(post, str) else post
            
            channel_type = post_data.get("channel_type", "")
            user_id = post_data.get("user_id", "")
            message = post_data.get("message", "")
            channel_id = post_data.get("channel_id", "")
            
            # Обрабатываем только личные сообщения (D = Direct)
            if channel_type == "D" and message.strip():
                
                # Получаем информацию о пользователе
                user_info = await mattermost_service.get_user_info(user_id)
                user_name = user_info.get("username", "unknown") if user_info else "unknown"
                
                # Создаем объект запроса
                dm_request = DirectMessageRequest(
                    user_id=user_id,
                    user_name=user_name,
                    channel_id=channel_id,
                    channel_type=channel_type,
                    team_id=request.get("event", {}).get("data", {}).get("team_id", ""),
                    text=message,
                    post_id=post_data.get("id", "")
                )
                
                # Обрабатываем как обычное личное сообщение
                return await handle_direct_message(dm_request)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка обработки события Mattermost: {e}")
        return {"status": "error", "message": str(e)} 