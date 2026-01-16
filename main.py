import sys
import os
import re
import json
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                             QMessageBox, QFrame, QFileDialog, QProgressBar, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QPixmap, QIcon
from pymobiledevice3.lockdown import create_using_usbmux

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_FILE_JSON = os.path.join(SCRIPT_DIR, "saved_cards.json")
LANG_FILE_JSON = os.path.join(SCRIPT_DIR, "languages.json")
WORKER_SCRIPT = os.path.join(SCRIPT_DIR, "cli_worker.py")
ASSETS_DIR = os.path.join(SCRIPT_DIR, "card_assets")

if not os.path.exists(ASSETS_DIR): 
    os.makedirs(ASSETS_DIR)

# --- THREAD DE TRAVAIL ---
class InjectorProcess(QThread):
    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal()

    def __init__(self, udid, card_id, img_path):
        super().__init__()
        self.udid, self.card_id, self.img_path = udid, card_id, img_path

    def run(self):
        try:
            cmd = [sys.executable, WORKER_SCRIPT, f"--udid={self.udid}", f"--card_id={self.card_id}", f"--image={self.img_path}"]
            # bufsize=1 est crucial pour la lecture en temps réel sous Linux
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            
            for line in process.stdout:
                line = line.strip()
                if not line: continue
                
                # Mise à jour de la barre basée sur la sortie console du worker
                if "Starting Process" in line:
                    self.progress_signal.emit("Initializing...", 10)
                elif "cardBackgroundCombined" in line:
                    self.progress_signal.emit("Replacing Background...", 30)
                elif "FrontFace" in line:
                    self.progress_signal.emit("Installing FrontFace...", 50)
                elif "PlaceHolder" in line:
                    self.progress_signal.emit("Installing Placeholder...", 75)
                elif "Preview" in line:
                    self.progress_signal.emit("Installing Preview...", 90)
                elif "All tasks finished" in line or "Success!" in line:
                    self.progress_signal.emit("Success!", 100)

            process.wait()
        except Exception as e:
            print(f"Error: {e}")
        
        self.finished_signal.emit()

class ScanWorker(QThread):
    found_signal = pyqtSignal(str)
    def run(self):
        try:
            from pymobiledevice3.services.os_trace import OsTraceService
            lockdown = create_using_usbmux()
            if not lockdown: return
            for entry in OsTraceService(lockdown=lockdown).syslog():
                match = re.search(r'passIDs(?:\[global\])?.\s*\{\(\s*"([^"]+)"', entry.message, re.I)
                if match: self.found_signal.emit(match.group(1)); break
                if '/var/mobile/Library/Passes/Cards/' in entry.message:
                    res = entry.message.split('/var/mobile/Library/Passes/Cards/')[1].split('.pkpass')[0]
                    self.found_signal.emit(res); break
        except: pass

# --- FENÊTRE PRINCIPALE ---
class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iOS Wallet Manager Pro")
        self.setGeometry(100, 100, 950, 720)
        self.user_image_path, self.udid = "", ""
        
        # Charger les langues
        try:
            with open(LANG_FILE_JSON, 'r', encoding='utf-8') as f:
                self.translations = json.load(f)
        except:
            self.translations = {"EN": {"display_name": "English", "title": "Error"}}

        self.current_lang = "FR" if "FR" in self.translations else list(self.translations.keys())[0]

        self.init_ui()
        self.apply_dark_theme()
        self.load_saved_data()
        self.load_assets()
        self.retranslate_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connection)
        self.timer.start(3000)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1C1C1E; color: #FFFFFF; font-family: 'Segoe UI', sans-serif; }
            #HeaderFrame { background-color: #2C2C2E; border-bottom: 2px solid #3A3A3C; padding: 10px; }
            #AppTitle { font-size: 24px; font-weight: bold; color: #0A84FF; background-color: transparent; }
            #CardContainer { background-color: #2C2C2E; border-radius: 12px; border: 1px solid #3A3A3C; padding: 12px; }
            #SectionTitle { color: #8E8E93; font-weight: bold; font-size: 11px; text-transform: uppercase; background-color: transparent; }
            QLineEdit, QListWidget, QTableWidget { background-color: #3A3A3C; border: 1px solid #48484A; border-radius: 8px; color: white; padding: 8px; }
            QComboBox { background-color: #3A3A3C; border: 1px solid #48484A; border-radius: 6px; padding: 5px 15px; color: white; }
            QComboBox QAbstractItemView { background-color: #2C2C2E; color: white; selection-background-color: #0A84FF; outline: none; }
            QPushButton { font-weight: bold; padding: 10px; border-radius: 8px; border: none; font-size: 13px; }
            #BtnPrimary { background-color: #0A84FF; color: white; }
            #BtnSecondary { background-color: #3A3A3C; color: white; }
            #BtnSuccess { background-color: #30D158; color: white; font-size: 16px; }
            #BtnSuccess:disabled { background-color: #2C2C2E; color: #48484A; border: 1px solid #3A3A3C; }
            #BtnSave { background-color: #FF9F0A; color: black; }
            #BtnDelete { background-color: #FF453A; color: white; }
            #PreviewArea { border: 2px dashed #48484A; border-radius: 15px; background-color: #1C1C1E; }
            QProgressBar { border: none; background-color: #3A3A3C; height: 12px; border-radius: 6px; text-align: center; color: white; font-weight: bold; }
            QProgressBar::chunk { background-color: #30D158; border-radius: 6px; }
        """)

    def init_ui(self):
        mw = QWidget(); self.setCentralWidget(mw); ml = QVBoxLayout(mw)
        tf = QFrame(); tf.setObjectName("HeaderFrame"); tl = QHBoxLayout(tf)
        self.lbl_title = QLabel(); self.lbl_title.setObjectName("AppTitle")
        self.combo_lang = QComboBox()
        for code, data in self.translations.items():
            self.combo_lang.addItem(data.get("display_name", code), code)
        self.combo_lang.currentIndexChanged.connect(self.change_lang)
        self.lbl_status = QLabel(); self.lbl_dev_name = QLabel()
        tl.addWidget(self.lbl_title); tl.addWidget(self.combo_lang); tl.addStretch()
        il = QVBoxLayout(); il.addWidget(self.lbl_status); il.addWidget(self.lbl_dev_name); tl.addLayout(il)
        ml.addWidget(tf)

        cl = QHBoxLayout()
        lf = QFrame(); lf.setObjectName("CardContainer"); ll = QVBoxLayout(lf)
        self.lbl_sec1 = QLabel(); self.lbl_sec1.setObjectName("SectionTitle"); ll.addWidget(self.lbl_sec1)
        self.btn_scan = QPushButton(); self.btn_scan.setObjectName("BtnPrimary"); self.btn_scan.clicked.connect(self.toggle_scan)
        ll.addWidget(self.btn_scan); self.txt_id = QLineEdit(); ll.addWidget(self.txt_id)
        mgmt = QHBoxLayout(); self.txt_name = QLineEdit(); self.btn_save = QPushButton(); self.btn_save.setObjectName("BtnSave")
        self.btn_save.clicked.connect(self.save_card); self.btn_del = QPushButton(); self.btn_del.setObjectName("BtnDelete")
        self.btn_del.clicked.connect(self.delete_card); mgmt.addWidget(self.txt_name); mgmt.addWidget(self.btn_save); mgmt.addWidget(self.btn_del); ll.addLayout(mgmt)
        self.table = QTableWidget(0, 2); self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.cellClicked.connect(self.on_table_click); ll.addWidget(self.table)
        cl.addWidget(lf, 45)

        rf = QFrame(); rf.setObjectName("CardContainer"); rl = QVBoxLayout(rf)
        self.lbl_sec2 = QLabel(); self.lbl_sec2.setObjectName("SectionTitle"); rl.addWidget(self.lbl_sec2)
        self.asset_list = QListWidget(); self.asset_list.setIconSize(QSize(60, 40)); self.asset_list.itemClicked.connect(self.on_asset_clicked); rl.addWidget(self.asset_list)
        self.btn_img = QPushButton(); self.btn_img.setObjectName("BtnSecondary"); self.btn_img.clicked.connect(self.choose_image); rl.addWidget(self.btn_img)
        self.lbl_preview = QLabel("PREVIEW"); self.lbl_preview.setObjectName("PreviewArea"); self.lbl_preview.setAlignment(Qt.AlignCenter); self.lbl_preview.setMinimumSize(250, 160)
        rl.addWidget(self.lbl_preview); cl.addWidget(rf, 55); ml.addLayout(cl)

        bf = QFrame(); bf.setObjectName("CardContainer"); bl = QVBoxLayout(bf)
        self.btn_run = QPushButton(); self.btn_run.setObjectName("BtnSuccess"); self.btn_run.setFixedHeight(60); self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.start_process)
        self.lbl_p_stat = QLabel(""); self.lbl_p_stat.setAlignment(Qt.AlignCenter)
        self.progress = QProgressBar(); self.progress.setTextVisible(False)
        bl.addWidget(self.btn_run); bl.addWidget(self.lbl_p_stat); bl.addWidget(self.progress); ml.addWidget(bf)

    def change_lang(self, index):
        self.current_lang = self.combo_lang.itemData(index)
        self.retranslate_ui()

    def retranslate_ui(self):
        t = self.translations.get(self.current_lang, {})
        self.lbl_title.setText(t.get("title", ""))
        self.lbl_sec1.setText(t.get("sec1_title", ""))
        self.lbl_sec2.setText(t.get("sec2_title", ""))
        self.btn_scan.setText(t.get("btn_scan", ""))
        self.btn_img.setText(t.get("btn_img", ""))
        self.btn_run.setText(t.get("btn_run", ""))
        self.btn_save.setText(t.get("btn_save", ""))
        self.btn_del.setText(t.get("btn_del", ""))
        self.table.setHorizontalHeaderLabels([t.get("col_name", ""), t.get("col_id", "")])
        self.txt_id.setPlaceholderText(t.get("ph_id", ""))
        self.txt_name.setPlaceholderText(t.get("ph_name", ""))
        self.check_connection()

    def load_assets(self):
        self.asset_list.clear()
        if os.path.exists(ASSETS_DIR):
            for f in sorted(os.listdir(ASSETS_DIR)):
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    path = os.path.join(ASSETS_DIR, f)
                    item = QListWidgetItem(f); item.setIcon(QIcon(path)); item.setData(Qt.UserRole, path); self.asset_list.addItem(item)

    def check_connection(self):
        t = self.translations.get(self.current_lang, {})
        try:
            lockdown = create_using_usbmux()
            if lockdown:
                self.lbl_status.setText(t.get("status_connected", "Connected"))
                self.lbl_status.setStyleSheet("color: #30D158; font-weight: bold; background:transparent;")
                self.lbl_dev_name.setText(lockdown.display_name); self.udid = lockdown.udid; self.btn_scan.setEnabled(True); self.check_ready()
            else: raise Exception()
        except:
            self.lbl_status.setText(t.get("status_disconnected", "Disconnected"))
            self.lbl_status.setStyleSheet("color: #FF453A; font-weight: bold; background:transparent;")
            self.lbl_dev_name.setText("--"); self.udid = ""; self.btn_run.setEnabled(False)

    def toggle_scan(self):
        t = self.translations.get(self.current_lang, {})
        msg = QMessageBox(self); msg.setWindowTitle(t.get("scan_popup_title", "Scan"))
        msg.setText(t.get("scan_popup_msg", "Scan card")); msg.show()
        self.sw = ScanWorker(); self.sw.found_signal.connect(lambda cid: (self.txt_id.setText(cid), msg.close(), self.check_ready())); self.sw.start()

    def on_asset_clicked(self, item):
        self.user_image_path = item.data(Qt.UserRole)
        self.lbl_preview.setPixmap(QPixmap(self.user_image_path).scaled(250, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.check_ready()

    def choose_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "Image", "", "Images (*.png *.jpg)")
        if p: self.user_image_path = p; self.lbl_preview.setPixmap(QPixmap(p).scaled(250, 160, Qt.KeepAspectRatio)); self.check_ready()

    def check_ready(self):
        if self.txt_id.text() and self.user_image_path and self.udid: self.btn_run.setEnabled(True)

    def save_card(self):
        n, c = self.txt_name.text(), self.txt_id.text()
        if not n or not c: return
        d = json.load(open(SAVED_FILE_JSON)) if os.path.exists(SAVED_FILE_JSON) else {}
        d[n] = c; json.dump(d, open(SAVED_FILE_JSON, 'w'), indent=4); self.load_saved_data()

    def load_saved_data(self):
        if not os.path.exists(SAVED_FILE_JSON): return
        d = json.load(open(SAVED_FILE_JSON)); self.table.setRowCount(len(d))
        for i, (k, v) in enumerate(d.items()):
            self.table.setItem(i, 0, QTableWidgetItem(k)); self.table.setItem(i, 1, QTableWidgetItem(v))

    def on_table_click(self, r, c): self.txt_id.setText(self.table.item(r, 1).text()); self.check_ready()

    def delete_card(self):
        r = self.table.currentRow(); n = self.table.item(r, 0).text()
        if n:
            d = json.load(open(SAVED_FILE_JSON)); del d[n]; json.dump(d, open(SAVED_FILE_JSON, 'w'), indent=4); self.load_saved_data()

    def start_process(self):
        # VERROUILLAGE DU BOUTON
        self.btn_run.setEnabled(False)
        self.btn_run.setText("INJECTING...")
        self.btn_run.setStyleSheet("background-color: #3A3A3C; color: #8E8E93;")
        
        self.progress.setValue(0)
        self.lbl_p_stat.setText("Starting process...")
        
        self.worker = InjectorProcess(self.udid, self.txt_id.text(), self.user_image_path)
        self.worker.progress_signal.connect(self.update_ui_progress)
        self.worker.finished_signal.connect(self.process_finished)
        self.worker.start()

    def update_ui_progress(self, text, value):
        self.lbl_p_stat.setText(text)
        self.progress.setValue(value)

    def process_finished(self):
        # RÉACTIVATION DU BOUTON
        t = self.translations.get(self.current_lang, {})
        self.btn_run.setEnabled(True)
        self.btn_run.setText(t.get("btn_run", "EXECUTE"))
        self.btn_run.setStyleSheet("background-color: #30D158; color: white;")
        
        self.progress.setValue(100)
        self.lbl_p_stat.setText("Finished")
        QMessageBox.information(self, "OK", t.get("msg_success", "Success!"))

if __name__ == "__main__":
    if os.name != 'nt' and os.getuid() != 0:
        os.execvp('sudo', ['sudo', 'python3'] + sys.argv)
    else:
        app = QApplication(sys.argv); w = AppWindow(); w.show(); sys.exit(app.exec_())