import sys
import os
import json
import subprocess
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                             QMessageBox, QFrame, QFileDialog, QProgressBar, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, QSizePolicy)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QFont, QPixmap, QIcon, QDesktopServices
from pymobiledevice3 import usbmux
from pymobiledevice3.lockdown import create_using_usbmux

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_FILE_JSON = os.path.join(SCRIPT_DIR, "saved_cards.json")
LOCAL_CARD_FOLDER = os.path.join(SCRIPT_DIR, "Cards")
WORKER_SCRIPT = os.path.join(SCRIPT_DIR, "cli_worker.py")

HASH_PATTERN = re.compile(
    r'passIDs(?:\[global\])?.\s*\{\(\s*"([^"]+)"',
    re.IGNORECASE
)

# --- TỪ ĐIỂN NGÔN NGỮ (ĐÃ XÓA EMOJI & THÊM CREDITS) ---

LANGUAGES = {
    "VN": {
        "title": "QUẢN LÝ VÍ WALLET",
        "device_prefix": "Thiết bị:",
        "status_connected": "Đã kết nối",
        "status_disconnected": "Mất kết nối",
        "sec1_title": "1. QUẢN LÝ ID THẺ",
        "btn_scan": "BẮT ĐẦU DÒ TÌM ID",
        "btn_scan_wait": "Đang đợi thẻ...",
        "ph_id": "ID Thẻ (Dạng hash)...",
        "ph_name": "Đặt tên gợi nhớ...",
        "btn_save": "Lưu",
        "btn_del": "Xóa",
        "col_name": "Tên Thẻ",
        "col_id": "ID",
        "sec2_title": "2. HÌNH ẢNH & PREVIEW",
        "btn_img": "Chọn Ảnh Nền",
        "lbl_no_img": "Chưa chọn ảnh",
        "btn_run": "THỰC THI (INJECT)",
        "btn_info": "Thông tin",
        "btn_donate": "Donate",
        "ready": "Sẵn sàng",
        "msg_done": "Hoàn tất!",
        "msg_success": "Đã thay thế thẻ thành công!\nKiểm tra lại Wallet trên iPhone.",
        "err_no_card_folder": "Không tìm thấy thư mục Cards!",
        "err_no_connect": "Chưa kết nối thiết bị.",
        "confirm_del": "Bạn có chắc muốn xóa thẻ này?",
        "p_init": "Đang khởi tạo kết nối...",
        "p_img": "Đang thay thế Ảnh nền...",
        "p_front": "Đang cài đặt Mặt trước...",
        "p_holder": "Đang cài đặt Giữ chỗ...",
        "p_preview": "Đang cài đặt Xem trước...",
        "p_respring": "Đang khởi động lại (Respring)...",
        "p_done": "Xử lý hoàn tất!",
        "info_title": "Thông tin dự án",
        "uuid_title": "YÊU CẦU TẢI SÁCH",
        "uuid_msg": "Tool chưa tìm thấy UUID của ứng dụng Sách.\n\n👉 Vui lòng mở iPhone, vào ứng dụng 'Sách' (Books) và tải ngay 1 cuốn sách bất kỳ.\n\nSau khi tải xong, Tool sẽ tự động nhận diện và chạy tiếp.",
        # Credits Text
        "cred_dev": "Nhà Phát Triển",
        "cred_log": "Khai Thác Logs ID Wallet",
        "cred_sbx": "Khai Thác bl_sbx"
    },
    "EN": {
        "title": "WALLET MANAGER",
        "device_prefix": "Device:",
        "status_connected": "Connected",
        "status_disconnected": "Disconnected",
        "sec1_title": "1. CARD ID MANAGEMENT",
        "btn_scan": "SCAN CARD ID",
        "btn_scan_wait": "Waiting for card...",
        "ph_id": "Card ID (Hash)...",
        "ph_name": "Enter alias name...",
        "btn_save": "Save",
        "btn_del": "Del",
        "col_name": "Card Name",
        "col_id": "ID",
        "sec2_title": "2. IMAGE & PREVIEW",
        "btn_img": "Select Image",
        "lbl_no_img": "No image selected",
        "btn_run": "EXECUTE (INJECT)",
        "btn_info": "Info",
        "btn_donate": "Donate",
        "ready": "Ready",
        "msg_done": "Done!",
        "msg_success": "Success!\nPlease check your iPhone Wallet.",
        "err_no_card_folder": "Cards folder not found!",
        "err_no_connect": "Device not connected.",
        "confirm_del": "Are you sure you want to delete this?",
        "p_init": "Initializing connection...",
        "p_img": "Replacing Background...",
        "p_front": "Installing FrontFace...",
        "p_holder": "Installing PlaceHolder...",
        "p_preview": "Installing Preview...",
        "p_respring": "Respringing device...",
        "p_done": "Process Finished!",
        "info_title": "Project Info",
        "uuid_title": "BOOK DOWNLOAD REQUIRED",
        "uuid_msg": "Books UUID is missing.\n\n👉 Please open 'Books' app on iPhone and download any book right now.\n\nThe tool will auto-continue once detected.",
        # Credits Text
        "cred_dev": "Developer",
        "cred_log": "Wallet ID Logs Exploit",
        "cred_sbx": "bl_sbx Exploit"
    },
    "CN": {
        "title": "钱包卡片管理",
        "device_prefix": "设备:",
        "status_connected": "已连接",
        "status_disconnected": "未连接",
        "sec1_title": "1. 卡片 ID 管理",
        "btn_scan": "扫描 ID",
        "btn_scan_wait": "等待卡片...",
        "ph_id": "卡片 ID (哈希)...",
        "ph_name": "输入备注名称...",
        "btn_save": "保存",
        "btn_del": "删除",
        "col_name": "名称",
        "col_id": "ID",
        "sec2_title": "2. 图片 & 预览",
        "btn_img": "选择图片",
        "lbl_no_img": "未选择图片",
        "btn_run": "执行 (注入)",
        "btn_info": "信息",
        "btn_donate": "捐赠",
        "ready": "准备就绪",
        "msg_done": "完成!",
        "msg_success": "成功!\n请检查 iPhone 钱包。",
        "err_no_card_folder": "未找到 Cards 文件夹!",
        "err_no_connect": "设备未连接。",
        "confirm_del": "确定要删除吗？",
        "p_init": "正在初始化...",
        "p_img": "正在替换背景...",
        "p_front": "正在安装正面...",
        "p_holder": "正在安装占位符...",
        "p_preview": "正在安装预览...",
        "p_respring": "正在注销 (Respring)...",
        "p_done": "处理完成!",
        "info_title": "项目信息",
        "uuid_title": "需要下载书籍",
        "uuid_msg": "未找到 Books UUID。\n\n👉 请在 iPhone 上打开“图书”应用并立即下载一本书。\n\n检测到后工具将自动继续。",
        # Credits Text
        "cred_dev": "开发者",
        "cred_log": "Wallet ID 日志漏洞",
        "cred_sbx": "bl_sbx 漏洞"
    }
}

class InjectorProcess(QThread):
    progress_signal = pyqtSignal(str, int)
    error_signal = pyqtSignal(str)
    uuid_missing_signal = pyqtSignal()
    finished_signal = pyqtSignal()

    def __init__(self, udid, card_id, img_path, lang_code):
        super().__init__()
        self.udid = udid
        self.card_id = card_id
        self.img_path = img_path
        self.lang = LANGUAGES[lang_code]

    def run(self):
        cmd = [
            sys.executable, WORKER_SCRIPT,
            "--udid", self.udid,
            "--card_id", self.card_id,
            "--image", self.img_path
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()
            if "urllib3" in line or "warnings" in line or "Verify the connection" in line: continue
            
            if "GUI:UUID_MISSING" in line:
                self.uuid_missing_signal.emit()
                continue

            msg = ""
            pct = 0
            
            if "Starting Process" in line:
                msg = self.lang["p_init"]; pct = 10
            elif "cardBackgroundCombined" in line and "Processing" in line:
                msg = self.lang["p_img"]; pct = 25
            elif "FrontFace" in line and "Processing" in line:
                msg = self.lang["p_front"]; pct = 45
            elif "PlaceHolder" in line and "Processing" in line:
                msg = self.lang["p_holder"]; pct = 65
            elif "Preview" in line and "Processing" in line:
                msg = self.lang["p_preview"]; pct = 85
            elif "Respringing" in line:
                msg = self.lang["p_respring"]; pct = 95
            elif "All tasks finished" in line:
                msg = self.lang["p_done"]; pct = 100
            
            if msg:
                self.progress_signal.emit(msg, pct)
            
            if "[Err]" in line or "Exception" in line or "Error" in line:
                self.error_signal.emit(line)

        process.wait()
        self.finished_signal.emit()

class ScanWorker(QThread):
    found_signal = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.running = True
    def run(self):
        try:
            from pymobiledevice3.services.os_trace import OsTraceService
            lockdown = create_using_usbmux()
            for entry in OsTraceService(lockdown=lockdown).syslog():
                if not self.running: break
                if not entry.label: continue

                if entry.label.subsystem == "com.apple.nfc" and (match := HASH_PATTERN.search(entry.message)):
                    self.found_signal.emit(match.group(1))
                    break
                    
        except: pass
    def stop(self): self.running = False

class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iOS Wallet Manager Pro")
        self.setGeometry(100, 100, 750, 600)
        
        self.user_image_path = ""
        self.udid = ""
        self.current_lang = "VN"
        
        self.init_ui()
        self.apply_dark_theme()
        self.load_saved_data()
        self.retranslate_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connection)
        self.timer.start(2000)
        self.check_connection()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        top_frame = QFrame()
        top_frame.setObjectName("HeaderFrame")
        top_layout = QHBoxLayout(top_frame)
        
        self.lbl_title = QLabel("WALLET CUSTOMIZER")
        self.lbl_title.setObjectName("AppTitle")
        
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Tiếng Việt", "English", "中文"])
        self.combo_lang.setFixedWidth(100)
        self.combo_lang.currentIndexChanged.connect(self.change_language)
        
        self.lbl_status = QLabel("Disconnected")
        self.lbl_status.setObjectName("StatusDisconnected")
        self.lbl_dev_name = QLabel("--")
        
        info_layout = QVBoxLayout()
        info_layout.addWidget(self.lbl_status)
        info_layout.addWidget(self.lbl_dev_name)
        info_layout.setAlignment(Qt.AlignRight)

        top_layout.addWidget(self.lbl_title)
        top_layout.addWidget(self.combo_lang)
        top_layout.addStretch()
        top_layout.addLayout(info_layout)
        
        main_layout.addWidget(top_frame)

        content_layout = QHBoxLayout()
        
        left_frame = QFrame()
        left_frame.setObjectName("Card")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setSpacing(10)

        self.lbl_sec1 = QLabel("1. QUẢN LÝ ID THẺ")
        self.lbl_sec1.setObjectName("SectionTitle")
        left_layout.addWidget(self.lbl_sec1)

        self.btn_scan = QPushButton("BẮT ĐẦU DÒ TÌM ID")
        self.btn_scan.setObjectName("BtnPrimary")
        self.btn_scan.setEnabled(False)
        self.btn_scan.clicked.connect(self.toggle_scan)
        left_layout.addWidget(self.btn_scan)

        self.txt_id = QLineEdit()
        left_layout.addWidget(self.txt_id)

        mgmt_layout = QHBoxLayout()
        self.txt_name = QLineEdit()
        self.btn_save = QPushButton("Lưu")
        self.btn_save.setObjectName("BtnSave")
        self.btn_save.setFixedWidth(50)
        self.btn_save.clicked.connect(self.save_card)
        self.btn_del = QPushButton("Xóa")
        self.btn_del.setObjectName("BtnDelete")
        self.btn_del.setFixedWidth(50)
        self.btn_del.clicked.connect(self.delete_card)
        
        mgmt_layout.addWidget(self.txt_name)
        mgmt_layout.addWidget(self.btn_save)
        mgmt_layout.addWidget(self.btn_del)
        left_layout.addLayout(mgmt_layout)

        self.table = QTableWidget(0, 2)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellClicked.connect(self.on_table_click)
        left_layout.addWidget(self.table)
        
        right_frame = QFrame()
        right_frame.setObjectName("Card")
        right_layout = QVBoxLayout(right_frame)
        right_layout.setSpacing(10)

        self.lbl_sec2 = QLabel("2. HÌNH ẢNH & PREVIEW")
        self.lbl_sec2.setObjectName("SectionTitle")
        right_layout.addWidget(self.lbl_sec2)

        self.btn_img = QPushButton("Chọn Ảnh Nền")
        self.btn_img.setObjectName("BtnSecondary")
        self.btn_img.clicked.connect(self.choose_image)
        right_layout.addWidget(self.btn_img)

        self.lbl_preview = QLabel("Preview")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.lbl_preview.setStyleSheet("border: 2px dashed #444; border-radius: 8px; background-color: #222;")
        right_layout.addWidget(self.lbl_preview)
        
        self.lbl_img_path = QLabel("")
        self.lbl_img_path.setStyleSheet("color: gray; font-size: 10px;")
        self.lbl_img_path.setWordWrap(True)
        right_layout.addWidget(self.lbl_img_path)

        content_layout.addWidget(left_frame, 55)
        content_layout.addWidget(right_frame, 45)
        main_layout.addLayout(content_layout)

        bottom_frame = QFrame()
        bottom_frame.setObjectName("Card")
        bottom_layout = QVBoxLayout(bottom_frame)

        self.btn_run = QPushButton("THỰC THI (INJECT)")
        self.btn_run.setObjectName("BtnSuccess")
        self.btn_run.setFixedHeight(50)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.start_process)
        
        status_layout = QHBoxLayout()
        self.lbl_process_status = QLabel("")
        self.lbl_process_status.setStyleSheet("color: #0A84FF; font-weight: bold;")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar {border:0px; background:#333; height: 5px;} QProgressBar::chunk {background:#30D158;}")
        
        status_layout.addWidget(self.lbl_process_status)
        
        bottom_layout.addWidget(self.btn_run)
        bottom_layout.addLayout(status_layout)
        bottom_layout.addWidget(self.progress)

        main_layout.addWidget(bottom_frame)

        footer_layout = QHBoxLayout()
        self.btn_info = QPushButton("Thông tin")
        self.btn_info.setFlat(True)
        self.btn_info.setStyleSheet("color: #888; padding: 5px;")
        self.btn_info.setCursor(Qt.PointingHandCursor)
        self.btn_info.clicked.connect(self.show_credits)
        
        self.btn_donate = QPushButton("Donate")
        self.btn_donate.setFlat(True)
        self.btn_donate.setStyleSheet("color: #FF9F0A; padding: 5px; font-weight: bold;")
        self.btn_donate.setCursor(Qt.PointingHandCursor)
        self.btn_donate.clicked.connect(self.open_donate)

        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_info)
        footer_layout.addWidget(self.btn_donate)
        
        main_layout.addLayout(footer_layout)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #E0E0E0; font-family: 'Helvetica Neue', sans-serif; font-size: 13px; }
            #HeaderFrame { background-color: #1E1E1E; border-bottom: 1px solid #333; border-radius: 5px; }
            #AppTitle { font-size: 22px; font-weight: 900; color: #FFFFFF; letter-spacing: 1px; }
            #SectionTitle { color: #888; font-weight: bold; font-size: 11px; margin-bottom: 5px; }
            #Card { background-color: #1E1E1E; border-radius: 10px; border: 1px solid #333; }
            #StatusConnected { color: #30D158; font-weight: bold; }
            #StatusDisconnected { color: #FF453A; font-weight: bold; }
            QLineEdit { background-color: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 5px; color: white; padding: 8px; }
            QLineEdit:focus { border: 1px solid #0A84FF; }
            QPushButton { padding: 8px; border-radius: 6px; font-weight: bold; font-size: 12px; }
            #BtnPrimary { background-color: #0A84FF; color: white; border: none; }
            #BtnPrimary:hover { background-color: #0071E3; }
            #BtnPrimary:disabled { background-color: #333; color: #555; }
            #BtnSecondary { background-color: #3A3A3C; color: white; border: 1px solid #555; }
            #BtnSecondary:hover { background-color: #48484A; }
            #BtnSuccess { background-color: #30D158; color: white; border: none; font-size: 16px; }
            #BtnSuccess:hover { background-color: #28B148; }
            #BtnSuccess:disabled { background-color: #333; color: #555; }
            #BtnSave { background-color: #FF9F0A; color: black; }
            #BtnDelete { background-color: #FF453A; color: white; }
            QTableWidget { background-color: #121212; color: white; gridline-color: #333; border: 1px solid #333; border-radius: 5px; }
            QHeaderView::section { background-color: #2C2C2E; color: white; padding: 4px; border: none; font-weight: bold; }
            QTableWidget::item:selected { background-color: #0A84FF; }
            QComboBox { background-color: #2C2C2E; color: white; border: 1px solid #3A3A3C; border-radius: 5px; padding: 5px; }
        """)

    def open_donate(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/yangjiii/goal?g=1"))

    def change_language(self, index):
        if index == 0: self.current_lang = "VN"
        elif index == 1: self.current_lang = "EN"
        elif index == 2: self.current_lang = "CN"
        self.retranslate_ui()
        self.check_connection() 

    def retranslate_ui(self):
        text = LANGUAGES[self.current_lang]
        self.lbl_title.setText(text["title"])
        self.lbl_sec1.setText(text["sec1_title"])
        self.lbl_sec2.setText(text["sec2_title"])
        self.btn_scan.setText(text["btn_scan"])
        self.txt_id.setPlaceholderText(text["ph_id"])
        self.txt_name.setPlaceholderText(text["ph_name"])
        self.btn_save.setText(text["btn_save"])
        self.btn_del.setText(text["btn_del"])
        self.table.setHorizontalHeaderLabels([text["col_name"], text["col_id"]])
        self.btn_img.setText(text["btn_img"])
        if self.lbl_img_path.text() == "" or "Chưa" in self.lbl_img_path.text() or "No" in self.lbl_img_path.text() or "未" in self.lbl_img_path.text():
            self.lbl_img_path.setText(text["lbl_no_img"])
        self.btn_run.setText(text["btn_run"])
        self.btn_info.setText(text["btn_info"])
        self.btn_donate.setText(text["btn_donate"])
        if self.lbl_process_status.text() in ["Sẵn sàng", "Ready", "准备就绪"]:
            self.lbl_process_status.setText(text["ready"])

    def show_credits(self):
        text = LANGUAGES[self.current_lang]
        msg = QMessageBox(self)
        msg.setWindowTitle(text["info_title"])
        msg.setText(
            f"<b>PROJECT CREDITS</b><br><br>"
            f"<b>{text['cred_dev']}:</b> YangJiii <span style='color:#0A84FF'>@duongduong0908</span><br>"
            f"<b>{text['cred_log']}:</b> paragon <span style='color:#0A84FF'>@paragonarsi</span><br>"
            f"<b>{text['cred_sbx']}:</b> Duy Tran <span style='color:#0A84FF'>@khanhduytran0</span>"
        )
        msg.setStyleSheet("QLabel { color: white; } QMessageBox { background-color: #1E1E1E; }")
        msg.exec_()

    def check_connection(self):
        text = LANGUAGES[self.current_lang]
        try:
            devices = usbmux.list_devices()
            if not devices:
                raise Exception("No USB device")
            lockdown = create_using_usbmux()
            name = lockdown.get_value(key="DeviceName")
            ver = lockdown.get_value(key="ProductVersion")
            self.lbl_status.setText(text["status_connected"])
            self.lbl_status.setObjectName("StatusConnected")
            self.lbl_status.setStyleSheet("color: #30D158; font-weight: bold;")
            self.lbl_dev_name.setText(f"{text['device_prefix']} {name} | iOS {ver}")
            self.udid = lockdown.udid
            if "..." not in self.btn_scan.text():
                self.btn_scan.setEnabled(True)
        except:
            self.lbl_status.setText(text["status_disconnected"])
            self.lbl_status.setObjectName("StatusDisconnected")
            self.lbl_status.setStyleSheet("color: #FF453A; font-weight: bold;")
            self.lbl_dev_name.setText(f"{text['device_prefix']} --")
            self.btn_scan.setEnabled(False)
            self.udid = ""

    def update_progress(self, msg, val):
        self.lbl_process_status.setText(msg)
        self.progress.setValue(val)

    def on_missing_uuid(self):
        text = LANGUAGES[self.current_lang]
        QMessageBox.information(self, text["uuid_title"], text["uuid_msg"])

    def on_error(self, err_msg):
        self.lbl_process_status.setText("Error!")
        self.lbl_process_status.setStyleSheet("color: #FF453A;")
        QMessageBox.warning(self, "Error", err_msg)

    def on_finished(self):
        text = LANGUAGES[self.current_lang]
        self.btn_run.setEnabled(True)
        self.lbl_process_status.setText(text["msg_done"])
        self.lbl_process_status.setStyleSheet("color: #30D158; font-weight: bold;")
        QMessageBox.information(self, "OK", text["msg_success"])

    def load_saved_data(self):
        self.table.setRowCount(0)
        if os.path.exists(SAVED_FILE_JSON):
            try:
                with open(SAVED_FILE_JSON, 'r') as f:
                    data = json.load(f)
                    for row, (name, cid) in enumerate(data.items()):
                        self.table.insertRow(row)
                        self.table.setItem(row, 0, QTableWidgetItem(name))
                        self.table.setItem(row, 1, QTableWidgetItem(cid))
            except: pass

    def save_card(self):
        name = self.txt_name.text()
        cid = self.txt_id.text()
        if not name or not cid: return
        data = {}
        if os.path.exists(SAVED_FILE_JSON):
            try:
                with open(SAVED_FILE_JSON, 'r') as f:
                    data = json.load(f)
            except: pass
        data[name] = cid
        try:
            with open(SAVED_FILE_JSON, 'w') as f:
                json.dump(data, f, indent=4)
        except: pass
        self.txt_name.clear()
        self.load_saved_data()

    def delete_card(self):
        text = LANGUAGES[self.current_lang]
        row = self.table.currentRow()
        if row < 0: return
        name = self.table.item(row, 0).text()
        reply = QMessageBox.question(self, 'Confirm', f"{text['confirm_del']} '{name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            if os.path.exists(SAVED_FILE_JSON):
                try:
                    with open(SAVED_FILE_JSON, 'r') as f:
                        data = json.load(f)
                    if name in data: del data[name]
                    with open(SAVED_FILE_JSON, 'w') as f:
                        json.dump(data, f, indent=4)
                    self.load_saved_data()
                except: pass

    def on_table_click(self, row, col):
        cid = self.table.item(row, 1).text()
        self.txt_id.setText(cid)
        self.check_ready()

    def toggle_scan(self):
        text = LANGUAGES[self.current_lang]
        self.btn_scan.setText(text["btn_scan_wait"])
        self.btn_scan.setStyleSheet("background-color: #FF9F0A; color: black;")
        self.scan_worker = ScanWorker()
        self.scan_worker.found_signal.connect(self.on_id_found)
        self.scan_worker.start()

    def on_id_found(self, cid):
        self.scan_worker.stop()
        self.txt_id.setText(cid)
        self.retranslate_ui()
        self.btn_scan.setStyleSheet("background-color: #30D158; color: white;")
        self.check_ready()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Image", "", "Images (*.png *.jpg *.jpeg)")
        if path:
            self.user_image_path = path
            self.lbl_img_path.setText(os.path.basename(path))
            pixmap = QPixmap(path)
            self.lbl_preview.setPixmap(pixmap.scaled(self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.check_ready()

    def check_ready(self):
        if self.txt_id.text() and self.user_image_path:
            self.btn_run.setEnabled(True)

    def start_process(self):
        text = LANGUAGES[self.current_lang]
        if not os.path.exists(LOCAL_CARD_FOLDER):
            QMessageBox.critical(self, "Error", text["err_no_card_folder"])
            return
        self.btn_run.setEnabled(False)
        self.progress.setValue(0)
        self.lbl_process_status.setText(text["ready"])
        self.lbl_process_status.setStyleSheet("color: #0A84FF;")
        self.worker = InjectorProcess(self.udid, self.txt_id.text(), self.user_image_path, self.current_lang)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.error_signal.connect(self.on_error)
        self.worker.uuid_missing_signal.connect(self.on_missing_uuid)
        self.worker.finished_signal.connect(self.on_finished)
        self.worker.start()

if __name__ == "__main__":
    # if os.geteuid() != 0:
    #     os.execvp('sudo', ['sudo', 'python3'] + sys.argv)
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica Neue", 9))
    w = AppWindow()
    w.show()
    sys.exit(app.exec_())