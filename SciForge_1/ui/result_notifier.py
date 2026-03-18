# ui/result_notifier.py
import os
import shutil
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QFileDialog)
from PyQt5.QtGui import QPixmap, QFont, QPainter
from PyQt5.QtCore import Qt
from qfluentwidgets import PushButton, PrimaryPushButton, TextBrowser

from core.signals import global_bus

class ResultNotificationWindow(QDialog):
    """静默分析完成后的图文交互简报弹窗"""
    
    def __init__(self, title, html_report, image_path, plugin_id, original_filepath, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_id
        self.image_path = image_path
        self.original_filepath = original_filepath
        
        # 现代化 UI 设定
        self.setWindowTitle("SciForge 渲染引擎通知")
        self.setFixedSize(750, 500)
        # 保持置顶，提醒用户处理结果
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet("background-color: #F8F9FA; border-radius: 8px;")
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 1. 顶部标题
        title_label = QLabel(f"✅ 渲染完成: {title}")
        title_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        title_label.setStyleSheet("color: #107C10;")
        main_layout.addWidget(title_label)
        
        # 2. 中部左右分栏布局
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # 2.1 左侧：富文本简报 (如果后台有返回数据特征的话)
        if html_report:
            self.text_browser = TextBrowser()
            self.text_browser.setHtml(html_report)
            self.text_browser.setFixedWidth(260)
            self.text_browser.setStyleSheet("background-color: white; border: 1px solid #E0E0E0; border-radius: 6px;")
            content_layout.addWidget(self.text_browser)
        
        # 2.2 右侧：可缩放的交互式图片视图
        if image_path and os.path.exists(image_path):
            self.scene = QGraphicsScene()
            self.image_view = QGraphicsView(self.scene)
            # 将 Qt 替换为 QPainter
            self.image_view.setRenderHint(QPainter.SmoothPixmapTransform)
            self.image_view.setDragMode(QGraphicsView.ScrollHandDrag) 
            self.image_view.setStyleSheet("background-color: white; border: 1px solid #E0E0E0; border-radius: 6px;")
            
            pixmap = QPixmap(image_path)
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)
            
            # 自适应缩小至视图内
            self.image_view.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            # 绑定鼠标滚轮缩放
            self.image_view.wheelEvent = self._on_zoom
            content_layout.addWidget(self.image_view)
        
        main_layout.addLayout(content_layout)
        
        # 3. 底部操作栏
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        
        save_btn = PushButton("💾 直接下载图片 (.png)")
        save_btn.clicked.connect(self._save_image)
        btn_layout.addWidget(save_btn)
        
        send_btn = PrimaryPushButton("✏️ 带着文件去工作台微调")
        send_btn.clicked.connect(self._send_to_workspace)
        btn_layout.addWidget(send_btn)
        
        main_layout.addLayout(btn_layout)

    def _on_zoom(self, event):
        """处理滚轮缩放图片"""
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
        self.image_view.scale(zoom_factor, zoom_factor)

    def _save_image(self):
        if not self.image_path or not os.path.exists(self.image_path): return
        
        save_path, _ = QFileDialog.getSaveFileName(self, "保存渲染结果", "SciForge_Result.png", "Images (*.png *.tif *.jpg)")
        if save_path:
            shutil.copy(self.image_path, save_path)

    def _send_to_workspace(self):
        """携带底层数据切回工作站，交给用户手动微调"""
        # 触发总线，先切界面，再灌数据
        global_bus.switch_main_tab.emit("workspace")
        # 把原始文件扔回前台插件
        # 第 85 行左右
        global_bus.send_file_to_plot.emit(self.original_filepath, self.plugin_id)
        self.accept()