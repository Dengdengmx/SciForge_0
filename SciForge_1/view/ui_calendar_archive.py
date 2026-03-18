# view/ui_calendar_archive.py
import re
import os
from PyQt5.QtCore import Qt, pyqtSignal, QDate
from PyQt5.QtGui import QTextCursor, QTextDocument
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QSplitter, QFrame, QSizePolicy, QStackedWidget, 
                             QListWidgetItem, QDialog, QHeaderView, 
                             QTableWidgetItem, QAbstractItemView)
from qfluentwidgets import (CardWidget, SubtitleLabel, BodyLabel, PrimaryPushButton,
                            PushButton, TextEdit, FluentIcon as FIF, ComboBox, 
                            ScrollArea, StrongBodyLabel, SegmentedWidget,
                            LineEdit, CheckBox, ListWidget, Slider,
                            SearchLineEdit, TableWidget) # 👈 确保有最后这两个

from core.signals import global_bus

class RichTextELNEditor(TextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                if os.path.exists(filepath):
                    global_bus.send_file_to_eln.emit(filepath)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def insert_image(self, image_path):
        if not os.path.exists(image_path): return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        safe_path = image_path.replace('\\', '/')
        html = f'<br><img src="file:///{safe_path}" width="350"><br>'
        cursor.insertHtml(html)
        self.setTextCursor(cursor)

# ==========================================
# 🚀 联动核心：样本引用与自动化消耗引擎
# ==========================================
class SampleReferenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧪 引用并消耗库存样本")
        self.setFixedSize(700, 450)
        self.setStyleSheet("background: white;")
        self.selected_sample = None
        
        # 实例化天眼，直接去读 SampleHub 的数据
        try:
            from controllers.ctrl_sample_hub import SampleHubLogic
            self.sample_logic = SampleHubLogic()
        except Exception as e:
            print("未能加载样本库:", e)
            self.sample_logic = None

        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. 搜索框
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("键入库存样本名称、管盒号或备注进行搜索...")
        self.search_bar.textChanged.connect(self._do_search)
        layout.addWidget(self.search_bar)
        
        # 2. 结果表格
        self.table = TableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['样本名称', '当前余量', '冻融', '📍 绝对物理位置'])
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.table)
        
        # 3. 消耗设置区
        control_layout = QHBoxLayout()
        control_layout.addWidget(StrongBodyLabel("本次消耗体积:"))
        from qfluentwidgets import DoubleSpinBox
        self.spin_vol = DoubleSpinBox()
        self.spin_vol.setRange(0.0, 9999.0); self.spin_vol.setDecimals(1); self.spin_vol.setValue(1.0)
        self.lbl_unit = BodyLabel("μL")
        
        self.chk_ft = CheckBox("☑️ 记入 1 次冻融")
        self.chk_ft.setChecked(True)
        self.chk_ft.setStyleSheet("color: #D83B01; font-weight: bold; margin-left: 20px;")
        
        control_layout.addWidget(self.spin_vol)
        control_layout.addWidget(self.lbl_unit)
        control_layout.addWidget(self.chk_ft)
        control_layout.addStretch(1)
        layout.addLayout(control_layout)
        
        # 4. 底部按钮
        btn_layout = QHBoxLayout()
        btn_cancel = PushButton("取消"); btn_cancel.clicked.connect(self.reject)
        self.btn_ok = PrimaryPushButton("确定引用并扣减库存")
        self.btn_ok.setEnabled(False) # 没选中不准点
        self.btn_ok.clicked.connect(self.accept)
        btn_layout.addStretch(); btn_layout.addWidget(btn_cancel); btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def _do_search(self, text):
        self.table.setRowCount(0)
        if not text.strip() or not self.sample_logic: return
        results = self.sample_logic.global_search(text)
        
        # 把搜到的数据塞进表格
        self.current_results = results 
        for i, res in enumerate(results):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(res['name']))
            self.table.setItem(i, 1, QTableWidgetItem(f"{res['vol']} {res['unit']}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{res['ft_count']}次"))
            self.table.setItem(i, 3, QTableWidgetItem(res['location_str']))

    def _on_select(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            self.btn_ok.setEnabled(False); return
            
        row = selected_items[0].row()
        self.selected_sample = self.current_results[row]
        
        # 智能动态上限限制
        self.lbl_unit.setText(self.selected_sample['unit'])
        self.spin_vol.setRange(0.0, float(self.selected_sample['vol']))
        self.btn_ok.setEnabled(True)

    def get_data(self):
        if not self.selected_sample: return None
        return {
            "path": self.selected_sample['path'],
            "well_id": self.selected_sample['well_id'],
            "name": self.selected_sample['name'],
            "location_str": self.selected_sample['location_str'],
            "consume_vol": self.spin_vol.value(),
            "unit": self.lbl_unit.text(),
            "add_ft": self.chk_ft.isChecked()
        }
    
class MiniMonthWidget(QFrame):
    clicked = pyqtSignal(int, int) 
    def __init__(self, year, month, parent=None):
        super().__init__(parent); self.year = year; self.month = month; self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("MiniMonthWidget { background-color: white; border: 1px solid #e0e0e0; border-radius: 6px; } MiniMonthWidget:hover { border: 1px solid #0078d4; }")
        layout = QVBoxLayout(self); layout.setContentsMargins(5, 5, 5, 5); layout.setSpacing(2)
        lbl_title = SubtitleLabel(f"{month}月"); lbl_title.setAlignment(Qt.AlignCenter); lbl_title.setStyleSheet("font-size: 13px; font-weight: bold;"); layout.addWidget(lbl_title)
        grid = QGridLayout(); grid.setSpacing(2)
        for i, day in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            lbl = BodyLabel(day); lbl.setAlignment(Qt.AlignCenter); lbl.setStyleSheet("font-size: 10px; color: #888;"); grid.addWidget(lbl, 0, i)
        first_day = QDate(year, month, 1); curr_date = first_day.addDays(-(first_day.dayOfWeek() - 1))
        for row in range(1, 7):
            for col in range(7):
                lbl = BodyLabel(str(curr_date.day())); lbl.setAlignment(Qt.AlignCenter); lbl.setFixedSize(18, 18)
                style = "font-size: 10px; " + ("color: #333;" if curr_date.month() == month else "color: #ccc;")
                if curr_date == QDate.currentDate(): style += "background-color: #0078d4; color: white; border-radius: 9px;"
                lbl.setStyleSheet(style); grid.addWidget(lbl, row, col); curr_date = curr_date.addDays(1)
        layout.addLayout(grid); layout.addStretch(1)
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.clicked.emit(self.year, self.month)
        super().mousePressEvent(event)

class DayCell(QFrame):
    clicked = pyqtSignal(QDate)
    def __init__(self, date, is_current_month=True, parent=None):
        super().__init__(parent); self.date = date; self.is_current_month = is_current_month; self.is_selected = False
        self.setFrameShape(QFrame.Box); self.setLineWidth(0); self.setMinimumHeight(100); self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(8, 8, 8, 8); self.layout.setSpacing(4)
        self.top_layout = QHBoxLayout()
        self.lbl_day = BodyLabel(str(date.day())); self.lbl_day.setFixedSize(24, 24); self.lbl_day.setAlignment(Qt.AlignCenter)
        if date == QDate.currentDate(): self.lbl_day.setStyleSheet("background-color: #0078d4; color: white; border-radius: 12px; font-weight: bold; font-size: 14px;")
        else: self.lbl_day.setStyleSheet(f"color: {'#333' if is_current_month else '#ccc'}; font-weight: bold; font-size: 14px;")
        self.top_layout.addWidget(self.lbl_day); self.top_layout.addStretch(1); self.layout.addLayout(self.top_layout)
        self.lbl_preview = BodyLabel(); self.lbl_preview.setAlignment(Qt.AlignLeft | Qt.AlignTop); self.lbl_preview.setWordWrap(True)
        self.layout.addWidget(self.lbl_preview, 1); self.update_style()

    def set_preview(self, day_data, view_mode=0):
        todos = day_data.get("todo", [])
        main_txt = day_data.get("main", "")
        
        doc = QTextDocument()
        doc.setHtml(main_txt)
        plain_text = doc.toPlainText()
        strictly_clean = plain_text.replace('\ufffc', '').replace('\u2029', '').strip()
        has_image = '<img' in main_txt.lower()
        has_valid_record = bool(strictly_clean) or has_image
        
        exp_tags = set(re.findall(r'【(.*?)】', plain_text))
        badges_html = ""
        for tag in exp_tags:
            color = "#0078D7" if "纯化" in tag else ("#107C10" if "构建" in tag else "#D83B01")
            badges_html += f"<span style='background-color:{color}; color:white; padding:1px 4px; border-radius:3px; font-size:10px; margin-right:2px;'>{tag}</span> "

        if view_mode == 0: 
            preview = badges_html + "<br>" if badges_html else ""
            if todos: preview += f"<span style='color:#0078D7; font-size:11px;'>☑ {len(todos)} 项待办</span><br>"
            
            if has_valid_record and not badges_html: 
                preview += "<span style='color:#666; font-size:11px;'>📝 有记录</span>"
                
            self.lbl_preview.setText(preview)
        else: 
            preview_html = badges_html + "<br>" if badges_html else ""
            preview_lines = []
            for t in todos[:3]: preview_lines.append(f"{'☑' if t.get('done') else '☐'} {t.get('text')}")
            
            if strictly_clean:
                lines = [line for line in strictly_clean.split('\n') if line.strip() and not line.startswith('【')]
                preview_lines.extend(lines[:3])
            elif has_image:
                preview_lines.append("[ 📊 包含图谱/图片记录 ]")
                
            preview_html += "<span style='color:#555; font-size:11px;'>" + "<br>".join(preview_lines).replace('\n', '<br>') + "</span>"
            self.lbl_preview.setText(preview_html)

    def set_selected(self, selected): self.is_selected = selected; self.update_style()
    def update_style(self):
        if self.is_selected: self.setStyleSheet("DayCell { background-color: #e0f2fe; border: 2px solid #0078d4; border-radius: 6px; }")
        else: self.setStyleSheet(f"DayCell {{ background-color: {'white' if self.is_current_month else '#fbfbfb'}; border: 2px solid transparent; border-radius: 6px; }} DayCell:hover {{ background-color: #f3f2f1; }}")
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.clicked.emit(self.date)

class TaskItemWidget(QWidget):
    sig_deleted = pyqtSignal(int); sig_toggled = pyqtSignal(int, bool)
    def __init__(self, text, is_done, idx, parent=None):
        super().__init__(parent); self.idx = idx
        layout = QHBoxLayout(self); layout.setContentsMargins(5, 2, 5, 2)
        self.checkbox = CheckBox(text); self.checkbox.setChecked(is_done); self.checkbox.stateChanged.connect(lambda state: self.sig_toggled.emit(self.idx, state == Qt.Checked))
        layout.addWidget(self.checkbox); layout.addStretch(1)
        self.btn_del = PushButton("×"); self.btn_del.setFixedSize(20, 20); self.btn_del.setStyleSheet("color: red; border: none; background: transparent;")
        self.btn_del.clicked.connect(lambda: self.sig_deleted.emit(self.idx)); layout.addWidget(self.btn_del)
    def set_editable(self, editable): self.checkbox.setEnabled(editable); self.btn_del.setVisible(editable)

class CalendarArchiveUI(QWidget):
    sig_date_changed = pyqtSignal(QDate)       
    sig_save_requested = pyqtSignal(str, list, str, str)
    sig_upload_clicked = pyqtSignal()
    sig_view_changed = pyqtSignal(int); sig_time_nav = pyqtSignal(int); sig_zoom_changed = pyqtSignal(int)
    sig_export_requested = pyqtSignal() 
    
    # 💡 核心新增：专门用于通知底层去渲染 PDF 的独立信号
    # 找到这里：
    sig_export_pdf = pyqtSignal() 
    # 💡 加上这一行：
    sig_ref_sample_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("CalendarArchiveUI")
        self.current_selected_date = QDate.currentDate(); self.is_editing = False; self.current_todos = []
        self.month_cells = []; self.week_cells = []
        self.templates_dict = {} 
        self._setup_ui(); self._set_edit_mode(False)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(10, 10, 10, 10); main_layout.setSpacing(10)

        top_bar = CardWidget(self); top_layout = QHBoxLayout(top_bar); top_layout.setContentsMargins(15, 10, 15, 10)
        top_layout.addWidget(SubtitleLabel("记录与归档工作台"))
        self.btn_export = PushButton("🖨️ 导出区间报告"); self.btn_export.clicked.connect(self.sig_export_requested.emit); top_layout.addSpacing(15); top_layout.addWidget(self.btn_export); top_layout.addSpacing(15)
        self.combo_view = ComboBox(); self.combo_view.addItems(["📅 月视图", "📜 周视图", "🌍 年视图"]); self.combo_view.currentIndexChanged.connect(self.sig_view_changed.emit); top_layout.addWidget(self.combo_view); top_layout.addSpacing(30)
        btn_prev = PushButton("<"); btn_prev.setFixedWidth(40); btn_prev.clicked.connect(lambda: self.sig_time_nav.emit(-1))
        self.lbl_time_nav = SubtitleLabel("加载中..."); self.lbl_time_nav.setAlignment(Qt.AlignCenter); self.lbl_time_nav.setFixedWidth(200)
        btn_next = PushButton(">"); btn_next.setFixedWidth(40); btn_next.clicked.connect(lambda: self.sig_time_nav.emit(1))
        top_layout.addWidget(btn_prev); top_layout.addWidget(self.lbl_time_nav); top_layout.addWidget(btn_next)
        top_layout.addSpacing(30); top_layout.addWidget(BodyLabel("高度缩放:"))
        self.slider_zoom = Slider(Qt.Horizontal); self.slider_zoom.setRange(80, 500); self.slider_zoom.setValue(100); self.slider_zoom.setFixedWidth(150); self.slider_zoom.valueChanged.connect(self.sig_zoom_changed.emit); top_layout.addWidget(self.slider_zoom); top_layout.addStretch(1)
        main_layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle { 
                background-color: #E0E0E0; 
                width: 4px; 
                border-radius: 2px; 
                margin: 4px 2px;
            } 
            QSplitter::handle:hover { 
                background-color: #0078D7; 
            }
        """)
        
        left_panel = CardWidget(); left_layout = QVBoxLayout(left_panel); left_layout.setContentsMargins(5, 5, 5, 5)
        self.stack_views = QStackedWidget()
        
        month_scroll = ScrollArea(); month_scroll.setWidgetResizable(True); month_scroll.setFrameShape(QFrame.NoFrame)
        month_widget = QWidget(); self.month_layout = QVBoxLayout(month_widget)
        self.month_grid = QGridLayout(); self.month_grid.setSpacing(6)
        
        days_label = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for col, day in enumerate(days_label):
            lbl = BodyLabel(day)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background-color: #0078d4; color: white; padding: 6px; border-radius: 4px;")
            self.month_grid.addWidget(lbl, 0, col)
            
        self.month_layout.addLayout(self.month_grid); self.month_layout.addStretch(1)
        month_scroll.setWidget(month_widget); self.stack_views.addWidget(month_scroll)

        week_scroll = ScrollArea(); week_scroll.setWidgetResizable(True); week_scroll.setFrameShape(QFrame.NoFrame)
        week_widget = QWidget(); self.week_layout = QVBoxLayout(week_widget)
        self.week_grid = QGridLayout(); self.week_grid.setSpacing(6)
        
        for col, day in enumerate(days_label):
            lbl = BodyLabel(day)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background-color: #0078d4; color: white; padding: 6px; border-radius: 4px;")
            self.week_grid.addWidget(lbl, 0, col)
            
        self.week_layout.addLayout(self.week_grid); self.week_layout.addStretch(1)
        week_scroll.setWidget(week_widget); self.stack_views.addWidget(week_scroll)

        year_widget = QWidget(); self.year_grid = QGridLayout(year_widget); self.year_grid.setSpacing(10); self.stack_views.addWidget(year_widget); left_layout.addWidget(self.stack_views)
        
        right_panel = CardWidget(); right_layout = QVBoxLayout(right_panel); right_layout.setContentsMargins(15, 15, 15, 15)
        right_panel.setMinimumWidth(300)
        
        header_layout = QHBoxLayout(); self.lbl_detail_date = SubtitleLabel("📝 请选择日期"); header_layout.addWidget(self.lbl_detail_date); header_layout.addStretch(1)
        
        # =======================================================
        # 💡 核心新增：在右侧面板顶部，加入导出单次 PDF 报告的按钮
        # =======================================================
        self.btn_export_pdf = PushButton("📄 导出PDF报告")
        self.btn_export_pdf.clicked.connect(self.sig_export_pdf.emit)
        header_layout.addWidget(self.btn_export_pdf)
        
        self.btn_edit = PrimaryPushButton("🔒 开启编辑", icon=FIF.EDIT); self.btn_edit.clicked.connect(self._toggle_edit); header_layout.addWidget(self.btn_edit); right_layout.addLayout(header_layout)

        self.pivot = SegmentedWidget(self); self.pivot.addItem("todo", "☑️ 待办规划"); self.pivot.addItem("eln", "📝 实验记录"); right_layout.addWidget(self.pivot, 0, Qt.AlignHCenter)
        self.stack_eln = QStackedWidget()
        
        todo_widget = QWidget(); todo_layout = QVBoxLayout(todo_widget); todo_layout.setContentsMargins(0,10,0,0)
        todo_input_layout = QHBoxLayout(); self.input_todo = LineEdit(); self.input_todo.setPlaceholderText("添加新待办... (按回车添加)"); self.input_todo.returnPressed.connect(self._add_todo); todo_input_layout.addWidget(self.input_todo); todo_layout.addLayout(todo_input_layout)
        self.list_todo = ListWidget(); todo_layout.addWidget(self.list_todo); self.stack_eln.addWidget(todo_widget)
        
        eln_widget = QWidget(); eln_layout = QVBoxLayout(eln_widget); eln_layout.setContentsMargins(0,10,0,0)
        preset_layout = QHBoxLayout(); preset_layout.addWidget(StrongBodyLabel("模板预设:"))
        
        self.combo_preset = ComboBox()
        self.combo_preset.addItem("-- 选择插入模板 --")
        self.combo_preset.currentIndexChanged.connect(self._insert_preset)
        preset_layout.addWidget(self.combo_preset)
        preset_layout.addStretch(1)
        self.btn_ref_sample = PushButton("🧪 引用/消耗样本")
        self.btn_ref_sample.setStyleSheet("color: #107C10; font-weight: bold; border: 1px dashed #107C10;")
        self.btn_ref_sample.clicked.connect(self.sig_ref_sample_clicked.emit)
        preset_layout.addWidget(self.btn_ref_sample)
        eln_layout.addLayout(preset_layout)

        self.text_main = RichTextELNEditor()
        self.text_main.setPlaceholderText("支持直接将数据文件拖拽至此框内进行归档计算！\n输入实验步骤、参数、现象..."); 
        self.text_main.textChanged.connect(self._update_assoc_exp_tags)
        eln_layout.addWidget(self.text_main, 2)
        
        archive_panel = CardWidget(); archive_layout = QVBoxLayout(archive_panel); archive_layout.setContentsMargins(10, 10, 10, 10)
        archive_layout.addWidget(StrongBodyLabel("📁 结果分析与独立归档上传"))
        
        tag_row = QHBoxLayout()
        self.combo_tag = ComboBox() 
        tag_row.addWidget(BodyLabel("总目录:")); tag_row.addWidget(self.combo_tag); tag_row.addSpacing(15)
        
        self.combo_assoc_exp = ComboBox(); self.combo_assoc_exp.setPlaceholderText("关联当天实验...")
        tag_row.addWidget(BodyLabel("关联子实验:")); tag_row.addWidget(self.combo_assoc_exp); tag_row.addStretch(1); archive_layout.addLayout(tag_row)
        
        self.text_extra = RichTextELNEditor()
        self.text_extra.setPlaceholderText("针对本次上传文件的特定分析结论..."); 
        self.text_extra.setFixedHeight(120) 
        archive_layout.addWidget(self.text_extra)
        
        btn_action_row = QHBoxLayout()
        self.btn_clear_log = PushButton("🧹清空分析", icon=FIF.DELETE)
        self.btn_clear_log.clicked.connect(self.text_extra.clear)
        
        self.btn_upload = PrimaryPushButton("归档该实验文件", icon=FIF.FOLDER_ADD)
        self.btn_upload.clicked.connect(self.sig_upload_clicked.emit) 
        
        btn_action_row.addWidget(self.btn_clear_log)
        btn_action_row.addWidget(self.btn_upload, 1)
        archive_layout.addLayout(btn_action_row)
        
        eln_layout.addWidget(archive_panel, 1); self.stack_eln.addWidget(eln_widget)
        right_layout.addWidget(self.stack_eln); self.pivot.currentItemChanged.connect(lambda k: self.stack_eln.setCurrentIndex(0 if k=="todo" else 1))
        
        splitter.addWidget(left_panel); splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 7); splitter.setStretchFactor(1, 3) 
        main_layout.addWidget(splitter, 1)

    def _set_edit_mode(self, editable):
        self.input_todo.setEnabled(editable); self.combo_preset.setEnabled(editable); self.combo_preset.setCurrentIndex(0)
        
        # 💡 控制引用按钮：只有开启编辑模式，才能引用样本
        self.btn_ref_sample.setEnabled(editable)

    def load_config_data(self, tags, templates_dict):
        self.templates_dict = templates_dict
        self.combo_tag.blockSignals(True)
        self.combo_tag.clear()
        self.combo_tag.addItems(tags)
        self.combo_tag.blockSignals(False)
        
        self.combo_preset.blockSignals(True)
        self.combo_preset.clear()
        self.combo_preset.addItem("-- 选择插入模板 --")
        self.combo_preset.addItems(list(templates_dict.keys()))
        self.combo_preset.blockSignals(False)

    def _insert_preset(self, index):
        if index == 0 or not self.is_editing: return
        text = self.combo_preset.currentText()
        if text in self.templates_dict:
            curr = self.text_main.toHtml() 
            cursor = self.text_main.textCursor()
            cursor.insertText(self.templates_dict[text] + "\n\n")
        self.combo_preset.setCurrentIndex(0)

    def _update_assoc_exp_tags(self):
        clean_text = self.text_main.toPlainText()
        tags = re.findall(r'【(.*?)】', clean_text)
        curr_text = self.combo_assoc_exp.currentText()
        self.combo_assoc_exp.blockSignals(True); self.combo_assoc_exp.clear()
        unique_tags = list(set(tags))
        if unique_tags:
            self.combo_assoc_exp.addItems(unique_tags)
            if curr_text in unique_tags: self.combo_assoc_exp.setCurrentText(curr_text)
        else: self.combo_assoc_exp.addItem("-- 未检测到具体实验 --")
        self.combo_assoc_exp.blockSignals(False)

    def switch_main_view(self, view_index): self.stack_views.setCurrentIndex(view_index); self.slider_zoom.setEnabled(view_index != 2)
    def update_top_nav(self, text): self.lbl_time_nav.setText(text)
    def update_grid_height(self, height_val):
        for cell in self.month_cells + self.week_cells: cell.setMinimumHeight(height_val)

    def render_month_view(self, year, month, schedule_data, zoom_val):
        for cell in self.month_cells: self.month_grid.removeWidget(cell); cell.deleteLater()
        self.month_cells.clear(); first_day = QDate(year, month, 1); curr_date = first_day.addDays(-(first_day.dayOfWeek() - 1))
        for row in range(6):
            for col in range(7):
                cell = DayCell(curr_date, is_current_month=(curr_date.month() == month)); cell.setMinimumHeight(zoom_val)
                date_str = curr_date.toString("yyyy-MM-dd")
                if date_str in schedule_data: cell.set_preview(schedule_data[date_str], view_mode=0) 
                if curr_date == self.current_selected_date: cell.set_selected(True)
                cell.clicked.connect(self.sig_date_changed.emit); self.month_grid.addWidget(cell, row + 1, col); self.month_cells.append(cell)
                curr_date = curr_date.addDays(1)

    def render_week_view(self, start_date, schedule_data, zoom_val):
        for cell in self.week_cells: self.week_grid.removeWidget(cell); cell.deleteLater()
        self.week_cells.clear(); curr_date = start_date
        for col in range(7):
            cell = DayCell(curr_date, is_current_month=True); cell.setMinimumHeight(zoom_val)
            date_str = curr_date.toString("yyyy-MM-dd")
            if date_str in schedule_data: cell.set_preview(schedule_data[date_str], view_mode=1) 
            if curr_date == self.current_selected_date: cell.set_selected(True)
            cell.clicked.connect(self.sig_date_changed.emit); self.week_grid.addWidget(cell, 1, col); self.week_cells.append(cell)
            curr_date = curr_date.addDays(1)

    def render_year_view(self, year):
        while self.year_grid.count():
            child = self.year_grid.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for m in range(1, 13):
            mini = MiniMonthWidget(year, m); mini.clicked.connect(lambda y, mo: self.combo_view.setCurrentIndex(0)) 
            self.year_grid.addWidget(mini, (m-1)//4, (m-1)%4)

    def update_right_panel(self, qdate, day_data):
        if self.is_editing: self._toggle_edit()
        self.current_selected_date = qdate; self.current_todos = day_data.get("todo", [])
        prefix = "🌟 今天: " if qdate == QDate.currentDate() else "📅 日期: "
        self.lbl_detail_date.setText(f"{prefix}{qdate.toString('yyyy-MM-dd')}")
        self.text_main.setHtml(day_data.get("main", ""))
        self.text_extra.setHtml(day_data.get("extra", "")) 
        self._refresh_todo_list()
        for cell in self.month_cells + self.week_cells: cell.set_selected(cell.date == qdate)
        self._update_assoc_exp_tags()

    def _toggle_edit(self):
        self.is_editing = not self.is_editing; self._set_edit_mode(self.is_editing)
        if self.is_editing:
            self.btn_edit.setText("💾 保存记录"); self.btn_edit.setIcon(FIF.SAVE)
        else:
            self.btn_edit.setText("🔒 开启编辑"); self.btn_edit.setIcon(FIF.EDIT)
            date_str = self.current_selected_date.toString("yyyy-MM-dd")
            self.sig_save_requested.emit(date_str, self.current_todos, self.text_main.toHtml(), self.text_extra.toHtml())

    def _set_edit_mode(self, editable):
        self.input_todo.setEnabled(editable); self.combo_preset.setEnabled(editable); self.combo_preset.setCurrentIndex(0)
        self.text_main.setReadOnly(not editable); self.text_extra.setReadOnly(not editable)
        bg_color = "white" if editable else "#f9f9f9"
        self.text_main.setStyleSheet(f"QTextEdit {{ background-color: {bg_color}; font-size: 13px; }}")
        self.text_extra.setStyleSheet(f"QTextEdit {{ background-color: {bg_color}; font-size: 13px; }}")
        for i in range(self.list_todo.count()):
            widget = self.list_todo.itemWidget(self.list_todo.item(i))
            if widget: widget.setEditable(editable)

    def _add_todo(self):
        text = self.input_todo.text().strip()
        if text: self.current_todos.append({"text": text, "done": False}); self.input_todo.clear(); self._refresh_todo_list()

    def _delete_todo(self, idx):
        if 0 <= idx < len(self.current_todos): del self.current_todos[idx]; self._refresh_todo_list()

    def _toggle_todo(self, idx, is_done):
        if 0 <= idx < len(self.current_todos): self.current_todos[idx]["done"] = is_done

    def _refresh_todo_list(self):
        self.list_todo.clear()
        for idx, task in enumerate(self.current_todos):
            item = QListWidgetItem(self.list_todo); widget = TaskItemWidget(task['text'], task['done'], idx)
            widget.sig_deleted.connect(self._delete_todo); widget.sig_toggled.connect(self._toggle_todo)
            widget.set_editable(self.is_editing)
            item.setSizeHint(widget.sizeHint()); self.list_todo.addItem(item); self.list_todo.setItemWidget(item, widget)