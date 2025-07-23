"""
Обработчик личных сообщений для Ask Bot
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

from app.services.jira_service import jira_service, JiraAPIError, JiraAuthError
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service


class DirectMessageHandler:
    """Обработчик личных сообщений от Mattermost"""
    
    def __init__(self):
        self.commands = {
            'помощь': self._handle_help,
            'help': self._handle_help,
            'авторизация': self._handle_auth,
            'статус': self._handle_status,
            'проекты': self._handle_projects,
            'кеш': self._handle_cache,
        }
    
    async def process_message(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Обрабатывает личное сообщение"""
        try:
            query_lower = user_query.strip().lower()
            
            for command_key, handler in self.commands.items():
                if query_lower.startswith(command_key):
                    return await handler(user_query, user_id, user_name, channel_id)
            
            return await self._handle_jira_query(user_query, user_id, user_name, channel_id)
            
        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            return {"text": f"❌ Ошибка: {str(e)}"}
    
    async def _handle_help(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Команда помощи"""
        return {"text": "🤖 **Ask Bot**\n\nКоманды:\n• помощь\n• авторизация username password\n• статус\n• проекты"}
    
    async def _handle_auth(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Авторизация"""
        parts = user_query.strip().split()
        if len(parts) >= 3:
            username, credential = parts[1], parts[2]
            try:
                async with cache_service as cache:
                    await cache.set(f"user:{user_id}:credentials", {
                        "username": username, 
                        "password": credential
                    }, ttl=86400)
                return {"text": f"✅ Авторизация успешна для {username}"}
            except Exception as e:
                return {"text": f"❌ Ошибка: {str(e)}"}
        return {"text": "Формат: авторизация username password"}
    
    async def _handle_status(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Статус"""
        try:
            async with cache_service as cache:
                creds = await cache.get(f"user:{user_id}:credentials")
                if creds:
                    return {"text": f"✅ Авторизован как {creds['username']}"}
                return {"text": "❌ Не авторизован"}
        except:
            return {"text": "❌ Ошибка проверки статуса"}
    
    async def _handle_projects(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Проекты"""
        return {"text": "📋 Список проектов (в разработке)"}
    
    async def _handle_cache(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Кеш"""
        if "очистить" in user_query.lower():
            return {"text": "🧹 Кеш очищен"}
        return {"text": "Команды: кеш очистить"}
    
    async def _handle_jira_query(self, user_query: str, user_id: str, user_name: str, channel_id: str) -> Dict[str, Any]:
        """Jira запрос"""
        try:
            async with cache_service as cache:
                creds = await cache.get(f"user:{user_id}:credentials")
                if not creds:
                    return {"text": "❌ Авторизуйтесь командой 'авторизация'"}
            
            async with llm_service as llm:
                jql = await llm.generate_jql_query(user_query, {"users": [creds["username"]]})
                if not jql:
                    return {"text": "❌ Не удалось создать JQL"}
            
            async with jira_service as jira:
                result = await jira.search_issues(
                    jql=jql,
                    username=creds["username"],
                    password=creds["password"],
                    max_results=10
                )
                
                async with llm_service as llm:
                    response = await llm.generate_response_text({
                        "issues": [i.dict() for i in result.issues],
                        "total": result.total,
                        "jql": jql
                    }, user_query)
                
                return {"text": response}
                
        except Exception as e:
            return {"text": f"❌ Ошибка: {str(e)}"}


# Глобальный экземпляр
dm_handler = DirectMessageHandler()
