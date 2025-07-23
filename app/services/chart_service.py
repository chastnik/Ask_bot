"""
Сервис для генерации графиков с Plotly
"""
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.io as pio
from loguru import logger

from app.config import settings


class ChartGenerationError(Exception):
    """Исключение для ошибок генерации графиков"""
    pass


class ChartService:
    """Сервис для генерации графиков с помощью Plotly"""
    
    def __init__(self):
        self.chart_save_path = settings.chart_save_path
        self.chart_url_prefix = settings.chart_url_prefix
        
        # Создаем директорию для графиков если её нет
        os.makedirs(self.chart_save_path, exist_ok=True)
        
        # Настройки Plotly
        pio.kaleido.scope.mathjax = None  # Отключаем MathJax для ускорения
        
        # Цветовые схемы
        self.color_schemes = {
            "default": px.colors.qualitative.Set3,
            "professional": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", 
                           "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"],
            "warm": px.colors.qualitative.Warm,
            "cool": px.colors.qualitative.Cool,
            "jira": ["#0052CC", "#36B37E", "#FFAB00", "#FF5630", "#6554C0"]
        }
    
    def _generate_filename(self, chart_type: str, extension: str = "png") -> str:
        """
        Генерирует уникальное имя файла для графика
        
        Args:
            chart_type: Тип графика
            extension: Расширение файла
            
        Returns:
            Имя файла
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{chart_type}_{timestamp}_{unique_id}.{extension}"
    
    def _prepare_data(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Подготавливает данные для создания графика
        
        Args:
            data: Список словарей с данными
            
        Returns:
            DataFrame с обработанными данными
        """
        if not data:
            raise ChartGenerationError("Нет данных для создания графика")
        
        df = pd.DataFrame(data)
        
        # Обработка дат
        for col in df.columns:
            if df[col].dtype == 'object':
                # Попытка конвертации в datetime
                try:
                    df[col] = pd.to_datetime(df[col])
                except (ValueError, TypeError):
                    pass
        
        return df
    
    async def create_bar_chart(self, data: List[Dict[str, Any]], 
                             title: str, x_axis: str, y_axis: str,
                             config: Optional[Dict[str, Any]] = None) -> str:
        """
        Создает столбчатую диаграмму
        
        Args:
            data: Данные для графика
            title: Заголовок
            x_axis: Поле для оси X
            y_axis: Поле для оси Y
            config: Дополнительная конфигурация
            
        Returns:
            URL созданного графика
        """
        try:
            df = self._prepare_data(data)
            config = config or {}
            
            # Создаем график
            fig = px.bar(
                df, 
                x=x_axis, 
                y=y_axis,
                title=title,
                color_discrete_sequence=self.color_schemes.get(
                    config.get("color_scheme", "jira")
                )
            )
            
            # Настройки оформления
            fig.update_layout(
                title_font_size=16,
                title_x=0.5,  # Центрируем заголовок
                xaxis_title=config.get("x_title", x_axis.title()),
                yaxis_title=config.get("y_title", y_axis.title()),
                showlegend=config.get("show_legend", False),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Arial, sans-serif", size=12),
                height=config.get("height", 500),
                width=config.get("width", 800)
            )
            
            # Поворот подписей оси X если они длинные
            max_label_len = max(len(str(x)) for x in df[x_axis])
            if max_label_len > 10:
                fig.update_xaxes(tickangle=45)
            
            # Добавляем значения на столбцы
            if config.get("show_values", True):
                fig.update_traces(texttemplate='%{y}', textposition='outside')
            
            # Сохраняем график
            filename = self._generate_filename("bar")
            filepath = os.path.join(self.chart_save_path, filename)
            
            fig.write_image(filepath, format="png", width=800, height=500)
            
            chart_url = f"{self.chart_url_prefix}{filename}"
            logger.info(f"Создан столбчатый график: {chart_url}")
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Ошибка создания столбчатого графика: {e}")
            raise ChartGenerationError(f"Не удалось создать столбчатый график: {e}")
    
    async def create_line_chart(self, data: List[Dict[str, Any]], 
                              title: str, x_axis: str, y_axis: str,
                              config: Optional[Dict[str, Any]] = None) -> str:
        """
        Создает линейную диаграмму
        
        Args:
            data: Данные для графика
            title: Заголовок
            x_axis: Поле для оси X
            y_axis: Поле для оси Y
            config: Дополнительная конфигурация
            
        Returns:
            URL созданного графика
        """
        try:
            df = self._prepare_data(data)
            config = config or {}
            
            # Сортируем по X для правильного отображения линии
            df = df.sort_values(x_axis)
            
            # Группировка по категориям если указана
            color_field = config.get("color_by")
            
            fig = px.line(
                df, 
                x=x_axis, 
                y=y_axis,
                color=color_field,
                title=title,
                color_discrete_sequence=self.color_schemes.get(
                    config.get("color_scheme", "jira")
                )
            )
            
            # Настройки оформления
            fig.update_layout(
                title_font_size=16,
                title_x=0.5,
                xaxis_title=config.get("x_title", x_axis.title()),
                yaxis_title=config.get("y_title", y_axis.title()),
                showlegend=bool(color_field),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Arial, sans-serif", size=12),
                height=config.get("height", 500),
                width=config.get("width", 800)
            )
            
            # Добавляем маркеры на линию
            fig.update_traces(mode='lines+markers', marker_size=6)
            
            # Настройки сетки
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            
            # Сохраняем график
            filename = self._generate_filename("line")
            filepath = os.path.join(self.chart_save_path, filename)
            
            fig.write_image(filepath, format="png", width=800, height=500)
            
            chart_url = f"{self.chart_url_prefix}{filename}"
            logger.info(f"Создан линейный график: {chart_url}")
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Ошибка создания линейного графика: {e}")
            raise ChartGenerationError(f"Не удалось создать линейный график: {e}")
    
    async def create_pie_chart(self, data: List[Dict[str, Any]], 
                             title: str, values_field: str, names_field: str,
                             config: Optional[Dict[str, Any]] = None) -> str:
        """
        Создает круговую диаграмму
        
        Args:
            data: Данные для графика
            title: Заголовок
            values_field: Поле со значениями
            names_field: Поле с названиями
            config: Дополнительная конфигурация
            
        Returns:
            URL созданного графика
        """
        try:
            df = self._prepare_data(data)
            config = config or {}
            
            fig = px.pie(
                df, 
                values=values_field, 
                names=names_field,
                title=title,
                color_discrete_sequence=self.color_schemes.get(
                    config.get("color_scheme", "jira")
                )
            )
            
            # Настройки оформления
            fig.update_layout(
                title_font_size=16,
                title_x=0.5,
                showlegend=True,
                font=dict(family="Arial, sans-serif", size=12),
                height=config.get("height", 500),
                width=config.get("width", 800)
            )
            
            # Настройки подписей
            fig.update_traces(
                textposition='inside', 
                textinfo='percent+label',
                textfont_size=10,
                hovertemplate='<b>%{label}</b><br>Значение: %{value}<br>Процент: %{percent}<extra></extra>'
            )
            
            # Сохраняем график
            filename = self._generate_filename("pie")
            filepath = os.path.join(self.chart_save_path, filename)
            
            fig.write_image(filepath, format="png", width=800, height=500)
            
            chart_url = f"{self.chart_url_prefix}{filename}"
            logger.info(f"Создана круговая диаграмма: {chart_url}")
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Ошибка создания круговой диаграммы: {e}")
            raise ChartGenerationError(f"Не удалось создать круговую диаграмму: {e}")
    
    async def create_scatter_chart(self, data: List[Dict[str, Any]], 
                                 title: str, x_axis: str, y_axis: str,
                                 config: Optional[Dict[str, Any]] = None) -> str:
        """
        Создает точечную диаграмму
        
        Args:
            data: Данные для графика
            title: Заголовок
            x_axis: Поле для оси X
            y_axis: Поле для оси Y
            config: Дополнительная конфигурация
            
        Returns:
            URL созданного графика
        """
        try:
            df = self._prepare_data(data)
            config = config or {}
            
            # Дополнительные поля для группировки и размера
            color_field = config.get("color_by")
            size_field = config.get("size_by")
            
            fig = px.scatter(
                df, 
                x=x_axis, 
                y=y_axis,
                color=color_field,
                size=size_field,
                title=title,
                color_discrete_sequence=self.color_schemes.get(
                    config.get("color_scheme", "jira")
                )
            )
            
            # Настройки оформления
            fig.update_layout(
                title_font_size=16,
                title_x=0.5,
                xaxis_title=config.get("x_title", x_axis.title()),
                yaxis_title=config.get("y_title", y_axis.title()),
                showlegend=bool(color_field),
                plot_bgcolor="white",
                paper_bgcolor="white",
                font=dict(family="Arial, sans-serif", size=12),
                height=config.get("height", 500),
                width=config.get("width", 800)
            )
            
            # Настройки сетки
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
            
            # Сохраняем график
            filename = self._generate_filename("scatter")
            filepath = os.path.join(self.chart_save_path, filename)
            
            fig.write_image(filepath, format="png", width=800, height=500)
            
            chart_url = f"{self.chart_url_prefix}{filename}"
            logger.info(f"Создана точечная диаграмма: {chart_url}")
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Ошибка создания точечной диаграммы: {e}")
            raise ChartGenerationError(f"Не удалось создать точечную диаграмму: {e}")
    
    async def create_table_chart(self, data: List[Dict[str, Any]], 
                               title: str, columns: Optional[List[str]] = None,
                               config: Optional[Dict[str, Any]] = None) -> str:
        """
        Создает таблицу в виде изображения
        
        Args:
            data: Данные для таблицы
            title: Заголовок
            columns: Список колонок для отображения
            config: Дополнительная конфигурация
            
        Returns:
            URL созданной таблицы
        """
        try:
            df = self._prepare_data(data)
            config = config or {}
            
            # Выбираем колонки
            if columns:
                available_cols = [col for col in columns if col in df.columns]
                if available_cols:
                    df = df[available_cols]
            
            # Ограничиваем количество строк
            max_rows = config.get("max_rows", 20)
            if len(df) > max_rows:
                df = df.head(max_rows)
            
            # Форматируем данные для таблицы
            table_data = []
            headers = list(df.columns)
            
            for _, row in df.iterrows():
                formatted_row = []
                for col in headers:
                    value = row[col]
                    if pd.isna(value):
                        formatted_row.append("-")
                    elif isinstance(value, datetime):
                        formatted_row.append(value.strftime("%Y-%m-%d"))
                    elif isinstance(value, (int, float)):
                        formatted_row.append(str(value))
                    else:
                        formatted_row.append(str(value)[:50])  # Ограничиваем длину
                table_data.append(formatted_row)
            
            # Создаем таблицу
            fig = go.Figure(data=[go.Table(
                header=dict(
                    values=headers,
                    fill_color='#0052CC',
                    font=dict(color='white', size=12),
                    align="center",
                    height=40
                ),
                cells=dict(
                    values=list(zip(*table_data)) if table_data else [[] for _ in headers],
                    fill_color=[['white', '#f8f9fa'] * len(table_data)],
                    font=dict(color='black', size=11),
                    align="left",
                    height=35
                )
            )])
            
            fig.update_layout(
                title=title,
                title_font_size=16,
                title_x=0.5,
                height=min(600, 150 + len(table_data) * 35),
                width=config.get("width", 1000),
                margin=dict(l=20, r=20, t=60, b=20)
            )
            
            # Сохраняем таблицу
            filename = self._generate_filename("table")
            filepath = os.path.join(self.chart_save_path, filename)
            
            fig.write_image(filepath, format="png", width=1000, height=fig.layout.height)
            
            chart_url = f"{self.chart_url_prefix}{filename}"
            logger.info(f"Создана таблица: {chart_url}")
            
            return chart_url
            
        except Exception as e:
            logger.error(f"Ошибка создания таблицы: {e}")
            raise ChartGenerationError(f"Не удалось создать таблицу: {e}")
    
    async def create_worklog_chart(self, worklogs_data: List[Dict[str, Any]], 
                                 chart_type: str = "bar") -> str:
        """
        Создает специализированный график для worklogs
        
        Args:
            worklogs_data: Данные о списании времени
            chart_type: Тип графика (bar, line, pie)
            
        Returns:
            URL созданного графика
        """
        try:
            if not worklogs_data:
                raise ChartGenerationError("Нет данных о списании времени")
            
            # Преобразуем время из секунд в часы
            for item in worklogs_data:
                if "time_seconds" in item:
                    item["time_hours"] = round(item["time_seconds"] / 3600, 1)
            
            title = "Списание времени по сотрудникам"
            
            if chart_type == "pie":
                return await self.create_pie_chart(
                    data=worklogs_data,
                    title=title,
                    values_field="time_hours",
                    names_field="author",
                    config={"color_scheme": "jira"}
                )
            elif chart_type == "line":
                return await self.create_line_chart(
                    data=worklogs_data,
                    title=title,
                    x_axis="date",
                    y_axis="time_hours",
                    config={
                        "color_scheme": "jira",
                        "y_title": "Часы"
                    }
                )
            else:  # bar chart
                return await self.create_bar_chart(
                    data=worklogs_data,
                    title=title,
                    x_axis="author",
                    y_axis="time_hours",
                    config={
                        "color_scheme": "jira",
                        "y_title": "Часы",
                        "show_values": True
                    }
                )
                
        except Exception as e:
            logger.error(f"Ошибка создания графика worklogs: {e}")
            raise ChartGenerationError(f"Не удалось создать график worklogs: {e}")
    
    async def create_issues_by_status_chart(self, issues_data: List[Dict[str, Any]]) -> str:
        """
        Создает график распределения задач по статусам
        
        Args:
            issues_data: Данные о задачах
            
        Returns:
            URL созданного графика
        """
        try:
            # Группируем по статусам
            status_counts = {}
            for issue in issues_data:
                status = issue.get("status", "Unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            chart_data = [
                {"status": status, "count": count}
                for status, count in status_counts.items()
            ]
            
            return await self.create_pie_chart(
                data=chart_data,
                title="Распределение задач по статусам",
                values_field="count",
                names_field="status",
                config={"color_scheme": "jira"}
            )
            
        except Exception as e:
            logger.error(f"Ошибка создания графика по статусам: {e}")
            raise ChartGenerationError(f"Не удалось создать график по статусам: {e}")
    
    async def create_issues_by_type_chart(self, issues_data: List[Dict[str, Any]]) -> str:
        """
        Создает график распределения задач по типам
        
        Args:
            issues_data: Данные о задачах
            
        Returns:
            URL созданного графика
        """
        try:
            # Группируем по типам
            type_counts = {}
            for issue in issues_data:
                issue_type = issue.get("issue_type", "Unknown")
                type_counts[issue_type] = type_counts.get(issue_type, 0) + 1
            
            chart_data = [
                {"type": issue_type, "count": count}
                for issue_type, count in type_counts.items()
            ]
            
            return await self.create_pie_chart(
                data=chart_data,
                title="Распределение задач по типам",
                values_field="count",
                names_field="type",
                config={"color_scheme": "jira"}
            )
            
        except Exception as e:
            logger.error(f"Ошибка создания графика по типам: {e}")
            raise ChartGenerationError(f"Не удалось создать график по типам: {e}")
    
    async def cleanup_old_charts(self, days_old: int = 7) -> int:
        """
        Удаляет старые графики
        
        Args:
            days_old: Возраст файлов в днях для удаления
            
        Returns:
            Количество удаленных файлов
        """
        try:
            import time
            current_time = time.time()
            deleted_count = 0
            
            for filename in os.listdir(self.chart_save_path):
                if filename.endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    filepath = os.path.join(self.chart_save_path, filename)
                    file_age = current_time - os.path.getctime(filepath)
                    
                    if file_age > (days_old * 24 * 3600):  # Конвертируем дни в секунды
                        os.remove(filepath)
                        deleted_count += 1
                        
            logger.info(f"Удалено старых графиков: {deleted_count}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых графиков: {e}")
            return 0


# Глобальный экземпляр сервиса
chart_service = ChartService() 