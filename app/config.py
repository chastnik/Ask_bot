"""
Конфигурация приложения
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Mattermost настройки
    mattermost_url: str = "https://mm.1bit.support"
    mattermost_token: str = "n13z7yah1tds3p8i9ohog1baoy"
    bot_name: str = "ask_bot"
    mattermost_team_id: str = "j5xmb3iie3n6txowdfu8adn3ma"
    mattermost_ssl_verify: bool = False
    
    # Jira настройки
    jira_url: str = "https://jira.1solution.ru"
    
    # LLM настройки
    llm_proxy_token: str = "8d10b6d4-2e40-42fc-a66a-c9c6bf20c92c"
    llm_base_url: str = "https://llm.1bitai.ru"
    llm_model: str = "qwen3:14b"
    
    # База данных
    database_url: str = "sqlite:///./askbot.db"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Общие настройки
    log_level: str = "INFO"
    secret_key: str = "your-secret-key-here"
    debug: bool = False
    
    # Настройки приложения
    host: str = "0.0.0.0"
    port: int = 8000
    
    # RAG настройки
    embedding_model: str = "all-MiniLM-L6-v2"
    max_context_length: int = 4000
    
    # График настройки
    chart_save_path: str = "./charts/"
    chart_url_prefix: str = "http://localhost:8000/charts/"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Глобальный экземпляр настроек
settings = Settings() 