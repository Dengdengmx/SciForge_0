# view/ui_settings.py
from PyQt5.QtCore import Qt, QSettings, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
from qfluentwidgets import (ScrollArea, SimpleCardWidget, SubtitleLabel, StrongBodyLabel, 
                            ComboBox, Slider, SegmentedWidget, LineEdit, PrimaryPushButton, 
                            PushButton, TextEdit, ListWidget, FluentIcon as FIF, BodyLabel,
                            SettingCardGroup) # 【核心新增】：引入原生的设置组控件

class SettingsUI(QWidget):
    sig_tag_added = pyqtSignal(str)
    sig_tag_deleted = pyqtSignal(str)
    sig_template_saved = pyqtSignal(str, str)
    sig_template_deleted = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsUI")
        self.global_settings = QSettings("SciForge", "Studio")
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 顶部选项卡
        self.pivot = SegmentedWidget(self)
        self.pivot.addItem("core", "🗂️ 全局字典与模板配置")
        self.pivot.addItem("plugin", "🔌 绘图工作站参数预设")
        layout.addWidget(self.pivot, 0, Qt.AlignHCenter)
        layout.addSpacing(10)
        
        self.stack = QStackedWidget(self)
        
        # ==========================================
        # Tab 1: 全局字典配置
        # ==========================================
        core_scroll = ScrollArea()
        core_scroll.setWidgetResizable(True); core_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        core_widget = QWidget(); self.core_layout = QVBoxLayout(core_widget)
        self.core_layout.setContentsMargins(10, 10, 10, 10); self.core_layout.setSpacing(20)
        
        # 模块 1：归档标签管理
        tag_card = SimpleCardWidget(); tag_layout = QVBoxLayout(tag_card)
        tag_layout.addWidget(SubtitleLabel("🏷️ 归档目录标签库 (Archive Tags)"))
        
        row1 = QHBoxLayout()
        self.input_tag = LineEdit(); self.input_tag.setPlaceholderText("输入新标签名称...")
        btn_add_tag = PrimaryPushButton("添加标签", icon=FIF.ADD)
        btn_add_tag.clicked.connect(lambda: self.sig_tag_added.emit(self.input_tag.text().strip()))
        row1.addWidget(self.input_tag); row1.addWidget(btn_add_tag)
        tag_layout.addLayout(row1)
        
        self.list_tags = ListWidget(); self.list_tags.setFixedHeight(120)
        tag_layout.addWidget(self.list_tags)
        
        btn_del_tag = PushButton("🗑️ 删除选中的标签")
        btn_del_tag.setStyleSheet("color: #D83B01;")
        btn_del_tag.clicked.connect(lambda: self.sig_tag_deleted.emit(self.list_tags.currentItem().text()) if self.list_tags.currentItem() else None)
        tag_layout.addWidget(btn_del_tag, 0, Qt.AlignRight)
        self.core_layout.addWidget(tag_card)
        
        # 模块 2：ELN 模板管理
        tpl_card = SimpleCardWidget(); tpl_layout = QVBoxLayout(tpl_card)
        tpl_layout.addWidget(SubtitleLabel("📝 ELN 实验模板库 (Templates)"))
        
        row2 = QHBoxLayout()
        row2.addWidget(StrongBodyLabel("选择现有模板:"))
        self.combo_tpl = ComboBox(); self.combo_tpl.setFixedWidth(200)
        row2.addWidget(self.combo_tpl)
        row2.addSpacing(20)
        row2.addWidget(StrongBodyLabel("或 创建新模板名:"))
        self.input_tpl_name = LineEdit(); self.input_tpl_name.setPlaceholderText("输入新模板名称...")
        row2.addWidget(self.input_tpl_name)
        tpl_layout.addLayout(row2)
        
        self.text_tpl = TextEdit(); self.text_tpl.setPlaceholderText("在此编写模板的详细文本格式...")
        self.text_tpl.setFixedHeight(200)
        tpl_layout.addWidget(self.text_tpl)
        
        row3 = QHBoxLayout()
        btn_del_tpl = PushButton("🗑️ 删除当前下拉框中的模板")
        btn_del_tpl.setStyleSheet("color: #D83B01;")
        btn_del_tpl.clicked.connect(lambda: self.sig_template_deleted.emit(self.combo_tpl.currentText()))
        row3.addWidget(btn_del_tpl); row3.addStretch(1)
        btn_save_tpl = PrimaryPushButton("💾 保存/覆盖 模板内容")
        btn_save_tpl.clicked.connect(self._emit_save_tpl)
        row3.addWidget(btn_save_tpl)
        tpl_layout.addLayout(row3)
        
        self.core_layout.addWidget(tpl_card); self.core_layout.addStretch(1)
        core_scroll.setWidget(core_widget); self.stack.addWidget(core_scroll)
        
        # ==========================================
        # Tab 2: 插件配置
        # ==========================================
        plugin_scroll = ScrollArea()
        plugin_scroll.setWidgetResizable(True); plugin_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.plugin_widget = QWidget(); self.plugin_layout = QVBoxLayout(self.plugin_widget)
        self.plugin_layout.setContentsMargins(10, 10, 10, 10); self.plugin_layout.setSpacing(20)
        
        # 【核心修复1】：增加顶端对齐，防止你的插件设置卡片被垂直拉伸占满全屏
        self.plugin_layout.setAlignment(Qt.AlignTop) 
        
        plugin_scroll.setWidget(self.plugin_widget); self.stack.addWidget(plugin_scroll)
        
        layout.addWidget(self.stack)
        self.pivot.currentItemChanged.connect(lambda k: self.stack.setCurrentIndex(0 if k=="core" else 1))
        self.pivot.setCurrentItem("core")

    def _emit_save_tpl(self):
        name = self.input_tpl_name.text().strip() or self.combo_tpl.currentText()
        content = self.text_tpl.toPlainText()
        if name: self.sig_template_saved.emit(name, content)

    def load_core_data(self, tags, templates_dict):
        self.list_tags.clear(); self.list_tags.addItems(tags); self.input_tag.clear()
        
        self.combo_tpl.blockSignals(True)
        self.combo_tpl.clear()
        self.combo_tpl.addItems(list(templates_dict.keys()))
        self.combo_tpl.blockSignals(False)
        self.input_tpl_name.clear()
        
        self.templates_dict = templates_dict
        self.combo_tpl.currentIndexChanged.connect(self._on_tpl_changed)
        if templates_dict: self._on_tpl_changed()

    def _on_tpl_changed(self):
        name = self.combo_tpl.currentText()
        self.text_tpl.setPlainText(self.templates_dict.get(name, ""))

    # ==========================================
    # 【核心升级：原生高颜值插件挂载逻辑】
    # ==========================================
    def build_dynamic_settings(self, plugins):
        """动态生成插件的全局设置界面"""
        while self.plugin_layout.count():
            item = self.plugin_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        if not plugins:
            self.plugin_layout.addWidget(BodyLabel("当前未扫描到任何需要预设的绘图插件。"))
            return
        
        # 【核心修复2】：使用 SettingCardGroup 聚合所有的插件设置，完美契合 Fluent Design
        group = SettingCardGroup("🧩 已挂载的自动化引擎与插件", self.plugin_widget)

        for plugin in plugins:
            # 优先寻找重型插件的自定义卡片 (如 SPRPlugin)
            if hasattr(plugin, 'get_setting_card'):
                card = plugin.get_setting_card(group) # 传入 group 作为 parent
                if card:
                    group.addSettingCard(card)
                    
            # 兼容旧版或轻量级插件的自动表单
            elif hasattr(plugin, 'get_settings_schema'):
                schema = plugin.get_settings_schema()
                if not schema: continue 
                
                card = SimpleCardWidget(self)
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(20, 20, 20, 20)
                card_layout.addWidget(SubtitleLabel(f"🎨 {plugin.plugin_name} - 参数选项"))

                for item in schema:
                    key, label, widget_type = item["key"], item["label"], item["type"]
                    full_key = f"Plugin_{plugin.plugin_id}/{key}"
                    row_layout = QHBoxLayout(); row_layout.addWidget(StrongBodyLabel(label)); row_layout.addStretch(1) 
                    current_val = self.global_settings.value(full_key, item["default"])

                    if widget_type == "combo":
                        ctrl = ComboBox(); ctrl.addItems(item["options"]); ctrl.setCurrentText(str(current_val))
                        ctrl.currentTextChanged.connect(lambda v, k=full_key: self.global_settings.setValue(k, v))
                        ctrl.setFixedWidth(200); row_layout.addWidget(ctrl)
                    elif widget_type == "slider":
                        ctrl = Slider(Qt.Horizontal); ctrl.setRange(item["min"], item["max"]); ctrl.setValue(int(current_val))
                        ctrl.setFixedWidth(200); ctrl.valueChanged.connect(lambda v, k=full_key: self.global_settings.setValue(k, v))
                        row_layout.addWidget(ctrl)

                    card_layout.addLayout(row_layout)
                self.plugin_layout.addWidget(card)
                
        self.plugin_layout.addWidget(group)