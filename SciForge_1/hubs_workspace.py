# hubs_workspace.py
import os
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBar, InfoBarPosition

from view.ui_workspace import WorkspaceUI
from core.plugin_manager import PluginManager
from core.signals import global_bus

class WorkspaceCoordinator:
    def __init__(self):
        self.ui = WorkspaceUI()
        self._load_all()
        self._bind_signals()

    def _load_all(self):
        plugins = PluginManager.get_plugins()
        self.ui.load_plugins(plugins)

    def _bind_signals(self):
        # 倾听来自 Data Hub 的右键定向发送请求
        global_bus.send_file_to_plot.connect(self.handle_incoming_file)

    def handle_incoming_file(self, filepath, target_plugin_id):
        """【神级路由】切换插件 ➔ 页面跳转 ➔ 注射数据"""
        
        # 1. 呼叫主程序：立刻将导航栏跳转到 Workspace (工作台)！
        global_bus.switch_main_tab.emit("workspace")
        
        # 2. 检查并强制切换下拉框到目标插件
        switched = self.ui.switch_to_plugin(target_plugin_id)
        if not switched:
            InfoBar.error(
                title='投送拦截',
                content=f'未在系统中找到标识符为 [{target_plugin_id}] 的分析引擎！',
                orient=Qt.Horizontal, position=InfoBarPosition.TOP, duration=4000, parent=self.ui
            )
            return

        # ===============================================
        # 👇 核心修复：如果是单纯跳转，弹完提示就直接 return！
        # ===============================================
        if not filepath:
            InfoBar.info(
                title="引擎已就绪",
                content="已为您切换至该分析引擎工作台。",
                orient=Qt.Horizontal, isClosable=True, position=InfoBarPosition.TOP,
                duration=1500, parent=self.ui
            )
            return 
            
        # ===============================================
        # 👇 以下是只有带有真实 filepath 时才会执行的注射逻辑
        # ===============================================
        widget = self.ui.current_plugin_widget
        file_name = os.path.basename(filepath)
        
        if widget and hasattr(widget, 'load_file'):
            try:
                widget.load_file(filepath)
                InfoBar.success(
                    title='数据定向注射成功',
                    content=f'文件「{file_name}」已精准投送至当前分析引擎！',
                    orient=Qt.Horizontal, isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self.ui
                )
            except Exception as e:
                InfoBar.error(
                    title='数据加载异常', content=f'引擎解析该文件时发生错误: {str(e)}',
                    orient=Qt.Horizontal, position=InfoBarPosition.TOP, duration=4000, parent=self.ui
                )
        else:
            InfoBar.warning(
                title='拒绝注射', content=f'目标分析引擎不支持接收外部文件交互。',
                orient=Qt.Horizontal, position=InfoBarPosition.TOP, duration=4000, parent=self.ui
            )