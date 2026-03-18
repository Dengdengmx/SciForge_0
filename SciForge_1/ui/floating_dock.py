# ui/floating_dock.py
import os
import tempfile
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from qfluentwidgets import InfoBar, InfoBarPosition

from core.signals import global_bus
from core.plugin_manager import PluginManager
# 【新增】引入第三阶段的结果弹窗
from ui.result_notifier import ResultNotificationWindow

class SilentPluginWorker(QThread):
    sig_success = pyqtSignal(str, str, str, str, str) 
    sig_error = pyqtSignal(str, str)

    def __init__(self, plugin_id, file_path, archive_dir):
        super().__init__()
        self.plugin_id = plugin_id
        self.file_path = file_path
        self.archive_dir = archive_dir

    def run(self):
        try:
            plugins = PluginManager.get_plugins()
            plugin_cls = next((p for p in plugins if getattr(p, 'plugin_id', '') == self.plugin_id), None)
            if not plugin_cls:
                self.sig_error.emit(self.plugin_id, "未找到对应的插件实体！")
                return

            img_path, html_report = plugin_cls.run(self.file_path, self.archive_dir)
            title = getattr(plugin_cls, 'plugin_name', self.plugin_id)
            self.sig_success.emit(title, html_report, img_path, self.plugin_id, self.file_path)
            
        except Exception as e:
            self.sig_error.emit(self.plugin_id, f"执行异常: {str(e)}")

# ==========================================
# 🎨 界面组件：原子投递按钮 (高颜值重构版)
# ==========================================
class DropZoneButton(QWidget):
    sig_file_dropped = pyqtSignal(str, str, bool)

    def __init__(self, target_id, icon_text, display_name, tooltip, is_plugin=True, parent=None):
        super().__init__(parent)
        self.target_id = target_id
        self.is_plugin = is_plugin
        
        self.setToolTip(tooltip)
        self.setFixedSize(70, 95) # 调整整体宽高比
        self.setAcceptDrops(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        layout.setSpacing(6)
        
        # 顶部：大图标 (圆角正方形白底)
        self.lbl_icon = QLabel(icon_text)
        self.lbl_icon.setFont(QFont("Segoe UI Emoji", 24))
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        self.lbl_icon.setFixedSize(54, 54)
        self.lbl_icon.setStyleSheet("""
            QLabel {
                background-color: #FFFFFF;
                border: 1px solid #E5E5E5;
                border-radius: 12px; 
            }
        """)
        
        # 底部：说明文字 (圆角矩形白底细边框)
        self.lbl_text = QLabel(display_name)
        self.lbl_text.setFont(QFont("Microsoft YaHei", 8))
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setFixedSize(66, 20)
        self.lbl_text.setStyleSheet("""
            QLabel {
                background-color: #FFFFFF;
                border: 1px solid #E5E5E5;
                border-radius: 4px; 
                color: #555555;
            }
        """)
        
        layout.addWidget(self.lbl_icon, 0, Qt.AlignHCenter)
        layout.addWidget(self.lbl_text, 0, Qt.AlignHCenter)
        
        # 外层不可见，仅用于捕获事件和悬停遮罩
        self.setStyleSheet("""
            DropZoneButton { background-color: transparent; border-radius: 8px; }
            DropZoneButton:hover { background-color: rgba(0, 120, 212, 0.08); }
        """)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            if self.is_plugin:
                global_bus.switch_main_tab.emit("workspace")
                # 【修改这里】：参数顺序严格为 (plugin_id, file_path)
                global_bus.send_file_to_plot.emit("", self.target_id)
            else:
                global_bus.switch_main_tab.emit(self.target_id)
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet("DropZoneButton { background-color: rgba(16, 124, 16, 0.15); border-radius: 8px; border: 1px dashed #107C10; }")
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet("""
            DropZoneButton:hover { background-color: rgba(0, 120, 212, 0.08); }
            DropZoneButton { background-color: transparent; border-radius: 8px; }
        """)

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if os.path.isfile(filepath):
                self.sig_file_dropped.emit(filepath, self.target_id, self.is_plugin)
        event.acceptProposedAction()


class FloatingDock(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.active_threads = []
        self.silent_archive_dir = os.path.join(tempfile.gettempdir(), "SciForge_Silent_Cache")
        os.makedirs(self.silent_archive_dir, exist_ok=True)
        self.init_ui()

    def _simplify_name(self, original_name):
        """【智能改名器】：精简插件名称以适应短圆角矩形"""
        n = original_name
        if "拼板" in n: return "绘图拼板"
        if "序列" in n: return "序列比对"
        if "BLI" in n or "热图" in n: return "竞争BLI"
        if "3D" in n: return "3D 结构"
        if "SPR" in n: return "SPR"
        if "AKTA" in n: return "AKTA"
        if "ELISA" in n: return "ELISA"
        return n[:6]

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15) 
        
        self.panel = QFrame(self)
        self.panel.setStyleSheet("""
            QFrame { background-color: rgba(245, 246, 247, 0.95); border: 1px solid #D1D1D1; border-radius: 18px; }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 30))
        shadow.setOffset(0, 6)
        self.panel.setGraphicsEffect(shadow)
        
        self.dock_layout = QHBoxLayout(self.panel)
        self.dock_layout.setContentsMargins(15, 8, 15, 8)
        self.dock_layout.setSpacing(10)
        
        self.add_drop_button("calendar", "📅", "智能归档", "点击：打开实验本\n拖入文件：智能改名并归档存证", is_plugin=False)
        self.add_drop_button("sample_hub", "🧊", "样本库存", "点击：打开库存视图", is_plugin=False)
        self.add_drop_button("data_hub", "📂", "数据中心", "点击：打开本地与云端数据面板", is_plugin=False)
        
        sep = QFrame()
        sep.setFixedSize(1, 45)
        sep.setStyleSheet("background-color: #CCCCCC;")
        self.dock_layout.addWidget(sep)
        
        plugins = PluginManager.get_plugins()
        if plugins:
            for p in plugins:
                p_id = getattr(p, 'plugin_id', 'unknown')
                p_icon = getattr(p, 'icon', '🧩') 
                p_name = getattr(p, 'plugin_name', p_id)
                short_name = self._simplify_name(p_name)
                tooltip = f"点击：跳转工作站调参\n拖入文件：无头模式静默算图"
                self.add_drop_button(p_id, p_icon, short_name, tooltip, is_plugin=True)
        
        main_layout.addWidget(self.panel)

    def add_drop_button(self, target_id, icon_text, display_name, tooltip, is_plugin=True):
        btn = DropZoneButton(target_id, icon_text, display_name, tooltip, is_plugin, self)
        btn.sig_file_dropped.connect(self.handle_file_dropped)
        self.dock_layout.addWidget(btn)

    def handle_file_dropped(self, filepath, target_id, is_plugin):
        if not is_plugin:
            if target_id == "calendar":
                global_bus.switch_main_tab.emit("calendar")
                global_bus.send_file_to_eln.emit(filepath)
            return

        filename = os.path.basename(filepath)
        InfoBar.info(
            title='🚀 后台算图引擎已启动',
            content=f'[{filename}] 正在静默处理中，请稍候...',
            orient=Qt.Horizontal, isClosable=True, position=InfoBarPosition.TOP_RIGHT,
            duration=3000, parent=self
        )
        
        worker = SilentPluginWorker(target_id, filepath, self.silent_archive_dir)
        worker.sig_success.connect(self.on_silent_success)
        worker.sig_error.connect(self.on_silent_error)
        
        self.active_threads.append(worker)
        worker.start()

    # ==========================================
    # 🎯 闭环：拉起弹窗简报
    # ==========================================
    def on_silent_success(self, title, html_report, image_path, plugin_id, original_filepath):
        self.active_threads = [t for t in self.active_threads if t.isRunning()]
        
        # 弹出一个模态的预览窗口
        self.notifier = ResultNotificationWindow(title, html_report, image_path, plugin_id, original_filepath)
        self.notifier.exec_() # 阻塞显示，直到用户点击按钮或关闭

    def on_silent_error(self, plugin_id, error_msg):
        self.active_threads = [t for t in self.active_threads if t.isRunning()]
        InfoBar.error(
            title='❌ 后台分析失败',
            content=f'引擎 [{plugin_id}] 报错: {error_msg}',
            orient=Qt.Horizontal, isClosable=True, position=InfoBarPosition.TOP_RIGHT,
            duration=5000, parent=self
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()