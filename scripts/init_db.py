#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных Ask Bot
"""
import sys
import os
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.database import Base
from loguru import logger


def create_database():
    """Создает таблицы базы данных"""
    try:
        engine = create_engine(settings.database_url)
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Таблицы базы данных созданы успешно")
        return engine
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")
        raise


def load_sample_data(engine):
    """Загружает примеры данных"""
    try:
        sample_data_path = Path(__file__).parent.parent / "examples" / "sample_data.sql"
        
        if not sample_data_path.exists():
            logger.warning("⚠️ Файл с примерами данных не найден")
            return
        
        with open(sample_data_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Разделяем на отдельные запросы
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
        
        with engine.connect() as conn:
            for statement in statements:
                if statement:
                    try:
                        conn.execute(text(statement))
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Пропущен запрос (возможно, данные уже существуют): {e}")
                        conn.rollback()
        
        logger.info("✅ Примеры данных загружены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки примеров данных: {e}")


def main():
    """Основная функция инициализации"""
    print("🚀 Инициализация базы данных Ask Bot")
    print("=" * 50)
    
    try:
        # Создаем таблицы
        engine = create_database()
        
        # Загружаем примеры данных
        answer = input("Загрузить примеры данных? (y/N): ").lower().strip()
        if answer in ['y', 'yes', 'да']:
            load_sample_data(engine)
        
        print("\n🎉 Инициализация завершена успешно!")
        print("\nТеперь вы можете:")
        print("1. Запустить приложение: uvicorn app.main:app --reload")
        print("2. Или использовать Docker: docker-compose up")
        print("3. Настроить переменные окружения в .env файле")
        
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 