# controllers/ctrl_calendar_archive.py
import os
import json
import re
import shutil
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
# 💡 引入了 QRunnable 和 QThreadPool 的底层支持
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal, QThreadPool

from core.config import GlobalConfig
from core.plugin_manager import PluginManager 

# ==========================================
# 🛠️ 系统级静默滚动日志配置 (Rolling Log)
# ==========================================
log_file_path = os.path.join(os.getcwd(), "SciForge_Analysis.log")
logger = logging.getLogger("SciForge_Analysis_Logger")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = RotatingFileHandler(log_file_path, maxBytes=2*1024*1024, backupCount=1, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ==========================================
# 🚀 并发任务队列核心：Worker 与 信号桥梁
# ==========================================
class WorkerSignals(QObject):
    """
    因为 QRunnable 是轻量级计算类，没有 QObject 的血统，无法发射信号。
    我们必须单独定义一个 QObject 作为它向主 UI 汇报进度的“对讲机”。
    """
    sig_process_done = pyqtSignal(str, str, str) 

class AutoProcessWorker(QRunnable):
    """
    【升级】从 QThread 降维打击到 QRunnable。
    它将作为标准“任务单元”被扔进 QThreadPool 的全局队列中排队执行。
    """
    def __init__(self, file_path, archive_dir, exp_tags):
        super().__init__()
        self.file_path = file_path
        self.archive_dir = archive_dir
        self.exp_tags = exp_tags
        # 挂载对讲机
        self.signals = WorkerSignals()

    def run(self):
        output_image_path = ""
        analysis_text = ""
        
        try:
            all_plugins = PluginManager.get_plugins()
            matched_plugin = None
            
            for plugin in all_plugins:
                if hasattr(plugin, 'trigger_tag') and plugin.trigger_tag in self.exp_tags:
                    matched_plugin = plugin
                    break
            
            if matched_plugin:
                if self.file_path.lower().endswith(('.csv', '.xlsx', '.xls', '.txt')):
                    output_image_path, analysis_text = matched_plugin.run(self.file_path, self.archive_dir)
                else:
                    analysis_text = f"【{matched_plugin.plugin_name} 跳过】传入的文件格式暂不支持自动化分析。"
            else:
                analysis_text = "已完成物理归档 (本次未匹配到自动化计算模块)。"
                
        except Exception as e:
            analysis_text = f"自动处理异常: {str(e)}"

        if analysis_text:
            clean_text = re.sub(r'<[^>]+>', '', analysis_text).strip() 
            logger.info(f"后台算图分析完成 | 文件: {os.path.basename(self.file_path)} | 结论: {clean_text}")

        # 通过对讲机发射完成信号
        self.signals.sig_process_done.emit(self.file_path, output_image_path, analysis_text)


# ==========================================
# 🗄️ LIMS 级物理存储与检索中枢 (保持不变)
# ==========================================
class CalendarArchiveLogic:
    def __init__(self):
        self.data_file = os.path.join(os.getcwd(), "sciforge_eln_data.json")
        self.schedule_data = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.schedule_data = json.load(f)
            except: self.schedule_data = {}

    def save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.schedule_data, f, ensure_ascii=False, indent=4)
        except Exception as e: print(f"保存失败: {e}")

    def get_day_data(self, date_str):
        data = self.schedule_data.get(date_str, {})
        if not isinstance(data, dict): data = {"main": str(data)} 
        return {"todo": data.get("todo", []), "main": data.get("main", ""), "extra": data.get("extra", "")}

    def update_day_data(self, date_str, todo_list, main_text, extra_text):
        if date_str not in self.schedule_data or not isinstance(self.schedule_data[date_str], dict):
            self.schedule_data[date_str] = {}
        self.schedule_data[date_str]["todo"] = todo_list
        self.schedule_data[date_str]["main"] = main_text
        self.schedule_data[date_str]["extra"] = extra_text
        self.save_data()

    def archive_raw_file(self, source_path, project, date_str, exp_type, item_name, operator):
        archive_root = GlobalConfig.get("archive_root", os.path.join(os.getcwd(), "SciForge_Archive"))
        
        safe_proj = re.sub(r'[\\/*?:"<>|]', "", project).strip() if project else "未分类项目"
        safe_exp = re.sub(r'[\\/*?:"<>|]', "", exp_type).strip() if exp_type else "常规实验"
        safe_name = re.sub(r'[\\/*?:"<>|]', "", item_name).strip() if item_name else "未命名"
        safe_op = re.sub(r'[\\/*?:"<>|]', "", operator).strip() if operator else ""
        
        target_dir = os.path.join(archive_root, safe_proj, date_str, safe_exp, safe_name)
        os.makedirs(target_dir, exist_ok=True)
        
        ext = os.path.splitext(source_path)[1]
        
        name_parts = [date_str, safe_proj]
        if safe_name != "未命名": name_parts.append(safe_name)
        if safe_exp != "常规实验": name_parts.append(safe_exp)
        if safe_op: name_parts.append(safe_op)
        
        base_new_filename = "_".join(name_parts)
        new_filename = f"{base_new_filename}{ext}"
        dest_path = os.path.join(target_dir, new_filename)
        
        counter = 1
        while os.path.exists(dest_path):
            new_filename = f"{base_new_filename}({counter}){ext}"
            dest_path = os.path.join(target_dir, new_filename)
            counter += 1
            
        shutil.copy2(source_path, dest_path)
        logger.info(f"成功归档实验文件 | 课题: {safe_proj} | 实验: {safe_exp} | 名称: {safe_name} | 路径: {dest_path}")
        
        return target_dir, dest_path

    def export_report(self, start_date_str, end_date_str, save_path):
        sorted_dates = sorted(self.schedule_data.keys())
        valid_dates = [d for d in sorted_dates if start_date_str <= d <= end_date_str]
        
        html_content = f"""
        <html><head><meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; padding: 40px; background: #f4f5f7; color: #333; }}
            .container {{ max-width: 900px; margin: auto; background: white; padding: 30px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); border-radius: 8px; }}
            h1 {{ text-align: center; color: #0078D7; border-bottom: 2px solid #0078D7; padding-bottom: 10px; }}
            .day-card {{ border-left: 5px solid #0078D7; background: #fafafa; padding: 15px; margin-bottom: 20px; border-radius: 0 8px 8px 0; }}
            .day-title {{ font-size: 20px; font-weight: bold; color: #0078D7; margin-top: 0; }}
            .section-title {{ font-weight: bold; color: #555; margin-top: 15px; border-bottom: 1px solid #ddd; display: inline-block; }}
            .content {{ font-size: 14px; margin-top: 5px; line-height: 1.6; overflow-wrap: break-word; }}
            .content img {{ max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #ddd; }}
            .badge {{ display: inline-block; background: #e0f2fe; color: #0078d4; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-right: 5px; }}
        </style></head><body>
        <div class="container">
        <h1>SciForge 实验记录简报</h1>
        <p style="text-align:center; color:#666;">时间范围: {start_date_str} 至 {end_date_str}</p>
        """
        
        if not valid_dates:
            html_content += "<p style='text-align:center;'>该时间段内无记录。</p>"
        else:
            for d in valid_dates:
                data = self.get_day_data(d)
                if not data["todo"] and not data["main"]: continue
                
                clean_text = re.sub(r'<[^>]+>', '', data["main"])
                tags = re.findall(r'【(.*?)】', clean_text)
                tag_html = "".join([f"<span class='badge'>{t}</span>" for t in set(tags)])
                
                html_content += f"<div class='day-card'><p class='day-title'>📅 {d}</p>"
                if tag_html: html_content += f"<div style='margin-bottom:10px;'>包含实验: {tag_html}</div>"
                
                if data["main"]:
                    html_content += f"<div class='section-title'>📝 实验记录</div><div class='content'>{data['main']}</div>"
                html_content += "</div>"
                
        html_content += "</div></body></html>"
        
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(html_content)