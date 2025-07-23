"""
Pydantic схемы для валидации данных API
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator


# Базовые схемы
class BaseSchema(BaseModel):
    """Базовая схема с общими настройками"""
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Пользователь
class UserBase(BaseSchema):
    username: str = Field(..., min_length=1, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    display_name: Optional[str] = Field(None, max_length=100)
    preferred_language: str = Field(default="ru", pattern=r'^(ru|en)$')
    timezone: str = Field(default="UTC", max_length=50)


class UserCreate(UserBase):
    id: str = Field(..., min_length=1, max_length=50)
    jira_username: Optional[str] = None
    jira_password: Optional[str] = None  # Будет зашифрован
    jira_token: Optional[str] = None


class UserUpdate(BaseSchema):
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    display_name: Optional[str] = Field(None, max_length=100)
    jira_username: Optional[str] = None
    jira_password: Optional[str] = None
    jira_token: Optional[str] = None
    preferred_language: Optional[str] = Field(None, pattern=r'^(ru|en)$')
    timezone: Optional[str] = Field(None, max_length=50)


class User(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    # Без паролей в ответе
    jira_username: Optional[str] = None


# Клиент
class ClientBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    jira_key: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    jira_key: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class Client(ClientBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


# Проект
class ProjectBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    jira_key: str = Field(..., min_length=1, max_length=20)
    description: Optional[str] = None


class ProjectCreate(ProjectBase):
    client_id: Optional[int] = None


class ProjectUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    jira_key: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    client_id: Optional[int] = None
    is_active: Optional[bool] = None


class Project(ProjectBase):
    id: int
    client_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    is_active: bool


# Шаблон запроса
class QueryTemplateBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    template: str = Field(..., min_length=1)
    category: str = Field(..., min_length=1, max_length=50)
    chart_type: Optional[str] = Field(None, pattern=r'^(bar|line|pie|table|scatter)$')


class QueryTemplateCreate(QueryTemplateBase):
    parameters: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    chart_config: Optional[Dict[str, Any]] = None


class QueryTemplateUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    template: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    parameters: Optional[List[str]] = None
    examples: Optional[List[str]] = None
    chart_type: Optional[str] = Field(None, pattern=r'^(bar|line|pie|table|scatter)$')
    chart_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class QueryTemplate(QueryTemplateBase):
    id: int
    parameters: Optional[List[str]]
    examples: Optional[List[str]]
    chart_config: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    usage_count: int


# Mattermost схемы
class MattermostUser(BaseSchema):
    """Схема пользователя Mattermost"""
    id: str
    username: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nickname: Optional[str] = None


class MattermostChannel(BaseSchema):
    """Схема канала Mattermost"""
    id: str
    team_id: str
    type: str
    display_name: str
    name: str


class MattermostPost(BaseSchema):
    """Схема поста Mattermost"""
    id: str
    create_at: int
    update_at: int
    user_id: str
    channel_id: str
    message: str
    type: str = ""
    
    @validator('create_at', 'update_at', pre=True)
    def convert_timestamp(cls, v):
        """Конвертируем миллисекунды в секунды"""
        if isinstance(v, int) and v > 1000000000000:
            return v // 1000
        return v


class SlashCommandRequest(BaseSchema):
    """Схема slash команды от Mattermost"""
    token: str
    team_id: str
    team_domain: str
    channel_id: str
    channel_name: str
    user_id: str
    user_name: str
    command: str
    text: str
    response_url: Optional[str] = None
    trigger_id: Optional[str] = None


class DirectMessageRequest(BaseSchema):
    """Схема входящего личного сообщения от Mattermost"""
    user_id: str
    user_name: str
    channel_id: str
    channel_type: str
    team_id: str
    text: str
    timestamp: Optional[str] = None
    post_id: Optional[str] = None
    
    class Config:
        extra = "allow"


class SlashCommandResponse(BaseSchema):
    """Схема ответа на slash команду"""
    response_type: str = Field(default="ephemera", pattern=r'^(ephemeral|in_channel)$')
    text: str
    username: Optional[str] = None
    icon_url: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        extra = "allow"


# Jira схемы
class JiraIssue(BaseSchema):
    """Упрощенная схема задачи Jira"""
    id: str
    key: str
    summary: str
    description: Optional[str] = None
    status: str
    issue_type: str
    priority: str
    assignee: Optional[str] = None
    reporter: str
    created: datetime
    updated: datetime
    due_date: Optional[datetime] = None
    resolved: Optional[datetime] = None
    project_key: str
    project_name: str
    
    @validator('created', 'updated', 'due_date', 'resolved', pre=True)
    def parse_jira_datetime(cls, v):
        """Парсим даты Jira"""
        if isinstance(v, str):
            # Jira возвращает ISO формат
            from dateutil.parser import parse
            return parse(v)
        return v


class JiraSearchResult(BaseSchema):
    """Результат поиска в Jira"""
    issues: List[JiraIssue]
    total: int
    start_at: int
    max_results: int
    jql: str


class JiraWorklog(BaseSchema):
    """Схема worklog из Jira"""
    id: str
    issue_key: str
    author: str
    time_spent_seconds: int
    created: datetime
    started: datetime
    comment: Optional[str] = None


# Запросы пользователя
class UserQuery(BaseSchema):
    """Схема запроса пользователя"""
    query: str = Field(..., min_length=1, max_length=1000)
    context: Optional[Dict[str, Any]] = None
    channel_id: str
    user_id: str
    should_visualize: bool = False


class QueryResult(BaseSchema):
    """Результат обработки запроса"""
    original_query: str
    processed_query: str
    jql_query: Optional[str] = None
    result_type: str  # data, chart, error, info
    data: Optional[Union[List[Dict], Dict[str, Any]]] = None
    chart_url: Optional[str] = None
    message: str
    execution_time: float
    cached: bool = False
    suggestions: Optional[List[str]] = None


# Аналитика и графики
class ChartRequest(BaseSchema):
    """Запрос на создание графика"""
    chart_type: str = Field(..., pattern=r'^(bar|line|pie|table|scatter)$')
    data: List[Dict[str, Any]]
    title: str
    x_axis: str
    y_axis: str
    config: Optional[Dict[str, Any]] = None


class ChartResponse(BaseSchema):
    """Ответ с графиком"""
    chart_url: str
    chart_type: str
    title: str
    created_at: datetime


# Схемы для кеширования
class CacheItem(BaseSchema):
    """Элемент кеша"""
    key: str
    data: Any
    ttl: int = 3600  # TTL в секундах
    tags: Optional[List[str]] = None


class CacheStats(BaseSchema):
    """Статистика кеша"""
    total_entries: int
    hit_rate: float
    memory_usage: int  # в байтах
    expired_entries: int


# Схемы для RAG
class DocumentBase(BaseSchema):
    """Базовая схема документа"""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    content_type: str = Field(..., pattern=r'^(jql|faq|guide)$')
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    content_type: Optional[str] = Field(None, pattern=r'^(jql|faq|guide)$')
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class Document(DocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class SearchQuery(BaseSchema):
    """Поисковый запрос для RAG"""
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)
    content_types: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class SearchResult(BaseSchema):
    """Результат поиска в RAG"""
    documents: List[Document]
    query: str
    total_found: int
    processing_time: float


# Системные схемы
class HealthCheck(BaseSchema):
    """Схема проверки здоровья системы"""
    status: str
    database: bool
    redis: bool
    jira: bool
    llm: bool
    timestamp: datetime


class ErrorResponse(BaseSchema):
    """Схема ошибки"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now) 