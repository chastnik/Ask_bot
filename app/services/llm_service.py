"""
Сервис для работы с локальной LLM
"""
import aiohttp
import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Union, Generator
from loguru import logger

from app.config import settings


class LLMError(Exception):
    """Исключение для ошибок LLM"""
    pass


class LLMService:
    """Сервис для работы с локальной LLM через прокси"""
    
    def __init__(self):
        self.base_url = settings.llm_base_url
        self.token = settings.llm_proxy_token
        self.model = settings.llm_model
        self.max_context_length = settings.max_context_length
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120),  # Увеличенный таймаут для LLM
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _get_headers(self) -> Dict[str, str]:
        """Получает заголовки для API запросов"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "python-requests/2.31.0"
        }
        
        # Используем X-PROXY-AUTH как в рабочем mm_bot
        if self.token:
            headers["X-PROXY-AUTH"] = self.token
        
        return headers
    
    async def test_connection(self) -> bool:
        """
        Тестирует подключение к LLM
        
        Returns:
            bool: True если соединение успешно
        """
        try:
            headers = self._get_headers()
            logger.debug(f"Используемые заголовки: {headers}")
            
            # Сначала пробуем GET endpoints для получения моделей
            get_endpoints = [
                "/v1/models",
                "/api/v1/models", 
                "/models"
            ]
            
            for endpoint in get_endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    logger.debug(f"Тестируем GET endpoint: {url}")
                    
                    async with self.session.get(url, headers=headers) as response:
                        logger.debug(f"Response status: {response.status}")
                        response_text = await response.text()
                        logger.debug(f"Response body: {response_text[:200]}...")
                        
                        if response.status == 200:
                            try:
                                models_data = await response.json() if response_text else {}
                                models = [model.get("id", "") for model in models_data.get("data", [])]
                                
                                if self.model in models:
                                    logger.info(f"Успешное подключение к LLM. Модель {self.model} доступна")
                                    return True
                                else:
                                    logger.warning(f"Модель {self.model} не найдена. Доступные: {models}")
                                    continue
                            except Exception as parse_error:
                                logger.error(f"Ошибка парсинга ответа: {parse_error}")
                                continue
                        elif response.status == 404:
                            continue
                        elif response.status == 403:
                            logger.error(f"Ошибка авторизации (403) для endpoint {endpoint}")
                            continue
                        else:
                            logger.error(f"Ошибка подключения к LLM: {response.status} для {endpoint}")
                            continue
                except Exception as e:
                    logger.error(f"Ошибка при тестировании endpoint {endpoint}: {e}")
                    continue
            
            # Если GET endpoints не работают, пробуем POST запрос к completions
            # для проверки работоспособности API
            try:
                url = f"{self.base_url}/v1/chat/completions"
                logger.debug(f"Тестируем POST endpoint: {url}")
                
                test_payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1,
                    "temperature": 0.1
                }
                
                async with self.session.post(url, headers=headers, json=test_payload) as response:
                    logger.debug(f"POST Response status: {response.status}")
                    response_text = await response.text()
                    logger.debug(f"POST Response body: {response_text[:200]}...")
                    
                    if response.status == 200:
                        logger.info(f"Успешное подключение к LLM через POST /v1/chat/completions")
                        return True
                    elif response.status == 400:
                        # Если получили 400, значит запрос дошёл, но модель не найдена или неверные параметры
                        # Это лучше чем 403, значит авторизация работает
                        logger.warning(f"API отвечает, но модель {self.model} недоступна или неверные параметры")
                        logger.warning(f"Ответ сервера: {response_text}")
                        return True  # Подключение работает, проблема в модели
                    elif response.status == 403:
                        logger.error(f"Ошибка авторизации (403) для POST endpoint")
                    else:
                        logger.error(f"Ошибка POST запроса: {response.status}")
                        
            except Exception as e:
                logger.error(f"Ошибка при тестировании POST endpoint: {e}")
            
            # Если ни один endpoint не сработал
            logger.error("Не удалось подключиться ни к одному endpoint LLM сервера")
            return False
                    
        except Exception as e:
            logger.error(f"Ошибка при тестировании подключения к LLM: {e}")
            return False
    
    async def generate_completion(self, prompt: str, temperature: float = 0.7,
                                max_tokens: int = 1000, system_prompt: Optional[str] = None) -> Optional[str]:
        """
        Генерирует ответ от LLM
        
        Args:
            prompt: Пользовательский запрос
            temperature: Температура генерации (0.0 - 2.0)
            max_tokens: Максимальное количество токенов
            system_prompt: Системный промпт (опционально)
            
        Returns:
            Сгенерированный текст или None при ошибке
        """
        try:
            url = f"{self.base_url}/v1/chat/completions"
            headers = self._get_headers()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False
            }
            
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if "choices" in data and len(data["choices"]) > 0:
                        content = data["choices"][0]["message"]["content"]
                        return content.strip()
                    else:
                        logger.error("Не получен контент в ответе LLM")
                        return None
                        
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка генерации LLM ({response.status}): {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при генерации LLM: {e}")
            return None
    
    async def generate_jql_query(self, user_question: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Генерирует JQL запрос на основе вопроса пользователя
        
        Args:
            user_question: Вопрос пользователя
            context: Контекст (клиенты, проекты, шаблоны, маппинги)
            
        Returns:
            JQL запрос или None при ошибке, или строка "UNKNOWN_CLIENT:name" если нужно уточнить маппинг
        """
        system_prompt = """Ты должен создать JQL запрос. Отвечай ТОЛЬКО JQL БЕЗ объяснений!

Правила:
- project = "ИМЯ_ПРОЕКТА" для поиска в конкретном проекте
- summary ~ "ТЕКСТ" OR description ~ "ТЕКСТ" для поиска по содержимому 
- created >= startOfMonth() для "этого месяца"
- created >= startOfWeek() для "этой недели"
- status = "Open" для открытых
- assignee is EMPTY для неназначенных

ПРИМЕРЫ:
Вход: "задачи в проекте ABC"
Выход: project = "ABC"

Вход: "найди задачи про Power BI"
Выход: summary ~ "Power BI" OR description ~ "Power BI"

Вход: "найди всё про Qlik Sense" 
Выход: summary ~ "Qlik Sense" OR description ~ "Qlik Sense"

Вход: "поиск упоминаний Python"
Выход: summary ~ "Python" OR description ~ "Python"

Вход: "новые задачи этого месяца"
Выход: created >= startOfMonth()

СТРОГО: отвечай только JQL без слов!"""

        # Формируем контекст для промпта
        context_text = ""
        if context.get("clients"):
            # context["clients"] - это список строк, не словарей
            clients = [f'"{c}"' for c in context["clients"]]
            context_text += f"\nДоступные клиенты: {', '.join(clients)}"
            
        if context.get("projects"):
            # context["projects"] - это список словарей с "key" и "name"
            projects = [f'"{p["key"]}" ({p["name"]})' for p in context["projects"]]
            context_text += f"\nДоступные проекты: {', '.join(projects)}"
            
        if context.get("users"):
            # context["users"] - это список строк, не словарей
            users = [f'"{u}"' for u in context["users"]]
            context_text += f"\nПользователи: {', '.join(users)}"

        prompt = f""""{user_question}"

Создай JQL:"""

        try:
            jql = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # Низкая температура для точности
                max_tokens=200
            )
            
            if jql:
                # Логируем исходный ответ от LLM
                logger.info(f"Исходный ответ от LLM: {jql}")
                # Очищаем от лишних символов и тегов
                jql = self._clean_jql_response(jql)
                logger.info(f"Очищенный JQL: {jql}")
                
                # Дополнительная проверка валидности
                if not jql or len(jql.strip()) < 5 or not self._is_valid_jql_format(jql):
                    logger.warning(f"JQL невалидный: '{jql}', попробуем fallback")
                    return await self._generate_smart_jql(user_question, context)
                    
                return jql
                
            return None
            
        except Exception as e:
            logger.error(f"Ошибка генерации JQL: {e}")
            return None
    
    async def interpret_query_intent(self, user_question: str) -> Dict[str, Any]:
        """
        Интерпретирует намерение пользователя и извлекает параметры
        
        Args:
            user_question: Вопрос пользователя
            
        Returns:
            Dict с параметрами запроса
        """
        system_prompt = """Ты - анализатор намерений для Jira бота. Проанализируй вопрос пользователя и верни JSON с параметрами.

Возможные типы запросов:
- "analytics" - аналитика, статистика, подсчеты
- "search" - поиск конкретных задач
- "worklog" - вопросы о списании времени
- "status" - вопросы о статусах задач
- "chart" - требуется визуализация

Параметры для извлечения:
- client: название клиента/компании
- project: название или ключ проекта  
- assignee: имя сотрудника
- date_range: период времени
- issue_type: тип задачи (Bug, Task, Epic)
- status: статус задачи
- chart_type: тип графика (bar, line, pie)
- group_by: по чему группировать данные (status, project, priority, assignee, issue_type)

ПРАВИЛА ОПРЕДЕЛЕНИЯ ТИПА ГРАФИКА:
- "круговая диаграмма", "круговой график", "pie chart" → chart_type: "pie"
- "столбчатая диаграмма", "столбчатый график", "bar chart" → chart_type: "bar"  
- "линейный график", "линейная диаграмма", "line chart" → chart_type: "line"

ПРАВИЛА ОПРЕДЕЛЕНИЯ ГРУППИРОВКИ:
- "в разрезе проектов", "по проектам", "группируй по проектам", "группировка по проектам" → group_by: "project"
- "в разрезе статусов", "по статусам", "группируй по статусам", "группировка по статусам" → group_by: "status"  
- "по приоритетам", "в разрезе приоритетов", "группируй по приоритетам", "группировка по приоритетам" → group_by: "priority"
- "по исполнителям", "в разрезе исполнителей", "группируй по исполнителям", "группировка по исполнителям" → group_by: "assignee"
- "по типам задач", "в разрезе типов", "группируй по типам", "группировка по типам" → group_by: "issue_type"

Примеры:
Вход: "покажи количество открытых задач в разрезе проектов в виде круговой диаграммы"
Выход: {
  "intent": "analytics",
  "parameters": {
    "status": "открытых",
    "chart_type": "pie",
    "group_by": "project"
  },
  "needs_chart": true
}

Вход: "статистика задач по статусам как график"
Выход: {
  "intent": "analytics", 
  "parameters": {
    "chart_type": "bar",
    "group_by": "status"
  },
  "needs_chart": true
}

Отвечай ТОЛЬКО JSON, без объяснений."""

        try:
            response = await self.generate_completion(
                prompt=f'Вопрос пользователя: "{user_question}"',
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=300
            )
            
            if response:
                # Очищаем ответ от служебных тегов
                clean_response = self._clean_json_response(response)
                # Попытка распарсить JSON
                try:
                    intent_data = json.loads(clean_response)
                    return intent_data
                except json.JSONDecodeError:
                    logger.warning(f"Не удалось распарсить JSON ответ: {clean_response}")
                    
            # Fallback - простой анализ
            return self._simple_intent_analysis(user_question)
            
        except Exception as e:
            logger.error(f"Ошибка анализа намерений: {e}")
            return self._simple_intent_analysis(user_question)

    async def extract_entities_from_query(self, user_question: str) -> Dict[str, Any]:
        """
        Извлекает сущности из запроса пользователя для JQL генерации
        
        Args:
            user_question: Вопрос пользователя
            
        Returns:
            Dict с извлеченными сущностями
        """
        system_prompt = """Ты извлекаешь сущности из запроса пользователя. Отвечай ТОЛЬКО JSON.

ВРЕМЕННЫЕ ПЕРИОДЫ (time_period):
• "сегодня", "за сегодня" → "сегодня"
• "вчера", "за вчера" → "вчера" 
• "эта неделя", "за эту неделю" → "эта неделя"
• "прошлая неделя" → "прошлая неделя"
• "этот месяц", "в этом месяце" → "этот месяц"
• "прошлый месяц" → "прошлый месяц"
• "в июле", "июль", "за июль" → "в июле"
• "последняя неделя" → "последняя неделя"
• "30 дней", "старше 30 дней" → "30 дней"

СТАТУСЫ (status_intent):
• "открыт", "открытых", "активн" → "open"
• "закрыт", "закрыли", "готов", "завершен" → "closed"
• "все", "любой" → "all"

ТИПЫ ЗАПРОСОВ (query_type):
• "сколько", "количество", "подсчет" → "count"
• "статистика", "аналитика" → "analytics"
• "найди", "покажи", "список" → "list"
• "топ", "рейтинг" → "ranking"

ТИПЫ ЗАДАЧ (issue_type):
• "баг", "баги", "ошибка" → "Bug"
• "задача", "таск" → "Task"
• "эпик" → "Epic"

ИСПОЛНИТЕЛИ (assignee):
• "без исполнителя", "неназначен" → "UNASSIGNED"
• "мои", "my", "назначенные мне" → "CURRENT_USER"

ПРИОРИТЕТЫ (priority):
• "высокий", "критический" → "High"
• "низкий" → "Low"
• "средний" → "Medium"

ПРИМЕРЫ:

"задачи созданные сегодня":
{
  "time_period": "сегодня",
  "status_intent": "all",
  "query_type": "list"
}

"сколько багов закрыли в июле":
{
  "issue_type": "Bug",
  "status_intent": "closed", 
  "time_period": "в июле",
  "query_type": "count"
}

"задачи без исполнителя старше 30 дней":
{
  "assignee": "UNASSIGNED",
  "time_period": "30 дней",
  "query_type": "list"
}

"статистика по исполнителям":
{
  "query_type": "analytics"
}

ОТВЕЧАЙ ТОЛЬКО JSON С ПОЛЯМИ:
{
  "client_name": null,
  "status_intent": "all",
  "time_period": null,
  "query_type": "list",
  "search_text": null,
  "issue_type": null,
  "assignee": null,
  "priority": null
}"""

        try:
            prompt = f'ВОПРОС: "{user_question}"\n\nТЫ ОТВЕЧАЕШЬ ТОЛЬКО JSON БЕЗ ОБЪЯСНЕНИЙ:'
            
            result = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.0,
                max_tokens=100  # Уменьшаем для принуждения к краткости
            )
            
            if result:
                logger.info(f"LLM ответ для сущностей (сырой): {result}")
                # Очищаем и парсим JSON
                cleaned_result = self._clean_json_response(result)
                logger.info(f"LLM ответ для сущностей (очищенный): {cleaned_result}")
                
                try:
                    entities = json.loads(cleaned_result)
                    logger.info(f"✅ Извлечены сущности: {entities}")
                    return entities
                except json.JSONDecodeError as json_error:
                    logger.error(f"❌ Ошибка парсинга JSON: {json_error}")
                    logger.error(f"❌ Проблемный JSON: '{cleaned_result}'")
                    # Fallback - возвращаем пустые сущности
                    logger.warning("Использую fallback пустые сущности")
                    return {
                        "client_name": None,
                        "status_intent": "all",
                        "time_period": None,
                        "query_type": "search",
                        "search_text": None,
                        "issue_type": None,
                        "assignee": None,
                        "priority": None
                    }
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка извлечения сущностей: {e}")
            
        # Общий fallback если все попытки провалились
        logger.warning("⚠️ Использую общий fallback - пустые сущности")
        return {
            "client_name": None,
            "status_intent": "all",
            "time_period": None,
            "query_type": "search",
            "search_text": None,
            "issue_type": None,
            "assignee": None,
            "priority": None
        }
    
    def _clean_jql_response(self, response: str) -> str:
        """Очищает ответ LLM от служебных тегов и оставляет только JQL"""
        import re
        
        # Удаляем всё содержимое между <think> и </think>
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # Удаляем любые XML/HTML теги
        response = re.sub(r'<[^>]+>', '', response)
        
        # Удаляем лишние пробелы и переносы строк
        response = re.sub(r'\s+', ' ', response).strip()
        
        # НЕ удаляем кавычки! Они важны для JQL значений
        # Убираем только обрамляющие обратные кавычки (если есть)
        if response.startswith('`') and response.endswith('`'):
            response = response[1:-1].strip()
        
        return response
    
    def _clean_json_response(self, response: str) -> str:
        """Агрессивно извлекает JSON из ответа LLM"""
        import re
        
        # Удаляем всё содержимое между <think> и </think>
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        
        # Удаляем любые XML/HTML теги
        response = re.sub(r'<[^>]+>', '', response)
        
        # Ищем последний (наиболее вероятный) JSON блок между фигурными скобками
        json_matches = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, flags=re.DOTALL)
        if json_matches:
            # Берем последний найденный JSON (обычно самый полный)
            json_candidate = json_matches[-1].strip()
            logger.info(f"Найдено JSON кандидатов: {len(json_matches)}, выбран последний")
            return json_candidate
        
        # Если JSON не найден в фигурных скобках, пробуем найти хотя бы ключи
        if 'client_name' in response or 'status_intent' in response:
            # Попробуем извлечь структуру из текста
            lines = response.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if '{' in line or in_json:
                    in_json = True
                    json_lines.append(line)
                    if '}' in line:
                        break
            if json_lines:
                potential_json = '\n'.join(json_lines)
                json_match = re.search(r'\{.*?\}', potential_json, flags=re.DOTALL)
                if json_match:
                    return json_match.group(0).strip()
        
        # Последняя попытка - возвращаем то что есть
        return response.strip()
    
    def _is_valid_jql_format(self, jql: str) -> bool:
        """Проверяет, похож ли текст на JQL запрос"""
        jql = jql.lower().strip()
        
        # Проверяем, что это не обычный текст
        if any(word in jql for word in ['okay', 'let\'s', 'tackle', 'user', 'asking', 'first', 'need']):
            return False
            
        # Проверяем наличие JQL ключевых слов
        jql_keywords = ['project', 'created', 'status', 'assignee', 'and', 'or', '=', '>=', '<=']
        has_keywords = any(keyword in jql for keyword in jql_keywords)
        
        return has_keywords and len(jql) < 200  # Ограничиваем длину JQL
    
    async def _generate_smart_jql(self, question: str, context: Dict[str, Any]) -> str:
        """Генерирует JQL используя LLM для извлечения сущностей"""
        
        # 1. Извлекаем сущности из запроса с помощью LLM
        entities = await self.extract_entities_from_query(question)
        logger.info(f"Smart JQL: извлечены сущности: {entities}")
        
        # 2. Обрабатываем клиента и проект
        client_name = entities.get("client_name")
        project = None
        
        if client_name:
            # Проверяем маппинги клиентов из RAG
            client_mappings = context.get("client_mappings", {})
            if client_mappings and client_name in client_mappings:
                project = client_mappings[client_name]
                logger.info(f"Использован маппинг клиента: {client_name} → {project}")
            else:
                # Если маппинг не найден - запрашиваем у пользователя
                logger.info(f"Маппинг для клиента '{client_name}' не найден")
                return f"UNKNOWN_CLIENT:{client_name}"
        
        # 3. Обрабатываем исполнителя
        assignee = entities.get("assignee")
        assignee_jql = None
        if assignee:
            if assignee == "UNASSIGNED":
                assignee_jql = "assignee is EMPTY"
            elif assignee == "CURRENT_USER":
                assignee_jql = "assignee = currentUser()"
                logger.info("Используется текущий пользователь для поиска")
            else:
                # Ищем пользователя в маппингах или используем как есть
                user_mappings = context.get("user_mappings", {})
                if user_mappings and assignee in user_mappings:
                    username = user_mappings[assignee]
                    assignee_jql = f'assignee = "{username}"'
                    logger.info(f"Использован маппинг пользователя: {assignee} → {username}")
                else:
                    # Пробуем использовать как username напрямую
                    assignee_jql = f'assignee = "{assignee}"'
                    logger.info(f"Используем исполнителя как есть: {assignee}")
        
        # 4. Формируем части JQL
        jql_parts = []
        
        # Добавляем проект
        if project:
            clean_project = self._clean_project_name(project)
            jql_parts.append(f'project = "{clean_project}"')
        
        # Добавляем исполнителя
        if assignee_jql:
            jql_parts.append(assignee_jql)
        
        # Добавляем тип задачи
        issue_type = entities.get("issue_type")
        if issue_type:
            jql_parts.append(f'issuetype = "{issue_type}"')
            logger.info(f"Добавлен тип задачи: {issue_type}")
        
        # Добавляем приоритет
        priority = entities.get("priority")
        if priority:
            jql_parts.append(f'priority = "{priority}"')
            logger.info(f"Добавлен приоритет: {priority}")
        
        # 5. Обрабатываем статусы на основе намерения
        status_intent = entities.get("status_intent", "all")
        jira_dictionaries = context.get('jira_dictionaries', {})
        
        if status_intent == "open":
            open_statuses = self._get_open_statuses(jira_dictionaries)
            if open_statuses:
                statuses_str = ', '.join([f'"{s}"' for s in open_statuses])
                jql_parts.append(f'status in ({statuses_str})')
            else:
                # Fallback если справочники недоступны
                jql_parts.append('status in ("Открыт", "В работе")')
                
        elif status_intent == "closed":
            closed_statuses = self._get_closed_statuses(jira_dictionaries)
            if closed_statuses:
                statuses_str = ', '.join([f'"{s}"' for s in closed_statuses])
                jql_parts.append(f'status in ({statuses_str})')
            else:
                # Fallback если справочники недоступны
                jql_parts.append('status in ("Закрыт", "Готово", "Отменен")')
        
        # 6. Обрабатываем временной период
        time_period = entities.get("time_period")
        if time_period:
            time_jql = self._convert_time_period_to_jql(time_period)
            if time_jql:
                jql_parts.append(time_jql)
        
        # 7. Обрабатываем текстовый поиск
        search_text = entities.get("search_text")
        if search_text:
            # Ищем по заголовку и описанию задач
            # Экранируем кавычки для безопасности
            safe_search_text = search_text.replace('"', '\\"')
            text_search_jql = f'(summary ~ "{safe_search_text}" OR description ~ "{safe_search_text}")'
            jql_parts.append(text_search_jql)
            logger.info(f"Добавлен текстовый поиск: {search_text}")
        
        # 8. Улучшенный fallback если ничего не найдено
        if not jql_parts:
            # Определяем тип запроса для разного fallback
            query_type = entities.get("query_type", "search")
            
            if query_type in ["analytics", "count", "ranking"]:
                # Для аналитических запросов - все задачи за последний месяц
                return 'created >= -30d'
            elif project:
                clean_project = self._clean_project_name(project)
                return f'project = "{clean_project}"'
            else:
                # Для обычного поиска - задачи текущего пользователя
                return 'assignee = currentUser() AND created >= startOfWeek()'
        
        final_jql = ' AND '.join(jql_parts)
        logger.info(f"Smart JQL сгенерирован: {final_jql}")
        return final_jql
    
    def _convert_time_period_to_jql(self, time_period: str) -> str:
        """Конвертирует временной период в JQL условие"""
        if not time_period:
            return ""
            
        time_lower = time_period.lower()
        
        # Относительные периоды
        if time_lower in ['этот месяц', 'этом месяце', 'в этом месяце']:
            return 'created >= startOfMonth()'
        elif time_lower in ['прошлый месяц', 'прошлом месяце']:
            return 'created >= startOfMonth(-1) AND created < startOfMonth()'
        elif time_lower in ['эта неделя', 'этой неделе', 'за эту неделю']:
            return 'created >= startOfWeek()'
        elif time_lower in ['прошлая неделя', 'прошлой неделе', 'за прошлую неделю']:
            return 'created >= startOfWeek(-1) AND created < startOfWeek()'
        elif time_lower in ['сегодня', 'за сегодня', 'созданные сегодня']:
            return 'created >= startOfDay()'
        elif time_lower in ['вчера', 'за вчера']:
            return 'created >= startOfDay(-1) AND created < startOfDay()'
        elif time_lower in ['последний месяц', 'за последний месяц']:
            return 'created >= -30d'
        elif time_lower in ['последняя неделя', 'за последнюю неделю']:
            return 'created >= -7d'
        elif '30 дней' in time_lower or 'старше 30 дней' in time_lower:
            return 'created <= -30d'  # Задачи старше 30 дней
        elif '7 дней' in time_lower or 'старше 7 дней' in time_lower:
            return 'created <= -7d'  # Задачи старше 7 дней
        elif '1 день' in time_lower or 'старше 1 дня' in time_lower:
            return 'created <= -1d'  # Задачи старше 1 дня
        
        # Конкретные месяцы (упрощенно - за текущий год)
        months_mapping = {
            'январь': '01', 'января': '01', 'в январе': '01',
            'февраль': '02', 'февраля': '02', 'в феврале': '02', 
            'март': '03', 'марта': '03', 'в марте': '03',
            'апрель': '04', 'апреля': '04', 'в апреле': '04',
            'май': '05', 'мая': '05', 'в мае': '05',
            'июнь': '06', 'июня': '06', 'в июне': '06',
            'июль': '07', 'июля': '07', 'в июле': '07',
            'август': '08', 'августа': '08', 'в августе': '08',
            'сентябрь': '09', 'сентября': '09', 'в сентябре': '09',
            'октябрь': '10', 'октября': '10', 'в октябре': '10',
            'ноябрь': '11', 'ноября': '11', 'в ноябре': '11',
            'декабрь': '12', 'декабря': '12', 'в декабре': '12'
        }
        
        for month_name, month_num in months_mapping.items():
            if month_name in time_lower:
                from datetime import datetime
                current_year = datetime.now().year
                
                # Вычисляем следующий месяц для верхней границы
                month_int = int(month_num)
                if month_int == 12:
                    next_month = "01"
                    next_year = current_year + 1
                else:
                    next_month = f"{month_int + 1:02d}"
                    next_year = current_year
                
                return f'created >= "{current_year}-{month_num}-01" AND created < "{next_year}-{next_month}-01"'
        
        # Если не распознали - возвращаем пустую строку
        return ""
    
    def _clean_project_name(self, project_name: str) -> str:
        """Очищает название проекта для безопасного использования в JQL"""
        # Убираем лишние пробелы и переводим в нижний регистр для поиска ключа
        cleaned = project_name.strip()
        
        # Список возможных ключей проектов для общих названий
        project_mappings = {
            'иль де ботэ': 'IDB',
            'иль де боте': 'IDB', 
            'ильдеботэ': 'IDB',
            'тестовый': 'TEST',
            'демо': 'DEMO'
        }
        
        # Проверяем маппинги (нечувствительно к регистру)
        for name_variant, key in project_mappings.items():
            if name_variant in cleaned.lower():
                return key
        
        # Если это похоже на ключ проекта (короткий, заглавные буквы)
        if len(cleaned) <= 10 and cleaned.isupper():
            return cleaned
            
        # Возвращаем очищенное название
        return cleaned
    
    def _simple_intent_analysis(self, question: str) -> Dict[str, Any]:
        """
        Простой анализ намерений без LLM (fallback)
        
        Args:
            question: Вопрос пользователя
            
        Returns:
            Dict с базовыми параметрами
        """
        question_lower = question.lower()
        
        # Определяем тип запроса (worklog проверяем первым, так как может содержать "сколько")
        worklog_phrases = [
            "сколько часов", "часов списал", "время списал", "трудозатраты", "worklog",
            "сколько потратил", "сколько указал", "списал времени", "потратили времени",
            "указал времени", "трудозатрат", "время по", "часы по", "время на",
            "часы на", "затратил", "затратили", "списали", "потратил время",
            "указал время", "вложили времени", "затрачено времени", "списано времени",
            "сколько времени потратил", "сколько времени списал", "время потратил",
            "время указал", "времени на", "списал часов", "потратил часов",
            "указал часов", "затратил часов"
        ]
        
        worklog_patterns = [
            r"[А-Яа-я]+\s+списал", r"[А-Яа-я]+\s+потратил", r"[А-Яа-я]+\s+указал", r"[А-Яа-я]+\s+затратил",
            r"списал\s+[А-Яа-я]+", r"потратил\s+[А-Яа-я]+", r"указал\s+[А-Яа-я]+", r"затратил\s+[А-Яа-я]+"
        ]
        
        if (any(phrase in question_lower for phrase in worklog_phrases) or 
            any(re.search(pattern, question_lower) for pattern in worklog_patterns)):
            intent = "worklog"
        elif any(word in question_lower for word in ["сколько", "количество", "count", "статистика"]):
            intent = "analytics"
        elif any(word in question_lower for word in ["график", "диаграмма", "chart", "покажи"]):
            intent = "chart"
        elif any(word in question_lower for word in ["статус", "status", "progress"]):
            intent = "status"
        else:
            intent = "search"
        
        # Нужен ли график
        needs_chart = any(word in question_lower for word in [
            "график", "диаграмма", "chart", "покажи", "визуал"
        ])
        
        # Определяем параметры
        parameters = {}
        
        # Для worklog запросов извлекаем дополнительные параметры
        if intent == "worklog":
            # Определяем кто (пользователь) - используем более точные паттерны
            user_patterns = [
                r"([А-Яа-я]+(?:\s+[А-Яа-я]+){0,2})\s+(?:списал|потратил|указал|затратил)",  # "Иванов списал"
                r"(?:списал|потратил|указал|затратил)\s+([А-Яа-я]+(?:\s+[А-Яа-я]+){0,2})",  # "списал Иванов"
                r"трудозатраты\s+([А-Яа-я]+(?:\s+[А-Яа-я]+){0,2})(?:\s+за|\s+в|\s*$)",  # "трудозатраты Иванова за"
                r"(?:время|часы)\s+([А-Яа-я]+(?:\s+[А-Яа-я]+){0,2})(?:\s+за|\s+в|\s+на|\s*$)",  # "время Иванова за"
            ]
            
            for pattern in user_patterns:
                match = re.search(pattern, question_lower)
                if match:
                    name = match.group(1).strip()
                    # Фильтруем стоп-слова
                    stop_words = ['сколько', 'время', 'часов', 'часы', 'которое', 'которые', 'за', 'в', 'на', 'по']
                    name_parts = [part for part in name.split() if part not in stop_words]
                    if name_parts:
                        parameters["assignee"] = ' '.join(name_parts)
                        break
            
            # Определяем временной период
            if any(period in question_lower for period in ["в июле", "июль", "за июль"]):
                parameters["time_period"] = "июль"
            elif any(period in question_lower for period in ["в июне", "июнь", "за июнь"]):
                parameters["time_period"] = "июнь"
            elif any(period in question_lower for period in ["этот месяц", "в этом месяце"]):
                parameters["time_period"] = "этот месяц"
            elif any(period in question_lower for period in ["прошлый месяц", "в прошлом месяце"]):
                parameters["time_period"] = "прошлый месяц"
            elif any(period in question_lower for period in ["эта неделя", "на этой неделе"]):
                parameters["time_period"] = "эта неделя"
            elif any(period in question_lower for period in ["прошлая неделя", "на прошлой неделе"]):
                parameters["time_period"] = "прошлая неделя"
            elif any(period in question_lower for period in ["сегодня", "за сегодня"]):
                parameters["time_period"] = "сегодня"
            elif any(period in question_lower for period in ["вчера", "за вчера"]):
                parameters["time_period"] = "вчера"
                
            # Определяем проект если указан
            project_patterns = [
                r"(?:на проект|по проекту|в проекте)\s+([A-Z]+(?:-\w+)*)",
                r"проект\s+([A-Z]+(?:-\w+)*)",
            ]
            
            for pattern in project_patterns:
                match = re.search(pattern, question_lower)
                if match:
                    parameters["project"] = match.group(1).strip()
                    break
        
        # Для обычных запросов определяем группировку
        if any(phrase in question_lower for phrase in [
            "по проектам", "группируй по проектам", "группировка по проектам", 
            "в разрезе проектов", "разбить по проектам"
        ]):
            parameters["group_by"] = "project"
        elif any(phrase in question_lower for phrase in [
            "по статусам", "группируй по статусам", "группировка по статусам",
            "в разрезе статусов", "разбить по статусам"  
        ]):
            parameters["group_by"] = "status"
        elif any(phrase in question_lower for phrase in [
            "по приоритетам", "группируй по приоритетам", "группировка по приоритетам",
            "в разрезе приоритетов", "разбить по приоритетам"
        ]):
            parameters["group_by"] = "priority" 
        elif any(phrase in question_lower for phrase in [
            "по исполнителям", "группируй по исполнителям", "группировка по исполнителям",
            "в разрезе исполнителей", "разбить по исполнителям"
        ]):
            parameters["group_by"] = "assignee"
        elif any(phrase in question_lower for phrase in [
            "по типам", "группируй по типам", "группировка по типам",
            "в разрезе типов", "разбить по типам", "по типам задач"
        ]):
            parameters["group_by"] = "issue_type"
        
        # Определяем тип графика
        if any(phrase in question_lower for phrase in [
            "круговая", "круговой", "pie", "пирог"
        ]):
            parameters["chart_type"] = "pie"
        elif any(phrase in question_lower for phrase in [
            "линейный", "линейная", "line", "динамика"
        ]):
            parameters["chart_type"] = "line"
        else:
            parameters["chart_type"] = "bar"  # по умолчанию столбчатая
        
        return {
            "intent": intent,
            "parameters": parameters,
            "needs_chart": needs_chart
        }
    
    async def generate_response_text(self, query_result: Dict[str, Any], 
                                   user_question: str) -> str:
        """
        Генерирует текстовый ответ на основе результатов запроса
        
        Args:
            query_result: Результаты выполнения запроса
            user_question: Оригинальный вопрос пользователя
            
        Returns:
            Текстовый ответ
        """
        system_prompt = """Ты - помощник по Jira, который формулирует ответы на русском языке.
Тебе дают результаты JQL запроса и исходный вопрос пользователя.

Твоя задача:
1. Кратко ответить на вопрос пользователя
2. Привести ключевые данные из результата
3. Добавить полезные инсайты если есть
4. Использовать эмодзи для улучшения восприятия

Стиль ответа:
- Дружелюбный и профессиональный
- Конкретный и информативный  
- Структурированный (используй списки)
- На русском языке

Если данных много - дай краткую сводку. Если данных нет - объясни возможные причины."""

        # Подготавливаем данные для промпта
        data_summary = {
            "total_issues": len(query_result.get("issues", [])),
            "jql_query": query_result.get("jql", ""),
            "execution_time": query_result.get("execution_time", 0),
            "has_chart": bool(query_result.get("chart_url"))
        }
        
        # Если есть задачи, добавляем примеры
        if query_result.get("issues"):
            issues = query_result["issues"][:3]  # Первые 3 задачи
            data_summary["sample_issues"] = [
                {
                    "key": issue.get("key"),
                    "summary": issue.get("summary", "")[:100],
                    "status": issue.get("status"),
                    "assignee": issue.get("assignee")
                }
                for issue in issues
            ]

        prompt = f"""Вопрос пользователя: "{user_question}"

Результаты запроса:
{json.dumps(data_summary, ensure_ascii=False, indent=2)}

Сформулируй ответ пользователю:"""

        try:
            response = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            return response or "Получены результаты, но не удалось сформулировать ответ."
            
        except Exception as e:
            logger.error(f"Ошибка генерации ответа: {e}")
            
            # Fallback - простой ответ
            total = len(query_result.get("issues", []))
            if total == 0:
                return "🔍 По вашему запросу задач не найдено."
            else:
                return f"📊 Найдено задач: **{total}**"
    
    async def suggest_improvements(self, user_question: str, 
                                 results_count: int) -> List[str]:
        """
        Предлагает улучшения для запроса
        
        Args:
            user_question: Оригинальный вопрос
            results_count: Количество найденных результатов
            
        Returns:
            Список предложений
        """
        if results_count == 0:
            return [
                "Попробуйте расширить временной период",
                "Проверьте корректность названий клиентов и проектов",
                "Уберите фильтры по статусу или исполнителю"
            ]
        elif results_count > 100:
            return [
                "Уточните временной период для более точных результатов",
                "Добавьте фильтр по статусу или исполнителю",
                "Ограничьте поиск конкретным проектом"
            ]
        else:
            return []
    
    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Извлекает именованные сущности из текста
        
        Args:
            text: Текст для анализа
            
        Returns:
            Dict с извлеченными сущностями
        """
        system_prompt = """Извлеки именованные сущности из текста пользователя.

Типы сущностей:
- PERSON: имена людей, сотрудников
- ORG: названия организаций, клиентов, компаний
- DATE: даты, периоды времени
- PROJECT: названия проектов, системы

Верни JSON:
{
  "PERSON": ["Сергей Журавлёв"],
  "ORG": ["Иль-Де-Ботэ", "Бургер-Кинг"],
  "DATE": ["июль", "последние 3 месяца"],
  "PROJECT": ["Битрикс", "Visiology"]
}

Если сущностей нет - верни пустые массивы."""

        try:
            response = await self.generate_completion(
                prompt=f'Текст: "{text}"',
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            if response:
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    pass
                    
        except Exception as e:
            logger.error(f"Ошибка извлечения сущностей: {e}")
        
        # Fallback
        return {"PERSON": [], "ORG": [], "DATE": [], "PROJECT": []}



    def _get_open_statuses(self, jira_dictionaries: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Получает список открытых статусов из справочников Jira"""
        try:
            statuses = jira_dictionaries.get('statuses', [])
            open_statuses = set()  # Используем set для автоматической дедупликации
            
            for status in statuses:
                category = status.get('category', '').lower()
                name = status.get('name', '')
                status_id = status.get('id', '')
                
                logger.debug(f"Проверяем статус: name='{name}', category='{category}', id='{status_id}'")
                
                # Приоритет - категории статусов
                if category in ['to do', 'indeterminate', 'new']:
                    open_statuses.add(name)
                    logger.debug(f"  ✅ Добавлен по категории: {name}")
                # Статусы 'в работе' - открытые
                elif 'работе' in name.lower() and 'не' not in name.lower():
                    open_statuses.add(name)
                    logger.debug(f"  ✅ Добавлен как 'в работе': {name}")
                # Точная проверка по названию
                elif name.lower() in ['открыт', 'открыто', 'новый', 'создан', 'создано']:
                    open_statuses.add(name)
                    logger.debug(f"  ✅ Добавлен точным названием: {name}")
            
            # Преобразуем в список и сортируем для стабильности
            result = sorted(list(open_statuses))
            logger.info(f"Найдены открытые статусы ({len(result)}): {result}")
            return result
            
        except Exception as e:
            logger.error(f"Ошибка получения открытых статусов: {e}")
            return []
    
    def _get_closed_statuses(self, jira_dictionaries: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        """Получает список закрытых статусов из справочников Jira"""
        try:
            statuses = jira_dictionaries.get('statuses', [])
            closed_statuses_set = set()  # Используем set для дедупликации
            
            for status in statuses:
                category = status.get('category', '').lower()
                name = status.get('name', '').lower()
                
                # Сначала проверяем категорию Jira (самый надежный способ)
                if category in ['done', 'complete', 'closed']:
                    closed_statuses_set.add(status.get('name'))
                else:
                    # Для статусов без правильной категории - проверяем по ключевым словам
                    # НО исключаем статусы с "к выполнению", "для выполнения", "в работе" и т.п.
                    if (any(keyword in name for keyword in ['закрыт', 'готово', 'завершен', 'отменен', 'cancel']) or
                        (name.endswith('выполнено') and 'к выполнению' not in name and 'для выполнения' not in name)):
                        # Исключаем статусы которые содержат слова указывающие на активную работу или подготовку
                        if not any(exclude_word in name for exclude_word in [
                            'работе', 'progress', 'открыт', 'open', 'новый', 'new',
                            'к выполнению', 'для выполнения', 'отобрано', 'назначено', 
                            'в очереди', 'ожидание', 'планирование'
                        ]):
                            closed_statuses_set.add(status.get('name'))  # Добавляем оригинальное имя (не lowercase)
            
            # Добавляем общие закрытые статусы если они есть в справочнике
            for common_status in ["Закрыт", "Готово", "Выполнено", "Done", "Closed", "Resolved", "Cancelled", "Отменен"]:
                for status in statuses:
                    if status.get('name', '').lower() == common_status.lower():
                        closed_statuses_set.add(status.get('name'))
            
            closed_statuses_list = list(closed_statuses_set)
            logger.info(f"Найдены закрытые статусы: {closed_statuses_list}")
            return closed_statuses_list
            
        except Exception as e:
            logger.error(f"Ошибка получения закрытых статусов: {e}")
            return []

# Глобальный экземпляр сервиса
llm_service = LLMService() 