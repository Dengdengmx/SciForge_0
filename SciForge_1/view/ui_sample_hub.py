# view/ui_sample_hub.py
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QSize
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QStackedWidget, QFrame, QDialog, QApplication, QSizePolicy,
                             QRubberBand)
from qfluentwidgets import (CardWidget, SubtitleLabel, BodyLabel, PrimaryPushButton,
                            PushButton, FluentIcon as FIF, IconWidget, ScrollArea, StrongBodyLabel,
                            LineEdit, ComboBox, TextEdit, RoundMenu, Action, TitleLabel, SpinBox, DoubleSpinBox, CheckBox)

# ==========================================
# 🚀 神级交互：支持原生地表最强橡皮筋框选的网格容器
# ==========================================
class GridContainer(QWidget):
    sig_selection_done = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_marquee_mode = False
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = QPoint()
        self.well_widgets = {} # wid -> QWidget

    def mousePressEvent(self, event):
        if self.is_marquee_mode and event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_marquee_mode and not self.origin.isNull():
            self.rubberBand.setGeometry(QRect(self.origin, event.pos()).normalized())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_marquee_mode and event.button() == Qt.LeftButton:
            self.rubberBand.hide()
            rect = self.rubberBand.geometry()
            selected_wids = []
            
            # 碰撞检测算法：只要框和按钮有交集，立马选中！
            for wid, btn in self.well_widgets.items():
                if rect.intersects(btn.geometry()):
                    selected_wids.append(wid)
                    
            if selected_wids: 
                self.sig_selection_done.emit(selected_wids)
            self.origin = QPoint()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

# ... 往下是你原来写的 RenameDialog, EquipmentSetupDialog 等代码，不要动 ...

class RenameDialog(QDialog):
    def __init__(self, current_name, parent=None):
        super().__init__(parent); self.setWindowTitle("自定义专属名称"); self.setFixedSize(320, 160); self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self); layout.addWidget(SubtitleLabel("✏️ 自定义专属名称"))
        self.input_name = LineEdit(); self.input_name.setText(current_name); layout.addWidget(self.input_name); layout.addStretch(1)
        btn_layout = QHBoxLayout(); btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject)
        btn_save = PrimaryPushButton("💾 保存"); btn_save.clicked.connect(self.accept)
        btn_layout.addStretch(1); btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_save); layout.addLayout(btn_layout)
    def get_name(self): return self.input_name.text().strip()

class EquipmentSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("🏢 采购/登记新物理设备"); self.setFixedSize(380, 260); self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self); layout.addWidget(StrongBodyLabel("1. 设备名称:")); self.input_name = LineEdit(); self.input_name.setPlaceholderText("例如: 二楼细胞房液氮罐")
        layout.addWidget(self.input_name); layout.addSpacing(10); layout.addWidget(StrongBodyLabel("2. 设备物理网格尺寸 (基础行与列):"))
        dim_layout = QHBoxLayout(); self.spin_row = SpinBox(); self.spin_row.setRange(1, 20); self.spin_row.setValue(5)
        self.spin_col = SpinBox(); self.spin_col.setRange(1, 20); self.spin_col.setValue(4)
        dim_layout.addWidget(BodyLabel("总行数:")); dim_layout.addWidget(self.spin_row); dim_layout.addWidget(BodyLabel("总列数:")); dim_layout.addWidget(self.spin_col)
        layout.addLayout(dim_layout); layout.addStretch(1); btn_box = QHBoxLayout(); btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("💾 建立设备档案"); btn_ok.clicked.connect(self.accept)
        btn_box.addStretch(); btn_box.addWidget(btn_cancel); btn_box.addWidget(btn_ok); layout.addLayout(btn_box)
    def get_data(self): return {"name": self.input_name.text().strip() or "未命名新设备", "rows": self.spin_row.value(), "cols": self.spin_col.value()}

class ContainerSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("🛠️ 安装物理大容器"); self.setFixedSize(380, 360); self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self); layout.addWidget(StrongBodyLabel("1. 容器名称:")); self.input_name = LineEdit(); layout.addWidget(self.input_name)
        layout.addSpacing(10); layout.addWidget(StrongBodyLabel("2. 容器大类:")); self.combo_type = ComboBox()
        self.combo_type.addItems(["🧊 标准冻存架 (含多个抽屉/盒子)", "📦 独立标准方格冻存盒", "🧫 独立试管架 / 离心管架", "📥 自由散装大抽屉 (可跨格且可嵌套)"])
        self.combo_type.currentIndexChanged.connect(self._on_type_changed); layout.addWidget(self.combo_type)
        layout.addSpacing(10); layout.addWidget(StrongBodyLabel("3. 内部规格/尺寸:")); self.combo_sub = ComboBox(); layout.addWidget(self.combo_sub)
        self.dim_widget = QWidget(); dim_layout = QHBoxLayout(self.dim_widget); dim_layout.setContentsMargins(0,0,0,0)
        self.spin_row = SpinBox(); self.spin_row.setRange(1, 10); self.spin_row.setValue(1); self.spin_col = SpinBox(); self.spin_col.setRange(1, 10); self.spin_col.setValue(1)
        dim_layout.addWidget(BodyLabel("占据行数:")); dim_layout.addWidget(self.spin_row); dim_layout.addWidget(BodyLabel("占据列数:")); dim_layout.addWidget(self.spin_col)
        self.dim_widget.hide(); layout.addWidget(self.dim_widget); layout.addStretch(1); btn_box = QHBoxLayout(); btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("确定上架"); btn_ok.clicked.connect(self.accept)
        btn_box.addStretch(); btn_box.addWidget(btn_cancel); btn_box.addWidget(btn_ok); layout.addLayout(btn_box)
        self._on_type_changed(0)
    def _on_type_changed(self, idx):
        self.combo_sub.clear()
        if idx == 0: self.combo_sub.show(); self.dim_widget.hide(); self.combo_sub.addItems(["5层 × 每层4盒 (标准架)", "4层 × 每层4盒", "5层 × 每层5盒"])
        elif idx == 1: self.combo_sub.show(); self.dim_widget.hide(); self.combo_sub.addItems(["9x9 (81孔标准盒)", "10x10 (100孔密集盒)"])
        elif idx == 2: self.combo_sub.show(); self.dim_widget.hide(); self.combo_sub.addItems(["12x8 (96孔板/PCR管架)", "12x5 (60孔标准试管架)"])
        else: self.combo_sub.hide(); self.dim_widget.show()
    def get_data(self):
        name = self.input_name.text().strip() or "未命名容器"; idx = self.combo_type.currentIndex()
        if idx == 0: 
            s = self.combo_sub.currentText(); layers = int(s.split('层')[0]); boxes = int(s.split('每层')[1].split('盒')[0])
            return {"name": name, "type": "rack", "rs": 1, "cs": 1, "layers": layers, "boxes": boxes}
        elif idx == 1: s = self.combo_sub.currentText(); return {"name": name, "type": "9x9" if "9x9" in s else "10x10", "rs": 1, "cs": 1}
        elif idx == 2: s = self.combo_sub.currentText(); return {"name": name, "type": "12x8" if "12x8" in s else "12x5", "rs": 1, "cs": 1}
        else: return {"name": name, "type": "freeform", "rs": self.spin_row.value(), "cs": self.spin_col.value()}

class InnerBoxSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("📦 放入内部容器"); self.setFixedSize(300, 220); self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self); layout.addWidget(StrongBodyLabel("1. 容器名称:")); self.input_name = LineEdit(); layout.addWidget(self.input_name)
        layout.addSpacing(10); layout.addWidget(StrongBodyLabel("2. 选择规格:")); self.combo_type = ComboBox()
        self.combo_type.addItems(["9x9 (81孔标准盒)", "10x10 (100孔密集盒)", "12x8 (96孔板/PCR管架)", "12x5 (60孔标准试管架)"]); layout.addWidget(self.combo_type)
        layout.addStretch(1); btn_box = QHBoxLayout(); btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject); btn_ok = PrimaryPushButton("确定放入"); btn_ok.clicked.connect(self.accept)
        btn_box.addStretch(); btn_box.addWidget(btn_cancel); btn_box.addWidget(btn_ok); layout.addLayout(btn_box)
    def get_data(self):
        name = self.input_name.text().strip() or "未命名盒子"; s = self.combo_type.currentText()
        itype = "9x9" if "9x9" in s else ("10x10" if "10x10" in s else ("12x8" if "12x8" in s else "12x5"))
        return {"name": name, "type": itype}

# ==========================================
# 🚀 神级更新一：一键出库对话框
# ==========================================
class CheckoutDialog(QDialog):
    def __init__(self, current_vol, unit, parent=None):
        super().__init__(parent); self.setWindowTitle("📤 样本消耗/出库"); self.setFixedSize(300, 200); self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self); layout.addWidget(SubtitleLabel(f"当前余量: {current_vol} {unit}"))
        layout.addSpacing(10); layout.addWidget(StrongBodyLabel("本次消耗体积:"))
        
        vol_layout = QHBoxLayout()
        self.spin_consume = DoubleSpinBox(); self.spin_consume.setRange(0.1, current_vol); self.spin_consume.setDecimals(1); self.spin_consume.setValue(1.0)
        vol_layout.addWidget(self.spin_consume); vol_layout.addWidget(BodyLabel(unit))
        layout.addLayout(vol_layout)
        
        self.chk_ft = CheckBox("☑️ 导致一次冻融 (Freeze-Thaw)"); self.chk_ft.setChecked(True)
        self.chk_ft.setStyleSheet("color: #D83B01; font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.chk_ft); layout.addStretch(1)
        
        btn_box = QHBoxLayout(); btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject)
        btn_ok = PrimaryPushButton("确定扣减"); btn_ok.clicked.connect(self.accept)
        btn_box.addStretch(); btn_box.addWidget(btn_cancel); btn_box.addWidget(btn_ok); layout.addLayout(btn_box)
        
    def get_data(self): return self.spin_consume.value(), self.chk_ft.isChecked()

# ==========================================
# 🚀 神级更新二：支持动态属性变形的表单
# ==========================================
class SampleItemDialog(QDialog):
    def __init__(self, well_id=None, existing_data=None, parent=None):
        super().__init__(parent)
        title = f"编辑孔位: {well_id}" if well_id else "添加散装件"
        self.setWindowTitle(title); self.setFixedSize(400, 580); self.setStyleSheet("background: white;")
        self.is_delete = False; layout = QVBoxLayout(self); layout.setSpacing(8)
        header = SubtitleLabel(f"📍 {well_id if well_id else '散装区'} 样本档案"); header.setStyleSheet("color: #0078D7; font-weight: bold;"); layout.addWidget(header); layout.addSpacing(5)
        
        layout.addWidget(StrongBodyLabel("样本名称 (必填):")); self.input_name = LineEdit(); layout.addWidget(self.input_name)
        layout.addWidget(StrongBodyLabel("样本大类:")); self.combo_type = ComboBox(); self.combo_type.addItems(["🧬 质粒 (Plasmid)", "🧪 蛋白 (Protein)", "🧫 细胞 (Cell)", "🦠 菌种 (Bacteria)", "💧 核酸 (DNA/RNA)", "📦 其他耗材"])
        layout.addWidget(self.combo_type)
        
        # 💡 动态表单容器区
        self.dynamic_container = QWidget(); self.dynamic_layout = QVBoxLayout(self.dynamic_container); self.dynamic_layout.setContentsMargins(0, 5, 0, 5)
        self.custom_widgets = {} # 用于存储动态生成的组件
        layout.addWidget(self.dynamic_container)
        self.combo_type.currentTextChanged.connect(self._on_type_changed)
        
        vol_layout = QHBoxLayout(); self.spin_vol = DoubleSpinBox(); self.spin_vol.setRange(0, 9999); self.spin_vol.setDecimals(1); self.spin_vol.setValue(0)
        self.combo_unit = ComboBox(); self.combo_unit.addItems(["μL", "mL", "L", "管", "盒"])
        vol_layout.addWidget(BodyLabel("当前余量:")); vol_layout.addWidget(self.spin_vol, 1); vol_layout.addWidget(self.combo_unit); layout.addLayout(vol_layout)
        
        ft_layout = QHBoxLayout(); self.spin_ft = SpinBox(); self.spin_ft.setRange(0, 100); self.spin_ft.setValue(0)
        btn_ft_add = PushButton("❄️ +1"); btn_ft_add.clicked.connect(lambda: self.spin_ft.setValue(self.spin_ft.value() + 1)); btn_ft_add.setStyleSheet("color: #0078D7; font-weight: bold;")
        ft_layout.addWidget(BodyLabel("冻融次数:")); ft_layout.addWidget(self.spin_ft, 1); ft_layout.addWidget(btn_ft_add); layout.addLayout(ft_layout)
        
        layout.addWidget(StrongBodyLabel("所有人 / 日期:")); self.input_owner = LineEdit(); layout.addWidget(self.input_owner)
        layout.addWidget(StrongBodyLabel("备注信息:")); self.input_notes = TextEdit(); self.input_notes.setFixedHeight(60); layout.addWidget(self.input_notes)
        
        layout.addStretch(1); btn_layout = QHBoxLayout()
        if existing_data:
            # 💡 一键出库按钮
            btn_checkout = PushButton("📤 消耗/出库")
            btn_checkout.setStyleSheet("color: #107C10; font-weight: bold; border: 1px solid #107C10;")
            btn_checkout.clicked.connect(self._handle_checkout)
            btn_layout.addWidget(btn_checkout)
            
            self.btn_del = PushButton("🗑️ 删除"); self.btn_del.setStyleSheet("color: #D83B01;"); self.btn_del.clicked.connect(self.on_delete); btn_layout.addWidget(self.btn_del)
            
        btn_layout.addStretch(1); btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject); btn_save = PrimaryPushButton("💾 保存"); btn_save.clicked.connect(self.accept)
        btn_layout.addWidget(btn_cancel); btn_layout.addWidget(btn_save); layout.addLayout(btn_layout)

        if existing_data:
            self.input_name.setText(existing_data.get("name", ""))
            self.combo_type.setCurrentText(existing_data.get("type", "🧬 质粒 (Plasmid)"))
            self.spin_vol.setValue(float(existing_data.get("vol", 0))); self.combo_unit.setCurrentText(existing_data.get("unit", "μL"))
            self.spin_ft.setValue(int(existing_data.get("ft", 0))); self.input_owner.setText(existing_data.get("owner", "")); self.input_notes.setPlainText(existing_data.get("notes", ""))
            
            # 还原动态属性
            self._on_type_changed(self.combo_type.currentText())
            custom_attrs = existing_data.get("custom_attrs", {})
            for k, v in custom_attrs.items():
                if k in self.custom_widgets:
                    widget = self.custom_widgets[k]
                    if isinstance(widget, LineEdit): widget.setText(str(v))
                    elif isinstance(widget, DoubleSpinBox): widget.setValue(float(v))
                    elif isinstance(widget, CheckBox): widget.setChecked(bool(v))
        else:
            self._on_type_changed(self.combo_type.currentText())

    def _on_type_changed(self, text):
        """💡 动态变形表单引擎 (已修复嵌套布局重叠Bug)"""
        
        # 1. 极其严谨的递归清理黑魔法
        def clear_layout(layout):
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    widget = item.widget()
                    if widget:
                        widget.deleteLater()
                    else:
                        sub_layout = item.layout()
                        if sub_layout:
                            clear_layout(sub_layout)
                            sub_layout.deleteLater()
                            
        clear_layout(self.dynamic_layout)
        self.custom_widgets = {}

        # 2. 重新加载对应表单
        if "蛋白" in text:
            row = QHBoxLayout()
            row.addWidget(BodyLabel("浓度(mg/mL):")); sp_conc = DoubleSpinBox(); sp_conc.setRange(0, 9999); sp_conc.setDecimals(2)
            chk_sec = CheckBox("☑️ 已过分子筛(SEC)")
            row.addWidget(sp_conc); row.addWidget(chk_sec); self.dynamic_layout.addLayout(row)
            self.custom_widgets['浓度'] = sp_conc; self.custom_widgets['SEC'] = chk_sec
            
        elif "质粒" in text:
            row = QHBoxLayout()
            row.addWidget(BodyLabel("抗性(Res):")); le_res = LineEdit()
            row.addWidget(le_res); self.dynamic_layout.addLayout(row)
            self.custom_widgets['抗性'] = le_res
            
        elif "细胞" in text:
            row = QHBoxLayout()
            row.addWidget(BodyLabel("代数(Passage):")); le_pas = LineEdit()
            row.addWidget(le_pas); self.dynamic_layout.addLayout(row)
            self.custom_widgets['代数'] = le_pas

    def _handle_checkout(self):
        """💡 触发一键出库工作流"""
        dlg = CheckoutDialog(self.spin_vol.value(), self.combo_unit.currentText(), self)
        if dlg.exec_():
            consume_vol, add_ft = dlg.get_data()
            self.spin_vol.setValue(self.spin_vol.value() - consume_vol)
            if add_ft: self.spin_ft.setValue(self.spin_ft.value() + 1)
            # 自动保存闭环！
            self.accept()

    def on_delete(self): self.is_delete = True; self.accept()
    
    def get_data(self): 
        # 收集固定数据
        data = {
            "name": self.input_name.text().strip(), "type": self.combo_type.currentText(), 
            "vol": self.spin_vol.value(), "unit": self.combo_unit.currentText(), 
            "ft": self.spin_ft.value(), "owner": self.input_owner.text().strip(), 
            "notes": self.input_notes.toPlainText().strip(),
            "custom_attrs": {}
        }
        # 收集动态形态数据
        for k, w in self.custom_widgets.items():
            if isinstance(w, DoubleSpinBox): data["custom_attrs"][k] = w.value()
            elif isinstance(w, CheckBox): data["custom_attrs"][k] = w.isChecked()
            elif isinstance(w, LineEdit): data["custom_attrs"][k] = w.text().strip()
        return data

# ==========================================
# (原有大厅卡片与管理器骨架省略，直接复用...)
# ==========================================
class EquipmentCard(CardWidget):
    sig_card_clicked = pyqtSignal(str)
    def __init__(self, disp_name, node_id, icon_path=FIF.CALENDAR, desc="", parent=None):
        super().__init__(parent); self.node_id = node_id; self.setFixedSize(240, 220) 
        self.setStyleSheet("EquipmentCard { background-color: white; border: 1px solid #e0e0e0; border-radius: 10px; } EquipmentCard:hover { border: 1px solid #0078D7; background-color: #f8fbff; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(20, 20, 20, 15)
        icon_widget = IconWidget(icon_path, self); icon_widget.setFixedSize(50, 50); layout.addWidget(icon_widget, 0, Qt.AlignHCenter); layout.addSpacing(10)
        lbl_name = SubtitleLabel(disp_name); lbl_name.setAlignment(Qt.AlignCenter); lbl_name.setWordWrap(True); layout.addWidget(lbl_name)
        if desc:
            layout.addSpacing(5); lbl_desc = BodyLabel(desc); lbl_desc.setAlignment(Qt.AlignCenter); lbl_desc.setWordWrap(True); lbl_desc.setStyleSheet("color: #666; font-size: 11px; line-height: 1.3;"); layout.addWidget(lbl_desc)
        layout.addStretch(1)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.sig_card_clicked.emit(self.node_id)
        super().mousePressEvent(event)

class SampleHubUI(QWidget):
    sig_equipment_clicked = pyqtSignal(str); sig_drill_down = pyqtSignal(str, str) 
    sig_well_clicked = pyqtSignal(str, str); sig_batch_add_requested = pyqtSignal(str, list); sig_batch_delete_requested = pyqtSignal(str, list) 
    sig_freeform_add = pyqtSignal(str); sig_freeform_delete = pyqtSignal(str, str) 
    sig_alias_changed = pyqtSignal(str, str); sig_print_pdf_requested = pyqtSignal()
    sig_add_container = pyqtSignal(str, int, int); sig_delete_container = pyqtSignal(str, str)
    sig_add_inner_box = pyqtSignal(str); sig_delete_inner_box = pyqtSignal(str, str)
    sig_resize_equipment = pyqtSignal(str, int, int) 
    sig_add_equipment = pyqtSignal(dict)
    sig_export_excel_requested = pyqtSignal(str)
    sig_import_excel_requested = pyqtSignal(str)
    # 🚀 剪贴板粘贴信号
    sig_paste_clipboard_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("SampleHubUI"); self.alias_dict = {}; self._setup_ui()
    def _setup_context_menu(self, widget, path, default_name, extra_actions=None):
        widget.setContextMenuPolicy(Qt.CustomContextMenu); widget.customContextMenuRequested.connect(lambda pos: self._pop_rename_menu(widget, pos, path, default_name, extra_actions))
    def _pop_rename_menu(self, widget, pos, path, default_name, extra_actions):
        menu = RoundMenu(parent=self); action = Action(FIF.EDIT, '✏️ 自定义名称', self); action.triggered.connect(lambda: self._show_rename_dialog(path, default_name)); menu.addAction(action)
        if extra_actions:
            menu.addSeparator()
            for act in extra_actions: menu.addAction(act)
        menu.exec_(widget.mapToGlobal(pos))
    def _show_rename_dialog(self, path, default_name):
        dlg = RenameDialog(self.alias_dict.get(path, ""), self)
        if dlg.exec_(): self.sig_alias_changed.emit(path, dlg.get_name())
    def _set_breadcrumb(self, path):
        parts = path.split('/'); aliased = []; acc = ""
        for p in parts:
            acc = f"{acc}/{p}" if acc else p; aliased.append(self.alias_dict.get(acc, p))
        self.lbl_breadcrumb.setText("🧪 全局视图 > " + " > ".join(aliased))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(20, 20, 20, 20); main_layout.setSpacing(15)
        top_layout = QHBoxLayout(); self.btn_back = PushButton("🔙 返回上一级", icon=FIF.RETURN); self.btn_back.clicked.connect(self._go_back); self.btn_back.hide(); top_layout.addWidget(self.btn_back)
        self.lbl_breadcrumb = SubtitleLabel("🧪 全局样本管理中心"); top_layout.addSpacing(20); top_layout.addWidget(self.lbl_breadcrumb); top_layout.addStretch(1)
        self.btn_print = PushButton("🖨️ 导出清单"); self.btn_print.clicked.connect(self.sig_print_pdf_requested.emit); top_layout.addWidget(self.btn_print); main_layout.addLayout(top_layout)
        self.stack = QStackedWidget(self)
        self.home_widget = QWidget(); self.home_layout = QGridLayout(self.home_widget); self.home_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop); self.stack.addWidget(self.home_widget)
        self.detail_scroll = ScrollArea(); self.detail_scroll.setWidgetResizable(True); self.detail_scroll.setFrameShape(QFrame.NoFrame); self.stack.addWidget(self.detail_scroll)
        self.box_scroll = ScrollArea(); self.box_scroll.setWidgetResizable(True); self.box_scroll.setFrameShape(QFrame.NoFrame); self.stack.addWidget(self.box_scroll)
        self.layer_scroll = ScrollArea(); self.layer_scroll.setWidgetResizable(True); self.layer_scroll.setFrameShape(QFrame.NoFrame); self.stack.addWidget(self.layer_scroll)
        self.freeform_scroll = ScrollArea(); self.freeform_scroll.setWidgetResizable(True); self.freeform_scroll.setFrameShape(QFrame.NoFrame); self.stack.addWidget(self.freeform_scroll)
        main_layout.addWidget(self.stack)

    def refresh_home_view(self, equipments, aliases):
        self.alias_dict = aliases
        while self.home_layout.count():
            item = self.home_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        count = 0
        for eid, eq in equipments.items():
            icon = FIF.CALENDAR if "冰箱" in eq["name"] else (FIF.TILES if "80" in eq["name"] else FIF.FOLDER)
            card = EquipmentCard(self.alias_dict.get(eid, eq["name"]), eid, icon, eq.get("desc", ""))
            card.sig_card_clicked.connect(self.sig_equipment_clicked.emit)
            self._setup_context_menu(card, eid, eq["name"]); self.home_layout.addWidget(card, count // 4, count % 4); count += 1
        btn_add_eq = PushButton("➕\n登记新物理设备"); btn_add_eq.setFixedSize(240, 220)
        btn_add_eq.setStyleSheet("PushButton { background-color: #fafafa; border: 2px dashed #ccc; border-radius: 10px; color: #999; font-size: 16px; font-weight: bold; } PushButton:hover { border: 2px dashed #0078D7; color: #0078D7; background-color: #f0f8ff; }")
        btn_add_eq.clicked.connect(lambda: self.sig_add_equipment.emit(EquipmentSetupDialog(self).get_data()) if EquipmentSetupDialog(self).exec_() else None)
        self.home_layout.addWidget(btn_add_eq, count // 4, count % 4)

    def _go_back(self):
        curr = self.stack.currentIndex(); parts = self.lbl_breadcrumb.text().split(" > ")
        if curr == 2: self.stack.setCurrentIndex(3); self.lbl_breadcrumb.setText(" > ".join(parts[:-1]))
        elif curr == 3 or curr == 4: self.stack.setCurrentIndex(1); self.lbl_breadcrumb.setText(" > ".join(parts[:2]))
        elif curr == 1: self.stack.setCurrentIndex(0); self.btn_back.hide(); self.lbl_breadcrumb.setText("🧪 全局样本管理中心")

    def render_detail_view(self, equip_id, eq_data, aliases):
        self.alias_dict = aliases; self.stack.setCurrentIndex(1); self.btn_back.show(); self._set_breadcrumb(equip_id)
        new_detail_widget = QWidget(); new_detail_layout = QVBoxLayout(new_detail_widget); new_detail_layout.setAlignment(Qt.AlignTop)
        layout_type = eq_data.get("layout", "Grid")
        if layout_type != "Grid": layout_type = "Grid" 

        if layout_type == "Grid":
            grid = QGridLayout(); grid.setSpacing(15); rows = eq_data.get("rows", 5); cols = eq_data.get("cols", 6)
            containers = eq_data.get("containers", {}); occupied = [[False] * cols for _ in range(rows)]
            row_zones = eq_data.get("row_zones", {})
            ui_row_current = 0; ui_row_map = {}
            for r in range(rows):
                if str(r) in row_zones:
                    z_info = row_zones[str(r)]
                    lbl = StrongBodyLabel(z_info.get("name", "分区")); color = z_info.get("color", "#333")
                    lbl.setStyleSheet(f"color: {color}; font-size: 15px; border-bottom: 1px solid {color}; padding-bottom: 5px; margin-top: 10px;")
                    grid.addWidget(lbl, ui_row_current, 0, 1, cols)
                    ui_row_current += 1
                ui_row_map[r] = ui_row_current; ui_row_current += 1

            for cid, cont in containers.items():
                r, c, rs, cs = cont.get("r",0), cont.get("c",0), cont.get("rs",1), cont.get("cs",1)
                for ir in range(r, r + rs):
                    for ic in range(c, c + cs):
                        if ir < rows and ic < cols: occupied[ir][ic] = True
                
                c_path = f"{equip_id}/{cid}"; disp_c = self.alias_dict.get(c_path, cont["name"])
                btn = PushButton(); btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); btn.setMinimumSize(120, 100)
                if rs > 1 or cs > 1:
                    btn.setText(f"{disp_c}\n(横跨大区)")
                    btn.setStyleSheet("PushButton { background-color: #FFF8DC; border: 1px dashed #F4A460; border-radius: 6px; color: #D2691E; font-weight: bold; font-size: 13px; } PushButton:hover { border-color: #CD853F; background-color: #FFEBCD; }")
                else:
                    itype = cont.get("type", "freeform")
                    if itype == "rack":
                        btn.setText(f"{disp_c}\n[金属架: {cont.get('layers',5)}层{cont.get('boxes',4)}盒]")
                        btn.setStyleSheet("PushButton { background-color: #F8F9FA; border: 1px solid #CED4DA; border-radius: 6px; color: #495057; font-weight: bold; } PushButton:hover { border: 1px solid #0078D4; background-color: #E9ECEF; }")
                    else:
                        desc = f"[{itype} 孔板架]" if "12x" in itype else (f"[{itype} 方格盒]" if "x" in itype else "[散装/隔板区]")
                        btn.setText(f"{disp_c}\n{desc}")
                        btn.setStyleSheet("PushButton { background-color: #F0F8FF; border: 1px solid #B3D4FC; border-radius: 6px; color: #0056B3; font-weight: bold; } PushButton:hover { border: 1px solid #0078D4; background-color: #E0F2FE; }")
                        
                act_del = Action(FIF.DELETE, '🗑️ 拆除该物理容器', self); act_del.triggered.connect(lambda checked, e=equip_id, i=cid: self.sig_delete_container.emit(e, i))
                self._setup_context_menu(btn, c_path, cont["name"], [act_del])
                itype = cont.get("type", "freeform")
                if itype == "rack": btn.clicked.connect(lambda _, p=c_path: self.sig_drill_down.emit(p, "boxes"))
                elif "x" in itype: btn.clicked.connect(lambda _, p=c_path: self.sig_drill_down.emit(p, "9x9"))
                else: btn.clicked.connect(lambda _, p=c_path: self.sig_drill_down.emit(p, "freeform"))
                ui_rs = ui_row_map[r + rs - 1] - ui_row_map[r] + 1 if r + rs - 1 < rows else rs
                grid.addWidget(btn, ui_row_map[r], c, ui_rs, cs)
                
            for r in range(rows):
                for c in range(cols):
                    if not occupied[r][c]:
                        btn_empty = PushButton("➕\n空闲位置"); btn_empty.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding); btn_empty.setMinimumSize(120, 100)
                        btn_empty.setStyleSheet("PushButton { background-color: transparent; border: 1px dashed #ccc; border-radius: 6px; color: #aaa; font-weight: bold; } PushButton:hover { border: 1px dashed #0078D7; color: #0078D7; background-color: #f8fbff; }")
                        btn_empty.clicked.connect(lambda _, er=r, ec=c: self.sig_add_container.emit(equip_id, er, ec))
                        grid.addWidget(btn_empty, ui_row_map[r], c, 1, 1)

            bottom_bar = QHBoxLayout(); btn_add_row = PushButton("➕ 向下扩增"); btn_add_row.setFixedHeight(30)
            btn_add_row.setStyleSheet("PushButton { background-color: #f8fbff; border: 1px dashed #0078D7; border-radius: 4px; color: #0078D7; font-weight: bold; } PushButton:hover { background-color: #e0f2fe; }")
            btn_sub_row = PushButton("🗑️ 削减底部"); btn_sub_row.setFixedHeight(30)
            btn_sub_row.setStyleSheet("PushButton { background-color: #fff8f8; border: 1px dashed #ea4335; border-radius: 4px; color: #ea4335; font-weight: bold; } PushButton:hover { background-color: #fce8e6; }")
            bottom_bar.addWidget(btn_add_row, 3); bottom_bar.addWidget(btn_sub_row, 1)
            grid.addLayout(bottom_bar, ui_row_current, 0, 1, cols)

            right_bar = QVBoxLayout(); btn_add_col = PushButton("➕\n扩\n列"); btn_add_col.setFixedWidth(30)
            btn_add_col.setStyleSheet("PushButton { background-color: #f8fbff; border: 1px dashed #0078D7; border-radius: 4px; color: #0078D7; font-weight: bold; } PushButton:hover { background-color: #e0f2fe; }")
            btn_sub_col = PushButton("🗑️\n削\n列"); btn_sub_col.setFixedWidth(30)
            btn_sub_col.setStyleSheet("PushButton { background-color: #fff8f8; border: 1px dashed #ea4335; border-radius: 4px; color: #ea4335; font-weight: bold; } PushButton:hover { background-color: #fce8e6; }")
            right_bar.addWidget(btn_add_col, 3); right_bar.addWidget(btn_sub_col, 1)
            grid.addLayout(right_bar, 0, cols, ui_row_current, 1)

            btn_add_row.clicked.connect(lambda: self.sig_resize_equipment.emit(equip_id, 1, 0)); btn_sub_row.clicked.connect(lambda: self.sig_resize_equipment.emit(equip_id, -1, 0))
            btn_add_col.clicked.connect(lambda: self.sig_resize_equipment.emit(equip_id, 0, 1)); btn_sub_col.clicked.connect(lambda: self.sig_resize_equipment.emit(equip_id, 0, -1))
            for r in range(rows): grid.setRowStretch(ui_row_map[r], 1)
            for c in range(cols): grid.setColumnStretch(c, 1)
            new_detail_layout.addLayout(grid)

        new_detail_layout.addStretch(1); self.detail_scroll.setWidget(new_detail_widget)

    def render_layer_boxes_view(self, rack_path, aliases):
        self.alias_dict = aliases; self.stack.setCurrentIndex(3); self.btn_back.show(); self._set_breadcrumb(rack_path)
        new_widget = QWidget(); new_layout = QVBoxLayout(new_widget); new_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        new_layout.addWidget(SubtitleLabel("冻存架 (并排纵向透视图)")); new_layout.addSpacing(20)
        equip_id = rack_path.split('/')[0]; cid = rack_path.split('/')[1]; topology = {}
        try:
            from controllers.ctrl_sample_hub import SampleHubLogic
            topology = SampleHubLogic().equipments.get(equip_id, {})
        except: pass
        layers_count = topology.get("containers", {}).get(cid, {}).get("layers", 5) if topology else 5
        boxes_per_layer = topology.get("containers", {}).get(cid, {}).get("boxes", 4) if topology else 4
        
        drawers_row = QHBoxLayout(); drawers_row.setSpacing(40)
        for l in range(layers_count):
            rack_metal_frame = QFrame()
            rack_metal_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; }")
            drawer_vbox = QVBoxLayout(rack_metal_frame); drawer_vbox.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
            lbl_title = StrongBodyLabel(f"第 {l+1} 层"); lbl_title.setStyleSheet("color: #333; font-size: 14px;"); drawer_vbox.addWidget(lbl_title, 0, Qt.AlignHCenter)
            lbl_deep = BodyLabel("↑ 内部"); lbl_deep.setStyleSheet("color: #999; font-size: 11px;"); drawer_vbox.addWidget(lbl_deep, 0, Qt.AlignHCenter); drawer_vbox.addSpacing(10)
            for b in range(boxes_per_layer, 0, -1):
                box_path = f"{rack_path}/层{l+1}_盒{b}"; disp_box = self.alias_dict.get(box_path, f"盒 {b}"); btn = PrimaryPushButton(f"🧊 {disp_box}"); btn.setFixedSize(140, 60)
                btn.setStyleSheet("PushButton { background-color: #ffffff; border: 1px solid #b3d4fc; color: #0078D7; font-weight: bold; border-radius: 6px; } PushButton:hover { background-color: #e0f2fe; }")
                self._setup_context_menu(btn, box_path, f"盒 {b}"); btn.clicked.connect(lambda _, p=box_path: self.sig_drill_down.emit(p, "9x9")); drawer_vbox.addWidget(btn)
            drawer_vbox.addSpacing(10); lbl_front = BodyLabel("↓ 外部"); lbl_front.setStyleSheet("color: #999; font-size: 11px;"); drawer_vbox.addWidget(lbl_front, 0, Qt.AlignHCenter)
            drawers_row.addWidget(rack_metal_frame)
        new_layout.addLayout(drawers_row); new_layout.addStretch(1); self.layer_scroll.setWidget(new_widget)

    # ==========================================
    # 💡 散装视图：呈现生命周期追踪
    # ==========================================
    def render_freeform_view(self, list_path, items_data, inner_boxes, aliases):
        self.alias_dict = aliases; self.stack.setCurrentIndex(4); self.btn_back.show(); self._set_breadcrumb(list_path)
        new_widget = QWidget(); new_layout = QVBoxLayout(new_widget); new_layout.setAlignment(Qt.AlignTop)
        disp_title = self.alias_dict.get(list_path, list_path.split('/')[-1]); header_layout = QHBoxLayout(); header_layout.addWidget(SubtitleLabel(f"存放区: {disp_title}")); header_layout.addStretch(1)
        btn_add_box = PrimaryPushButton("📦 放入内部冻存盒/管架"); btn_add_box.clicked.connect(lambda: self.sig_add_inner_box.emit(list_path))
        btn_add_item = PushButton("🧪 存入散装物品"); btn_add_item.clicked.connect(lambda: self.sig_freeform_add.emit(list_path))
        header_layout.addWidget(btn_add_box); header_layout.addWidget(btn_add_item); new_layout.addLayout(header_layout); new_layout.addSpacing(15)
        
        if inner_boxes:
            new_layout.addWidget(StrongBodyLabel("📁 内部收纳盒/管架：")); box_grid = QGridLayout(); box_grid.setSpacing(10)
            for i, (bid, binfo) in enumerate(inner_boxes.items()):
                bpath = f"{list_path}/{bid}"; bname = self.alias_dict.get(bpath, binfo["name"]); btn = PushButton(f"🧊 {bname}\n({binfo['type']})"); btn.setFixedSize(160, 60)
                btn.setStyleSheet("PushButton { background-color: #f0f8ff; border: 1px solid #b3d4fc; border-radius: 6px; color: #0056b3; font-weight: bold; } PushButton:hover { border: 1px solid #0078d4; background-color: #e0f2fe; }")
                act_del = Action(FIF.DELETE, '🗑️ 移出该收纳盒', self); act_del.triggered.connect(lambda checked, p=list_path, i=bid: self.sig_delete_inner_box.emit(p, i))
                self._setup_context_menu(btn, bpath, binfo["name"], [act_del]); btn.clicked.connect(lambda _, p=bpath: self.sig_drill_down.emit(p, "9x9")); box_grid.addWidget(btn, i // 4, i % 4)
            new_layout.addLayout(box_grid); new_layout.addSpacing(15)
            
        new_layout.addWidget(StrongBodyLabel("🧪 零散存放物品："))
        if not items_data:
            empty_lbl = BodyLabel("该区域目前空空如也。"); empty_lbl.setStyleSheet("color: #888;"); empty_lbl.setAlignment(Qt.AlignCenter); new_layout.addWidget(empty_lbl)
        else:
            for uid, info in items_data.items():
                item_card = QFrame(); item_card.setStyleSheet("QFrame { background-color: white; border: 1px solid #e0e0e0; border-radius: 4px; }")
                item_layout = QHBoxLayout(item_card); item_layout.setContentsMargins(10, 6, 10, 6)
                info_layout = QVBoxLayout(); info_layout.setSpacing(2)
                
                # 💡 检测冻融次数预警
                ft_count = int(info.get("ft", 0))
                warn_text = " <span style='color:red;'>⚠️易降解</span>" if ft_count >= 5 else ""
                
                lbl_name = StrongBodyLabel(info.get("name", "未命名物品") + warn_text)
                lbl_name.setTextFormat(Qt.RichText) # 允许渲染 HTML 红字
                lbl_name.setStyleSheet("color: #0078D7; font-size: 13px;")
                
                # 显示体积和冻融
                vol = info.get('vol', 0); unit = info.get('unit', 'μL')
                lbl_details = BodyLabel(f"[{info.get('type','')}] 余量: {vol}{unit} | 冻融: {ft_count}次 | 归属: {info.get('owner','')}"); lbl_details.setStyleSheet("color: #666; font-size: 11px;")
                
                info_layout.addWidget(lbl_name); info_layout.addWidget(lbl_details); item_layout.addLayout(info_layout); item_layout.addStretch(1)
                btn_del = PushButton("🗑️ 删除"); btn_del.setStyleSheet("color: #D83B01; font-size: 12px;"); btn_del.setFixedSize(60, 30); btn_del.clicked.connect(lambda _, p=list_path, i=uid: self.sig_freeform_delete.emit(p, i)); item_layout.addWidget(btn_del); new_layout.addWidget(item_card)
        new_layout.addStretch(1); self.freeform_scroll.setWidget(new_widget)

    # ==========================================
    # 🌟 神级更新三：带橡皮筋框选、剪贴板和动态Tooltip的网格视图
    # ==========================================
    def render_grid_9x9_view(self, box_path, box_data, aliases):
        self.alias_dict = aliases; self.stack.setCurrentIndex(2); self.btn_back.show(); self._set_breadcrumb(box_path)
        new_box_widget = QWidget(); new_box_layout = QVBoxLayout(new_box_widget); new_box_layout.setAlignment(Qt.AlignTop) 
        top_bar = QHBoxLayout(); disp_title = self.alias_dict.get(box_path, box_path.split('/')[-1]); top_bar.addWidget(SubtitleLabel(f"内部矩阵: {disp_title}")); top_bar.addStretch(1)
        
        self.is_batch_mode = False; self.batch_selected_wells = set()
        btn_batch_toggle = PushButton("🔘 开启拉框/批量模式"); btn_batch_add = PrimaryPushButton("🚀 批量填入 (0)"); btn_batch_add.hide(); btn_batch_del = PushButton("🗑️ 批量清空 (0)"); btn_batch_del.setStyleSheet("color: white; background-color: #D83B01; border-radius: 4px;"); btn_batch_del.hide()
        
        btn_import_excel = PushButton("📥 Excel导入"); btn_import_excel.clicked.connect(lambda: self.sig_import_excel_requested.emit(box_path))
        btn_export_excel = PushButton("📤 导出模板"); btn_export_excel.clicked.connect(lambda: self.sig_export_excel_requested.emit(box_path))
        btn_paste_clipboard = PushButton("📋 从剪贴板粘贴矩阵"); btn_paste_clipboard.setStyleSheet("color: white; font-weight: bold; background-color: #881798; border: none; border-radius: 4px;")
        btn_paste_clipboard.clicked.connect(lambda: self.sig_paste_clipboard_requested.emit(box_path))
        
        top_bar.addWidget(btn_paste_clipboard); top_bar.addSpacing(10)
        top_bar.addWidget(btn_export_excel); top_bar.addWidget(btn_import_excel); top_bar.addSpacing(15)
        top_bar.addWidget(btn_batch_toggle); top_bar.addWidget(btn_batch_add); top_bar.addWidget(btn_batch_del)
        new_box_layout.addLayout(top_bar); new_box_layout.addSpacing(20)
        
        grid_wrapper = QHBoxLayout(); grid_wrapper.addStretch(1)
        
        # 💡 使用全新的橡皮筋框选容器
        grid_container = GridContainer()
        grid = QGridLayout(grid_container); grid.setSpacing(5)
        
        is_10x10 = "10x10" in box_path or "10x10" in disp_title; is_12x8 = "12x8" in box_path or "12x8" in disp_title or "96孔" in disp_title or "8x12" in disp_title; is_12x5 = "12x5" in box_path or "12x5" in disp_title or "60孔" in disp_title
        if is_10x10: rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]; cols = [str(i) for i in range(1, 11)]
        elif is_12x8: rows = ["A", "B", "C", "D", "E", "F", "G", "H"]; cols = [str(i) for i in range(1, 13)]
        elif is_12x5: rows = ["A", "B", "C", "D", "E"]; cols = [str(i) for i in range(1, 13)]
        else: rows = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]; cols = [str(i) for i in range(1, 10)]
            
        for j, c in enumerate(cols): lbl = BodyLabel(c); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet("color: #999; font-weight: bold;"); lbl.setFixedSize(48, 30); grid.addWidget(lbl, 0, j+1)
        for i, r in enumerate(rows): lbl = BodyLabel(r); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet("color: #999; font-weight: bold;"); lbl.setFixedSize(30, 48); grid.addWidget(lbl, i+1, 0)
        
        def update_btn_style(btn, wid, has):
            if wid in self.batch_selected_wells: 
                btn.setText("已框选"); btn.setStyleSheet("background-color: #FFD700; color: #B8860B; border-radius: 4px; font-weight: bold; border: 1px solid #FF8C00;"); btn.setToolTip("")
            elif has:
                info = box_data[wid]; item_name = info.get("name", "样本"); t_type = info.get("type", "")
                ft_count = int(info.get("ft", 0)); vol = info.get("vol", 0); unit = info.get("unit", "μL")
                tooltip = f"【{wid}】 {item_name}\n类型: {t_type}\n余量: {vol} {unit}\n冻融次数: {ft_count}次"
                customs = info.get("custom_attrs", {})
                if customs:
                    c_str = "\n".join([f"{k}: {v}" for k, v in customs.items() if str(v).strip()])
                    tooltip += f"\n---\n{c_str}"
                btn.setText(item_name[:3] if ft_count < 5 else f"⚠️\n{item_name[:2]}") 
                btn.setToolTip(tooltip)
                color = "#107C10" if "蛋白" in t_type else ("#D83B01" if "质粒" in t_type else ("#881798" if "细胞" in t_type else "#0078D7"))
                btn.setStyleSheet(f"background-color: {color}; color: white; border-radius: 4px; font-weight: bold; border: 1px solid #005A9E; font-size: 11px;")
            else: btn.setText(""); btn.setStyleSheet("background-color: #fcfcfc; border: 1px dashed #ccc; border-radius: 4px;"); btn.setToolTip("空闲孔位")
            
        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                well_id = f"{r}{c}"; has_item = well_id in box_data
                btn_well = PushButton(); btn_well.setFixedSize(48, 48)
                grid_container.well_widgets[well_id] = btn_well
                update_btn_style(btn_well, well_id, has_item)
                
                # 绑定原生点击信号（非框选模式时触发单孔编辑）
                btn_well.clicked.connect(lambda _, w=well_id: self.sig_well_clicked.emit(box_path, w) if not self.is_batch_mode else None)
                grid.addWidget(btn_well, i+1, j+1)
                
        def toggle_mode():
            self.is_batch_mode = not self.is_batch_mode
            grid_container.is_marquee_mode = self.is_batch_mode
            self.batch_selected_wells.clear()
            btn_batch_add.setVisible(False); btn_batch_del.setVisible(False)
            
            if self.is_batch_mode:
                btn_batch_toggle.setText("🟢 退出框选模式"); btn_batch_toggle.setStyleSheet("color: white; background-color: #107C10;")
                grid_container.setCursor(Qt.CrossCursor) # 变成十字准星瞄准器！
                # ⚠️ 屏蔽按钮自身的拦截，将事件强行还给父容器画框！
                for btn in grid_container.well_widgets.values(): btn.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            else:
                btn_batch_toggle.setText("🔘 开启拉框/批量模式"); btn_batch_toggle.setStyleSheet("")
                grid_container.unsetCursor()
                for btn in grid_container.well_widgets.values(): btn.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                
            for wid, btn in grid_container.well_widgets.items(): update_btn_style(btn, wid, wid in box_data)
            
        def on_marquee_selected(wids):
            # 支持动态反选：本来没选中的加上，选中的去掉
            for wid in wids:
                if wid in self.batch_selected_wells: self.batch_selected_wells.remove(wid)
                else: self.batch_selected_wells.add(wid)
                
            empty_sel = [w for w in self.batch_selected_wells if w not in box_data]
            filled_sel = [w for w in self.batch_selected_wells if w in box_data]
            btn_batch_add.setText(f"🚀 批量填入 ({len(empty_sel)})"); btn_batch_add.setVisible(len(empty_sel) > 0)
            btn_batch_del.setText(f"🗑️ 批量清空 ({len(filled_sel)})"); btn_batch_del.setVisible(len(filled_sel) > 0)
            for wid, btn in grid_container.well_widgets.items(): update_btn_style(btn, wid, wid in box_data)

        btn_batch_toggle.clicked.connect(toggle_mode)
        grid_container.sig_selection_done.connect(on_marquee_selected)
        btn_batch_add.clicked.connect(lambda: self.sig_batch_add_requested.emit(box_path, [w for w in self.batch_selected_wells if w not in box_data]))
        btn_batch_del.clicked.connect(lambda: self.sig_batch_delete_requested.emit(box_path, [w for w in self.batch_selected_wells if w in box_data]))
        
        grid_wrapper.addWidget(grid_container)
        grid_wrapper.addStretch(1); new_box_layout.addLayout(grid_wrapper); new_box_layout.addStretch(1); self.box_scroll.setWidget(new_box_widget)