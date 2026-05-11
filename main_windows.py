# -*- coding: utf-8 -*-
"""
Windows 专用版本 - 行程单提取工具
底板 #888888 较深灰 + 白色标题 + 固定版面
"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QStackedWidget, QDialog, QTextEdit, QStyle
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

# 导入业务处理脚本
try:
    from extract_taxi_receipts import extract_taxi_receipts
    SCRIPT_READY = True
except Exception as e:
    SCRIPT_READY = False

# ===================== 全局样式：底板 #888888 较深灰 =====================
WIN_GLOBAL_STYLE = """
QMainWindow{
    background-color: #888888;
}
QWidget{
    background-color: #888888;
}
QLabel{
    font-family: Segoe UI, SimSun, Arial;
}
/* 按钮字体 22号 */
QPushButton{
    font-family: Segoe UI, SimSun, Arial;
    background-color: #E5E7EB;
    border: none;
    border-radius: 12px;
    font-size: 22px;
    padding: 12px 24px;
}
QPushButton:hover{
    background-color: #D1D5DB;
}
QPushButton#btn_primary{
    background-color: #A5E9CB;
    color: #1F2937;
}
QPushButton#btn_primary:hover{
    background-color: #8BDBB6;
}
/* 日志框字体 21号 */
QTextEdit{
    background-color: #4B5563;
    color: #FFFFFF;
    border-radius: 12px;
    border: none;
    padding: 20px;
    font-family: Segoe UI, Arial;
    font-size: 21px;
}
"""

# ===================== 后台工作线程 =====================
class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path

    def run(self):
        if not SCRIPT_READY:
            self.log_signal.emit("❌ 未找到处理脚本")
            self.finished_signal.emit()
            return
        extract_taxi_receipts(self.folder_path, log_func=self.log_signal.emit)
        self.finished_signal.emit()

# ===================== 提示弹窗 =====================
class CustomWarningDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提示")
        self.setFixedSize(400, 150)
        self.setStyleSheet("background-color:#FFFFFF;border-radius:12px;")
        main_layout = QHBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        icon_label = QLabel()
        icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        icon_label.setPixmap(icon.pixmap(50, 50))
        text_label = QLabel(message)
        text_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        main_layout.addWidget(icon_label)
        main_layout.addWidget(text_label)
        self.mousePressEvent = lambda e: self.close()

# ===================== 页面1：选择文件夹 =====================
class SelectFolderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(45)
        layout.setContentsMargins(150, 100, 150, 100)

        # 白色标题
        title = QLabel("行程单提取工具")
        title.setFont(QFont("Segoe UI", 36, QFont.Bold))
        title.setStyleSheet("color:#FFFFFF;")
        title.setAlignment(Qt.AlignCenter)

        self.drop = DropCircleWidget()
        self.drop.folder_selected.connect(self.on_select)

        hint = QLabel("点击或拖拽选择PDF文件夹")
        hint.setFont(QFont("Segoe UI", 22))
        hint.setStyleSheet("color:#EEEEEE;")
        hint.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(self.drop, alignment=Qt.AlignCenter)
        layout.addWidget(hint)

    def on_select(self, path):
        self.parent().parent().switch_to_process_page(path)

# ===================== 圆形拖拽选择控件 =====================
class DropCircleWidget(QLabel):
    folder_selected = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(400, 400)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color:#FFFFFF;border-radius:200px;border:2px dashed #D1D5DB;")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(75, 85, 99), 8))
        p.drawLine(125, 200, 275, 200)
        p.drawLine(200, 125, 200, 275)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet("background-color:#EFF6FF;border-radius:200px;border:2px dashed #3B82F6;")

    def dragLeaveEvent(self, e):
        self.setStyleSheet("background-color:#FFFFFF;border-radius:200px;border:2px dashed #D1D5DB;")

    def dropEvent(self, e):
        self.setStyleSheet("background-color:#FFFFFF;border-radius:200px;border:2px dashed #D1D5DB;")
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.folder_selected.emit(path)

    def mousePressEvent(self, e):
        folder = QFileDialog.getExistingDirectory(self, "选择存放PDF的文件夹")
        if folder:
            self.folder_selected.emit(folder)

# ===================== 页面2：准备提取 =====================
class ProcessPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.folder = ""
        self.setup_ui()

    def setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(150, 100, 150, 100)
        main.setSpacing(80)

        # 左侧固定图标区域
        left = QWidget()
        left.setFixedWidth(320)
        ly = QVBoxLayout(left)
        ly.setContentsMargins(0,0,0,0)
        ly.setAlignment(Qt.AlignCenter)

        circle_bg = QWidget()
        circle_bg.setFixedSize(320, 320)
        circle_bg.setStyleSheet("background-color:#4B5563;border-radius:160px;")
        cy = QVBoxLayout(circle_bg)
        cy.setContentsMargins(0,0,0,0)
        cy.setAlignment(Qt.AlignCenter)

        ico = QLabel()
        ico.setAlignment(Qt.AlignCenter)
        folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        ico.setPixmap(folder_icon.pixmap(130, 130))

        self.name_label = QLabel()
        self.name_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self.name_label.setStyleSheet("color:#FFFFFF;")
        self.name_label.setAlignment(Qt.AlignCenter)

        cy.addWidget(ico)
        cy.addWidget(self.name_label)
        ly.addWidget(circle_bg)
        main.addWidget(left)

        # 右侧功能区
        right = QWidget()
        ry = QVBoxLayout(right)
        ry.setContentsMargins(0,0,0,0)
        ry.setAlignment(Qt.AlignCenter)
        ry.setSpacing(45)

        # 白色标题
        title = QLabel("准备提取行程单")
        title.setFont(QFont("Segoe UI", 30, QFont.Bold))
        title.setStyleSheet("color:#FFFFFF;")
        title.setAlignment(Qt.AlignCenter)

        # 固定提示文字
        tip = QLabel("灰色：重选文件夹\n绿色：开始提取行程单")
        tip.setFont(QFont("Segoe UI", 18))
        tip.setStyleSheet("color:#EEEEEE;")
        tip.setAlignment(Qt.AlignLeft)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(35)

        btn_back = QPushButton("重选文件夹")
        btn_back.setFixedSize(190, 60)
        btn_back.clicked.connect(self.go_back)

        btn_start = QPushButton("开始提取")
        btn_start.setObjectName("btn_primary")
        btn_start.setFixedSize(190, 60)
        btn_start.clicked.connect(self.start_extract)

        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(btn_start)

        ry.addWidget(title)
        ry.addWidget(tip)
        ry.addLayout(btn_layout)
        main.addWidget(right)

    def set_folder(self, path):
        self.folder = path
        self.name_label.setText(os.path.basename(path.rstrip(os.sep)))

    def go_back(self):
        self.parent().parent().switch_to_select_page()

    def start_extract(self):
        self.parent().parent().page3.start_task(self.folder)

# ===================== 页面3：处理中 =====================
class ProcessingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(150, 100, 150, 100)
        main.setSpacing(80)

        # 左侧 和 页面2 完全一模一样对齐
        left = QWidget()
        left.setFixedWidth(320)
        ly = QVBoxLayout(left)
        ly.setContentsMargins(0,0,0,0)
        ly.setAlignment(Qt.AlignCenter)

        circle_bg = QWidget()
        circle_bg.setFixedSize(320, 320)
        circle_bg.setStyleSheet("background-color:#4B5563;border-radius:160px;")
        cy = QVBoxLayout(circle_bg)
        cy.setContentsMargins(0,0,0,0)
        cy.setAlignment(Qt.AlignCenter)

        ico = QLabel()
        ico.setAlignment(Qt.AlignCenter)
        folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        ico.setPixmap(folder_icon.pixmap(130, 130))

        self.name_label = QLabel()
        self.name_label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self.name_label.setStyleSheet("color:#FFFFFF;")
        self.name_label.setAlignment(Qt.AlignCenter)

        cy.addWidget(ico)
        cy.addWidget(self.name_label)
        ly.addWidget(circle_bg)
        main.addWidget(left)

        # 右侧日志区域
        right = QWidget()
        ry = QVBoxLayout(right)
        ry.setContentsMargins(0,0,0,0)
        ry.setAlignment(Qt.AlignCenter)
        ry.setSpacing(35)

        # 白色标题
        title = QLabel("正在处理行程单")
        title.setFont(QFont("Segoe UI", 30, QFont.Bold))
        title.setStyleSheet("color:#FFFFFF;")
        title.setAlignment(Qt.AlignCenter)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedSize(500, 260)
        self.log_box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.btn_ctrl = QPushButton("停止")
        self.btn_ctrl.setFixedSize(190, 60)
        self.btn_ctrl.clicked.connect(self.stop_task)

        ry.addWidget(title)
        ry.addWidget(self.log_box, alignment=Qt.AlignCenter)
        ry.addWidget(self.btn_ctrl, alignment=Qt.AlignCenter)
        main.addWidget(right)

    def set_folder(self, path):
        self.name_label.setText(os.path.basename(path.rstrip(os.sep)))

    def start_task(self, folder_path):
        self.parent().parent().switch_to_processing_page()
        self.set_folder(folder_path)
        self.log_box.clear()
        self.worker = WorkerThread(folder_path)
        self.worker.log_signal.connect(self.log_box.append)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_task(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.log_box.append("\n⏹️ 已手动停止处理")
        self.parent().parent().switch_to_process_page()

    def on_finished(self):
        self.btn_ctrl.setText("退出程序")
        self.btn_ctrl.clicked.disconnect()
        self.btn_ctrl.clicked.connect(QApplication.quit)

# ===================== 主窗口 =====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("行程单PDF提取工具 Windows版")
        self.setFixedSize(1300, 870)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.page1 = SelectFolderPage()
        self.page2 = ProcessPage()
        self.page3 = ProcessingPage()

        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

    def switch_to_process_page(self, path=None):
        if path:
            self.page2.set_folder(path)
        self.stack.setCurrentIndex(1)

    def switch_to_select_page(self):
        self.stack.setCurrentIndex(0)

    def switch_to_processing_page(self):
        self.stack.setCurrentIndex(2)

# ===================== 程序入口 =====================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(WIN_GLOBAL_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())