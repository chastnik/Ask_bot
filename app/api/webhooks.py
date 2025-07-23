"""
API роутер для обработки webhooks от Mattermost
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from app.models.schemas import SlashCommandRequest, SlashCommandResponse
from app.services.jira_service import jira_service, JiraAPIError, JiraAuthError
from app.services.mattermost_service import mattermost_service
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service
from app.services.chart_service import chart_service


router = APIRouter()


class BotLogic:
    """Основная логика бота"""
    
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
        return mattermost_service.create_error_response(
            "Не удалось получить статистику кеша"
        )


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