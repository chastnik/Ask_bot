"""
Конфигурация приложения Ask Bot

Этот файл содержит только структуру настроек и безопасные значения по умолчанию.
Реальные настройки должны быть в .env файле!
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
    secret_key: str = "change-this-secret-key-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    
    # ==============================================
    # НАСТРОЙКИ MATTERMOST
    # Реальные значения должны быть в .env файле!
    # ==============================================
    mattermost_url: str = ""  # Обязательно: URL вашего Mattermost
    mattermost_token: str = ""  # Обязательно: Токен бота
    mattermost_bot_username: str = "askbot"
    mattermost_team_id: str = ""  # Обязательно: ID команды
    mattermost_ssl_verify: bool = True  # Для безопасности по умолчанию True
    
    # ==============================================
    # НАСТРОЙКИ JIRA  
    # Реальные значения должны быть в .env файле!
    # ==============================================
    jira_base_url: str = ""  # Обязательно: URL вашего Jira
    jira_credentials_field: str = ""
    
    # ==============================================
    # НАСТРОЙКИ LLM (ЛОКАЛЬНАЯ МОДЕЛЬ)
    # ==============================================
    llm_proxy_url: str = "http://localhost:11434"  # Ollama по умолчанию
    llm_proxy_token: str = ""  # Опционально
    llm_model_name: str = "llama2"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.3
    llm_timeout: int = 60
    
    # ==============================================
    # НАСТРОЙКИ БАЗЫ ДАННЫХ
    # ==============================================
    database_url: str = "sqlite:///./askbot.db"  # По умолчанию SQLite
    database_auto_create: bool = True
    
    # ==============================================
    # НАСТРОЙКИ REDIS (КЕШИРОВАНИЕ)
    # ==============================================
    redis_url: str = "redis://localhost:6379/0"  # Локальный Redis по умолчанию
    cache_ttl: int = 3600  # 1 час
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
    charts_ttl: int = 86400  # 24 часа
    charts_format: str = "png"
    charts_dpi: int = 300
    
    # ==============================================
    # НАСТРОЙКИ БЕЗОПАСНОСТИ
    # ==============================================
    cors_origins: str = "*"  # В продакшене нужно ограничить!
    session_ttl: int = 86400  # 24 часа
    debug_endpoints_enabled: bool = True  # В продакшене False!
    
    # ==============================================
    # ДОПОЛНИТЕЛЬНЫЕ НАСТРОЙКИ
    # ==============================================
    default_timezone: str = "Europe/Moscow"
    default_language: str = "ru"
    max_file_size: int = 10485760  # 10MB
    sql_echo: bool = False  # True для отладки SQL
    
    # ==============================================
    # ВАЛИДАЦИЯ ОБЯЗАТЕЛЬНЫХ НАСТРОЕК
    # ==============================================
    def validate_required_settings(self) -> None:
        """Проверяет что все обязательные настройки заполнены"""
        required_fields = {
            'mattermost_url': 'URL Mattermost сервера',
            'mattermost_token': 'Токен Mattermost бота',
            'mattermost_team_id': 'ID команды в Mattermost',
            'jira_base_url': 'URL Jira сервера'
        }
        
        missing_fields = []
        for field, description in required_fields.items():
            if not getattr(self, field, None):
                missing_fields.append(f"{field} ({description})")
        
        if missing_fields:
            raise ValueError(
                f"Отсутствуют обязательные настройки в .env файле:\n" +
                "\n".join([f"- {field}" for field in missing_fields]) +
                f"\n\nПроверьте файл .env и заполните необходимые параметры."
            )
    
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

# Проверяем обязательные настройки при импорте
# (только в продакшн режиме, чтобы не мешать разработке)
if os.getenv("APP_MODE", "development") == "production":
    settings.validate_required_settings() 