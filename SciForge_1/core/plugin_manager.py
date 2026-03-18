# core/plugin_manager.py
import os
import sys
import importlib.util
import traceback

# 【绝对路径锁定】确保无论从哪里运行，都能找到项目根目录和 core 模块
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CORE_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

class BasePlugin:
    plugin_id = "base"
    plugin_name = "未命名插件"
    description = "这是一个基础插件模板"
    icon = "🧩" 

    def get_ui(self, parent=None):
        return None

    def get_setting_card(self, parent=None):
        """【新增】允许插件向全局设置中心提供一个入口卡片"""
        return None
    
    def get_settings_schema(self):
        return [] 

    def run(self, file_path, params, logger):
        raise NotImplementedError

class PluginManager:
    _plugins = []

    @classmethod
    def load_all_plugins(cls):
        cls._plugins = []
        plugins_dir = os.path.join(PROJECT_ROOT, "plugins")
        if not os.path.exists(plugins_dir):
            os.makedirs(plugins_dir)
        
        for file in os.listdir(plugins_dir):
            if file.endswith(".py") and not file.startswith("__"):
                module_name = file[:-3]
                file_path = os.path.join(plugins_dir, file)
                
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and attr.__name__ != "BasePlugin":
                            if hasattr(attr, "plugin_id") and hasattr(attr, "run"):
                                cls._plugins.append(attr())
                                print(f"[Plugin Engine] ✅ 成功加载插件: {getattr(attr, 'plugin_name', module_name)}")
                                
                except Exception as e:
                    print(f"\n[Plugin Engine] ❌ 插件 {file} 加载失败!")
                    print("="*40)
                    traceback.print_exc() # 打印极其详细的报错原因
                    print("="*40 + "\n")

    @classmethod
    def get_plugins(cls):
        if not cls._plugins:
            cls.load_all_plugins()
        return cls._plugins