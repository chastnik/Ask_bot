"""
Сервис для работы с локальной LLM
"""
import aiohttp
import asyncio
import json
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
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    async def test_connection(self) -> bool:
        """
        Тестирует подключение к LLM
        
        Returns:
            bool: True если соединение успешно
        """
        try:
            url = f"{self.base_url}/v1/models"
            headers = self._get_headers()
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    models_data = await response.json()
                    models = [model.get("id", "") for model in models_data.get("data", [])]
                    
                    if self.model in models:
                        logger.info(f"Успешное подключение к LLM. Модель {self.model} доступна")
                        return True
                    else:
                        logger.warning(f"Модель {self.model} не найдена. Доступные: {models}")
                        return False
                else:
                    logger.error(f"Ошибка подключения к LLM: {response.status}")
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
            context: Контекст (клиенты, проекты, шаблоны)
            
        Returns:
            JQL запрос или None при ошибке
        """
        system_prompt = """Ты - эксперт по Jira Query Language (JQL). Твоя задача - преобразовать естественный вопрос пользователя в правильный JQL запрос.

ВАЖНЫЕ ПРАВИЛА JQL:
1. Проекты указываются через project = "KEY" или project in ("KEY1", "KEY2")
2. Даты в формате YYYY-MM-DD или используй функции like startOfWeek(), startOfMonth()
3. Статусы: "To Do", "In Progress", "Done", "Closed"
4. assignee = "username" или assignee is EMPTY
5. Для временных периодов используй created >= "2024-01-01" AND created <= "2024-01-31"
6. worklogAuthor = "username" для поиска по автору worklog
7. worklogDate >= "2024-01-01" для фильтрации по дате worklog

ДОСТУПНЫЕ ПОЛЯ:
- project, key, summary, description, status, assignee, reporter, created, updated, resolved
- priority, issuetype, worklogAuthor, worklogDate, timeSpent
- labels, component, fixVersion, duedate

ФУНКЦИИ ВРЕМЕНИ:
- startOfWeek(), endOfWeek(), startOfMonth(), endOfMonth()  
- startOfYear(), endOfYear()
- now(), "-1w", "-1M", "-3M"

Отвечай ТОЛЬКО JQL запросом, без объяснений."""

        # Формируем контекст для промпта
        context_text = ""
        if context.get("clients"):
            clients = [f'"{c["name"]}"' for c in context["clients"]]
            context_text += f"\nДоступные клиенты: {', '.join(clients)}"
            
        if context.get("projects"):
            projects = [f'"{p["key"]}" ({p["name"]})' for p in context["projects"]]
            context_text += f"\nДоступные проекты: {', '.join(projects)}"
            
        if context.get("users"):
            users = [f'"{u}"' for u in context["users"]]
            context_text += f"\nПользователи: {', '.join(users)}"

        prompt = f"""Пользователь спрашивает: "{user_question}"

Контекст:{context_text}

Создай JQL запрос для этого вопроса:"""

        try:
            jql = await self.generate_completion(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,  # Низкая температура для точности
                max_tokens=200
            )
            
            if jql:
                # Очищаем от лишних символов
                jql = jql.strip().strip('"').strip("'").strip("`")
                logger.info(f"Сгенерирован JQL: {jql}")
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

Пример ответа:
{
  "intent": "analytics",
  "parameters": {
    "client": "Иль-Де-Ботэ",
    "date_range": "июль",
    "chart_type": "bar"
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
                # Попытка распарсить JSON
                try:
                    intent_data = json.loads(response)
                    return intent_data
                except json.JSONDecodeError:
                    logger.warning(f"Не удалось распарсить JSON ответ: {response}")
                    
            # Fallback - простой анализ
            return self._simple_intent_analysis(user_question)
            
        except Exception as e:
            logger.error(f"Ошибка анализа намерений: {e}")
            return self._simple_intent_analysis(user_question)
    
    def _simple_intent_analysis(self, question: str) -> Dict[str, Any]:
        """
        Простой анализ намерений без LLM (fallback)
        
        Args:
            question: Вопрос пользователя
            
        Returns:
            Dict с базовыми параметрами
        """
        question_lower = question.lower()
        
        # Определяем тип запроса
        if any(word in question_lower for word in ["сколько", "количество", "count", "статистика"]):
            intent = "analytics"
        elif any(word in question_lower for word in ["график", "диаграмма", "chart", "покажи"]):
            intent = "chart"
        elif any(word in question_lower for word in ["час", "время", "worklog", "списал"]):
            intent = "worklog"
        elif any(word in question_lower for word in ["статус", "status", "progress"]):
            intent = "status"
        else:
            intent = "search"
        
        # Нужен ли график
        needs_chart = any(word in question_lower for word in [
            "график", "диаграмма", "chart", "покажи", "визуал"
        ])
        
        return {
            "intent": intent,
            "parameters": {},
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


# Глобальный экземпляр сервиса
llm_service = LLMService() 