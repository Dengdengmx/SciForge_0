# plugins/plugin_structure.py
import os
import json
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QFileDialog, QMessageBox, QAbstractItemView)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QColor
from qfluentwidgets import (PrimaryPushButton, PushButton, SubtitleLabel, 
                            CardWidget, StrongBodyLabel, 
                            ComboBox, Slider, FluentIcon as FIF, ListWidget)

from core.plugin_manager import BasePlugin

try:
    from Bio.PDB import PDBParser, MMCIFParser, Superimposer, PDBIO
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu-compositing --disable-gpu"
# ==========================================
# 核心：丝滑无闪烁的 SPA (单页应用) HTML 引擎
# ==========================================
SPA_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://3dmol.csb.pitt.edu/build/3Dmol-min.js"></script>
    <style>
        body { margin: 0; padding: 0; background-color: #1E1E1E; overflow: hidden; color: #777; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        #container { width: 100vw; height: 100vh; position: relative; display: none; }
        #placeholder { display: flex; justify-content: center; align-items: center; height: 100vh; text-align: center; flex-direction: column; }
        .icon { font-size: 64px; margin-bottom: 20px; }
        h2 { color: #E0E0E0; margin: 0 0 10px 0; }
    </style>
</head>
<body>
    <div id="placeholder">
        <div class="icon">🧊</div>
        <h2>ProDesigner 3D Viewport</h2>
        <span style='font-size:13px;'>支持从 Data Hub 右键极速定向发送 PDB / CIF 文件至此<br>或直接点击左侧按钮挂载</span>
    </div>
    <div id="container"></div>

    <script>
        var viewer = null;

        function initViewerIfNeeded() {
            if(!viewer) {
                document.getElementById('placeholder').style.display = 'none';
                document.getElementById('container').style.display = 'block';
                viewer = $3Dmol.createViewer("container", {backgroundColor: "#1E1E1E"});
            }
        }

        function loadStructure(pdbStr, fmt) {
            initViewerIfNeeded();
            viewer.clear();
            viewer.addModel(pdbStr, fmt);
            viewer.zoomTo();
            viewer.render();
        }

        function updateView(styleJSON, surfType, opacity) {
            if(!viewer) return;
            viewer.setStyle({}, styleJSON);
            viewer.removeAllSurfaces();
            if(surfType === 'VDW') {
                viewer.addSurface($3Dmol.SurfaceType.VDW, {opacity: opacity, color: 'white'});
            } else if(surfType === 'SAS') {
                viewer.addSurface($3Dmol.SurfaceType.SAS, {opacity: opacity, color: 'white'});
            }
            viewer.render();
        }
    </script>
</body>
</html>
"""

# ==========================================
# 专属重型 UI：3D 结构工作台 (完美内嵌版)
# ==========================================
class StructureUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.pdbs = {}             
        self.aligned_pdbs = {}     
        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 1. 左侧：控制台
        left_panel = CardWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12)
        
        left_layout.addWidget(SubtitleLabel("🧊 3D 结构控制台"))

        self.btn_import = PrimaryPushButton("挂载 PDB/CIF...", icon=FIF.DOWNLOAD)
        self.btn_import.setFixedHeight(30)
        self.btn_import.clicked.connect(self.open_file_dialog)
        left_layout.addWidget(self.btn_import)

        left_layout.addWidget(StrongBodyLabel("结构列表 (支持多选):"))
        self.list_pdbs = ListWidget()
        self.list_pdbs.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_pdbs.itemSelectionChanged.connect(self.on_selection_changed)
        left_layout.addWidget(self.list_pdbs)

        align_layout = QHBoxLayout()
        self.btn_align = PrimaryPushButton("CA 结构对齐", icon=FIF.ALIGNMENT)
        self.btn_align.setFixedHeight(30)
        self.btn_align.clicked.connect(self.perform_alignment)
        
        self.btn_reset_align = PushButton("重置坐标")
        self.btn_reset_align.setFixedHeight(30)
        self.btn_reset_align.clicked.connect(self.reset_alignment)
        
        align_layout.addWidget(self.btn_align)
        align_layout.addWidget(self.btn_reset_align)
        left_layout.addLayout(align_layout)

        left_layout.addSpacing(5)
        left_layout.addWidget(StrongBodyLabel("主干渲染模式 (Style):"))
        self.combo_style = ComboBox()
        self.combo_style.addItems(["卡通模型 (Cartoon)", "球棍模型 (Stick)", "骨架线条 (Line)", "空间填充 (Sphere)"])
        self.combo_style.setFixedHeight(30)
        self.combo_style.currentIndexChanged.connect(self.update_render)
        left_layout.addWidget(self.combo_style)

        left_layout.addWidget(StrongBodyLabel("色彩方案 (Color):"))
        self.combo_color = ComboBox()
        self.combo_color.addItems(["按二级结构着色 (ssJmol)", "渐变彩虹 (Spectrum)", "纯净灰白 (White)"])
        self.combo_color.setFixedHeight(30)
        self.combo_color.currentIndexChanged.connect(self.update_render)
        left_layout.addWidget(self.combo_color)

        left_layout.addSpacing(5)
        left_layout.addWidget(StrongBodyLabel("表面与透明度 (Surface):"))
        self.combo_surface = ComboBox()
        self.combo_surface.addItems(["关闭表面 (None)", "分子表面 (VDW)", "溶剂可及表面 (SAS)"])
        self.combo_surface.setFixedHeight(30)
        self.combo_surface.currentIndexChanged.connect(self.update_render)
        left_layout.addWidget(self.combo_surface)
        
        self.slider_opacity = Slider(Qt.Horizontal)
        self.slider_opacity.setRange(1, 10)
        self.slider_opacity.setValue(7)
        self.slider_opacity.valueChanged.connect(self.update_render)
        left_layout.addWidget(self.slider_opacity)

        left_layout.addStretch()

        # 2. 右侧：物理隔绝防撕裂包裹的 Web 画布 (已直接内嵌)
        right_panel = CardWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5) 
        
        self.web_container = QWidget()
        self.web_container.setStyleSheet("background-color: #1E1E1E; border-radius: 8px;")
        web_layout = QVBoxLayout(self.web_container)
        web_layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView()
        self.web_view.page().setBackgroundColor(QColor("#1E1E1E"))
        self.web_view.setHtml(SPA_HTML_TEMPLATE)
        web_layout.addWidget(self.web_view)

        right_layout.addWidget(self.web_container)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("""
            QSplitter::handle { background-color: #E0E0E0; width: 4px; border-radius: 2px; margin: 10px 2px; }
            QSplitter::handle:hover { background-color: #0078D7; }
        """)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([320, 680])
        main_layout.addWidget(splitter)

    # ------------------------------------
    # 数据摄取接口
    # ------------------------------------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            self.load_file(url.toLocalFile())

    def open_file_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择 3D 结构文件", "", "Protein Structure (*.pdb *.cif);;All Files (*)")
        for f in files: self.load_file(f)

    def load_file(self, file_path):
        if not os.path.exists(file_path): return
        if not file_path.lower().endswith(('.pdb', '.cif')): return
        
        file_name = os.path.basename(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f: pdb_data = f.read()
            self.pdbs[file_name] = pdb_data
            
            if len(self.list_pdbs.findItems(file_name, Qt.MatchExactly)) == 0:
                self.list_pdbs.addItem(file_name)
            
            item = self.list_pdbs.findItems(file_name, Qt.MatchExactly)[0]
            item.setSelected(True)
        except Exception as e:
            QMessageBox.critical(self, "读取失败", str(e))

    def on_selection_changed(self):
        selected_items = self.list_pdbs.selectedItems()
        if not selected_items: return
        
        name = selected_items[0].text()
        pdb_data = self.aligned_pdbs.get(name, self.pdbs[name])
        fmt = 'cif' if name.lower().endswith('.cif') else 'pdb'
        
        safe_pdb_str = json.dumps(pdb_data)
        js_cmd = f"loadStructure({safe_pdb_str}, '{fmt}');"
        
        # 结构注入完毕后，紧接着应用当前的 UI 样式参数
        self.web_view.page().runJavaScript(js_cmd, lambda res: self.update_render())

    # ------------------------------------
    # 对齐与实时 JS 渲染控制
    # ------------------------------------
    def perform_alignment(self):
        if not BIOPYTHON_AVAILABLE:
            QMessageBox.warning(self, "缺少依赖", "结构对齐需要 BioPython 支持，请在终端执行: pip install biopython")
            return
        QMessageBox.information(self, "提示", "对齐算法引擎预留位，请接入你的 CA 对齐逻辑。")

    def reset_alignment(self):
        self.aligned_pdbs.clear()
        self.on_selection_changed()

    def update_render(self):
        selected_items = self.list_pdbs.selectedItems()
        if not selected_items: return
        
        style_str = self.combo_style.currentText()
        color_str = self.combo_color.currentText()

        base_style = "cartoon"
        if "Stick" in style_str: base_style = "stick"
        elif "Line" in style_str: base_style = "line"
        elif "Sphere" in style_str: base_style = "sphere"

        color_scheme = "ssJmol"
        color_val = None
        if "Spectrum" in color_str: color_scheme = "Amingo"
        elif "White" in color_str: color_val = "white"

        style_obj = {base_style: {}}
        if color_val: style_obj[base_style]["color"] = color_val
        else: style_obj[base_style]["colorscheme"] = color_scheme

        surf_str = self.combo_surface.currentText()
        surf_type = "None"
        if "VDW" in surf_str: surf_type = "VDW"
        elif "SAS" in surf_str: surf_type = "SAS"

        opacity = self.slider_opacity.value() / 10.0

        # 向浏览器发送极小的 JSON 指令，实现无闪烁变色变形！
        js_cmd = f"updateView({json.dumps(style_obj)}, '{surf_type}', {opacity});"
        self.web_view.page().runJavaScript(js_cmd)


# ==========================================
# 插件描述器与全局后台路由
# ==========================================
class StructurePlugin(BasePlugin):
    plugin_id = "structure_viewer"
    plugin_name = "3D 结构可视化引擎"
    icon = "🧊"
    
    trigger_tag = "3D 结构"

    def get_ui(self, parent=None):
        return StructureUI(parent)

    @staticmethod
    def run(file_path, archive_dir):
        try:
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ['.pdb', '.cif']:
                return "", "【3D 结构跳过】暂不支持该文件格式。"

            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            atom_count = 0
            chains = set()
            for line in lines:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    atom_count += 1
                    if len(line) > 21:
                        chain = line[21].strip()
                        if chain: chains.add(chain)

            chain_str = ", ".join(sorted(list(chains))) if chains else "未识别"

            res_text = (
                f"🧊 **【3D 结构物理分析简报】**<br>"
                f"源文件: {os.path.basename(file_path)}<br>"
                f"包含多肽/核酸链: {chain_str} (共 {len(chains)} 条)<br>"
                f"总原子数 (ATOM/HETATM): {atom_count}<br>"
                f"<br><span style='color:#0078D7; font-weight:bold;'>💡 系统保护: </span>"
                f"<span style='color:#555;'>后台已屏蔽 3D 重型渲染引擎触发，已完成结构特征解析。</span><br>"
                f"☞ 请前往 <b>Data Hub</b> 右键该文件 <span style='background-color:#e0f2fe; padding:2px 4px; border-radius:3px;'>定向投送至绘图引擎</span> 在前台查看实体模型。"
            )

            return "", res_text

        except Exception as e:
            return "", f"3D 结构解析失败: {str(e)}"