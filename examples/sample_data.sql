-- Примеры данных для инициализации базы Ask Bot

-- Клиенты
INSERT INTO clients (name, jira_key, description, is_active) VALUES
('Иль-Де-Ботэ', 'IDB', 'Крупная IT-компания, разработка корпоративных решений', true),
('Бургер-Кинг', 'BK', 'Сеть ресторанов быстрого питания', true),
('Летуаль', 'LET', 'Сеть магазинов косметики и парфюмерии', true),
('Visiology', 'VIS', 'Платформа для аналитики и визуализации данных', true),
('Битрикс', 'BTX', 'Разработчик CRM и веб-решений', true);

-- Проекты
INSERT INTO projects (name, jira_key, description, client_id, is_active) VALUES
('Поддержка клиентов', 'SUP', 'Техническая поддержка и консультации', 1, true),
('Мобильное приложение', 'MOBILE', 'Разработка iOS и Android приложений', 2, true),
('Веб-платформа', 'WEB', 'Корпоративный сайт и личный кабинет', 3, true),
('Аналитический модуль', 'ANALYTICS', 'BI система для анализа продаж', 4, true),
('Интеграция CRM', 'CRM', 'Интеграция с внешними системами', 5, true);

-- Шаблоны запросов
INSERT INTO query_templates (name, description, template, category, chart_type, parameters, examples) VALUES
('Задачи по клиенту за период', 
 'Получение всех задач клиента за указанный период времени',
 'project = "{project}" AND created >= "{start_date}" AND created <= "{end_date}"',
 'analytics',
 'bar',
 '["project", "start_date", "end_date"]',
 '["project=IDB start_date=2024-01-01 end_date=2024-01-31"]'),

('Распределение задач по статусам',
 'Показывает количество задач в каждом статусе',
 'project = "{project}" AND created >= "{start_date}"',
 'analytics', 
 'pie',
 '["project", "start_date"]',
 '["project=SUP start_date=2024-01-01"]'),

('Задачи без назначенного исполнителя',
 'Находит все задачи без assignee',
 'project = "{project}" AND assignee is EMPTY AND status != "Done"',
 'search',
 'table',
 '["project"]',
 '["project=MOBILE"]'),

('Просроченные задачи',
 'Задачи с истекшим due date',
 'project = "{project}" AND duedate < now() AND status != "Done"',
 'search',
 'table', 
 '["project"]',
 '["project=WEB"]'),

('Статистика по исполнителям',
 'Количество задач по каждому исполнителю',
 'project = "{project}" AND assignee is not EMPTY AND created >= "{start_date}"',
 'analytics',
 'bar',
 '["project", "start_date"]',
 '["project=ANALYTICS start_date=2024-01-01"]');

-- База знаний
INSERT INTO knowledge_base (title, content, content_type, category, tags) VALUES
('JQL для поиска задач по клиенту',
 'Для поиска задач определенного клиента используйте: project = "PROJECT_KEY". Например: project = "IDB" найдет все задачи проекта Иль-Де-Ботэ.',
 'jql',
 'search',
 '["jql", "проект", "клиент"]'),

('Фильтрация по датам в JQL',
 'Для поиска задач за период используйте: created >= "2024-01-01" AND created <= "2024-01-31". Доступные поля: created, updated, resolved, duedate.',
 'jql', 
 'dates',
 '["jql", "даты", "период"]'),

('Поиск по статусам задач',
 'Основные статусы: "To Do", "In Progress", "Done", "Closed". Пример: status = "In Progress" OR status = "To Do"',
 'jql',
 'status', 
 '["статус", "прогресс"]'),

('Работа с worklog в Jira',
 'Для поиска задач с worklog используйте: worklogAuthor = "username" AND worklogDate >= "2024-01-01"',
 'jql',
 'worklog',
 '["worklog", "время", "списание"]'),

('Типы задач в Jira',
 'Основные типы: Bug (ошибка), Task (задача), Epic (эпик), Story (история). Используйте: issuetype = "Bug"',
 'jql',
 'issuetype',
 '["тип", "задача", "баг"]);

-- Примеры пользователей (для демонстрации)
INSERT INTO users (id, username, email, display_name, preferred_language, timezone) VALUES
('demo_user_1', 'ivan.petrov', 'ivan.petrov@company.com', 'Иван Петров', 'ru', 'Europe/Moscow'),
('demo_user_2', 'anna.sidorova', 'anna.sidorova@company.com', 'Анна Сидорова', 'ru', 'Europe/Moscow'),
('demo_user_3', 'alex.smith', 'alex.smith@company.com', 'Alex Smith', 'en', 'UTC'); 