import sys
import os
import re
import json
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, 
                             QMessageBox, QFrame, QFileDialog, QProgressBar, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap
from pymobiledevice3.lockdown import create_using_usbmux

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAVED_FILE_JSON = os.path.join(SCRIPT_DIR, "saved_cards.json")
WORKER_SCRIPT = os.path.join(SCRIPT_DIR, "cli_worker.py")

# On garde ton dictionnaire LANGUAGES identique
LANGUAGES = {
    "EN": {
        "title": "WALLET MANAGER", "device_prefix": "Device:", "status_connected": "Connected",
        "status_disconnected": "Disconnected", "sec1_title": "1. CARD ID MANAGEMENT",
        "btn_scan": "SCAN CARD ID", "btn_scan_wait": "Waiting for card...",
        "ph_id": "Card ID (Hash)...", "ph_name": "Enter alias name...",
        "btn_save": "Save", "btn_del": "Del", "col_name": "Card Name", "col_id": "ID",
        "sec2_title": "2. IMAGE & PREVIEW", "btn_img": "Select or Drop Image",
        "lbl_no_img": "No image selected", "btn_run": "EXECUTE (INJECT)",
        "msg_done": "Done!", "msg_success": "Success!\nPlease check your iPhone Wallet.",
        "p_init": "Initializing...", "p_img": "Replacing Background...",
        "p_done": "Process Finished!", "scan_popup_title": "Scanning...",
        "scan_popup_msg": "Please open Wallet on iPhone and tap the card.", "btn_close": "Close"
    },
    "FR": {
        "title": "GESTIONNAIRE WALLET", "device_prefix": "Appareil :", "status_connected": "Connecté",
        "status_disconnected": "Déconnecté", "sec1_title": "1. GESTION ID DE CARTE",
        "btn_scan": "SCANNER ID CARTE", "btn_scan_wait": "Attente de la carte...",
        "ph_id": "ID Carte (Hash)...", "ph_name": "Nom de la carte...",
        "btn_save": "Sauver", "btn_del": "Suppr", "col_name": "Nom", "col_id": "ID",
        "sec2_title": "2. IMAGE & APPERÇU", "btn_img": "Choisir ou Déposer Image",
        "lbl_no_img": "Aucune image", "btn_run": "INJECTER (EXECUTE)",
        "msg_done": "Terminé !", "msg_success": "Succès !\nVérifiez votre Wallet sur iPhone.",
        "p_init": "Initialisation...", "p_img": "Remplacement fond...",
        "p_done": "Processus terminé !", "scan_popup_title": "Scan en cours...",
        "scan_popup_msg": "Ouvrez Wallet sur iPhone et touchez la carte.", "btn_close": "Fermer"
    },
    # ... (Garder VN, CN, KR à l'identique)
}

class ScanWorker(QThread):
    found_signal = pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.running = True
        self.pattern_nfc = re.compile(r'passIDs(?:\[global\])?.\s*\{\(\s*"([^"]+)"', re.IGNORECASE)

    def run(self):
        try:
            from pymobiledevice3.services.os_trace import OsTraceService
            # On tente de créer le lockdown à l'intérieur du thread
            lockdown = create_using_usbmux()
            if not lockdown: return
            
            for entry in OsTraceService(lockdown=lockdown).syslog():
                if not self.running: break
                if entry.label and entry.label.subsystem == "com.apple.nfc":
                    match = self.pattern_nfc.search(entry.message)
                    if match: self.found_signal.emit(match.group(1)); break
                if '/var/mobile/Library/Passes/Cards/' in entry.message:
                    res = entry.message.split('/var/mobile/Library/Passes/Cards/')[1].split('.pkpass')[0]
                    self.found_signal.emit(res); break
        except Exception as e:
            print(f"Scan Error: {e}")

class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("iOS Wallet Manager Pro")
        self.setGeometry(100, 100, 750, 600)
        self.setAcceptDrops(True)
        self.user_image_path, self.udid, self.current_lang = "", "", "EN"
        
        self.init_ui()
        self.apply_dark_theme()
        self.load_saved_data()
        self.retranslate_ui()
        
        # Timer pour la connexion
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_connection)
        self.timer.start(3000) # Augmenté à 3s pour laisser respirer l'USB

    def check_connection(self):
        t = LANGUAGES[self.current_lang]
        try:
            # On vérifie si un appareil est présent sur l'usbmux avant de tenter le lockdown
            lockdown = create_using_usbmux()
            if lockdown:
                self.lbl_status.setText(t["status_connected"])
                self.lbl_status.setStyleSheet("color: #30D158;")
                self.lbl_dev_name.setText(f"{lockdown.display_name} (iOS {lockdown.product_version})")
                self.udid = lockdown.udid
                self.btn_scan.setEnabled(True)
                self.check_ready()
            else:
                raise Exception("No Device")
        except Exception:
            self.lbl_status.setText(t["status_disconnected"])
            self.lbl_status.setStyleSheet("color: #FF453A;")
            self.lbl_dev_name.setText("--")
            self.udid = ""
            self.btn_scan.setEnabled(False)
            self.btn_run.setEnabled(False)

    # --- GARDER LE RESTE DU CODE (init_ui, apply_dark_theme, etc.) ---
    # NOTE : Assure-toi que toutes les méthodes que tu as fournies sont présentes en dessous.
    # La correction majeure est dans check_connection pour éviter le crash.

    def init_ui(self):
        mw = QWidget(); self.setCentralWidget(mw); ml = QVBoxLayout(mw)
        tf = QFrame(); tf.setObjectName("HeaderFrame"); tl = QHBoxLayout(tf)
        self.lbl_title = QLabel("WALLET CUSTOMIZER"); self.lbl_title.setObjectName("AppTitle")
        self.combo_lang = QComboBox(); self.combo_lang.addItems(["English", "Français", "Tiếng Việt", "中文", "한국어"])
        self.combo_lang.currentIndexChanged.connect(self.on_lang_changed)
        self.lbl_status = QLabel("Disconnected"); self.lbl_dev_name = QLabel("--")
        tl.addWidget(self.lbl_title); tl.addWidget(self.combo_lang); tl.addStretch()
        il = QVBoxLayout(); il.addWidget(self.lbl_status); il.addWidget(self.lbl_dev_name); tl.addLayout(il)
        ml.addWidget(tf)
        cl = QHBoxLayout(); lf = QFrame(); lf.setObjectName("Card"); ll = QVBoxLayout(lf)
        self.lbl_sec1 = QLabel(); self.lbl_sec1.setObjectName("SectionTitle"); ll.addWidget(self.lbl_sec1)
        self.btn_scan = QPushButton(); self.btn_scan.setObjectName("BtnPrimary"); self.btn_scan.clicked.connect(self.toggle_scan)
        ll.addWidget(self.btn_scan); self.txt_id = QLineEdit(); ll.addWidget(self.txt_id)
        mgmt = QHBoxLayout(); self.txt_name = QLineEdit(); self.btn_save = QPushButton("Save"); self.btn_save.setObjectName("BtnSave")
        self.btn_save.clicked.connect(self.save_card); self.btn_del = QPushButton("Del"); self.btn_del.setObjectName("BtnDelete")
        self.btn_del.clicked.connect(self.delete_card)
        mgmt.addWidget(self.txt_name); mgmt.addWidget(self.btn_save); mgmt.addWidget(self.btn_del); ll.addLayout(mgmt)
        self.table = QTableWidget(0, 2); self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.cellClicked.connect(self.on_table_click); ll.addWidget(self.table)
        rf = QFrame(); rf.setObjectName("Card"); rl = QVBoxLayout(rf)
        self.lbl_sec2 = QLabel(); self.lbl_sec2.setObjectName("SectionTitle"); rl.addWidget(self.lbl_sec2)
        self.btn_img = QPushButton(); self.btn_img.setObjectName("BtnSecondary"); self.btn_img.clicked.connect(self.choose_image)
        rl.addWidget(self.btn_img); self.lbl_preview = QLabel("Preview"); self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumSize(250, 150); self.lbl_preview.setStyleSheet("border: 2px dashed #444; border-radius: 8px; background-color: #222;")
        rl.addWidget(self.lbl_preview); self.lbl_img_path = QLabel(""); rl.addWidget(self.lbl_img_path)
        cl.addWidget(lf, 55); cl.addWidget(rf, 45); ml.addLayout(cl)
        bf = QFrame(); bf.setObjectName("Card"); bl = QVBoxLayout(bf)
        self.btn_run = QPushButton(); self.btn_run.setObjectName("BtnSuccess"); self.btn_run.setFixedHeight(50); self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.start_process); self.lbl_p_stat = QLabel(""); self.progress = QProgressBar()
        bl.addWidget(self.btn_run); bl.addWidget(self.lbl_p_stat); bl.addWidget(self.progress); ml.addWidget(bf)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #E0E0E0; font-family: 'Helvetica Neue', sans-serif; }
            #HeaderFrame { background-color: #1E1E1E; border-bottom: 1px solid #333; }
            #AppTitle { font-size: 20px; font-weight: bold; color: white; }
            #Card { background-color: #1E1E1E; border-radius: 10px; border: 1px solid #333; }
            QLineEdit, QTableWidget { background-color: #2C2C2E; border: 1px solid #3A3A3C; color: white; padding: 5px; }
            QPushButton { font-weight: bold; padding: 5px; border-radius: 5px; }
            #BtnPrimary { background-color: #0A84FF; color: white; }
            #BtnSecondary { background-color: #3A3A3C; color: white; border: 1px solid #555; }
            #BtnSuccess { background-color: #30D158; color: white; }
            #BtnSave { background-color: #FF9F0A; color: black; }
            #BtnDelete { background-color: #FF453A; color: white; }
            QHeaderView::section { background-color: #2C2C2E; color: white; border: none; font-weight: bold; }
            QComboBox { background-color: #2C2C2E; color: white; border: 1px solid #3A3A3C; padding: 5px; }
        """)

    def on_lang_changed(self, index):
        langs = ["EN", "FR", "VN", "CN", "KR"]
        self.current_lang = langs[index]; self.retranslate_ui()

    def retranslate_ui(self):
        t = LANGUAGES[self.current_lang]
        self.lbl_sec1.setText(t["sec1_title"]); self.lbl_sec2.setText(t["sec2_title"])
        self.btn_scan.setText(t["btn_scan"]); self.btn_img.setText(t["btn_img"]); self.btn_run.setText(t["btn_run"])
        self.table.setHorizontalHeaderLabels([t["col_name"], t["col_id"]])

    def toggle_scan(self):
        t = LANGUAGES[self.current_lang]
        self.scan_popup = QMessageBox(self)
        self.scan_popup.setWindowTitle(t["scan_popup_title"])
        self.scan_popup.setText(t["scan_popup_msg"])
        self.scan_popup.setStandardButtons(QMessageBox.Close)
        self.scan_popup.show()
        self.sw = ScanWorker(); self.sw.found_signal.connect(self.on_id_found); self.sw.start()

    def on_id_found(self, cid):
        self.txt_id.setText(cid); self.check_ready()
        if hasattr(self, 'scan_popup'): self.scan_popup.close()

    def choose_image(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg)")
        if p:
            self.user_image_path = p; self.lbl_img_path.setText(os.path.basename(p))
            self.lbl_preview.setPixmap(QPixmap(p).scaled(250, 150, Qt.KeepAspectRatio)); self.check_ready()

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
        r = self.table.currentRow()
        if r < 0: return
        n = self.table.item(r, 0).text()
        d = json.load(open(SAVED_FILE_JSON))
        if n in d: del d[n]
        json.dump(d, open(SAVED_FILE_JSON, 'w'), indent=4); self.load_saved_data()

    def start_process(self):
        t = LANGUAGES[self.current_lang]
        self.btn_run.setEnabled(False)
        self.worker = InjectorProcess(self.udid, self.txt_id.text(), self.user_image_path, self.current_lang)
        self.worker.progress_signal.connect(lambda m, v: (self.lbl_p_stat.setText(m), self.progress.setValue(v)))
        self.worker.finished_signal.connect(lambda: (self.btn_run.setEnabled(True), QMessageBox.information(self, "OK", t["msg_success"])))
        self.worker.start()

class InjectorProcess(QThread):
    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal()
    def __init__(self, udid, card_id, img_path, lang_code):
        super().__init__()
        self.udid, self.card_id, self.img_path = udid, card_id, img_path
        self.lang = LANGUAGES[lang_code]
    def run(self):
        cmd = [sys.executable, WORKER_SCRIPT, f"--udid={self.udid}", f"--card_id={self.card_id}", f"--image={self.img_path}"]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in process.stdout:
            line = line.strip()
            if "Starting Process" in line: self.progress_signal.emit(self.lang["p_init"], 10)
            elif "cardBackgroundCombined" in line: self.progress_signal.emit(self.lang["p_img"], 50)
            elif "All tasks finished" in line: self.progress_signal.emit(self.lang["p_done"], 100)
        process.wait()
        self.finished_signal.emit()

if __name__ == "__main__":
    if os.name != 'nt' and os.geteuid() != 0:
        os.execvp('sudo', ['sudo', 'python3'] + sys.argv)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AppWindow()
    w.show()
    sys.exit(app.exec_())