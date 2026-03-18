# view/ui_data_hub.py
# view/ui_data_hub.py 的最顶部

from PyQt5.QtCore import (Qt, pyqtSignal, QMimeData, QUrl, 
                          QRect, QPoint, QSize, QItemSelectionModel)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QGridLayout, QStackedWidget, QLabel, QHeaderView, 
                             QTableWidgetItem, QTableWidget, QAbstractItemView, QRubberBand)
from qfluentwidgets import (PrimaryPushButton, PushButton, CheckBox, TextEdit, SubtitleLabel, 
                            CardWidget, BodyLabel, ComboBox, StrongBodyLabel, 
                            SegmentedWidget, TableWidget, TreeWidget, FluentIcon as FIF,
                            SearchLineEdit, RoundMenu, Action)

# 【核心新增】：导入插件管理器，用于动态生成二级菜单
from core.plugin_manager import PluginManager

class NumericTableItem(QTableWidgetItem):
    def __lt__(self, other):
        try: return float(self.text().split()[0]) < float(other.text().split()[0])
        except ValueError: return self.text() < other.text()

# ==========================================
# 🚀 拖拽黑魔法：原生防弹版 (告别魔改事件冲突)
# ==========================================
class DraggableTableWidget(TableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 💡 彻底抛弃手工画框，启用 Qt 底层最稳固的原生拖放与多选机制！
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly) # 保证只能往外拖，防止误覆盖
        self.setSelectionMode(QAbstractItemView.ExtendedSelection) # 开启原生的 Ctrl/Shift 多选
        self.setSelectionBehavior(QAbstractItemView.SelectRows) # 保证一选就是一整行

    # 我们唯一需要介入的，就是告诉操作系统，被拖走的是什么物理文件
    def mimeData(self, items):
        mime_data = super().mimeData(items)
        urls = []
        seen_rows = set()
        
        # 💡 强力去重：因为选中一整行会传入3个 cell item，我们只提取第0列埋藏的绝对路径
        for item in items:
            row = item.row()
            if row not in seen_rows:
                col0_item = self.item(row, 0)
                if col0_item:
                    filepath = col0_item.data(Qt.UserRole)
                    if filepath: 
                        urls.append(QUrl.fromLocalFile(filepath))
                seen_rows.add(row)
                
        mime_data.setUrls(urls)
        return mime_data

class DroppableTreeWidget(TreeWidget):
    sig_files_dropped = pyqtSignal(list, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)
            
    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            item = self.itemAt(event.pos())
            if not item: return
            target_path = item.data(0, Qt.UserRole)
            if not target_path: return
            
            import os
            if not os.path.isdir(target_path):
                target_path = os.path.dirname(target_path)
                
            urls = [u.toLocalFile() for u in event.mimeData().urls()]
            self.sig_files_dropped.emit(urls, target_path)
            
            # 💡 核心修复：强行设置为 CopyAction！阻止 QTableWidget 擅自删掉表格里的一行
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            super().dropEvent(event)

class DataHubUI(QWidget):
    sig_mount_clicked = pyqtSignal()
    sig_filter_changed = pyqtSignal()
    sig_file_clicked = pyqtSignal(str)
    sig_send_to_workspace = pyqtSignal(str)
    # 【核心修改】：信号增加一个 str，变成 (动作类型, 文件路径, 附加参数/插件ID)
    sig_context_action = pyqtSignal(str, str, str) 
    sig_global_search_clicked = pyqtSignal()
    sig_data_source_changed = pyqtSignal(str)
    sig_files_dropped = pyqtSignal(list, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DataHubUI")
        self.current_selected_filepath = None
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: #E0E0E0; width: 4px; border-radius: 2px; margin: 10px 2px; } QSplitter::handle:hover { background-color: #0078D7; }")
        main_layout.addWidget(splitter)

        # === 1. 左侧过滤面板 ===
        left_panel = CardWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 15, 15, 15)
        left_layout.setSpacing(12) 
        left_layout.addWidget(SubtitleLabel("数据归档与检索"))
        
        self.btn_global_search = PrimaryPushButton("🔍 全局归档高级检索...", self)
        self.btn_global_search.setFixedHeight(35)
        self.btn_global_search.clicked.connect(self.sig_global_search_clicked.emit)
        left_layout.addWidget(self.btn_global_search)
        
        line = QWidget(); line.setFixedHeight(1); line.setStyleSheet("background-color: #E0E0E0;")
        left_layout.addWidget(line)

        # 【核心新增】：双模切换开关
        self.source_pivot = SegmentedWidget(self)
        self.source_pivot.addItem('external', '📂 外部数据')
        self.source_pivot.addItem('internal', '🗄️ 内部归档')
        self.source_pivot.currentItemChanged.connect(self.sig_data_source_changed.emit)
        left_layout.addWidget(self.source_pivot)
        
        self.btn_open = PushButton("挂载外部数据目录...")
        self.btn_open.setFixedHeight(30) 
        self.btn_open.clicked.connect(self.sig_mount_clicked.emit)
        left_layout.addWidget(self.btn_open)
        
        self.lbl_path = BodyLabel("当前路径: 未选择")
        self.lbl_path.setWordWrap(True)
        self.lbl_path.setStyleSheet("color: #666; font-size: 11px;")
        left_layout.addWidget(self.lbl_path)
        
        left_layout.addWidget(StrongBodyLabel("目录多维过滤:"))
        self.combo_project = ComboBox()
        self.combo_project.addItems(["全部项目", "ProDesigner", "SFTSV-Gc", "临时课题"])
        self.combo_exp = ComboBox()
        self.combo_exp.addItems(["全部实验类型", "SPR", "ELISA", "AKTA", "计算设计"])
        left_layout.addWidget(self.combo_project)
        left_layout.addWidget(self.combo_exp)
        self.combo_project.currentIndexChanged.connect(self.sig_filter_changed.emit)
        self.combo_exp.currentIndexChanged.connect(self.sig_filter_changed.emit)
        left_layout.addSpacing(5)
        
        left_layout.addWidget(StrongBodyLabel("文件载体类型:"))
        btn_row = QHBoxLayout()
        btn_all = PushButton("☑ 全选")
        btn_none = PushButton("☐ 全不选")
        btn_all.clicked.connect(lambda: self._set_all_filters(True))
        btn_none.clicked.connect(lambda: self._set_all_filters(False))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        left_layout.addLayout(btn_row)

        grid_type = QGridLayout()
        grid_type.setVerticalSpacing(5) 
        grid_type.setHorizontalSpacing(10)
        self.chk_py = CheckBox("脚本 (.py)")
        self.chk_pdb = CheckBox("结构 (.pdb/.cif)")
        self.chk_seq = CheckBox("序列 (.fasta)")
        self.chk_dna = CheckBox("图谱 (.dna)") 
        self.chk_img = CheckBox("图像 (.png/.jpg)")
        self.chk_tbl = CheckBox("表格 (.csv/.xlsx)")
        self.chk_txt = CheckBox("文档 (.txt/.md)")
        self.chk_doc = CheckBox("Word (.docx)")
        self.chk_pdf = CheckBox("PDF (.pdf)")
        self.chk_ppt = CheckBox("幻灯片 (.ppt)")
        self.chk_zip = CheckBox("压缩包 (.zip)")
        self.chk_mrc = CheckBox("电镜图 (.mrc)")
        
        self.filters = [self.chk_py, self.chk_pdb, self.chk_seq, self.chk_dna, 
                        self.chk_img, self.chk_tbl, self.chk_txt,
                        self.chk_doc, self.chk_pdf, self.chk_ppt, self.chk_zip, self.chk_mrc]
        row, col = 0, 0
        for chk in self.filters:
            chk.setChecked(True)
            chk.stateChanged.connect(self.sig_filter_changed.emit)
            chk.setStyleSheet("CheckBox { font-size: 12px; }")
            grid_type.addWidget(chk, row, col)
            col += 1
            if col > 1: col = 0; row += 1
        left_layout.addLayout(grid_type)
        left_layout.addStretch()

        # === 2. 中间数据展示区 ===
        middle_panel = QWidget(self)
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("快速检索当前目录文件名称...")
        self.search_bar.textChanged.connect(self._visual_search_filter)
        middle_layout.addWidget(self.search_bar)
        
        self.view_pivot = SegmentedWidget(self)
        self.view_pivot.addItem('table', '平铺表格')
        self.view_pivot.addItem('tree', '层级导图')
        self.view_pivot.currentItemChanged.connect(lambda k: self.middle_stack.setCurrentIndex(0 if k=='table' else 1))
        middle_layout.addWidget(self.view_pivot, alignment=Qt.AlignCenter)

        self.middle_stack = QStackedWidget(self)

        # ==================== 表格视图设置 ====================
        self.file_table = DraggableTableWidget(self)
        
        self.file_table.setColumnCount(3)
        self.file_table.setHorizontalHeaderLabels(['数据名称', '类型', '大小 (KB)'])
        self.file_table.verticalHeader().hide()
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.file_table.itemClicked.connect(lambda item: self._on_item_clicked(self.file_table.item(item.row(), 0).data(Qt.UserRole)))
        self.file_table.setSortingEnabled(True) 
        self.file_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.middle_stack.addWidget(self.file_table)

        # ==================== 树形视图设置 ====================
        self.file_tree = DroppableTreeWidget(self)
        # 💡 已修复幽灵信号问题，只保留一句直连
        self.file_tree.sig_files_dropped.connect(self.sig_files_dropped.emit)
            
        self.file_tree.setDragEnabled(True)
        self.file_tree.setHeaderLabels(['文件层级拓扑结构'])
        self.file_tree.setIndentation(20) 
        self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_tree.itemClicked.connect(lambda item, col: item.setExpanded(not item.isExpanded()))
        self.file_tree.itemClicked.connect(lambda item, col: self._on_item_clicked(item.data(0, Qt.UserRole)))
        self.file_tree.setSortingEnabled(True) 
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.middle_stack.addWidget(self.file_tree)

        middle_layout.addWidget(self.middle_stack)

        # === 3. 右侧洞察预览区 ===
        right_panel = CardWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(15, 15, 15, 15)
        right_layout.addWidget(SubtitleLabel("数据洞察 (Data Insights)"))
        
        self.lbl_details = BodyLabel("请选择左侧数据条目查看详情。")
        self.lbl_details.setStyleSheet("color: #0078D7; font-weight: bold;")
        self.lbl_details.setWordWrap(True)
        right_layout.addWidget(self.lbl_details)
        
        self.preview_stack = QStackedWidget(self)
        self.text_preview = TextEdit()
        self.text_preview.setReadOnly(True)
        self.text_preview.setFont(QFont("Consolas", 10))
        
        self.image_preview = QLabel("图片加载中...")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("background-color: #F3F3F3; border-radius: 5px;")
        
        self.binary_preview = QLabel("当前格式不支持快速预览。")
        self.binary_preview.setAlignment(Qt.AlignCenter)
        self.binary_preview.setStyleSheet("color: #666;")
        
        self.table_preview = QTableWidget(self)
        self.table_preview.setStyleSheet("QTableWidget { background-color: white; }")
        
        self.preview_stack.addWidget(self.text_preview)   
        self.preview_stack.addWidget(self.image_preview)  
        self.preview_stack.addWidget(self.binary_preview) 
        self.preview_stack.addWidget(self.table_preview)  
        
        right_layout.addWidget(self.preview_stack, 1)

        self.btn_send = PrimaryPushButton("发送至绘图可视化台")
        self.btn_send.clicked.connect(lambda: self.sig_send_to_workspace.emit(self.current_selected_filepath) if self.current_selected_filepath else None)
        right_layout.addWidget(self.btn_send)

        splitter.addWidget(left_panel)
        splitter.addWidget(middle_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 350, 450])

    def _visual_search_filter(self, text):
        text = text.lower()
        for r in range(self.file_table.rowCount()):
            item = self.file_table.item(r, 0)
            self.file_table.setRowHidden(r, text not in item.text().lower())
            
        def filter_tree(node):
            match = text in node.text(0).lower()
            child_match = False
            for i in range(node.childCount()):
                if filter_tree(node.child(i)): child_match = True
            show = match or child_match
            node.setHidden(not show)
            return show
            
        for i in range(self.file_tree.topLevelItemCount()):
            filter_tree(self.file_tree.topLevelItem(i))

    def _show_table_context_menu(self, pos):
        item = self.file_table.itemAt(pos)
        if item:
            filepath = self.file_table.item(item.row(), 0).data(Qt.UserRole)
            self._pop_round_menu(filepath, self.file_table.viewport().mapToGlobal(pos))

    def _show_tree_context_menu(self, pos):
        item = self.file_tree.itemAt(pos)
        if item and item.data(0, Qt.UserRole):
            filepath = item.data(0, Qt.UserRole)
            self._pop_round_menu(filepath, self.file_tree.viewport().mapToGlobal(pos))

    def _pop_round_menu(self, filepath, global_pos):
        menu = RoundMenu(parent=self)
        
        # 1. 基础系统操作组
        action_open = Action(FIF.DOCUMENT, '使用系统默认程序打开', self)
        action_open.triggered.connect(lambda checked=False, fp=filepath: self.sig_context_action.emit("open_system", fp, ""))
        menu.addAction(action_open)
        
        action_explore = Action(FIF.FOLDER, '在资源管理器中定位', self)
        action_explore.triggered.connect(lambda checked=False, fp=filepath: self.sig_context_action.emit("explore", fp, ""))
        menu.addAction(action_explore)
        
        menu.addSeparator() 
        
        # 2. 科研工作流组
        action_eln = Action(FIF.CALENDAR, '归档至今日实验记录', self)
        action_eln.triggered.connect(lambda checked=False, fp=filepath: self.sig_context_action.emit("send_to_eln", fp, ""))
        menu.addAction(action_eln)
        
        # 【核心修改】：构建动态二级菜单
        plot_menu = RoundMenu("🎯 定向投送至绘图引擎...", self)
        plot_menu.setIcon(FIF.APPLICATION)
        
        plugins = PluginManager.get_plugins()
        if not plugins:
            empty_action = Action("暂无已挂载的分析插件", self)
            empty_action.setEnabled(False)
            plot_menu.addAction(empty_action)
        else:
            for p in plugins:
                action = Action(f"{p.icon} {p.plugin_name}", self)
                # 巧妙利用 lambda 默认参数捕获循环变量
                action.triggered.connect(lambda checked=False, fp=filepath, pid=p.plugin_id: self.sig_context_action.emit("send_to_plot", fp, pid))
                plot_menu.addAction(action)
                
        menu.addMenu(plot_menu)
        
        menu.addSeparator() 
        
        # 3. 文件管理组
        action_copy = Action(FIF.COPY, '复制绝对路径', self)
        action_copy.triggered.connect(lambda checked=False, fp=filepath: self.sig_context_action.emit("copy", fp, ""))
        menu.addAction(action_copy)
        
        action_rename = Action(FIF.EDIT, '重命名文件', self)
        action_rename.triggered.connect(lambda checked=False, fp=filepath: self.sig_context_action.emit("rename", fp, ""))
        menu.addAction(action_rename)
        
        action_delete = Action(FIF.DELETE, '删除该文件 (慎用)', self)
        action_delete.triggered.connect(lambda checked=False, fp=filepath: self.sig_context_action.emit("delete", fp, ""))
        action_delete.setProperty('isDanger', True) 
        menu.addAction(action_delete)
        
        menu.exec_(global_pos)

    def _on_item_clicked(self, filepath):
        if filepath:
            self.current_selected_filepath = filepath
            self.sig_file_clicked.emit(filepath)

    def update_path_label(self, path): self.lbl_path.setText(f"当前路径:\n{path}")
    def get_active_extensions(self):
        exts = []
        if self.chk_py.isChecked(): exts.append('.py')
        if self.chk_pdb.isChecked(): exts.extend(['.pdb', '.cif'])
        if self.chk_seq.isChecked(): exts.extend(['.fasta', '.seq'])
        if self.chk_dna.isChecked(): exts.append('.dna')
        if self.chk_img.isChecked(): exts.extend(['.png', '.jpg', '.jpeg', '.tif'])
        if self.chk_tbl.isChecked(): exts.extend(['.csv', '.xlsx', '.xls'])
        if self.chk_txt.isChecked(): exts.extend(['.txt', '.md', '.json'])
        if self.chk_doc.isChecked(): exts.extend(['.doc', '.docx'])
        if self.chk_pdf.isChecked(): exts.append('.pdf')
        if self.chk_ppt.isChecked(): exts.extend(['.ppt', '.pptx'])
        if self.chk_zip.isChecked(): exts.extend(['.zip', '.rar', '.tar', '.gz'])
        if self.chk_mrc.isChecked(): exts.extend(['.mrc', '.map'])
        return exts
    def _set_all_filters(self, state):
        for chk in self.filters:
            chk.blockSignals(True); chk.setChecked(state); chk.blockSignals(False)
        self.sig_filter_changed.emit() 
    def set_details_label(self, text): self.lbl_details.setText(text)
    def show_text_preview(self, text): self.text_preview.setText(text); self.preview_stack.setCurrentIndex(0)
    def show_image_preview(self, filepath):
        self.image_preview.setPixmap(QPixmap(filepath).scaled(self.image_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.preview_stack.setCurrentIndex(1)
    def show_binary_preview(self, text): self.binary_preview.setText(text); self.preview_stack.setCurrentIndex(2)
    def show_table_preview(self, df):
        self.table_preview.clear(); self.table_preview.setRowCount(df.shape[0]); self.table_preview.setColumnCount(df.shape[1])
        self.table_preview.setHorizontalHeaderLabels(df.columns.astype(str))
        for row in range(df.shape[0]):
            for col in range(df.shape[1]):
                self.table_preview.setItem(row, col, QTableWidgetItem(str(df.iat[row, col])))
        self.preview_stack.setCurrentIndex(3)
    def load_config_tags(self, tags):
        self.combo_project.blockSignals(True); self.combo_project.clear(); self.combo_project.addItem("全部项目"); self.combo_project.addItems(tags); self.combo_project.blockSignals(False)