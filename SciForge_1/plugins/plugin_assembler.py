# plugins/plugin_assembler.py
import os
import json
import string
from PIL import Image

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QFileDialog, QMessageBox, QListWidget, QAbstractItemView, 
                             QFrame, QScrollArea, QDialog, QSizePolicy, QListWidgetItem)
from PyQt5.QtCore import Qt, pyqtSignal, QSettings

from qfluentwidgets import (CardWidget, BodyLabel, PrimaryPushButton, StrongBodyLabel,
                            PushButton, SpinBox, ComboBox, DoubleSpinBox, LineEdit,
                            FluentIcon as FIF)

from core.plugin_manager import BasePlugin

matplotlib.rcParams['font.family'] = 'Arial'

# ==============================================================================
# ★ 交互核心引擎：拖放画板与可拖拽文字 (保持纯净)
# ==============================================================================
class DropCanvas(FigureCanvasQTAgg):
    filesDropped = pyqtSignal(list)
    def __init__(self, fig):
        super().__init__(fig)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        valid_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.svg'))]
        if valid_files: self.filesDropped.emit(valid_files)
        event.acceptProposedAction()

class ImageListWidget(QListWidget):
    filesDropped = pyqtSignal(list)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            files = [u.toLocalFile() for u in urls if u.isLocalFile()]
            valid_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp'))]
            if valid_files: self.filesDropped.emit(valid_files)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

class DraggableText:
    def __init__(self, text_obj, canvas, tag_type='custom'):
        self.text = text_obj
        self.canvas = canvas
        self.tag_type = tag_type 
        self.press = None
        self.cid_press = canvas.mpl_connect('button_press_event', self.on_press)
        self.cid_release = canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_motion = canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        contains, _ = self.text.contains(event)
        if not contains: return
        if event.button == 1: 
            x0, y0 = self.text.get_position()
            self.press = (x0, y0, event.x, event.y)
        elif event.button == 3: 
            self.text.remove()
            self.canvas.draw_idle()

    def on_motion(self, event):
        if self.press is None: return
        if event.x is None or event.y is None: return
        x0, y0, xpress, ypress = self.press
        dx = (event.x - xpress) / self.canvas.figure.bbox.width
        dy = (event.y - ypress) / self.canvas.figure.bbox.height
        self.text.set_position((x0 + dx, y0 + dy))
        self.canvas.draw_idle()

    def on_release(self, event):
        self.press = None
        self.canvas.draw_idle()


# ==============================================================================
# ★ 前端：支持【工作台】与【全局设置】双模式的 Assembler UI
# ==============================================================================
class AssemblerUI(QWidget):
    def __init__(self, parent=None, is_setting_mode=False):
        super().__init__(parent)
        self.is_setting_mode = is_setting_mode
        self.items = [] 
        self.draggables = [] 
        self.active_item = None
        self.drag_data = None
        self.settings = QSettings("SciForge", "AssemblerPlugin")
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

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # ==============================================
        # 左侧：参数控制区
        # ==============================================
        left_panel = CardWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        h_tools = QHBoxLayout()
        btn_import_config = PushButton("📂 载入排版模板", icon=FIF.FOLDER)
        btn_export_config = PushButton("💾 保存排版模板", icon=FIF.SAVE)
        btn_import_config.clicked.connect(self.import_config)
        btn_export_config.clicked.connect(self.export_config)
        h_tools.addWidget(btn_import_config); h_tools.addWidget(btn_export_config)
        left_layout.addLayout(h_tools)

        # 1. 待拼装图片池 (仅工作站模式显示)
        gb_data, l_data = self._create_fluent_group("1. 图片资源队列 (拖拽排序)")
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 0, 0, 0)
        btn_add = PrimaryPushButton("导入图片", icon=FIF.DOWNLOAD)
        btn_add.clicked.connect(self.add_images_dialog)
        btn_clear = PushButton("清空", icon=FIF.DELETE)
        btn_clear.clicked.connect(self.clear_images)
        btn_row.addWidget(btn_add); btn_row.addWidget(btn_clear)
        l_data.addLayout(btn_row)
        
        self.list_widget = ImageListWidget()
        self.list_widget.setFixedHeight(90)
        self.list_widget.filesDropped.connect(self.add_images_from_files)
        self.list_widget.model().rowsMoved.connect(self.apply_auto_grid)
        l_data.addWidget(self.list_widget)
        
        if not self.is_setting_mode:
            left_layout.addWidget(gb_data)

        # 2. 全局画板设置
        gb_wh, l_wh = self._create_fluent_group("2. 画布物理尺寸 (英寸)")
        h_wh = QHBoxLayout(); h_wh.setContentsMargins(0, 0, 0, 0)
        self.spin_w = DoubleSpinBox(); self.spin_w.setRange(1.0, 50.0); self.spin_w.setValue(12.0); self.spin_w.setSingleStep(0.5)
        self.spin_h = DoubleSpinBox(); self.spin_h.setRange(1.0, 50.0); self.spin_h.setValue(8.0); self.spin_h.setSingleStep(0.5)
        h_wh.addWidget(BodyLabel("宽:")); h_wh.addWidget(self.spin_w, 1)
        h_wh.addSpacing(5)
        h_wh.addWidget(BodyLabel("高:")); h_wh.addWidget(self.spin_h, 1)
        l_wh.addLayout(h_wh)
        
        if not self.is_setting_mode:
            btn_resize = PushButton("🔄 调整并刷新物理画布")
            btn_resize.clicked.connect(self.apply_canvas_size)
            l_wh.addWidget(btn_resize)
        
        left_layout.addWidget(gb_wh)

        # 3. 自动网格打底参数
        gb_param, l_param = self._create_fluent_group("3. 自动网格排版策略")
        left_layout.addWidget(gb_param)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0) 
        scroll_layout.setSpacing(6)

        grid_row = QHBoxLayout()
        grid_row.addWidget(BodyLabel("分布 行:")); self.spin_rows = SpinBox(); self.spin_rows.setRange(1,20); self.spin_rows.setValue(1); grid_row.addWidget(self.spin_rows)
        grid_row.addWidget(BodyLabel("列:")); self.spin_cols = SpinBox(); self.spin_cols.setRange(1,20); self.spin_cols.setValue(2); grid_row.addWidget(self.spin_cols)
        scroll_layout.addLayout(grid_row)

        space_row = QHBoxLayout()
        space_row.addWidget(BodyLabel("间距 X:")); self.spin_wspace = DoubleSpinBox(); self.spin_wspace.setRange(0,0.5); self.spin_wspace.setSingleStep(0.02); self.spin_wspace.setValue(0.02); space_row.addWidget(self.spin_wspace)
        space_row.addWidget(BodyLabel("Y:")); self.spin_hspace = DoubleSpinBox(); self.spin_hspace.setRange(0,0.5); self.spin_hspace.setSingleStep(0.02); self.spin_hspace.setValue(0.02); space_row.addWidget(self.spin_hspace)
        scroll_layout.addLayout(space_row)
        
        tag_row = QHBoxLayout()
        tag_row.addWidget(BodyLabel("标号:")); self.cb_tag_style = ComboBox(); self.cb_tag_style.addItems(["A, B, C...", "a, b, c...", "无标号"])
        tag_row.addWidget(self.cb_tag_style, 1)
        tag_row.addWidget(BodyLabel("字号:")); self.spin_tag_fs = SpinBox(); self.spin_tag_fs.setRange(10,100); self.spin_tag_fs.setValue(24)
        tag_row.addWidget(self.spin_tag_fs)
        scroll_layout.addLayout(tag_row)

        # 4. 自由标注区 (工作站独有)
        if not self.is_setting_mode:
            scroll_layout.addSpacing(10)
            scroll_layout.addWidget(StrongBodyLabel("🔠 4. 自由文本标注"))
            
            custom_txt_row1 = QHBoxLayout()
            self.line_custom_text = LineEdit()
            self.line_custom_text.setPlaceholderText("如: 10μM, 24h")
            custom_txt_row1.addWidget(self.line_custom_text, 1)
            scroll_layout.addLayout(custom_txt_row1)

            custom_txt_row2 = QHBoxLayout()
            self.spin_custom_fs = SpinBox(); self.spin_custom_fs.setRange(8, 100); self.spin_custom_fs.setValue(16)
            btn_add_txt = PushButton("➕ 抛入画布")
            btn_add_txt.clicked.connect(self.add_custom_text)
            custom_txt_row2.addWidget(BodyLabel("字号:")); custom_txt_row2.addWidget(self.spin_custom_fs)
            custom_txt_row2.addWidget(btn_add_txt, 1)
            scroll_layout.addLayout(custom_txt_row2)
            
            tip_frame = QFrame()
            tip_frame.setStyleSheet("background-color: #f0f8ff; border: 1px solid #cce5ff; border-radius: 4px;")
            tip_layout = QVBoxLayout(tip_frame)
            lbl_tip = BodyLabel("💡 <b>自由排版指北：</b><br>"
                                "1. 点【一键排版】快速打底<br>"
                                "2. <b>左键拖拽</b> 任意微调元素<br>"
                                "3. <b>鼠标滚轮</b> 悬停单独缩放图片<br>"
                                "4. <b>右键单击</b> 直接删除元素")
            lbl_tip.setStyleSheet("font-size: 11px; color: #004085;")
            tip_layout.addWidget(lbl_tip)
            scroll_layout.addWidget(tip_frame)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        left_layout.addWidget(scroll)

        # ==============================================
        # 阻断逻辑：全局设置模式到此结束
        # ==============================================
        if self.is_setting_mode:
            self.btn_save_config = PrimaryPushButton("💾 确认并保存为全局默认参数", icon=FIF.SAVE)
            self.btn_save_config.setFixedHeight(45)
            self.btn_save_config.clicked.connect(self.save_settings_and_close)
            left_layout.addWidget(self.btn_save_config)
            main_layout.addWidget(left_panel)
            return

        # ==============================================
        # 正常模式：生成右侧巨型排版画板
        # ==============================================
        self.btn_grid = PrimaryPushButton("🌟 一键自动网格排版 (刷新)", icon=FIF.LAYOUT)
        self.btn_grid.clicked.connect(self.apply_auto_grid)
        self.btn_grid.setFixedHeight(40)
        self.btn_grid.setStyleSheet("background-color: #107c10; color: white;") 
        left_layout.addWidget(self.btn_grid)

        splitter = QSplitter(Qt.Horizontal, self)
        splitter.setStyleSheet("QSplitter::handle { background-color: #E0E0E0; width: 4px; border-radius: 2px; margin: 10px 2px; }")
        splitter.addWidget(left_panel)

        right_panel = CardWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # 核心：绝对物理锁死的拖拽画布
        self.fig = plt.figure()
        self.fig.patch.set_facecolor('white') 
        self.canvas = DropCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.canvas.filesDropped.connect(self.add_images_from_files)
        
        self.canvas_container = QWidget()
        self.canvas_container.setStyleSheet("background-color: #e5e5e5;")
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setAlignment(Qt.AlignCenter)
        self.canvas_layout.addWidget(self.canvas)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: #e5e5e5; }")
        self.scroll_area.setWidget(self.canvas_container)
        
        self.toolbar = NavigationToolbar2QT(self.canvas, right_panel)
        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.scroll_area)
        
        # 导出条
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        self.cb_dpi = ComboBox(); self.cb_dpi.addItems(["300 DPI", "600 DPI", "1200 DPI"])
        self.cb_fmt = ComboBox(); self.cb_fmt.addItems(["pdf", "tiff", "png"])
        export_layout.addWidget(StrongBodyLabel("质量/格式:"))
        export_layout.addWidget(self.cb_dpi); export_layout.addWidget(self.cb_fmt)
        
        btn_save = PushButton("💾 导出出版级大图", icon=FIF.SAVE)
        btn_save.clicked.connect(self.save_img)
        export_layout.addWidget(btn_save)
        right_layout.addLayout(export_layout)

        splitter.addWidget(right_panel)
        splitter.setSizes([320, 980])
        main_layout.addWidget(splitter)
        
        # 绑定核心交互事件
        self._connect_events()
        self.apply_canvas_size()

    # ------------------------------------
    # 数据摄取与 Data Hub 联动接口
    # ------------------------------------
    def load_file(self, filepath):
        """兼容 Workspace 从 Data Hub 右键传图过来"""
        if not os.path.exists(filepath): return
        if filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.svg')):
            self.add_images_from_files([filepath])

    def add_images_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择图片", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.webp);;All Files (*)")
        if files: self.add_images_from_files(files)

    def add_images_from_files(self, files):
        if self.is_setting_mode: return
        current_paths = [self.list_widget.item(i).data(Qt.UserRole) for i in range(self.list_widget.count())]
        added = False
        for f in files:
            if f not in current_paths:
                item = QListWidgetItem(os.path.basename(f))
                item.setData(Qt.UserRole, f)
                self.list_widget.addItem(item)
                added = True
        
        # 新增图片后自动触发网格打底
        if added: self.apply_auto_grid()

    def clear_images(self):
        if self.is_setting_mode: return
        self.list_widget.clear()
        self.items.clear()
        self.draggables.clear()
        self.fig.clear()
        self.canvas.draw_idle()

    # ------------------------------------
    # 核心排版引擎
    # ------------------------------------
    def apply_canvas_size(self):
        if self.is_setting_mode: return
        w_in, h_in = self.spin_w.value(), self.spin_h.value()
        base_dpi = 100 
        self.fig.set_size_inches(w_in, h_in)
        self.canvas.setFixedSize(int(w_in * base_dpi), int(h_in * base_dpi))
        self.canvas_container.updateGeometry()
        self.canvas.draw_idle()

    def apply_auto_grid(self, *args):
        if self.is_setting_mode or self.list_widget.count() == 0: return
        self._save_memory()
        
        # 清理旧图与自动标号，保留自由文本
        items_to_remove = []
        for item in self.items:
            if item['type'] == 'image':
                item['ax'].remove()
                items_to_remove.append(item)
            elif item['type'] == 'auto_tag':
                item['obj'].remove()
                items_to_remove.append(item)
                
        for item in items_to_remove: self.items.remove(item)
        self.draggables = [d for d in self.draggables if d.tag_type != 'auto_tag']

        rows, cols = self.spin_rows.value(), self.spin_cols.value()
        wspace, hspace = self.spin_wspace.value(), self.spin_hspace.value()
        W, H = self.fig.get_size_inches()
        
        paths = [self.list_widget.item(i).data(Qt.UserRole) for i in range(self.list_widget.count())]
        
        left, right, top, bottom = 0.05, 0.05, 0.05, 0.05
        avail_w = 1.0 - left - right
        avail_h = 1.0 - top - bottom
        
        cell_w = (avail_w - (cols - 1) * wspace) / cols if cols > 1 else avail_w
        cell_h = (avail_h - (rows - 1) * hspace) / rows if rows > 1 else avail_h
        
        style = self.cb_tag_style.currentText()
        if "A, B, C" in style: tags = list(string.ascii_uppercase)
        elif "a, b, c" in style: tags = list(string.ascii_lowercase)
        else: tags = [""] * 100
        tag_fs = self.spin_tag_fs.value()

        for i, path in enumerate(paths):
            if i >= rows * cols: break 
            
            r, c = i // cols, i % cols
            x = left + c * (cell_w + wspace)
            y = 1.0 - top - (r + 1) * cell_h - r * hspace
            
            try:
                img = Image.open(path)
                iw, ih = img.size
                ar = iw / ih
                cell_ar = (cell_w * W) / (cell_h * H)
                
                if ar > cell_ar:
                    ax_w = cell_w
                    ax_h = (cell_w * W / ar) / H
                else:
                    ax_h = cell_h
                    ax_w = (cell_h * H * ar) / W
                    
                ax_x = x + (cell_w - ax_w) / 2
                ax_y = y + (cell_h - ax_h) / 2
                
                ax = self.fig.add_axes([ax_x, ax_y, ax_w, ax_h])
                ax.imshow(img, aspect='equal')
                ax.axis('off')
                self.items.append({'type': 'image', 'ax': ax, 'z': 0, 'path': path})
                
                if tags[i]:
                    t = self.fig.text(ax_x - 0.01, ax_y + ax_h + 0.01, tags[i], 
                                      fontsize=tag_fs, fontweight='bold', va='bottom', ha='right', color='black')
                    drag = DraggableText(t, self.canvas, tag_type='auto_tag')
                    self.draggables.append(drag)
                    self.items.append({'type': 'auto_tag', 'obj': t, 'z': 0})
            except Exception as e:
                print(f"载入失败: {e}")

        self.apply_canvas_size() 

    def add_custom_text(self):
        text = self.line_custom_text.text().strip()
        if not text or self.is_setting_mode: return
        
        fs = self.spin_custom_fs.value()
        t = self.fig.text(0.5, 0.5, text, fontsize=fs, va='center', ha='center', color='black',
                          bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=2))
        
        drag = DraggableText(t, self.canvas, tag_type='custom_text')
        self.draggables.append(drag)
        self.items.append({'type': 'custom_text', 'obj': t, 'z': 0})
        
        self.line_custom_text.clear()
        self.canvas.draw_idle()

    def save_img(self):
        if self.is_setting_mode: return
        fmt = self.cb_fmt.currentText()
        dpi = int(self.cb_dpi.currentText().split()[0])
        
        path, _ = QFileDialog.getSaveFileName(self, "导出出版级大图", f"Figure_Assembly.{fmt}", f"{fmt.upper()} Files (*.{fmt})")
        if path:
            try:
                self.fig.savefig(path, dpi=dpi, transparent=True)
                QMessageBox.information(self, "成功", f"原图已导出:\n{path}\nDPI: {dpi}")
            except Exception as e:
                QMessageBox.critical(self, "导出失败", str(e))

    # ------------------------------------
    # 交互事件引擎
    # ------------------------------------
    def _connect_events(self):
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)

    def on_press(self, event):
        if event.x is None or event.y is None: return
        clicked_item = None
        for item in reversed(self.items):
            if item['type'] in ['auto_tag', 'custom_text']:
                contains, _ = item['obj'].contains(event)
                if contains: clicked_item = item; break
            elif item['type'] == 'image':
                if item['ax'] == event.inaxes: clicked_item = item; break

        if not clicked_item: return

        if event.button == 3:
            if clicked_item['type'] in ['auto_tag', 'custom_text']: clicked_item['obj'].remove()
            else: clicked_item['ax'].remove()
            self.items.remove(clicked_item)
            self.canvas.draw_idle()
            return

        if event.button == 1:
            self.active_item = clicked_item
            max_z = max([it.get('z', 0) for it in self.items] + [0])
            new_z = max_z + 1
            self.active_item['z'] = new_z
            
            if clicked_item['type'] in ['auto_tag', 'custom_text']:
                clicked_item['obj'].set_zorder(new_z)
                x, y = clicked_item['obj'].get_position()
                self.drag_data = {'x0': x, 'y0': y, 'press_x': event.x, 'press_y': event.y}
            else:
                clicked_item['ax'].set_zorder(new_z)
                pos = clicked_item['ax'].get_position()
                self.drag_data = {'x0': pos.x0, 'y0': pos.y0, 'press_x': event.x, 'press_y': event.y}
            self.canvas.draw_idle()

    def on_motion(self, event):
        if self.drag_data is None or self.active_item is None: return
        if event.x is None or event.y is None: return
        
        dx = (event.x - self.drag_data['press_x']) / self.fig.bbox.width
        dy = (event.y - self.drag_data['press_y']) / self.fig.bbox.height
        
        if self.active_item['type'] in ['auto_tag', 'custom_text']:
            self.active_item['obj'].set_position((self.drag_data['x0'] + dx, self.drag_data['y0'] + dy))
        else:
            ax = self.active_item['ax']
            pos = ax.get_position()
            ax.set_position([self.drag_data['x0'] + dx, self.drag_data['y0'] + dy, pos.width, pos.height])
        self.canvas.draw_idle()

    def on_release(self, event):
        self.active_item = None
        self.drag_data = None

    def on_scroll(self, event):
        if event.inaxes is None: return
        target_img = None
        for item in reversed(self.items):
            if item['type'] == 'image' and item['ax'] == event.inaxes:
                target_img = item; break
        if not target_img: return
        
        ax = target_img['ax']
        pos = ax.get_position()
        scale = 1.05 if event.button == 'up' else 0.95
        new_w, new_h = pos.width * scale, pos.height * scale
        new_x, new_y = pos.x0 - (new_w - pos.width) / 2, pos.y0 - (new_h - pos.height) / 2
        ax.set_position([new_x, new_y, new_w, new_h])
        self.canvas.draw_idle()

    # ------------------------------------
    # 系统记忆引擎
    # ------------------------------------
    def _save_memory(self):
        self.settings.setValue("assembler_plugin_params", json.dumps(self.get_config_dict()))

    def _load_memory(self):
        data_str = self.settings.value("assembler_plugin_params", "")
        if data_str:
            try: self.apply_config_dict(json.loads(data_str))
            except: pass

    def get_config_dict(self):
        config = {
            "spin_w": self.spin_w.value(), "spin_h": self.spin_h.value(),
            "spin_rows": self.spin_rows.value(), "spin_cols": self.spin_cols.value(),
            "spin_wspace": self.spin_wspace.value(), "spin_hspace": self.spin_hspace.value(),
            "cb_tag_style": self.cb_tag_style.currentText(), "spin_tag_fs": self.spin_tag_fs.value()
        }
        if not self.is_setting_mode:
            config["spin_custom_fs"] = self.spin_custom_fs.value()
            config["cb_dpi"] = self.cb_dpi.currentText()
            config["cb_fmt"] = self.cb_fmt.currentText()
        return config

    def apply_config_dict(self, data):
        self.spin_w.setValue(data.get("spin_w", 12.0)); self.spin_h.setValue(data.get("spin_h", 8.0))
        self.spin_rows.setValue(data.get("spin_rows", 1)); self.spin_cols.setValue(data.get("spin_cols", 2))
        self.spin_wspace.setValue(data.get("spin_wspace", 0.02)); self.spin_hspace.setValue(data.get("spin_hspace", 0.02))
        self.cb_tag_style.setCurrentText(data.get("cb_tag_style", "A, B, C...")); self.spin_tag_fs.setValue(data.get("spin_tag_fs", 24))
        
        if not self.is_setting_mode:
            if "spin_custom_fs" in data: self.spin_custom_fs.setValue(data["spin_custom_fs"])
            if "cb_dpi" in data: self.cb_dpi.setCurrentText(data["cb_dpi"])
            if "cb_fmt" in data: self.cb_fmt.setCurrentText(data["cb_fmt"])

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存排版参数模板", "assembler_template.json", "JSON Files (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f: json.dump(self.get_config_dict(), f, indent=4)
            QMessageBox.information(self, "成功", "模板保存成功！")

    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "载入排版参数模板", "", "JSON Files (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f: self.apply_config_dict(json.load(f))
            if not self.is_setting_mode: self.apply_auto_grid()

    def save_settings_and_close(self):
        self._save_memory()
        parent_dlg = self.window()
        if isinstance(parent_dlg, QDialog): parent_dlg.accept()

# ==========================================
# 后端：插件描述器与全局入口联动
# ==========================================
class AssemblerPlugin(BasePlugin):
    plugin_id = "figure_assembler"
    plugin_name = "科研绘图拼板组装引擎"
    icon = "🖼️"
    
    # 【核心 1：向系统宣告身份】
    trigger_tag = "科研拼板"

    def get_ui(self, parent=None):
        return AssemblerUI(parent, is_setting_mode=False)

    def get_setting_card(self, parent=None):
        from qfluentwidgets import PrimaryPushSettingCard, FluentIcon as FIF
        from PyQt5.QtWidgets import QDialog, QVBoxLayout

        card = PrimaryPushSettingCard(
            "配置全局默认排版参数", 
            FIF.EDIT, 
            "🖼️ 科研大图拼板引擎", 
            "修改工作站中图片组装的默认画布尺寸、间距、列数与标号风格", 
            parent
        )

        def show_global_settings_dialog():
            dlg = QDialog(card) 
            dlg.setWindowTitle("大图拼装全局默认参数预设中心")
            dlg.resize(460, 600) 
            layout = QVBoxLayout(dlg)
            
            settings_ui = AssemblerUI(dlg, is_setting_mode=True)
            layout.addWidget(settings_ui)
            dlg.exec_()

        card.clicked.connect(show_global_settings_dialog)
        return card

    # 【核心 2：防崩溃的单图兜底渲染处理】
    @staticmethod
    def run(file_path, archive_dir):
        try:
            import os
            ext = os.path.splitext(file_path)[1].lower()
            
            # 极度包容的格式支持
            allowed_exts = ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp', '.gif', '.webp']
            if ext not in allowed_exts:
                return "", "【拼板引擎跳过】传入的文件不是受支持的图像格式。"

            # 引入无界面的 Agg 引擎
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            import matplotlib.pyplot as plt
            from PIL import Image
            
            plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
            plt.rcParams['axes.unicode_minus'] = False

            # 读取图片
            img = Image.open(file_path)
            
            # 后台单图套壳处理
            fig = Figure(figsize=(8, 6), dpi=150)
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(111)
            
            ax.imshow(img)
            ax.axis('off')
            ax.set_title(f"A. {os.path.basename(file_path)}", fontweight='bold', fontsize=14, loc='left')

            fig.tight_layout()
            
            # 导出
            out_name = f"plot_Assemble_{os.path.basename(file_path)}.png"
            out_path = os.path.join(archive_dir, out_name)
            fig.savefig(out_path, dpi=150, bbox_inches='tight')
            fig.clf()
            
            res_text = "🖼️ **【科研大图拼板拦截提示】**<br>已为您生成单图预览。由于拼板操作通常涉及多图排版与字母标号（A, B, C），强烈建议您通过右键菜单将其【定向投送至绘图引擎】，在可视化前台中进行沉浸式拖拽排版！"
            
            return out_path, res_text

        except Exception as e:
            return "", f"拼板引擎执行失败: {str(e)}"