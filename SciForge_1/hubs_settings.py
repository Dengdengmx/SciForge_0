# hubs_settings.py
from view.ui_settings import SettingsUI
from core.plugin_manager import PluginManager
from core.config import GlobalConfig

class SettingsCoordinator:
    def __init__(self):
        self.ui = SettingsUI()
        
        # 1. 刷新和绑定第一页的“全局字典”
        self._refresh_core_ui()
        self._bind_core_signals()
        
        # 2. 刷新第二页的“绘图插件设置”
        plugins = PluginManager.get_plugins()
        self.ui.build_dynamic_settings(plugins)
        
    def _refresh_core_ui(self):
        # 从 GlobalConfig 索取数据并交给皮囊
        tags = GlobalConfig.get("archive_tags", [])
        tpls = GlobalConfig.get("eln_templates", {})
        self.ui.load_core_data(tags, tpls)

    def _bind_core_signals(self):
        self.ui.sig_tag_added.connect(self.add_tag)
        self.ui.sig_tag_deleted.connect(self.delete_tag)
        self.ui.sig_template_saved.connect(self.save_template)
        self.ui.sig_template_deleted.connect(self.delete_template)

    def add_tag(self, tag):
        if not tag: return
        tags = GlobalConfig.get("archive_tags", [])
        if tag not in tags:
            tags.append(tag)
            GlobalConfig.set("archive_tags", tags) # 自动写入 JSON 持久化
            self._refresh_core_ui()

    def delete_tag(self, tag):
        tags = GlobalConfig.get("archive_tags", [])
        if tag in tags:
            tags.remove(tag)
            GlobalConfig.set("archive_tags", tags)
            self._refresh_core_ui()

    def save_template(self, name, content):
        tpls = GlobalConfig.get("eln_templates", {})
        tpls[name] = content
        GlobalConfig.set("eln_templates", tpls)
        self._refresh_core_ui()
        
    def delete_template(self, name):
        tpls = GlobalConfig.get("eln_templates", {})
        if name in tpls:
            del tpls[name]
            GlobalConfig.set("eln_templates", tpls)
            self._refresh_core_ui()