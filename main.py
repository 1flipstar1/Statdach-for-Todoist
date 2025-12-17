import sys
import requests
import json
import os
from datetime import datetime, timedelta, timezone
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
from matplotlib import font_manager
import matplotlib as mpl
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QFontDatabase
from data import PROJECT_ID, API_TOKEN


# ============ НАСТРОЙКИ ============
UPDATE_INTERVAL = 15000

CUSTOM_FONT_PATH = "fonts/MyFont.ttf"
USE_CUSTOM_FONT = False
DEFAULT_FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10

MONTHLY_GOAL = 100
CACHE_FILE = "todoist_cache.json"
# ===================================


def setup_custom_font(font_path=None):
    """Настройка кастомного шрифта для PyQt6 и Matplotlib"""
    if font_path and USE_CUSTOM_FONT:
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            
            if font_id < 0:
                print(f"❌ Ошибка загрузки шрифта: {font_path}")
                return DEFAULT_FONT_FAMILY
            
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                font_family = families[0]
                print(f"✅ Загружен шрифт: {font_family}")
                
                font_manager.fontManager.addfont(font_path)
                mpl.rcParams['font.family'] = font_family
                
                return font_family
            else:
                return DEFAULT_FONT_FAMILY
                
        except Exception as e:
            print(f"❌ Ошибка при загрузке шрифта: {e}")
            return DEFAULT_FONT_FAMILY
    else:
        mpl.rcParams['font.family'] = DEFAULT_FONT_FAMILY
        return DEFAULT_FONT_FAMILY


class DataCache:
    """Класс для работы с кэшем данных"""
    
    @staticmethod
    def save(data):
        """Сохранить данные в кэш"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            print(f"💾 Кэш сохранен: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ Ошибка сохранения кэша: {e}")
    
    @staticmethod
    def load():
        """Загрузить данные из кэша"""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                    timestamp = cache_data.get('timestamp', '')
                    data = cache_data.get('data', None)
                    
                    if data:
                        print(f"📂 Кэш загружен (сохранен: {timestamp})")
                        return data
        except Exception as e:
            print(f"❌ Ошибка загрузки кэша: {e}")
        
        return None


class DataLoaderThread(QtCore.QThread):
    """Поток для асинхронной загрузки данных"""
    data_loaded = QtCore.pyqtSignal(dict)
    error_occurred = QtCore.pyqtSignal(str)
    
    def __init__(self, api, project_id):
        super().__init__()
        self.api = api
        self.project_id = project_id
    
    def run(self):
        """Выполнить загрузку данных в фоновом потоке"""
        try:
            print("🔄 Начало загрузки данных...")
            
            sections_dict = {s['id']: s['name'] for s in self.api.get_sections(self.project_id)}
            active_tasks = self.api.get_active_tasks(self.project_id)
            completed_tasks = self.api.get_completed_tasks(self.project_id)
            all_completed = self.api.get_all_completed_tasks()
            
            data = {
                'sections': sections_dict,
                'active_tasks': active_tasks,
                'completed_tasks': completed_tasks,
                'all_completed': all_completed,
                'timestamp': datetime.now().isoformat()
            }
            
            DataCache.save(data)
            
            self.data_loaded.emit(data)
            print("✅ Данные загружены успешно")
            
        except Exception as e:
            error_msg = f"Ошибка загрузки: {str(e)}"
            print(f"❌ {error_msg}")
            self.error_occurred.emit(error_msg)


class TodoistAPI:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://api.todoist.com/rest/v2"
        self.headers = {
            "Authorization": f"Bearer {api_token}"
        }
    
    def get_sections(self, project_id):
        """Получить все разделы проекта"""
        response = requests.get(
            f"{self.base_url}/sections?project_id={project_id}",
            headers=self.headers
        )
        return response.json() if response.status_code == 200 else []
    
    def get_active_tasks(self, project_id):
        """Получить активные задачи проекта"""
        response = requests.get(
            f"{self.base_url}/tasks?project_id={project_id}",
            headers=self.headers,
            timeout=30
        )
        return response.json() if response.status_code == 200 else []
    
    def get_all_completed_tasks(self):
        """Получить все выполненные задачи за последний год по всем проектам"""
        sync_url = "https://api.todoist.com/sync/v9/completed/get_all"
        
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        
        all_items = []
        offset = 0
        
        while True:
            params = {
                "limit": 200,
                "offset": offset
            }
            
            response = requests.post(
                sync_url, 
                headers=self.headers,
                json=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                for item in items:
                    completed_at = item.get('completed_at', '')
                    if completed_at:
                        try:
                            completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                            if completed_date >= one_year_ago:
                                all_items.append(item)
                        except (ValueError, AttributeError):
                            continue
                
                if len(items) < 200:
                    break
                
                offset += 200
            else:
                print(f"Ошибка API: {response.status_code}, {response.text}")
                break
        
        return all_items
    
    def get_completed_tasks(self, project_id):
        """Получить все выполненные задачи за последний год"""
        sync_url = "https://api.todoist.com/sync/v9/completed/get_all"
        
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        
        all_items = []
        offset = 0
        
        while True:
            params = {
                "project_id": project_id,
                "limit": 200,
                "offset": offset
            }
            
            response = requests.post(
                sync_url, 
                headers=self.headers,
                json=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                for item in items:
                    completed_at = item.get('completed_at', '')
                    if completed_at:
                        try:
                            completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                            if completed_date >= one_year_ago:
                                all_items.append(item)
                        except (ValueError, AttributeError):
                            continue
                
                if len(items) < 200:
                    break
                
                offset += 200
            else:
                print(f"Ошибка API: {response.status_code}, {response.text}")
                break
        
        return all_items


class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=6, dpi=100, font_family=DEFAULT_FONT_FAMILY):
        self.font_family = font_family
        
        fig = Figure(figsize=(width, height), dpi=dpi, 
                     facecolor='none', constrained_layout=True)
        self.axes = fig.add_subplot(111)
        self.axes.set_facecolor('none')
        super().__init__(fig)
        
        self.setStyleSheet("background-color: transparent;")
        
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding
        )
        
        self.setMinimumSize(400, 400)
        self.layout_fixed = False
        self.show_loading_state()
    
    def show_loading_state(self):
        """Показать состояние загрузки вместо пустых осей"""
        self.axes.clear()
        self.axes.set_facecolor('none')
        self.axes.axis('off')
        self.axes.text(0.5, 0.5, '⏳ Загрузка...', 
                      ha='center', va='center', 
                      fontsize=14, color='#666',
                      fontfamily=self.font_family,
                      transform=self.axes.transAxes)
        self.draw_idle()
    
    def create_bar_chart(self, weekday_data):
        """weekday_data: словарь {день_недели: количество}"""
        self.axes.clear()
        self.axes.set_facecolor('none')
        
        if not weekday_data:
            self.axes.axis('off')
            self.axes.text(0.5, 0.5, 'Нет данных за эту неделю', 
                        ha='center', va='center', fontsize=12, color='#666',
                        fontfamily=self.font_family,
                        transform=self.axes.transAxes)
            self.draw_idle()
            return
        
        days_order = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        days = []
        counts = []
        
        for day in days_order:
            days.append(day)
            counts.append(weekday_data.get(day, 0))
        
        # Определяем максимум для градиента
        max_count = max(counts) if counts and max(counts) > 0 else 1
        
        # Функция для получения цвета в зависимости от количества (4 уровня)
        def get_bar_color(count, max_val):
            if count == 0:
                return '#e9ecef'  # Серый для нуля
            
            ratio = count / max_val
            
            # 4 уровня синего (как в календаре)
            if ratio <= 0.25:
                return '#c6dbef'  # Светло-голубой
            elif ratio <= 0.5:
                return '#6baed6'  # Голубой
            elif ratio <= 0.75:
                return '#3182bd'  # Синий
            else:
                return '#08519c'  # Темно-синий
        
        # Создаем цвета для каждого столбца
        colors = [get_bar_color(count, max_count) for count in counts]
        
        bars = self.axes.bar(days, counts, color=colors, alpha=0.9, edgecolor='#2c3e50', linewidth=1.5)
        
        # Добавляем значения над столбцами
        for i, bar in enumerate(bars):
            height = bar.get_height()
            if height > 0:
                self.axes.text(bar.get_x() + bar.get_width()/2., height,
                            f'{int(height)}',
                            ha='center', va='bottom',
                            fontsize=11, weight='bold',
                            fontfamily=self.font_family,
                            color='#2c3e50')
        
        self.axes.set_xlabel('День недели', fontsize=11, fontfamily=self.font_family, color='#2c3e50')
        self.axes.set_ylabel('Количество задач', fontsize=11, fontfamily=self.font_family, color='#2c3e50')
        self.axes.set_title('Задачи по дням недели', 
                        fontsize=12, weight='bold', pad=15, color='#2c3e50',
                        fontfamily=self.font_family)
        
        # Настройка осей
        self.axes.spines['top'].set_visible(False)
        self.axes.spines['right'].set_visible(False)
        self.axes.spines['left'].set_color('#dee2e6')
        self.axes.spines['bottom'].set_color('#dee2e6')
        
        # Скрываем метки на оси Y
        self.axes.tick_params(left=False, labelleft=False, colors='#495057', labelsize=10)
        
        # Установка минимума для лучшего отображения
        max_count_display = max(counts) if counts else 0
        self.axes.set_ylim(0, max(max_count_display * 1.2, 1))
        
        # Убрана строка с grid - теперь нет горизонтальных линий
        
        self.draw_idle()



    def create_pie_chart(self, section_data):
        """section_data: словарь {название_раздела: количество_задач}"""
        self.axes.clear()
        self.axes.set_facecolor('none')
        
        if not section_data:
            self.axes.axis('off')
            self.axes.text(0.5, 0.5, 'Нет задач', 
                        ha='center', va='center', fontsize=12, color='#666',
                        fontfamily=self.font_family,
                        transform=self.axes.transAxes)
            self.draw_idle()
            return
        
        labels = list(section_data.keys())
        sizes = list(section_data.values())
        
        colors = ['#4A90E2', '#50C878', '#FFB347', '#FF6B6B', '#A463F2', 
                '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']
        
        wedges, texts, autotexts = self.axes.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%',
            startangle=90,
            colors=colors[:len(sizes)],
            textprops={'fontsize': 9, 'weight': 'bold', 'family': self.font_family}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(8)
            autotext.set_fontfamily(self.font_family)
        
        self.axes.axis('off')
        
        self.axes.set_title('Выполненные задачи', 
                        fontsize=12, weight='bold', pad=15, color='#2c3e50',
                        fontfamily=self.font_family)
        
        # Убираем фиксацию layout для правильного масштабирования
        self.draw_idle()



class MonthCalendarWidget(QtWidgets.QFrame):
    """Виджет календаря месяца с тепловой картой"""
    def __init__(self, font_family=DEFAULT_FONT_FAMILY):
        super().__init__()
        self.font_family = font_family
        self.date_counts = {}
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 12px;
            }
        """)
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setSpacing(8)
        self.main_layout.setContentsMargins(12, 12, 12, 12)
        
        # Заголовок
        self.title_label = QtWidgets.QLabel()
        self.title_label.setFont(QtGui.QFont(self.font_family, 14, QtGui.QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #2c3e50; padding-bottom: 5px;")
        self.title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.title_label)
        
        # Дни недели
        days_widget = QtWidgets.QWidget()
        days_layout = QtWidgets.QGridLayout(days_widget)
        days_layout.setSpacing(6)
        days_layout.setContentsMargins(0, 0, 0, 0)
        
        weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        for i, day in enumerate(weekdays):
            label = QtWidgets.QLabel(day)
            label.setFont(QtGui.QFont(self.font_family, 10, QtGui.QFont.Weight.Bold))
            label.setStyleSheet("color: #6c757d;")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            days_layout.addWidget(label, 0, i)
        
        self.main_layout.addWidget(days_widget)
        
        # Календарная сетка
        self.calendar_widget = QtWidgets.QWidget()
        self.calendar_layout = QtWidgets.QGridLayout(self.calendar_widget)
        self.calendar_layout.setSpacing(6)
        self.calendar_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.calendar_widget)
        
        self.main_layout.addStretch()
    
    def get_color_for_count(self, count, max_count):
        """Получить цвет в зависимости от количества задач (4 уровня)"""
        if count == 0:
            return '#e9ecef'
        
        if max_count == 0:
            return '#e9ecef'
        
        ratio = count / max_count
        
        # 4 уровня синего
        if ratio <= 0.25:
            return '#c6dbef'  # Светло-голубой
        elif ratio <= 0.5:
            return '#6baed6'  # Голубой
        elif ratio <= 0.75:
            return '#3182bd'  # Синий
        else:
            return '#08519c'  # Темно-синий
    
    def update_data(self, all_completed):
        """Обновить календарь с данными"""
        # Очищаем старые виджеты
        while self.calendar_layout.count():
            child = self.calendar_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Получаем текущий месяц
        now = datetime.now()
        self.title_label.setText(now.strftime('%B %Y'))
        
        # Подсчитываем задачи по дням текущего месяца
        self.date_counts = {}
        for task in all_completed:
            completed_at = task.get('completed_at')
            if completed_at:
                task_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                if task_date.year == now.year and task_date.month == now.month:
                    date_key = task_date.date()
                    self.date_counts[date_key] = self.date_counts.get(date_key, 0) + 1
        
        max_count = max(self.date_counts.values()) if self.date_counts else 1
        
        # Определяем первый день месяца и количество дней
        first_day = datetime(now.year, now.month, 1)
        start_weekday = first_day.weekday()  # 0 = понедельник
        
        # Количество дней в месяце
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1)
        else:
            next_month = datetime(now.year, now.month + 1, 1)
        days_in_month = (next_month - first_day).days
        
        # Создаем клетки календаря
        row = 1
        col = start_weekday
        
        for day in range(1, days_in_month + 1):
            date = datetime(now.year, now.month, day).date()
            count = self.date_counts.get(date, 0)
            color = self.get_color_for_count(count, max_count)
            
            cell = QtWidgets.QLabel(str(day))
            cell.setFont(QtGui.QFont(self.font_family, 12, QtGui.QFont.Weight.Bold))
            cell.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            cell.setFixedSize(50, 50)  # Увеличено с 35x35 до 50x50
            cell.setStyleSheet(f"""
                background-color: {color};
                border-radius: 8px;
                color: {'white' if count > max_count * 0.5 else '#2c3e50'};
            """)
            cell.setToolTip(f"{date.strftime('%d.%m.%Y')}: {count} задач")
            
            self.calendar_layout.addWidget(cell, row, col)
            
            col += 1
            if col > 6:
                col = 0
                row += 1


class WeeklyPage(QtWidgets.QWidget):
    """Страница с недельной статистикой и календарем месяца"""
    def __init__(self, api, font_family):
        super().__init__()
        self.api = api
        self.font_family = font_family
        self.current_data = None
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        # Левая колонка - столбчатый график
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        left_layout.setSpacing(10)
        
        title_label = QtWidgets.QLabel('📅 Статистика по дням недели')
        title_label.setFont(QtGui.QFont(self.font_family, 18, QtGui.QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.canvas = MplCanvas(self, width=8, height=7, dpi=100, font_family=self.font_family)
        
        # Время обновления
        self.time_label = QtWidgets.QLabel('Загрузка данных...')
        self.time_label.setFont(QtGui.QFont(self.font_family, 9))
        self.time_label.setStyleSheet("color: #6c757d; padding: 5px;")
        self.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        left_layout.addWidget(title_label)
        left_layout.addWidget(self.canvas, stretch=1)
        left_layout.addWidget(self.time_label)
        
        # Правая колонка - календарь месяца
        self.month_calendar = MonthCalendarWidget(self.font_family)
        
        main_layout.addWidget(left_widget, stretch=3)
        main_layout.addWidget(self.month_calendar, stretch=2)
    
    def update_from_data(self, data):
        """Обновить интерфейс из данных"""
        try:
            self.current_data = data
            
            all_completed = data.get('all_completed', [])
            
            # Обновляем столбчатый график
            now = datetime.now(timezone.utc)
            start_of_week = now - timedelta(days=now.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            weekday_counts = {
                'Пн': 0, 'Вт': 0, 'Ср': 0, 'Чт': 0, 'Пт': 0, 'Сб': 0, 'Вс': 0
            }
            weekday_map = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            
            for task in all_completed:
                completed_at = task.get('completed_at')
                if completed_at:
                    task_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    if task_date >= start_of_week:
                        weekday = weekday_map[task_date.weekday()]
                        weekday_counts[weekday] += 1
            
            self.canvas.create_bar_chart(weekday_counts)
            
            # Обновляем календарь месяца
            self.month_calendar.update_data(all_completed)
            
            timestamp = data.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp)
                self.time_label.setText(f'Обновлено: {dt.strftime("%H:%M:%S")}')
            else:
                current_time = QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')
                self.time_label.setText(f'Обновлено: {current_time}')
            
            total = sum(weekday_counts.values())
            print(f"✅ Недельная статистика: {total} задач")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            print(traceback.format_exc())




class ProgressWidget(QtWidgets.QFrame):
    """Виджет с прогресс-барами топ-3 разделов"""
    def __init__(self, font_family=DEFAULT_FONT_FAMILY):
        super().__init__()
        self.font_family = font_family
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        title = QtWidgets.QLabel('📈 Топ-3 раздела за месяц')
        title.setFont(QtGui.QFont(self.font_family, 13, QtGui.QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; padding: 5px;")
        layout.addWidget(title)
        
        self.progress_bars = []
        for i in range(3):
            container = QtWidgets.QWidget()
            container_layout = QtWidgets.QVBoxLayout(container)
            container_layout.setContentsMargins(0, 5, 0, 5)
            
            label = QtWidgets.QLabel(f"Раздел {i+1}")
            label.setFont(QtGui.QFont(self.font_family, 10))
            label.setStyleSheet("color: #495057;")
            
            progress = QtWidgets.QProgressBar()
            progress.setMaximum(MONTHLY_GOAL)
            progress.setTextVisible(True)
            progress.setFormat("%v / %m задач")
            progress.setFont(QtGui.QFont(self.font_family, 9))
            progress.setStyleSheet(f"""
                QProgressBar {{
                    border: 2px solid #dee2e6;
                    border-radius: 5px;
                    text-align: center;
                    background-color: #ffffff;
                    height: 25px;
                }}
                QProgressBar::chunk {{
                    background-color: {['#4A90E2', '#50C878', '#FFB347'][i]};
                    border-radius: 3px;
                }}
            """)
            
            container_layout.addWidget(label)
            container_layout.addWidget(progress)
            
            layout.addWidget(container)
            self.progress_bars.append((label, progress))
        
        layout.addStretch()
    
    def update_data(self, top_sections):
        for i, (label_widget, progress_bar) in enumerate(self.progress_bars):
            if i < len(top_sections):
                section_name, count = top_sections[i]
                label_widget.setText(f"🎯 {section_name}")
                progress_bar.setValue(count)
                progress_bar.setVisible(True)
                label_widget.setVisible(True)
            else:
                label_widget.setVisible(False)
                progress_bar.setVisible(False)


class SectionListWidget(QtWidgets.QFrame):
    """Виджет со списком разделов (раскрывающийся)"""
    def __init__(self, title, font_family=DEFAULT_FONT_FAMILY):
        super().__init__()
        self.font_family = font_family
        self.widget_title = title
        self.all_sections = []
        self.is_expanded = False
        self.setup_ui()
    
    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        
        self.main_layout = QtWidgets.QVBoxLayout(self)
        
        title = QtWidgets.QLabel(self.widget_title)
        title.setFont(QtGui.QFont(self.font_family, 12, QtGui.QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; padding: 5px;")
        self.main_layout.addWidget(title)
        
        self.items_container = QtWidgets.QWidget()
        self.items_layout = QtWidgets.QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(5)
        
        self.main_layout.addWidget(self.items_container)
        
        self.expand_btn = QtWidgets.QPushButton('▼ Показать все')
        self.expand_btn.setFont(QtGui.QFont(self.font_family, 9))
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #495057;
                border: 1px solid #dee2e6;
                border-radius: 5px;
                padding: 8px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.expand_btn.clicked.connect(self.toggle_expand)
        self.expand_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.expand_btn.setVisible(False)
        
        self.main_layout.addWidget(self.expand_btn)
    
    def toggle_expand(self):
        self.is_expanded = not self.is_expanded
        self.render_items()
        
        if self.is_expanded:
            self.expand_btn.setText('▲ Скрыть')
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
        else:
            self.expand_btn.setText('▼ Показать все')
            QtCore.QTimer.singleShot(10, self.apply_collapsed_size)
    
    def apply_collapsed_size(self):
        self.adjustSize()
        content_height = self.sizeHint().height()
        self.setMaximumHeight(content_height)
        self.setMinimumHeight(content_height)
        QtCore.QTimer.singleShot(100, lambda: self.setMinimumHeight(0))
    
    def update_data(self, sections):
        self.all_sections = sections
        self.is_expanded = False
        self.render_items()
        QtCore.QTimer.singleShot(10, self.apply_collapsed_size)
    
    def render_items(self):
        while self.items_layout.count():
            child = self.items_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.all_sections:
            empty_label = QtWidgets.QLabel("✅ Все разделы активны")
            empty_label.setFont(QtGui.QFont(self.font_family, 10))
            empty_label.setStyleSheet("color: #6c757d; padding: 10px;")
            empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.items_layout.addWidget(empty_label)
            self.expand_btn.setVisible(False)
        else:
            items_to_show = self.all_sections if self.is_expanded else self.all_sections[:3]
            
            for section in items_to_show:
                item = QtWidgets.QLabel(f"• {section}")
                item.setFont(QtGui.QFont(self.font_family, 10))
                item.setStyleSheet("""
                    color: #495057;
                    padding: 8px;
                    background-color: #ffffff;
                    border-radius: 5px;
                """)
                item.setWordWrap(True)
                self.items_layout.addWidget(item)
            
            self.expand_btn.setVisible(len(self.all_sections) > 3)


class SidebarButton(QtWidgets.QPushButton):
    """Кнопка боковой панели с иконкой"""
    def __init__(self, icon_text, tooltip, parent=None):
        super().__init__(icon_text, parent)
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFixedSize(60, 60)
        self.setFont(QtGui.QFont(DEFAULT_FONT_FAMILY, 20))
        self.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        
        self.setStyleSheet("""
            QPushButton {
                background-color: #f8f9fa;
                border: none;
                border-radius: 10px;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
            }
            QPushButton:checked {
                background-color: #4A90E2;
                color: white;
            }
        """)


class ProjectPage(QtWidgets.QWidget):
    """Страница с аналитикой проекта"""
    def __init__(self, api, project_id, font_family):
        super().__init__()
        self.api = api
        self.project_id = project_id
        self.font_family = font_family
        self.current_data = None
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        # Левая колонка
        left_column = QtWidgets.QVBoxLayout()
        
        title_label = QtWidgets.QLabel('📊 Аналитика проекта')
        title_label.setFont(QtGui.QFont(self.font_family, 20, QtGui.QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.canvas = MplCanvas(self, width=6, height=6, dpi=100, font_family=self.font_family)
        
        self.time_label = QtWidgets.QLabel('Загрузка данных...')
        self.time_label.setFont(QtGui.QFont(self.font_family, 9))
        self.time_label.setStyleSheet("color: #6c757d; padding: 5px;")
        self.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        left_column.addWidget(title_label)
        left_column.addWidget(self.canvas, stretch=1)
        left_column.addWidget(self.time_label)
        
        # Правая колонка
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(15)
        
        self.progress_widget = ProgressWidget(self.font_family)
        self.no_active_widget = SectionListWidget("⚠️ Разделы без активных задач", self.font_family)
        self.no_completed_widget = SectionListWidget("❌ Разделы без выполненных задач", self.font_family)
        
        right_column.addWidget(self.progress_widget)
        right_column.addWidget(self.no_active_widget)
        right_column.addWidget(self.no_completed_widget)
        right_column.addStretch()
        
        main_layout.addLayout(left_column, stretch=3)
        main_layout.addLayout(right_column, stretch=2)
    
    def update_from_data(self, data):
        """Обновить интерфейс из данных"""
        try:
            self.current_data = data
            
            sections_dict = data.get('sections', {})
            active_tasks = data.get('active_tasks', [])
            completed_tasks = data.get('completed_tasks', [])
            
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            monthly_completed = []
            for task in completed_tasks:
                completed_at = task.get('completed_at')
                if completed_at:
                    task_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    if task_date.month == current_month and task_date.year == current_year:
                        monthly_completed.append(task)
            
            section_completed_counts = {}
            for task in monthly_completed:
                section_id = task.get('section_id')
                section_name = sections_dict.get(section_id, 'Без раздела')
                section_completed_counts[section_name] = section_completed_counts.get(section_name, 0) + 1
            
            self.canvas.create_pie_chart(section_completed_counts)
            
            top_sections = sorted(section_completed_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            self.progress_widget.update_data(top_sections)
            
            sections_with_active = set()
            for task in active_tasks:
                section_id = task.get('section_id')
                if section_id in sections_dict:
                    sections_with_active.add(sections_dict[section_id])
            
            sections_without_active = [name for name in sections_dict.values() if name not in sections_with_active]
            self.no_active_widget.update_data(sections_without_active)
            
            sections_with_completed = set(section_completed_counts.keys())
            sections_without_completed = [name for name in sections_dict.values() if name not in sections_with_completed]
            self.no_completed_widget.update_data(sections_without_completed)
            
            timestamp = data.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp)
                self.time_label.setText(f'Обновлено: {dt.strftime("%H:%M:%S")}')
            else:
                current_time = QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')
                self.time_label.setText(f'Обновлено: {current_time}')
            
        except Exception as e:
            print(f"❌ Ошибка обновления: {e}")
            import traceback
            print(traceback.format_exc())


class WeeklyPage(QtWidgets.QWidget):
    """Страница с недельной статистикой и тепловыми картами"""
    def __init__(self, api, font_family):
        super().__init__()
        self.api = api
        self.font_family = font_family
        self.current_data = None
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        
        # Верхняя часть - две колонки
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout(top_widget)
        top_layout.setSpacing(20)
        
        # Левая колонка - столбчатый график
        left_widget = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left_widget)
        
        self.canvas = MplCanvas(self, width=7, height=5, dpi=100, font_family=self.font_family)
        left_layout.addWidget(self.canvas)
        
        # Правая колонка - календарь месяца
        self.month_calendar = MonthCalendarWidget(self.font_family)
        
        top_layout.addWidget(left_widget, stretch=3)
        top_layout.addWidget(self.month_calendar, stretch=2)
        
        
        # Время обновления
        self.time_label = QtWidgets.QLabel('Загрузка данных...')
        self.time_label.setFont(QtGui.QFont(self.font_family, 9))
        self.time_label.setStyleSheet("color: #6c757d; padding: 5px;")
        self.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(top_widget, stretch=2)
        main_layout.addWidget(self.time_label)
    
    def update_from_data(self, data):
        """Обновить интерфейс из данных"""
        try:
            self.current_data = data
            
            all_completed = data.get('all_completed', [])
            
            # Обновляем столбчатый график
            now = datetime.now(timezone.utc)
            start_of_week = now - timedelta(days=now.weekday())
            start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
            
            weekday_counts = {
                'Пн': 0, 'Вт': 0, 'Ср': 0, 'Чт': 0, 'Пт': 0, 'Сб': 0, 'Вс': 0
            }
            weekday_map = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
            
            for task in all_completed:
                completed_at = task.get('completed_at')
                if completed_at:
                    task_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    if task_date >= start_of_week:
                        weekday = weekday_map[task_date.weekday()]
                        weekday_counts[weekday] += 1
            
            self.canvas.create_bar_chart(weekday_counts)
            
            # Обновляем календарь месяца
            self.month_calendar.update_data(all_completed)
        
            
            timestamp = data.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp)
                self.time_label.setText(f'Обновлено: {dt.strftime("%H:%M:%S")}')
            else:
                current_time = QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')
                self.time_label.setText(f'Обновлено: {current_time}')
            
            total = sum(weekday_counts.values())
            print(f"✅ Недельная статистика: {total} задач")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            print(traceback.format_exc())


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, font_family=DEFAULT_FONT_FAMILY):
        super().__init__()
        self.font_family = font_family
        self.setWindowTitle('Todoist Analytics Dashboard')
        self.setGeometry(100, 100, 1400, 800)
        
        app_font = QtGui.QFont(self.font_family, FONT_SIZE)
        self.setFont(app_font)
        
        self.api = TodoistAPI(API_TOKEN)
        self.project_id = PROJECT_ID
        self.loader_thread = None
        
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный layout
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Боковая панель
        sidebar = QtWidgets.QWidget()
        sidebar.setFixedWidth(80)
        sidebar.setStyleSheet("background-color: #2c3e50;")
        sidebar_layout = QtWidgets.QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        sidebar_layout.setSpacing(15)
        
        # Кнопки боковой панели
        self.btn_project = SidebarButton('📊', 'Аналитика проекта')
        self.btn_weekly = SidebarButton('📅', 'Календарь активности')
        
        self.btn_project.setChecked(True)
        
        sidebar_layout.addWidget(self.btn_project)
        sidebar_layout.addWidget(self.btn_weekly)
        sidebar_layout.addStretch()
        
        # Кнопка обновления внизу
        self.refresh_btn = QtWidgets.QPushButton('🔄')
        self.refresh_btn.setFixedSize(60, 60)
        self.refresh_btn.setFont(QtGui.QFont(self.font_family, 20))
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2868A8;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.refresh_btn.clicked.connect(self.start_data_loading)
        self.refresh_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        sidebar_layout.addWidget(self.refresh_btn)
        
        # Контейнер для страниц
        pages_container = QtWidgets.QWidget()
        pages_layout = QtWidgets.QVBoxLayout(pages_container)
        pages_layout.setContentsMargins(20, 20, 20, 20)
        
        # QStackedWidget для переключения страниц
        self.stacked_widget = QtWidgets.QStackedWidget()
        
        # Создаем страницы
        self.project_page = ProjectPage(self.api, self.project_id, self.font_family)
        self.weekly_page = WeeklyPage(self.api, self.font_family)
        
        self.stacked_widget.addWidget(self.project_page)
        self.stacked_widget.addWidget(self.weekly_page)
        
        pages_layout.addWidget(self.stacked_widget)
        
        # Подключаем кнопки к переключению страниц
        self.btn_project.clicked.connect(lambda: self.switch_page(0))
        self.btn_weekly.clicked.connect(lambda: self.switch_page(1))
        
        # Добавляем в главный layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(pages_container, stretch=1)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
        """)
        
        # Таймер автообновления
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.start_data_loading)
        self.timer.start(UPDATE_INTERVAL)
        
        # Сначала загружаем кэш, потом запускаем обновление
        self.load_cached_data()
        QtCore.QTimer.singleShot(100, self.start_data_loading)
    
    def load_cached_data(self):
        """Загрузить данные из кэша"""
        cached_data = DataCache.load()
        if cached_data:
            self.project_page.update_from_data(cached_data)
            self.weekly_page.update_from_data(cached_data)
            print("✅ Данные из кэша отображены")
    
    def start_data_loading(self):
        """Запустить загрузку данных в фоновом потоке"""
        if self.loader_thread and self.loader_thread.isRunning():
            print("⚠️ Загрузка уже выполняется")
            return
        
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText('⏳')
        
        self.loader_thread = DataLoaderThread(self.api, self.project_id)
        self.loader_thread.data_loaded.connect(self.on_data_loaded)
        self.loader_thread.error_occurred.connect(self.on_error)
        self.loader_thread.finished.connect(self.on_loading_finished)
        self.loader_thread.start()
    
    def on_data_loaded(self, data):
        """Обработать загруженные данные"""
        self.project_page.update_from_data(data)
        self.weekly_page.update_from_data(data)
    
    def on_error(self, error_msg):
        """Обработать ошибку загрузки"""
        print(f"❌ {error_msg}")
    
    def on_loading_finished(self):
        """Завершение загрузки"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText('🔄')
    
    def switch_page(self, index):
        """Переключение между страницами"""
        self.stacked_widget.setCurrentIndex(index)
        
        self.btn_project.setChecked(index == 0)
        self.btn_weekly.setChecked(index == 1)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font_family = setup_custom_font(CUSTOM_FONT_PATH if USE_CUSTOM_FONT else None)
    app.setFont(QtGui.QFont(font_family, FONT_SIZE))
    
    window = MainWindow(font_family)
    window.show()
    sys.exit(app.exec())
