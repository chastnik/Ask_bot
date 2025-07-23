"""
Вспомогательные функции
"""
import re
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from loguru import logger


def sanitize_filename(filename: str) -> str:
    """
    Очищает имя файла от недопустимых символов
    
    Args:
        filename: Исходное имя файла
        
    Returns:
        Очищенное имя файла
    """
    # Убираем unicode символы
    filename = unicodedata.normalize('NFKD', filename)
    
    # Заменяем недопустимые символы
    filename = re.sub(r'[^\w\s-.]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    
    return filename.strip('-.')


def parse_date_range(date_string: str) -> Dict[str, Optional[datetime]]:
    """
    Парсит текстовое описание периода времени
    
    Args:
        date_string: Строка с описанием периода
        
    Returns:
        Словарь с начальной и конечной датой
    """
    date_string = date_string.lower().strip()
    now = datetime.now()
    
    # Месяцы на русском
    months_ru = {
        'январь': 1, 'января': 1, 'январе': 1,
        'февраль': 2, 'февраля': 2, 'феврале': 2,
        'март': 3, 'марта': 3, 'марте': 3,
        'апрель': 4, 'апреля': 4, 'апреле': 4,
        'май': 5, 'мая': 5, 'мае': 5,
        'июнь': 6, 'июня': 6, 'июне': 6,
        'июль': 7, 'июля': 7, 'июле': 7,
        'август': 8, 'августа': 8, 'августе': 8,
        'сентябрь': 9, 'сентября': 9, 'сентябре': 9,
        'октябрь': 10, 'октября': 10, 'октябре': 10,
        'ноябрь': 11, 'ноября': 11, 'ноябре': 11,
        'декабрь': 12, 'декабря': 12, 'декабре': 12
    }
    
    result = {"start_date": None, "end_date": None}
    
    try:
        # Последние N дней/недель/месяцев
        if 'последн' in date_string:
            if 'день' in date_string or 'дня' in date_string or 'дней' in date_string:
                days_match = re.search(r'(\d+)', date_string)
                if days_match:
                    days = int(days_match.group(1))
                    result["start_date"] = now - timedelta(days=days)
                    result["end_date"] = now
            
            elif 'недел' in date_string:
                weeks_match = re.search(r'(\d+)', date_string)
                if weeks_match:
                    weeks = int(weeks_match.group(1))
                    result["start_date"] = now - timedelta(weeks=weeks)
                    result["end_date"] = now
            
            elif 'месяц' in date_string:
                months_match = re.search(r'(\d+)', date_string)
                if months_match:
                    months = int(months_match.group(1))
                    start_date = now.replace(day=1)
                    for _ in range(months):
                        if start_date.month == 1:
                            start_date = start_date.replace(year=start_date.year - 1, month=12)
                        else:
                            start_date = start_date.replace(month=start_date.month - 1)
                    
                    result["start_date"] = start_date
                    result["end_date"] = now
        
        # Конкретные месяцы
        else:
            for month_name, month_num in months_ru.items():
                if month_name in date_string:
                    year = now.year
                    
                    # Проверяем указан ли год
                    year_match = re.search(r'(\d{4})', date_string)
                    if year_match:
                        year = int(year_match.group(1))
                    
                    # Начало и конец месяца
                    result["start_date"] = datetime(year, month_num, 1)
                    
                    if month_num == 12:
                        result["end_date"] = datetime(year + 1, 1, 1) - timedelta(days=1)
                    else:
                        result["end_date"] = datetime(year, month_num + 1, 1) - timedelta(days=1)
                    
                    break
        
        # Если не удалось распарсить, используем текущий месяц
        if not result["start_date"]:
            result["start_date"] = now.replace(day=1)
            if now.month == 12:
                result["end_date"] = datetime(now.year + 1, 1, 1) - timedelta(days=1)
            else:
                result["end_date"] = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
    
    except Exception as e:
        logger.error(f"Ошибка парсинга даты '{date_string}': {e}")
        
    return result


def extract_client_name(text: str) -> Optional[str]:
    """
    Извлекает название клиента из текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        Название клиента или None
    """
    # Список известных клиентов (в реальном проекте из БД)
    known_clients = [
        "Иль-Де-Ботэ", "Бургер-Кинг", "Летуаль", "Visiology", 
        "Битрикс", "1С", "Сбербанк", "ВТБ", "Альфа-Банк"
    ]
    
    text_lower = text.lower()
    
    for client in known_clients:
        if client.lower() in text_lower:
            return client
    
    return None


def extract_project_key(text: str) -> Optional[str]:
    """
    Извлекает ключ проекта из текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        Ключ проекта или None
    """
    # Паттерн для ключей проектов (обычно 2-5 заглавных букв)
    project_pattern = r'\b([A-Z]{2,5})\b'
    matches = re.findall(project_pattern, text)
    
    if matches:
        return matches[0]
    
    return None


def extract_user_names(text: str) -> List[str]:
    """
    Извлекает имена пользователей из текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        Список найденных имен
    """
    # Паттерн для русских имен (Имя Фамилия)
    name_pattern = r'\b([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)\b'
    matches = re.findall(name_pattern, text)
    
    return matches


def format_duration(seconds: int) -> str:
    """
    Форматирует продолжительность в человекочитаемый вид
    
    Args:
        seconds: Количество секунд
        
    Returns:
        Отформатированная строка
    """
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}м"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes == 0:
            return f"{hours}ч"
        else:
            return f"{hours}ч {minutes}м"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours == 0:
            return f"{days}д"
        else:
            return f"{days}д {hours}ч"


def format_number(number: Union[int, float]) -> str:
    """
    Форматирует число с разделителями тысяч
    
    Args:
        number: Число для форматирования
        
    Returns:
        Отформатированная строка
    """
    if isinstance(number, float):
        return f"{number:,.2f}".replace(",", " ")
    else:
        return f"{number:,}".replace(",", " ")


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Обрезает текст до указанной длины
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для обрезанного текста
        
    Returns:
        Обрезанный текст
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def clean_jql(jql: str) -> str:
    """
    Очищает и нормализует JQL запрос
    
    Args:
        jql: Исходный JQL запрос
        
    Returns:
        Очищенный JQL запрос
    """
    # Убираем лишние пробелы
    jql = re.sub(r'\s+', ' ', jql.strip())
    
    # Убираем лишние кавычки
    jql = re.sub(r'"{2,}', '"', jql)
    
    # Нормализуем операторы
    jql = re.sub(r'\s*=\s*', ' = ', jql)
    jql = re.sub(r'\s*!=\s*', ' != ', jql)
    jql = re.sub(r'\s*>\s*', ' > ', jql)
    jql = re.sub(r'\s*<\s*', ' < ', jql)
    jql = re.sub(r'\s*>=\s*', ' >= ', jql)
    jql = re.sub(r'\s*<=\s*', ' <= ', jql)
    
    # Нормализуем логические операторы
    jql = re.sub(r'\s+AND\s+', ' AND ', jql, flags=re.IGNORECASE)
    jql = re.sub(r'\s+OR\s+', ' OR ', jql, flags=re.IGNORECASE)
    jql = re.sub(r'\s+NOT\s+', ' NOT ', jql, flags=re.IGNORECASE)
    
    return jql


def validate_jql(jql: str) -> Dict[str, Any]:
    """
    Выполняет базовую валидацию JQL запроса
    
    Args:
        jql: JQL запрос для валидации
        
    Returns:
        Результат валидации
    """
    result = {
        "is_valid": True,
        "errors": [],
        "warnings": []
    }
    
    try:
        # Проверяем базовый синтаксис
        if not jql.strip():
            result["is_valid"] = False
            result["errors"].append("Пустой JQL запрос")
            return result
        
        # Проверяем парность скобок
        open_brackets = jql.count('(')
        close_brackets = jql.count(')')
        if open_brackets != close_brackets:
            result["is_valid"] = False
            result["errors"].append("Не совпадает количество открывающих и закрывающих скобок")
        
        # Проверяем парность кавычек
        quote_count = jql.count('"')
        if quote_count % 2 != 0:
            result["is_valid"] = False
            result["errors"].append("Не совпадает количество кавычек")
        
        # Проверяем наличие запрещенных символов
        forbidden_chars = ['<script', 'javascript:', 'eval(', 'alert(']
        for char in forbidden_chars:
            if char.lower() in jql.lower():
                result["is_valid"] = False
                result["errors"].append(f"Обнаружен потенциально опасный код: {char}")
        
        # Предупреждения
        if len(jql) > 1000:
            result["warnings"].append("Очень длинный JQL запрос")
        
        if 'ORDER BY' not in jql.upper():
            result["warnings"].append("Рекомендуется добавить сортировку (ORDER BY)")
    
    except Exception as e:
        result["is_valid"] = False
        result["errors"].append(f"Ошибка валидации: {str(e)}")
    
    return result


def generate_cache_key(*args: Any) -> str:
    """
    Генерирует ключ кеша на основе аргументов
    
    Args:
        *args: Аргументы для создания ключа
        
    Returns:
        Хеш строка для использования как ключ кеша
    """
    import hashlib
    import json
    
    # Сериализуем все аргументы
    serialized = []
    for arg in args:
        if isinstance(arg, (dict, list)):
            serialized.append(json.dumps(arg, sort_keys=True, ensure_ascii=False))
        else:
            serialized.append(str(arg))
    
    # Создаем хеш
    key_string = "|".join(serialized)
    return hashlib.md5(key_string.encode()).hexdigest()


def detect_chart_type(query: str, data: List[Dict]) -> str:
    """
    Автоматически определяет подходящий тип графика
    
    Args:
        query: Запрос пользователя
        data: Данные для визуализации
        
    Returns:
        Тип графика (bar, line, pie, table)
    """
    query_lower = query.lower()
    
    # Круговая диаграмма
    if any(word in query_lower for word in [
        'распределение', 'доля', 'процент', 'соотношение', 
        'диаграмма', 'круговая', 'pie'
    ]):
        return "pie"
    
    # Линейный график
    elif any(word in query_lower for word in [
        'динамика', 'тренд', 'изменение', 'время', 'временной',
        'за период', 'по дням', 'по месяцам', 'линейный', 'line'
    ]):
        return "line"
    
    # Таблица
    elif any(word in query_lower for word in [
        'список', 'таблица', 'показать', 'найти', 'какие',
        'table', 'детали', 'подробно'
    ]):
        return "table"
    
    # По умолчанию столбчатая диаграмма
    else:
        return "bar" 