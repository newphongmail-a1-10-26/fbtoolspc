#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SkyPilot Automation Studio 3.5.1
Advanced Auto-Fill, Screen Analysis & Smart Engine for Meta/Facebook Sign-Up.
Updated with Robust DOM Target Detection, Female-Only Profiles, and 'Fill Details' Fallback Button.
No page scrolling. React + new Meta form compatible typing.
"""

import os
import sys
import subprocess
import importlib.util
import time
import json
import csv
import sqlite3
import shutil
import platform
import logging
import secrets
import string
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urlparse

APP_NAME = "SkyPilot Automation Studio"
APP_VERSION = "3.5.1"
APP_DIR = Path.home() / "SkyPilotAutomationStudio"
DB_PATH = APP_DIR / "skypilot.db"
LOG_DIR = APP_DIR / "logs"
BACKUP_DIR = APP_DIR / "backups"
EXPORT_DIR = APP_DIR / "exports"
TOOL_BROWSER_DIR = APP_DIR / "tool_browser_profile"

for folder in (APP_DIR, LOG_DIR, BACKUP_DIR, EXPORT_DIR, TOOL_BROWSER_DIR):
    folder.mkdir(parents=True, exist_ok=True)

def bootstrap_dependencies():
    modules = {
        "PySide6": "PySide6",
        "PySide6.QtWebEngineWidgets": "PySide6-WebEngine",
        "psutil": "psutil",
    }
    missing = []
    for module, package in modules.items():
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(package)
        except (ImportError, ModuleNotFoundError, ValueError):
            missing.append(package)
    if missing:
        print(f"{APP_NAME}: installing required packages: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", *missing])

bootstrap_dependencies()

import psutil
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QUrl, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QListWidget, QListWidgetItem,
    QLineEdit, QTextEdit, QComboBox, QMessageBox, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout, QSpinBox,
    QSplitter, QStatusBar, QCheckBox, QScrollArea, QGraphicsOpacityEffect
)
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

logging.basicConfig(
    filename=LOG_DIR / "application.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(APP_NAME)

BROWSERS = {
    "Google Chrome": [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        "google-chrome", "google-chrome-stable", "chrome"
    ],
    "Microsoft Edge": [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        "msedge"
    ],
    "Mozilla Firefox": [
        os.path.expandvars(r"%ProgramFiles%\Mozilla Firefox\firefox.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"),
        os.path.expandvars(r"%LocalAppData%\Mozilla Firefox\firefox.exe"),
        "firefox"
    ],
}

def resolve_executable(name):
    for candidate in BROWSERS.get(name, []):
        if not candidate:
            continue
        candidate = os.path.expandvars(candidate)
        if os.path.isabs(candidate) and Path(candidate).is_file():
            return str(Path(candidate))
        found = shutil.which(candidate)
        if found:
            return found
    return None

def normalize_url(text):
    text = text.strip()
    if not text:
        raise ValueError("Enter a website address.")
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid HTTP or HTTPS address.")
    return text

def find_adb():
    candidates = [
        shutil.which("adb"),
        os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"),
        os.path.expandvars(r"%ANDROID_HOME%\platform-tools\adb.exe"),
    ]
    for item in candidates:
        if item and Path(item).is_file():
            return str(Path(item))
    return None

class Store:
    def __init__(self):
        self.initialize()

    def connect(self):
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        return con

    def initialize(self):
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                category TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS profiles(
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                first_name TEXT NOT NULL, last_name TEXT NOT NULL,
                email TEXT NOT NULL, notes TEXT DEFAULT '')""")
            con.execute("""CREATE TABLE IF NOT EXISTS workflow_runs(
                id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL, target_url TEXT NOT NULL,
                result TEXT NOT NULL, details TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
            con.execute("""CREATE TABLE IF NOT EXISTS accounts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                first_name TEXT, last_name TEXT,
                contact TEXT, password TEXT,
                gender TEXT, dob TEXT,
                uid TEXT, cookies TEXT, token TEXT,
                contact_type TEXT DEFAULT 'email',
                status TEXT DEFAULT 'created',
                notes TEXT DEFAULT '')""")
            con.execute("""CREATE TABLE IF NOT EXISTS contact_pool(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value TEXT NOT NULL UNIQUE,
                contact_type TEXT NOT NULL,
                used INTEGER DEFAULT 0,
                used_at TEXT DEFAULT '')""")

    def event(self, category, message, status="INFO"):
        with self.connect() as con:
            con.execute("INSERT INTO events(created_at,category,message,status) VALUES(?,?,?,?)",
                        (datetime.now().isoformat(timespec="seconds"), category, message, status))

    def add_profile(self, first, last, email, notes):
        with self.connect() as con:
            con.execute("INSERT INTO profiles(created_at,first_name,last_name,email,notes) VALUES(?,?,?,?,?)",
                        (datetime.now().isoformat(timespec="seconds"), first, last, email, notes))

    def profiles(self):
        with self.connect() as con:
            return con.execute("SELECT * FROM profiles ORDER BY id DESC").fetchall()

    def events(self):
        with self.connect() as con:
            return con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 500").fetchall()

    def record_run(self, start, end, url, result, details):
        with self.connect() as con:
            con.execute("INSERT INTO workflow_runs(started_at,finished_at,target_url,result,details) VALUES(?,?,?,?,?)",
                        (start, end, url, result, details))

    def get_setting(self, key, default=""):
        with self.connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self.connect() as con:
            con.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)", (key, value))

    def counts(self):
        with self.connect() as con:
            return {
                "profiles": con.execute("SELECT COUNT(*) FROM profiles").fetchone()[0],
                "runs": con.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0],
                "success": con.execute("SELECT COUNT(*) FROM workflow_runs WHERE result='Completed'").fetchone()[0],
                "failed": con.execute("SELECT COUNT(*) FROM workflow_runs WHERE result='Failed'").fetchone()[0],
            }

    def add_account(self, first, last, contact, password, gender, dob, uid="", cookies="", token="", contact_type="email", status="created", notes=""):
        with self.connect() as con:
            con.execute("""INSERT INTO accounts(created_at,first_name,last_name,contact,password,gender,dob,uid,cookies,token,contact_type,status,notes)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (datetime.now().isoformat(timespec="seconds"), first, last, contact, password, gender, dob, uid, cookies, token, contact_type, status, notes))

    def accounts(self, search=""):
        with self.connect() as con:
            if search:
                q = f"%{search}%"
                return con.execute("""SELECT * FROM accounts WHERE first_name LIKE ? OR last_name LIKE ? OR contact LIKE ? OR uid LIKE ?
                    ORDER BY id DESC""", (q,q,q,q)).fetchall()
            return con.execute("SELECT * FROM accounts ORDER BY id DESC").fetchall()

    def delete_accounts(self, ids):
        with self.connect() as con:
            for i in ids:
                con.execute("DELETE FROM accounts WHERE id=?", (i,))

    def clear_accounts(self):
        with self.connect() as con:
            con.execute("DELETE FROM accounts")

    def add_contacts(self, values, contact_type):
        with self.connect() as con:
            for v in values:
                v = v.strip()
                if not v:
                    continue
                try:
                    con.execute("INSERT OR IGNORE INTO contact_pool(value, contact_type, used) VALUES(?,?,0)", (v, contact_type))
                except Exception:
                    pass

    def next_contact(self, contact_type):
        with self.connect() as con:
            row = con.execute("SELECT * FROM contact_pool WHERE contact_type=? AND used=0 ORDER BY id ASC LIMIT 1", (contact_type,)).fetchone()
            if row:
                con.execute("UPDATE contact_pool SET used=1, used_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), row["id"]))
                return row["value"]
            return None

    def contact_stats(self, contact_type):
        with self.connect() as con:
            total = con.execute("SELECT COUNT(*) FROM contact_pool WHERE contact_type=?", (contact_type,)).fetchone()[0]
            used = con.execute("SELECT COUNT(*) FROM contact_pool WHERE contact_type=? AND used=1", (contact_type,)).fetchone()[0]
            return total, used, total - used


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = Store()
        self.adb_path = find_adb()
        
        self.current_app_title = self.store.get_setting("app_name", APP_NAME)
        
        self.setWindowTitle(f"{self.current_app_title}  |  {APP_VERSION}")
        self.resize(1450, 850)
        self.setMinimumSize(1100, 700)
        self.started = time.time()
        self.build_ui()
        self.apply_style()
        self.refresh_all()
        
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_monitor)
        self.monitor_timer.start(2000)
        self.store.event("Application", "Application started", "SUCCESS")

        self.popup_seconds = 5
        self.popup_timer = QTimer(self)
        self.popup_timer.timeout.connect(self.handle_popup_countdown)

        self.auto_observer_timer = QTimer(self)
        self.auto_observer_timer.timeout.connect(self.check_and_autofill_page)
        self.auto_observer_timer.start(1200)

        # First open: block autofill/redirect for 60 seconds so user can import & configure
        self._startup_block_autofill = True
        self._startup_grace_left = 180  # 3 minutes setup time on first open / after clear
        self._otp_resend_running = False
        self._startup_timer = QTimer(self)
        self._startup_timer.timeout.connect(self._tick_startup_grace)
        self._startup_timer.start(1000)

        self.flip_state = 0
        self.logo_anim_timer = QTimer(self)
        self.logo_anim_timer.timeout.connect(self.animate_3d_logo)
        self.logo_anim_timer.start(3000)

    def build_ui(self):
        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        self.sidebar = QFrame(objectName="sidebar")
        self.sidebar.setFixedWidth(190)
        sl = QVBoxLayout(self.sidebar)
        sl.setContentsMargins(6, 8, 6, 8)
        sl.setSpacing(4)
        
        self.brand_frame = QFrame(objectName="brandFrame")
        brand_layout = QHBoxLayout(self.brand_frame)
        brand_layout.setContentsMargins(6, 6, 6, 6)
        brand_layout.setSpacing(6)
        
        self.brand_icon = QLabel("f", objectName="fbLogoIcon")
        self.brand_text = QLabel(self.current_app_title.split()[0], objectName="brand")
        brand_layout.addWidget(self.brand_icon)
        brand_layout.addWidget(self.brand_text)
        brand_layout.addStretch()
        
        sl.addWidget(self.brand_frame)
        sl.addWidget(QLabel("AUTOMATION • 3.5.1", objectName="smallMuted"))
        
        spacer = QWidget()
        spacer.setFixedHeight(6)
        sl.addWidget(spacer)

        self.nav = QListWidget(objectName="navigation")
        self.pages = ["Overview", "Browser Center", "Browser Preview", "Profile Manager",
                      "Data Generator", "Workflow Runner", "Android / ADB",
                      "System Monitor", "Activity Logs", "Backup Center", "Settings"]
        for p in self.pages:
            QListWidgetItem("  " + p, self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self.change_page)
        sl.addWidget(self.nav, 1)

        self.stack = QStackedWidget()
        builders = [self.page_overview, self.page_browser, self.page_preview,
                    self.page_profiles, self.page_generator, self.page_workflow,
                    self.page_adb, self.page_monitor, self.page_logs,
                    self.page_backup, self.page_settings]
        for build in builders:
            self.stack.addWidget(build())

        outer.addWidget(self.sidebar)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready • Smart Pointer-Based Sync Engine Active")

    def animate_3d_logo(self):
        self.flip_state = (self.flip_state + 1) % 2
        if self.flip_state == 1:
            self.brand_frame.setStyleSheet("""
                #brandFrame {
                    background: transparent;
                    border: none;
                }
            """)
        else:
            self.brand_frame.setStyleSheet("""
                #brandFrame {
                    background: transparent;
                    border: none;
                }
            """)

    def header(self, title, subtitle):
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 6)
        l.setSpacing(2)
        l.addWidget(QLabel(title, objectName="pageTitle"))
        d = QLabel(subtitle, objectName="muted")
        d.setWordWrap(True)
        l.addWidget(d)
        return w

    def page_overview(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(self.header("Overview", "Live application records and local system status."))
        grid = QGridLayout()
        grid.setSpacing(8)
        self.cards = {}
        for i, (key, label) in enumerate([("profiles","Saved Profiles"),("runs","Workflow Runs"),
                                          ("success","Completed Runs"),("failed","Failed Runs")]):
            c = self.metric_card(label, "0")
            self.cards[key] = c
            grid.addWidget(c, 0, i)
        l.addLayout(grid)
        quick = QGroupBox("Quick Actions"); q = QGridLayout(quick)
        q.setSpacing(6)
        for i, (label, page) in enumerate([("Browser Center",1),("Open Tool Browser",2),
                                           ("Profile Manager",3),("Android / ADB",6)]):
            b = QPushButton(label); b.clicked.connect(lambda checked=False, p=page: self.nav.setCurrentRow(p))
            q.addWidget(b, 0, i)
        l.addWidget(quick)
        l.addStretch()
        return w

    def metric_card(self, title, value):
        frame = QFrame(objectName="card"); x = QVBoxLayout(frame)
        x.setContentsMargins(10, 10, 10, 10)
        x.setSpacing(4)
        x.addWidget(QLabel(title, objectName="muted"))
        val = QLabel(value, objectName="metric")
        x.addWidget(val); frame.metric_value = val
        return frame

    def page_browser(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(self.header("Browser Center", "Choose browser configuration and start page."))
        modebox = QGroupBox("Browser Execution"); ml = QHBoxLayout(modebox)
        self.browser_mode = QComboBox()
        self.browser_mode.addItems(["Tool Browser (Embedded)", "Desktop Browser"])
        ml.addWidget(QLabel("Mode:")); ml.addWidget(self.browser_mode, 1)
        l.addWidget(modebox)
        
        self.browser_form = QGroupBox("Browser Configuration"); f = QFormLayout(self.browser_form)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(6)
        self.destination = QLineEdit("https://www.facebook.com/")
        f.addRow("Start URL", self.destination)
        l.addWidget(self.browser_form)
        
        row = QHBoxLayout()
        self.launch_btn = QPushButton("Open Browser Preview"); self.launch_btn.setObjectName("primary")
        self.launch_btn.clicked.connect(lambda: self.nav.setCurrentRow(2))
        row.addWidget(self.launch_btn)
        l.addLayout(row); l.addStretch()
        return w

    def page_preview(self):
        w = QWidget(); main_layout = QVBoxLayout(w)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setMinimumWidth(300)
        left_scroll.setMaximumWidth(420)
        left_scroll.setFixedWidth(380)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # always show slider
        left_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                width: 10px;
                background: #E8EEF8;
                border-radius: 5px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #3B82F6;
                border-radius: 5px;
                min-height: 40px;
            }
            QScrollBar::handle:vertical:hover { background: #2563EB; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        left_container = QWidget()
        left_container.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(4, 4, 10, 12)
        left_layout.setSpacing(8)

        left_layout.addWidget(self.header("Smart Setup", "American Profile & Engine"))

        cfg = QGroupBox("Target Account Details"); cf = QFormLayout(cfg)
        cf.setContentsMargins(6, 8, 6, 8)
        cf.setSpacing(5)
        
        self.auto_fname = QLineEdit(); self.auto_fname.setPlaceholderText("First Name")
        self.auto_lname = QLineEdit(); self.auto_lname.setPlaceholderText("Surname")
        self.auto_credential = QLineEdit(); self.auto_credential.setPlaceholderText("Mobile or Email")
        self.auto_pass = QLineEdit(); self.auto_pass.setPlaceholderText("Password")
        
        self.auto_gender = QComboBox()
        self.auto_gender.addItems(["Female"])  # সবসময় ফিমেল নিশ্চিত করা হয়েছে
        self.auto_gender.setCurrentText("Female")
        
        dob_layout = QHBoxLayout()
        dob_layout.setSpacing(4)
        self.sel_day = QComboBox()
        self.sel_day.addItems([str(i) for i in range(1, 32)])
        self.sel_day.setCurrentText("15")
        self.sel_day.setMinimumWidth(50)
        self.sel_day.setMaximumWidth(70)
        self.sel_day.setMaxVisibleItems(12)

        self.sel_month = QComboBox()
        self.sel_month.addItems(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
        self.sel_month.setCurrentText("May")
        self.sel_month.setMinimumWidth(58)
        self.sel_month.setMaximumWidth(80)
        self.sel_month.setMaxVisibleItems(12)

        self.sel_year = QComboBox()
        self.sel_year.addItems([str(y) for y in range(1975, 2006)])
        self.sel_year.setCurrentText("1988")
        self.sel_year.setMinimumWidth(70)
        self.sel_year.setMaximumWidth(90)
        self.sel_year.setMaxVisibleItems(12)

        dob_layout.addWidget(self.sel_day)
        dob_layout.addWidget(self.sel_month)
        dob_layout.addWidget(self.sel_year)

        self.auto_submit_cb = QCheckBox("Force React Auto-Fill & Submit")
        self.auto_submit_cb.setChecked(True)

        cf.addRow("First name", self.auto_fname)
        cf.addRow("Surname", self.auto_lname)
        cf.addRow("Email", self.auto_credential)
        cf.addRow("Password", self.auto_pass)
        cf.addRow("Gender", self.auto_gender)
        cf.addRow("DOB", dob_layout)
        
        # ফলব্যাক "Fill Details" বাটন বক্স
        self.btn_fill_details_box = QPushButton("⚡ Fill Details (Manual Fallback)")
        self.btn_fill_details_box.setObjectName("primary")
        self.btn_fill_details_box.clicked.connect(self.execute_autofill_script)
        cf.addRow(self.btn_fill_details_box)

        cf.addRow(self.auto_submit_cb)

        # --- Contact source & resend settings ---
        self.contact_mode = QComboBox()
        self.contact_mode.addItems(["Email", "Phone"])
        self.contact_source = QComboBox()
        self.contact_source.addItems(["Random / Generated", "From imported list", "Manual (type yourself)"])
        self.run_mode = QComboBox()
        self.run_mode.addItems(["Custom mode (manual control)", "Auto mode (list loop)"])
        cf.addRow("Contact type", self.contact_mode)
        cf.addRow("Contact source", self.contact_source)
        cf.addRow("Run mode", self.run_mode)

        self.spin_resend_email = QSpinBox(); self.spin_resend_email.setRange(0, 30)
        self.spin_resend_email.setValue(int(self.store.get_setting("resend_email_times", "2") or "2"))
        self.spin_resend_phone = QSpinBox(); self.spin_resend_phone.setRange(0, 30)
        self.spin_resend_phone.setValue(int(self.store.get_setting("resend_phone_times", "8") or "8"))
        cf.addRow("OTP resend Email x", self.spin_resend_email)
        cf.addRow("OTP resend Phone x", self.spin_resend_phone)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Optional API key (SMS/Email/Telegram provider)")
        self.api_key_edit.setText(self.store.get_setting("api_key", ""))
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        cf.addRow("API Key", self.api_key_edit)

        btn_import = QPushButton("Import Email/Phone .txt")
        btn_import.clicked.connect(self.import_contact_list)
        btn_use_pool = QPushButton("Use next from list")
        btn_use_pool.clicked.connect(self.apply_next_contact_from_pool)
        btn_api = QPushButton("Fetch via API")
        btn_api.clicked.connect(self.fetch_contact_via_api)
        cf.addRow(btn_import)
        cf.addRow(btn_use_pool)
        cf.addRow(btn_api)

        self.lbl_contact_stats = QLabel("Pool — Email left: - | Phone left: -", objectName="muted")
        cf.addRow(self.lbl_contact_stats)
        try:
            self.refresh_contact_stats_label()
        except Exception:
            pass

        left_layout.addWidget(cfg)

        btn_box = QGroupBox("Quick Data & Copy Controls")
        btn_layout = QVBoxLayout(btn_box)
        btn_layout.setContentsMargins(6, 8, 6, 8)
        btn_layout.setSpacing(5)

        uid_row = QHBoxLayout()
        self.btn_uid = QLineEdit(); self.btn_uid.setPlaceholderText("UID (c_user after account exists)")
        copy_uid_btn = QPushButton("Copy UID")
        copy_uid_btn.clicked.connect(lambda: self.copy_to_clipboard(self.btn_uid.text(), "UID"))
        uid_row.addWidget(self.btn_uid); uid_row.addWidget(copy_uid_btn)
        btn_layout.addLayout(uid_row)

        cookie_row = QHBoxLayout()
        self.btn_cookies = QLineEdit(); self.btn_cookies.setPlaceholderText("Cookies (after account / Grab Cookies)")
        copy_cookie_btn = QPushButton("Copy Cookies")
        copy_cookie_btn.clicked.connect(lambda: self.copy_to_clipboard(self.btn_cookies.text(), "Cookies"))
        cookie_row.addWidget(self.btn_cookies); cookie_row.addWidget(copy_cookie_btn)
        btn_layout.addLayout(cookie_row)

        token_row = QHBoxLayout()
        self.btn_token = QLineEdit(); self.btn_token.setPlaceholderText("Access Token (only when real session exists)")
        copy_token_btn = QPushButton("Copy Token")
        copy_token_btn.clicked.connect(lambda: self.copy_to_clipboard(self.btn_token.text(), "Token"))
        token_row.addWidget(self.btn_token); token_row.addWidget(copy_token_btn)
        btn_layout.addLayout(token_row)

        email_row = QHBoxLayout()
        copy_email_btn = QPushButton("Copy Email")
        copy_email_btn.clicked.connect(lambda: self.copy_to_clipboard(self.auto_credential.text(), "Email"))
        email_row.addWidget(copy_email_btn)

        copy_pass_btn = QPushButton("Copy Pass")
        copy_pass_btn.clicked.connect(lambda: self.copy_to_clipboard(self.auto_pass.text(), "Password"))
        email_row.addWidget(copy_pass_btn)
        btn_layout.addLayout(email_row)

        copy_all_btn = QPushButton("📋 Copy All Data")
        copy_all_btn.setObjectName("primary")
        copy_all_btn.clicked.connect(self.copy_all_data)
        btn_layout.addWidget(copy_all_btn)

        extra_row = QHBoxLayout()
        btn_rand = QPushButton("🎲 Generate Random Details")
        btn_rand.setObjectName("primary")
        btn_rand.clicked.connect(self.generate_random_details)
        btn_grab = QPushButton("Grab Cookies")
        btn_grab.clicked.connect(self.grab_browser_cookies)
        extra_row.addWidget(btn_rand)
        extra_row.addWidget(btn_grab)
        btn_layout.addLayout(extra_row)

        left_layout.addWidget(btn_box)

        self.btn_fill_now = QPushButton("Force React Auto-Fill & Submit")
        self.btn_fill_now.setObjectName("primary")
        self.btn_fill_now.clicked.connect(self.execute_autofill_script)
        left_layout.addWidget(self.btn_fill_now)

        self.lbl_timer_status = QLabel("Popup Skip Timer: Idle", objectName="notice")
        left_layout.addWidget(self.lbl_timer_status)
        left_layout.addStretch(1)

        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.preview_back = QPushButton("←")
        self.preview_forward = QPushButton("→")
        self.preview_reload = QPushButton("↻")
        self.preview_url = QLineEdit("https://www.facebook.com/")
        self.preview_url.returnPressed.connect(self.navigate_preview)
        
        go = QPushButton("Go"); go.setObjectName("primary"); go.clicked.connect(self.navigate_preview)
        clear = QPushButton("Clear Data"); clear.clicked.connect(self.clear_tool_browser_data)
        
        self.btn_change = QPushButton("Change (Start)")
        self.btn_change.setObjectName("primary")
        self.btn_change.clicked.connect(self.change_and_restart_automation)

        self.btn_start = QPushButton("▶ Start")
        self.btn_start.setObjectName("primary")
        self.btn_start.setToolTip("Start automation on current Sign-Up / Sign-In page")
        self.btn_start.clicked.connect(self.start_automation_now)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setObjectName("primary")
        self.btn_pause.setToolTip("Pause all automation (fill, resend, redirect)")
        self.btn_pause.clicked.connect(self.pause_automation)

        self.btn_resume = QPushButton("⏵ Resume")
        self.btn_resume.setObjectName("primary")
        self.btn_resume.setToolTip("Resume paused automation")
        self.btn_resume.clicked.connect(self.resume_automation)

        for x in (self.preview_back, self.preview_forward, self.preview_reload, self.preview_url, go, clear,
                  self.btn_change, self.btn_start, self.btn_pause, self.btn_resume):
            bar.addWidget(x)
        right_layout.addLayout(bar)

        self.web_profile = QWebEngineProfile("SkyPilotIsolatedProfile", self)
        self.web_profile.setPersistentStoragePath(str(TOOL_BROWSER_DIR / "storage"))
        self.web_profile.setCachePath(str(TOOL_BROWSER_DIR / "cache"))
        self.web_profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self.web_profile.setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        self.web = QWebEngineView()
        self.web_page = QWebEnginePage(self.web_profile, self.web)
        
        self.web_page.settings().setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        self.web_page.settings().setAttribute(QWebEngineSettings.AutoLoadImages, True)
        self.web_page.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        
        self.web.setPage(self.web_page)
        self.web.setZoomFactor(0.95)

        self.preview_back.clicked.connect(self.web.back)
        self.preview_forward.clicked.connect(self.web.forward)
        self.preview_reload.clicked.connect(self.handle_manual_reload)

        self.web.urlChanged.connect(lambda u: self.preview_url.setText(u.toString()))
        self.web.loadFinished.connect(self.preview_load_finished)

        right_layout.addWidget(self.web, 1)
        splitter.addWidget(right_widget)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        return w

    def handle_manual_reload(self):
        self.web.reload()
        self.statusBar().showMessage("Page Reloaded • Restarting Auto-Fill Process...", 3000)

    def grab_browser_cookies(self):
        """Manual grab: only fills Cookies/UID when real c_user session exists."""
        self.capture_account_session_data()


    def generate_random_details(self):
        """Fill left panel with a fresh random female American profile."""
        female_firsts = [
            "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen",
            "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle"
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
        ]
        fn = secrets.choice(female_firsts)
        ln = secrets.choice(last_names)
        mode = "email"
        if hasattr(self, "contact_mode") and "email" not in self.contact_mode.currentText().lower():
            mode = "phone"
        source = "random"
        if hasattr(self, "contact_source"):
            source = self.contact_source.currentText().lower()
        cred = None
        if "list" in source:
            cred = self.store.next_contact(mode)
            if not cred:
                self.statusBar().showMessage(f"No {mode} left in list — falling back to random", 4000)
        if not cred and "manual" in source:
            # keep existing typed value if any
            cred = self.auto_credential.text().strip() or None
        if not cred:
            if mode == "phone":
                cred = f"+1{secrets.randbelow(8999999999)+1000000000}"
            else:
                cred = f"{fn.lower()}.{ln.lower()}{secrets.randbelow(8999)+1000}@gmail.com"
        pw = f"{fn}@{ln}{secrets.randbelow(8999)+1000}!"
        self.auto_fname.setText(fn)
        self.auto_lname.setText(ln)
        self.auto_credential.setText(cred)
        self.auto_pass.setText(pw)
        if hasattr(self, "auto_gender"):
            self.auto_gender.setCurrentText("Female")
        self.btn_uid.clear()
        self.btn_cookies.clear()
        self.btn_token.clear()
        self.statusBar().showMessage(f"Random details: {fn} {ln} / {cred}", 4000)
        if hasattr(self, "refresh_contact_stats_label"):
            self.refresh_contact_stats_label()

    def copy_to_clipboard(self, text, field_name):

        if text.strip():
            clipboard = QApplication.clipboard()
            clipboard.setText(text.strip())
            self.statusBar().showMessage(f"{field_name} copied to clipboard!", 3000)
        else:
            QMessageBox.warning(self, "Empty Field", f"No {field_name} available to copy.")

    def copy_all_data(self):
        all_text = f"First Name: {self.auto_fname.text()}\n" \
                   f"Last Name: {self.auto_lname.text()}\n" \
                   f"Email/Mobile: {self.auto_credential.text()}\n" \
                   f"Password: {self.auto_pass.text()}\n" \
                   f"UID: {self.btn_uid.text()}\n" \
                   f"Cookies: {self.btn_cookies.text()}\n" \
                   f"Token: {self.btn_token.text()}"
        clipboard = QApplication.clipboard()
        clipboard.setText(all_text)
        self.statusBar().showMessage("All created data copied to clipboard!", 3000)

    def page_profiles(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(self.header("Profile Manager", "Local profiles + quick actions for account creation data."))
        box = QGroupBox("New Profile"); f = QFormLayout(box)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(6)
        self.first = QLineEdit(); self.last = QLineEdit(); self.email = QLineEdit(); self.notes = QLineEdit()
        f.addRow("First name", self.first); f.addRow("Last name", self.last)
        f.addRow("Email", self.email); f.addRow("Notes", self.notes)
        save = QPushButton("Save Profile"); save.setObjectName("primary"); save.clicked.connect(self.save_profile)
        f.addRow("", save)
        l.addWidget(box)

        actions = QHBoxLayout()
        btn_load = QPushButton("Load selected → Smart Setup")
        btn_load.clicked.connect(self.load_profile_to_setup)
        btn_del = QPushButton("Delete selected")
        btn_del.clicked.connect(self.delete_selected_profile)
        btn_exp = QPushButton("Export profiles CSV")
        btn_exp.clicked.connect(self.export_profiles_csv)
        actions.addWidget(btn_load); actions.addWidget(btn_del); actions.addWidget(btn_exp)
        l.addLayout(actions)

        self.profile_table = QTableWidget(0, 5)
        self.profile_table.setHorizontalHeaderLabels(["ID", "Created", "First Name", "Last Name", "Email"])
        self.profile_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.profile_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.profile_table.setSelectionBehavior(QTableWidget.SelectRows)
        l.addWidget(self.profile_table, 1)
        return w

    def load_profile_to_setup(self):
        rows = self.profile_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Profile", "Select a profile row first.")
            return
        r = rows[0].row()
        fn = self.profile_table.item(r, 2).text() if self.profile_table.item(r, 2) else ""
        ln = self.profile_table.item(r, 3).text() if self.profile_table.item(r, 3) else ""
        em = self.profile_table.item(r, 4).text() if self.profile_table.item(r, 4) else ""
        self.auto_fname.setText(fn)
        self.auto_lname.setText(ln)
        self.auto_credential.setText(em)
        if hasattr(self, "contact_source"):
            self.contact_source.setCurrentText("Manual (type yourself)")
        self.nav.setCurrentRow(2)
        self.statusBar().showMessage(f"Loaded profile {fn} {ln} into Smart Setup", 4000)

    def delete_selected_profile(self):
        rows = self.profile_table.selectionModel().selectedRows()
        if not rows:
            return
        ids = []
        for idx in rows:
            item = self.profile_table.item(idx.row(), 0)
            if item:
                ids.append(int(item.text()))
        if not ids:
            return
        with self.store.connect() as con:
            for i in ids:
                con.execute("DELETE FROM profiles WHERE id=?", (i,))
        self.refresh_profiles()
        self.statusBar().showMessage(f"Deleted {len(ids)} profile(s)", 3000)

    def export_profiles_csv(self):
        rows = self.store.profiles()
        path, _ = QFileDialog.getSaveFileName(self, "Export Profiles", str(EXPORT_DIR / "profiles.csv"), "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "created_at", "first_name", "last_name", "email", "notes"])
            for r in rows:
                w.writerow([r["id"], r["created_at"], r["first_name"], r["last_name"], r["email"], r["notes"]])
        QMessageBox.information(self, "Export", f"Saved: {path}")


    def page_generator(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(self.header("Data Generator","Generate synthetic values."))
        box=QGroupBox("Password Generator"); pf=QFormLayout(box)
        pf.setContentsMargins(8, 8, 8, 8)
        pf.setSpacing(6)
        self.pw_len=QSpinBox(); self.pw_len.setRange(12,64); self.pw_len.setValue(16)
        self.pw_out=QLineEdit(); self.pw_out.setReadOnly(True)
        make=QPushButton("Generate Password"); make.clicked.connect(self.generate_password)
        pf.addRow("Length",self.pw_len); pf.addRow("Password",self.pw_out); pf.addRow("",make)
        l.addWidget(box); l.addStretch()
        return w

    def page_workflow(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(self.header("Workflow Runner","Run a real HTTP availability check."))
        self.check_url=QLineEdit("https://facebook.com/")
        run=QPushButton("Run Check"); run.setObjectName("primary"); run.clicked.connect(self.run_url_check)
        l.addWidget(self.check_url); l.addWidget(run)
        self.check_output=QTextEdit(); self.check_output.setReadOnly(True); l.addWidget(self.check_output,1)
        return w

    def page_adb(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(self.header("Android / ADB Device Center","Connect Android emulator or physical device."))
        self.adb_output=QTextEdit(); self.adb_output.setReadOnly(True)
        l.addWidget(self.adb_output,1)
        return w

    def page_monitor(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(self.header("System Monitor","Live system resource usage."))
        grid=QGridLayout()
        grid.setSpacing(8)
        self.cpu=self.metric_card("CPU","—"); self.ram=self.metric_card("RAM","—")
        grid.addWidget(self.cpu, 0, 0); grid.addWidget(self.ram, 0, 1)
        l.addLayout(grid); l.addStretch()
        return w

    def page_logs(self):
        w=QWidget(); l=QVBoxLayout(w)
        l.addWidget(self.header("Activity Logs","Logged system tasks."))
        self.log_table=QTableWidget(0,5); self.log_table.setHorizontalHeaderLabels(["ID","Time","Category","Message","Status"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l.addWidget(self.log_table,1)
        return w

    def page_backup(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(self.header("Backup Center", "Account history, export, search, delete."))

        # Search + actions
        top = QHBoxLayout()
        self.backup_search = QLineEdit(); self.backup_search.setPlaceholderText("Search name / email / phone / UID...")
        self.backup_search.returnPressed.connect(self.refresh_accounts_table)
        btn_search = QPushButton("Search"); btn_search.clicked.connect(self.refresh_accounts_table)
        top.addWidget(self.backup_search, 1); top.addWidget(btn_search)
        l.addLayout(top)

        self.accounts_table = QTableWidget(0, 9)
        self.accounts_table.setHorizontalHeaderLabels([
            "ID", "Created", "First", "Last", "Contact", "Password", "Gender", "DOB", "UID"
        ])
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.accounts_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.accounts_table.setEditTriggers(QTableWidget.NoEditTriggers)
        l.addWidget(self.accounts_table, 1)

        actions = QHBoxLayout()
        btn_refresh = QPushButton("Refresh"); btn_refresh.clicked.connect(self.refresh_accounts_table)
        btn_export_csv = QPushButton("Export CSV"); btn_export_csv.setObjectName("primary"); btn_export_csv.clicked.connect(lambda: self.export_accounts("csv"))
        btn_export_xlsx = QPushButton("Export Excel"); btn_export_xlsx.clicked.connect(lambda: self.export_accounts("xlsx"))
        btn_del_sel = QPushButton("Delete Selected"); btn_del_sel.clicked.connect(self.delete_selected_accounts)
        btn_clear = QPushButton("Clear All History"); btn_clear.clicked.connect(self.clear_all_accounts)
        btn_db_bak = QPushButton("DB Backup"); btn_db_bak.clicked.connect(self.create_backup)
        for b in (btn_refresh, btn_export_csv, btn_export_xlsx, btn_del_sel, btn_clear, btn_db_bak):
            actions.addWidget(b)
        l.addLayout(actions)
        return w

    def refresh_accounts_table(self):
        if not hasattr(self, "accounts_table"):
            return
        q = self.backup_search.text().strip() if hasattr(self, "backup_search") else ""
        rows = self.store.accounts(q)
        self.accounts_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["id"], row["created_at"], row["first_name"], row["last_name"],
                    row["contact"], row["password"], row["gender"], row["dob"], row["uid"]]
            for c, v in enumerate(vals):
                self.accounts_table.setItem(r, c, QTableWidgetItem(str(v or "")))

    def delete_selected_accounts(self):
        rows = self.accounts_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Delete", "Select one or more rows first.")
            return
        ids = []
        for idx in rows:
            item = self.accounts_table.item(idx.row(), 0)
            if item:
                ids.append(int(item.text()))
        if not ids:
            return
        reply = QMessageBox.question(self, "Confirm", f"Delete {len(ids)} account record(s)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.store.delete_accounts(ids)
            self.refresh_accounts_table()
            self.statusBar().showMessage(f"Deleted {len(ids)} records", 3000)

    def clear_all_accounts(self):
        reply = QMessageBox.question(self, "Confirm", "Clear ALL account history?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.store.clear_accounts()
            self.refresh_accounts_table()
            self.statusBar().showMessage("All account history cleared", 3000)

    def export_accounts(self, fmt="csv"):
        rows = self.store.accounts()
        if not rows:
            QMessageBox.information(self, "Export", "No records to export.")
            return
        if fmt == "csv":
            path, _ = QFileDialog.getSaveFileName(self, "Export CSV", str(EXPORT_DIR / "accounts.csv"), "CSV (*.csv)")
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id","created_at","first_name","last_name","contact","password","gender","dob","uid","contact_type","status"])
                for r in rows:
                    w.writerow([r["id"], r["created_at"], r["first_name"], r["last_name"], r["contact"],
                                r["password"], r["gender"], r["dob"], r["uid"], r["contact_type"], r["status"]])
            QMessageBox.information(self, "Export", f"Saved: {path}")
        else:
            # Excel via csv fallback if openpyxl not present, or simple xlsx-compatible csv
            path, _ = QFileDialog.getSaveFileName(self, "Export Excel/CSV", str(EXPORT_DIR / "accounts.xlsx.csv"), "CSV for Excel (*.csv)")
            if not path:
                return
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["id","created_at","first_name","last_name","contact","password","gender","dob","uid","contact_type","status"])
                for r in rows:
                    w.writerow([r["id"], r["created_at"], r["first_name"], r["last_name"], r["contact"],
                                r["password"], r["gender"], r["dob"], r["uid"], r["contact_type"], r["status"]])
            QMessageBox.information(self, "Export", f"Saved (Excel-compatible CSV): {path}")


    def page_settings(self):
        w = QWidget(); l = QVBoxLayout(w)
        l.addWidget(self.header("Settings", "Application Configuration & Branding"))

        box = QGroupBox("Branding Settings")
        f = QFormLayout(box)
        f.setContentsMargins(8, 8, 8, 8)
        f.setSpacing(6)
        self.setting_app_name = QLineEdit(self.current_app_title)
        save_btn = QPushButton("Save & Update App Name")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save_app_settings)
        f.addRow("Application Name", self.setting_app_name)
        f.addRow("", save_btn)
        l.addWidget(box)

        box2 = QGroupBox("Automation Defaults")
        f2 = QFormLayout(box2)
        f2.setContentsMargins(8, 8, 8, 8)
        self.set_resend_email = QSpinBox(); self.set_resend_email.setRange(0, 20)
        self.set_resend_email.setValue(int(self.store.get_setting("resend_email_times", "2") or "2"))
        self.set_resend_phone = QSpinBox(); self.set_resend_phone.setRange(0, 30)
        self.set_resend_phone.setValue(int(self.store.get_setting("resend_phone_times", "8") or "8"))
        self.set_api_key = QLineEdit(self.store.get_setting("api_key", ""))
        self.set_api_key.setEchoMode(QLineEdit.Password)
        self.set_api_key.setPlaceholderText("Optional SMS / Email / Telegram API key")
        self.set_api_endpoint = QLineEdit(self.store.get_setting("api_endpoint", ""))
        self.set_api_endpoint.setPlaceholderText("https://provider.example/api/get-number")
        save2 = QPushButton("Save Automation Settings")
        save2.setObjectName("primary")
        def _save_auto():
            self.store.set_setting("resend_email_times", str(self.set_resend_email.value()))
            self.store.set_setting("resend_phone_times", str(self.set_resend_phone.value()))
            self.store.set_setting("api_key", self.set_api_key.text().strip())
            self.store.set_setting("api_endpoint", self.set_api_endpoint.text().strip())
            if hasattr(self, "spin_resend_email"):
                self.spin_resend_email.setValue(self.set_resend_email.value())
            if hasattr(self, "spin_resend_phone"):
                self.spin_resend_phone.setValue(self.set_resend_phone.value())
            if hasattr(self, "api_key_edit"):
                self.api_key_edit.setText(self.set_api_key.text())
            QMessageBox.information(self, "Saved", "Automation settings saved.")
        save2.clicked.connect(_save_auto)
        f2.addRow("OTP resend (Email)", self.set_resend_email)
        f2.addRow("OTP resend (Phone)", self.set_resend_phone)
        f2.addRow("API Key (optional)", self.set_api_key)
        f2.addRow("API Endpoint URL", self.set_api_endpoint)
        f2.addRow("", save2)
        l.addWidget(box2)
        l.addStretch()
        return w


    def save_app_settings(self):
        new_name = self.setting_app_name.text().strip()
        if new_name:
            self.store.set_setting("app_name", new_name)
            self.current_app_title = new_name
            self.setWindowTitle(f"{self.current_app_title}  |  {APP_VERSION}")
            self.brand_text.setText(new_name)
            QMessageBox.information(self, "Settings Saved", "Application name updated successfully!")
        else:
            QMessageBox.warning(self, "Invalid Name", "App name cannot be empty.")

    def apply_style(self):
        self.setStyleSheet("""
        QWidget {
            background: #F5F8FF;
            color: #0F172A;
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 9.5pt;
        }
        QMainWindow, QStatusBar {
            background: #F5F8FF;
        }
        #sidebar {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
        }
        #brandFrame {
            background: transparent;
            border: none;
            padding: 4px;
        }
        #fbLogoIcon {
            color: #FFFFFF;
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4B9BFF, stop:0.5 #2563EB, stop:1 #1D4ED8);
            font-size: 18pt;
            font-weight: 900;
            font-family: Helvetica, Arial, sans-serif;
            border-radius: 10px;
            min-width: 34px;
            min-height: 34px;
            max-width: 34px;
            max-height: 34px;
            padding: 0px;
            qproperty-alignment: AlignCenter;
            border: 1px solid #1D4ED8;
        }
        #brand {
            font-size: 17pt;
            font-weight: 800;
            font-family: Helvetica, Arial, sans-serif;
            color: #2563EB;
            background: transparent;
            letter-spacing: -0.6px;
        }
        #smallMuted, #muted {
            color: #475569;
            font-size: 8.5pt;
            font-weight: 600;
        }
        #navigation {
            background: transparent;
            border: 0;
            outline: 0;
        }
        #navigation::item {
            padding: 10px 12px;
            margin: 3px 4px;
            border-radius: 10px;
            color: #475569;
            font-weight: 600;
        }
        #navigation::item:hover {
            background: #EFF6FF;
            color: #1E40AF;
        }
        #navigation::item:selected {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2563EB, stop:1 #3B82F6);
            color: #FFFFFF;
            font-weight: 700;
        }
        #pageTitle {
            color: #0F172A;
            font-size: 18pt;
            font-weight: 800;
            letter-spacing: -0.6px;
        }
        #card, QGroupBox {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
        }
        #card {
            min-height: 78px;
        }
        #metric {
            color: #2563EB;
            font-size: 20pt;
            font-weight: 800;
        }
        QGroupBox {
            margin-top: 10px;
            padding-top: 14px;
            font-weight: 700;
            color: #0F172A;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #1E293B;
        }
        QPushButton {
            background: #FFFFFF;
            color: #334155;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 7px 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background: #F8FAFC;
            border-color: #CBD5E1;
            color: #0F172A;
        }
        QPushButton:pressed {
            background: #E2E8F0;
        }
        QPushButton#primary {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #2563EB, stop:1 #3B82F6);
            color: #FFFFFF;
            border: 0;
            padding: 8px 14px;
            font-weight: 700;
            border-radius: 12px;
        }
        QPushButton#primary:hover {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1D4ED8, stop:1 #2563EB);
        }
        QPushButton#primary:pressed {
            background: #1E40AF;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 6px 10px;
            color: #0F172A;
            selection-background-color: #BFDBFE;
        }
        QLineEdit:disabled, QComboBox:disabled {
            color: #334155;
            background: #F8FAFC;
        }
        QFormLayout QLabel, QGroupBox QLabel {
            color: #1E293B;
            font-weight: 600;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
            border: 1.5px solid #2563EB;
            background: #F8FBFF;
        }
        QComboBox::drop-down {
            border: none;
            width: 22px;
        }
        QTableWidget {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            gridline-color: #F1F5F9;
            alternate-background-color: #F8FAFC;
        }
        QHeaderView::section {
            background: #F8FAFC;
            color: #475569;
            padding: 7px;
            border: none;
            border-bottom: 1px solid #E2E8F0;
            font-weight: 700;
        }
        #notice {
            background: #EFF6FF;
            color: #1D4ED8;
            border: 1px solid #BFDBFE;
            border-radius: 10px;
            padding: 8px 12px;
            font-weight: 600;
        }
        QStatusBar {
            background: #FFFFFF;
            color: #64748B;
            border-top: 1px solid #E2E8F0;
            font-weight: 500;
        }
        QScrollArea {
            background: transparent;
            border: none;
        }
        QScrollBar:vertical {
            width: 8px;
            background: transparent;
            margin: 2px;
        }
        QScrollBar::handle:vertical {
            background: #CBD5E1;
            border-radius: 4px;
            min-height: 28px;
        }
        QScrollBar::handle:vertical:hover {
            background: #94A3B8;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0;
        }
        QCheckBox {
            spacing: 8px;
            color: #334155;
            font-weight: 600;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1.5px solid #CBD5E1;
            background: #FFFFFF;
        }
        QCheckBox::indicator:checked {
            background: #2563EB;
            border-color: #2563EB;
        }
        QSplitter::handle {
            background: #E2E8F0;
            width: 3px;
            border-radius: 2px;
        }
        QMessageBox {
            background: #FFFFFF;
        }
        """)

    def change_page(self,index):
        current_widget = self.stack.currentWidget()
        if current_widget:
            opacity = QGraphicsOpacityEffect(current_widget)
            current_widget.setGraphicsEffect(opacity)
            self.anim = QPropertyAnimation(opacity, b"opacity")
            self.anim.setDuration(150)
            self.anim.setStartValue(1.0)
            self.anim.setEndValue(0.4)
            self.anim.setEasingCurve(QEasingCurve.InOutQuad)
            self.anim.start()

        self.stack.setCurrentIndex(index)
        
        new_widget = self.stack.currentWidget()
        if new_widget:
            opacity_new = QGraphicsOpacityEffect(new_widget)
            new_widget.setGraphicsEffect(opacity_new)
            self.anim_in = QPropertyAnimation(opacity_new, b"opacity")
            self.anim_in.setDuration(180)
            self.anim_in.setStartValue(0.2)
            self.anim_in.setEndValue(1.0)
            self.anim_in.setEasingCurve(QEasingCurve.OutCubic)
            self.anim_in.start()

        if index == 2 and not self.web.url().isValid():
            self.web.setUrl(QUrl("https://www.facebook.com/"))
        if index == 9:  # Backup Center
            try:
                self.refresh_accounts_table()
            except Exception:
                pass
        self.statusBar().showMessage(self.pages[index],3000)

    def navigate_preview(self):
        try: url=normalize_url(self.preview_url.text())
        except ValueError as e: QMessageBox.warning(self,"URL error",str(e)); return
        self.web.setUrl(QUrl(url))

    def preview_load_finished(self, ok):
        self.statusBar().showMessage("Page loaded successfully" if ok else "Page load error", 4000)
        if not ok:
            return
        current_url = self.web.url().toString().lower()

        # OTP / confirmation — stay, never redirect
        block_keywords = [
            "confirmemail", "confirm", "checkpoint", "two_step", "otp",
            "recovery", "identify", "login/identify", "approvals"
        ]
        if any(k in current_url for k in block_keywords):
            self.statusBar().showMessage("Confirmation / OTP page — staying (no reload)", 5000)
            # Try capture real session cookies/UID on confirm page too
            QTimer.singleShot(1500, self.capture_account_session_data)
            QTimer.singleShot(8000, self.capture_account_session_data)
            if "confirm" in current_url or "code" in current_url:
                if not getattr(self, "_paused", False):
                    QTimer.singleShot(2000, self.handle_otp_resend_flow)
            return

        # Sign-up page → only autofill if user already pressed Start (not blocked)
        if "/r.php" in current_url or "signup" in current_url or "/reg/" in current_url:
            if getattr(self, "_startup_block_autofill", False):
                self.statusBar().showMessage("Sign-Up loaded — waiting for ▶ Start (or grace period)", 4000)
                return
            css_fit = """
            (function(){
                let style = document.createElement('style');
                style.innerHTML = 'body { zoom: 95% !important; max-width: 100vw !important; overflow-x: hidden !important; }';
                document.head.appendChild(style);
            })();
            """
            self.web.page().runJavaScript(css_fit)
            QTimer.singleShot(1500, self.execute_autofill_script)
            self.start_popup_countdown()
            return

        # Landing / login page: NO auto-redirect on first open (1 min grace) or after clear
        if "facebook.com" in current_url:
            if getattr(self, "_startup_block_autofill", True):
                # First open or after clear — do not auto go to r.php
                left = getattr(self, "_startup_grace_left", 60)
                self.statusBar().showMessage(
                    f"Sign-in page. Setup time ~{left}s left. Import/configure then press ▶ Start.", 5000
                )
                return
            # User already started once — optional soft redirect after 5s
            self.statusBar().showMessage("Landing page. Opening Sign-Up in 5s (or press ▶ Start)...", 5000)
            QTimer.singleShot(5000, lambda: self.web.setUrl(QUrl("https://www.facebook.com/r.php")))


    def check_and_autofill_page(self):
        if self.stack.currentIndex() != 2:
            return
        if getattr(self, "_paused", False):
            return
        if getattr(self, "_startup_block_autofill", False):
            return
        try:
            url = self.web.url().toString().lower()
        except Exception:
            return
        # Never autofill on confirmation / OTP pages
        if any(k in url for k in ("confirmemail", "confirm", "checkpoint", "otp", "code", "recovery")):
            return

        check_js = """
        (function(){
            if (window.__skypilot_autofilled) return false;
            let inputs = document.querySelectorAll('input');
            let isSignUp = false;
            for (let input of inputs) {
                let name = (input.name || '').toLowerCase();
                let aria = (input.getAttribute('aria-label') || '').toLowerCase();
                let ph = (input.placeholder || '').toLowerCase();
                if (name.includes('firstname') || name.includes('lastname') || name.includes('reg_email')
                    || aria.includes('first name') || aria.includes('surname')
                    || ph.includes('first name') || ph.includes('surname')) {
                    isSignUp = true;
                    break;
                }
            }
            return isSignUp;
        })();
        """
        def handle_check_res(res):
            if res:
                self.execute_autofill_script()

        self.web.page().runJavaScript(check_js, handle_check_res)

    def execute_autofill_script(self):
        if getattr(self, "_paused", False):
            self.statusBar().showMessage("Paused — fill skipped", 3000)
            return
        female_firsts = [
            "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen",
            "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna", "Michelle"
        ]
        last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
            "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
        ]

        fn = self.auto_fname.text().strip() or secrets.choice(female_firsts)
        ln = self.auto_lname.text().strip() or secrets.choice(last_names)
        
        # জেন্ডার সবসময় Female সেট করা (value="1")
        gender_val = "1"

        # Contact: respect type (Email/Phone) + source (Random / List / Manual)
        mode = "email"
        if hasattr(self, "contact_mode") and "email" not in self.contact_mode.currentText().lower():
            mode = "phone"
        source = "random"
        if hasattr(self, "contact_source"):
            source = self.contact_source.currentText().lower()
        cred = self.auto_credential.text().strip()
        if "manual" in source:
            if not cred:
                # nothing typed — fall back
                cred = None
        elif "list" in source:
            pooled = self.store.next_contact(mode)
            cred = pooled or None
        else:
            # random always generates fresh unless user already typed and wants to keep
            cred = None
        if not cred:
            if mode == "phone":
                cred = f"+1{secrets.randbelow(8999999999)+1000000000}"
            else:
                cred = f"{fn.lower()}.{ln.lower()}{secrets.randbelow(8999)+1000}@gmail.com"
        self.auto_credential.setText(cred)

        raw_pw = self.auto_pass.text().strip()
        if not raw_pw:
            pw = f"{fn}@{ln}{secrets.randbelow(8999)+1000}!"
        else:
            pw = raw_pw
        self.auto_pass.setText(pw)

        # UID/cookies/token only filled from real session after account exists (capture_account_session_data)
        self.btn_uid.clear()
        self.btn_cookies.clear()
        self.btn_token.clear()

        target_day = self.sel_day.currentText()
        target_month_str = self.sel_month.currentText()
        month_map = {"Jan": "1", "Feb": "2", "Mar": "3", "Apr": "4", "May": "5", "Jun": "6", 
                     "Jul": "7", "Aug": "8", "Sep": "9", "Oct": "10", "Nov": "11", "Dec": "12",
                     "April": "4", "May": "5", "March": "3"}
        target_month = month_map.get(target_month_str, "5")
        target_year = self.sel_year.currentText()

        # Strong React + new Meta form autofill — NO scrolling — fill by position + label
        gender_text = self.auto_gender.currentText().strip() or "Female"
        # Ensure left panel shows the values we will fill
        self.auto_fname.setText(fn)
        self.auto_lname.setText(ln)
        fill_js = f"""
        (function(){{
            if (window.__skypilot_paused) return;
            if (window.__skypilot_autofilled) return;
            window.__skypilot_autofilled = true;

            function visible(el) {{
                if (!el) return false;
                let s = window.getComputedStyle(el);
                return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetParent !== null;
            }}

            // Character-by-character React-safe typing
            function typeText(el, text) {{
                if (!el || text == null) return false;
                text = String(text);
                el.focus();
                el.click();
                try {{ el.select(); }} catch(e){{}}

                let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                if (setter) setter.call(el, '');
                else el.value = '';
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));

                let cur = '';
                for (let i = 0; i < text.length; i++) {{
                    cur += text[i];
                    if (setter) setter.call(el, cur);
                    else el.value = cur;
                    el.dispatchEvent(new InputEvent('input', {{
                        bubbles: true, cancelable: true,
                        data: text[i], inputType: 'insertText'
                    }}));
                }}
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                el.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: 'a' }}));
                // final force
                if (setter) setter.call(el, text);
                else el.value = text;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                return true;
            }}

            function matchText(el, texts) {{
                let ph = (el.placeholder || '').toLowerCase();
                let al = (el.getAttribute('aria-label') || '').toLowerCase();
                let nm = (el.name || '').toLowerCase();
                for (let t of texts) {{
                    let tl = t.toLowerCase();
                    if (ph.indexOf(tl) !== -1 || al.indexOf(tl) !== -1 || nm.indexOf(tl) !== -1) return true;
                }}
                return false;
            }}

            function findByLabel(texts) {{
                let inputs = Array.from(document.querySelectorAll('input'));
                for (let inp of inputs) {{
                    if (visible(inp) && matchText(inp, texts)) return inp;
                }}
                return null;
            }}

            function clickOption(texts) {{
                let opts = document.querySelectorAll('[role="option"], [role="menuitem"], li, div[tabindex="0"], span[role="option"]');
                for (let opt of opts) {{
                    let t = (opt.textContent || '').trim().toLowerCase();
                    for (let w of texts) {{
                        if (t === w.toLowerCase()) {{ opt.click(); return true; }}
                    }}
                }}
                for (let opt of opts) {{
                    let t = (opt.textContent || '').trim().toLowerCase();
                    for (let w of texts) {{
                        if (t.indexOf(w.toLowerCase()) !== -1) {{ opt.click(); return true; }}
                    }}
                }}
                return false;
            }}

            // Collect all visible text-like inputs in document order
            function getTextInputs() {{
                return Array.from(document.querySelectorAll('input')).filter(function(el) {{
                    if (!visible(el)) return false;
                    let ty = (el.type || 'text').toLowerCase();
                    return ty === 'text' || ty === 'email' || ty === 'tel' || ty === '' || !el.type;
                }});
            }}

            // ========== FILL ==========

            // 1 + 2: First name & Surname by label OR by position (first two text inputs)
            setTimeout(function() {{
                let first = findByLabel(['First name', 'firstname', 'first name', 'given-name']);
                let last  = findByLabel(['Surname', 'Last name', 'lastname', 'last name', 'family-name']);

                if (!first || !last) {{
                    let texts = getTextInputs();
                    // exclude ones that look like email
                    let nameCandidates = texts.filter(function(el) {{
                        return !matchText(el, ['email', 'mobile', 'phone', 'password']);
                    }});
                    if (!first && nameCandidates[0]) first = nameCandidates[0];
                    if (!last  && nameCandidates[1]) last  = nameCandidates[1];
                }}

                if (first) typeText(first, "{fn}");
                if (last)  typeText(last,  "{ln}");
            }}, 400);

            // 3: Email / Mobile
            setTimeout(function() {{
                let el = findByLabel([
                    'Mobile number or email address',
                    'Mobile number or email',
                    'email address',
                    'Mobile number',
                    'email',
                    'phone'
                ]);
                if (!el) {{
                    // any remaining empty text input that is not name
                    let texts = getTextInputs();
                    for (let t of texts) {{
                        if (!t.value && matchText(t, ['email', 'mobile', 'phone'])) {{ el = t; break; }}
                    }}
                    if (!el) {{
                        for (let t of texts) {{
                            if (!t.value) {{ el = t; break; }}  // last empty text field
                        }}
                    }}
                }}
                if (el) typeText(el, "{cred}");
            }}, 1000);

            // 4: Confirm email if appears
            setTimeout(function() {{
                let el = findByLabel(['Re-enter', 'confirm email', 'Confirm email']);
                if (el) typeText(el, "{cred}");
            }}, 1500);

            // 5: Password
            setTimeout(function() {{
                let el = findByLabel(['Password', 'New password', 'password']) ||
                         document.querySelector('input[type="password"]');
                if (el && visible(el)) typeText(el, "{pw}");
            }}, 2000);

            // ---- Birthday Month / Day / Year (Meta custom dropdowns) ----
            function bdayControls() {{
                // Prefer controls under a "Birthday" / "Date of birth" heading
                let labels = Array.from(document.querySelectorAll('label, span, div, legend, h1, h2, h3, p'));
                let root = null;
                for (let lb of labels) {{
                    let t = (lb.textContent || '').trim().toLowerCase();
                    if (t === 'birthday' || t === 'date of birth' || t.indexOf('birthday') === 0) {{
                        root = lb.closest('form') || lb.parentElement || lb;
                        // climb a few levels for the field group
                        for (let i = 0; i < 4 && root; i++) {{
                            let count = root.querySelectorAll('[role="button"], [role="combobox"], select').length;
                            if (count >= 3) break;
                            root = root.parentElement;
                        }}
                        break;
                    }}
                }}
                let scope = root || document;
                let cands = Array.from(scope.querySelectorAll('[role="button"], [role="combobox"], select, [aria-haspopup="listbox"]'));
                // filter visible
                cands = cands.filter(function(el) {{
                    let s = window.getComputedStyle(el);
                    return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetParent !== null;
                }});
                // classify
                let monthEl = null, dayEl = null, yearEl = null;
                let months = {{jan:1,january:1,feb:2,february:2,mar:3,march:3,apr:4,april:4,may:5,jun:6,june:6,jul:7,july:7,aug:8,august:8,sep:9,september:9,oct:10,october:10,nov:11,november:11,dec:12,december:12}};
                for (let el of cands) {{
                    let al = (el.getAttribute('aria-label') || '').toLowerCase();
                    let name = (el.getAttribute('name') || '').toLowerCase();
                    let id = (el.id || '').toLowerCase();
                    let txt = (el.textContent || '').replace(/\\s+/g,' ').trim();
                    let tl = txt.toLowerCase();
                    if (!monthEl && (al.indexOf('month') !== -1 || name.indexOf('month') !== -1 || id === 'month' || tl === 'month' || months[tl])) monthEl = el;
                    else if (!dayEl && (al.indexOf('day') !== -1 || name.indexOf('day') !== -1 || id === 'day' || tl === 'day' || (/^\\d{{1,2}}$/.test(txt) && +txt <= 31))) dayEl = el;
                    else if (!yearEl && (al.indexOf('year') !== -1 || name.indexOf('year') !== -1 || id === 'year' || tl === 'year' || /^\\d{{4}}$/.test(txt))) yearEl = el;
                }}
                // If still missing, take first 3 unlabeled comboboxes in row near birthday
                if ((!monthEl || !dayEl || !yearEl) && cands.length >= 3) {{
                    // geometric: sort by x position
                    let row = cands.map(function(el) {{
                        let r = el.getBoundingClientRect();
                        return {{ el: el, x: r.left, y: r.top, w: r.width }};
                    }}).filter(function(o) {{ return o.w > 40 && o.w < 220; }});
                    row.sort(function(a,b) {{ return a.y - b.y || a.x - b.x; }});
                    // group same row (similar y)
                    if (row.length >= 3) {{
                        let y0 = row[0].y;
                        let same = row.filter(function(o) {{ return Math.abs(o.y - y0) < 30; }});
                        same.sort(function(a,b) {{ return a.x - b.x; }});
                        if (same.length >= 3) {{
                            if (!monthEl) monthEl = same[0].el;
                            if (!dayEl) dayEl = same[1].el;
                            if (!yearEl) yearEl = same[2].el;
                        }}
                    }}
                }}
                return {{ monthEl: monthEl, dayEl: dayEl, yearEl: yearEl }};
            }}

            function openAndPick(el, values, done) {{
                if (!el) {{ if (done) done(false); return; }}
                // Normalize values: "15", 15, "05" etc.
                let vals = [];
                for (let v of values) {{
                    let s = String(v).trim();
                    vals.push(s);
                    if (/^\\d+$/.test(s)) {{
                        vals.push(String(parseInt(s, 10))); // 15
                        if (s.length === 1) vals.push('0' + s);
                    }}
                }}
                values = vals;
                if (el.tagName === 'SELECT') {{
                    let ok = false;
                    for (let v of values) {{
                        el.value = String(v);
                        if (el.value == String(v) || el.value === String(v)) {{ ok = true; break; }}
                        // try option text match
                        for (let i = 0; i < el.options.length; i++) {{
                            let ot = (el.options[i].text || '').trim().toLowerCase();
                            if (ot === String(v).toLowerCase() || el.options[i].value == String(v)) {{
                                el.selectedIndex = i;
                                ok = true;
                                break;
                            }}
                        }}
                        if (ok) break;
                    }}
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    if (done) done(ok);
                    return;
                }}
                el.focus();
                el.click();
                setTimeout(function() {{
                    let opts = document.querySelectorAll('[role="option"], [role="listbox"] [role="option"], ul li, div[role="option"]');
                    let picked = false;
                    for (let v of values) {{
                        let want = String(v).toLowerCase().trim();
                        for (let opt of opts) {{
                            let t = (opt.textContent || '').replace(/\\s+/g,' ').trim().toLowerCase();
                            if (t === want) {{
                                opt.scrollIntoView({{ block: 'nearest' }});
                                opt.click();
                                picked = true;
                                break;
                            }}
                        }}
                        if (picked) break;
                    }}
                    if (!picked) {{
                        for (let v of values) {{
                            let want = String(v).toLowerCase().trim();
                            for (let opt of opts) {{
                                let t = (opt.textContent || '').replace(/\\s+/g,' ').trim().toLowerCase();
                                if (t === want || t.indexOf(want) !== -1) {{
                                    opt.scrollIntoView({{ block: 'nearest' }});
                                    opt.click();
                                    picked = true;
                                    break;
                                }}
                            }}
                            if (picked) break;
                        }}
                    }}
                    // close any leftover list with Escape
                    document.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Escape', bubbles: true }}));
                    if (done) done(picked);
                }}, 500);
            }}

            // Sequence: Month → Day → Year with retries on Day
            setTimeout(function() {{
                let c = bdayControls();
                openAndPick(c.monthEl, ["{target_month_str}", "May", "{target_month}"], function() {{
                    setTimeout(function() {{
                        let c2 = bdayControls();
                        openAndPick(c2.dayEl, ["{target_day}"], function(ok) {{
                            if (!ok) {{
                                // retry Day once more
                                setTimeout(function() {{
                                    let c3 = bdayControls();
                                    // force click any still showing "Day"
                                    let el = c3.dayEl;
                                    if (!el) {{
                                        document.querySelectorAll('[role="button"], [role="combobox"]').forEach(function(n) {{
                                            if ((n.textContent || '').trim().toLowerCase() === 'day') el = n;
                                        }});
                                    }}
                                    openAndPick(el, ["{target_day}"], function() {{
                                        setTimeout(function() {{
                                            let c4 = bdayControls();
                                            openAndPick(c4.yearEl, ["{target_year}"], null);
                                        }}, 700);
                                    }});
                                }}, 600);
                            }} else {{
                                setTimeout(function() {{
                                    let c4 = bdayControls();
                                    openAndPick(c4.yearEl, ["{target_year}"], null);
                                }}, 700);
                            }}
                        }});
                    }}, 700);
                }});
            }}, 2500);

            // 9: Gender — force Female
            setTimeout(function() {{
                let want = "{gender_text}";
                // old radio style
                let val = (want.toLowerCase() === 'female' || want.toLowerCase() === 'woman') ? '1' : '2';
                let radio = document.querySelector('input[name="sex"][value="' + val + '"]');
                if (radio) {{
                    radio.checked = true;
                    radio.click();
                    radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return;
                }}
                // new Meta dropdown — click anything that looks like gender selector
                let candidates = document.querySelectorAll('[role="button"], [aria-haspopup], [role="combobox"], div, span');
                let gBtn = null;
                for (let c of candidates) {{
                    if (!visible(c)) continue;
                    let al = (c.getAttribute('aria-label') || '').toLowerCase();
                    let t  = (c.textContent || '').trim().toLowerCase();
                    if (al.indexOf('gender') !== -1 || t.indexOf('select your gender') !== -1 ||
                        t === 'female' || t === 'male' || t === 'custom' ||
                        (t.indexOf('female') === -1 && t.indexOf('male') === -1 && al.indexOf('sex') !== -1)) {{
                        // prefer the one that says "Select your gender"
                        if (t.indexOf('select your gender') !== -1 || al.indexOf('gender') !== -1) {{
                            gBtn = c;
                            break;
                        }}
                        if (!gBtn) gBtn = c;
                    }}
                }}
                // fallback: look for the empty gender box by nearby label text
                if (!gBtn) {{
                    let labels = document.querySelectorAll('label, span, div, p');
                    for (let lb of labels) {{
                        if ((lb.textContent || '').trim().toLowerCase() === 'gender') {{
                            let parent = lb.parentElement;
                            if (parent) {{
                                let btn = parent.querySelector('[role="button"], [aria-haspopup], [role="combobox"]');
                                if (btn) {{ gBtn = btn; break; }}
                            }}
                        }}
                    }}
                }}
                if (gBtn) {{
                    gBtn.click();
                    setTimeout(function() {{
                        clickOption([want, 'Female', 'Woman', 'female']);
                    }}, 400);
                }}
            }}, 5200);

            // 9b: Final DOB verification — if Day still blank, force again
            setTimeout(function() {{
                try {{
                    let c = bdayControls();
                    let dayTxt = c.dayEl ? (c.dayEl.textContent || '').replace(/\\s+/g,' ').trim().toLowerCase() : '';
                    let monTxt = c.monthEl ? (c.monthEl.textContent || '').replace(/\\s+/g,' ').trim().toLowerCase() : '';
                    let yrTxt = c.yearEl ? (c.yearEl.textContent || '').replace(/\\s+/g,' ').trim().toLowerCase() : '';
                    let needDay = !dayTxt || dayTxt === 'day' || dayTxt.indexOf('day') === 0;
                    let needMon = !monTxt || monTxt === 'month';
                    let needYr = !yrTxt || yrTxt === 'year';
                    function chain() {{
                        if (needMon) {{
                            openAndPick(c.monthEl, ["{target_month_str}", "May", "{target_month}"], function() {{
                                needMon = false;
                                setTimeout(chain, 600);
                            }});
                            return;
                        }}
                        if (needDay) {{
                            openAndPick(c.dayEl, ["{target_day}"], function() {{
                                needDay = false;
                                setTimeout(chain, 600);
                            }});
                            return;
                        }}
                        if (needYr) {{
                            openAndPick(c.yearEl, ["{target_year}"], function() {{
                                needYr = false;
                            }});
                        }}
                    }}
                    if (needDay || needMon || needYr) chain();
                }} catch (e) {{}}
            }}, 5800);

            // 10: Final re-fill of anything still empty + Submit
            setTimeout(function() {{
                // re-fill names if empty
                let first = findByLabel(['First name', 'firstname']);
                let last  = findByLabel(['Surname', 'Last name']);
                if (!first || !last) {{
                    let texts = getTextInputs().filter(function(el) {{
                        return !matchText(el, ['email', 'mobile', 'phone', 'password']);
                    }});
                    if (!first && texts[0]) first = texts[0];
                    if (!last  && texts[1]) last  = texts[1];
                }}
                if (first && !first.value) typeText(first, "{fn}");
                if (last  && !last.value)  typeText(last,  "{ln}");

                // re-fill email if empty
                let emailEl = findByLabel(['Mobile number or email', 'email', 'Mobile number']);
                if (emailEl && !emailEl.value) typeText(emailEl, "{cred}");

                // re-try gender if still "Select your gender"
                let gText = '';
                document.querySelectorAll('[role="button"], [role="combobox"]').forEach(function(el) {{
                    let t = (el.textContent || '').toLowerCase();
                    if (t.indexOf('select your gender') !== -1) gText = t;
                }});
                if (gText.indexOf('select your gender') !== -1) {{
                    let gBtn = null;
                    document.querySelectorAll('[role="button"], [aria-haspopup], [role="combobox"]').forEach(function(c) {{
                        let t = (c.textContent || '').toLowerCase();
                        if (t.indexOf('select your gender') !== -1) gBtn = c;
                    }});
                    if (gBtn) {{
                        gBtn.click();
                        setTimeout(function() {{ clickOption(['Female', 'Woman', 'female']); }}, 300);
                    }}
                }}

                // After all details filled: wait 5 seconds, then 60fps slow-motion scroll to Submit and click
                setTimeout(function() {{
                    function findSubmitBtn() {{
                        // Prefer exact "Submit" (the blue button on Meta form)
                        let all = document.querySelectorAll('button, [role="button"], input[type="submit"]');
                        let exact = null, fallback = null;
                        for (let b of all) {{
                            let t = (b.textContent || b.value || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                            if (t === 'submit') {{ exact = b; break; }}
                            if (!fallback && (t.indexOf('sign up') !== -1 || t.indexOf('create account') !== -1 ||
                                t === 'next' || t === 'continue' || b.getAttribute('name') === 'websubmit' ||
                                b.type === 'submit')) {{
                                fallback = b;
                            }}
                        }}
                        return exact || fallback || document.querySelector('button[name="websubmit"], button[type="submit"]');
                    }}

                    function doSmoothScrollAndClick(targetBtn) {{
                        if (!targetBtn) return;
                        let rect = targetBtn.getBoundingClientRect();
                        let absoluteTop = rect.top + window.pageYOffset;
                        let targetY = Math.max(0, absoluteTop - (window.innerHeight * 0.35));
                        let startY = window.pageYOffset;
                        let distance = targetY - startY;
                        // If already near button, just click
                        if (Math.abs(distance) < 40) {{
                            targetBtn.focus();
                            targetBtn.click();
                            targetBtn.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true, view: window }}));
                            return;
                        }}
                        let duration = 3000; // 3 seconds slow smooth scroll ~60fps
                        let startTime = null;

                        function step(now) {{
                            if (!startTime) startTime = now;
                            let progress = Math.min((now - startTime) / duration, 1);
                            // ease-in-out
                            let ease = progress < 0.5
                                ? 4 * progress * progress * progress
                                : 1 - Math.pow(-2 * progress + 2, 3) / 2;
                            window.scrollTo(0, startY + distance * ease);
                            if (progress < 1) {{
                                requestAnimationFrame(step);
                            }} else {{
                                // Ensure button in view then click
                                targetBtn.scrollIntoView({{ block: 'center', behavior: 'instant' }});
                                setTimeout(function() {{
                                    targetBtn.focus();
                                    targetBtn.click();
                                    targetBtn.dispatchEvent(new MouseEvent('click', {{
                                        bubbles: true, cancelable: true, view: window
                                    }}));
                                    // one more safety click
                                    setTimeout(function() {{ targetBtn.click(); }}, 200);
                                }}, 150);
                            }}
                        }}
                        requestAnimationFrame(step);
                    }}

                    let btn = findSubmitBtn();
                    if (btn) {{
                        doSmoothScrollAndClick(btn);
                    }} else {{
                        setTimeout(function() {{
                            doSmoothScrollAndClick(findSubmitBtn());
                        }}, 800);
                    }}
                }}, 5000); // exactly 5 seconds after final fill pass, then scroll + click Submit
            }}, 6000);
        }})();
        """
        self.web.page().runJavaScript(fill_js)
        # capture cookies a bit later
        QTimer.singleShot(6000, self.grab_browser_cookies)
        QTimer.singleShot(14000, self.capture_account_session_data)
        QTimer.singleShot(25000, self.capture_account_session_data)
        QTimer.singleShot(40000, self.capture_account_session_data)
        # Auto mode: after one account cycle, prepare next from list
        if hasattr(self, "run_mode") and "auto" in self.run_mode.currentText().lower():
            QTimer.singleShot(45000, self._auto_mode_next_account)
        # persist resend + api settings
        try:
            if hasattr(self, "spin_resend_email"):
                self.store.set_setting("resend_email_times", str(self.spin_resend_email.value()))
            if hasattr(self, "spin_resend_phone"):
                self.store.set_setting("resend_phone_times", str(self.spin_resend_phone.value()))
            if hasattr(self, "api_key_edit"):
                self.store.set_setting("api_key", self.api_key_edit.text().strip())
        except Exception:
            pass
        dob_str = f"{target_day}/{target_month_str}/{target_year}"
        _g = locals().get("gender_text") or (self.auto_gender.currentText().strip() if hasattr(self, "auto_gender") else "Female")
        self.save_account_record(fn, ln, cred, pw, _g, dob_str, uid=self.btn_uid.text())
        self.store.event("Tool Browser", f"Auto-Fill & Submit executed for {fn} {ln} (DOB: {dob_str})", "SUCCESS")


    def handle_otp_resend_flow(self):
        """On confirmation page: click 'I didn't get the code' then resend, N times based on contact type."""
        if getattr(self, "_paused", False):
            return
        if getattr(self, "_otp_resend_running", False):
            return
        contact = ""
        try:
            contact = self.auto_credential.text().strip()
        except Exception:
            pass
        is_email = ("@" in contact) if contact else True
        # Configurable counts from settings / UI
        email_times = int(self.store.get_setting("resend_email_times", "2") or "2")
        phone_times = int(self.store.get_setting("resend_phone_times", "8") or "8")
        times = email_times if is_email else phone_times
        self._otp_resend_running = True
        self._otp_resend_left = times
        self.statusBar().showMessage(f"OTP page: will resend code {times} time(s) ({'email' if is_email else 'phone'} mode)", 5000)
        self.store.event("OTP", f"Starting resend flow x{times} ({'email' if is_email else 'phone'})", "INFO")
        QTimer.singleShot(1500, self._otp_resend_step)

    def _otp_resend_step(self):
        if not getattr(self, "_otp_resend_running", False):
            return
        if self._otp_resend_left <= 0:
            self._otp_resend_running = False
            self.statusBar().showMessage("OTP resend sequence finished", 4000)
            return
        left = self._otp_resend_left
        js = """
        (function(){
            function clickByText(texts) {
                let nodes = document.querySelectorAll('a, button, span, div[role="button"], [role="link"]');
                for (let n of nodes) {
                    let t = (n.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                    for (let w of texts) {
                        if (t === w || t.indexOf(w) !== -1) {
                            n.click();
                            return t;
                        }
                    }
                }
                return null;
            }
            // First try "I didn't get the code"
            let r1 = clickByText([
                "i didn't get the code",
                "i didnt get the code",
                "didn't get the code",
                "did not get the code",
                "resend code",
                "send code again"
            ]);
            return r1 || "none";
        })();
        """
        def after_didnt_get(result):
            self.statusBar().showMessage(f"OTP resend step ({left} left): clicked '{result}'", 3000)
            # Then click actual Resend confirmation code if a submenu appeared
            js2 = """
            (function(){
                function clickByText(texts) {
                    let nodes = document.querySelectorAll('a, button, span, div[role="button"], [role="link"], li');
                    for (let n of nodes) {
                        let t = (n.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
                        for (let w of texts) {
                            if (t === w || t.indexOf(w) !== -1) {
                                n.click();
                                return t;
                            }
                        }
                    }
                    return null;
                }
                return clickByText([
                    "resend confirmation code",
                    "resend code",
                    "send email again",
                    "send code again",
                    "get a new code",
                    "resend"
                ]) || "none";
            })();
            """
            def after_resend(r2):
                self._otp_resend_left -= 1
                self.store.event("OTP", f"Resend clicked ({self._otp_resend_left} remaining) result={r2}", "SUCCESS")
                if self._otp_resend_left > 0:
                    # Wait before next cycle (give FB time)
                    QTimer.singleShot(8000, self._otp_resend_step)
                else:
                    self._otp_resend_running = False
                    self.statusBar().showMessage("OTP resend sequence complete", 4000)
            QTimer.singleShot(1200, lambda: self.web.page().runJavaScript(js2, after_resend))

        self.web.page().runJavaScript(js, after_didnt_get)

    def save_account_record(self, fn, ln, contact, pw, gender, dob, uid=""):
        try:
            ctype = "email" if "@" in (contact or "") else "phone"
            self.store.add_account(fn, ln, contact, pw, gender, dob, uid=uid or self.btn_uid.text(),
                                   contact_type=ctype, status="submitted")
            self.store.event("Account", f"Saved {fn} {ln} / {contact}", "SUCCESS")
        except Exception as e:
            self.store.event("Account", f"Save failed: {e}", "ERROR")

    def import_contact_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Email/Phone List", "", "Text Files (*.txt);;CSV (*.csv);;All (*.*)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith("#")]
            # detect type
            emails = [x for x in lines if "@" in x]
            phones = [x for x in lines if "@" not in x]
            if emails:
                self.store.add_contacts(emails, "email")
            if phones:
                self.store.add_contacts(phones, "phone")
            te, ue, ae = self.store.contact_stats("email")
            tp, up, ap = self.store.contact_stats("phone")
            QMessageBox.information(
                self, "Import Done",
                f"Imported:\nEmail total {te} (available {ae})\nPhone total {tp} (available {ap})"
            )
            self.refresh_contact_stats_label()
            if hasattr(self, "contact_source"):
                self.contact_source.setCurrentText("From imported list")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", str(e))

    def refresh_contact_stats_label(self):
        if not hasattr(self, "lbl_contact_stats"):
            return
        te, ue, ae = self.store.contact_stats("email")
        tp, up, ap = self.store.contact_stats("phone")
        self.lbl_contact_stats.setText(f"Pool — Email left: {ae}/{te} | Phone left: {ap}/{tp}")

    def fetch_contact_via_api(self):
        """If API Key is set, try a simple GET to a user-configured endpoint pattern.
        Supported pattern in settings api_endpoint, default empty = disabled.
        Response: plain text one email/phone per line or JSON {"number":"..."} / {"email":"..."}."""
        key = ""
        if hasattr(self, "api_key_edit"):
            key = self.api_key_edit.text().strip()
        if not key:
            key = self.store.get_setting("api_key", "")
        endpoint = self.store.get_setting("api_endpoint", "").strip()
        if not key or not endpoint:
            QMessageBox.information(self, "API",
                "Set API Key and (in Settings) api_endpoint URL to use live numbers/emails.\\n"
                "Endpoint should return plain text or JSON with email/number.")
            return None
        try:
            import urllib.request
            req = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {key}", "X-API-Key": key})
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8", errors="ignore").strip()
            val = body.splitlines()[0].strip() if body else ""
            if body.startswith("{"):
                import json
                data = json.loads(body)
                val = data.get("email") or data.get("number") or data.get("phone") or data.get("data") or val
            if val:
                self.auto_credential.setText(str(val))
                self.statusBar().showMessage(f"API contact: {val}", 4000)
                return str(val)
        except Exception as e:
            QMessageBox.warning(self, "API Error", str(e))
        return None

    def apply_next_contact_from_pool(self):

        mode = "email"
        if hasattr(self, "contact_mode"):
            mode = "email" if "email" in self.contact_mode.currentText().lower() else "phone"
        val = self.store.next_contact(mode)
        if val:
            self.auto_credential.setText(val)
            self.statusBar().showMessage(f"Applied {mode} from list: {val}", 4000)
            return val
        self.statusBar().showMessage(f"No unused {mode} left in pool — using generated", 4000)
        return None



    def _tick_startup_grace(self):
        if not getattr(self, "_startup_block_autofill", False):
            self._startup_timer.stop()
            return
        self._startup_grace_left = max(0, getattr(self, "_startup_grace_left", 60) - 1)
        if self._startup_grace_left <= 0:
            self._startup_block_autofill = False
            self._startup_timer.stop()
            self.statusBar().showMessage("Grace period over. Press ▶ Start when you are ready to begin.", 8000)
            self.store.event("Application", "Startup grace finished — waiting for Start", "INFO")
        elif self._startup_grace_left % 15 == 0:
            self.statusBar().showMessage(
                f"Setup time left: {self._startup_grace_left}s (3 min total) — then press ▶ Start", 4000
            )

    def _auto_mode_next_account(self):
        if getattr(self, "_paused", False):
            return
        if not hasattr(self, "run_mode") or "auto" not in self.run_mode.currentText().lower():
            return
        # Clear session and start next with next list contact
        try:
            self.web_profile.cookieStore().deleteAllCookies()
        except Exception:
            pass
        try:
            self.web.page().runJavaScript("window.__skypilot_autofilled = false;")
        except Exception:
            pass
        if hasattr(self, "contact_source"):
            self.contact_source.setCurrentText("From imported list")
        self.generate_random_details()
        self.statusBar().showMessage("Auto mode: next account from list…", 5000)
        self.web.setUrl(QUrl("https://www.facebook.com/r.php"))
        QTimer.singleShot(5000, self.execute_autofill_script)

    def pause_automation(self):
        self._paused = True
        self._otp_resend_running = False
        self._startup_block_autofill = True
        self._run_generation = getattr(self, "_run_generation", 0) + 1
        try:
            self.web.page().runJavaScript(
                "window.__skypilot_autofilled = true; window.__skypilot_paused = true;"
            )
        except Exception:
            pass
        try:
            self.btn_pause.setText("⏸ Paused")
        except Exception:
            pass
        self.statusBar().showMessage("⏸ PAUSED — automation stopped. Press Resume to continue.", 10000)
        self.store.event("Control", "Automation paused", "INFO")
        QMessageBox.information(self, "Paused", "All automation is paused.\nClick Resume to continue.")

    def resume_automation(self):
        self._paused = False
        self._startup_block_autofill = False
        self._run_generation = getattr(self, "_run_generation", 0) + 1
        try:
            self.web.page().runJavaScript(
                "window.__skypilot_autofilled = false; window.__skypilot_paused = false;"
            )
        except Exception:
            pass
        try:
            self.btn_pause.setText("⏸ Pause")
        except Exception:
            pass
        self.statusBar().showMessage("⏵ RESUMED — continuing…", 6000)
        self.store.event("Control", "Automation resumed", "INFO")
        try:
            url = self.web.url().toString().lower()
        except Exception:
            url = ""
        if any(k in url for k in ("confirmemail", "confirm", "checkpoint")):
            QTimer.singleShot(400, self.handle_otp_resend_flow)
        elif "/r.php" in url or "signup" in url or "/reg/" in url:
            QTimer.singleShot(400, self.execute_autofill_script)
        else:
            self.statusBar().showMessage("Resumed. Press Start to open Sign-Up and fill.", 6000)


    def start_automation_now(self):

        """Unlock startup block and begin automation on Sign-Up (or OTP resend)."""
        self._startup_block_autofill = False
        self._startup_grace_left = 0
        try:
            self._startup_timer.stop()
        except Exception:
            pass
        try:
            self.web.page().runJavaScript("window.__skypilot_autofilled = false;")
        except Exception:
            pass
        url = ""
        try:
            url = self.web.url().toString().lower()
        except Exception:
            pass
        if any(k in url for k in ("confirmemail", "confirm", "checkpoint", "otp")):
            self.statusBar().showMessage("Start: OTP resend flow", 4000)
            self.handle_otp_resend_flow()
            return
        if "/r.php" in url or "signup" in url or "/reg/" in url:
            self.statusBar().showMessage("Start: auto-fill on Sign-Up…", 4000)
            QTimer.singleShot(500, self.execute_autofill_script)
            return
        self.statusBar().showMessage("Start: opening Sign-Up page…", 3000)
        self.web.setUrl(QUrl("https://www.facebook.com/r.php"))
        QTimer.singleShot(4000, self.execute_autofill_script)


    def capture_account_session_data(self):
        """Fill UID / Cookies / Access Token ONLY when a real registered session exists.
        Rules:
        - UID: from c_user cookie after successful registration
        - Cookies: browser cookies after login/home session
        - Access Token: from localStorage / sessionStorage / cookie if Facebook issued one
        Never write fake or demo values.
        """
        if getattr(self, "_paused", False):
            return
        try:
            url = self.web.url().toString().lower()
        except Exception:
            url = ""
        # Still on plain sign-up form without session — skip
        if "/r.php" in url and "confirm" not in url:
            return

        js = r"""
        (function(){
            function getCookie(name) {
                let m = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
                return m ? decodeURIComponent(m[1]) : '';
            }
            let uid = getCookie('c_user') || '';
            let xs = getCookie('xs') || '';
            let cookieStr = document.cookie || '';
            let token = '';
            try {
                // Common places FB / Meta web may store tokens (may be empty on pure web signup)
                for (let store of [localStorage, sessionStorage]) {
                    for (let i = 0; i < store.length; i++) {
                        let k = store.key(i) || '';
                        let kl = k.toLowerCase();
                        if (kl.indexOf('access_token') !== -1 || kl.indexOf('accessToken') !== -1 ||
                            kl === 'token' || kl.indexOf('fbssls') !== -1) {
                            let v = store.getItem(k) || '';
                            if (v && v.length > 20) { token = v; break; }
                        }
                    }
                    if (token) break;
                }
            } catch(e) {}
            try {
                if (!token && window.__accessToken) token = String(window.__accessToken);
            } catch(e) {}
            // Only report success if we have real c_user (account registered & session alive)
            return {
                uid: uid,
                cookies: cookieStr,
                token: token,
                xs: xs,
                hasSession: !!(uid && cookieStr)
            };
        })();
        """

        def _got(res):
            try:
                if not res or not isinstance(res, dict):
                    return
                if not res.get("hasSession") and not res.get("uid"):
                    # No real registered session yet — leave boxes empty
                    return
                uid = (res.get("uid") or "").strip()
                ck = (res.get("cookies") or "").strip()
                tok = (res.get("token") or "").strip()
                # Only set fields when real data present
                if uid:
                    self.btn_uid.setText(uid)
                if ck:
                    self.btn_cookies.setText(ck[:5000])
                if tok:
                    self.btn_token.setText(tok[:2000])
                elif not tok:
                    # keep token empty rather than fake — optional note only in placeholder
                    pass
                if uid or ck:
                    self.statusBar().showMessage(
                        f"Real session: UID={uid or '—'} | cookies={len(ck)} chars | token={'yes' if tok else 'not in page storage'}",
                        6000
                    )
                    try:
                        rows = self.store.accounts()
                        if rows:
                            last_id = rows[0]["id"]
                            with self.store.connect() as con:
                                if uid:
                                    con.execute("UPDATE accounts SET uid=? WHERE id=?", (uid, last_id))
                                if ck:
                                    con.execute("UPDATE accounts SET cookies=? WHERE id=?", (ck[:5000], last_id))
                                if tok:
                                    con.execute("UPDATE accounts SET token=? WHERE id=?", (tok, last_id))
                    except Exception:
                        pass
            except Exception as e:
                print("capture error", e)

        try:
            self.web.page().runJavaScript(js, _got)
        except Exception:
            pass


    def change_and_restart_automation(self):
        """Regenerate details and restart sign-up from scratch."""
        try:
            try:
                self.web_profile.cookieStore().deleteAllCookies()
            except Exception:
                pass
            try:
                self.web_profile.clearHttpCache()
            except Exception:
                pass
            try:
                self.web.page().runJavaScript("window.__skypilot_autofilled = false;")
            except Exception:
                pass

            # Always new random name/pass; contact depends on source setting
            self.generate_random_details()

            self.store.event("Tool Browser", "Change (Start) — new details + reload sign-up", "SUCCESS")
            self.web.setUrl(QUrl("https://www.facebook.com/r.php"))
            self.statusBar().showMessage("Change (Start): new details loaded, opening Sign-Up...", 4000)
            # Safety: run fill after page should be ready
            QTimer.singleShot(4000, self.execute_autofill_script)
        except Exception as e:
            QMessageBox.critical(self, "Change Error", str(e))

    def start_popup_countdown(self):
        self.popup_seconds = 5
        self.lbl_timer_status.setText(f"Popup Skip Timer: {self.popup_seconds}s")
        self.popup_timer.start(1000)

    def handle_popup_countdown(self):
        self.popup_seconds -= 1
        if self.popup_seconds > 0:
            self.lbl_timer_status.setText(f"Popup Skip Timer: {self.popup_seconds}s")
        else:
            self.popup_timer.stop()
            self.lbl_timer_status.setText("Popup Skip: Executed")
            skip_js = """
            (function(){
                let closeBtns = document.querySelectorAll('[aria-label="Close"], [aria-label="close"], ._8idr');
                closeBtns.forEach(btn => btn.click());
            })();
            """
            self.web.page().runJavaScript(skip_js)

    def clear_tool_browser_data(self):
        reply = QMessageBox.question(
            self, "Confirm Clear Data",
            "Clear ALL browser cookies, cache, history and form fields?\nYou will be taken to the Facebook sign-in page.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return
        # Stop any pending timers / automation
        self._otp_resend_running = False
        self._paused = False
        self._run_generation = 0
        self._startup_block_autofill = True
        self._startup_grace_left = 180
        try:
            self.web.page().runJavaScript("window.__skypilot_autofilled = false; window.__skypilot_startup = true;")
        except Exception:
            pass
        # Clear cookies & cache aggressively
        try:
            self.web_profile.cookieStore().deleteAllCookies()
        except Exception as e:
            print("cookie clear:", e)
        try:
            self.web_profile.clearHttpCache()
        except Exception as e:
            print("cache clear:", e)
        try:
            storage_path = TOOL_BROWSER_DIR / "storage"
            cache_path = TOOL_BROWSER_DIR / "cache"
            shutil.rmtree(storage_path, ignore_errors=True)
            shutil.rmtree(cache_path, ignore_errors=True)
            storage_path.mkdir(parents=True, exist_ok=True)
            cache_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print("disk clear:", e)
        # Clear ALL form fields — never leave fake UID/token
        for name in ("auto_fname", "auto_lname", "auto_credential", "auto_pass",
                     "btn_uid", "btn_cookies", "btn_token"):
            w = getattr(self, name, None)
            if w is not None:
                try:
                    w.clear()
                except Exception:
                    pass
        # Go to Facebook sign-in (home/login)
        try:
            self.web.setUrl(QUrl("about:blank"))
            QTimer.singleShot(200, lambda: self.web.setUrl(QUrl("https://www.facebook.com/")))
        except Exception as e:
            QMessageBox.critical(self, "Clear Failed", str(e))
            return
        self.store.event("Tool Browser", "Clear Data — cookies/cache/fields reset, on sign-in page", "SUCCESS")
        self.statusBar().showMessage("Cleared. On sign-in page. Waiting 5s… then ready. Press ▶ Start when ready.", 8000)
        # After 5 seconds unlock autofill block but do NOT auto-navigate; user presses Start
        def _after_clear():
            self._startup_block_autofill = False
            self.statusBar().showMessage("Ready. Click ▶ Start to open Sign-Up and begin.", 6000)
        QTimer.singleShot(5000, _after_clear)
        QMessageBox.information(self, "Clear Complete",
            "All data cleared.\nYou are on the Facebook sign-in page.\nAfter 5 seconds the tool is ready — press ▶ Start to begin.")


    def resume_automation_process(self):
        try:
            self.web_profile.cookieStore().deleteAllCookies()
            self.web_profile.clearHttpCache()
            self.store.event("Tool Browser", "Process Resumed - Profile Cleared & Reloading", "SUCCESS")
            self.web.setUrl(QUrl("https://www.facebook.com/"))
        except Exception as e:
            QMessageBox.critical(self, "Resume Error", str(e))

    def save_profile(self):
        first, last, email = self.first.text().strip(), self.last.text().strip(), self.email.text().strip()
        if not first or not last or "@" not in email:
            QMessageBox.warning(self, "Validation", "Valid fields required."); return
        self.store.add_profile(first, last, email, self.notes.text().strip())
        self.first.clear(); self.last.clear(); self.email.clear(); self.notes.clear()
        self.refresh_profiles()

    def refresh_profiles(self):
        if not hasattr(self, "profile_table"): return
        rows = self.store.profiles(); self.profile_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, k in enumerate(["id", "created_at", "first_name", "last_name", "email"]):
                self.profile_table.setItem(r, c, QTableWidgetItem(str(row[k])))

    def generate_password(self):
        chars = string.ascii_letters + string.digits + "!@#$"
        self.pw_out.setText("".join(secrets.choice(chars) for _ in range(self.pw_len.value())))

    def run_url_check(self):
        url = self.check_url.text().strip()
        self.check_output.append(f"Checking {url}...")

    def update_monitor(self):
        try:
            cpu = psutil.cpu_percent(interval=None); mem = psutil.virtual_memory()
            if hasattr(self, "cpu"):
                self.cpu.metric_value.setText(f"{cpu:.0f}%")
                self.ram.metric_value.setText(f"{mem.percent:.0f}%")
        except Exception: pass

    def refresh_dashboard(self):
        if not hasattr(self, "cards"): return
        counts = self.store.counts()
        for k, v in counts.items(): self.cards[k].metric_value.setText(str(v))

    def refresh_logs(self):
        if not hasattr(self, "log_table"): return
        rows = self.store.events(); self.log_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["id"], row["created_at"], row["category"], row["message"], row["status"]]
            for c, v in enumerate(vals): self.log_table.setItem(r, c, QTableWidgetItem(str(v)))

    def create_backup(self, *args, **kwargs):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = BACKUP_DIR / f"skypilot_backup_{ts}.db"
            shutil.copy2(DB_PATH, dest)
            # also dump accounts CSV next to it
            csv_path = BACKUP_DIR / f"accounts_{ts}.csv"
            rows = self.store.accounts()
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id","created_at","first_name","last_name","contact","password","gender","dob","uid","contact_type","status"])
                for r in rows:
                    w.writerow([r["id"], r["created_at"], r["first_name"], r["last_name"], r["contact"],
                                r["password"], r["gender"], r["dob"], r["uid"], r["contact_type"], r["status"]])
            QMessageBox.information(self, "Backup", f"Backup saved:\n{dest}\n{csv_path}")
            self.store.event("Backup", f"Created {dest.name}", "SUCCESS")
        except Exception as e:
            QMessageBox.critical(self, "Backup Failed", str(e))

    def refresh_all(self):
        self.refresh_profiles(); self.refresh_logs()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 9))
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
