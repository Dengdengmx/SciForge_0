# view/ui_workspace.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import SubtitleLabel, StrongBodyLabel, ComboBox

class WorkspaceUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("WorkspaceUI")
        self.plugins = []
        self.current_plugin_widget = None
        self._setup_ui()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        
        top_layout = QHBoxLayout()
        top_layout.addWidget(SubtitleLabel("🛠️ 数据分析与可视化工作站"))
        top_layout.addSpacing(40)
        top_layout.addWidget(StrongBodyLabel("🧰 当前挂载引擎:"))
        
        self.combo_plugins = ComboBox()
        self.combo_plugins.setFixedWidth(280)
        self.combo_plugins.currentIndexChanged.connect(self._on_plugin_selected)
        top_layout.addWidget(self.combo_plugins)
        top_layout.addStretch(1)

        self.main_layout.addLayout(top_layout)
        self.main_layout.addSpacing(10)

        self.plugin_slot = QVBoxLayout()
        self.plugin_slot.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addLayout(self.plugin_slot, 1)

    def load_plugins(self, plugins):
        self.plugins = plugins
        self.combo_plugins.blockSignals(True)
        self.combo_plugins.clear()
        for p in plugins:
            self.combo_plugins.addItem(f"{p.icon} {p.plugin_name}")
        self.combo_plugins.blockSignals(False)
        
        if plugins:
            self.combo_plugins.setCurrentIndex(0)
            self._on_plugin_selected(0)

    # 【核心新增】：供中枢调用的强制切换插件方法
    def switch_to_plugin(self, target_plugin_id):
        for i, p in enumerate(self.plugins):
            if p.plugin_id == target_plugin_id:
                self.combo_plugins.setCurrentIndex(i)
                return True
        return False

    def _on_plugin_selected(self, index):
        if index < 0 or index >= len(self.plugins): return
        plugin = self.plugins[index]
        
        if self.current_plugin_widget:
            self.current_plugin_widget.deleteLater()
            self.current_plugin_widget = None
            
        if hasattr(plugin, 'get_ui'):
            self.current_plugin_widget = plugin.get_ui(self)
            if self.current_plugin_widget:
                self.plugin_slot.addWidget(self.current_plugin_widget)