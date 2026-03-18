# hubs_data_hub.py
import os
import re
import json
import platform
import subprocess
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QTreeWidgetItem, QTableWidgetItem, QApplication, QInputDialog, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QHeaderView, QSplitter, QWidget
from qfluentwidgets import FluentIcon as FIF, SearchLineEdit, TableWidget, SubtitleLabel, PushButton, StrongBodyLabel

from view.ui_data_hub import DataHubUI, NumericTableItem
from controllers.ctrl_data_hub import DataHubLogic
from core.signals import global_bus
from core.config import GlobalConfig

# ?? 核心引入：接入 SampleHub 的数据神经网络
from controllers.ctrl_sample_hub import SampleHubLogic

class ArchiveSearchDialog(QDialog):
    # ?? 定义空间瞬移信号：当用户双击样本时发射 (物理路径, 孔位ID)
    sig_jump_to_sample = pyqtSignal(str, str) 

    def __init__(self, archive_root, parent=None):
        super().__init__(parent)
        self.archive_root = archive_root
        self.setWindowTitle("SciForge 全局数据与实体样本穿透检索")
        self.resize(1100, 750) 
        self.setStyleSheet("background: white;")
        
        self.all_files_data = [] 
        self.sample_logic = SampleHubLogic() # ?? 实例化天眼引擎
        
        self._setup_ui()
        self._scan_archive_async() 

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # --- 顶部搜索栏 ---
        header_layout = QHBoxLayout()
        header_layout.addWidget(SubtitleLabel("?? 全局穿透搜索 (Data & Physical Samples)"))
        self.search_bar = SearchLineEdit(self)
        self.search_bar.setPlaceholderText("键入关键字同时搜索：归档数据文件、实体样本名称、位置、备注...")
        self.search_bar.setFixedWidth(500)
        self.search_bar.textChanged.connect(self._do_global_search)
        header_layout.addStretch()
        header_layout.addWidget(self.search_bar)
        layout.addLayout(header_layout)
        
        # ?? 核心 UI 升级：上下分屏结构
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #E0E0E0; height: 2px; }")
        
        # === 上半部：归档文件库 ===
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget); file_layout.setContentsMargins(0, 10, 0, 0)
        file_layout.addWidget(StrongBodyLabel("?? 实验数据与归档文档"))
        self.file_table = TableWidget(self)
        self.file_table.setColumnCount(5)
        self.file_table.setHorizontalHeaderLabels(['文件名', '课题', '归档日期', '关联实验信息', '绝对存放路径'])
        self.file_table.verticalHeader().hide()
        self.file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.file_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.file_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.file_table.doubleClicked.connect(self._on_file_double_click)
        file_layout.addWidget(self.file_table)
        splitter.addWidget(file_widget)
        
        # === 下半部：实体物理样本库 ===
        sample_widget = QWidget()
        sample_layout = QVBoxLayout(sample_widget); sample_layout.setContentsMargins(0, 10, 0, 0)
        lbl_sample = StrongBodyLabel("?? 实体物理样本库 (? 双击行可瞬间瞬移至其实体存放位置)")
        lbl_sample.setStyleSheet("color: #0078D7;")
        sample_layout.addWidget(lbl_sample)
        self.sample_table = TableWidget(self)
        self.sample_table.setColumnCount(6)
        self.sample_table.setHorizontalHeaderLabels(['样本名称', '类型', '?? 绝对物理位置', '余量', '冻融次数', '所有人/备注'])
        self.sample_table.verticalHeader().hide()
        self.sample_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.sample_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.sample_table.setEditTriggers(TableWidget.NoEditTriggers)
        self.sample_table.doubleClicked.connect(self._on_sample_double_click)
        sample_layout.addWidget(self.sample_table)
        splitter.addWidget(sample_widget)
        
        # 默认平分空间
        splitter.setSizes([350, 350])
        layout.addWidget(splitter)
        
        # --- 底部状态栏 ---
        bottom_layout = QHBoxLayout()
        self.lbl_status = SubtitleLabel("正在扫描文件系统..."); self.lbl_status.setStyleSheet("font-size: 12px; color: #666;")
        bottom_layout.addWidget(self.lbl_status)
        bottom_layout.addStretch()
        btn_close = PushButton("关闭检索"); btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)

    def _scan_archive_async(self):
        """仅扫描硬盘文件，样本的检索移交给强大的 SampleHub API"""
        self.all_files_data.clear()
        if not os.path.exists(self.archive_root):
            self.lbl_status.setText("归档根目录未创建或不存在。")
            return
            
        count = 0
        for root, dirs, files in os.walk(self.archive_root):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(root, self.archive_root)
                parts = rel_path.split(os.sep)
                
                project = parts[0] if len(parts) > 0 and parts[0] != '.' else "未分类"
                date_str = parts[1] if len(parts) > 1 else "-"
                
                assoc_info = ""
                if len(parts) == 3: assoc_info = f"实验: {parts[2]}" 
                elif len(parts) >= 4: assoc_info = f"样品: {parts[2]} | 实验: {parts[3]}"
                
                self.all_files_data.append({
                    "name": file, "project": project, "date": date_str, 
                    "assoc": assoc_info, "path": full_path
                })
                count += 1
                
        self.lbl_status.setText(f"就绪。共挂载 {count} 个硬盘数据文件及全库实体样本记录。")
        self._populate_file_table(self.all_files_data)

    def _populate_file_table(self, data_list):
        self.file_table.setSortingEnabled(False)
        self.file_table.setRowCount(0)
        for i, row_data in enumerate(data_list):
            self.file_table.insertRow(i)
            self.file_table.setItem(i, 0, QTableWidgetItem(row_data["name"]))
            self.file_table.setItem(i, 1, QTableWidgetItem(row_data["project"]))
            self.file_table.setItem(i, 2, QTableWidgetItem(row_data["date"]))
            self.file_table.setItem(i, 3, QTableWidgetItem(row_data["assoc"]))
            
            path_item = QTableWidgetItem(row_data["path"])
            path_item.setData(Qt.UserRole, row_data["path"]) 
            self.file_table.setItem(i, 4, path_item)
        self.file_table.setSortingEnabled(True)

    def _get_bold_font(self):
        font = self.file_table.font(); font.setBold(True); return font

    def _do_global_search(self, text):
        """?? 【双核驱动】同时检索文件库和样本库！"""
        text = text.lower().strip()
        
        # 1. 检索引擎一：过滤本地硬盘文件
        filtered_files = []
        if text:
            for d in self.all_files_data:
                if (text in d["name"].lower() or text in d["project"].lower() or 
                    text in d["date"].lower() or text in d["assoc"].lower()):
                    filtered_files.append(d)
        else:
            filtered_files = self.all_files_data
        self._populate_file_table(filtered_files)
        
        # 2. 检索引擎二：呼叫 SampleHub 的全局神经网络 API
        self.sample_table.setRowCount(0)
        sample_results = []
        if text:
            sample_results = self.sample_logic.global_search(text)
            for i, res in enumerate(sample_results):
                self.sample_table.insertRow(i)
                
                # 名称 (带易降解警告)
                name_item = QTableWidgetItem(res["name"])
                if res["ft_count"] >= 5: 
                    name_item.setText(f"?? {res['name']}")
                    name_item.setForeground(Qt.red)
                self.sample_table.setItem(i, 0, name_item)
                
                self.sample_table.setItem(i, 1, QTableWidgetItem(res["type"]))
                
                # 物理位置 (埋入寻路锚点)
                loc_item = QTableWidgetItem(res["location_str"])
                loc_item.setForeground(Qt.darkBlue); loc_item.setFont(self._get_bold_font())
                loc_item.setData(Qt.UserRole, res["path"])         # 埋入机器路径
                loc_item.setData(Qt.UserRole + 1, res["well_id"])  # 埋入孔位ID
                self.sample_table.setItem(i, 2, loc_item)
                
                self.sample_table.setItem(i, 3, QTableWidgetItem(f"{res['vol']} {res['unit']}"))
                
                ft_item = QTableWidgetItem(f"{res['ft_count']} 次")
                if res["ft_count"] >= 5: ft_item.setForeground(Qt.red)
                self.sample_table.setItem(i, 4, ft_item)
                
                self.sample_table.setItem(i, 5, QTableWidgetItem(f"所有人:{res['owner']} | {res['notes']}"))
                
        self.lbl_status.setText(f"检索完成。找到 {len(filtered_files)} 个电子数据文件，{len(sample_results)} 个实体物理样本。")

    def _on_file_double_click(self, index):
        item = self.file_table.item(index.row(), 4)
        if item:
            filepath = item.data(Qt.UserRole)
            if os.path.exists(filepath):
                try:
                    if platform.system() == "Windows": os.startfile(filepath)
                    elif platform.system() == "Darwin": subprocess.Popen(['open', filepath])
                    else: subprocess.Popen(['xdg-open', filepath])
                except Exception as e: QMessageBox.warning(self, "打开失败", str(e))

    def _on_sample_double_click(self, index):
        """?? 空间瞬移触发点"""
        item = self.sample_table.item(index.row(), 2) # 获取位置列
        if item:
            path = item.data(Qt.UserRole)
            well_id = item.data(Qt.UserRole + 1)
            # 发射瞬移信号！
            self.sig_jump_to_sample.emit(path, well_id)
            self.accept() # 顺手关闭搜索框，让用户专心看样本库


# ==========================================
# 下方为 DataHubCoordinator 原有代码... 
# ==========================================
class DataHubCoordinator:
    def __init__(self):
        self.ui = DataHubUI()
        self.logic = DataHubLogic()
        self.current_root_path = ""
        self.external_root_path = "" 
        self._load_global_tags()
        self._bind_signals()

    def _load_global_tags(self):
        tags = GlobalConfig.get("archive_tags", [])
        self.ui.load_config_tags(tags)

    def _bind_signals(self):
        self.ui.sig_mount_clicked.connect(self.handle_mount_folder)
        self.ui.sig_filter_changed.connect(self.refresh_data_lists)
        self.ui.sig_file_clicked.connect(self.handle_file_preview)
        self.ui.sig_send_to_workspace.connect(global_bus.send_file_to_plot.emit)
        self.ui.sig_context_action.connect(self.handle_context_action)
        self.ui.sig_global_search_clicked.connect(self.handle_global_search)
        self.ui.sig_data_source_changed.connect(self.handle_source_changed)
        self.ui.sig_files_dropped.connect(self.handle_files_dropped)

    def handle_source_changed(self, mode):
        if mode == "internal":
            self.ui.btn_open.setVisible(False)
            self.current_root_path = GlobalConfig.get("archive_root", os.path.join(os.getcwd(), "SciForge_Archive"))
            if not os.path.exists(self.current_root_path):
                os.makedirs(self.current_root_path, exist_ok=True)
            self.ui.update_path_label(self.current_root_path)
        else:
            self.ui.btn_open.setVisible(True) 
            self.current_root_path = self.external_root_path
            self.ui.update_path_label(self.current_root_path if self.current_root_path else "未选择")
        self.refresh_data_lists()

    def handle_global_search(self):
        archive_root = GlobalConfig.get("archive_root", os.path.join(os.getcwd(), "SciForge_Archive"))
        dlg = ArchiveSearchDialog(archive_root, self.ui)
        
        # ?? 正确的做法：直接把弹窗发出的信号，桥接到全局总线上转发！
        dlg.sig_jump_to_sample.connect(global_bus.jump_to_sample.emit)
        
        dlg.exec_()
        
    def get_icon_for_ext(self, ext):
        if ext in ['.py']: return FIF.CODE.icon()
        if ext in ['.png', '.jpg', '.jpeg', '.tif']: return FIF.PHOTO.icon()
        if ext in ['.csv', '.xlsx', '.xls']: return FIF.LABEL.icon()
        if ext in ['.pdb', '.cif']: return FIF.APPLICATION.icon()
        if ext in ['.fasta', '.seq', '.dna']: return FIF.ALIGNMENT.icon()
        if ext in ['.pdf', '.doc', '.docx', '.ppt', '.pptx']: return FIF.DOCUMENT.icon()
        if ext in ['.zip', '.rar', '.tar', '.gz']: return FIF.FOLDER_ZIP.icon() if hasattr(FIF, 'FOLDER_ZIP') else FIF.FOLDER.icon()
        if ext in ['.mrc', '.map']: return FIF.TILES.icon()
        return FIF.DOCUMENT.icon()

    def handle_mount_folder(self):
        folder = QFileDialog.getExistingDirectory(self.ui, "选择数据根目录")
        if folder:
            self.external_root_path = folder 
            self.current_root_path = folder
            self.ui.update_path_label(folder)
            self.refresh_data_lists()

    def refresh_data_lists(self):
        if not self.current_root_path or not os.path.exists(self.current_root_path): return
        
        self.ui.file_table.setSortingEnabled(False)
        self.ui.file_tree.setSortingEnabled(False)
        self.ui.file_table.setRowCount(0)
        self.ui.file_tree.clear()

        allowed_exts = self.ui.get_active_extensions()
        project_tag = self.ui.combo_project.currentText()
        exp_tag = self.ui.combo_exp.currentText() 
        
        search_path = self.current_root_path
        if project_tag != "全部项目":
            search_path = os.path.join(self.current_root_path, project_tag)
            if not os.path.exists(search_path): 
                self.ui.file_table.setSortingEnabled(True)
                self.ui.file_tree.setSortingEnabled(True)
                return 

        row_idx = 0
        for root, dirs, files in os.walk(search_path):
            for file_name in files:
                if exp_tag != "全部实验类型" and exp_tag not in root and exp_tag not in file_name:
                    continue
                    
                ext = os.path.splitext(file_name)[1].lower()
                if ext in allowed_exts:
                    full_path = os.path.join(root, file_name)
                    size_kb, _ = self.logic.get_file_meta(full_path)
                    
                    self.ui.file_table.insertRow(row_idx)
                    name_item = QTableWidgetItem(file_name)
                    name_item.setIcon(self.get_icon_for_ext(ext))
                    name_item.setData(Qt.UserRole, full_path)
                    
                    self.ui.file_table.setItem(row_idx, 0, name_item)
                    self.ui.file_table.setItem(row_idx, 1, QTableWidgetItem(ext))
                    self.ui.file_table.setItem(row_idx, 2, NumericTableItem(f"{size_kb:.1f}"))
                    row_idx += 1

        root_node = QTreeWidgetItem(self.ui.file_tree)
        root_node.setText(0, os.path.basename(search_path))
        root_node.setIcon(0, FIF.FOLDER.icon())
        root_node.setData(0, Qt.UserRole, search_path) # ?? ?? 必须加这行！否则往根目录拖拽会失效
        root_node.setExpanded(True) 
        
        self._populate_tree_recursive(search_path, root_node, allowed_exts, exp_tag)

        self.ui.file_table.setSortingEnabled(True)
        self.ui.file_tree.setSortingEnabled(True)

    def _populate_tree_recursive(self, current_path, parent_node, allowed_exts, exp_tag="全部实验类型"):
        try:
            has_valid_child = False
            for item in os.listdir(current_path):
                full_path = os.path.join(current_path, item)
                if os.path.isdir(full_path):
                    folder_node = QTreeWidgetItem()
                    folder_node.setText(0, item)
                    folder_node.setIcon(0, FIF.FOLDER.icon())
                    folder_node.setData(0, Qt.UserRole, full_path) # ?? ?? 必须加这行！否则往子文件夹拖拽会失效
                    if self._populate_tree_recursive(full_path, folder_node, allowed_exts, exp_tag):
                        parent_node.addChild(folder_node)
                        has_valid_child = True
                else:
                    if exp_tag != "全部实验类型" and exp_tag not in current_path and exp_tag not in item:
                        continue
                        
                    ext = os.path.splitext(item)[1].lower()
                    if ext in allowed_exts:
                        file_node = QTreeWidgetItem()
                        file_node.setText(0, item)
                        file_node.setIcon(0, self.get_icon_for_ext(ext))
                        file_node.setData(0, Qt.UserRole, full_path)
                        parent_node.addChild(file_node)
                        has_valid_child = True
            return has_valid_child
        except PermissionError:
            return False

    def handle_context_action(self, action_type, filepath, extra_param=""):
        if action_type == "explore":
            self.logic.open_in_explorer(filepath)
        elif action_type == "open_system":
            self.logic.open_system_default(filepath)
        elif action_type == "copy":
            QApplication.clipboard().setText(filepath)
        elif action_type == "send_to_eln":
            global_bus.send_file_to_eln.emit(filepath)
            
        # 【核心修改】：把插件ID带上，发射给全局总线
        elif action_type == "send_to_plot":
            global_bus.send_file_to_plot.emit(filepath, extra_param)
            
        elif action_type == "rename":
            old_name = os.path.basename(filepath)
            new_name, ok = QInputDialog.getText(self.ui, "重命名", "请输入新的文件名称 (请保留后缀):", text=old_name)
            if ok and new_name and new_name != old_name:
                success, msg = self.logic.rename_file(filepath, new_name)
                if success:
                    self.ui.current_selected_filepath = None
                    self.refresh_data_lists()
                else:
                    QMessageBox.warning(self.ui, "重命名失败", f"无法重命名该文件:\n{msg}")
        elif action_type == "delete":
            reply = QMessageBox.question(
                self.ui, '高危操作警告', 
                f"?? 您确定要永久删除此文件吗？此操作无法通过回收站撤销！\n\n{os.path.basename(filepath)}", 
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                success, msg = self.logic.delete_file(filepath)
                if success:
                    self.ui.current_selected_filepath = None
                    self.ui.set_details_label("文件已被删除。")
                    self.refresh_data_lists()
                else:
                    QMessageBox.warning(self.ui, "删除失败", f"文件可能正被其他程序占用:\n{msg}")

    def handle_file_preview(self, filepath):
        if not os.path.exists(filepath): return
        ext = os.path.splitext(filepath)[1].lower()
        size_kb, mtime = self.logic.get_file_meta(filepath)
        deep_meta = self.logic.get_deep_meta(filepath, ext)
        info_text = f"载体: {os.path.basename(filepath)}  |  体积: {size_kb:.1f} KB  |  时间: {mtime}{deep_meta}"
        self.ui.set_details_label(info_text)

        if ext in ['.png', '.jpg', '.jpeg', '.tif']:
            self.ui.show_image_preview(filepath)
        elif ext in ['.csv', '.xlsx', '.xls']:
            try:
                import pandas as pd
                df = pd.read_csv(filepath) if ext == '.csv' else pd.read_excel(filepath)
                self.ui.show_table_preview(df) 
            except Exception as e:
                self.ui.show_binary_preview(f"表格读取失败:\n{str(e)}")
        elif ext in ['.doc', '.docx', '.pdf']:
            txt = self.logic.read_doc_pdf_content(filepath, ext)
            self.ui.show_text_preview(txt)
        elif ext in ['.zip', '.rar', '.gz', '.tar', '.mrc', '.map', '.ppt', '.pptx']:
            self.ui.show_binary_preview(f"二进制/压缩文件格式 ({ext})\n请在外部软件中打开。")
        else:
            txt = self.logic.read_text_content(filepath)
            self.ui.show_text_preview(txt)

    def handle_files_dropped(self, filepaths, target_dir):
        # 防呆检测：看看底层有没有 move_files 方法
        if not hasattr(self.logic, 'move_files'):
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self.ui, "严重错误", "底层逻辑缺失 move_files 方法！请检查 ctrl_data_hub.py")
            return
            
        success, msg = self.logic.move_files(filepaths, target_dir)
        if success:
            self.ui.set_details_label(f"? {msg}")
            # 静默刷新两边的视图，让用户看到文件真正“飞过去”了！
            self.refresh_data_lists()
        else:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self.ui, "物理移动失败", msg)