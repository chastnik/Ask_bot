"""
Конфигурация приложения Ask Bot
"""
import os
from typing import Optional
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения Ask Bot"""
    
    # Обновленная конфигурация для Pydantic 2.x
    model_config = ConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Игнорировать дополнительные поля
    )
    
    # ==============================================
    # ОСНОВНЫЕ НАСТРОЙКИ ПРИЛОЖЕНИЯ
    # ==============================================
    app_mode: str = "development"
    secret_key: str = "your-super-secret-key-change-this-immediately"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    
    # ==============================================
    # НАСТРОЙКИ MATTERMOST
    # ==============================================
    mattermost_url: str = "https://your-mattermost.example.com"
    mattermost_token: str = "your-mattermost-bot-token"
    mattermost_bot_username: str = "askbot"
    mattermost_team_id: str = "your-team-id"
    mattermost_ssl_verify: bool = False
    
    # ==============================================
    # НАСТРОЙКИ JIRA
    # ==============================================
    jira_base_url: str = "https://your-company.atlassian.net"
    jira_credentials_field: str = ""
    
    # ==============================================
    # НАСТРОЙКИ LLM (ЛОКАЛЬНАЯ МОДЕЛЬ)
    # ==============================================
    llm_proxy_url: str = "http://localhost:11434"
    llm_proxy_token: str = "your-llm-proxy-token"
    llm_model_name: str = "llama2"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3
    llm_timeout: int = 60
    
    # ==============================================
    # НАСТРОЙКИ БАЗЫ ДАННЫХ
    # ==============================================
    database_url: str = "sqlite:///./askbot.db"
    database_auto_create: bool = True
    
    # ==============================================
    # НАСТРОЙКИ REDIS (КЕШИРОВАНИЕ)
    # ==============================================
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600
    cache_max_size: int = 10000
    
    # ==============================================
    # НАСТРОЙКИ RAG СИСТЕМЫ
    # ==============================================
    rag_embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    rag_top_k: int = 5
    rag_similarity_threshold: float = 0.7
    
    # ==============================================
    # НАСТРОЙКИ ГРАФИКОВ
    # ==============================================
    charts_dir: str = "./charts"
    charts_ttl: int = 86400
    charts_format: str = "png"
    charts_dpi: int = 300
    
    # ==============================================
    # НАСТРОЙКИ БЕЗОПАСНОСТИ
    # ==============================================
    cors_origins: str = "*"
    session_ttl: int = 86400
    debug_endpoints_enabled: bool = True
    
    # ==============================================
    # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
    # ==============================================
    default_timezone: str = "Europe/Moscow"
    default_language: str = "ru"
    max_file_size: int = 10485760
    sql_echo: bool = False
    
    # ==============================================
    # ОБРАТНАЯ СОВМЕСТИМОСТЬ
    # ==============================================
    @property
    def host(self) -> str:
        """Обратная совместимость для host"""
        return self.app_host
    
    @property
    def port(self) -> int:
        """Обратная совместимость для port"""
        return self.app_port
    
    @property
    def jira_url(self) -> str:
        """Обратная совместимость для jira_url"""
        return self.jira_base_url
        
    @property
    def llm_base_url(self) -> str:
        """Обратная совместимость для llm_base_url"""
        return self.llm_proxy_url
        
    @property
    def llm_model(self) -> str:
        """Обратная совместимость для llm_model"""
        return self.llm_model_name
        
    @property
    def embedding_model(self) -> str:
        """Обратная совместимость для embedding_model"""
        return self.rag_embedding_model
        
    @property
    def chart_save_path(self) -> str:
        """Обратная совместимость для chart_save_path"""
        return self.charts_dir
        
    @property
    def bot_name(self) -> str:
        """Обратная совместимость для bot_name"""
        return self.mattermost_bot_username
        
    @property
    def chart_url_prefix(self) -> str:
        """Обратная совместимость для chart_url_prefix"""
        return f"http://{self.app_host}:{self.app_port}/charts/"
        
    @property
    def max_context_length(self) -> int:
        """Обратная совместимость для max_context_length"""
        return 4000


# Глобальный экземпляр настроек
settings = Settings() 