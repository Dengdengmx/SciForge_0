# hubs_calendar_archive.py
import os
import re
from PyQt5.QtCore import QDate, Qt, QThreadPool
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QFileDialog, QMessageBox
from qfluentwidgets import CalendarPicker, SubtitleLabel, PrimaryPushButton, BodyLabel, ComboBox, LineEdit

from view.ui_calendar_archive import CalendarArchiveUI
from controllers.ctrl_calendar_archive import CalendarArchiveLogic, AutoProcessWorker
from core.config import GlobalConfig
from core.signals import global_bus 

# ==========================================
# 🎯 终极归档弹窗：唯一真理网关
# ==========================================
class ArchiveConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件归档与追踪配置")
        self.setFixedSize(350, 220)
        self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self)
        
        self.input_name = LineEdit()
        self.input_name.setPlaceholderText("请输入名称 (选填)...")
        
        self.input_operator = LineEdit()
        self.input_operator.setPlaceholderText("请输入实验人姓名 (选填)...")
        
        layout.addWidget(BodyLabel("1. 名称 (将作为归档子文件夹和文件名):"))
        layout.addWidget(self.input_name)
        layout.addSpacing(10)
        layout.addWidget(BodyLabel("2. 实验人 (合并数据时方便追溯):"))
        layout.addWidget(self.input_operator)
        
        layout.addStretch()
        btn_box = QHBoxLayout()
        btn_ok = PrimaryPushButton("确定归档并运算")
        btn_ok.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(btn_ok)
        layout.addLayout(btn_box)
        
    def get_data(self):
        return self.input_name.text().strip(), self.input_operator.text().strip()

class ExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择报告导出区间")
        self.setFixedSize(400, 200)
        self.setStyleSheet("background: white;")
        layout = QVBoxLayout(self)
        layout.addWidget(SubtitleLabel("选择时间范围"))
        row = QHBoxLayout()
        self.picker_start = CalendarPicker(); self.picker_end = CalendarPicker()
        row.addWidget(BodyLabel("开始日期:")); row.addWidget(self.picker_start); row.addSpacing(20)
        row.addWidget(BodyLabel("结束日期:")); row.addWidget(self.picker_end); layout.addLayout(row)
        layout.addStretch(); btn_row = QHBoxLayout()
        btn_export = PrimaryPushButton("导出报告"); btn_export.clicked.connect(self.accept)
        btn_row.addStretch(); btn_row.addWidget(btn_export); layout.addLayout(btn_row)

class CalendarArchiveCoordinator:
    def __init__(self):
        self.ui = CalendarArchiveUI()
        self.logic = CalendarArchiveLogic()
        self.current_view_date = QDate.currentDate()
        
        # 💡 新增这一行：让中枢自己也记录当前选中的日期
        self.current_selected_date = QDate.currentDate() 
        
        self.view_mode = 0 
        # ... 后面的代码保持不变 
        
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(3)
        
        self._load_global_config()
        self._bind_signals()
        self._bind_global_signals() 
        self._refresh_calendar()
        self.handle_date_changed(QDate.currentDate())

    def _load_global_config(self):
        tags = GlobalConfig.get("archive_tags", ["默认项目"])
        tpls = GlobalConfig.get("eln_templates", {})
        self.ui.load_config_data(tags, tpls)

    def _bind_signals(self):
        self.ui.sig_date_changed.connect(self.handle_date_changed)
        self.ui.sig_view_changed.connect(self.handle_view_changed)
        self.ui.sig_time_nav.connect(self.handle_time_nav)
        self.ui.sig_zoom_changed.connect(self.handle_zoom_changed)
        self.ui.sig_save_requested.connect(self.handle_save_requested)
        self.ui.sig_export_requested.connect(self.handle_export) 
        self.ui.sig_upload_clicked.connect(self.handle_manual_upload)
        # 💡 核心新增：接收导出单日 PDF 的信号
        self.ui.sig_export_pdf.connect(self.handle_export_single_pdf)
        self.ui.sig_ref_sample_clicked.connect(self.handle_reference_sample)


    def _bind_global_signals(self):
        global_bus.send_file_to_eln.connect(self.handle_incoming_file)

    def handle_manual_upload(self, *args):
        filepath, _ = QFileDialog.getOpenFileName(self.ui, "选择要归档分析的实验文件", "", "All Files (*)")
        if filepath:
            self.handle_incoming_file(filepath)

    def handle_incoming_file(self, filepath, target_date=None):
        date_qdate = target_date if target_date else self.current_selected_date
        date_str = date_qdate.toString("yyyy-MM-dd")
        
        exp_type = self.ui.combo_assoc_exp.currentText()
        if not exp_type or "未检测" in exp_type or "关联" in exp_type:
            clean_text = self.ui.text_main.toPlainText()
            exp_tags = re.findall(r'【(.*?)】', clean_text)
            exp_type = exp_tags[0] if exp_tags else "常规实验"

        dlg = ArchiveConfigDialog(self.ui)
        if not dlg.exec_(): return 
        
        item_name, operator = dlg.get_data()

        try:
            project = self.ui.combo_tag.currentText() 
        except AttributeError:
            project = GlobalConfig.get("archive_tags", ["默认项目"])[0]

        try:
            archive_dir, dest_path = self.logic.archive_raw_file(filepath, project, date_str, exp_type, item_name, operator)
            safe_dest = dest_path.replace('\\', '/')
            path_html = f"<span style='color:#107C10;'>📁 归档成功！路径: <br><a href='file:///{safe_dest}'>{safe_dest}</a></span>"
            self.ui.text_extra.append(path_html)
        except Exception as e:
            self.ui.text_extra.append(f"<span style='color:red;'>归档失败: {e}</span>")
            return

        self.ui.text_extra.append("<span style='color:#0078D7;'>⚙️ 正在排队等待后台执行计算脚本...</span>")
        
        worker = AutoProcessWorker(dest_path, archive_dir, [exp_type])
        worker.signals.sig_process_done.connect(self.on_auto_process_done)
        self.thread_pool.start(worker)

    def on_auto_process_done(self, original_file, image_path, analysis_text):
        date_str = self.current_selected_date.toString("yyyy-MM-dd")
        if analysis_text:
            self.ui.text_extra.append(f"<b>{analysis_text}</b>")
        if image_path and os.path.exists(image_path):
            self.ui.text_main.insert_image(image_path)
            
        self.ui.sig_save_requested.emit(date_str, self.ui.current_todos, self.ui.text_main.toHtml(), self.ui.text_extra.toHtml())

    # ==========================================
    # 💡 核心新增：一键导出单日高清 PDF 逻辑
    # ==========================================
    def handle_export_single_pdf(self):
        date_str = self.current_selected_date.toString("yyyy-MM-dd")
        
        # 让用户选择保存路径
        save_path, _ = QFileDialog.getSaveFileName(self.ui, "导出单次实验报告", f"SciForge_Report_{date_str}.pdf", "PDF Files (*.pdf)")
        if not save_path: return
        
        main_html = self.ui.text_main.toHtml()
        extra_html = self.ui.text_extra.toHtml()
        
        # 组装极度严谨漂亮的科研报告排版
        html_template = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif; padding: 20px; color: #333; }}
                h1 {{ text-align: center; color: #0078D7; border-bottom: 2px solid #0078D7; padding-bottom: 10px; font-size: 24px; }}
                h2 {{ color: #107C10; margin-top: 25px; font-size: 18px; border-left: 5px solid #107C10; padding-left: 10px; background-color: #f3f2f1; }}
                h3 {{ color: #D83B01; margin-top: 25px; font-size: 18px; border-left: 5px solid #D83B01; padding-left: 10px; background-color: #f3f2f1; }}
                .date {{ text-align: center; font-size: 14px; color: #666; margin-bottom: 30px; }}
                .content-box {{ border: 1px solid #ddd; padding: 15px; border-radius: 5px; background-color: #ffffff; line-height: 1.6; font-size: 13px; }}
            </style>
        </head>
        <body>
            <h1>SciForge 实验记录与归档报告</h1>
            <div class="date">实验日期: {date_str}</div>
            
            <h2>📝 实验记录与图谱</h2>
            <div class="content-box">{main_html}</div>
            
            <h3>📌 数据解析与结论</h3>
            <div class="content-box">{extra_html}</div>
        </body>
        </html>
        """
        
        try:
            # 动用 Qt 顶级渲染引擎 QPrinter + QTextDocument
            doc = QTextDocument()
            doc.setHtml(html_template)
            
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(save_path)
            
            # 执行渲染并写入硬盘
            doc.print_(printer)
            QMessageBox.information(self.ui, "导出成功", f"🎉 单次实验报告已成功导出至:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self.ui, "导出失败", f"PDF 渲染引擎发生异常:\n{str(e)}")

    # ==========================================
    # 🚀 联动核心：双向穿透与自动化生命周期管理
    # ==========================================
    def handle_reference_sample(self):
        from view.ui_calendar_archive import SampleReferenceDialog
        
        # 弹窗索要数据
        dlg = SampleReferenceDialog(self.ui)
        if not dlg.exec_(): return
        
        data = dlg.get_data()
        if not data: return

        # 🎯 动作一：穿透进入 SampleHub 扣减真实库存
        try:
            from controllers.ctrl_sample_hub import SampleHubLogic
            s_logic = SampleHubLogic()
            
            # 读取旧数据
            sample_info = s_logic.get_location_data(data['path']).get(data['well_id'])
            if sample_info:
                # 自动扣体积
                old_vol = float(sample_info.get('vol', 0))
                sample_info['vol'] = max(0.0, old_vol - data['consume_vol'])
                
                # 自动加冻融
                if data['add_ft']:
                    sample_info['ft'] = int(sample_info.get('ft', 0)) + 1
                    
                # 写回数据库！
                s_logic.update_item(data['path'], data['well_id'], sample_info)
        except Exception as e:
            QMessageBox.warning(self.ui, "联动警告", f"库存扣减失败，但记录仍将插入。\n{e}")

        # 🎯 动作二：在你的 ELN 编辑器里插入一枚绝美的记录勋章
        html_tag = (
            f"<span style='background-color:#e0f2fe; color:#0078D7; padding:2px 6px; "
            f"border-radius:4px; font-weight:bold; border: 1px solid #b3d4fc;'>"
            f"🧪 消耗 {data['consume_vol']}{data['unit']} | {data['name']} <span style='color:#666; font-size:11px;'>({data['location_str']})</span>"
            f"</span> &nbsp;"
        )
        
        # 自动插入到光标位置
        cursor = self.ui.text_main.textCursor()
        cursor.insertHtml(html_tag)
        self.ui.text_main.setTextCursor(cursor)

    # ==========================================
    # 视图控制代码
    # ==========================================
    def handle_view_changed(self, idx):
        self.view_mode = idx; self.ui.switch_main_view(idx); self._refresh_calendar()
    def handle_time_nav(self, offset):
        if self.view_mode == 0: self.current_view_date = self.current_view_date.addMonths(offset)
        elif self.view_mode == 1: self.current_view_date = self.current_view_date.addDays(7 * offset)
        elif self.view_mode == 2: self.current_view_date = self.current_view_date.addYears(offset)
        self._refresh_calendar()
    def handle_zoom_changed(self, height_val): self.ui.update_grid_height(height_val)
    def _refresh_calendar(self):
        self._load_global_config()
        y = self.current_view_date.year(); m = self.current_view_date.month(); d = self.current_view_date
        zoom_val = self.ui.slider_zoom.value()
        if self.view_mode == 0:
            self.ui.update_top_nav(f"{y}年 {m}月")
            self.ui.render_month_view(y, m, self.logic.schedule_data, zoom_val)
        elif self.view_mode == 1:
            sw = d.addDays(-(d.dayOfWeek() - 1))
            self.ui.update_top_nav(f"{sw.toString('MM.dd')} - {sw.addDays(6).toString('MM.dd')}")
            self.ui.render_week_view(sw, self.logic.schedule_data, zoom_val)
        elif self.view_mode == 2:
            self.ui.update_top_nav(f"{y}年"); self.ui.render_year_view(y)
    def handle_date_changed(self, qdate: QDate):
        # 💡 新增这一行：当用户在UI上点选了新日期，同步更新中枢的记录
        self.current_selected_date = qdate 
        
        date_str = qdate.toString("yyyy-MM-dd")
        if self.view_mode == 0 and qdate.month() != self.current_view_date.month():
            self.current_view_date = QDate(qdate.year(), qdate.month(), 1); self._refresh_calendar()
        self.ui.update_right_panel(qdate, self.logic.get_day_data(date_str))
    def handle_save_requested(self, date_str, todo_list, main_text, extra_text):
        self.logic.update_day_data(date_str, todo_list, main_text, extra_text)
        self._refresh_calendar() 
    def handle_export(self):
        dlg = ExportDialog(self.ui)
        if dlg.exec_():
            start = dlg.picker_start.date.toString("yyyy-MM-dd")
            end = dlg.picker_end.date.toString("yyyy-MM-dd")
            save_path, _ = QFileDialog.getSaveFileName(self.ui, "保存区间报告", f"SciForge_Report_{start}_{end}.html", "HTML Files (*.html)")
            if save_path:
                self.logic.export_report(start, end, save_path)
                QMessageBox.information(self.ui, "导出成功", f"报告已成功导出至:\n{save_path}")