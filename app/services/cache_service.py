"""
Сервис для работы с Redis кешированием
"""
import json
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import aioredis
from loguru import logger

from app.config import settings


class CacheError(Exception):
    """Исключение для ошибок кеширования"""
    pass


class CacheService:
    """Сервис для работы с Redis кешированием"""
    
    def __init__(self):
        self.redis_url = settings.redis_url
        self.redis = None
        self.default_ttl = 3600  # 1 час по умолчанию
        self.key_prefix = "askbot:"
        
    async def __aenter__(self):
        """Async context manager entry"""
        try:
            self.redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            # Проверяем соединение
            await self.redis.ping()
            logger.info("Подключение к Redis установлено")
            return self
        except Exception as e:
            logger.error(f"Ошибка подключения к Redis: {e}")
            raise CacheError(f"Не удалось подключиться к Redis: {e}")
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.redis:
            await self.redis.close()
    
    def _make_key(self, key: str) -> str:
        """
        Создает полный ключ с префиксом
        
        Args:
            key: Базовый ключ
            
        Returns:
            Полный ключ с префиксом
        """
        return f"{self.key_prefix}{key}"
    
    def _hash_key(self, data: Union[str, Dict, List]) -> str:
        """
        Создает хеш для сложных ключей
        
        Args:
            data: Данные для хеширования
            
        Returns:
            MD5 хеш строки
        """
        if isinstance(data, (dict, list)):
            data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            data_str = str(data)
        
        return hashlib.md5(data_str.encode()).hexdigest()
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Получает значение из кеша
        
        Args:
            key: Ключ
            default: Значение по умолчанию
            
        Returns:
            Значение из кеша или default
        """
        try:
            if not self.redis:
                return default
                
            full_key = self._make_key(key)
            value = await self.redis.get(full_key)
            
            if value is None:
                return default
            
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except Exception as e:
            logger.error(f"Ошибка получения из кеша {key}: {e}")
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Сохраняет значение в кеш
        
        Args:
            key: Ключ
            value: Значение
            ttl: Время жизни в секундах
            
        Returns:
            True при успехе
        """
        try:
            if not self.redis:
                return False
                
            full_key = self._make_key(key)
            ttl = ttl or self.default_ttl
            
            # Сериализуем значение
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value, ensure_ascii=False, default=str)
            else:
                serialized_value = str(value)
            
            await self.redis.setex(full_key, ttl, serialized_value)
            logger.debug(f"Значение сохранено в кеш: {key} (TTL: {ttl}s)")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в кеш {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Удаляет значение из кеша
        
        Args:
            key: Ключ
            
        Returns:
            True при успехе
        """
        try:
            if not self.redis:
                return False
                
            full_key = self._make_key(key)
            result = await self.redis.delete(full_key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Ошибка удаления из кеша {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Проверяет существование ключа в кеше
        
        Args:
            key: Ключ
            
        Returns:
            True если ключ существует
        """
        try:
            if not self.redis:
                return False
                
            full_key = self._make_key(key)
            result = await self.redis.exists(full_key)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Ошибка проверки существования ключа {key}: {e}")
            return False
    
    async def get_ttl(self, key: str) -> int:
        """
        Получает оставшееся время жизни ключа
        
        Args:
            key: Ключ
            
        Returns:
            Оставшееся время в секундах (-1 если без TTL, -2 если не существует)
        """
        try:
            if not self.redis:
                return -2
                
            full_key = self._make_key(key)
            return await self.redis.ttl(full_key)
            
        except Exception as e:
            logger.error(f"Ошибка получения TTL для ключа {key}: {e}")
            return -2
    
    async def extend_ttl(self, key: str, ttl: int) -> bool:
        """
        Продлевает время жизни ключа
        
        Args:
            key: Ключ
            ttl: Новое время жизни в секундах
            
        Returns:
            True при успехе
        """
        try:
            if not self.redis:
                return False
                
            full_key = self._make_key(key)
            result = await self.redis.expire(full_key, ttl)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Ошибка продления TTL для ключа {key}: {e}")
            return False
    
    def make_jql_cache_key(self, jql: str, username: str, additional_params: Dict = None) -> str:
        """
        Создает ключ кеша для JQL запроса
        
        Args:
            jql: JQL запрос
            username: Имя пользователя
            additional_params: Дополнительные параметры
            
        Returns:
            Ключ кеша
        """
        cache_data = {
            "jql": jql,
            "username": username,
            "params": additional_params or {}
        }
        
        cache_hash = self._hash_key(cache_data)
        return f"jql:{cache_hash}"
    
    def make_user_cache_key(self, user_id: str, data_type: str) -> str:
        """
        Создает ключ кеша для пользовательских данных
        
        Args:
            user_id: ID пользователя
            data_type: Тип данных (credentials, projects, etc.)
            
        Returns:
            Ключ кеша
        """
        return f"user:{user_id}:{data_type}"
    
    def make_chart_cache_key(self, chart_data: Dict[str, Any]) -> str:
        """
        Создает ключ кеша для графика
        
        Args:
            chart_data: Данные для графика
            
        Returns:
            Ключ кеша
        """
        cache_hash = self._hash_key(chart_data)
        return f"chart:{cache_hash}"
    
    async def cache_jql_result(self, jql: str, username: str, result: Dict[str, Any], 
                             ttl: int = 1800) -> bool:
        """
        Кеширует результат JQL запроса
        
        Args:
            jql: JQL запрос
            username: Имя пользователя
            result: Результат запроса
            ttl: Время жизни кеша (30 минут по умолчанию)
            
        Returns:
            True при успехе
        """
        try:
            cache_key = self.make_jql_cache_key(jql, username)
            
            # Добавляем метаданные
            cache_data = {
                "result": result,
                "cached_at": datetime.now().isoformat(),
                "jql": jql,
                "username": username
            }
            
            return await self.set(cache_key, cache_data, ttl)
            
        except Exception as e:
            logger.error(f"Ошибка кеширования JQL результата: {e}")
            return False
    
    async def get_cached_jql_result(self, jql: str, username: str) -> Optional[Dict[str, Any]]:
        """
        Получает кешированный результат JQL запроса
        
        Args:
            jql: JQL запрос
            username: Имя пользователя
            
        Returns:
            Кешированный результат или None
        """
        try:
            cache_key = self.make_jql_cache_key(jql, username)
            cached_data = await self.get(cache_key)
            
            if cached_data and "result" in cached_data:
                logger.info(f"Найден кешированный результат для JQL: {jql[:50]}...")
                return cached_data["result"]
                
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения кешированного JQL результата: {e}")
            return None
    
    async def cache_user_credentials(self, user_id: str, credentials: Dict[str, str], 
                                   ttl: int = 7200) -> bool:
        """
        Кеширует учетные данные пользователя
        
        Args:
            user_id: ID пользователя
            credentials: Учетные данные
            ttl: Время жизни (2 часа по умолчанию)
            
        Returns:
            True при успехе
        """
        try:
            cache_key = self.make_user_cache_key(user_id, "credentials")
            return await self.set(cache_key, credentials, ttl)
            
        except Exception as e:
            logger.error(f"Ошибка кеширования учетных данных пользователя {user_id}: {e}")
            return False
    
    async def get_cached_user_credentials(self, user_id: str) -> Optional[Dict[str, str]]:
        """
        Получает кешированные учетные данные пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Учетные данные или None
        """
        try:
            cache_key = self.make_user_cache_key(user_id, "credentials")
            return await self.get(cache_key)
            
        except Exception as e:
            logger.error(f"Ошибка получения кешированных учетных данных пользователя {user_id}: {e}")
            return None
    
    async def invalidate_user_cache(self, user_id: str) -> bool:
        """
        Инвалидирует весь кеш пользователя
        
        Args:
            user_id: ID пользователя
            
        Returns:
            True при успехе
        """
        try:
            if not self.redis:
                return False
                
            # Получаем все ключи пользователя
            pattern = self._make_key(f"user:{user_id}:*")
            keys = await self.redis.keys(pattern)
            
            if keys:
                await self.redis.delete(*keys)
                logger.info(f"Инвалидирован кеш пользователя {user_id}: {len(keys)} ключей")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инвалидации кеша пользователя {user_id}: {e}")
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Получает статистику кеша
        
        Returns:
            Словарь со статистикой
        """
        try:
            if not self.redis:
                return {"error": "Redis не подключен"}
            
            # Информация о Redis
            info = await self.redis.info()
            
            # Подсчитываем ключи по типам
            all_keys = await self.redis.keys(self._make_key("*"))
            
            stats = {
                "total_keys": len(all_keys),
                "memory_usage": info.get("used_memory_human", "N/A"),
                "connected_clients": info.get("connected_clients", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "key_types": {}
            }
            
            # Группируем ключи по типам
            for key in all_keys:
                key_type = key.split(":")[1] if ":" in key else "other"
                stats["key_types"][key_type] = stats["key_types"].get(key_type, 0) + 1
            
            # Вычисляем hit rate
            total_ops = stats["hits"] + stats["misses"]
            if total_ops > 0:
                stats["hit_rate"] = round(stats["hits"] / total_ops * 100, 2)
            else:
                stats["hit_rate"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Ошибка получения статистики кеша: {e}")
            return {"error": str(e)}
    
    async def cleanup_expired_keys(self) -> int:
        """
        Очищает истекшие ключи (Redis делает это автоматически, но можно форсировать)
        
        Returns:
            Количество удаленных ключей
        """
        try:
            if not self.redis:
                return 0
            
            # Получаем все наши ключи
            pattern = self._make_key("*")
            keys = await self.redis.keys(pattern)
            
            deleted_count = 0
            for key in keys:
                ttl = await self.redis.ttl(key)
                if ttl == -2:  # Ключ не существует (уже истек)
                    deleted_count += 1
            
            logger.info(f"Найдено истекших ключей: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки истекших ключей: {e}")
            return 0
    
    async def flush_all_cache(self) -> bool:
        """
        Очищает весь кеш приложения (ОСТОРОЖНО!)
        
        Returns:
            True при успехе
        """
        try:
            if not self.redis:
                return False
            
            # Удаляем только наши ключи
            pattern = self._make_key("*")
            keys = await self.redis.keys(pattern)
            
            if keys:
                await self.redis.delete(*keys)
                logger.warning(f"Очищен весь кеш приложения: {len(keys)} ключей")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка очистки всего кеша: {e}")
            return False


# Глобальный экземпляр сервиса
cache_service = CacheService() 