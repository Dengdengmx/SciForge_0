# plugins/plugin_elisa.py
import os
import json
from io import StringIO
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.cm as cm
import matplotlib
from matplotlib.ticker import ScalarFormatter, AutoMinorLocator, MaxNLocator, LogLocator, NullLocator
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDialog, QScrollArea, 
                             QColorDialog, QMessageBox, QFileDialog, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings

from qfluentwidgets import (LineEdit, SpinBox, DoubleSpinBox, CheckBox, ComboBox, 
                            BodyLabel, PushButton, PlainTextEdit, PrimaryPushButton, 
                            StrongBodyLabel, CardWidget, ListWidget, FluentIcon as FIF)

from core.plugin_manager import BasePlugin

# ==========================================
# 核心算法区 (原生算法，保持纯净)
# ==========================================
def safe_load_dataframe(filepath):
    if filepath.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(filepath, header=None, engine='openpyxl')
    for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "latin1"]:
        try:
            with open(filepath, 'r', encoding=enc) as f: first_line = f.readline()
            sep = '\t' if '\t' in first_line else ','
            return pd.read_csv(filepath, header=None, encoding=enc, sep=sep)
        except: continue
    return pd.read_csv(filepath, header=None, encoding='utf-8', errors='replace')

def fourPL(x, A, B, C, D): 
    return D + (A - D) / (1 + (x / (C + 1e-10))**B)

def r_squared(y_true, y_pred):
    residuals = y_true - y_pred
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y_true - np.mean(y_true))**2)
    return 1 - (ss_res / ss_tot)

def scan_for_plate_blocks(df_raw):
    valid_blocks = []; rows, cols = df_raw.shape
    if rows < 8: return []
    for c in range(cols):
        col_data = df_raw.iloc[:, c].astype(str).str.strip().str.upper().values
        for r in range(rows - 7):
            if col_data[r] == 'A':
                if all(col_data[r+1+i] == char for i, char in enumerate(['B','C','D','E','F','G','H'])):
                    if r > 0:
                        end_col = min(c + 13, cols)
                        headers = df_raw.iloc[r - 1, c + 1 : end_col].values
                        block = df_raw.iloc[r : r + 8, c + 1 : end_col].copy()
                        block.columns = headers
                        block = block.apply(pd.to_numeric, errors='coerce').dropna(axis=1, how='any')
                        if not block.empty: valid_blocks.append(block)
    return valid_blocks

# ==========================================
# 前端：支持【工作台】与【全局设置】双模式的 UI
# ==========================================
class ElisaUI(QWidget):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(parent)
        self.is_setting_mode = is_setting_mode 
        self.ui_vars = {}
        self.file_list = []
        self.custom_styles = {} 
        self.fit_results = []
        self.setAcceptDrops(True)
        self.settings = QSettings("SciForge", "ElisaPlugin")
        self._setup_ui()
        self._load_memory()

    def _create_fluent_group(self, title_text):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 2, 0, 6); layout.setSpacing(3)
        title = BodyLabel(title_text); title.setStyleSheet("font-weight: bold; color: #0078D7; font-size: 13px;")
        layout.addWidget(title)
        line = QWidget(); line.setFixedHeight(1); line.setStyleSheet("background-color: #E0E0E0;")
        layout.addWidget(line)
        return w, layout

    def add_row(self, layout, label1, widget1, label2=None, widget2=None):
        h = QHBoxLayout(); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(4)
        lbl1 = BodyLabel(label1); lbl1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        h.addWidget(lbl1); h.addWidget(widget1, 1)
        if label2 and widget2:
            h.addSpacing(4)
            lbl2 = BodyLabel(label2); lbl2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(lbl2); h.addWidget(widget2, 1)
        layout.addLayout(h)

    def get_float(self, widget, default=0.0):
        try: return float(widget.text())
        except: return default

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        left_panel = CardWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        h_tools = QHBoxLayout()
        btn_import_config = PushButton("📂 载入模板", icon=FIF.FOLDER)
        btn_export_config = PushButton("💾 保存模板", icon=FIF.SAVE)
        btn_import_config.clicked.connect(self.import_config)
        btn_export_config.clicked.connect(self.export_config)
        h_tools.addWidget(btn_import_config); h_tools.addWidget(btn_export_config)
        left_layout.addLayout(h_tools)

        gb_data, l_data = self._create_fluent_group("1. 数据池 (支持批量拖拽与发送)")
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 0, 0, 0)
        btn_add = PrimaryPushButton("导入...", icon=FIF.DOWNLOAD)
        btn_add.clicked.connect(self.open_files)
        btn_clear = PushButton("清空", icon=FIF.DELETE)
        btn_clear.clicked.connect(self.clear_files)
        btn_row.addWidget(btn_add); btn_row.addWidget(btn_clear)
        l_data.addLayout(btn_row)
        
        self.list_widget = ListWidget()
        self.list_widget.setFixedHeight(65)
        self.list_widget.itemClicked.connect(self.trigger_render)
        l_data.addWidget(self.list_widget)
        
        if not self.is_setting_mode:
            left_layout.addWidget(gb_data) 

        gb_wh, l_wh = self._create_fluent_group("2. 全局画板设置 (英寸)")
        h_wh = QHBoxLayout(); h_wh.setContentsMargins(0, 0, 0, 0)
        self.ui_vars['spin_w'] = DoubleSpinBox(); self.ui_vars['spin_w'].setRange(1.0, 50.0); self.ui_vars['spin_w'].setValue(7.0); self.ui_vars['spin_w'].setSingleStep(0.5)
        self.ui_vars['spin_h'] = DoubleSpinBox(); self.ui_vars['spin_h'].setRange(1.0, 50.0); self.ui_vars['spin_h'].setValue(5.0); self.ui_vars['spin_h'].setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("W:")); h_wh.addWidget(self.ui_vars['spin_w'], 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("H:")); h_wh.addWidget(self.ui_vars['spin_h'], 1)
        l_wh.addLayout(h_wh)
        left_layout.addWidget(gb_wh)

        gb_param, l_param = self._create_fluent_group("3. 专属参数配置")
        left_layout.addWidget(gb_param)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0) 
        scroll_layout.setSpacing(2)
        u = self.ui_vars

        u['text_data'] = PlainTextEdit()
        u['text_data'].setPlaceholderText("覆盖数据：可直接粘贴文本矩阵...")
        u['text_data'].setFixedHeight(60)
        u['parse_lbl'] = BodyLabel("状态: 未解析")
        u['parse_lbl'].setStyleSheet("color: #666; font-size: 11px;")
        if not self.is_setting_mode:
            scroll_layout.addWidget(u['text_data'])
            scroll_layout.addWidget(u['parse_lbl'])
        
        u['start']=LineEdit(); u['start'].setText("1000"); u['start'].setFixedWidth(55)
        u['dil']=LineEdit(); u['dil'].setText("3"); u['dil'].setFixedWidth(40)
        u['unit']=LineEdit(); u['unit'].setText("ng/mL"); u['unit'].setFixedWidth(60)
        h1 = QHBoxLayout(); h1.setSpacing(5)
        h1.addWidget(BodyLabel("起始:")); h1.addWidget(u['start'])
        h1.addWidget(BodyLabel("倍数:")); h1.addWidget(u['dil'])
        h1.addWidget(BodyLabel("单位:")); h1.addWidget(u['unit'])
        h1.addStretch(1); scroll_layout.addLayout(h1)
        u['merge'] = CheckBox("合并文件列表中的所有孔板"); u['merge'].setChecked(True)
        scroll_layout.addWidget(u['merge'])
        
        scroll_layout.addWidget(StrongBodyLabel("坐标轴设置"))
        u['title']=LineEdit(); u['title'].setText("ELISA 4PL Fit")
        self.add_row(scroll_layout, "主标题:", u['title'])
        u['xl']=LineEdit(); u['xl'].setText("Concentration")
        u['yl']=LineEdit(); u['yl'].setText("OD450")
        self.add_row(scroll_layout, "X轴名:", u['xl'], "Y轴名:", u['yl'])
        u['x1']=LineEdit(); u['x2']=LineEdit()
        self.add_row(scroll_layout, "X范围 起:", u['x1'], "止:", u['x2'])
        u['y1']=LineEdit(); u['y2']=LineEdit()
        self.add_row(scroll_layout, "Y范围 起:", u['y1'], "止:", u['y2'])
        
        scroll_layout.addWidget(StrongBodyLabel("外观与高级自定义"))
        h_chk1 = QHBoxLayout(); h_chk1.setSpacing(5)
        u['log'] = CheckBox("Log X"); u['log'].setChecked(True); h_chk1.addWidget(u['log'])
        u['leg'] = CheckBox("图例"); u['leg'].setChecked(True); h_chk1.addWidget(u['leg'])
        u['ec50'] = CheckBox("EC50"); u['ec50'].setChecked(True); h_chk1.addWidget(u['ec50'])
        u['grid'] = CheckBox("网格"); h_chk1.addWidget(u['grid'])
        scroll_layout.addLayout(h_chk1)
        
        u['diff'] = CheckBox("自动分配不同散点形状"); u['diff'].setChecked(True); scroll_layout.addWidget(u['diff'])
        
        lbl_bold = BodyLabel("独立加粗控制:"); lbl_bold.setStyleSheet("color:#666; font-size:11px;")
        scroll_layout.addWidget(lbl_bold)
        h_bold = QHBoxLayout(); h_bold.setSpacing(5)
        u['b_title'] = CheckBox("标题"); u['b_title'].setChecked(True); h_bold.addWidget(u['b_title'])
        u['b_label'] = CheckBox("轴名"); u['b_label'].setChecked(True); h_bold.addWidget(u['b_label'])
        u['b_tick'] = CheckBox("刻度"); h_bold.addWidget(u['b_tick'])
        u['b_leg'] = CheckBox("图例"); h_bold.addWidget(u['b_leg'])
        scroll_layout.addLayout(h_bold)
        
        u['ms']=SpinBox(); u['ms'].setRange(10, 200); u['ms'].setValue(30)
        u['lw']=DoubleSpinBox(); u['lw'].setRange(0.5, 5.0); u['lw'].setValue(2.0)
        u['ls']=ComboBox(); u['ls'].addItems(["-", "--", "-.", ":"])
        self.add_row(scroll_layout, "点大小:", u['ms'], "线宽:", u['lw'])
        
        h_ls = QHBoxLayout()
        h_ls.addWidget(BodyLabel("线型:")); h_ls.addWidget(u['ls'], 1)
        h_ls.addWidget(BodyLabel("图例位置:")); 
        u['leg_loc']=ComboBox(); u['leg_loc'].addItems(["best", "outside", "upper right", "upper left", "lower right", "lower left", "center right", "center left"])
        h_ls.addWidget(u['leg_loc'], 2); scroll_layout.addLayout(h_ls)
        
        btn_custom = PushButton("🎨 自定义各个样品颜色与形状")
        btn_custom.clicked.connect(self.open_style_customizer)
        scroll_layout.addWidget(btn_custom)
        
        lbl_fs = BodyLabel("字号控制:"); lbl_fs.setStyleSheet("color:#666; font-size:11px; margin-top:5px;")
        scroll_layout.addWidget(lbl_fs)
        u['fs_title']=SpinBox(); u['fs_title'].setRange(8, 30); u['fs_title'].setValue(14)
        u['fs_label']=SpinBox(); u['fs_label'].setRange(6, 24); u['fs_label'].setValue(12)
        u['fs_tick']=SpinBox(); u['fs_tick'].setRange(6, 24); u['fs_tick'].setValue(10)
        u['fs_leg']=SpinBox(); u['fs_leg'].setRange(6, 24); u['fs_leg'].setValue(9)
        h_fs1 = QHBoxLayout(); h_fs1.addWidget(BodyLabel("标题:")); h_fs1.addWidget(u['fs_title']); h_fs1.addWidget(BodyLabel("轴名:")); h_fs1.addWidget(u['fs_label']); scroll_layout.addLayout(h_fs1)
        h_fs2 = QHBoxLayout(); h_fs2.addWidget(BodyLabel("刻度:")); h_fs2.addWidget(u['fs_tick']); h_fs2.addWidget(BodyLabel("图例:")); h_fs2.addWidget(u['fs_leg']); scroll_layout.addLayout(h_fs2)
        
        lbl_tk = BodyLabel("刻度与边框控制:"); lbl_tk.setStyleSheet("color:#666; font-size:11px; margin-top:5px;")
        scroll_layout.addWidget(lbl_tk)
        h_border = QHBoxLayout()
        u['tk_dir']=ComboBox(); u['tk_dir'].addItems(["in", "out"])
        u['top']=CheckBox("上边框"); u['top'].setChecked(True)
        u['right']=CheckBox("右边框"); u['right'].setChecked(True)
        h_border.addWidget(BodyLabel("朝向:")); h_border.addWidget(u['tk_dir']); h_border.addWidget(u['top']); h_border.addWidget(u['right']); scroll_layout.addLayout(h_border)
        
        u['x_maj']=SpinBox(); u['x_maj'].setRange(2, 20); u['x_maj'].setValue(6)
        u['x_min']=SpinBox(); u['x_min'].setRange(0, 10); u['x_min'].setValue(0)
        u['y_maj']=SpinBox(); u['y_maj'].setRange(2, 20); u['y_maj'].setValue(5)
        u['y_min']=SpinBox(); u['y_min'].setRange(0, 10); u['y_min'].setValue(2)
        h_tk1 = QHBoxLayout(); h_tk1.addWidget(BodyLabel("X(主/次):")); h_tk1.addWidget(u['x_maj']); h_tk1.addWidget(u['x_min']); scroll_layout.addLayout(h_tk1)
        h_tk2 = QHBoxLayout(); h_tk2.addWidget(BodyLabel("Y(主/次):")); h_tk2.addWidget(u['y_maj']); h_tk2.addWidget(u['y_min']); scroll_layout.addLayout(h_tk2)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        if self.is_setting_mode:
            self.btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            self.btn_save_config.setFixedHeight(45)
            self.btn_save_config.clicked.connect(self.save_settings_and_close)
            left_layout.addWidget(self.btn_save_config)
            
            main_layout.addWidget(left_panel)
            return 

        self.btn_plot = PrimaryPushButton("⚡ 渲染图表", icon=FIF.PLAY)
        self.btn_plot.setFixedHeight(35)
        self.btn_plot.clicked.connect(self.trigger_render)
        left_layout.addWidget(self.btn_plot)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: #E0E0E0; width: 4px; border-radius: 2px; margin: 10px 2px; }")
        splitter.addWidget(left_panel)

        right_panel = CardWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        self.fig = Figure(dpi=120)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed) 
        
        self.canvas_container = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setAlignment(Qt.AlignCenter)
        self.canvas_layout.addWidget(self.canvas)
        
        self.scroll_canvas = QScrollArea()
        self.scroll_canvas.setWidgetResizable(True)
        self.scroll_canvas.setFrameShape(QScrollArea.NoFrame)
        self.scroll_canvas.setWidget(self.canvas_container) 
        
        self.toolbar = NavigationToolbar(self.canvas, right_panel)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.scroll_canvas)
        
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        u['chk_trans'] = CheckBox("透明背景")
        export_layout.addWidget(u['chk_trans'])
        export_layout.addSpacing(15)
        u['combo_fmt'] = ComboBox(); u['combo_fmt'].addItems(["pdf", "png", "svg"])
        export_layout.addWidget(StrongBodyLabel("导出格式:"))
        export_layout.addWidget(u['combo_fmt'])
        btn_export = PushButton("保存图表", icon=FIF.SAVE)
        btn_export.clicked.connect(self.export_plot)
        export_layout.addWidget(btn_export)
        btn_csv = PushButton("💾 导出 EC50 (.csv)")
        btn_csv.clicked.connect(self.save_csv)
        export_layout.addWidget(btn_csv)
        
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_panel)
        splitter.setSizes([350, 750])
        main_layout.addWidget(splitter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            fp = url.toLocalFile()
            self.load_file(fp)

    def load_file(self, filepath):
        if not os.path.exists(filepath): return
        if filepath.lower().endswith(('.csv', '.xlsx', '.xls', '.txt')):
            if filepath not in self.file_list:
                self.file_list.append(filepath)
                if not self.is_setting_mode: self.list_widget.addItem(os.path.basename(filepath))
        if self.file_list and not self.is_setting_mode and not self.list_widget.currentItem():
            self.list_widget.setCurrentRow(0)
            self.trigger_render()

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择数据文件", "", "Data Files (*.csv *.xlsx *.xls *.txt);;All Files (*)")
        for fp in files: self.load_file(fp)

    def clear_files(self):
        self.file_list.clear()
        if not self.is_setting_mode:
            self.list_widget.clear(); self.fig.clear(); self.canvas.draw()
            self.ui_vars['text_data'].clear()
            self.ui_vars['parse_lbl'].setText("状态: 数据已清空")

    def get_elisa_df(self):
        u = self.ui_vars
        raw_text = u['text_data'].toPlainText().strip()
        
        if raw_text:
            try:
                df_raw = pd.read_csv(StringIO(raw_text), sep='\t', header=None, engine='python')
                if df_raw.shape[1] < 2:
                    df_raw = pd.read_csv(StringIO(raw_text), sep=r'\s+', header=None, engine='python')
            except:
                df_raw = pd.read_csv(StringIO(raw_text), sep=',', header=None, engine='python')
            blocks = scan_for_plate_blocks(df_raw)
            if blocks: return pd.concat(blocks, axis=1) if u['merge'].isChecked() else blocks[-1]
            
            header_idx = 0 
            for idx, row in df_raw.head(30).iterrows():
                if any(k in str(row.values).lower() for k in ['conc', 'concentration']):
                    header_idx = idx; break
            df_data = df_raw.iloc[header_idx+1:].copy()
            df_data.columns = df_raw.iloc[header_idx]
            if len(df_data.columns) > 0: df_data.set_index(df_data.columns[0], inplace=True)
            df_data = df_data.apply(pd.to_numeric, errors='coerce')
            df_data.dropna(how='all', axis=1, inplace=True)
            if df_data.empty: raise ValueError("粘贴的数据未能提取出任何有效数值！请检查格式。")
            return df_data
        else:
            if not self.file_list: raise ValueError("请先粘贴数据，或在上方添加文件！")
            all_dfs = []
            for fp in self.file_list:
                df_raw = safe_load_dataframe(fp)
                blocks = scan_for_plate_blocks(df_raw)
                if blocks: all_dfs.extend(blocks)
            if not all_dfs: raise ValueError("所有文件均未检测到标准的 96孔板(A-H) 格式！")
            if u['merge'].isChecked(): return pd.concat(all_dfs, axis=1)
            else:
                row = self.list_widget.currentRow()
                if row >= 0:
                    blocks = scan_for_plate_blocks(safe_load_dataframe(self.file_list[row]))
                    if blocks: return blocks[-1]
                return all_dfs[-1]

    def _save_memory(self):
        self.settings.setValue("elisa_plugin_params", json.dumps(self.get_config_dict()))

    def _load_memory(self):
        data_str = self.settings.value("elisa_plugin_params", "")
        if data_str:
            try: self.apply_config_dict(json.loads(data_str))
            except: pass

    def get_config_dict(self):
        u = self.ui_vars
        config = {
            "start": u['start'].text(), "dil": u['dil'].text(), "unit": u['unit'].text(), "merge": u['merge'].isChecked(),
            "title": u['title'].text(), "xl": u['xl'].text(), "yl": u['yl'].text(),
            "x1": u['x1'].text(), "x2": u['x2'].text(), "y1": u['y1'].text(), "y2": u['y2'].text(),
            "spin_w": u['spin_w'].value(), "spin_h": u['spin_h'].value(),
            "log": u['log'].isChecked(), "leg": u['leg'].isChecked(), "ec50": u['ec50'].isChecked(), "grid": u['grid'].isChecked(), "diff": u['diff'].isChecked(),
            "b_title": u['b_title'].isChecked(), "b_label": u['b_label'].isChecked(), "b_tick": u['b_tick'].isChecked(), "b_leg": u['b_leg'].isChecked(),
            "ms": u['ms'].value(), "lw": u['lw'].value(), "ls": u['ls'].currentText(), "leg_loc": u['leg_loc'].currentText(),
            "fs_title": u['fs_title'].value(), "fs_label": u['fs_label'].value(), "fs_tick": u['fs_tick'].value(), "fs_leg": u['fs_leg'].value(),
            "tk_dir": u['tk_dir'].currentText(), "top": u['top'].isChecked(), "right": u['right'].isChecked(),
            "x_maj": u['x_maj'].value(), "x_min": u['x_min'].value(), "y_maj": u['y_maj'].value(), "y_min": u['y_min'].value(),
            "custom_styles": self.custom_styles
        }
        if not self.is_setting_mode:
            config["chk_trans"] = u['chk_trans'].isChecked()
            config["combo_fmt"] = u['combo_fmt'].currentText()
        return config

    def apply_config_dict(self, data):
        u = self.ui_vars
        u['start'].setText(data.get("start", "1000")); u['dil'].setText(data.get("dil", "3")); u['unit'].setText(data.get("unit", "ng/mL")); u['merge'].setChecked(data.get("merge", True))
        u['title'].setText(data.get("title", "ELISA 4PL Fit")); u['xl'].setText(data.get("xl", "Concentration")); u['yl'].setText(data.get("yl", "OD450"))
        u['x1'].setText(data.get("x1", "")); u['x2'].setText(data.get("x2", "")); u['y1'].setText(data.get("y1", "")); u['y2'].setText(data.get("y2", ""))
        u['spin_w'].setValue(data.get("spin_w", 7.0)); u['spin_h'].setValue(data.get("spin_h", 5.0))
        u['log'].setChecked(data.get("log", True)); u['leg'].setChecked(data.get("leg", True)); u['ec50'].setChecked(data.get("ec50", True)); u['grid'].setChecked(data.get("grid", False)); u['diff'].setChecked(data.get("diff", True))
        u['b_title'].setChecked(data.get("b_title", True)); u['b_label'].setChecked(data.get("b_label", True)); u['b_tick'].setChecked(data.get("b_tick", False)); u['b_leg'].setChecked(data.get("b_leg", False))
        u['ms'].setValue(data.get("ms", 30)); u['lw'].setValue(data.get("lw", 2.0)); u['ls'].setCurrentText(data.get("ls", "-")); u['leg_loc'].setCurrentText(data.get("leg_loc", "best"))
        u['fs_title'].setValue(data.get("fs_title", 14)); u['fs_label'].setValue(data.get("fs_label", 12)); u['fs_tick'].setValue(data.get("fs_tick", 10)); u['fs_leg'].setValue(data.get("fs_leg", 9))
        u['tk_dir'].setCurrentText(data.get("tk_dir", "in")); u['top'].setChecked(data.get("top", True)); u['right'].setChecked(data.get("right", True))
        u['x_maj'].setValue(data.get("x_maj", 6)); u['x_min'].setValue(data.get("x_min", 0)); u['y_maj'].setValue(data.get("y_maj", 5)); u['y_min'].setValue(data.get("y_min", 2))
        self.custom_styles = data.get("custom_styles", {})
        if not self.is_setting_mode and "chk_trans" in u:
            u['chk_trans'].setChecked(data.get("chk_trans", False))
            u['combo_fmt'].setCurrentText(data.get("combo_fmt", "pdf"))

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 ELISA 参数模板", "elisa_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入 ELISA 参数模板", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f: self.apply_config_dict(json.load(f))
            if not self.is_setting_mode: self.trigger_render()

    def save_settings_and_close(self):
        self._save_memory()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog):
            parent_dlg.accept()

    def trigger_render(self, *args):
        if self.is_setting_mode: return
        self._save_memory() 
        self.render_plot()
        
        dpi = self.fig.dpi
        w_px = int(self.ui_vars['spin_w'].value() * dpi)
        h_px = int(self.ui_vars['spin_h'].value() * dpi)
        self.canvas.setFixedSize(w_px, h_px)
        self.canvas_container.updateGeometry()

    def open_style_customizer(self):
        if self.is_setting_mode:
            QMessageBox.information(self, "提示", "请在工作站中导入数据后再配置独立样品颜色。")
            return
        try: df_data = self.get_elisa_df()
        except Exception as e: QMessageBox.warning(self, "提示", f"获取失败:\n{e}"); return
        dlg = QDialog(self); dlg.setWindowTitle("个性化配置"); dlg.resize(400, 500); dlg_layout = QVBoxLayout(dlg)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        content = QWidget(); vbox = QVBoxLayout(content)
        marker_opts = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', '<', '>', 'x', '+']
        self.temp_vars = {}
        try: colors = matplotlib.colormaps['tab10']
        except: colors = cm.get_cmap('tab10')
        for i, col_name in enumerate(df_data.columns):
            row_l = QHBoxLayout(); lbl = BodyLabel(str(col_name)); lbl.setFixedWidth(120); row_l.addWidget(lbl)
            current_color = self.custom_styles.get(col_name, {}).get('color', matplotlib.colors.to_hex(colors(i % 10)))
            btn_color = PushButton(""); btn_color.setFixedWidth(50)
            btn_color.setStyleSheet(f"background-color: {current_color}; border: 1px solid #ccc;"); btn_color.property_color = current_color
            def make_color_picker(btn):
                def pick():
                    color = QColorDialog.getColor(); 
                    if color.isValid(): btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #ccc;"); btn.property_color = color.name()
                return pick
            btn_color.clicked.connect(make_color_picker(btn_color)); row_l.addWidget(btn_color)
            cb_marker = ComboBox(); cb_marker.addItems(marker_opts)
            cb_marker.setCurrentText(self.custom_styles.get(col_name, {}).get('marker', marker_opts[i % len(marker_opts)])); row_l.addWidget(cb_marker)
            row_w = QWidget(); row_w.setLayout(row_l); vbox.addWidget(row_w); self.temp_vars[col_name] = {'btn': btn_color, 'cb': cb_marker}
        vbox.addStretch(1); scroll.setWidget(content); dlg_layout.addWidget(scroll)
        btn_apply = PushButton("✅ 应用并刷新"); 
        def apply_styles():
            for name, w in self.temp_vars.items():
                if name not in self.custom_styles: self.custom_styles[name] = {}
                self.custom_styles[name]['color'] = w['btn'].property_color; self.custom_styles[name]['marker'] = w['cb'].currentText()
            dlg.accept(); self.trigger_render()
        btn_apply.clicked.connect(apply_styles); dlg_layout.addWidget(btn_apply); dlg.exec_()

    def export_plot(self):
        if self.is_setting_mode: return
        fmt = self.ui_vars['combo_fmt'].currentText()
        is_transparent = self.ui_vars['chk_trans'].isChecked()
        row = self.list_widget.currentRow()
        default_name = os.path.splitext(self.list_widget.item(max(0,row)).text())[0] + f"_ELISA.{fmt}" if self.list_widget.count() > 0 else f"ELISA_Plot.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出高清图表", default_name, f"Images (*.{fmt})")
        if file_path:
            try:
                self.fig.savefig(file_path, dpi=600, bbox_inches="tight", transparent=is_transparent)
                QMessageBox.information(self, "成功", f"图表已成功导出为:\n{file_path}")
            except Exception as e: QMessageBox.critical(self, "导出失败", str(e))

    def save_csv(self):
        if not self.fit_results: return
        path, _ = QFileDialog.getSaveFileName(self, "导出 EC50 数据", "ELISA_FitResult.csv", "CSV Files (*.csv)")
        if path: pd.DataFrame(self.fit_results).to_csv(path, index=False)

    def render_plot(self):
        if self.is_setting_mode: return
        self.fig.clear()
        u = self.ui_vars
        self.fig.set_size_inches(u['spin_w'].value(), u['spin_h'].value())
        self.ax = self.fig.add_subplot(111)
        self.fit_results = []
        
        try: 
            df_data = self.get_elisa_df()
            u['parse_lbl'].setText(f"✔ 解析成功: 检测到 {df_data.shape[1]} 列数据")
            u['parse_lbl'].setStyleSheet("color: #107C10; font-weight: bold;")
        except Exception as e:
            u['parse_lbl'].setText(f"❌ 解析失败: {str(e)}")
            u['parse_lbl'].setStyleSheet("color: red; font-weight: bold;")
            self.ax.text(0.5, 0.5, f"数据错误:\n{str(e)}", ha='center', va='center')
            self.canvas.draw()
            return
            
        title_text = "ELISA_4PL_Fit"
        if not u['text_data'].toPlainText().strip():
            row = self.list_widget.currentRow()
            if row >= 0 and row < len(self.file_list): title_text = os.path.splitext(os.path.basename(self.file_list[row]))[0]

        start = self.get_float(u['start'], 1000); dil = self.get_float(u['dil'], 3)
        x_arr = np.array([start / (dil ** i) for i in range(len(df_data))])
        
        is_log = u['log'].isChecked()
        fw_title = 'bold' if u['b_title'].isChecked() else 'normal'
        fw_label = 'bold' if u['b_label'].isChecked() else 'normal'
        fw_tick  = 'bold' if u['b_tick'].isChecked() else 'normal'
        fw_leg   = 'bold' if u['b_leg'].isChecked() else 'normal'
        
        try: colors = matplotlib.colormaps['tab10']
        except: colors = cm.get_cmap('tab10')
        default_markers = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', '<', '>']

        for i, col_name in enumerate(df_data.columns):
            y_raw = df_data.iloc[:, i].values
            curr_x = x_arr[:len(y_raw)] if len(y_raw) < len(x_arr) else x_arr
            mask = ~np.isnan(y_raw[:len(curr_x)])
            x_fit, y_fit = curr_x[mask], y_raw[:len(curr_x)][mask]
            
            col_c = self.custom_styles.get(col_name, {}).get('color', matplotlib.colors.to_hex(colors(i % 10)))
            col_m = self.custom_styles.get(col_name, {}).get('marker', default_markers[i % len(default_markers)] if u['diff'].isChecked() else 'o')
            
            self.ax.scatter(x_fit, y_fit, color=col_c, marker=col_m, s=u['ms'].value(), edgecolors='white', zorder=3)
            res_dict = {'Sample': col_name, 'R2':'-', 'EC50':'-', 'A':'-', 'B':'-', 'C':'-', 'D':'-'}
            lbl = str(col_name)
            
            if len(x_fit) >= 4:
                try:
                    p0 = [min(y_fit), 1.0, np.median(x_fit), max(y_fit)]
                    params, _ = curve_fit(fourPL, x_fit, y_fit, p0=p0, maxfev=5000)
                    x_sm = np.logspace(np.log10(min(x_fit)/2), np.log10(max(x_fit)*2), 100) if is_log else np.linspace(0, max(x_fit)*1.1, 100)
                    if u['ec50'].isChecked(): lbl += f" ($\\mathbf{{EC_{{50}}={params[2]:.2f}}}$)" if fw_leg=='bold' else f" ($EC_{{50}}={params[2]:.2f}$)"
                    self.ax.plot(x_sm, fourPL(x_sm, *params), color=col_c, lw=u['lw'].value(), ls=u['ls'].currentText(), label=lbl, zorder=2)
                    res_dict.update({'R2': r_squared(y_fit, fourPL(x_fit, *params)), 'EC50': params[2]})
                except: self.ax.plot(x_fit, y_fit, color=col_c, ls='--', lw=1, label=lbl + " (Fit Fail)")
            else: self.ax.plot(x_fit, y_fit, color=col_c, ls=':', lw=1, label=lbl + " (<4 pts)")
            self.fit_results.append(res_dict)

        self.ax.set_title(u['title'].text() if u['title'].text() else title_text, fontsize=u['fs_title'].value(), fontweight=fw_title, pad=10)
        self.ax.set_xlabel(u['xl'].text(), fontsize=u['fs_label'].value(), fontweight=fw_label)
        self.ax.set_ylabel(u['yl'].text(), fontsize=u['fs_label'].value(), fontweight=fw_label)
        
        if u['x1'].text(): self.ax.set_xlim(left=self.get_float(u['x1']))
        if u['x2'].text(): self.ax.set_xlim(right=self.get_float(u['x2']))
        if u['y1'].text(): self.ax.set_ylim(bottom=self.get_float(u['y1']))
        if u['y2'].text(): self.ax.set_ylim(top=self.get_float(u['y2']))

        if is_log:
            self.ax.set_xscale('log')
            self.ax.xaxis.set_major_formatter(ScalarFormatter())
            self.ax.ticklabel_format(style='plain', axis='x')

        try:
            nx_maj, nx_min = u['x_maj'].value(), u['x_min'].value()
            ny_maj, ny_min = u['y_maj'].value(), u['y_min'].value()
            self.ax.yaxis.set_major_locator(MaxNLocator(nbins=ny_maj))
            self.ax.yaxis.set_minor_locator(NullLocator() if ny_min==0 else AutoMinorLocator(ny_min))
            if not is_log:
                self.ax.xaxis.set_major_locator(MaxNLocator(nbins=nx_maj))
                self.ax.xaxis.set_minor_locator(NullLocator() if nx_min==0 else AutoMinorLocator(nx_min))
            else:
                self.ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=nx_maj+2))
                self.ax.xaxis.set_minor_locator(NullLocator() if nx_min==0 else LogLocator(base=10.0, subs='auto'))
        except: pass

        top_on, right_on = u['top'].isChecked(), u['right'].isChecked()
        self.ax.tick_params(which='both', direction=u['tk_dir'].currentText(), top=top_on, right=right_on, labelsize=u['fs_tick'].value())
        self.ax.spines['top'].set_visible(top_on)
        self.ax.spines['right'].set_visible(right_on)
        for sp in self.ax.spines.values(): sp.set_linewidth(1.2)
        for label in self.ax.get_xticklabels() + self.ax.get_yticklabels(): label.set_fontweight(fw_tick)

        if u['leg'].isChecked():
            loc = u['leg_loc'].currentText()
            if loc == 'outside': leg = self.ax.legend(frameon=False, fontsize=u['fs_leg'].value(), bbox_to_anchor=(1.02, 1), loc='upper left')
            else: leg = self.ax.legend(frameon=False, fontsize=u['fs_leg'].value(), loc=loc)
            for text in leg.get_texts(): text.set_fontweight(fw_leg)

        if u['grid'].isChecked():
            self.ax.grid(True, which='major', ls='--', alpha=0.5)
            if is_log: self.ax.grid(True, which='minor', ls=':', alpha=0.2)
            
        self.fig.tight_layout()
        self.canvas.draw()

# ==========================================
# 后端：插件描述器与全局入口联动
# ==========================================
class ElisaPlugin(BasePlugin):
    plugin_id = "elisa_analyzer"
    plugin_name = "ELISA 4PL 拟合分析"
    icon = "📊"
    
    # 【核心：亮明身份标签】
    trigger_tag = "ELISA 检测"

    def get_ui(self, parent=None):
        return ElisaUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard(
            "配置全局默认参数", 
            FIF.EDIT, 
            "📊 ELISA 4PL 拟合分析", 
            "修改工作站中 ELISA 图谱的全局默认线宽、字号与外观偏好", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card) 
            dlg.setWindowTitle("ELISA 全局默认参数预设中心")
            dlg.resize(460, 750) 
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(10, 10, 10, 10)
            
            settings_ui = ElisaUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    # 【核心注入：纯后台、线程安全的自动化作图逻辑】
    @staticmethod
    def run(file_path, archive_dir):
        try:
            settings = QSettings("SciForge", "ElisaPlugin")
            param_str = settings.value("elisa_plugin_params", "")
            u = {}
            if param_str:
                try: u = json.loads(param_str)
                except: pass
            
            # 读取数据
            df_raw = safe_load_dataframe(file_path)
            blocks = scan_for_plate_blocks(df_raw)
            if not blocks:
                return "", "【ELISA 分析跳过】未能从文件中检测到标准的 96孔板格式 (A-H行)。"
                
            if u.get("merge", True):
                df_data = pd.concat(blocks, axis=1)
            else:
                df_data = blocks[-1]
                
            # 计算浓度梯度
            start = float(u.get('start', 1000))
            dil = float(u.get('dil', 3))
            x_arr = np.array([start / (dil ** i) for i in range(len(df_data))])
            
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt
            
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig = Figure(figsize=(u.get("spin_w", 7.0), u.get("spin_h", 5.0)), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)
            
            is_log = u.get('log', True)
            fw_title = 'bold' if u.get('b_title', True) else 'normal'
            fw_label = 'bold' if u.get('b_label', True) else 'normal'
            fw_tick  = 'bold' if u.get('b_tick', False) else 'normal'
            fw_leg   = 'bold' if u.get('b_leg', False) else 'normal'
            
            try: colors = matplotlib.colormaps['tab10']
            except: colors = cm.get_cmap('tab10')
            default_markers = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', '<', '>']
            custom_styles = u.get("custom_styles", {})
            
            fit_texts = []
            
            for i, col_name in enumerate(df_data.columns):
                y_raw = df_data.iloc[:, i].values
                curr_x = x_arr[:len(y_raw)] if len(y_raw) < len(x_arr) else x_arr
                mask = ~np.isnan(y_raw[:len(curr_x)])
                x_fit, y_fit = curr_x[mask], y_raw[:len(curr_x)][mask]
                
                col_c = custom_styles.get(str(col_name), {}).get('color', matplotlib.colors.to_hex(colors(i % 10)))
                col_m = custom_styles.get(str(col_name), {}).get('marker', default_markers[i % len(default_markers)] if u.get('diff', True) else 'o')
                
                ax.scatter(x_fit, y_fit, color=col_c, marker=col_m, s=u.get('ms', 30), edgecolors='white', zorder=3)
                lbl = str(col_name)
                
                if len(x_fit) >= 4:
                    try:
                        p0 = [min(y_fit), 1.0, np.median(x_fit), max(y_fit)]
                        params, _ = curve_fit(fourPL, x_fit, y_fit, p0=p0, maxfev=5000)
                        x_sm = np.logspace(np.log10(min(x_fit)/2), np.log10(max(x_fit)*2), 100) if is_log else np.linspace(0, max(x_fit)*1.1, 100)
                        
                        if u.get('ec50', True):
                            lbl += f" ($\\mathbf{{EC_{{50}}={params[2]:.2f}}}$)" if fw_leg=='bold' else f" ($EC_{{50}}={params[2]:.2f}$)"
                            
                        ax.plot(x_sm, fourPL(x_sm, *params), color=col_c, lw=u.get('lw', 2.0), ls=u.get('ls', '-'), label=lbl, zorder=2)
                        
                        r2 = r_squared(y_fit, fourPL(x_fit, *params))
                        fit_texts.append(f"[{col_name}] EC50: {params[2]:.2f}, R²: {r2:.3f}")
                    except Exception:
                        ax.plot(x_fit, y_fit, color=col_c, ls='--', lw=1, label=lbl + " (Fit Fail)")
                        fit_texts.append(f"[{col_name}] 拟合失败")
                else:
                    ax.plot(x_fit, y_fit, color=col_c, ls=':', lw=1, label=lbl + " (<4 pts)")
                    fit_texts.append(f"[{col_name}] 数据点不足")

            title_text = os.path.splitext(os.path.basename(file_path))[0]
            ax.set_title(u.get('title', "ELISA 4PL Fit") if u.get('title', "") else title_text, fontsize=u.get('fs_title', 14), fontweight=fw_title, pad=10)
            ax.set_xlabel(u.get('xl', "Concentration"), fontsize=u.get('fs_label', 12), fontweight=fw_label)
            ax.set_ylabel(u.get('yl', "OD450"), fontsize=u.get('fs_label', 12), fontweight=fw_label)
            
            if u.get('x1', ""): ax.set_xlim(left=float(u['x1']))
            if u.get('x2', ""): ax.set_xlim(right=float(u['x2']))
            if u.get('y1', ""): ax.set_ylim(bottom=float(u['y1']))
            if u.get('y2', ""): ax.set_ylim(top=float(u['y2']))

            if is_log:
                ax.set_xscale('log')
                ax.xaxis.set_major_formatter(ScalarFormatter())
                ax.ticklabel_format(style='plain', axis='x')

            try:
                nx_maj, nx_min = u.get('x_maj', 6), u.get('x_min', 0)
                ny_maj, ny_min = u.get('y_maj', 5), u.get('y_min', 2)
                ax.yaxis.set_major_locator(MaxNLocator(nbins=ny_maj))
                ax.yaxis.set_minor_locator(NullLocator() if ny_min==0 else AutoMinorLocator(ny_min))
                if not is_log:
                    ax.xaxis.set_major_locator(MaxNLocator(nbins=nx_maj))
                    ax.xaxis.set_minor_locator(NullLocator() if nx_min==0 else AutoMinorLocator(nx_min))
                else:
                    ax.xaxis.set_major_locator(LogLocator(base=10.0, numticks=nx_maj+2))
                    ax.xaxis.set_minor_locator(NullLocator() if nx_min==0 else LogLocator(base=10.0, subs='auto'))
            except: pass

            top_on, right_on = u.get('top', True), u.get('right', True)
            ax.tick_params(which='both', direction=u.get('tk_dir', 'in'), top=top_on, right=right_on, labelsize=u.get('fs_tick', 10))
            ax.spines['top'].set_visible(top_on)
            ax.spines['right'].set_visible(right_on)
            for sp in ax.spines.values(): sp.set_linewidth(1.2)
            for label in ax.get_xticklabels() + ax.get_yticklabels(): label.set_fontweight(fw_tick)

            if u.get('leg', True):
                loc = u.get('leg_loc', "best")
                if loc == 'outside': leg = ax.legend(frameon=False, fontsize=u.get('fs_leg', 9), bbox_to_anchor=(1.02, 1), loc='upper left')
                else: leg = ax.legend(frameon=False, fontsize=u.get('fs_leg', 9), loc=loc)
                for text in leg.get_texts(): text.set_fontweight(fw_leg)

            if u.get('grid', False):
                ax.grid(True, which='major', ls='--', alpha=0.5)
                if is_log: ax.grid(True, which='minor', ls=':', alpha=0.2)
                
            fig.tight_layout()
            
            # 导出图片并销毁资源
            out_name = f"plot_ELISA_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150)
            fig.clf()
            
            res_text = "📊 【ELISA 4PL 拟合分析完毕】<br>"
            if fit_texts:
                res_text += "<br>".join(fit_texts)
            
            return out_path, res_text
            
        except Exception as e:
            return "", f"ELISA 自动作图引擎执行失败: {str(e)}"