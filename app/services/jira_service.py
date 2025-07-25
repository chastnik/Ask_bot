"""
Сервис для интеграции с Jira API
"""
import re
import aiohttp
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin
import base64
import json
from loguru import logger

from app.config import settings
from app.models.schemas import JiraIssue, JiraSearchResult, JiraWorklog
from app.utils.auth import decrypt_password


class JiraAPIError(Exception):
    """Исключение для ошибок Jira API"""
    pass


class JiraAuthError(Exception):
    """Исключение для ошибок авторизации Jira"""
    pass


class JiraService:
    """Сервис для работы с Jira API"""
    
    def __init__(self):
        self.base_url = settings.jira_url
        self.session = None
        self._auth_cache = {}  # Кеш авторизованных сессий
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(ssl=False)  # Для внутренних сетей
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    def _get_auth_header(self, username: str, password: str) -> Dict[str, str]:
        """Создает заголовок авторизации для Basic Auth"""
        credentials = f"{username}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded_credentials}"}
    
    def _get_token_auth_header(self, username: str, token: str) -> Dict[str, str]:
        """Создает заголовок авторизации для API Token"""
        credentials = f"{username}:{token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded_credentials}"}
    
    async def test_connection(self, username: str, password: Optional[str] = None, 
                            token: Optional[str] = None) -> bool:
        """
        Тестирует подключение к Jira
        
        Args:
            username: Имя пользователя Jira
            password: Пароль (для Basic Auth)
            token: API токен (предпочтительный способ)
            
        Returns:
            bool: True если соединение успешно
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен для авторизации")
            
            url = urljoin(self.base_url, "/rest/api/2/myself")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    user_info = await response.json()
                    logger.info(f"Успешная авторизация в Jira для пользователя: {user_info.get('displayName')}")
                    return True
                elif response.status == 401:
                    logger.error("Неверные учетные данные Jira")
                    return False
                else:
                    logger.error(f"Ошибка подключения к Jira: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка при тестировании подключения к Jira: {e}")
            return False
    
    async def get_user_info(self, username: str, password: Optional[str] = None,
                          token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о пользователе Jira
        
        Args:
            username: Имя пользователя
            password: Пароль (опционально)
            token: API токен (опционально)
            
        Returns:
            Dict с информацией о пользователе или None при ошибке
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            url = urljoin(self.base_url, "/rest/api/2/myself")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Ошибка получения информации о пользователе: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении информации о пользователе: {e}")
            return None

    async def search_users(self, query: str, username: str, password: Optional[str] = None,
                         token: Optional[str] = None, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Поиск пользователей в Jira по запросу
        
        Args:
            query: Поисковый запрос (имя, email, username)
            username: Имя пользователя для авторизации
            password: Пароль (опционально)
            token: API токен (опционально)
            max_results: Максимальное количество результатов
            
        Returns:
            Список найденных пользователей
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            # Используем search endpoint для поиска пользователей
            url = urljoin(self.base_url, "/rest/api/2/user/search")
            params = {
                "username": query,  # Jira требует параметр username
                "maxResults": max_results
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    users = await response.json()
                    logger.info(f"Найдено пользователей: {len(users)} для запроса '{query}'")
                    return users
                elif response.status == 401:
                    raise JiraAuthError("Неавторизованный доступ к Jira")
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка поиска пользователей: {response.status} - {error_text}")
                    return []
                    
        except (JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователей: {e}")
            return []

    async def find_user_by_display_name(self, display_name: str, username: str, 
                                      password: Optional[str] = None, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Ищет пользователя по отображаемому имени
        
        Args:
            display_name: Отображаемое имени (например "Олег Антонов")
            username: Имя пользователя для авторизации
            password: Пароль (опционально)
            token: API токен (опционально)
            
        Returns:
            Информация о пользователе или None
        """
        try:
            # Сначала пытаемся найти в кэшированном справочнике пользователей
            from app.services.cache_service import cache_service
            
            # Получаем user_id для доступа к кэшу (используем username как user_id)
            async with cache_service as cache:
                cached_users = await cache.get_jira_dictionary("users", username)
                
            # Ищем в кэшированных пользователях
            if cached_users:
                # Точное совпадение по displayName
                for user in cached_users:
                    if user.get("displayName", "").lower() == display_name.lower():
                        logger.info(f"Найден пользователь в кэше: {display_name} → {user.get('name', 'N/A')}")
                        return user
                
                # Частичное совпадение
                for user in cached_users:
                    if display_name.lower() in user.get("displayName", "").lower():
                        logger.info(f"Найдено частичное совпадение в кэше: {display_name} → {user.get('displayName')} ({user.get('name', 'N/A')})")
                        return user
                
                # Поиск по частям имени в кэше
                name_parts = display_name.split()
                if len(name_parts) >= 2:
                    for user in cached_users:
                        user_display = user.get("displayName", "").lower()
                        if all(part.lower() in user_display for part in name_parts):
                            logger.info(f"Найден пользователь в кэше по частям имени: {display_name} → {user.get('displayName')} ({user.get('name', 'N/A')})")
                            return user
            
            # Если не найден в кэше, делаем API запрос
            logger.info(f"Пользователь не найден в кэше, ищем через API: {display_name}")
            users = await self.search_users(display_name, username, password, token)
            
            # Ищем точное совпадение по displayName
            for user in users:
                if user.get("displayName", "").lower() == display_name.lower():
                    logger.info(f"Найден пользователь: {display_name} → {user.get('name', 'N/A')}")
                    return user
            
            # Если точного совпадения нет, ищем частичное совпадение
            for user in users:
                if display_name.lower() in user.get("displayName", "").lower():
                    logger.info(f"Найдено частичное совпадение: {display_name} → {user.get('displayName')} ({user.get('name', 'N/A')})")
                    return user
            
            # Попробуем поиск по частям имени (имя и фамилия отдельно)
            name_parts = display_name.split()
            if len(name_parts) >= 2:
                for part in name_parts:
                    if len(part) >= 3:  # Минимум 3 символа для поиска
                        users = await self.search_users(part, username, password, token)
                        for user in users:
                            user_display = user.get("displayName", "").lower()
                            if all(part.lower() in user_display for part in name_parts):
                                logger.info(f"Найден пользователь по частям имени: {display_name} → {user.get('displayName')} ({user.get('name', 'N/A')})")
                                return user
            
            logger.warning(f"Пользователь не найден: {display_name}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка поиска пользователя {display_name}: {e}")
            return None
    
    async def search_issues(self, jql: str, username: str, password: Optional[str] = None,
                          token: Optional[str] = None, start_at: int = 0, 
                          max_results: int = 50, fields: Optional[List[str]] = None) -> JiraSearchResult:
        """
        Поиск задач в Jira по JQL запросу
        
        Args:
            jql: JQL запрос
            username: Имя пользователя
            password: Пароль (опционально)
            token: API токен (опционально)  
            start_at: Начальная позиция
            max_results: Максимальное количество результатов
            fields: Список полей для получения
            
        Returns:
            JiraSearchResult: Результат поиска
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            if not fields:
                fields = [
                    "key", "summary", "description", "status", "issuetype", 
                    "priority", "assignee", "reporter", "created", "updated",
                    "duedate", "resolutiondate", "project"
                ]
            
            payload = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": fields,
                "expand": ["changelog"]
            }
            
            url = urljoin(self.base_url, "/rest/api/2/search")
            
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Преобразуем в наши схемы
                    issues = []
                    for issue_data in data.get("issues", []):
                        try:
                            issue = self._parse_jira_issue(issue_data)
                            issues.append(issue)
                        except Exception as e:
                            logger.warning(f"Ошибка парсинга задачи {issue_data.get('key', 'unknown')}: {e}")
                    
                    return JiraSearchResult(
                        issues=issues,
                        total=data.get("total", 0),
                        start_at=data.get("startAt", 0),
                        max_results=data.get("maxResults", 0),
                        jql=jql
                    )
                    
                elif response.status == 400:
                    error_data = await response.json()
                    raise JiraAPIError(f"Неверный JQL запрос: {error_data.get('errorMessages', [])}")
                elif response.status == 401:
                    raise JiraAuthError("Неавторизованный доступ к Jira")
                else:
                    error_text = await response.text()
                    raise JiraAPIError(f"Ошибка поиска в Jira ({response.status}): {error_text}")
                    
        except (JiraAPIError, JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске в Jira: {e}")
            raise JiraAPIError(f"Неожиданная ошибка: {e}")
    
    def _parse_jira_issue(self, issue_data: Dict[str, Any]) -> JiraIssue:
        """
        Парсит данные задачи из Jira API в нашу схему
        
        Args:
            issue_data: Данные задачи из Jira API
            
        Returns:
            JiraIssue: Объект задачи
        """
        fields = issue_data.get("fields", {})
        
        # Парсим даты
        def parse_jira_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            try:
                # Jira возвращает даты в ISO формате
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except Exception:
                return None
        
        # Извлекаем assignee
        assignee = fields.get("assignee")
        assignee_name = assignee.get("displayName") if assignee else None
        
        # Извлекаем reporter
        reporter = fields.get("reporter", {})
        reporter_name = reporter.get("displayName", "Unknown")
        
        # Извлекаем project
        project = fields.get("project", {})
        project_key = project.get("key", "UNKNOWN")
        project_name = project.get("name", "Unknown Project")
        
        return JiraIssue(
            id=issue_data.get("id"),
            key=issue_data.get("key"),
            summary=fields.get("summary", ""),
            description=fields.get("description", ""),
            status=fields.get("status", {}).get("name", "Unknown"),
            issue_type=fields.get("issuetype", {}).get("name", "Unknown"),
            priority=fields.get("priority", {}).get("name", "Unknown"),
            assignee=assignee_name,
            reporter=reporter_name,
            created=parse_jira_date(fields.get("created")),
            updated=parse_jira_date(fields.get("updated")),
            due_date=parse_jira_date(fields.get("duedate")),
            resolved=parse_jira_date(fields.get("resolutiondate")),
            project_key=project_key,
            project_name=project_name
        )
    
    async def get_worklogs(self, issue_key: str, username: str, 
                         password: Optional[str] = None, token: Optional[str] = None) -> List[JiraWorklog]:
        """
        Получает worklogs для задачи
        
        Args:
            issue_key: Ключ задачи
            username: Имя пользователя
            password: Пароль (опционально)
            token: API токен (опционально)
            
        Returns:
            List[JiraWorklog]: Список worklogs
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            url = urljoin(self.base_url, f"/rest/api/2/issue/{issue_key}/worklog")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    worklogs = []
                    
                    for worklog_data in data.get("worklogs", []):
                        try:
                            worklog = JiraWorklog(
                                id=worklog_data.get("id"),
                                issue_key=issue_key,
                                author=worklog_data.get("author", {}).get("displayName", "Unknown"),
                                time_spent_seconds=worklog_data.get("timeSpentSeconds", 0),
                                created=datetime.fromisoformat(worklog_data.get("created").replace('Z', '+00:00')),
                                started=datetime.fromisoformat(worklog_data.get("started").replace('Z', '+00:00')),
                                comment=worklog_data.get("comment", "")
                            )
                            worklogs.append(worklog)
                        except Exception as e:
                            logger.warning(f"Ошибка парсинга worklog: {e}")
                    
                    return worklogs
                    
                elif response.status == 404:
                    logger.warning(f"Задача {issue_key} не найдена")
                    return []
                elif response.status == 401:
                    raise JiraAuthError("Неавторизованный доступ к Jira")
                else:
                    error_text = await response.text()
                    raise JiraAPIError(f"Ошибка получения worklogs ({response.status}): {error_text}")
                    
        except (JiraAPIError, JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении worklogs: {e}")
            raise JiraAPIError(f"Неожиданная ошибка: {e}")
    
    async def get_projects(self, username: str, password: Optional[str] = None,
                         token: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получает список проектов
        
        Args:
            username: Имя пользователя
            password: Пароль (опционально)
            token: API токен (опционально)
            
        Returns:
            List[Dict]: Список проектов
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            url = urljoin(self.base_url, "/rest/api/2/project")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    projects = await response.json()
                    return [
                        {
                            "key": project.get("key"),
                            "name": project.get("name"),
                            "description": project.get("description", ""),
                            "lead": project.get("lead", {}).get("displayName", "Unknown")
                        }
                        for project in projects
                    ]
                elif response.status == 401:
                    raise JiraAuthError("Неавторизованный доступ к Jira")
                else:
                    error_text = await response.text()
                    raise JiraAPIError(f"Ошибка получения проектов ({response.status}): {error_text}")
                    
        except (JiraAPIError, JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении проектов: {e}")
            raise JiraAPIError(f"Неожиданная ошибка: {e}")
    
    def build_jql_query(self, **filters) -> str:
        """
        Строит JQL запрос на основе фильтров
        
        Args:
            **filters: Фильтры для запроса
            
        Returns:
            str: JQL запрос
        """
        conditions = []
        
        # Проект
        if "project" in filters:
            project = filters["project"]
            if isinstance(project, list):
                project_str = ", ".join([f'"{p}"' for p in project])
                conditions.append(f"project in ({project_str})")
            else:
                conditions.append(f'project = "{project}"')
        
        # Статус
        if "status" in filters:
            status = filters["status"]
            if isinstance(status, list):
                status_str = ", ".join([f'"{s}"' for s in status])
                conditions.append(f"status in ({status_str})")
            else:
                conditions.append(f'status = "{status}"')
        
        # Assignee
        if "assignee" in filters:
            assignee = filters["assignee"]
            if assignee.lower() == "unassigned":
                conditions.append("assignee is EMPTY")
            else:
                conditions.append(f'assignee = "{assignee}"')
        
        # Даты
        if "created_after" in filters:
            conditions.append(f'created >= "{filters["created_after"]}"')
        if "created_before" in filters:
            conditions.append(f'created <= "{filters["created_before"]}"')
        if "updated_after" in filters:
            conditions.append(f'updated >= "{filters["updated_after"]}"')
        if "updated_before" in filters:
            conditions.append(f'updated <= "{filters["updated_before"]}"')
        
        # Тип задачи
        if "issue_type" in filters:
            issue_type = filters["issue_type"]
            if isinstance(issue_type, list):
                type_str = ", ".join([f'"{t}"' for t in issue_type])
                conditions.append(f"issuetype in ({type_str})")
            else:
                conditions.append(f'issuetype = "{issue_type}"')
        
        # Приоритет
        if "priority" in filters:
            priority = filters["priority"]
            if isinstance(priority, list):
                priority_str = ", ".join([f'"{p}"' for p in priority])
                conditions.append(f"priority in ({priority_str})")
            else:
                conditions.append(f'priority = "{priority}"')
        
        # Резолюция
        if "resolution" in filters:
            resolution = filters["resolution"]
            if resolution.lower() == "unresolved":
                conditions.append("resolution is EMPTY")
            else:
                conditions.append(f'resolution = "{resolution}"')
        
        # Собираем запрос
        jql = " AND ".join(conditions) if conditions else "project is not EMPTY"
        
        # Сортировка
        if "order_by" in filters:
            order_by = filters["order_by"]
            direction = filters.get("order_direction", "ASC")
            jql += f" ORDER BY {order_by} {direction}"
        else:
            jql += " ORDER BY created DESC"
        
        return jql
    
    async def aggregate_worklogs_by_user(self, jql: str, username: str,
                                       password: Optional[str] = None, 
                                       token: Optional[str] = None) -> Dict[str, int]:
        """
        Агрегирует worklogs по пользователям для задач из JQL запроса
        
        Args:
            jql: JQL запрос для фильтрации задач
            username: Имя пользователя для авторизации
            password: Пароль (опционально)
            token: API токен (опционально)
            
        Returns:
            Dict[str, int]: Пользователь -> общее время в секундах
        """
        try:
            # Получаем задачи
            search_result = await self.search_issues(
                jql=jql, 
                username=username, 
                password=password, 
                token=token,
                max_results=1000  # Увеличиваем лимит для агрегации
            )
            
            user_time = {}
            
            # Для каждой задачи получаем worklogs
            for issue in search_result.issues:
                try:
                    worklogs = await self.get_worklogs(
                        issue_key=issue.key,
                        username=username,
                        password=password,
                        token=token
                    )
                    
                    # Агрегируем по пользователям
                    for worklog in worklogs:
                        if worklog.author not in user_time:
                            user_time[worklog.author] = 0
                        user_time[worklog.author] += worklog.time_spent_seconds
                        
                except Exception as e:
                    logger.warning(f"Ошибка получения worklogs для {issue.key}: {e}")
                    continue
            
            return user_time
            
        except Exception as e:
            logger.error(f"Ошибка агрегации worklogs: {e}")
            raise JiraAPIError(f"Ошибка агрегации worklogs: {e}")

    # === Методы для получения справочников Jira ===
    
    async def get_statuses(self, username: str, password: Optional[str] = None, 
                          token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получает все доступные статусы из Jira"""
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            url = urljoin(self.base_url, "/rest/api/2/status")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    statuses = await response.json()
                    return [
                        {
                            "id": status.get("id"),
                            "name": status.get("name"),
                            "description": status.get("description", ""),
                            "category": status.get("statusCategory", {}).get("name", "")
                        }
                        for status in statuses
                    ]
                else:
                    error_text = await response.text()
                    raise JiraAPIError(f"Ошибка получения статусов ({response.status}): {error_text}")
                    
        except (JiraAPIError, JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении статусов: {e}")
            raise JiraAPIError(f"Неожиданная ошибка: {e}")
    
    async def get_issue_types(self, username: str, password: Optional[str] = None, 
                             token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получает все типы задач из Jira"""
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            url = urljoin(self.base_url, "/rest/api/2/issuetype")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    issue_types = await response.json()
                    return [
                        {
                            "id": issue_type.get("id"),
                            "name": issue_type.get("name"),
                            "description": issue_type.get("description", ""),
                            "subtask": issue_type.get("subtask", False)
                        }
                        for issue_type in issue_types
                    ]
                else:
                    error_text = await response.text()
                    raise JiraAPIError(f"Ошибка получения типов задач ({response.status}): {error_text}")
                    
        except (JiraAPIError, JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении типов задач: {e}")
            raise JiraAPIError(f"Неожиданная ошибка: {e}")
    
    async def get_priorities(self, username: str, password: Optional[str] = None, 
                            token: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получает все приоритеты из Jira"""
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_token_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            url = urljoin(self.base_url, "/rest/api/2/priority")
            
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    priorities = await response.json()
                    return [
                        {
                            "id": priority.get("id"),
                            "name": priority.get("name"),
                            "description": priority.get("description", "")
                        }
                        for priority in priorities
                    ]
                else:
                    error_text = await response.text()
                    raise JiraAPIError(f"Ошибка получения приоритетов ({response.status}): {error_text}")
                    
        except (JiraAPIError, JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Неожиданная ошибка при получении приоритетов: {e}")
            raise JiraAPIError(f"Неожиданная ошибка: {e}")

    async def get_users(self, username: str, password: Optional[str] = None,
                       token: Optional[str] = None, max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        Получает список всех пользователей из Jira
        
        Args:
            username: Имя пользователя для авторизации
            password: Пароль (опционально)
            token: API токен (опционально)
            max_results: Максимальное количество результатов
            
        Returns:
            Список пользователей
        """
        try:
            headers = {"Content-Type": "application/json"}
            
            if token:
                headers.update(self._get_auth_header(username, token))
            elif password:
                headers.update(self._get_auth_header(username, password))
            else:
                raise JiraAuthError("Не указан пароль или токен")
            
            # Используем поиск с пустым запросом для получения всех пользователей
            url = urljoin(self.base_url, "/rest/api/2/user/search")
            params = {
                "username": ".",  # Ищем всех пользователей с точкой в имени (обычно все)
                "maxResults": max_results
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    users = await response.json()
                    logger.info(f"Получено пользователей: {len(users)}")
                    return users
                elif response.status == 401:
                    raise JiraAuthError("Неавторизованный доступ к Jira")
                else:
                    error_text = await response.text()
                    logger.warning(f"Не удалось получить список пользователей: {response.status} - {error_text}")
                    return []
                    
        except (JiraAuthError):
            raise
        except Exception as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            raise JiraAPIError(f"Ошибка получения пользователей: {e}")

    async def get_all_dictionaries(self, username: str, password: Optional[str] = None, 
                                  token: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Получает все справочники Jira одним запросом"""
        try:
            dictionaries = {}
            
            # Получаем все справочники параллельно
            import asyncio
            results = await asyncio.gather(
                self.get_projects(username, password, token),
                self.get_statuses(username, password, token),
                self.get_issue_types(username, password, token),
                self.get_priorities(username, password, token),
                self.get_users(username, password, token),
                return_exceptions=True
            )
            
            # Обрабатываем результаты
            dict_names = ["projects", "statuses", "issue_types", "priorities", "users"]
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Ошибка получения {dict_names[i]}: {result}")
                    dictionaries[dict_names[i]] = []
                else:
                    dictionaries[dict_names[i]] = result
            
            logger.info(f"Получены справочники: {', '.join([f'{k}({len(v)})' for k, v in dictionaries.items()])}")
            return dictionaries
            
        except Exception as e:
            logger.error(f"Ошибка получения справочников: {e}")
            raise JiraAPIError(f"Ошибка получения справочников: {e}")


# Глобальный экземпляр сервиса
jira_service = JiraService() 