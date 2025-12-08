import sys
import os
import shutil
import time
import socket
import sqlite3
import functools
import threading
import argparse
import subprocess
import asyncio
import queue
import posixpath # Quan trọng để xử lý đường dẫn log
from http.server import HTTPServer, SimpleHTTPRequestHandler
from packaging.version import parse as parse_version

try:
    from pymobiledevice3 import usbmux
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.os_trace import OsTraceService
    from pymobiledevice3.services.afc import AfcService
    from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl
    from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
    from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
except ImportError as e:
    print(f"[Err] Missing lib: {e}", flush=True)
    sys.exit(1)

# --- CẤU HÌNH ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_SOURCE_FOLDER = os.path.join(SCRIPT_DIR, "Cards")
BASE_REMOTE_PATH = "/private/var/mobile/Library/Passes/Cards"
UUID_FILE = os.path.join(SCRIPT_DIR, "uuid.txt")

FILE_BL_ORIGIN = "BLDatabaseManager.sqlite"
FILE_DL_ORIGIN = "downloads.28.sqlitedb"
FILE_BL_TEMP = "working_BL.sqlite"
FILE_DL_TEMP = "working_DL.sqlitedb"

TARGET_DISCLOSURE_PATH = "" 
sd_file = "" 
RESPRING_ENABLED = False
audio_head_ok = threading.Event()
audio_get_ok = threading.Event()
info_queue = queue.Queue()

class AudioRequestHandler(SimpleHTTPRequestHandler):
    def log_request(self, code='-', size='-'): pass
    def do_HEAD(self):
        if self.path == "/" + os.path.basename(sd_file):
            audio_head_ok.set()
        super().do_HEAD()
    def do_GET(self):
        if self.path == "/" + os.path.basename(sd_file):
            audio_get_ok.set()
        super().do_GET()

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    except: return "127.0.0.1"
    finally: s.close()

def start_http_server():
    try:
        handler = functools.partial(AudioRequestHandler)
        httpd = HTTPServer(("0.0.0.0", 0), handler)
        info_queue.put((get_lan_ip(), httpd.server_port))
        httpd.serve_forever()
    except Exception as e:
        print(f"[Err] Server Error: {e}", flush=True)

# --- LOGIC LẤY UUID TỪ CODE MẪU BẠN GỬI ---
def wait_for_uuid_logic(service_provider):
    # Gửi tín hiệu để GUI hiện Popup nhắc tải sách
    print("[GUI:UUID_MISSING]", flush=True)
    print("[Log] Đang quét log bookassetd để tìm UUID...", flush=True)
    
    found_uuid = None
    start_time = time.time()
    
    try:
        # Lắng nghe syslog
        for syslog_entry in OsTraceService(lockdown=service_provider).syslog():
            # Timeout 2 phút
            if time.time() - start_time > 120: 
                print("[Err] Quá thời gian chờ UUID (120s).", flush=True)
                break
            
            # Chỉ lọc tiến trình bookassetd
            if posixpath.basename(syslog_entry.filename) == 'bookassetd':
                message = syslog_entry.message
                
                # Case 1: Tìm thấy trong Shared SystemGroup
                if "/var/containers/Shared/SystemGroup/" in message:
                    try:
                        uuid_part = message.split("/var/containers/Shared/SystemGroup/")[1].split("/")[0]
                        if len(uuid_part) >= 10 and not uuid_part.startswith("systemgroup.com.apple"):
                            found_uuid = uuid_part
                            break
                    except: continue
                
                # Case 2: Tìm thấy trong BLDownloads
                if "/Documents/BLDownloads/" in message:
                    try:
                        uuid_part = message.split("/var/containers/Shared/SystemGroup/")[1].split("/Documents/BLDownloads")[0]
                        if len(uuid_part) >= 10:
                            found_uuid = uuid_part
                            break
                    except: continue
                    
    except Exception as e:
        print(f"[Err] Lỗi đọc log: {e}", flush=True)
        
    return found_uuid

def main_callback(service_provider, dvt, uuid):
    global audio_head_ok, audio_get_ok
    audio_head_ok.clear()
    audio_get_ok.clear()

    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()
    
    try:
        ip, port = info_queue.get(timeout=5)
    except:
        print("[Err] Cannot start server.", flush=True)
        return

    filename_only = os.path.basename(sd_file)
    audio_url = f"http://{ip}:{port}/{filename_only}"
    print(f"[Log] Server running: {audio_url}", flush=True)

    try:
        shutil.copy(FILE_BL_ORIGIN, FILE_BL_TEMP)
        shutil.copy(FILE_DL_ORIGIN, FILE_DL_TEMP)
    except Exception as e: 
        print(f"[Err] Missing SQLite files: {e}", flush=True)
        return

    with sqlite3.connect(FILE_BL_TEMP) as bldb_conn:
        c = bldb_conn.cursor()
        c.execute("UPDATE ZBLDOWNLOADINFO SET ZASSETPATH=?, ZPLISTPATH=?, ZDOWNLOADID=?", (TARGET_DISCLOSURE_PATH, TARGET_DISCLOSURE_PATH, TARGET_DISCLOSURE_PATH))
        c.execute("UPDATE ZBLDOWNLOADINFO SET ZURL=?", (audio_url,))
        bldb_conn.commit()

    afc = AfcService(lockdown=service_provider)
    pc = ProcessControl(dvt)

    with sqlite3.connect(FILE_DL_TEMP) as conn:
        c = conn.cursor()
        local_p = f"/private/var/containers/Shared/SystemGroup/{uuid}/Documents/BLDatabaseManager/BLDatabaseManager.sqlite"
        server_p = f"http://{ip}:{port}/{FILE_BL_TEMP}" 
        
        c.execute(f"UPDATE asset SET local_path = CASE WHEN local_path LIKE '%/BLDatabaseManager.sqlite' THEN '{local_p}' WHEN local_path LIKE '%/BLDatabaseManager.sqlite-shm' THEN '{local_p}-shm' WHEN local_path LIKE '%/BLDatabaseManager.sqlite-wal' THEN '{local_p}-wal' END WHERE local_path LIKE '/private/var/containers/Shared/SystemGroup/%/Documents/BLDatabaseManager/BLDatabaseManager.sqlite%'")
        c.execute(f"UPDATE asset SET url = CASE WHEN url LIKE '%/BLDatabaseManager.sqlite' THEN '{server_p}' WHEN url LIKE '%/BLDatabaseManager.sqlite-shm' THEN '{server_p}-shm' WHEN url LIKE '%/BLDatabaseManager.sqlite-wal' THEN '{server_p}-wal' END WHERE url LIKE '%/BLDatabaseManager.sqlite%'")
        conn.commit()

    procs = OsTraceService(lockdown=service_provider).get_pid_list().get("Payload", {})
    pid_book = next((pid for pid, p in procs.items() if p['ProcessName'] == 'bookassetd'), None)
    pid_books = next((pid for pid, p in procs.items() if p['ProcessName'] == 'Books'), None)
    if pid_book: 
        try: pc.signal(pid_book, 19)
        except: pass
    if pid_books: 
        try: pc.kill(pid_books)
        except: pass

    print(f"[Log] Uploading: {filename_only}", flush=True)
    try:
        AfcService(lockdown=service_provider).push(sd_file, filename_only)
        afc.push(FILE_DL_TEMP, "Downloads/downloads.28.sqlitedb")
        afc.push(f"{FILE_DL_TEMP}-shm", "Downloads/downloads.28.sqlitedb-shm")
        afc.push(f"{FILE_DL_TEMP}-wal", "Downloads/downloads.28.sqlitedb-wal")
    except Exception as e:
        print(f"[Warn] Upload fail: {e}", flush=True)

    pid_itunes = next((pid for pid, p in procs.items() if p['ProcessName'] == 'itunesstored'), None)
    if pid_itunes: 
        try: pc.kill(pid_itunes)
        except: pass

    time.sleep(3)
    
    pid_book = next((pid for pid, p in procs.items() if p['ProcessName'] == 'bookassetd'), None)
    pid_books = next((pid for pid, p in procs.items() if p['ProcessName'] == 'Books'), None)
    if pid_book: 
        try: pc.kill(pid_book)
        except: pass
    if pid_books: 
        try: pc.kill(pid_books)
        except: pass

    try: pc.launch("com.apple.iBooks")
    except: pass

    print("[Log] Waiting for device request...", flush=True)
    start = time.time()
    success = False
    while True:
        if audio_get_ok.is_set():
            print("[OK] Success!", flush=True)
            success = True
            break
        if time.time() - start > 45:
            print("[Fail] Timeout.", flush=True)
            break
        time.sleep(0.1)

    if os.path.exists(sd_file): os.remove(sd_file)

    if RESPRING_ENABLED:
        print("[Log] Respringing...", flush=True)
        pid_sb = next((pid for pid, p in procs.items() if p['ProcessName'] == 'SpringBoard'), None)
        if pid_sb: 
            try: pc.kill(pid_sb)
            except: pass
    
    # Cleanup temp
    if os.path.exists(FILE_BL_TEMP): os.remove(FILE_BL_TEMP)
    if os.path.exists(FILE_DL_TEMP): os.remove(FILE_DL_TEMP)
    if os.path.exists(f"{FILE_DL_TEMP}-shm"): os.remove(f"{FILE_DL_TEMP}-shm")
    if os.path.exists(f"{FILE_DL_TEMP}-wal"): os.remove(f"{FILE_DL_TEMP}-wal")

async def create_tunnel(udid):
    cmd = f"sudo {sys.executable} -m pymobiledevice3 lockdown start-tunnel --script-mode --udid {udid}"
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        line = p.stdout.readline()
        if line: return {"address": line.decode().split(" ")[0], "port": int(line.decode().split(" ")[1])}

async def connection_context(udid):
    sp = create_using_usbmux(serial=udid)
    ver = parse_version(sp.product_version)
    
    uuid = ""
    if os.path.exists(UUID_FILE):
        content = open(UUID_FILE).read().strip()
        if len(content) > 10: uuid = content

    if not uuid:
        # Gọi hàm logic mới
        uuid = wait_for_uuid_logic(sp)
        if uuid:
            with open(UUID_FILE, "w") as f: f.write(uuid)
            print(f"[Log] Got UUID: {uuid}", flush=True)
        else:
            print("[Err] Failed to capture UUID. Process aborted.", flush=True)
            return

    if ver >= parse_version('17.0'):
        addr = await create_tunnel(udid)
        if addr:
            async with RemoteServiceDiscoveryService((addr["address"], addr["port"])) as rsd:
                with DvtSecureSocketProxyService(rsd) as dvt: main_callback(rsd, dvt, uuid)
    else:
        with DvtSecureSocketProxyService(lockdown=sp) as dvt: main_callback(sp, dvt, uuid)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--udid", required=True)
    parser.add_argument("--card_id", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    os.chdir(SCRIPT_DIR)
    
    if not os.path.exists(LOCAL_SOURCE_FOLDER):
        print(f"[Err] Folder Cards not found at {LOCAL_SOURCE_FOLDER}", flush=True)
        sys.exit(1)

    card_id = args.card_id
    user_img = args.image

    print(f"[*] Starting Process for Card: {card_id}", flush=True)

    tasks = [
        ("cardBackgroundCombined@2x.png", f"{card_id}.pkpass/cardBackgroundCombined@2x.png"),
        ("FrontFace",  f"{card_id}.cache/FrontFace"),
        ("PlaceHolder", f"{card_id}.cache/PlaceHolder"),
        ("Preview",    f"{card_id}.cache/Preview")
    ]

    for index, (filename, subpath) in enumerate(tasks):
        if filename == "cardBackgroundCombined@2x.png":
            src_path = user_img
        else:
            src_path = os.path.join(LOCAL_SOURCE_FOLDER, filename)

        if not os.path.exists(src_path):
            print(f"[Skip] File not found: {src_path}", flush=True)
            continue

        sd_file = filename
        shutil.copy(src_path, sd_file) 
        TARGET_DISCLOSURE_PATH = f"{BASE_REMOTE_PATH}/{subpath}"
        RESPRING_ENABLED = (index == len(tasks) - 1)

        print(f"--> Processing: {filename}", flush=True)
        try:
            asyncio.run(connection_context(args.udid))
        except Exception as e:
            print(f"[Err] Exception: {e}", flush=True)
            import traceback
            traceback.print_exc()
            
    print("[Done] All tasks finished.", flush=True)