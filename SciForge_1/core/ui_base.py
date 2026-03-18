# core/ui_base.py
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from qfluentwidgets import SimpleCardWidget, SubtitleLabel, ScrollArea

class BasePluginUI(QWidget):
    def __init__(self, plugin_id="unknown", plugin_name="未命名插件", parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        
        # 接入系统注册表/配置文件引擎
        self.global_settings = QSettings("SciForge", "Studio")
        
        self._setup_base_ui()

    # ==========================================
    # 【核心新增】插件与全局设置中心的联动接口
    # ==========================================
    def get_settings_schema(self):
        """【虚函数】由子类覆写。返回一个列表，声明自己需要全局设置中心生成哪些控件"""
        return []

    def get_conf(self, key, default_val=None, type_cls=str):
        """供子类在初始化时读取用户的全局预设"""
        full_key = f"Plugin_{self.plugin_id}/{key}"
        return self.global_settings.value(full_key, default_val, type=type_cls)

    # ==========================================
    # 基础 UI 搭建 (保持不变)
    # ==========================================
    def _setup_base_ui(self):
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(15)

        self.param_panel = SimpleCardWidget(self)
        self.param_panel.setFixedWidth(300) 
        self.param_layout = QVBoxLayout(self.param_panel)
        self.param_layout.setContentsMargins(15, 15, 15, 15)

        self.title_label = SubtitleLabel(f"{self.plugin_name} 参数")
        self.param_layout.addWidget(self.title_label)

        self.scroll_area = ScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(0, 10, 0, 0)
        self.scroll_layout.setSpacing(15)
        self.scroll_area.setWidget(self.scroll_widget)
        
        self.param_layout.addWidget(self.scroll_area)
        self.main_layout.addWidget(self.param_panel)

        self.canvas_panel = SimpleCardWidget(self)
        self.canvas_layout = QVBoxLayout(self.canvas_panel)
        self.main_layout.addWidget(self.canvas_panel)
        
        self.main_layout.setStretch(0, 0)
        self.main_layout.setStretch(1, 1)

    def add_param_widget(self, widget: QWidget):
        self.scroll_layout.addWidget(widget)

    def add_param_stretch(self):
        self.scroll_layout.addStretch(1)

    def get_canvas_layout(self):
        return self.canvas_layout

    def receive_data(self, filepath: str):
        raise NotImplementedError("子类必须实现 receive_data 方法！")