import sys
import requests
from datetime import datetime, timedelta
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
from matplotlib import font_manager
import matplotlib as mpl
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QFontDatabase


# ============ НАСТРОЙКИ ============
PROJECT_ID = "your_id"
API_TOKEN = "your_api"
UPDATE_INTERVAL = 5000

CUSTOM_FONT_PATH = "SF-Pro-Display-Medium.otf"
USE_CUSTOM_FONT = False
DEFAULT_FONT_FAMILY = "Segoe UI"
FONT_SIZE = 10

MONTHLY_GOAL = 100
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
    
    def get_completed_tasks(self, project_id):
        """Получить все выполненные задачи за последний год"""
        sync_url = "https://api.todoist.com/sync/v9/completed/get_all"
        
        # Дата год назад
        from datetime import timezone
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        since_date = one_year_ago.strftime("%Y-%m-%dT%H:%M:%S")
        
        all_items = []
        offset = 0
        
        # Пагинация - получаем все задачи без лимита
        while True:
            params = {
                "project_id": project_id,
                "limit": 200,  # Максимум за один запрос
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
                
                # Фильтруем только задачи не старше года
                for item in items:
                    completed_at = item.get('completed_at', '')
                    if completed_at:
                        completed_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                        if completed_date >= one_year_ago:
                            all_items.append(item)
                
                # Если получили меньше чем лимит, значит это последняя страница
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
    
    def create_pie_chart(self, section_data):
        """
        section_data: словарь {название_раздела: количество_задач}
        """
        self.axes.clear()
        self.axes.set_facecolor('none')
        self.axes.axis('on')
        
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
        
        if not self.layout_fixed:
            self.draw()
            self.figure.canvas.draw()
            self.layout_positions = [ax.get_position().bounds for ax in self.figure.axes]
            self.figure.set_constrained_layout(False)
            for ax, bounds in zip(self.figure.axes, self.layout_positions):
                ax.set_position(bounds)
            self.layout_fixed = True
        
        self.draw_idle()


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
        
        # Заголовок
        title = QtWidgets.QLabel('📈 Топ-3 раздела за месяц')
        title.setFont(QtGui.QFont(self.font_family, 13, QtGui.QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; padding: 5px;")
        layout.addWidget(title)
        
        # Контейнеры для прогресс-баров
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
        """
        top_sections: список кортежей [(название, количество), ...]
        """
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
        
        # Заголовок
        title = QtWidgets.QLabel(self.widget_title)
        title.setFont(QtGui.QFont(self.font_family, 12, QtGui.QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50; padding: 5px;")
        self.main_layout.addWidget(title)
        
        # Контейнер для элементов списка
        self.items_container = QtWidgets.QWidget()
        self.items_layout = QtWidgets.QVBoxLayout(self.items_container)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(5)
        
        self.main_layout.addWidget(self.items_container)
        
        # Кнопка "Показать все"
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
        """Переключить раскрытие/скрытие"""
        self.is_expanded = not self.is_expanded
        self.render_items()
        
        if self.is_expanded:
            self.expand_btn.setText('▲ Скрыть')
            # При раскрытии убираем ограничения
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
        else:
            self.expand_btn.setText('▼ Показать все')
            # При сворачивании устанавливаем максимальную высоту
            QtCore.QTimer.singleShot(10, self.apply_collapsed_size)
    
    def apply_collapsed_size(self):
        """Применить размер для свернутого состояния"""
        # Получаем реальную высоту содержимого
        self.adjustSize()
        content_height = self.sizeHint().height()
        
        # Устанавливаем фиксированную высоту для свернутого состояния
        self.setMaximumHeight(content_height)
        self.setMinimumHeight(content_height)
        
        # Через небольшую задержку снова разрешаем минимальное изменение
        QtCore.QTimer.singleShot(100, lambda: self.setMinimumHeight(0))
    
    def update_data(self, sections):
        """
        sections: список названий разделов
        """
        self.all_sections = sections
        self.is_expanded = False
        self.render_items()
        
        # При обновлении данных сбрасываем ограничения и применяем размер
        QtCore.QTimer.singleShot(10, self.apply_collapsed_size)
    
    def render_items(self):
        """Отрисовать элементы списка"""
        # Очищаем старые виджеты
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
            # Показываем первые 3 или все в зависимости от состояния
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
            
            # Показываем кнопку только если элементов больше 3
            self.expand_btn.setVisible(len(self.all_sections) > 3)


# Также нужно изменить правую колонку в MainWindow, убрав stretch:
# В методе __init__ класса MainWindow найдите эти строки и измените:

        # ========== ПРАВАЯ КОЛОНКА ==========
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(15)
        
        # Виджет с прогресс-барами
        self.progress_widget = ProgressWidget(self.font_family)
        
        # Виджет без активных задач
        self.no_active_widget = SectionListWidget(
            "⚠️ Разделы без активных задач", 
            self.font_family
        )
        
        # Виджет без выполненных задач
        self.no_completed_widget = SectionListWidget(
            "❌ Разделы без выполненных задач",
            self.font_family
        )
        
        # Убираем stretch - виджеты будут занимать только необходимое место
        right_column.addWidget(self.progress_widget)
        right_column.addWidget(self.no_active_widget)
        right_column.addWidget(self.no_completed_widget)
        right_column.addStretch()  # Добавляем stretch в конец колонки




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
        
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной горизонтальный layout
        main_layout = QtWidgets.QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # ========== ЛЕВАЯ КОЛОНКА ==========
        left_column = QtWidgets.QVBoxLayout()
        
        # Заголовок
        title_label = QtWidgets.QLabel('📊 Todoist Analytics')
        title_label.setFont(QtGui.QFont(self.font_family, 20, QtGui.QFont.Weight.Bold))
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Canvas для диаграммы
        self.canvas = MplCanvas(self, width=6, height=6, dpi=100, font_family=self.font_family)
        
        # Время обновления
        self.time_label = QtWidgets.QLabel('Обновлено: --:--:--')
        self.time_label.setFont(QtGui.QFont(self.font_family, 9))
        self.time_label.setStyleSheet("color: #6c757d; padding: 5px;")
        self.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Кнопка обновления
        self.refresh_btn = QtWidgets.QPushButton('🔄 Обновить')
        self.refresh_btn.setFont(QtGui.QFont(self.font_family, 11, QtGui.QFont.Weight.Bold))
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2868A8;
            }
        """)
        self.refresh_btn.clicked.connect(self.update_all_data)
        self.refresh_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        
        left_column.addWidget(title_label)
        left_column.addWidget(self.canvas, stretch=1)
        left_column.addWidget(self.time_label)
        left_column.addWidget(self.refresh_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # ========== ПРАВАЯ КОЛОНКА ==========
        right_column = QtWidgets.QVBoxLayout()
        right_column.setSpacing(15)
        
        # Виджет с прогресс-барами
        self.progress_widget = ProgressWidget(self.font_family)
        
        # Виджет без активных задач
        self.no_active_widget = SectionListWidget(
            "⚠️ Разделы без активных задач", 
            self.font_family
        )
        
        # Виджет без выполненных задач
        self.no_completed_widget = SectionListWidget(
            "❌ Разделы без выполненных задач",
            self.font_family
        )
        
        right_column.addWidget(self.progress_widget, stretch=2)
        right_column.addWidget(self.no_active_widget, stretch=2)
        right_column.addWidget(self.no_completed_widget, stretch=2)
        
        # Добавляем колонки в main layout
        main_layout.addLayout(left_column, stretch=3)
        main_layout.addLayout(right_column, stretch=2)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
        """)
        
        # Таймер автообновления
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_all_data)
        self.timer.start(UPDATE_INTERVAL)
        
        QtCore.QTimer.singleShot(500, self.update_all_data)
    
    def update_all_data(self):
        try:
            # Получаем данные
            sections_dict = {s['id']: s['name'] for s in self.api.get_sections(self.project_id)}
            active_tasks = self.api.get_active_tasks(self.project_id)
            completed_tasks = self.api.get_completed_tasks(self.project_id)
            
            print(f"✅ Загружено {len(completed_tasks)} выполненных задач за последний год")
            
            # Фильтруем задачи за текущий месяц
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            monthly_completed = []
            for task in completed_tasks:
                completed_at = task.get('completed_at')
                if completed_at:
                    task_date = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    if task_date.month == current_month and task_date.year == current_year:
                        monthly_completed.append(task)
            
            # Подсчет по разделам (за месяц)
            section_completed_counts = {}
            for task in monthly_completed:
                section_id = task.get('section_id')
                section_name = sections_dict.get(section_id, 'Без раздела')
                section_completed_counts[section_name] = section_completed_counts.get(section_name, 0) + 1
            
            # Обновляем круговую диаграмму
            self.canvas.create_pie_chart(section_completed_counts)
            
            # Топ-3 раздела
            top_sections = sorted(
                section_completed_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            self.progress_widget.update_data(top_sections)
            
            # Разделы без активных задач
            sections_with_active = set()
            for task in active_tasks:
                section_id = task.get('section_id')
                if section_id in sections_dict:
                    sections_with_active.add(sections_dict[section_id])
            
            sections_without_active = [
                name for name in sections_dict.values() 
                if name not in sections_with_active
            ]
            self.no_active_widget.update_data(sections_without_active)
            
            # Разделы без выполненных задач за месяц
            sections_with_completed = set(section_completed_counts.keys())
            sections_without_completed = [
                name for name in sections_dict.values()
                if name not in sections_with_completed
            ]
            self.no_completed_widget.update_data(sections_without_completed)
            
            # Обновляем время
            current_time = QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')
            self.time_label.setText(f'Обновлено: {current_time}')
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            print(traceback.format_exc())


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    font_family = setup_custom_font(CUSTOM_FONT_PATH if USE_CUSTOM_FONT else None)
    app.setFont(QtGui.QFont(font_family, FONT_SIZE))
    
    window = MainWindow(font_family)
    window.show()
    sys.exit(app.exec())
