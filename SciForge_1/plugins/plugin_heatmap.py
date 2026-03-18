# plugins/plugin_heatmap.py
import os
import sys
import json
from io import StringIO
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QDialog, QScrollArea, 
                             QMessageBox, QFileDialog, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings

from qfluentwidgets import (LineEdit, SpinBox, DoubleSpinBox, CheckBox, ComboBox, 
                            BodyLabel, PushButton, PlainTextEdit, PrimaryPushButton, 
                            SubtitleLabel, StrongBodyLabel, CardWidget, ListWidget, FluentIcon as FIF)

from core.plugin_manager import BasePlugin

try:
    from scipy.spatial.distance import pdist
    from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.patheffects
    HAS_SCI_LIBS = True
except ImportError:
    HAS_SCI_LIBS = False

# ==========================================
# 核心算法区 (原生算法，保持纯净)
# ==========================================
def safe_read_bli_file(path):
    try:
        if str(path).lower().endswith('.csv'):
            df = pd.read_csv(path, sep=None, engine='python', index_col=0)
        else:
            df = pd.read_excel(path, index_col=0)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        df = df.apply(pd.to_numeric, errors='coerce')
        return df
    except Exception as e:
        return None

def calculate_inhibition(df, ref_name="PBST"):
    if df is None or df.empty: return None
    ref_name = str(ref_name).strip().lower()
    
    ref_row = None
    for idx in df.index:
        if str(idx).lower() == ref_name:
            ref_row = df.loc[idx]
            break
    
    if ref_row is None: return df
    
    ref_safe = ref_row.replace(0, 1e-9)
    ratio = df.div(ref_safe, axis=1)
    inhibition = 1.0 - ratio
    
    inhibition = inhibition.replace([np.inf, -np.inf], 0).fillna(0)
    inhibition = inhibition.clip(0, 1)
    
    cols_to_drop = [c for c in inhibition.columns if str(c).lower() == ref_name]
    if cols_to_drop: inhibition.drop(columns=cols_to_drop, inplace=True)
    rows_to_drop = [r for r in inhibition.index if str(r).lower() == ref_name]
    if rows_to_drop: inhibition.drop(index=rows_to_drop, inplace=True)
        
    return inhibition

def process_bli_data(df, calc_mode="inhibition", ref_name="PBST"):
    if df is None or df.empty: return None
    if "1 -" in calc_mode: df = calculate_inhibition(df, ref_name)
    df.fillna(0, inplace=True)
    df.replace([np.inf, -np.inf], 0, inplace=True)
    return df

# ==========================================
# 前端：支持【工作台】与【全局设置】双模式的 Heatmap UI
# ==========================================
class HeatmapUI(QWidget):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(parent)
        self.is_setting_mode = is_setting_mode
        self.ui_vars = {}
        self.file_list = []
        self.export_df = None
        self.setAcceptDrops(True)
        self.settings = QSettings("SciForge", "HeatmapPlugin")
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
        self.ui_vars['spin_w'] = DoubleSpinBox(); self.ui_vars['spin_w'].setRange(1.0, 50.0); self.ui_vars['spin_w'].setValue(8.0); self.ui_vars['spin_w'].setSingleStep(0.5)
        self.ui_vars['spin_h'] = DoubleSpinBox(); self.ui_vars['spin_h'].setRange(1.0, 50.0); self.ui_vars['spin_h'].setValue(6.0); self.ui_vars['spin_h'].setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("W:")); h_wh.addWidget(self.ui_vars['spin_w'], 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("H:")); h_wh.addWidget(self.ui_vars['spin_h'], 1)
        l_wh.addLayout(h_wh)
        left_layout.addWidget(gb_wh)

        gb_param, l_param = self._create_fluent_group("3. 聚类算法与样式参数")
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

        u['text_data'] = PlainTextEdit()
        u['text_data'].setPlaceholderText("覆盖数据：可直接粘贴包含表头与侧边的文本矩阵...")
        u['text_data'].setFixedHeight(60)
        if not self.is_setting_mode:
            scroll_layout.addWidget(u['text_data'])

        scroll_layout.addWidget(StrongBodyLabel("模式与计算逻辑"))
        u['mode'] = ComboBox()
        u['mode'].addItems(["Heatmap (热图与层级聚类)", "K-Means (PCA降维散点图)"])
        self.add_row(scroll_layout, "当前模式:", u['mode'])
        
        u['ref'] = LineEdit(); u['ref'].setText("PBST")
        self.add_row(scroll_layout, "参考行(对照):", u['ref'])
        
        u['calc'] = ComboBox(); u['calc'].addItems(["自动计算: 1 - (Row / Ref)", "使用原始数据"])
        self.add_row(scroll_layout, "计算方式:", u['calc'])
        
        h_chk1 = QHBoxLayout()
        u['trans'] = CheckBox("转置数据"); u['trans'].setChecked(True); h_chk1.addWidget(u['trans'])
        u['merge'] = CheckBox("合并多文件"); u['merge'].setChecked(True); h_chk1.addWidget(u['merge'])
        scroll_layout.addLayout(h_chk1)

        scroll_layout.addSpacing(5)
        scroll_layout.addWidget(StrongBodyLabel("外观与文字控制"))
        
        lbl_bold = BodyLabel("独立加粗:")
        lbl_bold.setStyleSheet("color:#666; font-size:11px;")
        scroll_layout.addWidget(lbl_bold)
        
        h_bold = QHBoxLayout(); h_bold.setSpacing(5)
        u['b_title'] = CheckBox("标题"); u['b_title'].setChecked(True); h_bold.addWidget(u['b_title'])
        u['b_label'] = CheckBox("轴名"); u['b_label'].setChecked(True); h_bold.addWidget(u['b_label'])
        u['b_tick'] = CheckBox("刻度"); h_bold.addWidget(u['b_tick'])
        u['b_annot'] = CheckBox("点/图注"); h_bold.addWidget(u['b_annot'])
        scroll_layout.addLayout(h_bold)
        
        lbl_fs = BodyLabel("字号矩阵:"); lbl_fs.setStyleSheet("color:#666; font-size:11px; margin-top:4px;")
        scroll_layout.addWidget(lbl_fs)
        
        u['fs_title'] = SpinBox(); u['fs_title'].setRange(6, 40); u['fs_title'].setValue(14)
        u['fs_label'] = SpinBox(); u['fs_label'].setRange(6, 40); u['fs_label'].setValue(12)
        u['fs_tick']  = SpinBox(); u['fs_tick'].setRange(6, 40); u['fs_tick'].setValue(9)
        
        h_fs = QHBoxLayout()
        h_fs.addWidget(BodyLabel("标题:")); h_fs.addWidget(u['fs_title'], 1)
        h_fs.addWidget(BodyLabel("轴名:")); h_fs.addWidget(u['fs_label'], 1)
        h_fs.addWidget(BodyLabel("刻度:")); h_fs.addWidget(u['fs_tick'], 1)
        scroll_layout.addLayout(h_fs)
        
        u['cmap'] = ComboBox(); u['cmap'].addItems(["Default (Soft RdBu)", "RdBu_r", "viridis", "coolwarm", "magma", "Blues", "YlGnBu"])
        u['annot'] = CheckBox("显示数值"); u['annot'].setChecked(True)
        self.add_row(scroll_layout, "色带:", u['cmap'], "", u['annot'])
        
        u['auto_size'] = CheckBox("自适应画布(防拥挤)"); u['auto_size'].setChecked(True)
        u['square'] = CheckBox("强制正方形"); u['square'].setChecked(False)
        self.add_row(scroll_layout, "", u['auto_size'], "", u['square'])
        
        u['grid'] = CheckBox("切割网格"); u['grid'].setChecked(True)
        u['ms'] = SpinBox(); u['ms'].setRange(10, 500); u['ms'].setValue(120)
        self.add_row(scroll_layout, "KMeans点大小:", u['ms'], "", u['grid'])

        scroll_layout.addSpacing(5)
        scroll_layout.addWidget(StrongBodyLabel("聚类算法参数"))
        u['do_cluster'] = CheckBox("执行聚类 (显示树状图)"); u['do_cluster'].setChecked(True)
        scroll_layout.addWidget(u['do_cluster'])
        
        u['cutoff'] = LineEdit(); u['cutoff'].setText("0.4")
        self.add_row(scroll_layout, "Cutoff:", u['cutoff'])
        
        u['metric'] = ComboBox(); u['metric'].addItems(["cosine", "euclidean", "correlation"])
        u['method'] = ComboBox(); u['method'].addItems(["average", "single", "complete", "ward"])
        self.add_row(scroll_layout, "距离:", u['metric'], "方法:", u['method'])
        
        u['k'] = SpinBox(); u['k'].setRange(2, 50); u['k'].setValue(4)
        self.add_row(scroll_layout, "K-means K:", u['k'])

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

        self.btn_plot = PrimaryPushButton("⚡ 执行聚类与渲染", icon=FIF.PLAY)
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
        
        btn_csv = PushButton("💾 导出数据 (.csv)")
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
            self.ui_vars['text_data'].clear()

    def get_heatmap_df(self):
        u = self.ui_vars
        mode = u['calc'].currentText()
        ref_name = u['ref'].text()
        processed_dfs = []
        
        raw_text = u['text_data'].toPlainText().strip()
        if raw_text:
            try:
                df = pd.read_csv(StringIO(raw_text), sep='\t', index_col=0)
                if df.shape[1] < 2: df = pd.read_csv(StringIO(raw_text), sep=r'\s+', index_col=0)
                df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                df = df.apply(pd.to_numeric, errors='coerce')
                df = process_bli_data(df, mode, ref_name)
                processed_dfs.append(df)
            except Exception as e:
                raise ValueError(f"粘贴数据解析失败:\n{str(e)}")
        else:
            if not self.file_list:
                raise ValueError("请先粘贴数据，或在上方添加文件！")
            
            target_paths = self.file_list if u['merge'].isChecked() else [self.file_list[self.list_widget.currentRow()]] if self.list_widget.currentRow() >= 0 else []
            
            for fp in target_paths:
                df_raw = safe_read_bli_file(fp)
                if df_raw is not None:
                    df_calc = process_bli_data(df_raw, mode, ref_name)
                    processed_dfs.append(df_calc)

        if not processed_dfs: 
            raise ValueError("未能提取出有效数据！")
        
        final_df = pd.DataFrame()
        global_idx_counts = {}
        for df in processed_dfs:
            if df is None or df.empty: continue
            new_indices = []
            for idx in df.index:
                s_idx = str(idx)
                if s_idx not in global_idx_counts:
                    global_idx_counts[s_idx] = 1
                    new_indices.append(s_idx)
                else:
                    global_idx_counts[s_idx] += 1
                    new_indices.append(f"{s_idx}_{global_idx_counts[s_idx]}")
            df.index = new_indices
            
            if final_df.empty: 
                final_df = df
            else: 
                final_df = pd.concat([final_df, df], axis=0, join='outer')
        
        final_df.fillna(0, inplace=True)
        if u['trans'].isChecked(): final_df = final_df.T
            
        return final_df

    def _save_memory(self):
        self.settings.setValue("heatmap_plugin_params", json.dumps(self.get_config_dict()))

    def _load_memory(self):
        data_str = self.settings.value("heatmap_plugin_params", "")
        if data_str:
            try: self.apply_config_dict(json.loads(data_str))
            except: pass

    def get_config_dict(self):
        u = self.ui_vars
        config = {
            "mode": u['mode'].currentText(), "ref": u['ref'].text(), "calc": u['calc'].currentText(),
            "trans": u['trans'].isChecked(), "merge": u['merge'].isChecked(),
            "spin_w": u['spin_w'].value(), "spin_h": u['spin_h'].value(),
            "b_title": u['b_title'].isChecked(), "b_label": u['b_label'].isChecked(), "b_tick": u['b_tick'].isChecked(), "b_annot": u['b_annot'].isChecked(),
            "fs_title": u['fs_title'].value(), "fs_label": u['fs_label'].value(), "fs_tick": u['fs_tick'].value(),
            "cmap": u['cmap'].currentText(), "annot": u['annot'].isChecked(),
            "auto_size": u['auto_size'].isChecked(), "square": u['square'].isChecked(),
            "grid": u['grid'].isChecked(), "ms": u['ms'].value(),
            "do_cluster": u['do_cluster'].isChecked(), "cutoff": u['cutoff'].text(),
            "metric": u['metric'].currentText(), "method": u['method'].currentText(), "k": u['k'].value()
        }
        if not self.is_setting_mode:
            config["chk_trans"] = u['chk_trans'].isChecked()
            config["combo_fmt"] = u['combo_fmt'].currentText()
        return config

    def apply_config_dict(self, data):
        u = self.ui_vars
        u['mode'].setCurrentText(data.get("mode", "Heatmap (热图与层级聚类)")); u['ref'].setText(data.get("ref", "PBST")); u['calc'].setCurrentText(data.get("calc", "自动计算: 1 - (Row / Ref)"))
        u['trans'].setChecked(data.get("trans", True)); u['merge'].setChecked(data.get("merge", True))
        u['spin_w'].setValue(data.get("spin_w", 8.0)); u['spin_h'].setValue(data.get("spin_h", 6.0))
        u['b_title'].setChecked(data.get("b_title", True)); u['b_label'].setChecked(data.get("b_label", True)); u['b_tick'].setChecked(data.get("b_tick", True)); u['b_annot'].setChecked(data.get("b_annot", False))
        u['fs_title'].setValue(data.get("fs_title", 14)); u['fs_label'].setValue(data.get("fs_label", 12)); u['fs_tick'].setValue(data.get("fs_tick", 9))
        u['cmap'].setCurrentText(data.get("cmap", "Default (Soft RdBu)")); u['annot'].setChecked(data.get("annot", True))
        u['auto_size'].setChecked(data.get("auto_size", True)); u['square'].setChecked(data.get("square", False))
        u['grid'].setChecked(data.get("grid", True)); u['ms'].setValue(data.get("ms", 120))
        u['do_cluster'].setChecked(data.get("do_cluster", True)); u['cutoff'].setText(data.get("cutoff", "0.4"))
        u['metric'].setCurrentText(data.get("metric", "cosine")); u['method'].setCurrentText(data.get("method", "average")); u['k'].setValue(data.get("k", 4))
        
        if not self.is_setting_mode and "chk_trans" in u:
            u['chk_trans'].setChecked(data.get("chk_trans", False))
            u['combo_fmt'].setCurrentText(data.get("combo_fmt", "pdf"))

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存 Heatmap 参数模板", "heatmap_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入 Heatmap 参数模板", "", "JSON Files (*.json)")
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
        default_name = os.path.splitext(self.list_widget.item(max(0,row)).text())[0] + f"_Heatmap.{fmt}" if self.list_widget.count() > 0 else f"Heatmap_Plot.{fmt}"
        file_path, _ = QFileDialog.getSaveFileName(self, "导出图表", default_name, f"Images (*.{fmt})")
        if file_path:
            try:
                self.fig.savefig(file_path, dpi=600, bbox_inches="tight", transparent=is_transparent)
                QMessageBox.information(self, "成功", f"图表已导出:\n{file_path}")
            except Exception as e: QMessageBox.critical(self, "导出失败", str(e))

    def save_csv(self):
        if self.export_df is None or self.export_df.empty:
            QMessageBox.warning(self, "提示", "目前没有可导出的数据，请先渲染图表！")
            return
        default_name = "Heatmap_CalcResult.csv"
        row = self.list_widget.currentRow()
        if row >= 0 and row < len(self.file_list) and not self.ui_vars['text_data'].toPlainText().strip() and not self.ui_vars['merge'].isChecked():
            default_name = os.path.splitext(self.list_widget.item(row).text())[0] + "_CalcResult.csv"
            
        path, _ = QFileDialog.getSaveFileName(self, "导出计算结果", default_name, "CSV Files (*.csv)")
        if path:
            try:
                self.export_df.to_csv(path)
                QMessageBox.information(self, "成功", f"数据已成功导出至:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    def render_plot(self):
        if self.is_setting_mode: return
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self.export_df = None

        if not HAS_SCI_LIBS:
            self.ax.text(0.5, 0.5, "缺少 scipy/sklearn 库，无法聚类计算", ha='center')
            self.canvas.draw()
            return
            
        try:
            df = self.get_heatmap_df()
        except Exception as e:
            self.ax.text(0.5, 0.5, f"获取数据失败:\n{str(e)}", ha='center', va='center')
            self.canvas.draw()
            return
            
        self.export_df = df.copy() 
        u = self.ui_vars
        
        # 自适应画布
        if u['auto_size'].isChecked():
            cell_size = 0.55 if u['square'].isChecked() else 0.45
            min_w = max(5.0, df.shape[1] * cell_size + 3.0) 
            min_h = max(4.0, df.shape[0] * cell_size + 2.0) 
            u['spin_w'].setValue(min_w)
            u['spin_h'].setValue(min_h)
            
        self.fig.set_size_inches(u['spin_w'].value(), u['spin_h'].value())
        
        fw_title = 'bold' if u['b_title'].isChecked() else 'normal'
        fw_label = 'bold' if u['b_label'].isChecked() else 'normal'
        fw_tick  = 'bold' if u['b_tick'].isChecked() else 'normal'
        fw_annot = 'bold' if u['b_annot'].isChecked() else 'normal'

        fs_title = u['fs_title'].value()
        fs_label = u['fs_label'].value()
        fs_tick  = u['fs_tick'].value()
        is_inhib = "1 -" in u['calc'].currentText()

        # ================== Heatmap 模式 ==================
        if "Heatmap" in u['mode'].currentText():
            do_cluster = u['do_cluster'].isChecked()
            divider = make_axes_locatable(self.ax)
            
            if do_cluster and df.shape[1] >= 2:
                dist = np.nan_to_num(pdist(df.T + 1e-9, metric=u['metric'].currentText()))
                Z = linkage(dist, method=u['method'].currentText())
                
                cutoff_val = self.get_float(u['cutoff'], 0.4)
                color_threshold = cutoff_val * max(Z[:,2]) if len(Z) > 0 else 0
                
                ax_cbar_cluster = divider.append_axes("top", size="4%", pad=0.01) 
                ax_tree = divider.append_axes("top", size="15%", pad=0.0)
                
                dendro = dendrogram(Z, ax=ax_tree, no_labels=True, color_threshold=color_threshold, above_threshold_color='#555555')
                ax_tree.axis('off')
                
                leaves_order = dendro['leaves']
                df_plot = df.iloc[:, leaves_order]
                
                clusters = fcluster(Z, t=color_threshold, criterion='distance')
                clusters_ordered = clusters[leaves_order]
                try: cmap_cluster = matplotlib.colormaps["tab10"]
                except: cmap_cluster = cm.get_cmap("tab10")
                ax_cbar_cluster.imshow([clusters_ordered], aspect='auto', cmap=cmap_cluster, interpolation='nearest')
                ax_cbar_cluster.axis('off')
            else:
                df_plot = df
                do_cluster = False

            cmap_sel = u['cmap'].currentText()
            if cmap_sel == "Default (Soft RdBu)":
                colors = ["#63aaff", "#ffffff", "#ff6b6b"]
                cmap = LinearSegmentedColormap.from_list("soft_rdbu", colors)
            else: cmap = cmap_sel
            
            aspect_val = 'equal' if u['square'].isChecked() else 'auto'
            im = self.ax.imshow(df_plot, aspect=aspect_val, cmap=cmap, interpolation='nearest')
            
            if u['annot'].isChecked():
                for i in range(len(df_plot.index)):
                    for j in range(len(df_plot.columns)):
                        val = df_plot.iloc[i, j]
                        txt_val = f"{val*100:.0f}" if is_inhib else f"{val:.1f}"
                        self.ax.text(j, i, txt_val, 
                                     ha="center", va="center", color="black", fontsize=fs_tick, fontweight=fw_annot,
                                     path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="white")])

            self.ax.set_xticks(range(len(df_plot.columns)))
            self.ax.set_yticks(range(len(df_plot.index)))
            self.ax.set_xticklabels(df_plot.columns, rotation=90, fontsize=fs_tick, fontweight=fw_tick)
            self.ax.set_yticklabels(df_plot.index, fontsize=fs_tick, fontweight=fw_tick)
            
            if u['grid'].isChecked():
                self.ax.set_xticks(np.arange(df_plot.shape[1] + 1) - 0.5, minor=True)
                self.ax.set_yticks(np.arange(df_plot.shape[0] + 1) - 0.5, minor=True)
                self.ax.grid(which="minor", color="white", linestyle='-', linewidth=2)
                self.ax.tick_params(which="minor", bottom=False, left=False)
            
            self.ax.set_title("")
            
            cbar = plt.colorbar(im, cax=divider.append_axes("right", size="3%", pad=0.1))
            cbar_label = "Inhibition Rate" if is_inhib else "Value"
            cbar.set_label(cbar_label, fontsize=fs_label, fontweight=fw_label, labelpad=10)
            
        # ================== K-Means 模式 ==================
        else:
            k = u['k'].value()
            if len(df) < k: return
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            clusters = kmeans.fit_predict(df)
            coords = PCA(n_components=2).fit_transform(df)
            
            self.export_df['Cluster'] = clusters 
            
            try: cmap_km = matplotlib.colormaps["tab10"]
            except: cmap_km = cm.get_cmap("tab10")
            
            self.ax.scatter(coords[:,0], coords[:,1], c=clusters, cmap=cmap_km, s=u['ms'].value(), edgecolors='white', alpha=0.9)
            for i, txt in enumerate(df.index):
                self.ax.annotate(txt, (coords[i,0], coords[i,1]), xytext=(6,6), textcoords='offset points', fontsize=fs_tick, fontweight=fw_annot)
            
            self.ax.set_title(f"K-Means PCA Scatter (K={k})", fontweight=fw_title, fontsize=fs_title)
            
            if u['grid'].isChecked():
                self.ax.grid(True, ls='--', alpha=0.5)

        self.fig.tight_layout()
        self.canvas.draw()

# ==========================================
# 后端：插件描述器与全局入口联动
# ==========================================
class HeatmapPlugin(BasePlugin):
    plugin_id = "heatmap_analyzer"
    plugin_name = "BLI 热图与聚类分析"
    icon = "🔥"
    
    # 【核心 1：向全局系统宣告自己处理什么标签的实验数据】
    trigger_tag = "BLI 热图" 

    def get_ui(self, parent=None):
        return HeatmapUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard(
            "配置全局默认参数", 
            FIF.EDIT, 
            "🔥 BLI 热图与聚类分析", 
            "修改工作站中热图的默认聚类算法、色带模板与外观偏好", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card) 
            dlg.setWindowTitle("Heatmap 全局默认参数预设中心")
            dlg.resize(460, 750) 
            layout = QVBoxLayout(dlg)
            layout.setContentsMargins(10, 10, 10, 10)
            
            settings_ui = HeatmapUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    # 【核心 2：纯后台、无 UI 依赖的静默计算引擎】
    @staticmethod
    def run(file_path, archive_dir):
        try:
            settings = QSettings("SciForge", "HeatmapPlugin")
            param_str = settings.value("heatmap_plugin_params", "")
            u = {}
            if param_str:
                try: u = json.loads(param_str)
                except: pass

            if not HAS_SCI_LIBS:
                return "", "【BLI 热图分析跳过】当前环境缺少 scipy/sklearn 依赖库，无法执行聚类计算。"

            df_raw = safe_read_bli_file(file_path)
            if df_raw is None or df_raw.empty:
                return "", "【BLI 热图分析跳过】数据文件读取失败或格式不支持。"

            # 获取计算参数
            calc_mode = u.get("calc", "自动计算: 1 - (Row / Ref)")
            ref_name = u.get("ref", "PBST")
            df = process_bli_data(df_raw, calc_mode, ref_name)

            if df is None or df.empty:
                return "", "【BLI 热图分析跳过】数据处理后为空矩阵。"

            if u.get("trans", True):
                df = df.T

            # 动态计算自适应画布大小
            w, h = float(u.get("spin_w", 8.0)), float(u.get("spin_h", 6.0))
            if u.get("auto_size", True):
                cell_size = 0.55 if u.get("square", False) else 0.45
                w = max(5.0, df.shape[1] * cell_size + 3.0)
                h = max(4.0, df.shape[0] * cell_size + 2.0)

            # 引入无界面的 Agg 引擎进行绘制
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt
            from mpl_toolkits.axes_grid1 import make_axes_locatable
            from matplotlib.colors import LinearSegmentedColormap
            import matplotlib.patheffects

            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False

            fig = Figure(figsize=(w, h), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)

            fw_title = 'bold' if u.get('b_title', True) else 'normal'
            fw_label = 'bold' if u.get('b_label', True) else 'normal'
            fw_tick  = 'bold' if u.get('b_tick', True) else 'normal'
            fw_annot = 'bold' if u.get('b_annot', False) else 'normal'

            fs_title = u.get('fs_title', 14)
            fs_label = u.get('fs_label', 12)
            fs_tick  = u.get('fs_tick', 9)
            is_inhib = "1 -" in calc_mode

            mode_str = u.get('mode', "Heatmap (热图与层级聚类)")
            
            if "Heatmap" in mode_str:
                do_cluster = u.get('do_cluster', True)
                divider = make_axes_locatable(ax)
                
                if do_cluster and df.shape[1] >= 2:
                    dist = np.nan_to_num(pdist(df.T + 1e-9, metric=u.get('metric', 'cosine')))
                    Z = linkage(dist, method=u.get('method', 'average'))
                    
                    cutoff_val = float(u.get('cutoff', 0.4))
                    color_threshold = cutoff_val * max(Z[:,2]) if len(Z) > 0 else 0
                    
                    ax_cbar_cluster = divider.append_axes("top", size="4%", pad=0.01) 
                    ax_tree = divider.append_axes("top", size="15%", pad=0.0)
                    
                    dendro = dendrogram(Z, ax=ax_tree, no_labels=True, color_threshold=color_threshold, above_threshold_color='#555555')
                    ax_tree.axis('off')
                    
                    leaves_order = dendro['leaves']
                    df_plot = df.iloc[:, leaves_order]
                    
                    clusters = fcluster(Z, t=color_threshold, criterion='distance')
                    clusters_ordered = clusters[leaves_order]
                    try: cmap_cluster = matplotlib.colormaps["tab10"]
                    except: cmap_cluster = cm.get_cmap("tab10")
                    ax_cbar_cluster.imshow([clusters_ordered], aspect='auto', cmap=cmap_cluster, interpolation='nearest')
                    ax_cbar_cluster.axis('off')
                else:
                    df_plot = df

                cmap_sel = u.get('cmap', "Default (Soft RdBu)")
                if cmap_sel == "Default (Soft RdBu)":
                    colors = ["#63aaff", "#ffffff", "#ff6b6b"]
                    cmap = LinearSegmentedColormap.from_list("soft_rdbu", colors)
                else: cmap = cmap_sel
                
                aspect_val = 'equal' if u.get('square', False) else 'auto'
                im = ax.imshow(df_plot, aspect=aspect_val, cmap=cmap, interpolation='nearest')
                
                if u.get('annot', True):
                    for i in range(len(df_plot.index)):
                        for j in range(len(df_plot.columns)):
                            val = df_plot.iloc[i, j]
                            txt_val = f"{val*100:.0f}" if is_inhib else f"{val:.1f}"
                            ax.text(j, i, txt_val, 
                                    ha="center", va="center", color="black", fontsize=fs_tick, fontweight=fw_annot,
                                    path_effects=[matplotlib.patheffects.withStroke(linewidth=2, foreground="white")])

                ax.set_xticks(range(len(df_plot.columns)))
                ax.set_yticks(range(len(df_plot.index)))
                ax.set_xticklabels(df_plot.columns, rotation=90, fontsize=fs_tick, fontweight=fw_tick)
                ax.set_yticklabels(df_plot.index, fontsize=fs_tick, fontweight=fw_tick)
                
                if u.get('grid', True):
                    ax.set_xticks(np.arange(df_plot.shape[1] + 1) - 0.5, minor=True)
                    ax.set_yticks(np.arange(df_plot.shape[0] + 1) - 0.5, minor=True)
                    ax.grid(which="minor", color="white", linestyle='-', linewidth=2)
                    ax.tick_params(which="minor", bottom=False, left=False)
                
                ax.set_title("")
                
                cbar = plt.colorbar(im, cax=divider.append_axes("right", size="3%", pad=0.1))
                cbar_label = "Inhibition Rate" if is_inhib else "Value"
                cbar.set_label(cbar_label, fontsize=fs_label, fontweight=fw_label, labelpad=10)
                
            else:
                # K-Means 模式
                k = int(u.get('k', 4))
                if len(df) >= k:
                    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                    clusters = kmeans.fit_predict(df)
                    coords = PCA(n_components=2).fit_transform(df)
                    
                    try: cmap_km = matplotlib.colormaps["tab10"]
                    except: cmap_km = cm.get_cmap("tab10")
                    
                    ax.scatter(coords[:,0], coords[:,1], c=clusters, cmap=cmap_km, s=u.get('ms', 120), edgecolors='white', alpha=0.9)
                    for i, txt in enumerate(df.index):
                        ax.annotate(txt, (coords[i,0], coords[i,1]), xytext=(6,6), textcoords='offset points', fontsize=fs_tick, fontweight=fw_annot)
                    
                    ax.set_title(f"K-Means PCA Scatter (K={k})", fontweight=fw_title, fontsize=fs_title)
                    
                    if u.get('grid', True):
                        ax.grid(True, ls='--', alpha=0.5)

            fig.tight_layout()

            # 导出图片并销毁资源
            out_name = f"plot_Heatmap_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150)
            fig.clf()

            return out_path, "🔥 【BLI 表位聚类/热图分析完毕】<br>已根据全局参数完成绘图。"
            
        except Exception as e:
            return "", f"热图生成引擎执行失败: {str(e)}"