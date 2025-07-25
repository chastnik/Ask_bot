"""
Сервис для интеграции с Mattermost API
"""
import aiohttp
import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin
from loguru import logger

from app.config import settings
from app.models.schemas import (
    MattermostUser, MattermostChannel, MattermostPost,
    SlashCommandRequest, SlashCommandResponse
)


class MattermostAPIError(Exception):
    """Исключение для ошибок Mattermost API"""
    pass


class MattermostService:
    """Сервис для работы с Mattermost API"""
    
    def __init__(self):
        self.base_url = settings.mattermost_url
        self.token = settings.mattermost_token
        self.bot_name = settings.bot_name
        self.team_id = settings.mattermost_team_id
        self.ssl_verify = settings.mattermost_ssl_verify
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(ssl=self.ssl_verify)
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=connector,
            headers={"Authorization": f"Bearer {self.token}"}
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
        Тестирует подключение к Mattermost
        
        Returns:
            bool: True если соединение успешно
        """
        try:
            url = urljoin(self.base_url, "/api/v4/users/me")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    user_data = await response.json()
                    logger.info(f"Успешное подключение к Mattermost. Бот: {user_data.get('username')}")
                    return True
                else:
                    logger.error(f"Ошибка подключения к Mattermost: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"Ошибка при тестировании подключения к Mattermost: {e}")
            return False
    
    async def get_user_by_id(self, user_id: str) -> Optional[MattermostUser]:
        """
        Получает информацию о пользователе по ID
        
        Args:
            user_id: ID пользователя
            
        Returns:
            MattermostUser или None
        """
        try:
            url = urljoin(self.base_url, f"/api/v4/users/{user_id}")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    user_data = await response.json()
                    return MattermostUser(**user_data)
                elif response.status == 404:
                    logger.warning(f"Пользователь {user_id} не найден")
                    return None
                else:
                    logger.error(f"Ошибка получения пользователя {user_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя {user_id}: {e}")
            return None
    
    async def get_user_by_username(self, username: str) -> Optional[MattermostUser]:
        """
        Получает информацию о пользователе по username
        
        Args:
            username: Имя пользователя
            
        Returns:
            MattermostUser или None
        """
        try:
            url = urljoin(self.base_url, f"/api/v4/users/username/{username}")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    user_data = await response.json()
                    return MattermostUser(**user_data)
                elif response.status == 404:
                    logger.warning(f"Пользователь {username} не найден")
                    return None
                else:
                    logger.error(f"Ошибка получения пользователя {username}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя {username}: {e}")
            return None
    
    async def get_channel_by_id(self, channel_id: str) -> Optional[MattermostChannel]:
        """
        Получает информацию о канале по ID
        
        Args:
            channel_id: ID канала
            
        Returns:
            MattermostChannel или None
        """
        try:
            url = urljoin(self.base_url, f"/api/v4/channels/{channel_id}")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    channel_data = await response.json()
                    return MattermostChannel(**channel_data)
                elif response.status == 404:
                    logger.warning(f"Канал {channel_id} не найден")
                    return None
                else:
                    logger.error(f"Ошибка получения канала {channel_id}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении канала {channel_id}: {e}")
            return None
    
    async def create_post(self, channel_id: str, message: str, 
                         props: Optional[Dict[str, Any]] = None,
                         file_ids: Optional[List[str]] = None) -> Optional[str]:
        """
        Создает пост в канале
        
        Args:
            channel_id: ID канала
            message: Текст сообщения
            props: Дополнительные свойства поста
            file_ids: ID прикрепленных файлов
            
        Returns:
            ID созданного поста или None при ошибке
        """
        try:
            url = urljoin(self.base_url, "/api/v4/posts")
            
            payload = {
                "channel_id": channel_id,
                "message": message
            }
            
            if props:
                payload["props"] = props
                
            if file_ids:
                payload["file_ids"] = file_ids
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 201:
                    post_data = await response.json()
                    logger.info(f"Пост создан в канале {channel_id}: {post_data.get('id')}")
                    return post_data.get("id")
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка создания поста ({response.status}): {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при создании поста: {e}")
            return None
    
    async def create_dm_channel(self, user_id: str) -> Optional[str]:
        """
        Создает канал прямых сообщений с пользователем
        
        Args:
            user_id: ID пользователя
            
        Returns:
            ID канала DM или None при ошибке
        """
        try:
            # Получаем ID бота
            bot_user = await self.get_me()
            if not bot_user:
                logger.error("Не удалось получить информацию о боте")
                return None
            
            url = urljoin(self.base_url, "/api/v4/channels/direct")
            payload = [bot_user["id"], user_id]
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 201 or response.status == 200:
                    channel_data = await response.json()
                    return channel_data.get("id")
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка создания DM канала ({response.status}): {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при создании DM канала: {e}")
            return None
    
    async def send_dm(self, user_id: str, message: str, 
                     props: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Отправляет прямое сообщение пользователю
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
            props: Дополнительные свойства
            
        Returns:
            ID поста или None при ошибке
        """
        try:
            # Создаем или получаем DM канал
            dm_channel_id = await self.create_dm_channel(user_id)
            if not dm_channel_id:
                return None
            
            # Отправляем сообщение
            return await self.create_post(dm_channel_id, message, props)
            
        except Exception as e:
            logger.error(f"Ошибка при отправке DM: {e}")
            return None
    
    async def get_me(self) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о текущем пользователе (боте)
        
        Returns:
            Dict с информацией о пользователе или None
        """
        try:
            url = urljoin(self.base_url, "/api/v4/users/me")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Ошибка получения информации о боте: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении информации о боте: {e}")
            return None
    
    async def upload_file(self, channel_id: str, file_data: bytes, 
                         filename: str, content_type: str = "image/png") -> Optional[str]:
        """
        Загружает файл на сервер Mattermost
        
        Args:
            channel_id: ID канала
            file_data: Данные файла
            filename: Имя файла
            content_type: MIME тип файла
            
        Returns:
            ID загруженного файла или None при ошибке
        """
        try:
            url = urljoin(self.base_url, "/api/v4/files")
            
            form_data = aiohttp.FormData()
            form_data.add_field('channel_id', channel_id)
            form_data.add_field('files', file_data, 
                              filename=filename, 
                              content_type=content_type)
            
            headers = {"Authorization": f"Bearer {self.token}"}  # Без Content-Type для FormData
            
            async with self.session.post(url, data=form_data, headers=headers) as response:
                if response.status == 201:
                    files_data = await response.json()
                    if files_data.get("file_infos"):
                        file_id = files_data["file_infos"][0]["id"]
                        logger.info(f"Файл {filename} загружен: {file_id}")
                        return file_id
                    else:
                        logger.error("Не получен ID загруженного файла")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка загрузки файла ({response.status}): {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {e}")
            return None
    
    async def create_post_with_file(self, channel_id: str, message: str,
                                  file_data: bytes, filename: str,
                                  content_type: str = "image/png") -> Optional[str]:
        """
        Создает пост с прикрепленным файлом
        
        Args:
            channel_id: ID канала
            message: Текст сообщения
            file_data: Данные файла
            filename: Имя файла
            content_type: MIME тип файла
            
        Returns:
            ID созданного поста или None при ошибке
        """
        try:
            # Загружаем файл
            file_id = await self.upload_file(channel_id, file_data, filename, content_type)
            if not file_id:
                return None
            
            # Создаем пост с файлом
            return await self.create_post(channel_id, message, file_ids=[file_id])
            
        except Exception as e:
            logger.error(f"Ошибка при создании поста с файлом: {e}")
            return None
    
    def create_slash_command_response(self, text: str, response_type: str = "ephemeral",
                                    attachments: Optional[List[Dict]] = None) -> SlashCommandResponse:
        """
        Создает ответ на slash команду
        
        Args:
            text: Текст ответа
            response_type: Тип ответа (ephemeral или in_channel)
            attachments: Список вложений
            
        Returns:
            SlashCommandResponse: Объект ответа
        """
        return SlashCommandResponse(
            text=text,
            response_type=response_type,
            username=self.bot_name,
            attachments=attachments or []
        )
    
    def create_error_response(self, error_message: str) -> SlashCommandResponse:
        """
        Создает ответ об ошибке
        
        Args:
            error_message: Сообщение об ошибке
            
        Returns:
            SlashCommandResponse: Объект ответа с ошибкой
        """
        return self.create_slash_command_response(
            text=f"❌ **Ошибка:** {error_message}",
            response_type="ephemeral"
        )
    
    def create_info_response(self, info_message: str, 
                           response_type: str = "ephemeral") -> SlashCommandResponse:
        """
        Создает информационный ответ
        
        Args:
            info_message: Информационное сообщение
            response_type: Тип ответа
            
        Returns:
            SlashCommandResponse: Объект ответа
        """
        return self.create_slash_command_response(
            text=f"ℹ️ {info_message}",
            response_type=response_type
        )
    
    def create_data_response(self, title: str, data: List[Dict[str, Any]], 
                           chart_url: Optional[str] = None) -> SlashCommandResponse:
        """
        Создает ответ с данными и опциональным графиком
        
        Args:
            title: Заголовок ответа
            data: Данные для отображения
            chart_url: URL графика (опционально)
            
        Returns:
            SlashCommandResponse: Объект ответа с данными
        """
        # Формируем текст с данными
        text_lines = [f"📊 **{title}**", ""]
        
        if len(data) <= 10:  # Показываем данные в тексте, если их немного
            for item in data:
                line_parts = []
                for key, value in item.items():
                    if key != "id":  # Скрываем ID
                        line_parts.append(f"**{key}:** {value}")
                text_lines.append("• " + " | ".join(line_parts))
        else:
            text_lines.append(f"Найдено записей: **{len(data)}**")
            text_lines.append("_Данные слишком объемные для отображения в чате._")
        
        if chart_url:
            text_lines.extend(["", f"📈 [Открыть график]({chart_url})"])
        
        return self.create_slash_command_response(
            text="\n".join(text_lines),
            response_type="in_channel"
        )
    
    async def send_typing_indicator(self, channel_id: str, parent_id: str = "") -> bool:
        """
        Отправляет индикатор печати
        
        Args:
            channel_id: ID канала
            parent_id: ID родительского поста (для тредов)
            
        Returns:
            bool: True при успехе
        """
        try:
            url = urljoin(self.base_url, f"/api/v4/users/me/typing")
            payload = {"channel_id": channel_id}
            
            if parent_id:
                payload["parent_id"] = parent_id
            
            async with self.session.post(url, json=payload) as response:
                return response.status == 200
                
        except Exception as e:
            logger.debug(f"Ошибка при отправке индикатора печати: {e}")
            return False
    
    async def get_team_by_name(self, team_name: str) -> Optional[Dict[str, Any]]:
        """
        Получает команду по имени
        
        Args:
            team_name: Имя команды
            
        Returns:
            Dict с информацией о команде или None
        """
        try:
            url = urljoin(self.base_url, f"/api/v4/teams/name/{team_name}")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logger.warning(f"Команда {team_name} не найдена")
                    return None
                else:
                    logger.error(f"Ошибка получения команды {team_name}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Ошибка при получении команды {team_name}: {e}")
            return None
    
    async def get_channels_for_team(self, team_id: str) -> List[MattermostChannel]:
        """
        Получает список каналов команды
        
        Args:
            team_id: ID команды
            
        Returns:
            List[MattermostChannel]: Список каналов
        """
        try:
            url = urljoin(self.base_url, f"/api/v4/teams/{team_id}/channels")
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    channels_data = await response.json()
                    return [MattermostChannel(**ch) for ch in channels_data]
                else:
                    logger.error(f"Ошибка получения каналов команды {team_id}: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Ошибка при получении каналов команды {team_id}: {e}")
            return []

    async def send_direct_message(self, user_id: str, message: str) -> bool:
        """
        Отправляет личное сообщение пользователю
        
        Args:
            user_id: ID пользователя в Mattermost
            message: Текст сообщения
            
        Returns:
            True если сообщение отправлено успешно, False - иначе
        """
        try:
            # Сначала создаем или получаем канал для личных сообщений
            dm_channel = await self.create_direct_message_channel(user_id)
            
            if not dm_channel:
                logger.error(f"Не удалось создать канал личных сообщений с пользователем {user_id}")
                return False
            
            channel_id = dm_channel.get("id")
            
            # Отправляем сообщение в канал
            url = f"{self.base_url}/api/v4/posts"
            
            payload = {
                "channel_id": channel_id,
                "message": message
            }
            
            async with self.session.post(
                url,
                json=payload
            ) as response:
                
                if response.status == 201:
                    logger.info(f"Личное сообщение отправлено пользователю {user_id}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка отправки личного сообщения: {response.status} - {error_text}")
                    return False
                        
        except Exception as e:
            logger.error(f"Ошибка при отправке личного сообщения пользователю {user_id}: {e}")
            return False

    async def create_direct_message_channel(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Создает или получает канал для личных сообщений с пользователем
        
        Args:
            user_id: ID пользователя в Mattermost
            
        Returns:
            Информация о канале личных сообщений или None при ошибке
        """
        try:
            url = f"{self.base_url}/api/v4/channels/direct"
            
            # Получаем ID текущего бота (нам нужно знать свой ID)
            bot_user = await self.get_me()
            if not bot_user:
                logger.error("Не удалось получить информацию о текущем пользователе (боте)")
                return None
            
            bot_user_id = bot_user.get("id")
            
            payload = [bot_user_id, user_id]
            
            async with self.session.post(
                url,
                json=payload
            ) as response:
                
                if response.status in [200, 201]:
                    channel_data = await response.json()
                    logger.info(f"Канал личных сообщений создан/получен для пользователя {user_id}")
                    return channel_data
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка создания канала личных сообщений: {response.status} - {error_text}")
                    return None
                        
        except Exception as e:
            logger.error(f"Ошибка при создании канала личных сообщений с пользователем {user_id}: {e}")
            return None

    async def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о текущем пользователе (боте)
        
        Returns:
            Информация о текущем пользователе или None при ошибке
        """
        try:
            url = f"{self.base_url}/api/v4/users/me"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    user_data = await response.json()
                    return user_data
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка получения информации о текущем пользователе: {response.status} - {error_text}")
                    return None
                        
        except Exception as e:
            logger.error(f"Ошибка при получении информации о текущем пользователе: {e}")
            return None


# Глобальный экземпляр сервиса
mattermost_service = MattermostService() 