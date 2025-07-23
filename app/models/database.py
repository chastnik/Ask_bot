"""
Модели базы данных для RAG системы и кеширования
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, 
    JSON, Float, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    """Модель пользователя Mattermost"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)  # Mattermost user ID
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=True)
    display_name = Column(String, nullable=True)
    
    # Jira credentials (зашифрованы)
    jira_username = Column(String, nullable=True)
    jira_password_hash = Column(String, nullable=True)  # Зашифрованный пароль
    jira_token = Column(String, nullable=True)  # API token
    
    # Настройки пользователя
    preferred_language = Column(String, default="ru")
    timezone = Column(String, default="UTC")
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи
    conversations = relationship("Conversation", back_populates="user")
    queries = relationship("QueryHistory", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username={self.username})>"


class Client(Base):
    """Модель клиента из Jira"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    jira_key = Column(String, nullable=True)  # Ключ проекта в Jira
    description = Column(Text, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи
    projects = relationship("Project", back_populates="client")
    
    def __repr__(self):
        return f"<Client(id={self.id}, name={self.name})>"


class Project(Base):
    """Модель проекта"""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    jira_key = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Связи
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    client = relationship("Client", back_populates="projects")
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, key={self.jira_key})>"


class QueryTemplate(Base):
    """Шаблоны запросов для RAG"""
    __tablename__ = "query_templates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    template = Column(Text, nullable=False)  # JQL шаблон
    category = Column(String, nullable=False)  # analytics, reporting, status, etc.
    
    # Параметры шаблона
    parameters = Column(JSON, nullable=True)  # Список параметров
    examples = Column(JSON, nullable=True)  # Примеры использования
    
    # Настройки визуализации
    chart_type = Column(String, nullable=True)  # bar, line, pie, table
    chart_config = Column(JSON, nullable=True)  # Конфигурация графика
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    usage_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<QueryTemplate(id={self.id}, name={self.name}, category={self.category})>"


class QueryHistory(Base):
    """История запросов пользователей"""
    __tablename__ = "query_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Данные запроса
    original_query = Column(Text, nullable=False)  # Оригинальный вопрос
    processed_query = Column(Text, nullable=True)  # Обработанный запрос
    jql_query = Column(Text, nullable=True)  # Сгенерированный JQL
    
    # Результаты
    result_count = Column(Integer, nullable=True)
    execution_time = Column(Float, nullable=True)  # Время выполнения в секундах
    
    # Метаданные
    query_type = Column(String, nullable=True)  # analytics, search, status
    template_id = Column(Integer, ForeignKey("query_templates.id"), nullable=True)
    
    # Кеширование
    cache_key = Column(String, nullable=True)
    cached = Column(Boolean, default=False)
    
    # Связи
    user = relationship("User", back_populates="queries")
    template = relationship("QueryTemplate")
    
    # Временные метки
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<QueryHistory(id={self.id}, user_id={self.user_id})>"


class Conversation(Base):
    """Контекст разговора для сохранения истории"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    channel_id = Column(String, nullable=False)  # Mattermost channel ID
    
    # Контекст разговора
    context = Column(JSON, nullable=True)  # Сохранённый контекст
    last_query = Column(Text, nullable=True)
    last_result = Column(JSON, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Связи
    user = relationship("User", back_populates="conversations")
    
    # Индексы
    __table_args__ = (
        Index('idx_conversation_user_channel', 'user_id', 'channel_id'),
        UniqueConstraint('user_id', 'channel_id', name='uq_user_channel'),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, user_id={self.user_id}, channel_id={self.channel_id})>"


class CacheEntry(Base):
    """Кеш для частых запросов"""
    __tablename__ = "cache_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String, unique=True, nullable=False)
    data = Column(JSON, nullable=False)
    
    # TTL и метаданные
    ttl_seconds = Column(Integer, default=3600)  # TTL в секундах
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, server_default=func.now())
    
    # Индексы
    __table_args__ = (
        Index('idx_cache_key', 'cache_key'),
        Index('idx_cache_expires', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<CacheEntry(cache_key={self.cache_key})>"


class KnowledgeBase(Base):
    """База знаний для RAG системы"""
    __tablename__ = "knowledge_base"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String, nullable=False)  # jql, faq, guide
    
    # Векторные эмбеддинги
    embedding = Column(JSON, nullable=True)  # Векторное представление
    
    # Категоризация
    category = Column(String, nullable=True)
    tags = Column(JSON, nullable=True)  # Список тегов
    
    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Индексы
    __table_args__ = (
        Index('idx_kb_category', 'category'),
        Index('idx_kb_content_type', 'content_type'),
    )
    
    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, title={self.title[:50]}...)>" 