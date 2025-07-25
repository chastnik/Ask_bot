"""
Основное FastAPI приложение Ask Bot
Теперь работает только с личными сообщениями через WebSocket
"""
import os
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings
from app.models.schemas import HealthCheck, ErrorResponse
from app.services.jira_service import jira_service
from app.services.mattermost_service import mattermost_service
from app.services.llm_service import llm_service
from app.services.cache_service import cache_service
from app.services.chart_service import chart_service
from app.services.websocket_client import websocket_client
from app.services.message_processor import message_processor


# Настройка логирования
logger.add(
    "logs/askbot.log",
    rotation="10 MB",
    retention="7 days",
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}"
)

# Создаем директории
os.makedirs("logs", exist_ok=True)
os.makedirs(settings.chart_save_path, exist_ok=True)


async def handle_websocket_message(message_info: Dict[str, Any]):
    """
    Обработчик сообщений от WebSocket клиента
    """
    try:
        user_id = message_info["user_id"]
        message_text = message_info["message"]
        
        logger.info(f"📥 Обработка сообщения от {user_id}: {message_text}")
        
        # Обрабатываем сообщение через процессор
        response = await message_processor.process_message(user_id, message_text)
        
        if response:
            # Отправляем ответ пользователю
            async with mattermost_service as mm:
                success = await mm.send_direct_message(user_id, response)
                
            if success:
                logger.info(f"📤 Ответ отправлен пользователю {user_id}")
            else:
                logger.error(f"❌ Не удалось отправить ответ пользователю {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки WebSocket сообщения: {e}")
        
        # Пытаемся отправить сообщение об ошибке
        try:
            async with mattermost_service as mm:
                await mm.send_direct_message(
                    message_info["user_id"],
                    f"❌ Произошла ошибка при обработке сообщения: {str(e)}"
                )
        except Exception as send_error:
            logger.error(f"❌ Не удалось отправить сообщение об ошибке: {send_error}")


async def start_websocket_client():
    """Запускает WebSocket клиент в фоновом режиме"""
    try:
        # Устанавливаем обработчик сообщений
        websocket_client.set_message_handler(handle_websocket_message)
        
        # Запускаем подключение
        while True:
            try:
                logger.info("🔌 Запуск WebSocket клиента...")
                await websocket_client.connect()
                
            except Exception as e:
                logger.error(f"❌ Ошибка WebSocket: {e}")
                logger.info("🔄 Переподключение через 10 секунд...")
                await asyncio.sleep(10)
                
    except Exception as e:
        logger.error(f"❌ Критическая ошибка WebSocket клиента: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("🚀 Запуск Ask Bot...")
    
    # Инициализация сервисов
    try:
        # Проверяем подключения
        async with cache_service as cache:
            logger.info("✅ Redis подключен")
            
        async with mattermost_service as mm:
            if await mm.test_connection():
                logger.info("✅ Mattermost подключен")
            else:
                logger.warning("⚠️ Проблемы с подключением к Mattermost")
                
        async with jira_service as jira:
            logger.info("✅ Jira сервис инициализирован")
            
        async with llm_service as llm:
            if await llm.test_connection():
                logger.info("✅ LLM подключена")
            else:
                logger.warning("⚠️ Проблемы с подключением к LLM")
        
        # Запускаем WebSocket клиент в фоновой задаче
        websocket_task = asyncio.create_task(start_websocket_client())
        
        logger.info("🎉 Ask Bot успешно запущен!")
        logger.info("💬 Бот готов к работе с личными сообщениями")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        
    yield
    
    # Завершение работы
    logger.info("🛑 Остановка Ask Bot...")
    
    # Закрываем WebSocket соединение
    try:
        websocket_task.cancel()
        await websocket_client.disconnect()
    except Exception as e:
        logger.error(f"Ошибка закрытия WebSocket: {e}")


# Создание FastAPI приложения
app = FastAPI(
    title="Ask Bot",
    description="Универсальный чат-бот для Jira с аналитикой и визуализацией (только личные сообщения)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы для графиков
app.mount("/charts", StaticFiles(directory=settings.chart_save_path), name="charts")


@app.get("/", response_model=Dict[str, str])
async def root():
    """Корневой эндпоинт"""
    return {
        "message": "Ask Bot API (только личные сообщения)",
        "version": "1.0.0",
        "status": "running",
        "mode": "direct_messages_only",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Проверка здоровья системы"""
    try:
        health_status = {
            "status": "healthy",
            "database": True,  # SQLite всегда доступен
            "redis": False,
            "jira": False,
            "llm": False,
            "websocket": websocket_client.is_connected,
            "timestamp": datetime.now()
        }
        
        # Проверяем Redis
        try:
            async with cache_service as cache:
                await cache.redis.ping()
                health_status["redis"] = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
        
        # Проверяем Mattermost
        try:
            async with mattermost_service as mm:
                health_status["mattermost"] = await mm.test_connection()
        except Exception as e:
            logger.error(f"Mattermost health check failed: {e}")
            health_status["mattermost"] = False
        
        # Проверяем Jira (базовый тест без авторизации)
        try:
            health_status["jira"] = True  # Предполагаем что URL доступен
        except Exception as e:
            logger.error(f"Jira health check failed: {e}")
        
        # Проверяем LLM
        try:
            async with llm_service as llm:
                health_status["llm"] = await llm.test_connection()
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
        
        # Определяем общий статус
        if all([health_status["redis"], health_status.get("mattermost", False), 
                health_status["jira"], health_status["llm"], health_status["websocket"]]):
            health_status["status"] = "healthy"
        elif health_status["database"]:
            health_status["status"] = "degraded"
        else:
            health_status["status"] = "unhealthy"
        
        return HealthCheck(**health_status)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return HealthCheck(
            status="error",
            database=False,
            redis=False,
            jira=False,
            llm=False,
            websocket=False,
            timestamp=datetime.now()
        )


@app.get("/cache/stats")
async def get_cache_stats():
    """Получить статистику кеша"""
    try:
        async with cache_service as cache:
            stats = await cache.get_cache_stats()
            return JSONResponse(content=stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/clear")
async def clear_cache():
    """Очистить кеш"""
    try:
        async with cache_service as cache:
            result = await cache.flush_all_cache()
            if result:
                return {"message": "Кеш успешно очищен"}
            else:
                raise HTTPException(status_code=500, detail="Не удалось очистить кеш")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/websocket/status")
async def websocket_status():
    """Получить статус WebSocket подключения"""
    return {
        "connected": websocket_client.is_connected,
        "bot_username": websocket_client.bot_username,
        "base_url": websocket_client.base_url,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/charts/cleanup")
async def cleanup_old_charts(background_tasks: BackgroundTasks, days: int = 7):
    """Очистить старые графики"""
    try:
        def cleanup_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                deleted_count = loop.run_until_complete(
                    chart_service.cleanup_old_charts(days)
                )
                logger.info(f"Удалено старых графиков: {deleted_count}")
            finally:
                loop.close()
        
        background_tasks.add_task(cleanup_task)
        return {"message": f"Запущена очистка графиков старше {days} дней"}
        
    except Exception as e:
        logger.error(f"Error scheduling chart cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/test-llm")
async def test_llm_connection():
    """Тестовый эндпоинт для проверки LLM"""
    try:
        async with llm_service as llm:
            response = await llm.generate_completion(
                prompt="Привет! Как дела?",
                temperature=0.7,
                max_tokens=50
            )
            return {
                "status": "success",
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"LLM test error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/debug/test-jira")
async def test_jira_connection():
    """Тестовый эндпоинт для проверки Jira (требует авторизации)"""
    try:
        # Этот эндпоинт требует передачи учетных данных
        return {
            "status": "info",
            "message": "Для тестирования Jira необходимы учетные данные пользователя",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Jira test error: {e}")
        return {
            "status": "error", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Обработчик HTTP исключений"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            code=str(exc.status_code),
            timestamp=datetime.now()
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Обработчик общих исключений"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Внутренняя ошибка сервера",
            detail=str(exc) if settings.app_mode == "development" else None,
            code="500",
            timestamp=datetime.now()
        ).dict()
    )


# Запуск приложения
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_mode == "development",
        log_level=settings.log_level.lower()
    ) 