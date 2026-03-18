# plugins/plugin_spr.py
import os
import sys
import json
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDialog, QScrollArea, 
                             QMessageBox, QFileDialog, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings

from qfluentwidgets import (LineEdit, SpinBox, DoubleSpinBox, CheckBox, ComboBox, 
                            BodyLabel, PushButton, PrimaryPushButton, 
                            SubtitleLabel, StrongBodyLabel, CardWidget, ListWidget, FluentIcon as FIF)

from core.plugin_manager import BasePlugin

# ==========================================
# 核心算法区 (原生算法，保持纯净)
# ==========================================
def safe_load_array(filepath, skiprows=0):
    if filepath.lower().endswith(('.xlsx', '.xls')):
        df = pd.read_excel(filepath, header=None, skiprows=skiprows, engine='openpyxl')
        return df.apply(pd.to_numeric, errors='coerce').values
        
    for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "latin1"]:
        try:
            with open(filepath, "r", encoding=enc) as f: content = f.readlines()
            break
        except: continue
        
    data_rows = []
    max_cols = 0
    for i, line in enumerate(content):
        if i < skiprows: continue
        line = line.strip()
        if not line: continue
        
        if '\t' in line: parts = line.split('\t')
        elif ',' in line: parts = line.split(',')
        elif ';' in line: parts = line.split(';')
        else: parts = line.split()
        
        row = []
        for p in parts:
            p = p.strip()
            try: row.append(float(p))
            except ValueError: row.append(np.nan)
        
        if row and not all(np.isnan(x) for x in row):
            data_rows.append(row)
            max_cols = max(max_cols, len(row))
            
    if not data_rows: return np.array([])
    return np.array([r + [np.nan]*(max_cols-len(r)) for r in data_rows], dtype=float)

def guess_kinetics_times(t, fit):
    idx_max = np.argmax(fit)
    t_off_guess = t[idx_max]
    t_on_guess = max(0, t_off_guess - 60.0)
    mask = (t > t_off_guess - 150) & (t < t_off_guess - 10)
    if np.any(mask):
        dt = np.diff(t); dy = np.diff(fit); dt[dt==0] = 1e-9
        deriv = np.zeros_like(fit); deriv[1:] = dy/dt
        idx = np.where(mask)[0]
        if len(idx) > 0: t_on_guess = t[idx[np.argmax(deriv[idx])]]
    return t_on_guess, t_off_guess

def fit_sck_model(t, y_fit, conc, t_on, t_off, skip=1.5):
    mask_a = (t >= t_on + skip) & (t <= t_off)
    mask_d = (t >= t_off + skip)
    t_a, y_a = t[mask_a], y_fit[mask_a]
    t_d, y_d = t[mask_d], y_fit[mask_d]
    if len(t_a) < 10 or len(t_d) < 10: raise ValueError("有效数据点不足")
    def m_diss(t_arr, kb, R0, off): return R0 * np.exp(-kb * (t_arr - t_off)) + off
    popt_d, _ = curve_fit(m_diss, t_d, y_d, p0=[1e-3, y_d[0], 0], bounds=([1e-6, 0, -np.inf], [1.0, np.inf, np.inf]), maxfev=10000)
    kb_opt = popt_d[0]
    def m_assoc(t_arr, ka, Rmax, Rstart):
        kobs = ka * conc + kb_opt
        Req = (ka * conc * Rmax) / kobs
        return Req + (Rstart - Req) * np.exp(-kobs * (t_arr - t_on))
    popt_a, _ = curve_fit(m_assoc, t_a, y_a, p0=[1e5, np.max(y_a), y_a[0]], bounds=([100, np.max(y_a)*0.1, -np.inf], [1e8, np.max(y_a)*10, np.inf]), maxfev=10000)
    return popt_a[0], kb_opt, kb_opt / popt_a[0]

def get_spr_texts(ka, kb, kd, is_bold):
    def fmt(v):
        if v == 0 or np.isnan(v): return "0"
        exp = int(np.floor(np.log10(abs(v)))); c = v / (10**exp)
        return r"{0:.2f}\ \times\ 10^{{{1}}}".format(c, exp) if is_bold else r"{0:.2f} \times 10^{{{1}}}".format(c, exp)
    if is_bold:
        t1 = r"$\mathbf{k_a\ =\ " + fmt(ka) + r"\ M^{-1}s^{-1}}$" + "\n" + r"$\mathbf{k_b\ =\ " + fmt(kb) + r"\ s^{-1}}$"
        if kd == 0 or np.isnan(kd): kd_s = r"0\ M"
        elif kd < 1e-7: kd_s = f"{kd * 1e9:.2f}\\ \\mathrm{{nM}}"
        elif kd < 1e-4: kd_s = f"{kd * 1e6:.2f}\\ \\boldsymbol{{\\mu}}\\mathrm{{M}}"
        elif kd < 1e-1: kd_s = f"{kd * 1e3:.2f}\\ \\mathrm{{mM}}"
        else: kd_s = fmt(kd) + r"\ M"
        return t1, r"$\mathbf{K_D\ =\ " + kd_s + r"}$"
    else:
        t1 = r"$k_a = " + fmt(ka) + r"\ \mathrm{M^{-1}s^{-1}}$" + "\n" + r"$k_b = " + fmt(kb) + r"\ \mathrm{s^{-1}}$"
        if kd == 0 or np.isnan(kd): kd_s = r"0\ \mathrm{M}"
        elif kd < 1e-7: kd_s = f"{kd * 1e9:.2f}\\ \\mathrm{{nM}}"
        elif kd < 1e-4: kd_s = f"{kd * 1e6:.2f}\\ \\mu \\mathrm{{M}}"
        elif kd < 1e-1: kd_s = f"{kd * 1e3:.2f}\\ \\mathrm{{mM}}"
        else: kd_s = fmt(kd) + r"\ \mathrm{M}"
        return t1, r"$K_D = " + kd_s + r"$"

# ==========================================
# 前端：支持【工作台】与【全局设置】双模式的 SPR UI
# ==========================================
class SprUI(QWidget):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(parent)
        self.is_setting_mode = is_setting_mode
        self.ui_vars = {}
        self.file_list = []
        self.setAcceptDrops(True)
        self.settings = QSettings("SciForge", "SprPlugin")
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

    def get_float(self, line_edit, default=0.0):
        try: return float(line_edit.text())
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

        gb_data, l_data = self._create_fluent_group("1. 数据池 (支持拖拽/右键发送)")
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

        gb_wh, l_wh = self._create_fluent_group("2. 全局画板尺寸 (英寸)")
        h_wh = QHBoxLayout(); h_wh.setContentsMargins(0, 0, 0, 0)
        self.ui_vars['spin_w'] = DoubleSpinBox(); self.ui_vars['spin_w'].setRange(1.0, 50.0); self.ui_vars['spin_w'].setValue(7.0); self.ui_vars['spin_w'].setSingleStep(0.5)
        self.ui_vars['spin_h'] = DoubleSpinBox(); self.ui_vars['spin_h'].setRange(1.0, 50.0); self.ui_vars['spin_h'].setValue(5.0); self.ui_vars['spin_h'].setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("W:")); h_wh.addWidget(self.ui_vars['spin_w'], 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("H:")); h_wh.addWidget(self.ui_vars['spin_h'], 1)
        l_wh.addLayout(h_wh)
        left_layout.addWidget(gb_wh)

        gb_param, l_param = self._create_fluent_group("3. SPR 拟合与样式参数")
        left_layout.addWidget(gb_param)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0) 
        scroll_layout.setSpacing(4)
        u = self.ui_vars

        scroll_layout.addWidget(StrongBodyLabel("数据列映射 (Index)"))
        u['c_t']=SpinBox(); u['c_t'].setRange(0, 999); u['c_t'].setValue(0)
        u['c_r']=SpinBox(); u['c_r'].setRange(0, 999); u['c_r'].setValue(1)
        u['c_f']=SpinBox(); u['c_f'].setRange(0, 999); u['c_f'].setValue(2)
        h_col=QHBoxLayout()
        h_col.addWidget(BodyLabel("Time:")); h_col.addWidget(u['c_t'], 1)
        h_col.addWidget(BodyLabel("Raw:")); h_col.addWidget(u['c_r'], 1)
        h_col.addWidget(BodyLabel("Fit:")); h_col.addWidget(u['c_f'], 1)
        scroll_layout.addLayout(h_col)

        scroll_layout.addSpacing(5)
        scroll_layout.addWidget(StrongBodyLabel("SCK 动力学拟合参数"))
        u['conc']=LineEdit(); u['conc'].setText("1e-7")
        self.add_row(scroll_layout, "最高浓度(M):", u['conc'])
        
        u['ton']=LineEdit(); u['ton'].setText("-1")
        u['toff']=LineEdit(); u['toff'].setText("-1")
        self.add_row(scroll_layout, "结合(s):", u['ton'], "解离(s):", u['toff'])
        
        u['skip']=LineEdit(); u['skip'].setText("1.5")
        self.add_row(scroll_layout, "跳过波动(s):", u['skip'])
        
        lbl_hint = BodyLabel("注: 结合/解离填 -1 开启自动寻峰识别")
        lbl_hint.setStyleSheet("color:#888; font-size:11px;")
        scroll_layout.addWidget(lbl_hint)

        if not self.is_setting_mode:
            scroll_layout.addSpacing(5)
            scroll_layout.addWidget(StrongBodyLabel("实时计算结果"))
            u['ka']=LineEdit(); u['ka'].setReadOnly(True)
            u['kb']=LineEdit(); u['kb'].setReadOnly(True)
            u['kd']=LineEdit(); u['kd'].setReadOnly(True)
            self.add_row(scroll_layout, "ka:", u['ka']); self.add_row(scroll_layout, "kb:", u['kb']); self.add_row(scroll_layout, "KD:", u['kd'])

        scroll_layout.addSpacing(5)
        scroll_layout.addWidget(StrongBodyLabel("坐标轴与范围"))
        u['title']=LineEdit(); u['title'].setText("SPR Kinetics")
        self.add_row(scroll_layout, "标题:", u['title'])
        u['xl']=LineEdit(); u['xl'].setText("Time (s)")
        u['yl']=LineEdit(); u['yl'].setText("Response (RU)")
        self.add_row(scroll_layout, "X轴名:", u['xl'], "Y轴名:", u['yl'])
        u['x1']=LineEdit(); u['x2']=LineEdit()
        self.add_row(scroll_layout, "X 范围起:", u['x1'], "止:", u['x2'])
        u['y1']=LineEdit(); u['y2']=LineEdit()
        self.add_row(scroll_layout, "Y 范围起:", u['y1'], "止:", u['y2'])

        scroll_layout.addSpacing(5)
        scroll_layout.addWidget(StrongBodyLabel("高级外观样式"))
        
        lbl_bold = BodyLabel("独立加粗控制:"); lbl_bold.setStyleSheet("color:#666; font-size:11px;")
        scroll_layout.addWidget(lbl_bold)
        
        h_bold = QHBoxLayout(); h_bold.setSpacing(5)
        u['b_title'] = CheckBox("标题"); u['b_title'].setChecked(True); h_bold.addWidget(u['b_title'])
        u['b_label'] = CheckBox("轴名"); u['b_label'].setChecked(True); h_bold.addWidget(u['b_label'])
        u['b_tick'] = CheckBox("刻度"); h_bold.addWidget(u['b_tick'])
        u['b_text'] = CheckBox("文本"); h_bold.addWidget(u['b_text'])
        scroll_layout.addLayout(h_bold)
        
        u['craw']=LineEdit(); u['craw'].setText("#1f77b4")
        u['ls_raw']=ComboBox(); u['ls_raw'].addItems(["-", "--", "-.", ":"])
        self.add_row(scroll_layout, "Raw色:", u['craw'], "型:", u['ls_raw'])
        
        u['cfit']=LineEdit(); u['cfit'].setText("#d62728")
        u['ls_fit']=ComboBox(); u['ls_fit'].addItems(["-", "--", "-.", ":"])
        self.add_row(scroll_layout, "Fit色:", u['cfit'], "型:", u['ls_fit'])
        
        u['fs']=SpinBox(); u['fs'].setRange(6, 40); u['fs'].setValue(12)
        h_misc = QHBoxLayout()
        h_misc.addWidget(BodyLabel("全局字号:")); h_misc.addWidget(u['fs'], 1)
        u['show_txt'] = CheckBox("显示标注"); u['show_txt'].setChecked(True); h_misc.addWidget(u['show_txt'])
        u['grid'] = CheckBox("网格线"); h_misc.addWidget(u['grid'])
        scroll_layout.addLayout(h_misc)

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

        self.btn_plot = PrimaryPushButton("⚡ 执行动力学拟合", icon=FIF.PLAY)
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
        
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_panel)
        splitter.setSizes([350, 750])
        main_layout.addWidget(splitter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.load_file(url.toLocalFile())

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
            self.ui_vars.get('ka', LineEdit()).clear()
            self.ui_vars.get('kb', LineEdit()).clear()
            self.ui_vars.get('kd', LineEdit()).clear()

    def _save_memory(self):
        self.settings.setValue("spr_plugin_params", json.dumps(self.get_config_dict()))

    def _load_memory(self):
        data_str = self.settings.value("spr_plugin_params", "")
        if data_str:
            try: self.apply_config_dict(json.loads(data_str))
            except: pass

    def get_config_dict(self):
        u = self.ui_vars
        config = {
            "c_t": u['c_t'].value(), "c_r": u['c_r'].value(), "c_f": u['c_f'].value(),
            "conc": u['conc'].text(), "ton": u['ton'].text(), "toff": u['toff'].text(), "skip": u['skip'].text(),
            "title": u['title'].text(), "xl": u['xl'].text(), "yl": u['yl'].text(),
            "x1": u['x1'].text(), "x2": u['x2'].text(), "y1": u['y1'].text(), "y2": u['y2'].text(),
            "spin_w": u['spin_w'].value(), "spin_h": u['spin_h'].value(),
            "b_title": u['b_title'].isChecked(), "b_label": u['b_label'].isChecked(), "b_tick": u['b_tick'].isChecked(), "b_text": u['b_text'].isChecked(),
            "craw": u['craw'].text(), "ls_raw": u['ls_raw'].currentText(),
            "cfit": u['cfit'].text(), "ls_fit": u['ls_fit'].currentText(),
            "fs": u['fs'].value(), "show_txt": u['show_txt'].isChecked(), "grid": u['grid'].isChecked()
        }
        if not self.is_setting_mode:
            config["chk_trans"] = u['chk_trans'].isChecked()
            config["combo_fmt"] = u['combo_fmt'].currentText()
        return config

    def apply_config_dict(self, data):
        u = self.ui_vars
        u['c_t'].setValue(data.get("c_t", 0)); u['c_r'].setValue(data.get("c_r", 1)); u['c_f'].setValue(data.get("c_f", 2))
        u['conc'].setText(data.get("conc", "1e-7")); u['ton'].setText(data.get("ton", "-1")); u['toff'].setText(data.get("toff", "-1")); u['skip'].setText(data.get("skip", "1.5"))
        u['title'].setText(data.get("title", "SPR Kinetics")); u['xl'].setText(data.get("xl", "Time (s)")); u['yl'].setText(data.get("yl", "Response (RU)"))
        u['x1'].setText(data.get("x1", "")); u['x2'].setText(data.get("x2", "")); u['y1'].setText(data.get("y1", "")); u['y2'].setText(data.get("y2", ""))
        u['spin_w'].setValue(data.get("spin_w", 7.0)); u['spin_h'].setValue(data.get("spin_h", 5.0))
        u['b_title'].setChecked(data.get("b_title", True)); u['b_label'].setChecked(data.get("b_label", True)); u['b_tick'].setChecked(data.get("b_tick", False)); u['b_text'].setChecked(data.get("b_text", False))
        u['craw'].setText(data.get("craw", "#1f77b4")); u['ls_raw'].setCurrentText(data.get("ls_raw", "-"))
        u['cfit'].setText(data.get("cfit", "#d62728")); u['ls_fit'].setCurrentText(data.get("ls_fit", "-"))
        u['fs'].setValue(data.get("fs", 12)); u['show_txt'].setChecked(data.get("show_txt", True)); u['grid'].setChecked(data.get("grid", False))
        
        if not self.is_setting_mode and "chk_trans" in u:
            u['chk_trans'].setChecked(data.get("chk_trans", False))
            u['combo_fmt'].setCurrentText(data.get("combo_fmt", "pdf"))

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 SPR 参数模板", "spr_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入 SPR 参数模板", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f: self.apply_config_dict(json.load(f))
            if not self.is_setting_mode: self.trigger_render()

    def save_settings_and_close(self):
        self._save_memory()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog): parent_dlg.accept()

    def trigger_render(self, *args):
        if self.is_setting_mode: return
        self._save_memory()
        self.render_plot()
        
        dpi = self.fig.dpi
        w_px = int(self.ui_vars['spin_w'].value() * dpi)
        h_px = int(self.ui_vars['spin_h'].value() * dpi)
        self.canvas.setFixedSize(w_px, h_px)
        self.canvas_container.updateGeometry()

    def export_plot(self):
        if self.is_setting_mode: return
        fmt = self.ui_vars['combo_fmt'].currentText()
        is_transparent = self.ui_vars['chk_trans'].isChecked()
        row = self.list_widget.currentRow()
        default_name = os.path.splitext(self.list_widget.item(max(0,row)).text())[0] + f"_SPR.{fmt}" if self.list_widget.count() > 0 else f"SPR_Plot.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出图表", default_name, f"Images (*.{fmt})")
        if file_path:
            try:
                self.fig.savefig(file_path, dpi=600, bbox_inches="tight", transparent=is_transparent)
                QMessageBox.information(self, "成功", f"图表已导出:\n{file_path}")
            except Exception as e: QMessageBox.critical(self, "导出失败", str(e))

    def render_plot(self):
        if self.is_setting_mode: return
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.file_list): return
        fp = self.file_list[row]
        title_text = os.path.splitext(os.path.basename(fp))[0]
        
        self.fig.clear()
        u = self.ui_vars
        self.fig.set_size_inches(u['spin_w'].value(), u['spin_h'].value())
        self.ax = self.fig.add_subplot(111)
        
        data = safe_load_array(fp)
        if data.size == 0: return
        
        max_col = max(u['c_t'].value(), u['c_r'].value(), u['c_f'].value())
        if data.shape[1] <= max_col:
            self.ax.text(0.5, 0.5, f"数据列不足！请检查 Index 设置\n最大列数需 > {max_col}", ha='center', va='center')
            self.canvas.draw()
            return
            
        t, raw, fit = data[:, u['c_t'].value()], data[:, u['c_r'].value()], data[:, u['c_f'].value()]
        mask = ~np.isnan(t) & ~np.isnan(fit)
        t, raw, fit = t[mask], raw[mask], fit[mask]
        
        conc = self.get_float(u['conc'], 1e-7)
        t_on = self.get_float(u['ton'], -1)
        t_off = self.get_float(u['toff'], -1)
        skip_val = self.get_float(u['skip'], 1.5)
        
        if t_on < 0 or t_off < 0:
            t_on, t_off = guess_kinetics_times(t, fit)
            u['ton'].setText(f"{t_on:.1f}")
            u['toff'].setText(f"{t_off:.1f}")
        
        try: 
            ka, kb, kd = fit_sck_model(t, fit, conc, t_on, t_off, skip=skip_val)
        except: 
            ka, kb, kd = 0, 0, 0
        
        u['ka'].setText(f"{ka:.2e}")
        u['kb'].setText(f"{kb:.2e}")
        u['kd'].setText(f"{kd:.2e}")
        
        fs = u['fs'].value()
        fw_title = 'bold' if u['b_title'].isChecked() else 'normal'
        fw_label = 'bold' if u['b_label'].isChecked() else 'normal'
        fw_tick  = 'bold' if u['b_tick'].isChecked() else 'normal'
        fw_text  = 'bold' if u['b_text'].isChecked() else 'normal'

        self.ax.plot(t, raw, color=u['craw'].text(), lw=1.5, ls=u['ls_raw'].currentText(), label="Raw Data")
        self.ax.plot(t, fit, color=u['cfit'].text(), lw=2.0, ls=u['ls_fit'].currentText(), label="Fitted Curve")
        
        if u['show_txt'].isChecked():
            txt_1, txt_2 = get_spr_texts(ka, kb, kd, is_bold=u['b_text'].isChecked())
            self.ax.text(0.05, 0.95, txt_1, transform=self.ax.transAxes, fontsize=fs-1, va='top', fontweight=fw_text)
            self.ax.text(0.95, 0.05, txt_2, transform=self.ax.transAxes, fontsize=fs-1, va='bottom', ha='right', fontweight=fw_text)

        self.ax.set_xlabel(u['xl'].text(), fontsize=fs, fontweight=fw_label)
        self.ax.set_ylabel(u['yl'].text(), fontsize=fs, fontweight=fw_label)
        self.ax.set_title(u['title'].text() if u['title'].text() else title_text, fontsize=fs+2, fontweight=fw_title, pad=10)
        
        if u['x1'].text(): self.ax.set_xlim(left=self.get_float(u['x1']))
        if u['x2'].text(): self.ax.set_xlim(right=self.get_float(u['x2']))
        if u['y1'].text(): self.ax.set_ylim(bottom=self.get_float(u['y1']))
        if u['y2'].text(): self.ax.set_ylim(top=self.get_float(u['y2']))

        self.ax.tick_params(which='major', labelsize=fs-1)
        for label in self.ax.get_xticklabels() + self.ax.get_yticklabels(): label.set_fontweight(fw_tick)

        self.ax.spines['top'].set_visible(False)
        self.ax.spines['right'].set_visible(False)
        for sp in self.ax.spines.values(): sp.set_linewidth(1.5)
            
        if u['grid'].isChecked():
            self.ax.grid(True, which='major', ls='--', alpha=0.5)
        
        self.fig.tight_layout()
        self.canvas.draw()


# ==========================================
# 后端：插件描述器与全局入口联动
# ==========================================
class SPRPlugin(BasePlugin):
    plugin_id = "spr_analyzer"
    plugin_name = "SPR 动力学拟合引擎"
    icon = "📈"

    trigger_tag = "SPR"
    
    def get_ui(self, parent=None):
        return SprUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard(
            "配置全局默认参数", 
            FIF.EDIT, 
            "📈 SPR 动力学分析", 
            "修改工作站中 SPR 传感图的默认列索引、寻峰规则与动力学常数展示外观", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card) 
            dlg.setWindowTitle("SPR 全局默认参数预设中心")
            dlg.resize(460, 750) 
            layout = QVBoxLayout(dlg)
            
            settings_ui = SprUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    # 【核心注入】：纯后台、线程安全的自动化作图逻辑
    @staticmethod
    def run(file_path, archive_dir):
        try:
            # 1. 提取全局 UI 存储的字典设定
            settings = QSettings("SciForge", "SprPlugin")
            param_str = settings.value("spr_plugin_params", "")
            u = {}
            if param_str:
                try: u = json.loads(param_str)
                except: pass
            
            c_t = u.get("c_t", 0)
            c_r = u.get("c_r", 1)
            c_f = u.get("c_f", 2)
            conc = float(u.get("conc", 1e-7))
            t_on = float(u.get("ton", -1))
            t_off = float(u.get("toff", -1))
            skip_val = float(u.get("skip", 1.5))
            
            # 2. 静默读取数据
            data = safe_load_array(file_path)
            max_col = max(c_t, c_r, c_f)
            if data.size == 0 or data.shape[1] <= max_col:
                return "", "【SPR分析跳过】数据为空或列数不足（请检查 Index 映射）。"
            
            t, raw, fit = data[:, c_t], data[:, c_r], data[:, c_f]
            mask = ~np.isnan(t) & ~np.isnan(fit)
            t, raw, fit = t[mask], raw[mask], fit[mask]
            
            if t_on < 0 or t_off < 0:
                t_on, t_off = guess_kinetics_times(t, fit)
                
            try:
                ka, kb, kd = fit_sck_model(t, fit, conc, t_on, t_off, skip=skip_val)
            except Exception:
                ka, kb, kd = 0, 0, 0
                
            # 3. 线程安全绘图：摒弃 pyplot 状态机，使用纯底层的 FigureCanvasAgg
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt
            
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False
            
            fig = Figure(figsize=(u.get("spin_w", 7.0), u.get("spin_h", 5.0)), dpi=150)
            canvas = FigureCanvasAgg(fig) # 此处为非 GUI 画布
            ax = fig.add_subplot(111)
            
            fs = u.get("fs", 12)
            fw_title = 'bold' if u.get("b_title", True) else 'normal'
            fw_label = 'bold' if u.get("b_label", True) else 'normal'
            fw_tick  = 'bold' if u.get("b_tick", False) else 'normal'
            fw_text  = 'bold' if u.get("b_text", False) else 'normal'

            ax.plot(t, raw, color=u.get("craw", "#1f77b4"), lw=1.5, ls=u.get("ls_raw", "-"), label="Raw Data")
            ax.plot(t, fit, color=u.get("cfit", "#d62728"), lw=2.0, ls=u.get("ls_fit", "-"), label="Fitted Curve")
            
            if u.get("show_txt", True):
                txt_1, txt_2 = get_spr_texts(ka, kb, kd, is_bold=u.get("b_text", False))
                ax.text(0.05, 0.95, txt_1, transform=ax.transAxes, fontsize=fs-1, va='top', fontweight=fw_text)
                ax.text(0.95, 0.05, txt_2, transform=ax.transAxes, fontsize=fs-1, va='bottom', ha='right', fontweight=fw_text)

            title_text = os.path.splitext(os.path.basename(file_path))[0]
            ax.set_xlabel(u.get("xl", "Time (s)"), fontsize=fs, fontweight=fw_label)
            ax.set_ylabel(u.get("yl", "Response (RU)"), fontsize=fs, fontweight=fw_label)
            ax.set_title(u.get("title", "SPR Kinetics") if u.get("title", "") else title_text, fontsize=fs+2, fontweight=fw_title, pad=10)
            
            if u.get("x1", ""): ax.set_xlim(left=float(u["x1"]))
            if u.get("x2", ""): ax.set_xlim(right=float(u["x2"]))
            if u.get("y1", ""): ax.set_ylim(bottom=float(u["y1"]))
            if u.get("y2", ""): ax.set_ylim(top=float(u["y2"]))

            ax.tick_params(which='major', labelsize=fs-1)
            for label in ax.get_xticklabels() + ax.get_yticklabels(): label.set_fontweight(fw_tick)

            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            for sp in ax.spines.values(): sp.set_linewidth(1.5)
                
            if u.get("grid", False):
                ax.grid(True, which='major', ls='--', alpha=0.5)
            
            fig.tight_layout()
            
            # 4. 导出图片并销毁资源防内存泄露
            out_name = f"plot_SPR_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150)
            fig.clf()
            
            # 5. 返回结果给中枢
            return out_path, f"🔬 【SPR 动力学拟合完毕】<br>计算结果: ka={ka:.2e}, kb={kb:.2e}, KD={kd:.2e}"
            
        except Exception as e:
            return "", f"SPR 自动作图引擎执行失败: {str(e)}"