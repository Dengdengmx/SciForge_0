# core/signals.py
from PyQt5.QtCore import QObject, pyqtSignal

class GlobalEventBus(QObject):
    send_file_to_plot = pyqtSignal(str, str)  # 跨模块下发文件
    send_file_to_eln = pyqtSignal(str)
    switch_main_tab = pyqtSignal(str)
    jump_to_sample = pyqtSignal(str, str)
global_bus = GlobalEventBus()