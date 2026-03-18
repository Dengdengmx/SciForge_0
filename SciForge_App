# SciForge_App.py
import os
import sys

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu-compositing"

import keyboard # 【新增】系统级全局键盘监听库

from PyQt5.QtCore import Qt, QObject, pyqtSignal, QSettings

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction
from qfluentwidgets import (FluentWindow, NavigationItemPosition, setTheme, Theme, 
                            FluentIcon as FIF, MessageBoxBase, SubtitleLabel, BodyLabel, CheckBox)

from hubs_data_hub import DataHubCoordinator
from hubs_workspace import WorkspaceCoordinator
from hubs_settings import SettingsCoordinator  
from hubs_calendar_archive import CalendarArchiveCoordinator
from hubs_sample_hub import SampleHubCoordinator 

from core.signals import global_bus
from core.plugin_manager import PluginManager
from ui.floating_dock import FloatingDock

# 【新增】跨线程快捷键信号桥梁
class HotkeyBridge(QObject):
    toggle_dock_signal = pyqtSignal()

class CloseConfirmDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('退出确认', self)
        self.contentLabel = BodyLabel('您希望将 SciForge 缩小到系统托盘常驻，还是直接退出整个程序？\n\n(缩小到托盘后，按 Ctrl+Alt+D 仍可随时唤出引力坞)', self)
        self.cb_remember = CheckBox("记住我的选择，以后不再提示", self)
        
        # 关键：将组件按顺序塞入底层提供的 viewLayout 中
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addSpacing(10)
        self.viewLayout.addWidget(self.cb_remember)
        
        # 设置按钮文字和最小宽度防止拥挤
        self.yesButton.setText('隐藏至托盘')
        self.cancelButton.setText('完全退出')
        self.widget.setMinimumWidth(380)

class SciForgeApp(FluentWindow):
    def __init__(self):
        super().__init__()
        self.resize(1300, 850)
        self.setWindowTitle('SciForge Studio - ProDesigner')
        self.settings = QSettings("SciForge", "AppConfig")
        
        # 1. 启动各个中枢
        self.calendar_module = CalendarArchiveCoordinator()
        self.data_hub_module = DataHubCoordinator()
        self.workspace_module = WorkspaceCoordinator() 
        self.sample_module = SampleHubCoordinator() 
        self.settings_module = SettingsCoordinator() 
        
        # 2. 挂载上方导航
        self.addSubInterface(self.calendar_module.ui, FIF.CALENDAR, '日历记录本', position=NavigationItemPosition.TOP)
        self.addSubInterface(self.data_hub_module.ui, FIF.FOLDER, '数据归档检索', position=NavigationItemPosition.TOP)
        self.addSubInterface(self.workspace_module.ui, FIF.APPLICATION, '绘图工作站', position=NavigationItemPosition.TOP)
        self.addSubInterface(self.sample_module.ui, FIF.TILES, '物理样本库存', position=NavigationItemPosition.TOP)
        self.addSubInterface(self.settings_module.ui, FIF.SETTING, '全局设置', position=NavigationItemPosition.BOTTOM)
        
        self.navigationInterface.setCurrentItem(self.calendar_module.ui.objectName())
        global_bus.switch_main_tab.connect(self.handle_tab_switch)

        # 🚀 接收数据中心传来的“空间瞬移”指令
        global_bus.jump_to_sample.connect(lambda path, wid: self.switchTo(self.sample_module.ui)) # 1. 切换左侧导航栏到样本库
        global_bus.jump_to_sample.connect(self.sample_module.jump_to_specific_location)           # 2. 命令样本库自动剥开 UI

        # ==========================================
        # 🌟 悬浮引力坞与全局系统级快捷键
        # ==========================================
        self.floating_dock = FloatingDock()
        
        # 建立跨线程信号桥
        self.hotkey_bridge = HotkeyBridge()
        self.hotkey_bridge.toggle_dock_signal.connect(self.toggle_floating_dock)
        
        # 注册纯底层的系统级快捷键 (即使软件在后台也能捕获)
        try:
            keyboard.add_hotkey('ctrl+alt+d', self.hotkey_bridge.toggle_dock_signal.emit)
        except Exception as e:
            print(f"[Warning] 快捷键注册失败，可能是权限问题: {e}")

        # 初始化系统托盘
        self.init_system_tray()
        
    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(self.style().SP_ComputerIcon))
        
        self.tray_menu = QMenu(self)
        action_show_main = QAction("显示主工作台", self)
        action_show_main.triggered.connect(self.show_normal_and_activate)
        
        self.action_toggle_dock = QAction("显示桌面引力坞 (Ctrl+Alt+D)", self)
        self.action_toggle_dock.triggered.connect(self.toggle_floating_dock)
        
        action_reset_close = QAction("⚙️ 恢复退出提示弹窗", self)
        action_reset_close.triggered.connect(lambda: self.settings.remove("close_action"))

        action_quit = QAction("完全退出程序", self)
        action_quit.triggered.connect(self.force_quit)
        
        self.tray_menu.addAction(action_show_main)
        self.tray_menu.addAction(self.action_toggle_dock)
        self.tray_menu.addAction(action_reset_close)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(action_quit)
        
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        self.tray_icon.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_normal_and_activate()

    def show_normal_and_activate(self):
        self.show()
        # 确保窗口强制回到最前台
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    def toggle_floating_dock(self):
        if self.floating_dock.isVisible():
            self.floating_dock.hide()
            self.action_toggle_dock.setText("显示桌面引力坞 (Ctrl+Alt+D)")
        else:
            # 获取主屏幕尺寸，将引力坞展示在屏幕中上方
            screen_geo = QApplication.primaryScreen().geometry()
            dock_geo = self.floating_dock.geometry()
            self.floating_dock.move(
                (screen_geo.width() - dock_geo.width()) // 2, 
                screen_geo.height() // 8
            )
            self.floating_dock.show()
            self.floating_dock.raise_()
            self.floating_dock.activateWindow()
            self.action_toggle_dock.setText("隐藏桌面引力坞 (Ctrl+Alt+D)")

    def closeEvent(self, event):
        # 1. 检查本地是否已经记住了用户的选择
        saved_action = self.settings.value("close_action", "")
        
        if saved_action == "tray":
            self._minimize_to_tray()
            event.ignore()
            return
        elif saved_action == "quit":
            self.force_quit()
            return

        # 2. 如果没记住，则实例化并弹出我们自定义的高级确认框
        dialog = CloseConfirmDialog(self)

        if dialog.exec():
            # 用户点击了“隐藏至托盘” (Yes)
            if dialog.cb_remember.isChecked():
                self.settings.setValue("close_action", "tray")
            self._minimize_to_tray()
            event.ignore()
        else:
            # 用户点击了“完全退出” (Cancel)
            if dialog.cb_remember.isChecked():
                self.settings.setValue("close_action", "quit")
            self.force_quit()

    def _minimize_to_tray(self):
        """抽出独立的方法以供复用"""
        self.hide()
        self.tray_icon.showMessage(
            "SciForge 已进入静默护航模式",
            "快捷键 Ctrl+Alt+D 可随时唤出桌面引力坞。",
            self.tray_icon.Information, # 这里修正了图标枚举的调用
            2000
        )
            
    def force_quit(self):
        # 退出前卸载全局键盘钩子，防止系统内存泄漏
        keyboard.unhook_all()
        self.tray_icon.hide()
        self.floating_dock.close()
        QApplication.quit()

    def handle_tab_switch(self, tab_name):
        self.show_normal_and_activate()
        if tab_name == "workspace":
            self.switchTo(self.workspace_module.ui)
        elif tab_name == "calendar":
            self.switchTo(self.calendar_module.ui)
        elif tab_name == "data_hub":
            self.switchTo(self.data_hub_module.ui)
        elif tab_name == "sample_hub":
            self.switchTo(self.sample_module.ui)

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False) 
    
    setTheme(Theme.LIGHT)
    window = SciForgeApp()
    window.show()
    sys.exit(app.exec_())
