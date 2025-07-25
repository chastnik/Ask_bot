"""
Сервис для работы с контекстом беседы
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from app.models.database import ConversationContext as ConversationContextModel
from app.models.schemas import ConversationContext, ConversationContextCreate, ConversationContextUpdate

logger = logging.getLogger(__name__)


class ConversationService:
    """Сервис для управления контекстом беседы"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def get_or_create_context(self, user_id: str, channel_id: Optional[str] = None) -> Optional[ConversationContext]:
        """Получает или создает контекст беседы для пользователя"""
        try:
            # Попытка получить существующий контекст
            stmt = select(ConversationContextModel).where(
                ConversationContextModel.user_id == user_id,
                ConversationContextModel.channel_id == channel_id
            )
            result = await self.db.execute(stmt)
            context_model = result.scalar_one_or_none()
            
            if context_model:
                return ConversationContext.model_validate(context_model)
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения контекста беседы: {e}")
            return None
    
    async def save_context(
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
            # Получаем существующий контекст или создаем новый
            stmt = select(ConversationContextModel).where(
                ConversationContextModel.user_id == user_id,
                ConversationContextModel.channel_id == channel_id
            )
            result = await self.db.execute(stmt)
            context_model = result.scalar_one_or_none()
            
            if context_model:
                # Обновляем существующий контекст
                context_model.last_query = query
                context_model.last_intent = intent
                context_model.last_response = response
                context_model.entities = entities or {}
                context_model.updated_at = datetime.utcnow()
            else:
                # Создаем новый контекст
                context_model = ConversationContextModel(
                    user_id=user_id,
                    channel_id=channel_id,
                    last_query=query,
                    last_intent=intent,
                    last_response=response,
                    entities=entities or {},
                    clarifications=[]
                )
                self.db.add(context_model)
            
            await self.db.commit()
            logger.info(f"Контекст беседы сохранен для пользователя {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения контекста беседы: {e}")
            await self.db.rollback()
            return False
    
    async def enrich_query_with_context(
        self, 
        user_id: str, 
        current_query: str,
        channel_id: Optional[str] = None
    ) -> tuple[str, Dict[str, Any]]:
        """Обогащает текущий запрос контекстом предыдущих сообщений"""
        try:
            context = await self.get_or_create_context(user_id, channel_id)
            
            if not context or not context.last_query:
                return current_query, {}
            
            # Проверяем, является ли текущий запрос уточнением
            clarification_indicators = [
                "рулев это сотрудник", "это сотрудник", "это работник", "это пользователь",
                "а закрытые", "а открытые", "а у", "а для", "а по", "также", "еще",
                "и еще", "добавь", "включи", "исключи", "убери", "замени"
            ]
            
            is_clarification = any(indicator in current_query.lower() for indicator in clarification_indicators)
            
            enhanced_context = {}
            if is_clarification and context.entities:
                enhanced_context = context.entities.copy()
                
                # Обрабатываем специальные уточнения
                if any(phrase in current_query.lower() for phrase in ["рулев это сотрудник", "это сотрудник", "это работник"]):
                    # Переносим "клиента" в assignee
                    if "client_name" in enhanced_context:
                        enhanced_context["assignee"] = enhanced_context.pop("client_name")
                        logger.info(f"Перенесли client_name в assignee: {enhanced_context.get('assignee')}")
                
                # Обрабатываем изменения в фильтрах
                if "а закрытые" in current_query.lower():
                    enhanced_context["status"] = "closed"
                elif "а открытые" in current_query.lower():
                    enhanced_context["status"] = "open"
                
                # Обрабатываем "а у [пользователя]"
                if "а у" in current_query.lower():
                    import re
                    user_match = re.search(r'а у ([А-Яа-я\s]+)', current_query)
                    if user_match:
                        enhanced_context["assignee"] = user_match.group(1).strip()
                
                # Создаем обогащенный запрос
                enriched_query = f"{context.last_query} {current_query}"
                
                return enriched_query, enhanced_context
            
            return current_query, enhanced_context
            
        except Exception as e:
            logger.error(f"Ошибка обогащения запроса контекстом: {e}")
            return current_query, {}


async def get_conversation_service(db_session: AsyncSession) -> ConversationService:
    """Фабрика для создания сервиса контекста беседы"""
    return ConversationService(db_session)
