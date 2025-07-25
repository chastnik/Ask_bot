"""
WebSocket клиент для подключения к Mattermost
"""
import asyncio
import json
import websockets
from typing import Dict, Any, Optional, Callable
from urllib.parse import urljoin, urlparse
from loguru import logger

from app.config import settings


class MattermostWebSocketClient:
    """WebSocket клиент для Mattermost"""
    
    def __init__(self):
        self.base_url = settings.mattermost_url
        self.token = settings.mattermost_token
        self.bot_username = settings.mattermost_bot_username
        self.ws = None
        self.user_id = None
        self.is_connected = False
        self.message_handler: Optional[Callable] = None
        
    def set_message_handler(self, handler: Callable[[Dict[str, Any]], None]):
        """Устанавливает обработчик сообщений"""
        self.message_handler = handler
    
    async def connect(self):
        """Подключается к Mattermost WebSocket API"""
        try:
            # Получаем WebSocket URL
            ws_url = self._get_websocket_url()
            
            logger.info(f"🔌 Подключение к Mattermost WebSocket: {ws_url}")
            
            # Подключаемся
            self.ws = await websockets.connect(
                ws_url,
                additional_headers={"Authorization": f"Bearer {self.token}"},
                ping_interval=30,
                ping_timeout=10
            )
            
            self.is_connected = True
            logger.info("✅ WebSocket подключение установлено")
            
            # Отправляем аутентификацию
            await self._authenticate()
            
            # Запускаем слушатель сообщений
            await self._listen_messages()
            
        except Exception as e:
            logger.error(f"❌ Ошибка WebSocket подключения: {e}")
            self.is_connected = False
            raise
    
    async def disconnect(self):
        """Отключается от WebSocket"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("🔌 WebSocket подключение закрыто")
    
    def _get_websocket_url(self) -> str:
        """Формирует WebSocket URL"""
        parsed = urlparse(self.base_url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        return f"{ws_scheme}://{parsed.netloc}/api/v4/websocket"
    
    async def _authenticate(self):
        """Отправляет аутентификацию"""
        auth_message = {
            "seq": 1,
            "action": "authentication_challenge",
            "data": {
                "token": self.token
            }
        }
        
        await self.ws.send(json.dumps(auth_message))
        logger.debug("🔐 Отправлен запрос аутентификации")
    
    async def _listen_messages(self):
        """Слушает входящие сообщения"""
        try:
            async for message in self.ws:
                await self._handle_websocket_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket соединение закрыто")
            self.is_connected = False
        except Exception as e:
            logger.error(f"❌ Ошибка при получении сообщения: {e}")
            self.is_connected = False
    
    async def _handle_websocket_message(self, message: str):
        """Обрабатывает входящее WebSocket сообщение"""
        try:
            data = json.loads(message)
            
            # Обрабатываем различные типы событий
            event_type = data.get("event", "")
            
            if event_type == "hello":
                # Приветствие от сервера
                logger.info("👋 Получено приветствие от Mattermost")
                # Получаем ID бота
                await self._get_bot_user_id()
                
            elif event_type == "posted":
                # Новое сообщение
                logger.info(f"📨 Получено событие posted: {data}")
                await self._handle_posted_event(data)
                
            elif event_type == "status_change":
                # Изменение статуса пользователя
                logger.debug(f"📊 Статус пользователя изменен: {data}")
                
            else:
                logger.info(f"📨 Получено событие: {event_type}")
                
        except json.JSONDecodeError:
            logger.error("❌ Ошибка парсинга JSON сообщения")
        except Exception as e:
            logger.error(f"❌ Ошибка обработки WebSocket сообщения: {e}")
    
    async def _handle_posted_event(self, data: Dict[str, Any]):
        """Обрабатывает событие нового сообщения"""
        try:
            logger.info(f"🔍 Обработка posted события: {data}")
            event_data = data.get("data", {})
            post_data = event_data.get("post")
            
            if not post_data:
                logger.warning("⚠️ Нет данных поста в posted событии")
                return
            
            # Парсим данные поста
            if isinstance(post_data, str):
                post_data = json.loads(post_data)
            
            message = post_data.get("message", "").strip()
            user_id = post_data.get("user_id", "")
            channel_id = post_data.get("channel_id", "")
            # channel_type берем из event_data, а не из post_data!
            channel_type = event_data.get("channel_type", "")
            
            logger.info(f"📝 Пост: user_id={user_id}, channel_type={channel_type}, message='{message}'")
            logger.info(f"🤖 ID бота: {self.user_id}")
            
            # Игнорируем сообщения от самого бота
            if user_id == self.user_id:
                logger.info("🚫 Игнорируем сообщение от самого бота")
                return
            
            # Обрабатываем только личные сообщения (канал типа D)
            if channel_type == "D" and message:
                logger.info(f"💬 Получено личное сообщение от {user_id}: {message}")
                
                # Передаем обработчику сообщений
                if self.message_handler:
                    message_info = {
                        "user_id": user_id,
                        "channel_id": channel_id,
                        "message": message,
                        "post_id": post_data.get("id", "")
                    }
                    
                    await self.message_handler(message_info)
                    
        except Exception as e:
            logger.error(f"❌ Ошибка обработки posted события: {e}")
    
    async def _get_bot_user_id(self):
        """Получает ID бота через API"""
        try:
            from app.services.mattermost_service import mattermost_service
            async with mattermost_service as mm:
                bot_user = await mm.get_me()
                if bot_user:
                    self.user_id = bot_user.get("id")
                    logger.info(f"🆔 ID бота установлен: {self.user_id}")
                else:
                    logger.error("❌ Не удалось получить ID бота")
        except Exception as e:
            logger.error(f"❌ Ошибка получения ID бота: {e}")


# Глобальный экземпляр клиента
websocket_client = MattermostWebSocketClient()