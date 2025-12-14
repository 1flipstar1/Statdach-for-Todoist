import sys
import requests
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
from matplotlib import font_manager
import matplotlib as mpl
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QFontDatabase


# ============ НАСТРОЙКИ ============
PROJECT_ID = "your id"
API_TOKEN = "your api"
UPDATE_INTERVAL = 15000

# Настройки шрифта
CUSTOM_FONT_PATH = "SF-Pro-Display-Medium.otf"  # Путь к вашему .ttf файлу
USE_CUSTOM_FONT = True  # Установите True для использования кастомного шрифта
DEFAULT_FONT_FAMILY = "Segoe UI"  # Используется если USE_CUSTOM_FONT = False
FONT_SIZE = 10
# ===================================


def setup_custom_font(font_path=None):
    """Настройка кастомного шрифта для PyQt6 и Matplotlib"""
    if font_path and USE_CUSTOM_FONT:
        try:
            # Загружаем шрифт в PyQt6
            font_id = QFontDatabase.addApplicationFont(font_path)
            
            if font_id < 0:
                print(f"❌ Ошибка загрузки шрифта: {font_path}")
                return DEFAULT_FONT_FAMILY
            
            # Получаем имя семейства шрифта
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                font_family = families[0]
                print(f"✅ Загружен шрифт: {font_family}")
                
                # Настраиваем matplotlib для использования этого же шрифта
                font_manager.fontManager.addfont(font_path)
                mpl.rcParams['font.family'] = font_family
                
                return font_family
            else:
                print(f"⚠️ Не удалось получить семейство шрифта")
                return DEFAULT_FONT_FAMILY
                
        except Exception as e:
            print(f"❌ Ошибка при загрузке шрифта: {e}")
            return DEFAULT_FONT_FAMILY
    else:
        # Используем системный шрифт по умолчанию
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
    
    def get_completed_tasks(self, project_id):
        """Получить выполненные задачи через Sync API"""
        sync_url = "https://api.todoist.com/sync/v9/completed/get_all"
        
        params = {
            "project_id": project_id,
            "limit": 200
        }
        
        response = requests.post(
            sync_url, 
            headers=self.headers,
            json=params,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            print(f"Ошибка API: {response.status_code}, {response.text}")
            return []


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
        
        self.setMinimumSize(600, 450)
        self.layout_fixed = False
        self.show_loading_state()
    
    def show_loading_state(self):
        """Показать состояние загрузки вместо пустых осей"""
        self.axes.clear()
        self.axes.set_facecolor('none')
        self.axes.axis('off')
        self.axes.text(0.5, 0.5, '⏳ Загрузка данных...', 
                      ha='center', va='center', 
                      fontsize=16, color='#666',
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
            self.axes.text(0.5, 0.5, 'Нет выполненных задач', 
                          ha='center', va='center', fontsize=14, color='#666',
                          fontfamily=self.font_family,
                          transform=self.axes.transAxes)
            self.draw_idle()
            return
        
        labels = list(section_data.keys())
        sizes = list(section_data.values())
        
        colors = ['#4A90E2', '#50C878', '#FFB347', '#FF6B6B', '#A463F2', 
                  '#45B7D1', '#FFA07A', '#98D8C8', '#F7DC6F', '#BB8FCE']
        
        # Создание круговой диаграммы с кастомным шрифтом
        wedges, texts, autotexts = self.axes.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%',
            startangle=90,
            colors=colors[:len(sizes)],
            textprops={'fontsize': 10, 'weight': 'bold', 'family': self.font_family}
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_fontsize(9)
            autotext.set_fontfamily(self.font_family)
        
        self.axes.axis('off')
        
        self.axes.set_title('Распределение выполненных задач', 
                           fontsize=13, weight='bold', pad=20, color='#2c3e50',
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


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, font_family=DEFAULT_FONT_FAMILY):
        super().__init__()
        self.font_family = font_family
        self.setWindowTitle('Todoist Analytics')
        self.setGeometry(100, 100, 900, 750)
        
        # Устанавливаем шрифт для всего окна
        app_font = QtGui.QFont(self.font_family, FONT_SIZE)
        self.setFont(app_font)
        
        self.api = TodoistAPI(API_TOKEN)
        self.project_id = PROJECT_ID
        
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Заголовок с явным указанием шрифта
        title_label = QtWidgets.QLabel('📊 Todoist Analytics Dashboard')
        title_label.setFont(QtGui.QFont(self.font_family, 24, QtGui.QFont.Weight.Bold))
        title_label.setStyleSheet("""
            color: #2c3e50;
            padding: 10px;
        """)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Информационная панель
        info_panel = QtWidgets.QFrame()
        info_panel.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 15px;
            }
        """)
        info_layout = QtWidgets.QHBoxLayout(info_panel)
        
        # Статус-лейбл
        self.status_label = QtWidgets.QLabel('🔄 Загрузка данных...')
        self.status_label.setFont(QtGui.QFont(self.font_family, 13))
        self.status_label.setStyleSheet("color: #495057; padding: 5px;")
        
        # Время последнего обновления
        self.time_label = QtWidgets.QLabel('')
        self.time_label.setFont(QtGui.QFont(self.font_family, 11))
        self.time_label.setStyleSheet("color: #6c757d; padding: 5px;")
        self.time_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        
        info_layout.addWidget(self.status_label)
        info_layout.addStretch()
        info_layout.addWidget(self.time_label)
        
        # Canvas для диаграммы
        self.canvas = MplCanvas(self, width=8, height=6, dpi=100, font_family=self.font_family)
        
        # Кнопка ручного обновления
        self.refresh_btn = QtWidgets.QPushButton('🔄 Обновить сейчас')
        self.refresh_btn.setFont(QtGui.QFont(self.font_family, 13, QtGui.QFont.Weight.Bold))
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4A90E2;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #357ABD;
            }
            QPushButton:pressed {
                background-color: #2868A8;
            }
        """)
        self.refresh_btn.clicked.connect(self.update_chart)
        self.refresh_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        
        main_layout.addWidget(title_label)
        main_layout.addWidget(info_panel)
        main_layout.addWidget(self.canvas, stretch=1)
        main_layout.addWidget(self.refresh_btn, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ffffff;
            }
        """)
        
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_chart)
        self.timer.start(UPDATE_INTERVAL)
        
        QtCore.QTimer.singleShot(500, self.update_chart)
    
    def update_chart(self):
        try:
            self.status_label.setText('🔄 Обновление данных...')
            QtWidgets.QApplication.processEvents()
            
            sections = {s['id']: s['name'] for s in self.api.get_sections(self.project_id)}
            completed = self.api.get_completed_tasks(self.project_id)
            
            section_counts = {}
            for task in completed:
                section_id = task.get('section_id')
                section_name = sections.get(section_id, 'Без раздела')
                section_counts[section_name] = section_counts.get(section_name, 0) + 1
            
            self.canvas.create_pie_chart(section_counts)
            
            total_tasks = sum(section_counts.values())
            if total_tasks > 0:
                self.status_label.setText(
                    f'✅ {total_tasks} выполненных задач в {len(section_counts)} разделах'
                )
            else:
                self.status_label.setText('⚠️ Нет выполненных задач в этом проекте')
            
            current_time = QtCore.QDateTime.currentDateTime().toString('hh:mm:ss')
            self.time_label.setText(f'Обновлено: {current_time}')
            
        except Exception as e:
            self.status_label.setText(f'❌ Ошибка: {str(e)}')
            import traceback
            print(traceback.format_exc())


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Загружаем кастомный шрифт (если указан)
    font_family = setup_custom_font(CUSTOM_FONT_PATH if USE_CUSTOM_FONT else None)
    
    # Применяем шрифт ко всему приложению
    app.setFont(QtGui.QFont(font_family, FONT_SIZE))
    
    window = MainWindow(font_family)
    window.show()
    sys.exit(app.exec())
