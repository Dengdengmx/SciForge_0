# plugins/akta_plugin/ui_akta.py
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel
from qfluentwidgets import Slider, ComboBox, BodyLabel, StrongBodyLabel
from core.ui_base import BasePluginUI

class AKTAPluginUI(BasePluginUI):
    def __init__(self, parent=None):
        super().__init__(plugin_id="akta", plugin_name="AKTA 层析分析", parent=parent)
        self._init_custom_params()
        self._init_custom_canvas()

    # 【联动核心 1】：向上级汇报自己的配置字典
    def get_settings_schema(self):
        return [
            {"key": "theme", "label": "默认色彩主题", "type": "combo", "options": ["SciForge Teal", "Classic Blue", "Publication Red"], "default": "SciForge Teal"},
            {"key": "smooth", "label": "默认平滑级别", "type": "slider", "min": 1, "max": 10, "default": 3}
        ]

    def _init_custom_params(self):
        # 【联动核心 2】：从内存读取预设，没有就用默认值
        default_smooth = self.get_conf("smooth", 3, int)
        default_theme = self.get_conf("theme", "SciForge Teal", str)

        self.add_param_widget(StrongBodyLabel("平滑处理 (Smoothing):"))
        self.slider_smooth = Slider(Qt.Horizontal)
        self.slider_smooth.setRange(1, 10)
        self.slider_smooth.setValue(default_smooth) # 应用预设
        self.add_param_widget(self.slider_smooth)

        self.add_param_widget(StrongBodyLabel("色彩主题 (Theme):"))
        self.combo_color = ComboBox()
        self.combo_color.addItems(["SciForge Teal", "Classic Blue", "Publication Red"])
        if default_theme in ["SciForge Teal", "Classic Blue", "Publication Red"]:
            self.combo_color.setCurrentText(default_theme) # 应用预设
        self.add_param_widget(self.combo_color)
        
        self.add_param_stretch()

    def _init_custom_canvas(self):
        self.canvas_label = BodyLabel("Matplotlib 画布将在这里渲染...")
        self.canvas_label.setAlignment(Qt.AlignCenter)
        self.canvas_label.setStyleSheet("color: #666;")
        self.get_canvas_layout().addWidget(self.canvas_label)

    def receive_data(self, filepath: str):
        filename = os.path.basename(filepath)
        self.canvas_label.setText(f"🚀 成功接收数据：\n{filename}")
        self.canvas_label.setStyleSheet("color: #0078D7; font-weight: bold; font-size: 14px;")