"""
Утилиты для авторизации и шифрования данных
"""
import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from loguru import logger

from app.config import settings


class CryptoManager:
    """Менеджер для шифрования и дешифрования чувствительных данных"""
    
    def __init__(self):
        # Генерируем ключ на основе SECRET_KEY
        key_material = settings.secret_key.encode()
        
        # Создаем 32-байтовый ключ для Fernet
        digest = hashlib.sha256(key_material).digest()
        self.key = base64.urlsafe_b64encode(digest)
        self.cipher = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Шифрует строку
        
        Args:
            plaintext: Строка для шифрования
            
        Returns:
            Зашифрованная строка в base64
        """
        try:
            if not plaintext:
                return ""
            
            encrypted_bytes = self.cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
            
        except Exception as e:
            logger.error(f"Ошибка шифрования: {e}")
            raise
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Дешифрует строку
        
        Args:
            encrypted_text: Зашифрованная строка в base64
            
        Returns:
            Расшифрованная строка
        """
        try:
            if not encrypted_text:
                return ""
            
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
            
        except Exception as e:
            logger.error(f"Ошибка дешифрования: {e}")
            raise


# Глобальный экземпляр криптоменеджера
crypto_manager = CryptoManager()


def encrypt_password(password: str) -> str:
    """
    Шифрует пароль для безопасного хранения
    
    Args:
        password: Пароль для шифрования
        
    Returns:
        Зашифрованный пароль
    """
    return crypto_manager.encrypt(password)


def decrypt_password(encrypted_password: str) -> str:
    """
    Дешифрует пароль
    
    Args:
        encrypted_password: Зашифрованный пароль
        
    Returns:
        Расшифрованный пароль
    """
    return crypto_manager.decrypt(encrypted_password)


def hash_password(password: str) -> str:
    """
    Создает хеш пароля для проверки (односторонняя функция)
    
    Args:
        password: Пароль для хеширования
        
    Returns:
        Хеш пароля
    """
    return hashlib.pbkdf2_hex(
        password.encode(), 
        settings.secret_key.encode(),
        100000  # iterations
    )


def verify_password(password: str, password_hash: str) -> bool:
    """
    Проверяет пароль против хеша
    
    Args:
        password: Проверяемый пароль
        password_hash: Сохраненный хеш
        
    Returns:
        True если пароль верный
    """
    return hash_password(password) == password_hash


def validate_jira_credentials(username: str, password: Optional[str] = None, 
                            token: Optional[str] = None) -> bool:
    """
    Базовая валидация учетных данных Jira
    
    Args:
        username: Имя пользователя
        password: Пароль (опционально)
        token: API токен (опционально)
        
    Returns:
        True если данные прошли базовую валидацию
    """
    if not username or len(username.strip()) < 3:
        return False
    
    if not token and not password:
        return False
    
    if password and len(password.strip()) < 6:
        return False
    
    if token and len(token.strip()) < 10:
        return False
        
    return True


def parse_auth_message(message: str) -> dict:
    """
    Парсит сообщение с учетными данными от пользователя
    
    Args:
        message: Сообщение пользователя с учетными данными
        
    Returns:
        Словарь с распарсенными данными
    """
    credentials = {}
    
    lines = message.strip().split('\n')
    for line in lines:
        line = line.strip()
        if ' ' in line:
            key, value = line.split(' ', 1)
            key = key.lower()
            
            if key in ['username', 'user', 'login']:
                credentials['username'] = value.strip()
            elif key in ['password', 'pass', 'pwd']:
                credentials['password'] = value.strip()
            elif key in ['token', 'api_token', 'apitoken']:
                credentials['token'] = value.strip()
    
    return credentials


class JiraRoleManager:
    """Менеджер ролей и прав доступа в Jira"""
    
    @staticmethod
    def get_user_permissions(user_data: dict) -> dict:
        """
        Определяет права доступа пользователя на основе его данных Jira
        
        Args:
            user_data: Данные пользователя из Jira API
            
        Returns:
            Словарь с правами доступа
        """
        # Базовые права для всех пользователей
        permissions = {
            "can_view_issues": True,
            "can_search": True,
            "can_view_worklogs": False,
            "can_view_all_projects": False,
            "can_create_reports": False,
            "can_manage_bot": False,
            "accessible_projects": []
        }
        
        # Определяем роли на основе групп пользователя
        user_groups = user_data.get("groups", {}).get("items", [])
        group_names = [group.get("name", "").lower() for group in user_groups]
        
        # Администраторы
        if any("admin" in group for group in group_names):
            permissions.update({
                "can_view_worklogs": True,
                "can_view_all_projects": True,
                "can_create_reports": True,
                "can_manage_bot": True
            })
        
        # Менеджеры проектов
        elif any("manager" in group or "lead" in group for group in group_names):
            permissions.update({
                "can_view_worklogs": True,
                "can_create_reports": True
            })
        
        # Разработчики
        elif any("developer" in group or "dev" in group for group in group_names):
            permissions.update({
                "can_view_worklogs": True
            })
        
        return permissions
    
    @staticmethod
    def can_access_project(user_permissions: dict, project_key: str) -> bool:
        """
        Проверяет может ли пользователь получить доступ к проекту
        
        Args:
            user_permissions: Права пользователя
            project_key: Ключ проекта
            
        Returns:
            True если доступ разрешен
        """
        if user_permissions.get("can_view_all_projects", False):
            return True
        
        accessible_projects = user_permissions.get("accessible_projects", [])
        return project_key in accessible_projects
    
    @staticmethod
    def can_view_worklogs(user_permissions: dict) -> bool:
        """
        Проверяет может ли пользователь просматривать worklogs
        
        Args:
            user_permissions: Права пользователя
            
        Returns:
            True если доступ разрешен
        """
        return user_permissions.get("can_view_worklogs", False)
    
    @staticmethod
    def filter_jql_by_permissions(jql: str, user_permissions: dict) -> str:
        """
        Модифицирует JQL запрос с учетом прав пользователя
        
        Args:
            jql: Исходный JQL запрос
            user_permissions: Права пользователя
            
        Returns:
            Модифицированный JQL запрос
        """
        # Если пользователь может видеть все проекты, возвращаем как есть
        if user_permissions.get("can_view_all_projects", False):
            return jql
        
        # Добавляем ограничение по проектам
        accessible_projects = user_permissions.get("accessible_projects", [])
        if accessible_projects:
            project_filter = f"project in ({', '.join(accessible_projects)})"
            
            if "project" not in jql.lower():
                # Добавляем фильтр по проектам
                if jql.strip():
                    jql = f"({jql}) AND {project_filter}"
                else:
                    jql = project_filter
        
        return jql


# Глобальный экземпляр менеджера ролей
role_manager = JiraRoleManager() 