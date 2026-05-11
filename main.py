# -*- coding: utf-8 -*-
"""
行程单提取工具 - GUI界面
功能：选择文件夹 → 处理文件 → 日志展示
界面：3个页面无缝切换，布局统一对齐，原生系统图标
"""
import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QStackedWidget, QDialog, QTextEdit, QStyle
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPainter, QColor, QPen, QFont

# 导入核心处理函数（业务逻辑模块）
try:
    from extract_taxi_receipts import extract_taxi_receipts
    SCRIPT_READY = True
except Exception as e:
    SCRIPT_READY = False

# ------------------------------
# 后台工作线程：处理文件，避免界面卡顿
# ------------------------------
class WorkerThread(QThread):
    # 自定义信号：日志输出 / 任务完成
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path  # 待处理的文件夹路径

    def run(self):
        """线程执行函数：调用处理逻辑"""
        if not SCRIPT_READY:
            self.log_signal.emit("❌ 未找到处理脚本")
            self.finished_signal.emit()
            return
        extract_taxi_receipts(self.folder_path, log_func=self.log_signal.emit)
        self.finished_signal.emit()

# ------------------------------
# 通用提示弹窗
# ------------------------------
class CustomWarningDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("提示")
        self.setFixedSize(300, 105)
        self.setStyleSheet("background-color: white;")
        # 弹窗布局
        main_layout = QHBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        # 警告图标
        icon_label = QLabel()
        icon = self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        icon_label.setPixmap(icon.pixmap(38, 38))
        # 提示文字
        text_label = QLabel(message)
        text_label.setFont(QFont("Arial", 16, QFont.Bold))
        # 组装布局
        main_layout.addWidget(icon_label)
        main_layout.addWidget(text_label)
        self.mousePressEvent = lambda e: self.close()

# ------------------------------
# 页面1：文件夹选择页面
# ------------------------------
class SelectFolderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #333333;")
        self.setup_ui()

    def setup_ui(self):
        """初始化选择文件夹界面"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(22)
        # 标题
        title = QLabel("行程单提取")
        title.setFont(QFont("Arial", 27, QFont.Bold))
        title.setStyleSheet("color:white;")
        title.setAlignment(Qt.AlignCenter)
        # 文件夹选择区域
        self.drop = DropCircleWidget()
        self.drop.folder_selected.connect(self.on_select)
        # 提示文字
        hint = QLabel("选择或拖拽文件夹")
        hint.setFont(QFont("Arial", 14))
        hint.setStyleSheet("color:#eeeeee;")
        hint.setAlignment(Qt.AlignCenter)
        # 组装布局
        layout.addWidget(title)
        layout.addWidget(self.drop, alignment=Qt.AlignCenter)
        layout.addWidget(hint)

    def on_select(self, path):
        """选择文件夹后，切换到页面2"""
        self.parent().parent().switch_to_process_page(path)

# ------------------------------
# 圆形文件夹选择控件
# ------------------------------
class DropCircleWidget(QLabel):
    folder_selected = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(270, 270)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color:white; border-radius:135px;")

    def paintEvent(self, e):
        """绘制圆形内部的加号图标"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(70, 70, 90), 5))
        p.drawLine(75, 135, 195, 135)
        p.drawLine(135, 70, 135, 195)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setStyleSheet("background-color:#e0e7ff; border-radius:135px;")

    def dragLeaveEvent(self, e):
        self.setStyleSheet("background-color:white; border-radius:135px;")

    def dropEvent(self, e):
        self.setStyleSheet("background-color:white; border-radius:135px;")
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.folder_selected.emit(path)

    def mousePressEvent(self, e):
        """点击选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self.folder_selected.emit(folder)

# ------------------------------
# 页面2：准备提取页面（基准布局）
# ------------------------------
class ProcessPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color:#333;")
        self.folder = ""
        self.setup_ui()

    def setup_ui(self):
        """初始化布局：左侧固定圆形图标，右侧功能按钮"""
        main = QHBoxLayout(self)
        main.setContentsMargins(60, 60, 60, 60)
        main.setSpacing(45)

        # ========== 左侧固定布局（与页面3完全统一，无偏移） ==========
        left = QWidget()
        left.setFixedWidth(200)
        ly = QVBoxLayout(left)
        ly.setContentsMargins(0,0,0,0)
        ly.setAlignment(Qt.AlignCenter)
        # 圆形背景
        c = QWidget()
        c.setFixedSize(200, 200)
        c.setStyleSheet("background-color:#4a4a5a; border-radius:100px;")
        cy = QVBoxLayout(c)
        cy.setContentsMargins(0,0,0,0)
        cy.setAlignment(Qt.AlignCenter)
        # 系统原生彩色文件夹图标
        ico = QLabel()
        ico.setAlignment(Qt.AlignCenter)
        folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        ico.setPixmap(folder_icon.pixmap(80, 80))
        # 文件夹名称标签
        self.name = QLabel()
        self.name.setFont(QFont("Arial", 14, QFont.Bold))
        self.name.setStyleSheet("color:white;")
        self.name.setAlignment(Qt.AlignCenter)
        # 组装左侧布局
        cy.addWidget(ico)
        cy.addWidget(self.name)
        ly.addWidget(c)
        main.addWidget(left)

        # ========== 右侧功能区 ==========
        right = QWidget()
        ry = QVBoxLayout(right)
        ry.setContentsMargins(0,0,0,0)
        ry.setAlignment(Qt.AlignCenter)
        ry.setSpacing(22)
        # 标题
        t = QLabel("准备提取行程单")
        t.setFont(QFont("Arial", 20, QFont.Bold))
        t.setStyleSheet("color:white;")
        t.setAlignment(Qt.AlignCenter)
        # 提示说明
        tip = QLabel("灰色：重选文件夹\n绿色：开始提取行程单")
        tip.setFont(QFont("Arial", 14))
        tip.setStyleSheet("color:#ddd;")
        tip.setAlignment(Qt.AlignLeft)
        # 按钮组
        btnl = QHBoxLayout()
        btnl.setSpacing(22)
        back = QPushButton("重选文件夹")
        back.setFont(QFont("Arial", 13, QFont.Bold))
        back.setFixedSize(110, 32)
        back.setStyleSheet("""QPushButton{background:#404040;color:white;border-radius:8px;}QPushButton:hover{background:#505050;}""")
        back.clicked.connect(self.go_back)
        go = QPushButton("提取行程单")
        go.setFont(QFont("Arial", 13, QFont.Bold))
        go.setFixedSize(110, 32)
        go.setStyleSheet("""QPushButton{background:#a5e9cb;color:#222;border-radius:8px;}QPushButton:hover{background:#8bdbb6;}""")
        go.clicked.connect(self.start_extract)
        btnl.addWidget(back)
        btnl.addWidget(go)
        # 组装右侧布局
        ry.addWidget(t)
        ry.addWidget(tip)
        ry.addLayout(btnl)
        main.addWidget(right)

    def set_folder(self, p):
        """设置文件夹路径，并显示文件夹名称"""
        self.folder = p
        self.name.setText(os.path.basename(p.rstrip(os.sep)))

    def go_back(self):
        """返回文件夹选择页面"""
        self.parent().parent().switch_to_select_page()

    def start_extract(self):
        """开始处理，切换到页面3"""
        self.parent().parent().page3.start_task(self.folder)

# ------------------------------
# 页面3：文件处理中页面（布局与页面2完全对齐）
# ------------------------------
class ProcessingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color:#333;")
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        """初始化：左侧与页面2完全一致，右侧日志+按钮居中"""
        main = QHBoxLayout(self)
        main.setContentsMargins(60, 60, 60, 60)
        main.setSpacing(45)

        # ========== 左侧：1:1复刻页面2，绝对无偏移 ==========
        left = QWidget()
        left.setFixedWidth(200)
        ly = QVBoxLayout(left)
        ly.setContentsMargins(0,0,0,0)
        ly.setAlignment(Qt.AlignCenter)
        # 圆形背景
        c = QWidget()
        c.setFixedSize(200, 200)
        c.setStyleSheet("background-color:#4a4a5a; border-radius:100px;")
        cy = QVBoxLayout(c)
        cy.setContentsMargins(0,0,0,0)
        cy.setAlignment(Qt.AlignCenter)
        # 原生彩色文件夹图标
        ico = QLabel()
        ico.setAlignment(Qt.AlignCenter)
        folder_icon = self.style().standardIcon(QStyle.SP_DirIcon)
        ico.setPixmap(folder_icon.pixmap(80, 80))
        # 文件夹名称
        self.name = QLabel()
        self.name.setFont(QFont("Arial", 14, QFont.Bold))
        self.name.setStyleSheet("color:white;")
        self.name.setAlignment(Qt.AlignCenter)
        # 组装左侧
        cy.addWidget(ico)
        cy.addWidget(self.name)
        ly.addWidget(c)
        main.addWidget(left)

        # ========== 右侧：日志框+按钮，居中对齐，无滚动条 ==========
        right = QWidget()
        ry = QVBoxLayout(right)
        ry.setContentsMargins(0,0,0,0)
        ry.setAlignment(Qt.AlignCenter)
        ry.setSpacing(18)
        # 标题
        t = QLabel("正在处理行程单")
        t.setFont(QFont("Arial", 20, QFont.Bold))
        t.setStyleSheet("color:white;")
        t.setAlignment(Qt.AlignCenter)
        # 日志框（核心：禁用所有滚动条，只读模式）
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedSize(280, 120)
        self.log_box.setFont(QFont("Arial", 13))
        # 隐藏滚动条
        self.log_box.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_box.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.log_box.setStyleSheet("""QTextEdit{background:#4a4a5a;color:white;border-radius:8px;padding:12px;}""")
        # 停止按钮
        self.btn = QPushButton("停止")
        self.btn.setFont(QFont("Arial", 13, QFont.Bold))
        self.btn.setFixedSize(110, 32)
        self.btn.setStyleSheet("""QPushButton{background:#505050;color:white;border-radius:8px;}QPushButton:hover{background:#606060;}""")
        self.btn.clicked.connect(self.stop_task)
        # 组装右侧
        ry.addWidget(t)
        ry.addWidget(self.log_box, alignment=Qt.AlignCenter)
        ry.addWidget(self.btn, alignment=Qt.AlignCenter)
        main.addWidget(right)

    def set_folder(self, p):
        """同步显示文件夹名称"""
        self.name.setText(os.path.basename(p.rstrip(os.sep)))

    def start_task(self, folder_path):
        """启动后台处理线程"""
        self.parent().parent().switch_to_processing_page()
        self.set_folder(folder_path)
        self.log_box.clear()
        # 创建并启动线程
        self.worker = WorkerThread(folder_path)
        self.worker.log_signal.connect(self.log_box.append)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

    def stop_task(self):
        """终止处理线程"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.log_box.append("\n⏹️ 已停止")
        self.parent().parent().switch_to_process_page()

    def on_finished(self):
        """处理完成，按钮变为退出"""
        self.btn.setText("退出")
        self.btn.clicked.disconnect()
        self.btn.clicked.connect(QApplication.quit)

# ------------------------------
# 主窗口：管理3个页面的切换
# ------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("行程单提取")
        self.setFixedSize(750, 488)
        # 页面堆叠容器
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        # 初始化3个页面
        self.page1 = SelectFolderPage()
        self.page2 = ProcessPage()
        self.page3 = ProcessingPage()
        # 添加页面到堆叠布局
        self.stack.addWidget(self.page1)
        self.stack.addWidget(self.page2)
        self.stack.addWidget(self.page3)

    def switch_to_process_page(self, path=None):
        """切换到页面2：准备处理"""
        if path: self.page2.set_folder(path)
        self.stack.setCurrentIndex(1)
        
    def switch_to_select_page(self):
        """切换到页面1：选择文件夹"""
        self.stack.setCurrentIndex(0)
        
    def switch_to_processing_page(self):
        """切换到页面3：处理中"""
        self.stack.setCurrentIndex(2)

# ------------------------------
# 程序入口
# ------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())