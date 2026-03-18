# controllers/ctrl_data_hub.py
import os
import time
import platform
import subprocess

class DataHubLogic:
    """纯大脑：负责磁盘扫描、深度数据提取和系统级调用"""
    
    def get_file_meta(self, file_path):
        if not os.path.exists(file_path): return 0, "未知"
        stats = os.stat(file_path)
        size_kb = stats.st_size / 1024
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats.st_mtime))
        return size_kb, mtime

    def get_deep_meta(self, file_path, ext):
        """【新功能】深度探测科研数据文件的内部信息"""
        try:
            if ext in ['.fasta', '.seq']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    count = sum(1 for line in f if line.startswith('>'))
                return f"  |  序列数: {count} 条"
            elif ext in ['.pdb', '.cif']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # 快速统计 PDB 中的 ATOM 行数
                    count = sum(1 for line in f if line.startswith('ATOM'))
                return f"  |  原子数: {count} 个"
        except Exception:
            pass
        return "" # 如果不是这俩格式，或者读取失败，就返回空

    def open_in_explorer(self, file_path):
        """【新功能】调用系统底层接口，在资源管理器中定位文件"""
        if not os.path.exists(file_path): return
        if platform.system() == "Windows":
            # Windows 下高亮选中该文件
            subprocess.Popen(f'explorer /select,"{os.path.normpath(file_path)}"')
        elif platform.system() == "Darwin": # macOS
            subprocess.Popen(['open', '-R', file_path])
        else: # Linux
            subprocess.Popen(['xdg-open', os.path.dirname(file_path)])

    def read_text_content(self, file_path):
        try:
            if os.stat(file_path).st_size < 2 * 2048 * 2048: 
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read(8000)
            return "文件过大，已中止文本预览。"
        except Exception as e:
            return f"读取失败，可能并非纯文本文件。\n{str(e)}"
            
    def read_doc_pdf_content(self, file_path, ext):
        """【新功能】极速抽取 Word 和 PDF 的纯文本内容用于预览"""
        try:
            if ext in ['.docx', '.doc']:
                import docx
                doc = docx.Document(file_path)
                content = '\n'.join([para.text for para in doc.paragraphs])
                if not content.strip(): return "【此 Word 文档似乎没有可提取的文本内容或包含大量图片】"
                return content
                
            elif ext == '.pdf':
                import fitz  # PyMuPDF 库
                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                if not text.strip(): return "【此 PDF 可能是扫描件或纯图片组合，未能提取到文本】"
                return text
                
        except ImportError as e:
            if 'fitz' in str(e): return "⚠️ 预览 PDF 需要安装 PyMuPDF 库。\n请在终端运行: pip install PyMuPDF"
            if 'docx' in str(e): return "⚠️ 预览 Word 需要安装 python-docx 库。\n请在终端运行: pip install python-docx"
            return f"缺少运行库: {str(e)}"
        except Exception as e:
            return f"读取文档失败:\n{str(e)}"
            
    def open_system_default(self, file_path):
        """【新增】使用系统默认程序打开文件"""
        if not os.path.exists(file_path): return
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(['open', file_path])
            else:
                subprocess.Popen(['xdg-open', file_path])
        except Exception as e:
            print(f"打开文件失败: {e}")

    def rename_file(self, old_path, new_name):
        """【新增】重命名物理文件"""
        try:
            dir_name = os.path.dirname(old_path)
            new_path = os.path.join(dir_name, new_name)
            if os.path.exists(new_path) and new_path.lower() != old_path.lower():
                return False, "同名文件已存在！"
            os.rename(old_path, new_path)
            return True, new_path
        except Exception as e:
            return False, str(e)

    def delete_file(self, file_path):
        """【新增】永久删除物理文件"""
        try:
            os.remove(file_path)
            return True, ""
        except Exception as e:
            return False, str(e)

    def move_files(self, filepaths, target_dir):
        """【神级交互】物理移动文件，自动处理同名冲突"""
        import shutil
        results = []
        if not os.path.exists(target_dir): return False, "目标目录不存在"
        
        try:
            for src in filepaths:
                if not os.path.exists(src): continue
                if os.path.dirname(src) == target_dir: continue # 如果拖到了原来的文件夹，忽略
                
                filename = os.path.basename(src)
                dest = os.path.join(target_dir, filename)
                
                # 智能防冲突：加 (1), (2)
                counter = 1
                base_name, ext = os.path.splitext(filename)
                while os.path.exists(dest):
                    dest = os.path.join(target_dir, f"{base_name}({counter}){ext}")
                    counter += 1
                    
                shutil.move(src, dest)
                results.append(dest)
            return True, f"成功转移 {len(results)} 个文件。"
        except Exception as e:
            return False, f"物理移动失败: {str(e)}"