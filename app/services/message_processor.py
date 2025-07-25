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
    
    async def process_message(self, user_id: str, message: str) -> str:
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
                return ""
            
            # Проверяем, является ли сообщение командой
            command_result = await self._try_handle_command(user_id, message)
            if command_result:
                return command_result
            
            # Если не команда, обрабатываем как запрос к Jira
            return await self._handle_jira_query(user_id, message)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения от {user_id}: {e}")
            return f"❌ Произошла ошибка при обработке запроса: {str(e)}"
    
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
    
    async def _handle_jira_query(self, user_id: str, query: str) -> str:
        """Обработка запроса к Jira"""
        try:
            # Получаем учетные данные пользователя из кеша
            async with cache_service as cache:
                credentials = await cache.get_cached_user_credentials(user_id)
                
            if not credentials:
                return """
❌ **Необходимо авторизоваться в Jira**

Используйте команду:
`авторизация [логин] [пароль/токен]`

Пример: `авторизация user@company.com mytoken`
"""

            # Анализируем запрос с помощью LLM
            try:
                async with llm_service as llm:
                    intent = await llm.interpret_query_intent(query)
                logger.info(f"Определен intent: {intent}")
            except Exception as e:
                logger.warning(f"Ошибка анализа intent: {e}")
                # Используем простой анализ намерений как fallback
                async with llm_service as llm:
                    intent = llm._simple_intent_analysis(query)

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
                    return await self._ask_for_client_mapping(user_id, client_name)
                elif jql and jql.startswith("UNKNOWN_USER:"):
                    user_name = jql.replace("UNKNOWN_USER:", "")
                    return await self._resolve_user_mapping(user_id, user_name, query)
                    
            except Exception as e:
                logger.error(f"Ошибка генерации JQL: {e}")
                return f"❌ Не удалось понять запрос: {str(e)}"
            
            # Выполняем запрос к Jira
            try:
                async with jira_service as jira:
                    issues = await jira.search_issues(
                        jql,
                        credentials['username'],
                        credentials['password'],
                        max_results=50
                    )
                
                logger.info(f"Найдено задач: {issues.total if issues else 0}")

            except JiraAuthError:
                # Удаляем недействительные учетные данные
                async with cache_service as cache:
                    await cache.invalidate_user_cache(user_id)
                return "❌ Ошибка авторизации в Jira. Необходимо повторить авторизацию."
            except JiraAPIError as e:
                return f"❌ Ошибка Jira API: {str(e)}"

            if not issues or not issues.issues:
                return "📋 По вашему запросу задачи не найдены."

            # Создаем график если запрошен
            chart_url = None
            if intent.get("needs_chart", False):
                try:
                    # Конвертируем задачи в данные для графика
                    # Группируем по статусам и считаем количество
                    status_count = {}
                    for issue in issues.issues:
                        status = issue.status
                        status_count[status] = status_count.get(status, 0) + 1
                    
                    chart_data = []
                    for status, count in status_count.items():
                        chart_data.append({
                            'name': status,
                            'value': count,
                            'category': status
                        })
                    
                    # Определяем тип графика
                    chart_type = intent.get("parameters", {}).get("chart_type", "bar")
                    
                    # Создаем график в зависимости от типа
                    if chart_type == "pie":
                        chart_url = await chart_service.create_pie_chart(chart_data, "Распределение по статусам")
                    elif chart_type == "line":
                        chart_url = await chart_service.create_line_chart(chart_data, "Динамика задач", "name", "value")
                    else:  # по умолчанию столбчатый график
                        chart_url = await chart_service.create_bar_chart(chart_data, "Статистика по статусам", "name", "value")
                    logger.info(f"Создан график: {chart_url}")
                    
                except Exception as e:
                    logger.error(f"Ошибка создания графика: {e}")
                    # Продолжаем без графика

            # Формируем текстовый ответ
            response_text = f"📋 **Найдено задач:** {issues.total}\n\n"

            for issue in issues.issues[:10]:  # Показываем до 10 задач
                response_text += f"• **{issue.key}** - {issue.summary}\n"
                response_text += f"  Статус: {issue.status}\n\n"

            if issues.total > 10:
                response_text += f"... и еще {issues.total - 10} задач(и)"

            # Добавляем ссылку на график если он создан
            if chart_url:
                response_text += f"\n\n📊 **График:** [Открыть визуализацию]({chart_url})"

            return response_text
                
        except Exception as e:
            logger.error(f"Ошибка обработки запроса от {user_id}: {e}")
            return f"❌ Произошла ошибка при обработке запроса: {str(e)}"

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

# Глобальный экземпляр процессора
message_processor = MessageProcessor()