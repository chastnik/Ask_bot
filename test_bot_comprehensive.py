#!/usr/bin/env python3
"""
Комплексный тест Ask Bot
Проверяет все типы запросов и команд бота

Запуск: python3 test_bot_comprehensive.py
Запуск с авторизацией: python3 test_bot_comprehensive.py --auth
Запуск с данными: python3 test_bot_comprehensive.py --login user --password pass
"""

import asyncio
import json
import time
import sys
import argparse
import getpass
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TestCase:
    """Класс для тестового случая"""
    category: str
    query: str
    expected_keywords: List[str]  # Ожидаемые ключевые слова в ответе
    should_not_contain: List[str] = None  # Что НЕ должно быть в ответе
    description: str = ""
    priority: str = "normal"  # low, normal, high, critical

class BotTester:
    """Класс для тестирования бота"""
    
    def __init__(self, with_auth: bool = False):
        self.test_user_id = "test_user_12345"
        self.results = []
        self.with_auth = with_auth
        self.auth_credentials = None
    
    def get_auth_credentials(self, login: str = None, password: str = None) -> Dict[str, str]:
        """Получает учетные данные для авторизации"""
        if login and password:
            return {"login": login, "password": password}
        
        print()
        print("🔐 АВТОРИЗАЦИЯ В JIRA ДЛЯ ПОЛНОГО ТЕСТИРОВАНИЯ")
        print("=" * 50)
        print("Для тестирования всех функций бота нужны учетные данные Jira.")
        print("Данные будут использованы только для тестирования и не сохраняются.")
        print()
        
        try:
            login = input("Логин Jira: ").strip()
            if not login:
                print("❌ Логин не может быть пустым")
                return None
            
            password = getpass.getpass("Пароль/токен Jira: ").strip()
            if not password:
                print("❌ Пароль не может быть пустым")
                return None
                
            return {"login": login, "password": password}
            
        except KeyboardInterrupt:
            print("\n❌ Авторизация отменена пользователем")
            return None
        except Exception as e:
            print(f"❌ Ошибка получения учетных данных: {e}")
            return None
    
    async def authorize_in_jira(self, credentials: Dict[str, str]) -> bool:
        """Авторизует тестового пользователя в Jira"""
        if not credentials:
            return False
            
        try:
            from app.services.message_processor import MessageProcessor
            
            processor = MessageProcessor()
            auth_command = f"авторизация {credentials['login']} {credentials['password']}"
            
            print(f"🔐 Авторизация в Jira как {credentials['login']}...")
            response = await processor.process_message(self.test_user_id, auth_command)
            
            if "Успешная авторизация" in response:
                print(f"✅ Авторизация успешна!")
                
                # Дополнительная проверка - тестируем статус
                print(f"🔍 Проверяем сохранение авторизации...")
                status_response = await processor.process_message(self.test_user_id, "статус")
                
                if "авторизован" in status_response.lower():
                    print(f"✅ Авторизация сохранена в кеше!")
                    self.auth_credentials = credentials
                    return True
                else:
                    print(f"❌ Авторизация не сохранилась в кеше: {status_response}")
                    return False
            else:
                print(f"❌ Ошибка авторизации: {response}")
                return False
                
        except Exception as e:
            print(f"❌ Исключение при авторизации: {e}")
            return False
        
    def get_test_cases(self) -> List[TestCase]:
        """Генерирует все тестовые случаи"""
        test_cases = []
        
        # ========================================
        # 1. КОМАНДЫ УПРАВЛЕНИЯ И ПОМОЩЬ
        # ========================================
        management_tests = [
            TestCase("управление", "помощь", ["Ask Bot", "команды", "примеры"], 
                    description="Команда помощи"),
            TestCase("управление", "help", ["Ask Bot", "команды"], 
                    description="Команда помощи на английском"),
            TestCase("управление", "статус", ["авторизован", "Jira", "svchashin"], 
                    description="Проверка статуса авторизации"),
            TestCase("управление", "status", ["авторизован", "Jira", "svchashin"], 
                    description="Проверка статуса на английском"),
            TestCase("управление", "проекты", ["проект"], 
                    description="Список доступных проектов"),
            TestCase("управление", "projects", ["проект"], 
                    description="Список проектов на английском"),
        ]
        
        # ========================================
        # 2. УПРАВЛЕНИЕ КЭШЕМ И МАППИНГАМИ
        # ========================================
        cache_tests = [
            TestCase("кэш", "кеш статистика", ["кеш", "статистика"], 
                    description="Статистика кэша"),
            TestCase("кэш", "кеш очистить", ["кеш очищен"], 
                    description="Очистка кэша"),
            TestCase("кэш", "маппинги", ["маппинг", "Клиенты"], 
                    description="Показать все маппинги"),
            TestCase("кэш", "mappings", ["маппинг"], 
                    description="Маппинги на английском"),
            TestCase("кэш", "обновить", ["справочник", "обновл"], 
                    description="Обновление справочников Jira"),
            TestCase("кэш", "refresh", ["справочник"], 
                    description="Обновление на английском"),
        ]
        
        # ========================================
        # 3. КОМАНДЫ ОБУЧЕНИЯ
        # ========================================
        learning_tests = [
            TestCase("обучение", 'научи клиент "Тестовый Клиент" проект "TEST"', 
                    ["Отлично", "знаю", "соответствует"], 
                    description="Обучение соответствию клиент->проект"),
            TestCase("обучение", 'научи пользователь "Иван Иванов" username "iivanov"', 
                    ["Отлично", "знаю", "соответствует"], 
                    description="Обучение соответствию имя->username"),
            TestCase("обучение", "научи клиент Акме проект ACME", 
                    ["Отлично", "знаю"], 
                    description="Обучение без кавычек"),
            TestCase("обучение", "научи", ["Команды обучения", "научи клиент"], 
                    description="Помощь по команде научи"),
        ]
        
        # ========================================
        # 4. ПОИСК И ФИЛЬТРАЦИЯ ЗАДАЧ
        # ========================================
        search_tests = [
            TestCase("поиск", "покажи мои открытые задачи", 
                    ["задач", "открыт"], ["ошибка"],
                    description="Мои открытые задачи"),
            TestCase("поиск", "найди все задачи в проекте ABC", 
                    ["задач", "проект"], ["ошибка"],
                    description="Задачи в конкретном проекте"),
            TestCase("поиск", "покажи закрытые задачи за последний месяц", 
                    ["задач", "закрыт"], ["ошибка"],
                    description="Закрытые задачи за период"),
            TestCase("поиск", "найди задачи без исполнителя", 
                    ["задач"], ["ошибка"],
                    description="Неназначенные задачи"),
            TestCase("поиск", "покажи просроченные задачи", 
                    ["задач"], ["ошибка"],
                    description="Просроченные задачи"),
            TestCase("поиск", "найди баги в высоким приоритетом", 
                    ["задач"], ["ошибка"],
                    description="Баги с высоким приоритетом"),
            TestCase("поиск", "покажи задачи на исполнителе Иван Петров", 
                    ["задач", "исполнител"], ["ошибка"],
                    description="Задачи конкретного исполнителя"),
            TestCase("поиск", "найди Epic-и в проекте XYZ", 
                    ["задач", "Epic"], ["ошибка"],
                    description="Поиск по типу задач"),
        ]
        
        # ========================================
        # 5. ТЕКСТОВЫЙ ПОИСК ПО СОДЕРЖИМОМУ
        # ========================================
        text_search_tests = [
            TestCase("текстовый поиск", "найди задачи про Power BI", 
                    ["задач", "Power BI"], ["ошибка"],
                    description="Поиск по ключевым словам", priority="high"),
            TestCase("текстовый поиск", "найди всё про Qlik Sense", 
                    ["задач", "Qlik Sense"], ["ошибка"],
                    description="Поиск всего по ключевому слову", priority="high"),
            TestCase("текстовый поиск", "поиск упоминаний Python", 
                    ["задач", "Python"], ["ошибка"],
                    description="Поиск упоминаний технологии"),
            TestCase("текстовый поиск", "найди задачи связанные с API", 
                    ["задач", "API"], ["ошибка"],
                    description="Поиск по техническим терминам"),
            TestCase("текстовый поиск", "покажи все задачи про базу данных", 
                    ["задач"], ["ошибка"],
                    description="Поиск по сложным фразам"),
            TestCase("текстовый поиск", "найди задачи с ошибкой авторизации", 
                    ["задач"], ["ошибка"],
                    description="Поиск по описанию проблем"),
        ]
        
        # ========================================
        # 6. АНАЛИТИКА И СТАТИСТИКА
        # ========================================
        analytics_tests = [
            TestCase("аналитика", "сколько открытых задач в проекте ABC?", 
                    ["задач", "открыт"], ["ошибка"],
                    description="Подсчет открытых задач"),
            TestCase("аналитика", "сколько багов закрыли в этом месяце?", 
                    ["баг", "закрыт"], ["ошибка"],
                    description="Статистика по багам за период"),
            TestCase("аналитика", "статистика по исполнителям в проекте XYZ", 
                    ["статистика", "исполнител"], ["ошибка"],
                    description="Статистика по исполнителям"),
            TestCase("аналитика", "сколько задач создано за последнюю неделю?", 
                    ["задач", "создан"], ["ошибка"],
                    description="Статистика по созданным задачам"),
            TestCase("аналитика", "средний возраст открытых задач", 
                    ["задач", "возраст"], ["ошибка"],
                    description="Возраст задач"),
            TestCase("аналитика", "топ 5 исполнителей по количеству задач", 
                    ["исполнител", "топ"], ["ошибка"],
                    description="Рейтинг исполнителей"),
        ]
        
        # ========================================
        # 7. ВРЕМЕННЫЕ ФИЛЬТРЫ
        # ========================================
        time_filter_tests = [
            TestCase("время", "задачи созданные сегодня", 
                    ["задач"], ["ошибка"],
                    description="Задачи за сегодня"),
            TestCase("время", "задачи за вчера", 
                    ["задач"], ["ошибка"],
                    description="Задачи за вчера"),
            TestCase("время", "задачи за эту неделю", 
                    ["задач"], ["ошибка"],
                    description="Задачи за текущую неделю"),
            TestCase("время", "задачи за прошлую неделю", 
                    ["задач"], ["ошибка"],
                    description="Задачи за прошлую неделю"),
            TestCase("время", "задачи за этот месяц", 
                    ["задач"], ["ошибка"],
                    description="Задачи за текущий месяц"),
            TestCase("время", "задачи созданные в июле", 
                    ["задач"], ["ошибка"],
                    description="Задачи за конкретный месяц"),
            TestCase("время", "задачи за 2024 год", 
                    ["задач"], ["ошибка"],
                    description="Задачи за год"),
        ]
        
        # ========================================
        # 8. ГРАФИКИ И ВИЗУАЛИЗАЦИЯ
        # ========================================
        chart_tests = [
            TestCase("графики", "покажи статистику по статусам как график", 
                    ["график", "статус"], ["ошибка"],
                    description="График по статусам"),
            TestCase("графики", "задачи по исполнителям покажи как график", 
                    ["график", "исполнител"], ["ошибка"],
                    description="График по исполнителям"),
            TestCase("графики", "динамика создания задач за месяц как график", 
                    ["график", "динамика"], ["ошибка"],
                    description="График динамики"),
            TestCase("графики", "распределение типов задач покажи как круговую диаграмму", 
                    ["график", "тип"], ["ошибка"],
                    description="Круговая диаграмма типов"),
        ]
        
        # ========================================
        # 9. КОМБИНИРОВАННЫЕ ЗАПРОСЫ
        # ========================================
        complex_tests = [
            TestCase("сложные", "сколько задач закрыли по клиенту Филипс в июле?", 
                    ["задач", "закрыт", "июль"], ["ошибка"],
                    description="Задачи клиента за период", priority="high"),
            TestCase("сложные", "открытые баги высокого приоритета в проекте ABC", 
                    ["баг", "открыт", "приоритет"], ["ошибка"],
                    description="Сложная фильтрация"),
            TestCase("сложные", "задачи без исполнителя старше 30 дней", 
                    ["задач", "исполнител", "дней"], ["ошибка"],
                    description="Комбинированный фильтр по времени и исполнителю"),
            TestCase("сложные", "баги созданные в этом месяце исполнителем Иван", 
                    ["баг", "создан", "месяц"], ["ошибка"],
                    description="Фильтр по типу, времени и исполнителю"),
        ]
        
        # ========================================
        # 10. EDGE CASES И ОШИБКИ
        # ========================================
        edge_case_tests = [
            TestCase("граничные", "", 
                    [], [],
                    description="Пустое сообщение"),
            TestCase("граничные", "   ", 
                    [], [],
                    description="Только пробелы"),
            TestCase("граничные", "несуществующая команда абвгд", 
                    ["задач"], ["ошибка"],  # Должно обработаться как Jira запрос
                    description="Неизвестная команда"),
            TestCase("граничные", "задачи в несуществующем проекте ZZZZZZ", 
                    [], [],
                    description="Несуществующий проект"),
            TestCase("граничные", "очень длинный запрос " + "слово " * 100, 
                    [], [],
                    description="Очень длинный запрос"),
        ]
        
        # ========================================
        # 11. РАЗЛИЧНЫЕ ФОРМУЛИРОВКИ ОДНОГО ЗАПРОСА
        # ========================================
        variation_tests = [
            TestCase("вариации", "покажи мои задачи", 
                    ["задач"], ["ошибка"],
                    description="Вариация 1: мои задачи"),
            TestCase("вариации", "дай мне список моих задач", 
                    ["задач"], ["ошибка"],
                    description="Вариация 2: список задач"),
            TestCase("вариации", "какие у меня есть задачи", 
                    ["задач"], ["ошибка"],
                    description="Вариация 3: вопросная форма"),
            TestCase("вариации", "хочу посмотреть свои задачи", 
                    ["задач"], ["ошибка"],
                    description="Вариация 4: желание"),
            TestCase("вариации", "мне нужны мои активные задачи", 
                    ["задач"], ["ошибка"],
                    description="Вариация 5: потребность"),
        ]
        
        # ========================================
        # 12. РАЗНЫЕ ЯЗЫКИ И СТИЛИ
        # ========================================
        language_tests = [
            TestCase("язык", "show my open tasks", 
                    ["задач"], [],
                    description="Английский запрос"),
            TestCase("язык", "ПОКАЖИ ВСЕ ЗАДАЧИ", 
                    ["задач"], ["ошибка"],
                    description="Заглавные буквы"),
            TestCase("язык", "покажи, пожалуйста, мои задачи", 
                    ["задач"], ["ошибка"],
                    description="Вежливая форма"),
            TestCase("язык", "задачи плз", 
                    ["задач"], ["ошибка"],
                    description="Сокращенная форма"),
        ]
        
        # Собираем все тесты
        all_tests = (management_tests + cache_tests + learning_tests + 
                    search_tests + text_search_tests + analytics_tests + 
                    time_filter_tests + chart_tests + complex_tests + 
                    edge_case_tests + variation_tests + language_tests)
        
        return all_tests
    
    async def test_query(self, test_case: TestCase) -> Dict[str, Any]:
        """Тестирует один запрос"""
        start_time = time.time()
        
        try:
            # Используем прямой импорт MessageProcessor
            from app.services.message_processor import MessageProcessor
            
            processor = MessageProcessor()
            response = await processor.process_message(self.test_user_id, test_case.query)
            
            # Специальная обработка для ошибок авторизации
            if "Необходимо авторизоваться в Jira" in response and self.auth_credentials:
                # Попытка повторной авторизации если данные есть
                print(f"⚠️  Авторизация потеряна для теста '{test_case.query[:30]}...', попытка восстановления...")
                auth_success = await self.authorize_in_jira(self.auth_credentials)
                
                if auth_success:
                    # Повторный запуск теста после восстановления авторизации
                    response = await processor.process_message(self.test_user_id, test_case.query)
                    print(f"🔄 Тест перезапущен после восстановления авторизации")
                else:
                    print(f"❌ Не удалось восстановить авторизацию")
            
            response_time = (time.time() - start_time) * 1000
            
            # Анализируем ответ
            success = True
            error_msg = ""
            
            # Проверяем наличие ожидаемых ключевых слов
            if test_case.expected_keywords:
                for keyword in test_case.expected_keywords:
                    if keyword.lower() not in response.lower():
                        success = False
                        error_msg += f"Отсутствует ключевое слово: '{keyword}'. "
            
            # Проверяем отсутствие нежелательных слов
            if test_case.should_not_contain:
                for keyword in test_case.should_not_contain:
                    if keyword.lower() in response.lower():
                        success = False
                        error_msg += f"Найдено нежелательное слово: '{keyword}'. "
            
            result = {
                "test_case": test_case,
                "response": response,
                "response_time_ms": response_time,
                "success": success,
                "error_msg": error_msg.strip(),
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            return {
                "test_case": test_case,
                "response": f"ИСКЛЮЧЕНИЕ: {str(e)}",
                "response_time_ms": (time.time() - start_time) * 1000,
                "success": False,
                "error_msg": f"Исключение при тестировании: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Запускает все тесты"""
        test_cases = self.get_test_cases()
        print(f"🧪 Запуск {len(test_cases)} тестов...")
        print()
        
        results = []
        categories = {}
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"[{i:3d}/{len(test_cases)}] {test_case.category:15} | {test_case.query[:50]:<50}")
            
            result = await self.test_query(test_case)
            results.append(result)
            
            # Группируем по категориям
            if test_case.category not in categories:
                categories[test_case.category] = {"total": 0, "passed": 0, "failed": 0}
            
            categories[test_case.category]["total"] += 1
            if result["success"]:
                categories[test_case.category]["passed"] += 1
                print(f"                   ✅ PASSED ({result['response_time_ms']:.0f}ms)")
            else:
                categories[test_case.category]["failed"] += 1
                print(f"                   ❌ FAILED: {result['error_msg']}")
                if len(result["response"]) > 100:
                    print(f"                      Ответ: {result['response'][:100]}...")
                else:
                    print(f"                      Ответ: {result['response']}")
            print()
        
        # Подсчитываем общую статистику
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r["success"])
        failed_tests = total_tests - passed_tests
        
        average_response_time = sum(r["response_time_ms"] for r in results) / len(results)
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": (passed_tests / total_tests) * 100,
            "average_response_time_ms": average_response_time,
            "categories": categories,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]):
        """Выводит итоговую статистику"""
        print("=" * 80)
        print("🎯 ИТОГИ ТЕСТИРОВАНИЯ")
        print("=" * 80)
        print()
        
        # Показываем статус авторизации
        if self.auth_credentials:
            print(f"🔐 Авторизация: ✅ Выполнена как {self.auth_credentials['login']}")
        else:
            print(f"🔐 Авторизация: ❌ Не выполнена (тестируются только базовые функции)")
        print()
        
        print(f"📊 Общая статистика:")
        print(f"   • Всего тестов: {summary['total_tests']}")
        print(f"   • Прошли: {summary['passed_tests']} ✅")
        print(f"   • Провалились: {summary['failed_tests']} ❌")
        print(f"   • Успешность: {summary['success_rate']:.1f}%")
        print(f"   • Среднее время ответа: {summary['average_response_time_ms']:.0f}ms")
        print()
        
        # Анализируем результаты с учетом авторизации
        auth_required_fails = 0
        real_fails = 0
        
        for result in summary['results']:
            if not result['success']:
                response = result['response']
                if "Необходимо авторизоваться в Jira" in response:
                    auth_required_fails += 1
                else:
                    real_fails += 1
        
        if not self.auth_credentials and auth_required_fails > 0:
            print(f"🔍 АНАЛИЗ РЕЗУЛЬТАТОВ:")
            print(f"   • Реальные ошибки: {real_fails}")
            print(f"   • Требуют авторизации: {auth_required_fails}")
            print(f"   • Реальная успешность: {((summary['passed_tests'] + auth_required_fails) / summary['total_tests'] * 100):.1f}%")
            print()
        
        print(f"📈 Статистика по категориям:")
        for category, stats in summary['categories'].items():
            success_rate = (stats['passed'] / stats['total']) * 100
            print(f"   • {category:20} {stats['passed']:2d}/{stats['total']:2d} ({success_rate:5.1f}%)")
        print()
        
        # Показываем неуспешные тесты
        failed_tests = [r for r in summary['results'] if not r['success']]
        if failed_tests:
            print(f"❌ Провалившиеся тесты ({len(failed_tests)}):")
            for result in failed_tests:
                tc = result['test_case']
                print(f"   • [{tc.category}] {tc.query[:60]}")
                print(f"     Ошибка: {result['error_msg']}")
                if tc.priority == "critical":
                    print("     ⚠️  КРИТИЧЕСКИЙ ТЕСТ!")
                print()
        
        # Показываем медленные тесты
        slow_tests = [r for r in summary['results'] if r['response_time_ms'] > 5000]
        if slow_tests:
            print(f"🐌 Медленные тесты (>5с, {len(slow_tests)} шт.):")
            for result in sorted(slow_tests, key=lambda x: x['response_time_ms'], reverse=True):
                tc = result['test_case']
                print(f"   • {result['response_time_ms']:.0f}ms | {tc.query[:50]}")
            print()

async def main():
    """Главная функция теста"""
    # Парсим аргументы командной строки
    parser = argparse.ArgumentParser(description='Комплексное тестирование Ask Bot')
    parser.add_argument('--auth', action='store_true', 
                       help='Запросить учетные данные для авторизации в Jira')
    parser.add_argument('--login', type=str, 
                       help='Логин для Jira (используется с --password)')
    parser.add_argument('--password', type=str, 
                       help='Пароль/токен для Jira (используется с --login)')
    parser.add_argument('--no-auth', action='store_true',
                       help='Пропустить авторизацию и тестировать только базовые функции')
    
    args = parser.parse_args()
    
    print("🚀 Ask Bot - Комплексное тестирование")
    print("=" * 50)
    print()
    
    # Определяем нужна ли авторизация
    with_auth = args.auth or (args.login and args.password)
    
    if not args.no_auth and not with_auth:
        print("💡 ОПЦИИ ТЕСТИРОВАНИЯ:")
        print("   1. Базовое тестирование (без Jira) - нажмите ENTER")
        print("   2. Полное тестирование (с Jira) - введите 'auth'")
        print()
        
        choice = input("Выберите режим [ENTER/auth]: ").strip().lower()
        with_auth = choice in ['auth', 'a', 'да', 'yes', 'y']
    
    tester = BotTester(with_auth=with_auth)
    
    # Авторизация если нужна
    if with_auth:
        credentials = tester.get_auth_credentials(args.login, args.password)
        if credentials:
            auth_success = await tester.authorize_in_jira(credentials)
            if not auth_success:
                print()
                print("⚠️  Продолжить тестирование без авторизации? [y/N]: ", end="")
                continue_without_auth = input().strip().lower()
                if continue_without_auth not in ['y', 'yes', 'да']:
                    print("❌ Тестирование отменено")
                    return 1
                print()
        else:
            print("❌ Не удалось получить учетные данные")
            return 1
    
    summary = await tester.run_all_tests()
    tester.print_summary(summary)
    
    # Сохраняем результаты в файл
    with open(f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    
    print("💾 Результаты сохранены в test_results_YYYYMMDD_HHMMSS.json")
    
    # Возвращаем код выхода
    if summary['failed_tests'] == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        return 0
    else:
        print(f"\n⚠️  {summary['failed_tests']} ТЕСТОВ ПРОВАЛИЛИСЬ")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
