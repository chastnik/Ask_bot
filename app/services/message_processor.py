"""
Процессор сообщений для Ask Bot
Обрабатывает команды в личных сообщениях
"""
import re
from typing import Dict, Any, Optional
from loguru import logger

from app.services.jira_service import jira_service, JiraAPIError, JiraAuthError
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service
from app.services.mattermost_service import mattermost_service
from app.services.chart_service import chart_service
from app.services.conversation_service import get_conversation_service
from app.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


class MessageProcessor:
    """Процессор сообщений для Ask Bot"""
    
    def __init__(self):
        self.commands = {
            'помощь': self._handle_help,
            'help': self._handle_help,
            'авторизация': self._handle_auth,
            'auth': self._handle_auth,
            'статус': self._handle_status,
            'status': self._handle_status,
            'проекты': self._handle_projects,
            'projects': self._handle_projects,
            'кеш': self._handle_cache,
            'cache': self._handle_cache,
            'научи': self._handle_teach,
            'teach': self._handle_teach,
            'маппинги': self._handle_mappings,
            'mappings': self._handle_mappings,
            'обновить': self._handle_refresh_dictionaries,
            'refresh': self._handle_refresh_dictionaries,
        }
    
    def _format_issue_link(self, issue_key: str) -> str:
        """
        Форматирует ссылку на задачу в Jira
        
        Args:
            issue_key: Ключ задачи (например, PROJECT-123)
            
        Returns:
            Отформатированная Markdown ссылка
        """
        jira_base_url = settings.jira_base_url.rstrip('/')
        issue_link = f"{jira_base_url}/browse/{issue_key}"
        return f"[**{issue_key}**]({issue_link})"
    
    async def _enrich_query_with_context(self, user_id: str, query: str, channel_id: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
        """Обогащает запрос контекстом предыдущих сообщений"""
        try:
            engine = create_async_engine(settings.database_url)
            async with AsyncSession(engine) as db_session:
                conv_service = await get_conversation_service(db_session)
                return await conv_service.enrich_query_with_context(user_id, query, channel_id)
        except Exception as e:
            logger.error(f"Ошибка обогащения контекста: {e}")
            return query, {}
        finally:
            if 'engine' in locals():
                await engine.dispose()
    
    async def _save_conversation_context(
        self, 
        user_id: str, 
        query: str, 
        intent: Dict[str, Any], 
        response: str,
        entities: Optional[Dict[str, Any]] = None,
        channel_id: Optional[str] = None
    ) -> bool:
        """Сохраняет контекст беседы"""
        try:
            engine = create_async_engine(settings.database_url)
            async with AsyncSession(engine) as db_session:
                conv_service = await get_conversation_service(db_session)
                return await conv_service.save_context(user_id, query, intent, response, entities, channel_id)
        except Exception as e:
            logger.error(f"Ошибка сохранения контекста: {e}")
            return False
        finally:
            if 'engine' in locals():
                await engine.dispose()
    
    async def process_message(self, user_id: str, message: str) -> str:
        """
        Обрабатывает сообщение от пользователя (только текст)
        """
        response_text, _ = await self.process_message_with_files(user_id, message)
        return response_text

    async def process_message_with_files(self, user_id: str, message: str) -> tuple[str, Optional[str]]:
        """
        Обрабатывает сообщение от пользователя
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
            
        Returns:
            Ответ для пользователя
        """
        try:
            message = message.strip()
            
            if not message:
                return "", None
            
            # Проверяем, является ли сообщение командой
            command_result = await self._try_handle_command(user_id, message)
            if command_result:
                return command_result, None
            
            # Если не команда, обрабатываем как запрос к Jira
            return await self._handle_jira_query(user_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения от {user_id}: {e}")
            return f"❌ Произошла ошибка при обработке запроса: {str(e)}", None
    
    async def _try_handle_command(self, user_id: str, message: str) -> Optional[str]:
        """Пытается обработать сообщение как команду"""
        words = message.lower().split()
        
        if not words:
            return None
        
        first_word = words[0]
        
        # Проверяем команды
        if first_word in self.commands:
            return await self.commands[first_word](user_id, message)
        
        # Проверяем команды из нескольких слов
        if len(words) >= 2:
            two_words = f"{words[0]} {words[1]}"
            if two_words in self.commands:
                return await self.commands[two_words](user_id, message)
        
        return None
    
    async def _handle_help(self, user_id: str, message: str) -> str:
        """Обработка команды помощи"""
        return """
🤖 **Ask Bot - Ваш помощник по Jira**

**💬 Как пользоваться:**
Просто напишите мне запрос на естественном языке!

**📝 Примеры запросов:**
• "Покажи мои открытые задачи"
• "Сколько багов в проекте PROJECT_KEY?"
• "Задачи без исполнителя в проекте ABC"
• "Статистика по исполнителям за последний месяц"
• "Просроченные задачи в проекте XYZ"

**⚙️ Специальные команды:**
• `помощь` - показать это сообщение
• `авторизация [логин] [пароль/токен]` - войти в Jira
• `статус` - проверить статус авторизации
• `проекты` - список доступных проектов
• `кеш очистить` - очистить кеш
• `кеш статистика` - статистика кеша

**🎓 Обучение бота:**
• `научи клиент "Название" проект "КЛЮЧ"` - научить соответствию клиент→проект
• `научи пользователь "Имя" username "login"` - научить соответствию имя→username
• `маппинги` - показать все известные соответствия
• `обновить` - принудительно обновить справочники Jira

**📊 Создание графиков:**
Добавьте "покажи как график" к любому запросу для визуализации!

Пример: "Задачи по статусам в проекте ABC покажи как график"
"""
    
    async def _handle_auth(self, user_id: str, message: str) -> str:
        """Обработка авторизации"""
        parts = message.strip().split()
        
        if len(parts) < 3:
            return """
🔐 **Авторизация в Jira**

**Формат команды:**
`авторизация [логин] [пароль/токен]`

**Примеры:**
• `авторизация user@company.com mypassword`
• `авторизация username api_token_here`

**Для Jira Cloud рекомендуется использовать API токен вместо пароля.**
"""
        
        username = parts[1]
        password = parts[2]
        
        try:
            # Тестируем подключение к Jira (токен или пароль)
            async with jira_service as jira:
                # Пытаемся сначала как токен, потом как пароль
                test_result = await jira.test_connection(username, token=password)
                if not test_result:
                    test_result = await jira.test_connection(username, password=password)

            if test_result:
                # Сохраняем учетные данные в кеше
                async with cache_service as cache:
                    credentials = {"username": username, "password": password}
                    await cache.cache_user_credentials(user_id, credentials)
                
                return f"✅ Успешная авторизация в Jira как **{username}**"
            else:
                return "❌ Неверные учетные данные для Jira. Проверьте логин и пароль/токен."
                
        except Exception as e:
            logger.error(f"Ошибка авторизации для пользователя {user_id}: {e}")
            return f"❌ Ошибка при авторизации: {str(e)}"
    
    async def _handle_status(self, user_id: str, message: str) -> str:
        """Проверка статуса авторизации"""
        try:
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if credentials:
                # Проверяем, что учетные данные все еще действительны
                async with jira_service as jira:
                    # Пытаемся сначала как токен, потом как пароль
                    test_result = await jira.test_connection(
                        credentials['username'],
                        token=credentials['password']
                    )
                    if not test_result:
                        test_result = await jira.test_connection(
                            credentials['username'],
                            password=credentials['password']
                        )
                
                if test_result:
                    return f"✅ Вы авторизованы в Jira как **{credentials['username']}**"
                else:
                    # Удаляем недействительные учетные данные
                    async with cache_service as cache:
                        await cache.invalidate_user_cache(user_id)
                    return "❌ Ваши учетные данные устарели. Необходимо повторить авторизацию."
            else:
                return """
❌ **Вы не авторизованы в Jira**

Для авторизации используйте команду:
`авторизация [логин] [пароль/токен]`
"""
                
        except Exception as e:
            logger.error(f"Ошибка проверки статуса для пользователя {user_id}: {e}")
            return f"❌ Ошибка при проверке статуса: {str(e)}"
    
    async def _handle_projects(self, user_id: str, message: str) -> str:
        """Получение списка проектов"""
        try:
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return "❌ Необходимо авторизоваться в Jira. Используйте: `авторизация [логин] [пароль]`"
            
            # Получаем список проектов
            async with jira_service as jira:
                projects = await jira.get_projects(
                    credentials['username'],
                    credentials['password']
                )
            
            if projects:
                projects_text = "📋 **Доступные проекты Jira:**\n\n"
                for project in projects[:20]:  # Ограничиваем вывод
                    projects_text += f"• **{project.get('key')}** - {project.get('name')}\n"
                
                if len(projects) > 20:
                    projects_text += f"\n... и еще {len(projects) - 20} проектов"
                    
                return projects_text
            else:
                return "📋 Проекты не найдены или у вас нет доступа к ним."
                
        except Exception as e:
            logger.error(f"Ошибка получения проектов для пользователя {user_id}: {e}")
            return f"❌ Ошибка при получении списка проектов: {str(e)}"
    
    async def _handle_cache(self, user_id: str, message: str) -> str:
        """Обработка команд кеша"""
        if 'очистить' in message or 'clear' in message:
            try:
                async with cache_service as cache:
                    await cache.invalidate_user_cache(user_id)
                return "✅ Ваш кеш очищен"
            except Exception as e:
                return f"❌ Ошибка очистки кеша: {str(e)}"
                
        elif 'статистик' in message or 'stats' in message:
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
                    
                return stats_text
                
            except Exception as e:
                return f"❌ Ошибка получения статистики: {str(e)}"
        else:
            return """
**Команды кеша:**
• `кеш очистить` - очистить ваш кеш
• `кеш статистика` - показать статистику кеша
"""
    
    async def _handle_jira_query(self, user_id: str, query: str) -> tuple[str, Optional[str]]:
        """Обработка запроса к Jira"""
        try:
            # Обогащаем запрос контекстом предыдущих сообщений
            enriched_query, context_entities = await self._enrich_query_with_context(user_id, query)
            logger.info(f"Исходный запрос: {query}")
            logger.info(f"Обогащенный запрос: {enriched_query}")
            logger.info(f"Контекстные сущности: {context_entities}")
            
            # Получаем учетные данные пользователя из кеша
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return """
❌ **Необходимо авторизоваться в Jira**

Используйте команду:
`авторизация [логин] [пароль/токен]`

Пример: `авторизация user@company.com mytoken`
""", None

            # Анализируем запрос с помощью LLM (используем обогащенный запрос)
            try:
                async with llm_service as llm:
                    intent = await llm.interpret_query_intent(enriched_query)
                
                # Дополняем intent контекстными сущностями
                if context_entities:
                    if "parameters" not in intent:
                        intent["parameters"] = {}
                    intent["parameters"].update(context_entities)
                
                logger.info(f"Определен intent: {intent}")
            except Exception as e:
                logger.warning(f"Ошибка анализа intent: {e}")
                # Используем простой анализ намерений как fallback
                async with llm_service as llm:
                    intent = llm._simple_intent_analysis(enriched_query)
                    
                # Дополняем intent контекстными сущностями для fallback тоже
                if context_entities:
                    if "parameters" not in intent:
                        intent["parameters"] = {}
                    intent["parameters"].update(context_entities)

            # Загружаем маппинги и справочники Jira из кеша
            try:
                async with cache_service as cache:
                    client_mappings = await cache.get_all_client_mappings()
                    user_mappings = await cache.get_all_user_mappings()
                    
                    # Получаем справочники Jira
                    jira_dictionaries = await cache.get_all_jira_dictionaries(user_id)
                    
                    # Если справочники пустые - обновляем их
                    if not any(jira_dictionaries.values()):
                        logger.info(f"Справочники Jira пустые для пользователя {user_id}, обновляем...")
                        refresh_success = await self._refresh_jira_dictionaries(user_id)
                        if refresh_success:
                            jira_dictionaries = await cache.get_all_jira_dictionaries(user_id)
                
                # Отладочные логи
                logger.info(f"Client mappings type: {type(client_mappings)}, value: {client_mappings}")
                logger.info(f"User mappings type: {type(user_mappings)}, value: {user_mappings}")
                logger.info(f"Jira dictionaries loaded: {', '.join([f'{k}({len(v)})' for k, v in jira_dictionaries.items()])}")
                
                # Проверяем типы и исправляем если нужно
                if not isinstance(client_mappings, dict):
                    logger.warning(f"client_mappings не словарь: {type(client_mappings)}, заменяем на пустой словарь")
                    client_mappings = {}
                if not isinstance(user_mappings, dict):
                    logger.warning(f"user_mappings не словарь: {type(user_mappings)}, заменяем на пустой словарь")
                    user_mappings = {}
                    
                # Проверяем тип намерения
                intent_type = intent.get("intent", "search")
                
                # Для worklog запросов используем специальную обработку
                if intent_type == "worklog":
                    logger.info(f"Обрабатываем worklog запрос: {intent}")
                    
                    # Извлекаем assignee из параметров intent
                    assignee = intent.get("parameters", {}).get("assignee")
                    if not assignee:
                        return "❌ Не удалось определить пользователя для подсчета трудозатрат.", None
                    
                    # Генерируем JQL для поиска задач пользователя
                    jql = f"assignee = \"{assignee}\" OR assignee was \"{assignee}\""
                    
                    # Добавляем временной фильтр если указан
                    time_period = intent.get("parameters", {}).get("time_period")
                    if time_period:
                        # Простое определение месяца для JQL
                        month_mapping = {
                            "январь": "01", "февраль": "02", "март": "03", "апрель": "04",
                            "май": "05", "июнь": "06", "июль": "07", "август": "08",
                            "сентябрь": "09", "октябрь": "10", "ноябрь": "11", "декабрь": "12"
                        }
                        
                        current_year = "2024"  # Можно сделать динамическим
                        for month_ru, month_num in month_mapping.items():
                            if month_ru in time_period.lower():
                                jql += f" AND worklogDate >= \"{current_year}-{month_num}-01\" AND worklogDate <= \"{current_year}-{month_num}-31\""
                                break
                
                else:
                    # Для обычных запросов используем генерацию JQL через LLM
                    user_context = {
                        "projects": jira_dictionaries.get("projects", []), 
                        "clients": list(client_mappings.keys()),
                        "users": list(user_mappings.keys()),
                        "client_mappings": client_mappings,
                        "user_mappings": user_mappings,
                        "jira_dictionaries": jira_dictionaries
                    }
                    
                    async with llm_service as llm:
                        jql = await llm.generate_jql_query(query, user_context)
                    logger.info(f"Сгенерирован JQL: {jql}")
                    
                    # Проверяем, нужно ли уточнить маппинг
                    if jql and jql.startswith("UNKNOWN_CLIENT:"):
                        client_name = jql.replace("UNKNOWN_CLIENT:", "")
                        response = await self._ask_for_client_mapping(user_id, client_name)
                        return response, None
                    elif jql and jql.startswith("UNKNOWN_USER:"):
                        user_name = jql.replace("UNKNOWN_USER:", "")
                        response = await self._resolve_user_mapping(user_id, user_name, query)
                        return response, None
                    
            except Exception as e:
                logger.error(f"Ошибка генерации JQL: {e}")
                return f"❌ Не удалось понять запрос: {str(e)}", None
            
            # Выполняем запрос к Jira
            try:
                async with jira_service as jira:
                    issues = await jira.search_issues(
                        jql,
                        credentials['username'],
                        credentials['password'],
                        max_results=1000  # Увеличиваем лимит для получения всех задач
                    )
                
                logger.info(f"Найдено задач: {issues.total if issues else 0}")

            except JiraAuthError:
                # Удаляем недействительные учетные данные
                async with cache_service as cache:
                    await cache.invalidate_user_cache(user_id)
                return "❌ Ошибка авторизации в Jira. Необходимо повторить авторизацию.", None
            except JiraAPIError as e:
                return f"❌ Ошибка Jira API: {str(e)}", None

            # Проверяем намерение для специальной обработки пустых результатов
            if not issues or not issues.issues:
                intent_type = intent.get("intent", "search")
                if intent_type == "analytics":
                    # Для аналитических запросов формируем специальный ответ даже при 0 результатах
                    empty_issues = type('EmptyIssues', (), {'total': 0, 'issues': []})()
                    response_text = await self._format_analytics_response(empty_issues, intent, query)
                    return response_text, None
                else:
                    return "📋 По вашему запросу задачи не найдены.", None

            # Создаем график если запрошен
            chart_file_path = None
            if intent.get("needs_chart", False):
                try:
                    # Определяем параметры группировки
                    group_by = intent.get("parameters", {}).get("group_by", "status")
                    chart_type = intent.get("parameters", {}).get("chart_type", "bar")
                    
                    # Группируем задачи по выбранному полю
                    group_count = {}
                    group_label = "статусам"  # по умолчанию
                    
                    for issue in issues.issues:
                        if group_by == "project":
                            key = getattr(issue, 'project_key', issue.key.split('-')[0])
                            group_label = "проектам"
                        elif group_by == "priority":
                            key = getattr(issue, 'priority', 'Не указан')
                            group_label = "приоритетам"
                        elif group_by == "assignee":
                            key = getattr(issue, 'assignee', 'Не назначен')
                            group_label = "исполнителям"
                        elif group_by == "issue_type":
                            key = getattr(issue, 'issue_type', 'Неизвестный тип')
                            group_label = "типам задач"
                        else:  # по умолчанию status
                            key = issue.status
                            group_label = "статусам"
                        
                        group_count[key] = group_count.get(key, 0) + 1
                    
                    # Подготавливаем данные для графика
                    chart_data = []
                    for name, count in group_count.items():
                        chart_data.append({
                            'name': name,
                            'value': count,
                            'category': name
                        })
                    
                    # Создаем заголовок
                    chart_title = f"Распределение по {group_label}"
                    
                    # Создаем график в зависимости от типа
                    if chart_type == "pie":
                        chart_file_path = await chart_service.create_pie_chart(chart_data, chart_title, "value", "name")
                    elif chart_type == "line":
                        chart_file_path = await chart_service.create_line_chart(chart_data, chart_title, "name", "value")
                    else:  # по умолчанию столбчатый график
                        chart_file_path = await chart_service.create_bar_chart(chart_data, chart_title, "name", "value")
                    logger.info(f"Создан график: {chart_file_path}")
                    
                except Exception as e:
                    logger.error(f"Ошибка создания графика: {e}")
                    # Продолжаем без графика

            # Проверяем намерение для специальной обработки аналитических запросов
            intent_type = intent.get("intent", "search")
            
            if intent_type == "analytics":
                # Формируем аналитический ответ
                response_text = await self._format_analytics_response(issues, intent, query)
            elif intent_type == "worklog":
                # Формируем ответ по трудозатратам
                response_text = await self._format_worklog_response(issues, intent, query, user_id)
            else:
                # Формируем стандартный текстовый ответ со списком
                response_text = f"📋 **Найдено задач:** {issues.total}\n\n"
                
                for issue in issues.issues[:10]:  # Показываем до 10 задач
                    # Формируем ссылку на задачу
                    issue_link = self._format_issue_link(issue.key)
                    response_text += f"• {issue_link} - {issue.summary}\n"
                    response_text += f"  Статус: {issue.status}\n\n"

                if issues.total > 10:
                    response_text += f"... и еще {issues.total - 10} задач(и)"

            # Сохраняем контекст беседы
            try:
                await self._save_conversation_context(
                    user_id=user_id,
                    query=query,
                    intent=intent,
                    response=response_text,
                    entities=intent.get("parameters", {})
                )
            except Exception as e:
                logger.warning(f"Не удалось сохранить контекст беседы: {e}")
            
            # Возвращаем текст и путь к файлу графика
            return response_text, chart_file_path
                
        except Exception as e:
            logger.error(f"Ошибка обработки запроса от {user_id}: {e}")
            return f"❌ Произошла ошибка при обработке запроса: {str(e)}", None

    async def _refresh_jira_dictionaries(self, user_id: str) -> bool:
        """
        Обновляет справочники Jira для пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True при успешном обновлении
        """
        try:
            # Получаем учетные данные пользователя
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                logger.warning(f"Нет учетных данных для пользователя {user_id}, не можем обновить справочники")
                return False
            
            # Получаем все справочники из Jira
            async with jira_service as jira:
                dictionaries = await jira.get_all_dictionaries(
                    credentials['username'],
                    credentials['password']
                )
            
            # Кэшируем каждый справочник
            async with cache_service as cache:
                for dict_type, data in dictionaries.items():
                    await cache.cache_jira_dictionary(dict_type, data, user_id)
            
            logger.info(f"Справочники Jira обновлены для пользователя {user_id}: {', '.join([f'{k}({len(v)})' for k, v in dictionaries.items()])}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления справочников для пользователя {user_id}: {e}")
            return False
    
    async def _ask_for_client_mapping(self, user_id: str, client_name: str) -> str:
        """Спрашивает у пользователя маппинг клиента на проект"""
        return f"""
🤔 **Я не знаю, какой проект соответствует клиенту "{client_name}"**

Пожалуйста, научите меня! Используйте команду:
`научи клиент "{client_name}" проект "КЛЮЧ_ПРОЕКТА"`

**Пример:**
`научи клиент "Иль де Ботэ" проект "IDB"`

После этого я смогу обработать ваш запрос.
"""

    async def _resolve_user_mapping(self, user_id: str, display_name: str, original_query: str) -> str:
        """Ищет пользователя в Jira и предлагает маппинг или обучение"""
        try:
            # Получаем учетные данные пользователя
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
            
            if not credentials:
                return "❌ Для поиска пользователей необходима авторизация в Jira."
            
            # Ищем пользователя в Jira
            async with jira_service as jira:
                found_user = await jira.find_user_by_display_name(
                    display_name, 
                    credentials['username'], 
                    token=credentials['password']
                )
            
            if found_user:
                # Автоматически сохраняем найденный маппинг
                jira_username = found_user.get('name', '')
                jira_display_name = found_user.get('displayName', display_name)
                
                async with cache_service as cache:
                    await cache.save_user_username_mapping(
                        jira_display_name, jira_username, user_id
                    )
                
                logger.info(f"Автоматически создан маппинг: {jira_display_name} → {jira_username}")
                
                # Повторно обрабатываем исходный запрос
                return f"""✅ Найден пользователь: **{jira_display_name}** → `{jira_username}`

Обрабатываю ваш запрос...

""" + await self._handle_jira_query(user_id, original_query)
            
            else:
                # Пользователь не найден, просим научить
                return f"""
🤔 **Не удалось найти пользователя "{display_name}" в Jira**

Возможно, имя написано не точно или используется другое имя.

Пожалуйста, научите меня:
`научи пользователь "{display_name}" username "jira_username"`

**Пример:**
`научи пользователь "Олег Антонов" username "olegantov"`

Или попробуйте поискать точное имя в Jira и использовать его.
"""
                
        except Exception as e:
            logger.error(f"Ошибка разрешения пользователя {display_name}: {e}")
            return f"❌ Ошибка при поиске пользователя: {str(e)}"

    async def _handle_teach(self, user_id: str, message: str) -> str:
        """Обработка команды обучения маппингам"""
        try:
            # Парсим команду обучения
            parts = message.strip().split()
            
            if len(parts) < 5:
                return """
🎓 **Команды обучения:**

**Клиент → Проект:**
`научи клиент "Название клиента" проект "КЛЮЧ_ПРОЕКТА"`

**Имя → Username:**
`научи пользователь "Имя Фамилия" username "jira_username"`

**Примеры:**
• `научи клиент "Иль де Ботэ" проект "IDB"`
• `научи пользователь "Станислав Чашин" username "svchashin"`
"""

            mapping_type = parts[1].lower()
            
            if mapping_type == "клиент" and len(parts) >= 5:
                # Извлекаем название клиента и ключ проекта
                import re
                # Поддерживаем как с кавычками, так и без них
                client_match = re.search(r'клиент\s+(?:"([^"]+)"|(\S+))', message, re.IGNORECASE)
                project_match = re.search(r'проект\s+(?:"([^"]+)"|(\S+))', message, re.IGNORECASE)
                
                if client_match and project_match:
                    # Берем первую найденную группу (с кавычками или без)
                    client_name = client_match.group(1) or client_match.group(2)
                    project_key = project_match.group(1) or project_match.group(2)
                    
                    async with cache_service as cache:
                        success = await cache.save_client_project_mapping(
                            client_name, project_key, user_id
                        )
                    
                    if success:
                        return f'✅ Отлично! Теперь я знаю, что клиент **"{client_name}"** соответствует проекту **"{project_key}"**'
                    else:
                        return "❌ Ошибка сохранения маппинга"
                        
            elif mapping_type == "пользователь" and len(parts) >= 5:
                # Извлекаем имя и username
                import re
                # Поддерживаем как с кавычками, так и без них
                name_match = re.search(r'пользователь\s+(?:"([^"]+)"|(\S+(?:\s+\S+)*))', message, re.IGNORECASE)
                username_match = re.search(r'username\s+(?:"([^"]+)"|(\S+))', message, re.IGNORECASE)
                
                if name_match and username_match:
                    # Берем первую найденную группу (с кавычками или без)
                    display_name = name_match.group(1) or name_match.group(2)
                    username = username_match.group(1) or username_match.group(2)
                    
                    async with cache_service as cache:
                        success = await cache.save_user_username_mapping(
                            display_name, username, user_id
                        )
                    
                    if success:
                        return f'✅ Отлично! Теперь я знаю, что **"{display_name}"** соответствует username **"{username}"**'
                    else:
                        return "❌ Ошибка сохранения маппинга"
            
            return "❌ Неправильный формат команды. Используйте `научи` для помощи."
            
        except Exception as e:
            logger.error(f"Ошибка обучения для пользователя {user_id}: {e}")
            return f"❌ Ошибка при обучении: {str(e)}"

    async def _handle_mappings(self, user_id: str, message: str) -> str:
        """Показывает все известные маппинги"""
        try:
            async with cache_service as cache:
                client_mappings = await cache.get_all_client_mappings()
                user_mappings = await cache.get_all_user_mappings()
            
            response = "📋 **Известные маппинги:**\n\n"
            
            if client_mappings:
                response += "**Клиенты → Проекты:**\n"
                for client, project in client_mappings.items():
                    response += f"• **{client}** → `{project}`\n"
                response += "\n"
            else:
                response += "**Клиенты → Проекты:** Пока нет\n\n"
            
            if user_mappings:
                response += "**Пользователи → Username:**\n"
                for display_name, username in user_mappings.items():
                    response += f"• **{display_name}** → `{username}`\n"
            else:
                response += "**Пользователи → Username:** Пока нет\n"
            
            response += "\n💡 Для добавления новых маппингов используйте команду `научи`"
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка получения маппингов для пользователя {user_id}: {e}")
            return f"❌ Ошибка при получении маппингов: {str(e)}"


    async def _handle_refresh_dictionaries(self, user_id: str, message: str) -> str:
        """Обработка команды принудительного обновления справочников"""
        try:
            # Инвалидируем кэш справочников
            async with cache_service as cache:
                await cache.invalidate_jira_dictionaries(user_id)
            
            # Обновляем справочники
            success = await self._refresh_jira_dictionaries(user_id)
            
            if success:
                return """
✅ **Справочники Jira обновлены-30 app/services/message_processor.py*

Загружены актуальные данные:
• Статусы задач
• Типы задач  
• Приоритеты
• Проекты

Теперь JQL запросы будут использовать актуальные справочники.
"""
            else:
                return "❌ Ошибка обновления справочников. Проверьте авторизацию в Jira."
                
        except Exception as e:
            logger.error(f"Ошибка команды обновления справочников: {e}")
            return f"❌ Ошибка обновления справочников: {str(e)}"

    async def _format_analytics_response(self, issues, intent: Dict[str, Any], original_query: str) -> str:
        """
        Форматирует аналитический ответ вместо простого списка задач
        
        Args:
            issues: Результаты поиска из Jira
            intent: Намерение пользователя
            original_query: Оригинальный запрос
            
        Returns:
            Отформатированный аналитический ответ
        """
        try:
            # Получаем параметры для группировки из намерения
            group_by = intent.get("parameters", {}).get("group_by", "status")
            
            # Если это просто подсчет без группировки
            if "сколько" in original_query.lower() or "количество" in original_query.lower():
                return self._format_count_response(issues, original_query)
            
            # Группированная аналитика
            return self._format_grouped_analytics(issues, group_by, original_query)
            
        except Exception as e:
            logger.error(f"Ошибка форматирования аналитического ответа: {e}")
            # Fallback к стандартному ответу
            return f"📊 **Найдено:** {issues.total} задач(и)"

    def _format_count_response(self, issues, original_query: str) -> str:
        """Форматирует ответ для запросов типа 'сколько'"""
        total = issues.total
        
        # Определяем контекст из запроса
        context_words = []
        query_lower = original_query.lower()
        
        if "баг" in query_lower:
            context_words.append("багов")
        elif "задач" in query_lower:
            context_words.append("задач")
        
        if "закрыт" in query_lower:
            context_words.append("закрытых")
        elif "открыт" in query_lower:
            context_words.append("открытых")
            
        if "июль" in query_lower or "июн" in query_lower:
            context_words.append("в июле")
        elif "неделя" in query_lower:
            context_words.append("за неделю")
        elif "сегодня" in query_lower:
            context_words.append("сегодня")
            
        context = " ".join(context_words) if context_words else "задач"
        
        response = f"🔢 **Количество {context}:** {total}\n\n"
        
        if total == 0:
            response += "Задачи по указанным критериям не найдены."
        elif total == 1:
            response += "Найдена 1 задача по вашим критериям."
        elif total <= 5:
            response += f"Найдено {total} задачи. Вот они:\n\n"
            
            for issue in issues.issues:
                # Формируем ссылку на задачу
                issue_link = self._format_issue_link(issue.key)
                response += f"• {issue_link} - {issue.summary}\n"
        else:
            response += f"📈 **Краткая сводка:**\n"
            # Группируем по статусам для краткой сводки
            status_count = {}
            for issue in issues.issues:
                status = issue.status
                status_count[status] = status_count.get(status, 0) + 1
            
            for status, count in sorted(status_count.items(), key=lambda x: x[1], reverse=True):
                response += f"• {status}: {count}\n"
                
        return response

    def _format_grouped_analytics(self, issues, group_by: str, original_query: str) -> str:
        """Форматирует групповую аналитику"""
        total = issues.total
        
        # Группируем данные
        grouped_data = {}
        for issue in issues.issues:
            if group_by == "assignee":
                key = getattr(issue, 'assignee', 'Не назначен') or 'Не назначен'
            elif group_by == "project":
                key = getattr(issue, 'project_key', issue.key.split('-')[0])
            elif group_by == "priority":
                key = getattr(issue, 'priority', 'Не указан')
            elif group_by == "issue_type":
                key = getattr(issue, 'issue_type', 'Неизвестный тип')
            else:  # status по умолчанию
                key = issue.status
                
            grouped_data[key] = grouped_data.get(key, 0) + 1
        
        # Определяем заголовок группировки
        group_labels = {
            "assignee": "исполнителям",
            "project": "проектам", 
            "priority": "приоритетам",
            "issue_type": "типам задач",
            "status": "статусам"
        }
        group_label = group_labels.get(group_by, "категориям")
        
        response = f"📊 **Статистика по {group_label}**\n"
        response += f"Всего задач: {total}\n\n"
        
        # Сортируем по количеству (по убыванию)
        sorted_groups = sorted(grouped_data.items(), key=lambda x: x[1], reverse=True)
        
        for i, (name, count) in enumerate(sorted_groups, 1):
            percentage = (count / total * 100) if total > 0 else 0
            response += f"{i}. **{name}**: {count} ({percentage:.1f}%)\n"
            
        # Добавляем инсайты для топ-групп
        if len(sorted_groups) > 0:
            top_group = sorted_groups[0]
            response += f"\n💡 **Больше всего задач:** {top_group[0]} ({top_group[1]} задач)"
            
            if len(sorted_groups) > 1:
                response += f"\n📈 **Активные {group_label}:** {len(sorted_groups)}"
                
        return response
    
    async def _format_worklog_response(self, issues, intent: Dict[str, Any], original_query: str, user_id: str) -> str:
        """
        Форматирует ответ по трудозатратам (worklog)
        
        Args:
            issues: Результаты поиска из Jira
            intent: Намерение пользователя с параметрами
            original_query: Оригинальный запрос
            user_id: ID пользователя для получения учетных данных
            
        Returns:
            Отформатированный ответ с суммой часов
        """
        try:
            if issues.total == 0:
                return "📋 По указанным критериям задачи не найдены, поэтому трудозатраты равны 0 часов."
            
            # Получаем учетные данные для доступа к worklog
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return "❌ Для получения данных о трудозатратах необходимо авторизоваться в Jira."
            
            # Агрегируем трудозатраты
            total_seconds = 0
            user_time = {}
            task_count = 0
            
            # Определяем фильтр по пользователю из намерения
            target_assignee = intent.get("parameters", {}).get("assignee")
            
            async with jira_service as jira:
                for issue in issues.issues:
                    try:
                        # Получаем worklogs для каждой задачи
                        worklogs = await jira.get_worklogs(
                            issue.key,
                            credentials['username'],
                            token=credentials['password']
                        )
                        
                        for worklog in worklogs:
                            # Если указан конкретный пользователь, фильтруем по нему
                            if target_assignee:
                                # Проверяем различные варианты сравнения имени
                                author_name = worklog.author.lower()
                                target_name = target_assignee.lower()
                                
                                # Точное совпадение или содержание имени
                                if (target_name not in author_name and 
                                    author_name not in target_name and
                                    not any(part in author_name for part in target_name.split())):
                                    continue
                            
                            # Добавляем время к общей сумме
                            total_seconds += worklog.time_spent_seconds
                            
                            # Агрегируем по пользователям для статистики
                            if worklog.author not in user_time:
                                user_time[worklog.author] = 0
                            user_time[worklog.author] += worklog.time_spent_seconds
                        
                        task_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Ошибка получения worklogs для {issue.key}: {e}")
                        continue
            
            # Конвертируем секунды в часы
            total_hours = total_seconds / 3600
            
            # Формируем ответ в зависимости от параметров запроса
            assignee_param = intent.get("parameters", {}).get("assignee")
            time_period = intent.get("parameters", {}).get("time_period", "")
            project_param = intent.get("parameters", {}).get("project", "")
            
            # Основной ответ
            if total_hours == 0:
                if assignee_param:
                    response = f"⏱️ **{assignee_param}** не списывал время"
                else:
                    response = f"⏱️ **Время не списывалось**"
            else:
                if assignee_param:
                    response = f"⏱️ **{assignee_param}** списал **{total_hours:.1f} часов**"
                else:
                    response = f"⏱️ **Общие трудозатраты: {total_hours:.1f} часов**"
            
            # Добавляем контекст
            context_parts = []
            if time_period:
                context_parts.append(f"за {time_period}")
            if project_param:
                context_parts.append(f"по проекту {project_param}")
            elif issues.total > 0:
                # Определяем проекты из найденных задач
                projects = set()
                for issue in issues.issues[:5]:  # берем первые 5 для определения проектов
                    project_key = issue.key.split('-')[0]
                    projects.add(project_key)
                if len(projects) == 1:
                    context_parts.append(f"по проекту {list(projects)[0]}")
                elif len(projects) > 1:
                    context_parts.append(f"по проектам {', '.join(sorted(projects))}")
            
            if context_parts:
                response += f" {' '.join(context_parts)}"
            
            response += f"\n\n📊 **Детализация:**\n"
            response += f"• Проанализировано задач: {task_count}\n"
            
            if len(user_time) > 1 and not assignee_param:
                # Показываем топ-3 пользователей по времени
                sorted_users = sorted(user_time.items(), key=lambda x: x[1], reverse=True)[:3]
                response += f"• Топ исполнителей:\n"
                for i, (user, seconds) in enumerate(sorted_users, 1):
                    hours = seconds / 3600
                    response += f"  {i}. {user}: {hours:.1f} ч\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка форматирования worklog ответа: {e}")
            return f"❌ Ошибка при обработке трудозатрат: {str(e)}"


# Глобальный экземпляр процессора
message_processor = MessageProcessor()