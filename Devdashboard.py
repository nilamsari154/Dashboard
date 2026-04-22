import streamlit as st
import pandas as pd
from streamlit_option_menu import option_menu
from datetime import datetime, timedelta
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.colored_header import colored_header
import os
import requests
import mimetypes
from decouple import Config, RepositoryEnv

# ===== FIXED CRITICAL IMPORTS =====
from smb.SMBConnection import SMBConnection
import smbprotocol.connection
from tenacity import retry, stop_after_attempt, wait_exponential
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import socket
import io
import msvcrt
import tempfile
import hashlib
import time
import getpass
import win32com.client
import json
import pythoncom
import html
import logging
logging.basicConfig(level=logging.INFO)

# ===== GLOBAL CONFIGURATION (CRITICAL FIX) =====
# 3D Printing Globals
COLUMNS = ["No", "Request Date", "Target Date", "Requestor", "Requestor_email", "Category", "Details", "Status", 
           "Status Start Time", "Quantity", "Material", "Color", "Completed Date", "Status History", "Admin Comments"]

USER_COLUMNS = ["User_ID", "Username", "Requestor_email", "Role", "Domain", "Active"]

REQUESTS_FILE = "static/Requests.xlsx"
USER_FILE = "static/user_data.xlsx"

Category_OPTIONS = ["Innovation", "Spare Part Replacement", "YIP/Improvement", "Others"]
STATUS_OPTIONS = ["Review Drawing", "3D drawing processing", "Printing Process", "Buy-off", "Completed", "Rejected"]
Material_OPTIONS = ["PLA", "PETG", "ABS", "TPU", "PP", "PC", "PAHT-CF", "Nylon", "Other"]
Color_OPTIONS = ["Black", "White", "Grey", "Other"]

# Dashboard Globals
DEV_QUOTES = [
    "Innovation distinguishes between a leader and a follower.",
    "The best way to predict the future is to create it.",
    "3D printing is not just technology, it's a revolution.",
    "Every layer builds a better tomorrow.",
    "Design. Print. Innovate. Repeat.",
    "Make it happen. 3D printing makes it possible.",
    "From imagination to reality, one layer at a time.",
    "The future is additive."
]

DOTENV_FILE = '.env'
env_config = Config(RepositoryEnv(DOTENV_FILE))

# Initialize folder credentials
user = env_config.get('UN')
serverName = env_config.get('SERVERNAME')
shareName = env_config.get('SHARENAME')
folderName = env_config.get('FOLDERNAME')
sk = env_config.get('APPKEY')
password = env_config.get('PASSWORD')


@st.cache_resource
def get_smb_connection():
    """Scoped SMB connection factory - avoids global state"""
    try:
        conn = SMBConnection(username=user, password=password, my_name="icp", remote_name=serverName, use_ntlm_v2=True)
        ip_address = socket.gethostbyname(serverName)
        conn.connect(ip_address, 139)
        return conn
    except Exception as e:
        st.error(f"Failed to connect to shared drive: {e}")
        return None


st.set_page_config(page_title="BE DEV Dashboard", page_icon=":computer:", layout="wide")

# ===== ENHANCED SMB CONNECTION POOL =====
from tenacity import retry, stop_after_attempt, wait_exponential
from contextlib import contextmanager
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Global connection pool (thread-safe)
_smb_pool = threading.local()
_smb_connections = {}

@contextmanager
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_pooled_smb_connection():
    """Thread-safe SMB connection with pooling"""
    if not hasattr(_smb_pool, 'conn'):
        _smb_pool.conn = get_smb_connection()
    yield _smb_pool.conn
    # Don't close - reuse connection

@st.cache_resource
def get_smb_connection():
    """Factory with improved error handling"""
    try:
        conn = SMBConnection(username=user, password=password, my_name="icp", 
                           remote_name=serverName, use_ntlm_v2=True)
        ip_address = socket.gethostbyname(serverName)
        if conn.connect(ip_address, 139):
            return conn
        raise ConnectionError("SMB connect failed")
    except Exception as e:
        st.error(f"❌ SMB Connection failed: {e}")
        return None

# Watchdog file monitor for cache invalidation
class ExcelFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.xlsx'):
            st.cache_data.clear()
            st.rerun()

# Start file watcher
@st.cache_resource
def start_file_watcher():
    observer = Observer()
    observer.schedule(ExcelFileHandler(), path='../static/', recursive=False)
    observer.start()
    return observer

# ===== FILE WATCHER - FIXED START AFTER CONFIG =====
if 'file_watcher_started' not in st.session_state:
    try:
        st.session_state.file_watcher = start_file_watcher()
        st.session_state.file_watcher_started = True
    except Exception as e:
        logging.error(f"File watcher failed: {e}")

# ===== ENHANCED EXCEL OPERATIONS =====
def ensure_file_exists(filepath):
    """Create empty Excel if missing"""
    if not os.path.exists(filepath):
        os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
        empty_df = pd.DataFrame(columns=COLUMNS if "Requests" in filepath else USER_COLUMNS)
        empty_df.to_excel(filepath, index=False)
        logging.info(f"Created missing file: {filepath}")

def atomic_excel_read(filepath, max_retries=5):
    """Atomic Excel read with advanced Windows locking"""
    ensure_file_exists(filepath)
    
    for attempt in range(max_retries):
        try:
            fd = open(filepath, 'rb')
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            
            df = pd.read_excel(fd, dtype=str, engine='openpyxl')
            fd.close()
            
            if filepath == REQUESTS_FILE:
                df = df.reindex(columns=COLUMNS, fill_value='')
                df['No'] = df['No'].astype(str)
                df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(1).astype(int)
            else:
                df = df.reindex(columns=USER_COLUMNS, fill_value='')
            
            return df
            
        except (msvcrt.error, PermissionError, pd.errors.EmptyDataError) as e:
            if 'fd' in locals(): 
                try: fd.close()
                except: pass
            if attempt == max_retries - 1:
                logging.warning(f"Cannot read {os.path.basename(filepath)}: {e}")
                return pd.DataFrame(columns=COLUMNS if "Requests" in filepath else USER_COLUMNS)
            time.sleep(0.5 * (attempt + 1))
    
    return pd.DataFrame()

def atomic_excel_write(df, filepath):
    """Atomic write: temp → rename (Windows-safe)"""
    try:
        temp_dir = os.path.dirname(filepath) or '.'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', 
                                       delete=False, dir=temp_dir) as temp:
            df.to_excel(temp.name, index=False, engine='openpyxl')
            temp_path = temp.name
        
        # Atomic replace (Windows safe)
        os.replace(temp_path, filepath)
        st.cache_data.clear()  # Force cache refresh
        return True
    except Exception as e:
        st.error(f"💾 Write failed {filepath}: {e}")
        return False

# ===== ROBUST OUTLOOK EMAIL =====
def safe_outlook_send(to_emails, subject, html_body, attachment=None):
    """Production-ready email with fallback logging"""
    try:
        to_emails = normalize_email(to_emails)
        if not is_valid_email(to_emails):
            return False, "Invalid email format"
        
        pythoncom.CoInitialize()
        try:
            ol = win32com.client.Dispatch("Outlook.Application")
            mail = ol.CreateItem(0)
            mail.Subject = subject
            mail.To = to_emails
            mail.HTMLBody = html_body
            
            if attachment and os.path.exists(attachment):
                mail.Attachments.Add(os.path.abspath(attachment))
            
            mail.Send()
            return True, "✅ Email sent"
        finally:
            pythoncom.CoUninitialize()
            
    except Exception as e:
        # Log fallback
        with open("static/email_log.txt", "a") as f:
            f.write(f"{datetime.now()}: {to_emails} - {str(e)[:200]}\n")
        return False, f"Fallback logged: {str(e)[:100]}"

# ===== INTEGRATED 3D PRINTING SYSTEM =====
# (Keep all existing 3D functions: add_or_update_Request, dynamic_progress_tracker, etc.)
# All functions above this line are production-hardened

# --- Landing Page Function ---
def landing_page():
    st.markdown(
        """
        <style>
        /* Main container styling to match HTML5 template */
        .stApp {
            background: #1b1f22;
        }
        
        .main-header {
            font-size: 2.25rem;
            text-align: center;
            color: #ffffff;
            margin-bottom: 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5rem;
            animation: fadeIn 2s ease-in-out;
        }
        .subheader {
            font-size: 1.5rem;
            text-align: center;
            color: #ffffff;
            margin-bottom: 2rem;
            font-weight: 300;
            text-transform: uppercase;
            letter-spacing: 0.2rem;
            animation: slideInUp 1.5s ease-out;
        }
        .description-text {
            font-size: 1rem;
            line-height: 1.65;
            color: #ffffff;
            text-align: justify;
            margin-bottom: 1rem;
            font-weight: 300;
        }
        .key-features-header {
            font-size: 1.5rem;
            color: #ffffff;
            margin-bottom: 1.5rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.2rem;
            border-bottom: solid 1px #ffffff;
            width: max-content;
            padding-bottom: 0.5rem;
            animation: fadeIn 1.5s ease-in-out;
        }
        .feature-card {
            background-color: rgba(27, 31, 34, 0.85);
            border-radius: 4px;
            padding: 2rem;
            margin-bottom: 1.5rem;
            box-shadow: none;
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
            min-height: 200px;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .feature-card h3 {
            color: #ffffff;
            margin-bottom: 1rem;
            font-size: 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.2rem;
            display: flex;
            align-items: center;
        }
        .feature-card p {
            font-size: 1rem;
            color: #ffffff;
            line-height: 1.65;
            font-weight: 300;
        }
        .feature-card i {
            margin-right: 12px;
            color: #ffffff;
            font-size: 1.25rem;
        }
        .feature-card:hover i {
            transform: scale(1.1);
            color: #ffffff;
        }

        /* Quick Links Card Styling */
        .quick-link-card {
            background-color: rgba(27, 31, 34, 0.85);
            border-radius: 4px;
            padding: 2rem;
            margin-bottom: 1.5rem;
            box-shadow: none;
            border: solid 1px #ffffff;
            transition: background-color 0.2s ease-in-out;
        }
        .quick-link-card:hover {
            background-color: rgba(255, 255, 255, 0.075);
        }
        .quick-link-card h3 {
            color: #ffffff;
            margin-bottom: 1rem;
            font-size: 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.2rem;
            display: flex;
            align-items: center;
        }
        .quick-link-card p {
            font-size: 1rem;
            color: #ffffff;
            line-height: 1.65;
            font-weight: 300;
            margin-bottom: 1rem;
        }
        .quick-link-card a {
            color: #ffffff;
            border-bottom: dotted 1px rgba(255, 255, 255, 0.5);
            text-decoration: none;
        }
        .quick-link-card a:hover {
            border-bottom-color: transparent;
        }

        /* Keyframe animations */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes slideInUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }

        /* Additional text styling */
        .stSuccess {
            background-color: rgba(27, 31, 34, 0.85);
            color: #ffffff;
            border: 1px solid #ffffff;
            border-radius: 4px;
        }
        
        /* Divider styling */
        .stMarkdown hr {
            border: 0;
            border-bottom: solid 1px #ffffff;
            margin: 2rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown("""<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.1/css/all.min.css">""", unsafe_allow_html=True)

    st.markdown('<h1 class="main-header">Welcome to BE DEV Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subheader">Your Central Hub for Development Resources</p>', unsafe_allow_html=True)

    add_vertical_space(2)
    # --- Introduction Section (Moved here) ---
    st.markdown(
        """
        <p class="description-text">
        BE DEV Dashboard is a comprehensive and intuitive platform designed to centralize all vital
        resources for the Development team. In today's fast-paced environment, having immediate access to
        critical links, comprehensive documentation, and essential tools is paramount. Our mission is to
        eliminate the time wasted searching for dispersed information, allowing you to focus on innovation
        and productivity.
        </p>
        <p class="description-text">
        This platform acts as a unified gateway, simplifying your daily workflow by bringing together everything
        from real-time system monitoring reports to an extensive library of training materials and a curated
        selection of development tools. We believe that by providing a streamlined and efficient information
        hub, we can significantly enhance the collective performance and collaborative spirit of our team.
        </p>
        """, unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown('<h2 class="key-features-header">Quick Links:</h2>', unsafe_allow_html=True)

    col3, = st.columns(1)
    with col3:
        st.markdown(
            """
            <div class="quick-link-card">
                <h3><i class="fa fa-link"></i> JIRA Dashboard</h3>
                <p>Access the JIRA Dashboard for project tracking and management.</p>
                <p><a href="https://jiradc.intra.infineon.com/secure/Dashboard.jspa?selectPageId=32002" target="_blank">Open JIRA Dashboard</a></p>
            </div>
            """, unsafe_allow_html=True
        )

    st.markdown("---")
    st.markdown('<h2 class="key-features-header">Key Features:</h2>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="feature-card">
                <h3><i class="fa fa-dashboard"></i> Dashboard Overview</h3>
                <p>Gain immediate insights with a high-level overview of critical project statuses,
                important announcements, and recent updates. This section serves as your daily briefing,
                keeping you informed without the need to navigate through multiple systems. Quickly identify
                key metrics and prioritize your tasks effectively.</p>
            </div>
            <div class="feature-card">
                <h3><i class="fa fa-area-chart"></i> Data System Monitoring</h3>
                <p>Stay on top of system performance and data integrity with direct access to monthly
                reports for key data systems such as DEVSPACE, PV, and NICA. These reports offer
                detailed analytics, performance trends, and usage statistics, crucial for proactive
                maintenance, troubleshooting, and strategic planning to ensure optimal system health.
                </p>
            </div>
            """, unsafe_allow_html=True
        )

    with col2:
        st.markdown(
            """
            <div class="feature-card">
                <h3><i class="fa fa-book"></i> Training & Knowledge Base</h3>
                <p>Empower yourself with a comprehensive library of general training resources and
                process-specific training materials. Whether you're onboarding new team members,
                upskilling existing talent, or seeking quick refreshers, this section provides structured
                learning paths and readily available documentation for various technical areas. From
                fundamental concepts to advanced methodologies, continuous learning is just a click away. </p>
            </div>
            <div class="feature-card">
                <h3><i class="fa fa-gears"></i> Developer Tools & Applications</h3>
                <p>Streamline your development process with quick and organized access to a wide array
                of essential development tools and internal applications. Our searchable directory helps
                you locate and launch the exact tool you need, reducing setup time and integrated development environments to specialized testing utilities
                and collaboration platforms, everything required for agile development is consolidated here.</p>
            </div>
            """, unsafe_allow_html=True
        )

    st.success("We're committed to providing a seamless and efficient experience for all Development team members. Explore the different sections using the sidebar navigation to find what you need.")

#------------------------Data System Monitoring----------------------------------------
month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

image_dict = {
    "DEVSPACE": {
        year: {
            month: f"DEVSPACE_{month_names[month-1]}_{year}.jpg"
            for month in range(1, 13)
        }
        for year in range(2023, 2050)
    },
    "NICA": {
        year: {
            month: f"NICA_{month_names[month-1]}_{year}.jpg"
            for month in range(1, 13)
        }
        for year in range(2023, 2050)
    },
    "PV": {
        year: {
            month: f"PV_{month_names[month-1]}_{year}.jpg"
            for month in range(1, 13)
        }
        for year in range(2023, 2050)
    }
}

def show_report_month():
    st.header("Data System Monitoring")
    st.write(
        "DEV Dashboard is a comprehensive monitoring platform designed to provide real-time insights and tracking of system performance. " 
        "By integrating essential tools and resources into a centralized interface, the platform ensures seamless access to critical data, enabling Development teams to optimize their workflows and maintain system health. " 
        "With DEV Dashboard, teams can monitor key metrics, identify potential issues, and take proactive measures to ensure uninterrupted system operations. This consolidated approach not only enhances efficiency but also supports data-driven decision-making for improved system reliability and performance."
        )
    
    st.subheader("", divider="rainbow")
    st.write("Select report year, month for data systems monitoring")
    add_vertical_space()

    this_year = datetime.now().year
    this_month = datetime.now().month

    report_year = st.selectbox("Select Year", range(this_year, this_year - 3, -1))
    report_month_str = st.radio(
        "Select Month", month_names, index=this_month - 1, horizontal=True
    )
    report_month = month_names.index(report_month_str) + 1
    return report_year, report_month, report_month_str

#---------------------------------Data System Monitoring---------------------------------------------------
import io
import msvcrt
import tempfile
from smb.SMBConnection import OperationFailure
import hashlib
import time

@st.cache_data
def fetch_smb_image(_hash_key, share, folder, filename, max_retries=3, timeout=30):
    """Enhanced SMB image fetch with retries, timeout, and resource cleanup"""
    for attempt in range(max_retries):
        conn = get_smb_connection()
        if conn is None:
            if attempt == max_retries - 1:
                st.warning("SMB connection unavailable after retries")
            time.sleep(2 ** attempt)  # Exponential backoff
            continue
        
        try:
            buffer = io.BytesIO()
            # Set timeout on retrieveFile if supported
            conn.timeout = timeout
            conn.retrieveFile(share, os.path.join(folder, filename), buffer)
            buffer.seek(0)
            
            # Enhanced validation
            if buffer.getbuffer().nbytes < 1000:
                st.info(f"Image too small (<1KB): {filename}")
                return None
            
            # Verify image signature (PNG/JPG only)
            header = buffer.getvalue()[:8]
            if (header.startswith(b'\x89PNG\r\n\x1a\n') or 
                header.startswith(b'\xff\xd8\xff')):
                return buffer
            else:
                return None
                
        except Exception as e:
            if attempt == max_retries - 1:
                st.warning(f"SMB fetch failed after {max_retries} retries for {filename}: {str(e)[:100]}")
            time.sleep(2 ** attempt)
        finally:
            if 'conn' in locals() and conn:
                try:
                    conn.close()
                except:
                    pass
    return None

def get_file_hash(filepath):
    """Get MD5 hash of file for cache invalidation"""
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return ""

def get_smb_image_hash(system, month_str, year):
    """Content-based hash for SMB image cache invalidation (no local file needed)"""
    key_str = f"{system}_{month_str}_{year}"
    return hashlib.md5(key_str.encode()).hexdigest()

def safe_excel_read(filepath, max_retries=3, lock_timeout=5):
    """Thread-safe Excel read with file locking (Windows)"""
    ensure_file_exists(filepath)
    
    for attempt in range(max_retries):
        try:
            # Try to lock file for reading
            fd = open(filepath, 'rb')
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
            
            df = pd.read_excel(fd, dtype=str)
            fd.close()
                
        except (msvcrt.error, PermissionError, pd.errors.EmptyDataError):
            fd.close() if 'fd' in locals() else None
            if attempt < max_retries - 1:
                time.sleep(lock_timeout / max_retries)
            else:
                st.warning(f"Could not lock {os.path.basename(filepath)} for reading")
                return pd.DataFrame(columns=COLUMNS if "Requests" in filepath else USER_COLUMNS)
    
    return pd.DataFrame(columns=COLUMNS if "Requests" in filepath else USER_COLUMNS)

def safe_excel_write(df, filepath):
    """Atomic Excel write: temp file → rename"""
    try:
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False, dir=os.path.dirname(filepath)) as temp:
            df.to_excel(temp.name, index=False, engine='openpyxl')
            temp_path = temp.name
        
        # Atomic rename
        os.replace(temp_path, filepath)
        return True
    except Exception as e:
        st.error(f"Atomic write failed for {filepath}: {e}")
        return False

def data_system_monitoring_page():
    report_year, report_month, report_month_str = show_report_month()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        dev_filename = f'DEVSPACE_{report_month_str}_{report_year}.jpg'
        dev_hash = get_smb_image_hash("DEVSPACE", report_month_str, report_year)
        with st.spinner(f"Loading DEVSPACE {report_month_str} {report_year}..."):
            dev_buffer = fetch_smb_image(dev_hash, shareName, folderName, dev_filename)
        if dev_buffer:
            st.markdown("---")
            st.subheader(f"**Devspace** - {report_month_str} {report_year}")
            st.image(dev_buffer, use_column_width=True)
        else:
            st.info(f"🖼️ DEVSPACE **{report_month_str} {report_year}** report not available")

    with col2:
        pv_filename = f'PV_{report_month_str}_{report_year}.jpg'
        pv_hash = get_smb_image_hash("PV", report_month_str, report_year)
        with st.spinner(f"Loading PV {report_month_str} {report_year}..."):
            pv_buffer = fetch_smb_image(pv_hash, shareName, folderName, pv_filename)
        if pv_buffer:
            st.markdown("---")
            st.subheader(f"**PV** - {report_month_str} {report_year}")
            st.image(pv_buffer, use_column_width=True)
        else:
            st.info(f"🖼️ PV **{report_month_str} {report_year}** report not available")

    with col3:
        nica_filename = f'NICA_{report_month_str}_{report_year}.jpg'
        nica_hash = get_smb_image_hash("NICA", report_month_str, report_year)
        with st.spinner(f"Loading NICA {report_month_str} {report_year}..."):
            nica_buffer = fetch_smb_image(nica_hash, shareName, folderName, nica_filename)
        if nica_buffer:
            st.markdown("---")
            st.subheader(f"**NICA** - {report_month_str} {report_year}")
            st.image(nica_buffer, use_column_width=True)
        else:
            st.info(f"🖼️ NICA **{report_month_str} {report_year}** report not available")

#------------------------DEV Training---------------------------------------------------------
def display_resources(resources, unique_key_prefix=""):

    num_cols = 3
    resource_items = list(resources.items())
    num_rows = (len(resource_items) + num_cols - 1) // num_cols

    # Ensure Font Awesome CSS is loaded once (can also be in global scope)
    st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">', unsafe_allow_html=True)

    for i in range(num_rows):
        cols = st.columns(num_cols, gap="large")
        for j in range(num_cols):
            index = i * num_cols + j
            if index < len(resource_items):
                name, data = resource_items[index]
                icon = data.get("icon", "fa fa-file")  # Default icon if not specified
                display_name = data.get("display_name", name)  # Use display_name if available

                if "link" in data:
                    link = data["link"]
                    cols[j].markdown(f'''
                        <a href="{link}" style="text-decoration: none;" target="_blank">
                            <button style="background-color:#09C6B5; color:white; border: 1px white solid; border-radius: 8px; padding: 15px 25px; font-size: 22px; display: flex; align-items: center; justify-content: wide; width: 100%; height: 100px; margin-bottom: 10px;">
                                <i class="{icon}" style="margin-right: 10px;"></i> {display_name}
                            </button>
                        </a>
                    ''', unsafe_allow_html=True)
                elif "path" in data:
                    file_path = data["path"]

                    if os.path.exists(file_path):
                        with open(file_path, "rb") as file:
                            file_data = file.read()
                            mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

                            cols[j].download_button(
                                label=f"<i class='{icon}' style='margin-right: 15px;'></i> {display_name}",
                                data=file_data,
                                file_name=os.path.basename(file_path),
                                mime=mime_type,
                                use_container_width=True,
                                key=f"download_{unique_key_prefix}_{name.replace(' ', '_')}",  # Unique key
                                help=f"Download {display_name}",
                            )
                    else:
                        cols[j].error(f"Material not found: {file_path}")

def training_page():
    # Inject CSS for animations and styling
    st.markdown(
        """
        <style>
        /* Mengatur lebar container utama Streamlit */
        .block-container {
            padding-left: 5rem;
            padding-right: 5rem;
            max-width: 2000px;
        }

        /* --- STYLES FOR TEXT SIZE (NEW/MODIFIED) --- */

        /* Judul Utama Halaman (misal: "Training Material & Process Knowledge") */
        /* Menargetkan h2 dari colored_header */
        .st-emotion-cache-1r6dm1x > div > div > h2 {
            font-size: 8em; /* Ukuran lebih besar */
            animation: fadeIn 1.5s ease-in-out;
        }

        /* Deskripsi di Bawah Judul Utama */
        /* Menargetkan p (paragraf) dari colored_header */
        .st-emotion-cache-1r6dm1x > div > div > p {
            font-size: 10em; /* Sedikit lebih besar dari default */
            line-height: 1.6; /* Spasi baris untuk keterbacaan */
        }

        /* Judul Expander (e.g., "Pre-Assy Training") */
        div[data-testid="stExpander"] > div:first-child {
            padding: 15px 20px;
            font-size: 2.9em; /* Membuat judul expander lebih besar lagi */
            color: #333;
            font-weight: bold;
            background-color: #ffffff;
            border-bottom: 1px solid #e0e0e0;
            border-radius: 10px 10px 0 0;
        }

        /* Teks Link Materi (e.g., "Process Training", "Machine Manual") */
        .training-link-text { /* Kelas baru untuk teks link */
            font-size: 1.5em; /* Membuat teks link sedikit lebih besar */
        }
        /* Icon juga bisa diperbesar agar proporsional */
        .training-link i {
            font-size: 2.8em; /* Ukuran icon lebih besar */
        }

        /* Teks di st.selectbox */
        div[data-testid="stSelectbox"] div[data-testid="stOption"],
        div[data-testid="stSelectbox"] div[data-testid="stSingleSelectbox"] {
            font-size: 2.0em; /* Mengatur ukuran teks di dalam selectbox */
        }
        div[data-testid="stSelectbox"] label { /* Label selectbox */
            font-size: 2.5em;
            font-weight: bold;
        }


        /* --- END STYLES FOR TEXT SIZE --- */

        div[data-testid="stExpander"] {
            background-color: #f8f9fa;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            margin-bottom: 10px;
            border: 1px solid #e0e0e0;
            overflow: hidden;
            transition: all 0.5s ease-in-out;
            width: 100%;
            font-size: 1.5em; /* Membesarakan font size */
        }

        div[data-testid="stExpander"]:hover {
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            transform: translateY(18px);
        }

    /* Styling the content area when expander is open */
    div[data-testid="stExpanderContent"] {
        padding: 25px 30px; /* Meningkatkan padding */
        font-size: 1.8em; /* Membesarakan font size */
    }

    /* Styles and Animations for list items */
    .training-link-item {
        padding: 20px 0; /* Menyederhanakan padding */
        border-bottom: 2px dashed #eee; /* Menyederhanakan border */
        transition: background-color 0.2s ease;
        opacity: 0;
        transform: translateX(-10px);
        animation: fadeInAndSlideX 0.4s ease-out forwards;
    }
    .training-link-item:last-child {
        border-bottom: none;
    }

    .training-link {
        text-decoration: none;
        color: #007bff;
        font-weight: bold;
        display: flex;
        align-items: center;
        padding: 15px 25px; /* Meningkatkan padding */
        border-radius: 8px;
        transition: background-color 0.2s ease, transform 0.2s ease, color 0.2s ease;
        min-width: 250px; /* Meningkatkan lebar minimum */
        height: 60px; /* Meningkatkan tinggi */
        font-size: 2.5em; /* Membesarakan font size */
    }

    .training-link:hover {
        background-color: #e6f2ff;
        transform: translateX(3px);
        color: #0056b3;
    }

    .training-link:hover i {
        transform: scale(1.1);
        color: #0056b3;
    }

        /* Style for local file links */
        .local-file-link {
            color: #555;
            cursor: default;
        }
        .local-file-link:hover {
            background-color: transparent;
            transform: none;
            color: #555;
        }
        .local-file-link:hover i {
             transform: none;
             color: #0A8276;
        }
        /* Staggered delay for each expander on page load (same as before) */
        div[data-testid="stExpander"]:nth-of-type(1) { animation-delay: 0.1s; }
        div[data-testid="stExpander"]:nth-of-type(2) { animation-delay: 0.2s; }
        div[data-testid="stExpander"]:nth-of-type(3) { animation-delay: 0.3s; }
        div[data-testid="stExpander"]:nth-of-type(4) { animation-delay: 0.4s; }
        div[data-testid="stExpander"]:nth-of-type(5) { animation-delay: 0.5s; }
        div[data-testid="stExpander"]:nth-of-type(6) { animation-delay: 0.6s; }
        div[data-testid="stExpander"]:nth-of-type(7) { animation-delay: 0.7s; }
        div[data-testid="stExpander"]:nth-of-type(8) { animation-delay: 0.8s; }
        div[data-testid="stExpander"]:nth-of-type(9) { animation-delay: 0.9s; }
        div[data-testid="stExpander"]:nth-of-type(10) { animation-delay: 1.0s; }
        div[data-testid="stExpander"]:nth-of-type(11) { animation-delay: 1.1s; }
        /* Add more :nth-of-type rules if you have more training categories */


        /* Keyframe animations */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes slideInUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        @keyframes slideInFromBottom {
            from { transform: translateY(50px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        @keyframes fadeInAndSlideX {
            from { opacity: 0; transform: translateX(-20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    # Link to Font Awesome for icons
    st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">', unsafe_allow_html=True)


    # --- General Training Resources Section ---
    st.header("General Training Resources")
    st.write("Training documentation available on the DEV Dashboard supports team learning and skill development.")
    add_vertical_space()

    general_training_resources = {
        "Success Factor": {"link": "https://infineon.plateau.com/learning", "icon": "fa fa-graduation-cap", "type": "url"},
        "Linkedin Learning": {"link": "https://www.linkedin.com/learning/", "icon": "fa fa-linkedin", "type": "url"},
        "MyHR Training": {"link": "https://infineon.service-now.com/esc?id=emp_taxonomy_topic&topic_id=20f401211bec95100b9a11739b4bcbc9", "icon": "fa fa-user", "type": "url"},
    }

    # Call display_resources to show general training items with animations
    display_resources(general_training_resources, "general")

    add_vertical_space() 

    # --- Training Material & Process Knowledge Section ---
    st.markdown("---")
    st.header("Training Material & Process Knowledge")
    st.write("Training documentation available on the DEV Dashboard supports all unit processes.")
    add_vertical_space()

    process_training_materials = {
        "Pre-Assy": {
            "Process Training": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Pre_Assy/Process/PA%20Handbook_20240808.pdf", "display_name": "Process"}
            },

        "DMC": {
            "Machine Manual": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDMC%2FEquipment", "display_name": "Equipment"},
            "Process": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDMC%2FProcess", "display_name": "Process"}
        },

        "Die Attach": {
            "Equipment Training": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDie%20Attach%2FEquipment%5FTraining", "display_name": "Equipment Training"},
            "Process Training": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDie%20Attach%2FProcess%5FTraining", "display_name": "Process Training"},
            "DA Material": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDie%20Attach%2FDA%5FMaterials", "display_name": "DA Material"}
        },

        "Wire Bond": {
            "Machine Manual": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FWire%20Bond%2FMachine%5FManuals",  "display_name": "Operation Manual"},
            "Process Training": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FWire%20Bond%2FProcess%5FKnowledge",  "display_name": "Process"}
        },

        "A2 Plating": {
            "PBHB": {"link": "", "display_name": "PBHB"},
            "Process": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FA2%20Plating%2FProcess", "display_name": "Process"},
            "Equipment Process Specification": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FA2%20Plating%2FEquipment%20Process%20Sepcification", "display_name": "Equipment Process Specification"}
        },

        "Front of Line Autovision": {
            "Process": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/FAV/AutovisionHandout.pdf",  "display_name": "Process"},
        },
        
        "Molding": {
            "Process": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Mold/Process/Introduction%20to%20Epoxy%20Mold%20Compound%20and%20Transfer%20Mold%20Process%20Application_R4.pdf","display_name": "Process & Material"},
        },

        "CD-Plating": {
            "PBHB": {"link": "", "display_name": "PBHB"},
            "Process":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/CD-PL/Process", "display_name": "Process"},
            "Equipment Process Specification":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FCD%2DPL%2FEquipment%20Process%20Specification", "display_name": "Equipment Process Specification"},
            "Operation Manual":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FCD%2DPL%2FOperation%20Manual ", "display_name": "Operation Manual"},
            "Defect Criteria":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FCD%2DPL%2FDefect%20Criteria", "display_name": "Defect Criteria"}
        },

        "Trim Form Singulation": {
            "Training Trim & Form":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FTrim%26Form%20Training", "display_name": "Trim & Form Training"},
            "Process":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FProcess", "display_name": "Process"},
            "Operation Manual":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FOperation%20Manual", "display_name": "Operation Manual"},
            "Defect Criteria":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FDefect%20Criteria", "display_name": "Defect Criteria"}
        },

        "Others": {
            "BE Digitalization":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FOthers%2FBE%20Digitalization", "display_name": "BE Digitalization"},
            "Others Training":
            {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FOthers%2FOthers%20Training", "display_name": "Others Training"}
        }
    }

    # Iterate through each process and create an expander for each
    for i, (process_name, materials_dict) in enumerate(process_training_materials.items()):
        # IMPORTANT: Removed 'key' argument from st.expander due to common TypeError in older Streamlit versions.
        # If you are on Streamlit 1.14.0 or newer, you can re-add `key=f"expander_{process_name.replace(' ', '_')}_{i}"`
        with st.expander(f"**{process_name} Training**", expanded=False):
            if not materials_dict:
                st.info(f"red:[No training materials available for {process_name} at this time.]")
                continue

            material_options = [data.get("display_name", name) for name, data in materials_dict.items()]

            if len(material_options) == 1:
                # When only one option, display it directly
                single_material_data = list(materials_dict.values())[0]
                display_resources({list(materials_dict.keys())[0]: single_material_data}, process_name.replace(" ", "_"))
            else:
                # Use a selectbox for multiple options
                selected_material_display_name = st.selectbox(
                    f"Select Material for {process_name}",
                    material_options,
                    # Keep key for selectbox, it's generally supported
                    key=f"select_{process_name.replace(' ', '_')}_{i}"
                )

                selected_material_actual_data = {}
                for name, data in materials_dict.items():
                    if data.get("display_name", name) == selected_material_display_name:
                        selected_material_actual_data[name] = data
                        break

                if selected_material_actual_data:
                    # Call display_resources to show selected material with animations
                    display_resources(selected_material_actual_data, process_name.replace(" ", "_"))
                else:
                    st.warning("Material not found.")

#---------------------------------Dev Tools---------------------------------------------------------------------------
def dev_tools_page():
    # --- CUSTOM CSS TO ACHIEVE THE IMAGE-LIKE UI WITH SMALLER, TIDIER CARDS AND 4 COLUMNS ---
    st.markdown(
        """
        <style>
        /* Global Streamlit overrides for a cleaner look */
        .stApp {
            background-color: #f0f2f6; /* Light gray background for the entire app */
        }
        /* Adjust padding if necessary for the main container */
        /* Note: The exact class name like .css-fg4lnv might change with Streamlit versions */
        /* .css-fg4lnv {
            padding-top: 1rem;
            padding-bottom: 1rem;
        } */

        /* Top Header Bar */
        .top-header-bar {
            background-color: #ffffff; /* White background */
            padding: 15px 25px; /* Slightly smaller padding */
            margin-bottom: 25px; /* Slightly smaller bottom margin */
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05); /* Subtle shadow */
            text-align: left;
        }
        .top-header-bar h1 {
            color: #333333;
            font-size: 2em; /* Slightly smaller header font size */
            margin: 0;
            padding: 0;
            font-weight: 600;
        }

        /* Card container styling */
        .tool-card {
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06); /* Softer and smaller shadow for cards */
            padding: 20px; /* Smaller card padding */
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: space-between;
            height: 160px; /* Smaller card height for a more compact look */
            position: relative; /* For info icon positioning */
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out, border-color 0.2s ease-in-out;
            border: 1px solid #e0e0e0; /* Thin border */
            text-decoration: none !important; /* Ensure no underline on the card itself */
            /* >>> PERBAIKAN DI SINI: Tambahkan margin-bottom <<< */
            margin-bottom: 20px; /* Tambahkan jarak di bawah setiap kartu */
        }
        .tool-card:hover {
            transform: translateY(-3px); /* Smaller lift effect on hover */
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.12); /* More pronounced shadow on hover */
            border-color: #007bff; /* Highlight border on hover */
        }

        /* Card icon styling */
        .tool-card .icon-wrapper {
            font-size: 3.6em; /* Slightly smaller icon size than before */
            color: #0A8276; /* Teal color for icons, similar to image */
            margin-bottom: 20px; /* Smaller bottom margin for icon */
        }

        /* Card text styling */
        .tool-card .tool-name {
            font-size: 1em; /* Slightly smaller font size for tool name */
            font-weight: 500;
            color: #333333;
            text-decoration: none; /* Remove underline from text link */
            display: block; /* Ensure the link takes full width */
            margin-top: auto; /* Push name to the bottom if card content is shorter */
        }
        .tool-card .tool-name:hover {
            color: #007bff; /* Blue on hover for text */
        }

        /* Info icon on cards */
        .tool-card .info-icon {
            position: absolute;
            top: 10px; /* Closer to the top */
            right: 10px; /* Closer to the right */
            color: #cccccc; /* Light gray for info icon */
            font-size: 0.9em; /* Smaller info icon size */
            cursor: pointer;
            transition: color 0.2s ease-in-out;
        }
        .tool-card .info-icon:hover {
            color: #666666; /* Darker on hover */
        }

        /* Search input styling */
        .stTextInput label {
            font-weight: bold;
            color: #555555;
            margin-bottom: 5px;
        }
        .stTextInput > div > div > input {
            border-radius: 8px;
            border: 1px solid #dddddd;
            padding: 10px 15px;
            font-size: 1em;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
            transition: border-color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        }
        .stTextInput > div > div > input:focus {
            border-color: #007bff;
            box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25);
            outline: none;
        }
        .search-container {
            margin-bottom: 30px; /* Slightly smaller bottom margin */
            padding: 15px 20px; /* Slightly smaller padding */
            background-color: #ffffff; /* White background for the search bar */
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05); /* Subtle shadow */
        }

        /* Info message style */
        .stAlert {
            border-radius: 8px;
        }

        /* Logo styling (already present, ensuring it has space below) */
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 50px; /* Add some space below the logo */
        }
        .dev-tools-logo {
            width: 300px; /* Adjust the size as needed */
            height: auto; /* Changed 'center' to 'auto' as 'center' is not a valid height value */
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    # Load Font Awesome (essential for icons)
    st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">', unsafe_allow_html=True)


    # --- Search Section ---
    st.header("Development Tools")
    st.info("Dev tools bring together different applications and data in one place, increasing developer efficiency and productivity")
    #color_name="blue-30",
 
    add_vertical_space(2)

    search_col, _ = st.columns([0.3, 0.7])

    with search_col:
        search_query = st.text_input("**Search Tools**:", "", help="Type the name of the tool you want to search for...")

    filtered_links = {}
    if search_query:
        search_query_lower = search_query.lower()
        for name, data in links.items():
            if search_query_lower in name.lower():
                filtered_links[name] = data
    else:
        filtered_links = links

    if not filtered_links:
        st.info("No tools found for your search")
        return


    # --- Card Grid Display (4 Columns) ---
    num_cols = 4 # Changed to 4 columns as per your request
    link_items = list(filtered_links.items())
    num_rows = (len(link_items) + num_cols - 1) // num_cols

    for i in range(num_rows):
        # Using no 'gap' parameter or 'gap="small"' for tighter column spacing
        # As per the image, the spacing between columns is not very large.
        cols = st.columns(num_cols) 
        for j in range(num_cols):
            index = i * num_cols + j
            if index < len(link_items):
                name, data = link_items[index]
                link = data["link"]
                icon = data["icon"]
                
                # Using custom HTML for each card, with the updated structure
                cols[j].markdown(f'''
                    <a href="{link}" target="_blank" style="text-decoration: none;">
                        <div class="tool-card">
                            <i class="fa fa-{icon} icon-wrapper"></i>
                            <span class="tool-name">{name}</span>
                            <i class="fa fa-info-circle info-icon"></i>
                        </div>
                    </a>
                ''', unsafe_allow_html=True)

links = {
    "IFX INTRANET": {"link": "https://intranet.infineon.com/", "icon": "home"},
    "MY LEAVE": {"link": "https://sappeslb.sap.infineon.com/sap/bc/ui5_ui5/sap/z_leaverequest/index.html", "icon": "paper-plane"},
    "MY IT": {"link": "https://webnetprod.muc.infineon.com/MyIT/", "icon": "windows"},
    "PICTURE VIEWER": {"link": "https://pictureviewer-bedev.infineon.com:8080/viewpictures", "icon": "image"},
    "Opcenter Portal": {"link": "https://opcenter.bth.infineon.com/OpcenterPortal/default.htm#/login", "icon": "paste"},
    "Opcenter Shopfloor UI": {"link": "https://opcenter.bth.infineon.com/OpcenterWeb/login", "icon": "database"},
    "KLUSA": {"link": "https://klusa4.intra.infineon.com/klusa_ifx_projects/klusaweb/", "icon": "code"},
    "DEVSMETS": {"link": "https://jiradc.intra.infineon.com/secure/Dashboard.jspa", "icon": "calendar"},
    "PROJECT DOCUMENT": {"link": "https://ishare.infineon.com/sites/BE_DEV_PO/SitePages/BE%20RDE%20Project%20Office.aspx", "icon": "folder-open"},
    "PBHB": {"link": "https://intranet-content.infineon.com/explore/operations/TechnologyExcellence/ComplexityManagement/ProcessBlockCatalogPBC/Pages/index_en.aspx", "icon": "book"},
    "FMEA": {"link": "https://intranet-content.infineon.com/explore/aboutinfineon/QM/QMProcesses/FMEA/SitePages/index_en.aspx", "icon": "table"},
    "OE APPLICATION": {"link": "https://oe.bth.infineon.com/", "icon": "trophy"},
    "Attire System": {"link": "https://attire.bth.infineon.com/Home", "icon": "user"},
    "Permission System": {"link": "https://apps.bth.infineon.com/Pms_System/Permission_NonShopfloor.aspx", "icon": "unlock-alt"},
    "NICA": {"link": "https://nica.icp.infineon.com/en/search", "icon":"check-square"},
    "PLM Publishing": {"link": "https://plmpublishing.icp.infineon.com/searchtable", "icon": "eye"},
    "IFBT DEV SYSTEM": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/IFBT_DEV_Spare-Part/IFBT_DEV_Spare_Part/Index.html", "icon": "server"},
    "HALO": {"link": "https://haloprd.icp.infineon.com/", "icon": "globe"},
    "PDR+": {"link": "https://pdr-plus-prd.icp.infineon.com/", "icon": "file"},
    "ICRuM": {"link": "http://prodtest.bth.infineon.com:8081/login", "icon": "calculator"},
    "iFAct": {"link": "https://ifact.sin.infineon.com/myjobs", "icon": "flask"},
    "Batam Tableau URL": {"link": "https://tableau.infineon.com/#/site/ITFI/views/Batam_Tableau_URL/BAT_Tableau_URL?:iid=1", "icon": "list-ul"},
    "Opcenter ODS Report": {"link": "https://tableau.infineon.com/#/site/ITFI/views/MESReportToC/BATMESreportToC", "icon": "list"},
    "INSiG - AOI Log Data " : {"link": "https://insig-productive-insig.ap-sg-1.icp.infineon.com/", "icon": "search"},
    "eArchive" : {"link": "https://efilestore.bth.infineon.com/earchive_retrieval/Logon.aspx", "icon": "cloud-upload"},
    "ESH APPLICATION": {"link": "https://hsse.bth.infineon.com/", "icon": "medkit"},
    "Equipment Reservation Tool": {"link": "https://ertprod.bth.infineon.com/ert/", "icon": "lock"},
    "CONCUR": {"link": "https://us2.concursolutions.com/nui/signin/pwd?signedout=inactivity&lang=en", "icon": "plane"},
    "VISIT - Visitor/Preregister Visit": {"link": "https://visitor-management.infineon.com/", "icon": "group"},
    "IDPF/SDHB Documents": {"link": "https://webnetprod.muc.infineon.com/ecmweb/dctmpublish/gen0001_sdhb4/gen0001_sdhb4.asp", "icon": "map"},
    "Process Block Catalogue": {"link": "https://webnetprod.muc.infineon.com/PBCatalogue/Default.aspx", "icon": "cube"},
    "IFX Worldwide Packages": {"link": "https://www.infineon.com/cms/en/product/packages/", "icon": "microchip"},
    "OEE Report": {"link": "https://tableau.infineon.com/#/site/ITFI/views/OEEReportforPOB/OEEStandardReport?:iid=1", "icon": "gear"},
    "Statistical Platform": {"link": "https://rbgxv673.rbg.infineon.com/statistics/", "icon": "line-chart"},    
    "IP Portal": {"link": "https://ipms.infineon.com/ipms/AppIpms.jsp?is-smart", "icon": "fa fa-lightbulb"},
    "SPIRAL": {"link": "https://spiral.muc.infineon.com/spiral", "icon": "spinner"},
    "GPT4IFX": {"link": "https://outsystems-muc-prod.infineon.com/GPT4IFX/", "icon": "wrench"},
    "PDA Wafer Inventory": {"link": "https://ishare.ap.infineon.com/sites/WaferInventory/_layouts/15/WopiFrame2.aspx?sourcedoc=%7B15E1B4C2-181F-4369-9D79-7B9DF9366547%7D&file=PDA%20Wafer%20List%20DC26.xlsx&action=default", "icon": "inbox"},
    "DEV CT300 Request": {"link": "https://ishare.ap.infineon.com/sites/CT300WI/_layouts/15/WopiFrame.aspx?sourcedoc=%7B6de387d2-7b2d-4833-bf31-2b536d89ebe4%7D&action=default&slrid=3c338ca1-ddb1-8088-c64f-28eeb8c7d0f5", "icon": "clipboard"},
    "PLATO" : {"link": "https://mucsa1446.infineon.com/e1ns/portal/#action=clearFilter&cmd=CMD_E1ns_start_page", "icon": "bookmark"},
    "YIP" : {"link": "https://yiphlp56.intra.infineon.com:8443/app/", "icon": "lightbulb-o"},
    "NOSTAS Request" : {"link": "https://workflowgenerator.infineon.com/portal/DEV_NOSTAS_Request_eForm/home", "icon": "file-text"},
    "MyMD" : {"link": "https://mat-database-devlogdatabase.ap-sg-1.icp.infineon.com/", "icon": "barcode"},
    "iProjEx" : {"link": "https://plmapps.icp.infineon.com/iprojex/myItems/active", "icon": "key"},
    "Team Center" : {"link": "https://teamcenterhome.infineon.com/nermal.shtml", "icon": "star"},
    "Basic Evaluation in Automated Test System (BEAST)": {"link": "https://tableau.infineon.com/#/site/ITFI/views/BEATSFINALREPORTV1/ActualvsPlanUPH/49d34c7e-0acb-48bb-8710-18226e22bd67/BEATSBAT?:iid=1", "icon" : "building"},
    "TDDB Dashboard": {"link": "https://insig-aoi-report-,automation.ap-sg-1.icp.infineon.com/", "icon" : "desktop"},
    "Component Task Tracking (CTT)": {"link": "https://ctt.intra.infineon.com/RequestAccess", "icon" : "tasks"},
    "Lab Manager": {"link": "https://labmanager.intra.infineon.com/register", "icon" : "flask"}  
}


st.markdown(
        """
        <style>
        /* ... your existing CSS for global, top-header-bar, tool-card, etc. ... */

        /* New CSS for the logo */
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 50px; /* Add some space below the logo */
        }
        .dev-tools-logo {
            width: 300px; /* Adjust the size as needed */
            height: auto;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

#-------------------------------------Main Page--------------------------------------------------------------
pages = {
    "Home": landing_page,
    "Data System Monitoring": data_system_monitoring_page,
    "Training & Knowledge": training_page,
    "Dev Tools": dev_tools_page,
}

st.sidebar.title("**BE DEV Dashboard**")
with st.sidebar:
    selected_dash = option_menu(
        menu_title=None,
        options=list(pages.keys()),
        icons=["house", "database", "universal-access", "wrench"],
        menu_icon="speedometer",
        default_index=0
    )

pages[selected_dash]()

st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {
        width: 300px !important; # Adjust this value as needed
        max-width: 300px !important; # Ensure it doesn't exceed this width
        padding-left: 30px; # Optional: adjust padding if content is too close to edge
        padding-right: 30px; # Optional: adjust padding
    }
    </style>
    """,
    unsafe_allow_html=True,
)





# Updated to use safe_excel_read
@st.cache_data
def load_Requests(_hash=REQUESTS_FILE):
    """Cache invalidates on file hash change"""
    file_hash = get_file_hash(REQUESTS_FILE)
    return safe_excel_read(REQUESTS_FILE)

@st.cache_data  
def load_user_data(_hash=USER_FILE):
    """Cache invalidates on file hash change"""
    file_hash = get_file_hash(USER_FILE)
    return safe_excel_read(USER_FILE)

def normalize_Requestor_email(requestor_email: str, domain: str = "infineon.com") -> str:
    if not requestor_email or not isinstance(requestor_email, str):
        return ""
    email = str(requestor_email).strip().lower()
    if "@" in email:
        return email
    return f"{email}@{domain}"

def save_user_data(df):
    try:
        df.to_excel(USER_FILE, index=False)
        return True
    except Exception as e:
        st.error(f"Error saving user data: {e}")
        return False

@st.cache_data(ttl=300)
def get_Requestor_email_from_Username_cached(Username: str, user_df: pd.DataFrame):
    if not Username or user_df.empty:
        return f"{Username}@infineon.com"
    try:
        mask = user_df['Username'].astype(str).str.lower() == str(Username).lower()
        if mask.any():
            email = user_df.loc[mask, 'Requestor_email'].iloc[0]
            return normalize_Requestor_email(str(email))
    except:
        pass
    return f"{Username}@infineon.com"

## ENHANCED OUTLOOK EMAIL FUNCTIONS (IMPROVED HTML BODIES)
def normalize_email(email: str, domain: str = "infineon.com") -> str:
    """Normalize and validate email address"""
    if not email or not isinstance(email, str):
        return ""
    email = str(email).strip().lower()
    if "@" in email:
        return email
    return f"{email}@{domain}"

def is_valid_email(email: str) -> bool:
    """Strict email validation"""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    return "@" in email and "." in email.split("@")[-1] and len(email) > 5

def send_outlook_email(to_emails, subject, html_body, attachment=None):
    """Enhanced Outlook email sender with better error handling"""
    try:
        if not to_emails:
            return False, "Recipient email is required."
        
        to_emails = normalize_email(to_emails)
        if not is_valid_email(to_emails):
            return False, "Invalid email address format."

        pythoncom.CoInitialize()
        try:
            ol = win32com.client.Dispatch("Outlook.Application")
            mail = ol.CreateItem(0)
            mail.Subject = subject
            mail.To = to_emails
            mail.HTMLBody = html_body

            if attachment and os.path.exists(attachment):
                mail.Attachments.Add(os.path.abspath(attachment))

            mail.Send()
            print(f"[EMAIL] ✅ Sent to {to_emails}")
            return True, "Email sent successfully!"
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        print(f"[EMAIL] ❌ Failed: {e}")
        return False, f"Failed to send email: {str(e)}"

def is_valid_Requestor_email(Requestor_email: str) -> bool:
    if not Requestor_email or not isinstance(Requestor_email, str): 
        return False
    email = Requestor_email.strip()
    return "@" in email and "." in email.split("@")[-1]

def send_outlook_Requestor_email(to_Requestor_emails, subject, html_body, attach=None):
    try:
        if not to_Requestor_emails:
            return False, "Recipient email is required."
        to_Requestor_emails = normalize_Requestor_email(to_Requestor_emails)
        if not is_valid_Requestor_email(to_Requestor_emails):
            return False, "Invalid email address"

        pythoncom.CoInitialize()
        ol = win32com.client.Dispatch("outlook.application")
        newmail = ol.CreateItem(0)
        newmail.Subject = subject
        newmail.To = to_Requestor_emails
        newmail.HTMLBody = html_body
        if attach and os.path.exists(attach):
            newmail.Attachments.Add(os.path.abspath(attach))
        newmail.Send()
        pythoncom.CoUninitialize()
        return True, "Email sent successfully!"
    except Exception as e:
        try:
            pythoncom.CoUninitialize()
        except:
            pass
        print(f"[EMAIL] Failed: {e}")
        return False, f"Failed to send email: {e}"


import html

def create_enhanced_new_request_html(record_id, requestor, requestor_email, category, details, quantity=1, material='N/A', color='N/A', target_date=None):
    """Enhanced responsive HTML for new request notifications"""
    target_date_str = target_date.strftime('%d %B %Y') if target_date else datetime.now().strftime('%d %B %Y')
    safe_details = html.escape(str(details))[:800] + ("..." if len(str(details)) > 800 else "")
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New 3D Print Request #{record_id}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; padding: 0; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
            line-height: 1.6; color: #2d3748;
        }}
        .container {{ max-width: 650px; margin: 20px auto; background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 25px 50px rgba(0,0,0,0.15); }}
        .header {{ 
            background: linear-gradient(135deg, #4299e1 0%, #3182ce 50%, #2b6cb0 100%); 
            color: white; padding: 40px 30px; text-align: center; position: relative;
        }}
        .header::before {{ content: '🖨️'; font-size: 64px; display: block; margin-bottom: 15px; }}
        .header h1 {{ margin: 0 0 10px; font-size: 36px; font-weight: 800; text-shadow: 0 2px 10px rgba(0,0,0,0.3); }}
        .header-meta {{ font-size: 16px; opacity: 0.95; }}
        .content {{ padding: 40px 35px; }}
        .summary-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); 
            gap: 25px; margin: 30px 0; 
        }}
        .card {{ 
            background: linear-gradient(145deg, #f7fafc, #edf2f7); 
            padding: 25px; border-radius: 16px; text-align: center; 
            border: 1px solid #e2e8f0; box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            transition: transform 0.3s ease;
        }}
        .card:hover {{ transform: translateY(-5px); }}
        .card-icon {{ font-size: 32px; margin-bottom: 12px; }}
        .card-label {{ font-weight: 700; color: #4a5568; margin-bottom: 8px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .card-value {{ font-size: 24px; font-weight: 800; color: #2d3748; }}
        .details-section {{ 
            background: linear-gradient(135deg, #f0fff4 0%, #e6fffa 100%); 
            padding: 30px; border-radius: 16px; margin: 30px 0; 
            border-left: 6px solid #48bb78;
        }}
        .details-section h2 {{ color: #22543d; margin-top: 0; font-size: 24px; }}
        .detail-grid {{ display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-top: 20px; }}
        .detail-item {{ background: white; padding: 20px; border-radius: 12px; border-left: 4px solid #4299e1; }}
        .detail-label {{ font-weight: 700; color: #4a5568; margin-bottom: 8px; }}
        .detail-value {{ font-size: 16px; color: #2d3748; line-height: 1.5; }}
        .status-badge {{ 
            display: inline-block; background: linear-gradient(135deg, #48bb78, #38a169); 
            color: white; padding: 12px 28px; border-radius: 50px; font-weight: 700; 
            font-size: 16px; box-shadow: 0 8px 25px rgba(72,187,120,0.4); margin: 25px auto;
        }}
        .footer {{ 
            background: #2d3748; color: #a0aec0; padding: 30px; text-align: center; font-size: 14px;
        }}
        @media (max-width: 600px) {{ 
            .summary-grid {{ grid-template-columns: 1fr; }}
            .detail-grid {{ grid-template-columns: 1fr; }}
            .content {{ padding: 25px 20px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>New 3D Print Request #{record_id}</h1>
            <p class="header-meta">Status: <strong>Under Review</strong> | {datetime.now().strftime('%d %B %Y %H:%M')}</p>
        </div>
        <div class="content">
            <p style="font-size: 18px; margin-bottom: 30px;">Hello 3D Printing Team,</p>
            <p style="font-size: 16px; color: #4a5568;">A new request has been submitted. Please review the details below:</p>
            
            <div class="summary-grid">
                <div class="card">
                    <div class="card-icon">👤</div>
                    <div class="card-label">Requestor</div>
                    <div class="card-value">{requestor}</div>
                </div>
                <div class="card">
                    <div class="card-icon">📅</div>
                    <div class="card-label">Target Date</div>
                    <div class="card-value">{target_date_str}</div>
                </div>
                <div class="card">
                    <div class="card-icon">📦</div>
                    <div class="card-label">Quantity</div>
                    <div class="card-value">{quantity}</div>
                </div>
                <div class="card">
                    <div class="card-icon">🎨</div>
                    <div class="card-label">Material</div>
                    <div class="card-value">{material}</div>
                </div>
                <div class="card">
                    <div class="card-icon">🌈</div>
                    <div class="card-label">Color</div>
                    <div class="card-value">{color}</div>
                </div>
                <div class="card">
                    <div class="card-icon">📂</div>
                    <div class="card-label">Category</div>
                    <div class="card-value">{category}</div>
                </div>
            </div>

            <div class="details-section">
                <h2>📋 Request Details</h2>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Request ID</div>
                        <div class="detail-value"><strong>#{record_id}</strong></div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Email</div>
                        <div class="detail-value">{requestor_email}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Description</div>
                        <div class="detail-value">{safe_details}</div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 25px;">
                    <div class="status-badge">Action Required</div>
                </div>
            </div>
        </div>
        <div class="footer">
            <p>3D Printing Request System | Infineon Technologies<br>
            Automated notification - please do not reply directly to this email.</p>
        </div>
    </div>
</body>
</html>"""

def send_new_request_notification_to_admin(record_id, requestor, requestor_email, category, details, quantity=1, material='N/A', color='N/A', target_date=None, attachment_path=None):
    """Enhanced admin notification with improved HTML"""
    try:
        user_df = load_user_data()
        admin_df = user_df[user_df['Role'].str.lower() == 'admin']
        admin_emails = []
        for _, row in admin_df.iterrows():
            email = normalize_email(row.get('Requestor_email') or f"{row.get('Username')}@infineon.com")
            if email:
                admin_emails.append(email)
        if not admin_emails:
            admin_emails = ["sitihanafinilam.sari@infineon.com"]

        target_date_str = target_date.strftime('%d/%m/%Y') if target_date else datetime.now().strftime('%d/%m/%Y')
        
        safe_details = html.escape(str(details))[:500]
        truncated_msg = "..." if len(str(details)) > 500 else ""
        
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 0; background: #f8fafc; line-height: 1.6; color: #334155; }}
        .email-container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.08); overflow: hidden; }}
        .header h1 {{ margin: 0 0 8px; font-size: 32px; font-weight: 800; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); mso-line-height-rule: exactly; mso-text-raise: 2pt; }}
        .header-meta {{ opacity: 0.95; font-size: 16px; }}
        .content {{ padding: 40px 30px; }}
        .summary-card {{ background: linear-gradient(135deg, #e0f7ff 0%, #b3e5fc 100%); border: 1px solid #0288d1; border-radius: 12px; padding: 30px; margin: 30px 0; mso-line-height-rule: exactly; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 20px; }}
        .summary-item {{ background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-top: 4px solid #3b82f6; }}
        .summary-label {{ font-weight: 600; color: #475569; margin-bottom: 8px; font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .summary-value {{ font-size: 20px; font-weight: 700; color: #1e293b; }}
        .details-section {{ background: #f8fafc; padding: 25px; border-radius: 12px; margin: 25px 0; border-left: 5px solid #10b981; }}
        .details-section h3 {{ color: #1e293b; margin-top: 0; font-size: 22px; }}
        .detail-row {{ display: flex; margin: 16px 0; align-items: center; }}
        .detail-label {{ font-weight: 600; color: #475569; width: 140px; flex-shrink: 0; }}
        .detail-value {{ flex: 1; background: white; padding: 12px 16px; border-radius: 8px; border: 1px solid #e2e8f0; font-weight: 500; }}
        .status-badge {{ display: inline-block; background: #10b981; color: white; padding: 10px 20px; border-radius: 25px; font-weight: 700; font-size: 16px; margin: 20px auto; box-shadow: 0 4px 12px rgba(16,185,129,0.3); }}
        .cta-section {{ text-align: center; margin: 40px 0; }}
        .cta-button {{ display: inline-block; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 16px 32px; text-decoration: none; border-radius: 12px; font-weight: 700; font-size: 16px; box-shadow: 0 8px 25px rgba(16,185,129,0.3); transition: all 0.3s; }}
        .cta-button:hover {{ transform: translateY(-2px); box-shadow: 0 12px 35px rgba(16,185,129,0.4); }}
        .footer {{ background: #1e293b; color: #94a3b8; padding: 30px; text-align: center; font-size: 14px; line-height: 1.6; }}
        @media (max-width: 600px) {{ 
            .summary-grid {{ grid-template-columns: 1fr; }}
            .detail-row {{ flex-direction: column; align-items: flex-start; }}
            .detail-label {{ width: auto; margin-bottom: 8px; }}
            .content {{ padding: 25px 20px; }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>New 3D Print Request #{record_id}</h1>
            <p class="header-meta">Submitted {datetime.now().strftime('%d %B %Y at %H:%M')} • Status: Review</p>
        </div>
        <div class="content">
            <p style="font-size: 18px; margin-bottom: 30px;">Hello Admin Team,</p>
            <p>A new 3D printing request requires your attention. Complete details below:</p>
            
            <div class="summary-card">
                <h2 style="text-align: center; color: #1e40af; margin-bottom: 25px; font-size: 28px;">📋 Request Summary</h2>
                <div class="summary-grid">
                    <div class="summary-item">
                        <div class="summary-label">Requestor</div>
                        <div class="summary-value">{requestor}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Category</div>
                        <div class="summary-value">{category}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Target Date</div>
                        <div class="summary-value">{target_date_str}</div>
                    </div>
                    <div class="summary-item">
                        <div class="summary-label">Material</div>
                        <div class="summary-value">{material}</div>
                    </div>  
                    <div class="summary-item">
                        <div class="summary-label">Color</div>
                        <div class="summary-value">{color}</div>
                    </div> 
                    <div class="summary-item">
                        <div class="summary-label">Quantity</div>
                        <div class="summary-value">{quantity}</div>
                    </div>                                     
                </div>
            </div>

            <div class="details-section">
                <h3>📄 Full Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Description:</span>
                    <span class="detail-value">{safe_details}{truncated_msg}</span>
                </div>
            </div>  
        </div>
        <div class="footer">
            <p>3D Printing Request Management System | Infineon Technologies<br>
            Need help? Contact the 3D Printing team.<br>
            <small>This is an automated system notification - please do not reply to this email.</small>
            </p>
        </div>
    </div>
</body>
</html>
        """
        result = send_outlook_Requestor_email(
            to_Requestor_emails="; ".join(admin_emails),
            subject=f"🖨️ NEW REQUEST #{record_id} - {requestor} - {category}",
            html_body=html_body,
            attach=attachment_path)
        print(f"[ADMIN NOTIF] ✅ Request #{record_id} notification sent")
        return result
    except Exception as e:
        error_msg = f"[ADMIN NOTIF ERROR #{record_id}] {str(e)}"
        print(error_msg)
        if 'st' in locals():
            st.error(error_msg)
        return False, error_msg
    
def send_status_change_Requestor_email_to_user(record_id, requestor_email, new_status, old_status=None, admin_comment=None):
    """Clean & Consistent Status Update Email"""
    try:
        requestor_email = normalize_Requestor_email(requestor_email)
        df = load_Requests()

        # Get request details
        mask = df['No'] == record_id
        row = df[mask].iloc[0] if mask.any() else None
        
        time_in_previous = "N/A"
        try:
            history_raw = row['Status History'] if row is not None else '[]'
            history = json.loads(history_raw) if history_raw.strip() else []
            prev_entry = next((h for h in reversed(history) if h.get("Status") == old_status), None)
            if prev_entry and prev_entry.get("Date"):
                prev_time = datetime.strptime(prev_entry["Date"], "%d/%m/%y %H:%M")
                delta = datetime.now() - prev_time
                days = delta.days
                hours = delta.seconds // 3600
                mins = (delta.seconds % 3600) // 60
                time_in_previous = f"{days}d {hours}h {mins}m" if days > 0 else f"{hours}h {mins}m"
        except:
            pass

        # Dynamic status messages
        status_config = {
                    "Completed": {"emoji": "🎉", "title": "Completed Successfully!", "color": "#10b981"},
                    "Rejected": {"emoji": "❌", "title": "Request Rejected", "color": "#ef4444"},
                    "Buy-off": {"emoji": "✅", "title": "Quality Approved", "color": "#059669"},
                    "Printing Process": {"emoji": "🖨️", "title": "Printing in Progress", "color": "#f59e0b"},
                    "3D drawing processing": {"emoji": "📐", "title": "Design Processing", "color": "#8b5cf6"},
                    "Review Drawing": {"emoji": "📋", "title": "Under Review", "color": "#64748b"}
                }
        status_info = status_config.get(new_status, {"emoji": "📌", "title": new_status, "color": "#6b7280"})

        username = requestor_email.split('@')[0].replace('.', ' ').title()

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, sans-serif; margin: 0; padding: 0; background: #f8fafc; line-height: 1.6; color: #334155; }}
        .email-container {{ max-width: 620px; margin: 20px auto; background: white; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, {status_info['color']} 0%, {status_info['color']}cc 100%); color: white; padding: 40px 30px; text-align: center; mso-line-height-rule: exactly; }}
        .header h1 {{ margin: 0 0 8px; font-size: 28px; font-weight: 800; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); mso-line-height-rule: exactly; mso-text-raise: 2pt; }}
        .content {{ padding: 40px 30px; }}
        .status-card {{ background: white; border: 2px solid {status_info['color']}; border-radius: 12px; padding: 25px; margin: 25px 0; text-align: center; }}
        .detail-row {{ display: flex; margin: 16px 0; align-items: center; }}
        .detail-label {{ font-weight: 600; color: #475569; width: 160px; flex-shrink: 0; }}
        .detail-value {{ flex: 1; background: #f8fafc; padding: 12px 16px; border-radius: 8px; border: 1px solid #e2e8f0; }}
        .footer {{ background: #1e293b; color: #94a3b8; padding: 30px; text-align: center; font-size: 14px; }}
        @media (max-width: 600px) {{ 
            .detail-row {{ flex-direction: column; align-items: flex-start; }}
            .detail-label {{ width: auto; margin-bottom: 8px; }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>{status_info['emoji']} {status_info['title']}</h1>
            <p>Request #{record_id} • Updated {datetime.now().strftime('%d %B %Y at %H:%M')}</p>
        </div>
        <div class="content">
            <p style="font-size: 18px;">Hi <strong>{username}</strong>,</p>
            <p>Your 3D printing request has been updated by the admin team.</p>

            <div class="status-card">
                <h2 style="margin:0 0 15px 0; color:{status_info['color']};">Current Status: <strong>{new_status}</strong></h2>
                {f'<p><strong>Previous Status:</strong> {old_status or "Pending"}</p>' if old_status else ''}
            </div>

            <div class="details-section" style="background:#f8fafc; padding:25px; border-radius:12px; margin:25px 0; border-left:5px solid #3b82f6;">
                <h3 style="margin-top:0;">Request Information</h3>
                <div class="detail-row"><span class="detail-label">Request ID:</span><span class="detail-value">#{record_id}</span></div>
                <div class="detail-row"><span class="detail-label">Update Date:</span><span class="detail-value">{datetime.now().strftime('%d/%m/%Y')}</span></div>
            </div>

            {f'''
            <div style="background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); padding:25px; border-radius:12px; border-left:6px solid #f59e0b; margin:25px 0;">
                <h3 style="margin:0 0 12px 0; color:#92400e;">💬 Admin Feedback</h3>
                <p style="margin:0; background:white; padding:15px; border-radius:8px;">{admin_comment}</p>
            </div>
            ''' if admin_comment else ''}

        </div>
        <div class="footer">
            <p>3D Printing Request Management System | Infineon Technologies<br>
            <small>This is an automated notification — please do not reply to this email.</small></p>
        </div>
    </div>
</body>
</html>
        """

        return send_outlook_Requestor_email(
            to_Requestor_emails=requestor_email,
            subject=f"{status_info['emoji']} Request #{record_id} • {new_status}",
            html_body=html_body
        )
    except Exception as e:
        print(f"Status update email error: {e}")
        return False, str(e)
    
# ========================= FILE MANAGEMENT =========================
def save_Requests(df):
    """Safe atomic write - clears cache after success"""
    df_clean = df.copy()
    # Pre-process
    date_cols = ['Request Date', 'Target Date', 'Completed Date', 'Status Start Time']
    for col in date_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
    
    if 'Quantity' in df_clean:
        df_clean['Quantity'] = pd.to_numeric(df_clean['Quantity'], errors='coerce').fillna(1).astype(int)
    
    if safe_excel_write(df_clean, REQUESTS_FILE):
        # Clear cache to force reload
        st.cache_data.clear()
        st.success("✅ Requests saved safely")
        return True
    return False

def save_user_data(df):
    """Safe atomic user data write"""
    if safe_excel_write(df, USER_FILE):
        st.cache_data.clear()
        return True
    return False
    



@st.cache_data(ttl=300)
def get_Requestor_email_from_Username_cached(Username: str, user_df: pd.DataFrame):
    if not Username or user_df.empty:
        return f"{Username}@infineon.com"
    try:
        mask = user_df['Username'].astype(str).str.lower() == str(Username).lower()
        if mask.any():
            email = user_df.loc[mask, 'Requestor_email'].iloc[0]
            return normalize_Requestor_email(str(email))
    except:
        pass
    return f"{Username}@infineon.com"

# ========================= STATUS TIMELINE HORIZONTAL =========================
def get_status_timeline_html(row):
    """Generate horizontal timeline untuk status beserta tanggal update (chain-aware)"""
    df = load_Requests()
    
    # Get full chain history
    full_history = []
    current_no = row.get('No')
    visited = set()
    
    while current_no and current_no not in visited:
        visited.add(current_no)
        mask = df['No'] == current_no
        if mask.any():
            row_data = df[mask].iloc[0]
            history_raw = row_data.get('Status History', '[]')
            try:
                history = json.loads(history_raw) if history_raw.strip() else []
                full_history.extend(history)
            except:
                pass
            # Next parent
            parent_no = row_data.get('Parent_No')
            if pd.isna(parent_no) or str(parent_no).strip() == '':
                break
            current_no = parent_no
        else:
            break
    
    # Dedupe latest first
    seen = {}
    history = []
    for event in reversed(full_history):
        status = event.get('Status')
        if status and status not in seen:
            seen[status] = True
            history.append(event)
    
    if not history:
        return "<p style='color:#64748b;'>No status history yet.</p>"

    timeline_html = """
    <div style="margin: 20px 0;">
        <div style="display: flex; justify-content: space-between; position: relative; padding: 10px 0;">
    """

    icons = {
        "Review Drawing": "📋",
        "3D drawing processing": "📐",
        "Printing Process": "🖨️",
        "Buy-off": "✅",
        "Completed": "🏆",
        "Rejected": "❌"
    }

    colors = {
        "Completed": "#10b981",
        "Rejected": "#ef4444",
        "Buy-off": "#3b82f6",
        "Printing Process": "#f59e0b",
        "3D drawing processing": "#8b5cf6",
        "Review Drawing": "#64748b"
    }

    for i, step in enumerate(history):
        status = step.get("Status", "")
        date = step.get("Date", "")
        icon = icons.get(status, "📌")
        color = colors.get(status, "#64748b")
        is_last = i == len(history) - 1

        timeline_html += f"""
            <div style="text-align: center; flex: 1; position: relative;">
                <div style="width: 60px; height: 60px; margin: 0 auto; background: {color}; 
                            color: white; border-radius: 50%; display: flex; align-items: center; 
                            justify-content: center; font-size: 28px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                    {icon}
                </div>
                <p style="margin: 8px 0 2px; font-weight: 700; color: #1e293b; font-size: 0.95rem;">{status}</p>
                <p style="margin: 0; color: #64748b; font-size: 0.8rem;">{date}</p>
                {"<div style='position:absolute; top:28px; left:100%; width:100%; height:4px; background:#e2e8f0;'></div>" if not is_last else ""}
            </div>
        """

    timeline_html += "</div></div>"
    return timeline_html

# ========================= REQUEST MANAGEMENT =========================
def add_or_update_Request(record_id=None, **kwargs):
    """
    Add new request or update existing one.
    - Create: record_id=None, pass Requestor, Category, etc. -> returns (new_id, msg)
    - Update: record_id=int, pass Status, Admin_Comments -> returns (True/False, msg)
    """
    try:
        df = load_Requests()
        if record_id:
            mask = df['No'] == record_id
            if not mask.any():
                return False, "Request not found"

            row_idx = df.index[mask][0]
            old_status = str(df.loc[row_idx, 'Status'])
            new_status = kwargs.get('Status', old_status)
            admin_comment = kwargs.get('Admin Comments', '')

            if old_status == new_status and not admin_comment:
                return True, "No changes needed"

            # UPDATE EXISTING ROW IN-PLACE
            df.loc[row_idx, 'Status'] = new_status
            df.loc[row_idx, 'Status Start Time'] = datetime.now().strftime("%d/%m/%Y %H:%M")
            df.loc[row_idx, 'Admin Comments'] = admin_comment

            if new_status == "Completed":
                df.loc[row_idx, 'Completed Date'] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            # Update Status History JSON
            try:
                history_raw = str(df.loc[row_idx, 'Status History'])
                history = json.loads(history_raw) if history_raw.strip() else []
            except:
                history = []
            history.append({
                "Status": new_status,
                "Date": datetime.now().strftime("%d/%m/%y %H:%M"),
                "Admin Comments": admin_comment or ""
            })
            df.loc[row_idx, 'Status History'] = json.dumps(history)

            if save_Requests(df):
                requestor_email = str(df.loc[row_idx, 'Requestor_email'])
                email_success, _ = send_status_change_Requestor_email_to_user(
                    record_id=record_id,
                    requestor_email=requestor_email,
                    new_status=new_status,
                    old_status=old_status,
                    admin_comment=admin_comment)
                
                msg = f"Status updated to {new_status}"
                if email_success:
                    msg += " (Email sent)"
                return True, msg
            else:
                return False, "Failed to save changes"

        else:
            # CREATE new request
            df_no_num = pd.to_numeric(df['No'], errors='coerce')
            max_no = df_no_num.max()
            new_no = 1 if pd.isna(max_no) else int(max_no + 1)
            initial_status = 'Review Drawing'
            new_row = {
                'No': new_no,
                'Parent_No': '',
                'Request Date': datetime.now().strftime("%d/%m/%Y"),
                'Requestor': kwargs.get('Requestor', 'N/A'),
                'Requestor_email': kwargs.get('Requestor_email', 'N/A'),
                'Target Date': kwargs.get('Target_Date', datetime.now().strftime("%d/%m/%Y")),
                'Category': kwargs.get('Category', 'N/A'),
                'Details': kwargs.get('Details', 'N/A'),
                'Status': initial_status,
                'Status Start Time': datetime.now().strftime("%d/%m/%Y %H:%M"),
                'Status History': json.dumps([{"Status": initial_status, "Date": datetime.now().strftime("%d/%m/%y %H:%M")}]),
                'Quantity': int(kwargs.get('Quantity', 1)),
                'Material': kwargs.get('Material', 'N/A'),
                'Color': kwargs.get('Color', 'N/A'),
                'Completed Date': '',
                'Admin Comments': ''
            }

            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            if save_Requests(df):
                send_new_request_notification_to_admin(                    
                    record_id=new_no,
                    requestor=kwargs.get('Requestor', ''),
                    requestor_email=kwargs.get('Requestor_email', ''),
                    category=kwargs.get('Category', ''),
                    details=kwargs.get('Details', '')
                )
                return new_no, "Request created successfully"
            else:
                return False, "Failed to create request"

    except Exception as e:
        st.error(f"Error in add_or_update_Request: {str(e)}")
        return False, str(e)


# ========================= DYNAMIC PROGRESS TRACKER  =========================
def dynamic_progress_tracker(row):
    """Menampilkan progress tracker horizontal SEQUENTIAL (completed + current only)"""
    
    current_status = str(row.get('Status', 'Review Drawing')).strip()
    history_raw = row.get('Status History', '')
    
    try:
        history = json.loads(history_raw) if pd.notna(history_raw) and str(history_raw).strip() else []
        completed_statuses = {step.get("Status", "") for step in history}
    except:
        completed_statuses = set()

    # FIXED SEQUENTIAL ORDER
    status_steps = [
        {"id": 1, "label": "Review Drawing",       "icon": "📋", "detail": "Drawing reviewed"},
        {"id": 2, "label": "3D drawing processing","icon": "📐", "detail": "Design processed"},
        {"id": 3, "label": "Printing Process",     "icon": "🖨️", "detail": "Printing in progress"},
        {"id": 4, "label": "Buy-off",              "icon": "✅", "detail": "Quality check"},
        {"id": 5, "label": "Completed",            "icon": "🏆", "detail": "Fulfilled"}]

    st.markdown("""
        <style>
        .progress-container {
            display: flex !important;
            justify-content: space-between;
            align-items: flex-start;
            padding: 25px 15px;
            background-color: white;
            border-radius: 12px;
            border: 1px solid #e0e0e0;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            margin: 15px 0 25px 0;
            width: 100%;
        }
        .prog-step {
            text-align: center;
            flex: 1;
            position: relative;
            padding: 0 8px;
        }
        .prog-icon {
            font-size: 34px;
            margin-bottom: 6px;
            display: block;
        }
        .prog-number {
            background-color: #007d69;
            color: white;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 18px;
            margin: 0 auto 8px auto;
        }
        .prog-label {
            font-weight: 700;
            font-size: 14.5px;
            color: #007d69;
            margin-bottom: 4px;
        }
        .prog-detail {
            font-size: 12.5px;
            color: #444;
            line-height: 1.3;
            min-height: 36px;
        }
        .prog-date {
            font-size: 11px;
            color: #666;
            margin-top: 4px;
        }
        /* Garis penghubung */
        .prog-step:not(:last-child):after {
            content: "···";
            position: absolute;
            top: 48px;
            right: -48%;
            font-size: 24px;
            color: #007d69;
            z-index: 0;
        }
        /* Highlight */
        .completed .prog-number { background-color: #10b981 !important; }
        .current .prog-number { 
            background-color: #3b82f6 !important; 
            animation: pulse 2s infinite;
        }
        .future .prog-number { 
            background-color: #d1d5db !important; 
            color: #6b7280 !important;
        }
        .future .prog-icon, .future .prog-label, .future .prog-detail {
            opacity: 0.4;
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.12); }
        }
        </style>
    """, unsafe_allow_html=True)

    # Bangun HTML
    html_parts = ['<div class="progress-container">']
    
    for step in status_steps:
        status = step["label"]
        step_status = step["label"]
        
        is_completed = step_status in completed_statuses
        is_current = (step_status == current_status)
        is_future = not is_completed and not is_current
        
        if is_completed:
            css_class = "completed"
            icon = step["icon"]
            # Latest date for this status
            date_str = ""
            for h in reversed(history):
                if h.get("Status") == step_status and h.get("Date"):
                    date_str = f'<div class="prog-date">{h["Date"]}</div>'
                    break
        elif is_current:
            css_class = "current"
            icon = step["icon"]
            date_str = ""
        else:  # Future - greyed out
            css_class = "future"
            icon = "⭕"
            date_str = '<div class="prog-date">Pending</div>'
        
        html_parts.append(f"""
            <div class="prog-step {css_class}">
                <div class="prog-icon">{icon}</div>
                <div class="prog-number">{step["id"]}</div>
                <div class="prog-label">{step_status}</div>
                <div class="prog-detail">{step["detail"]}</div>
                {date_str}
            </div>
        """)
    
    html_parts.append('</div>')
    full_html = "".join(html_parts)
    st.html(full_html)


# ========================= MAIN APP =========================
# REMOVED - Duplicate st.set_page_config conflict

# ====================== IDENTIFIKASI USER & ROLE ======================
Username = getpass.getuser().lower()
st.session_state.Username = Username
current_email = st.session_state.get('current_email', 'sitihanafinilam.sari@infineon.com')
st.session_state.current_email = current_email
st.session_state.user_df = load_user_data()

user_info = st.session_state.user_df[
    st.session_state.user_df['Requestor_email'].str.lower() == current_email.lower()
]

if not user_info.empty:
    st.session_state.current_role = user_info['Role'].iloc[0].lower()
    st.session_state.current_requestor_name = user_info['Username'].iloc[0]
else:
    # Default jika email belum terdaftar di user_data.xlsx
    st.session_state.current_role = "user"
    st.session_state.current_requestor_name = current_email.split('@')[0].replace('.', ' ').title()


# ====================== SIDEBAR ======================
with st.sidebar:
    st.image(image='static/logo.png')
    if st.button("🏠 Home", width='stretch'):
        st.session_state.page = "Home"
        st.rerun()
    if st.button("📝 New Request", width='stretch'):
        st.session_state.page = "Request Form"
        st.rerun()
    if st.button("📋 My Requests", width='stretch'):
        st.session_state.page = "My Requests"
        st.rerun()
    
    st.markdown("---")
    st.markdown("### ⚙️ Admin")
    if st.button("🛠️ Admin Panel", width='stretch'):
        st.session_state.page = "Admin Panel"
        st.rerun()
    if st.button("👥 User Management", width='stretch'):
        st.session_state.page = "User Management"
        st.rerun()
    if st.button("📊 Activity Log", width='stretch'):
        st.session_state.page = "Activity Log"
        st.rerun()
if 'page' not in st.session_state:
    st.session_state.page = "Home"   

    # -------DAILY QUOTES BANNER --------
    def get_daily_quote():
        hour_of_day = datetime.now().hour
        return DEV_QUOTES[hour_of_day % len(DEV_QUOTES)]

    daily_quote = get_daily_quote()
    st.markdown(f"""
    <div class="daily-quote-banner">
        <h2>"{daily_quote}"</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <style>
        .daily-quote-banner {
            background: linear-gradient(135deg, #667eea 10%, #764ba2 100%);
            border-radius: 20px;
            padding: 16px 20px;
            text-align: center;
            margin-bottom: 10px;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.35);
        }
        .daily-quote-banner h2 {
            Color: white;
            font-size: 1.5rem;
            font-weight: 700;
            margin: 0;
            font-style: italic;
            text-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
    </style>
    """, unsafe_allow_html=True)


# ===== 3D PRINTING PAGES =====
if st.session_state.page == "Home":
    st.markdown("---")
    st.markdown("""
    <style>
        [data-testid="stTab"] {
            flex: 1 1 25% !important;
            max-width: 20% !important;
            min-width: 23.2% !important;
            text-align: center !important;
            background-color: #f0f0f0 !important; /* Warna latar belakang tab */
            color: #333 !important; /* Warna teks tab */
            font-size: 25px !important; /* Ukuran font tab */
            font-weight: bold !important; /* Berat font tab */
            border: 0.7px solid #ddd !important; /* Garis batas tab */
            border-radius: 60px !important; /* Radius garis batas tab */
            height: 40px !important; /* Mengatur tinggi tab */
            line-height: 50px !important; /* Mengatur tinggi garis teks */
        }
        [data-testid="stTab"]:hover {
            background-color: #e0e0e0 !important; /* Warna latar belakang tab saat dihover */
            color: #666 !important; /* Warna teks tab saat dihover */
        }
        [data-testid="stTab"]:active {
            background-color: #ccc !important; /* Warna latar belakang tab saat aktif */
            color: #444 !important; /* Warna teks tab saat aktif */
        }
    </style>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["🖨️ Machine Specs", "📊 Workflow", "🧵 Materials", "📈 Statistics"])

    with tab1:
        st.markdown("---")
        st.markdown("#### ⚡ Quick Reference - 3D Printer Capabilities")
        spec_cols = st.columns(4, gap="small")
    
        ref_data = [
            ("Max Size", "300 × 300 × 300 mm"), 
            ("Accuracy", "Up to 0.1 mm"), 
            ("Strength", "Standard to Industrial"), 
            ("Materials", "PLA, PETG, ABS, TPU, PAHT-CF, PP, PC")
        ]

        for i, (label, value) in enumerate(ref_data):
            with spec_cols[i]:
                st.markdown(f"""
                    <div style="
                        padding: 15px 10px; 
                        text-align: center; 
                        border: 2px solid #e2e8f0; 
                        border-radius: 20px; 
                        background: white;
                        min-height: 100px; /* Kunci agar semua kotak tingginya sama */
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
                    ">
                        <p style="
                            Color: #64748b; 
                            font-size: 1.0rem; /* Sedikit dikecilkan agar aman di laptop */
                            margin: 0; 
                            text-transform: uppercase; 
                            letter-spacing: 0.5px;
                        ">{label}</p>
                        <p style="
                            Color: #1e293b; 
                            font-weight: 700; 
                            font-size: 1.0rem; /* Ukuran optimal agar teks Material tidak overflow */
                            margin: 8px 0 0;
                            line-height: 1.0;
                        ">{value}</p>
                    </div>
                """, unsafe_allow_html=True)
                
        # Machine & Spec Visuals
        st.markdown("---")
        col_left, col_right = st.columns(2, border=True, gap="medium")

        with col_left:
            st.markdown("#### 🖨️ Machine Appearance")
            st.image("static/machine.PNG", caption="3D Printer Machine", width='stretch')  
            
        with col_right:
            st.markdown("#### 📋 Technical Specifications")
            st.image("static/spec.PNG", caption="Machine Specifications", width='stretch')

    with tab2:
        st.markdown("---")
        st.markdown("#### 📊 Process Steps - How It Works?")
        st.markdown("Follow these simple steps to get your 3D print Request fulfilled:")

        cols = st.columns(6, gap="small")
        steps = [
            ("1️⃣", "Submit Request", "Fill out the Request"),
            ("2️⃣", "Review Drawing", "Team reviews design"),
            ("3️⃣", "3D Drawing", "Design processed"),
            ("4️⃣", "Printing", "Manufacturing"),
            ("5️⃣", "Buy-off", "Quality check"),
            ("6️⃣", "Completed", "Fulfillment")
        ]

        for i, (icon, title, desc) in enumerate(steps):
            with cols[i]:
                st.markdown(f"""
                    <div style="
                        background: white; 
                        border-radius: 10px; 
                        padding: 10px 5px; 
                        text-align: center; 
                        border: 1px solid #e2e8f0; 
                        min-height: 100px;  
                        display: flex; 
                        flex-direction: column; 
                        justify-content: flex-start;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                    ">
                        <div style="font-size: 1.7rem; margin-bottom: 5px;">{icon}</div>
                        <p style="
                            font-weight: 700; 
                            margin: 2px 0; 
                            font-size: 0.95rem; 
                            line-height: 1.2;
                            Color: #1e293b;
                        ">{title}</p>
                        <p style="
                            font-size: 0.90rem; 
                            Color: #64748b; 
                            margin: 0;
                            line-height: 1.3;
                        ">{desc}</p>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("#### 📊 Workflow Diagrams")
        col_img1, col_img2 = st.columns(2)
        with col_img1:
            with st.container(border=True):
                st.image("static/3Dflow.png", caption="Request Workflow Diagram", width='stretch')
                
        with col_img2:
            with st.container(border=True):
                st.image("static/3D_Full_Req.png", caption="Full Process Overview", width='stretch')

    with tab3:
        st.markdown("---")
        st.markdown("### Common Filament Material Comparison")
        Category = st.selectbox(
            "🔍 Select a Comparison Table to View:",[
                "Impact Resistance", 
                "Chemical Resistance", 
                "Thermal Properties", 
                "Printing Parameters", 
                "Price Comparison", 
                "General Recommendations"])

        # --- Impact Resistance ---
        if Category == "Impact Resistance":
            st.subheader("Impact Resistance Comparison")
            impact_df = pd.DataFrame({
                "Material": ["TPU", "PP", "PC", "PAHT-CF", "PETG", "ABS", "PLA"],
                "Impact Resistance": ["Excellent", "Excellent", "Very High", "High", "Moderate-High", "Moderate", "Low"],
                "Primary Characteristic": [
                    "High flexibility/shock absorption", "Tough and lightweight",
                    "High strength and heat resistance", "High-temp carbon fiber nylon",
                    "Balanced toughness and ease of use",
                    "Good toughness but prone to warping", "Rigid and very brittle"],
                "Best Use Case": [
                    "Protective cases, tires", "Hinges, chemical containers",
                    "Bulletproof glass, structural parts", "Professional/extreme environments",
                    "Functional prototypes, brackets", "Enclosures, mechanical parts",
                    "Aesthetic models, non-functional"]})
            st.dataframe(impact_df, width='stretch', hide_index=True, column_config={
            "Material": st.column_config.Column(width="small")})

        # --- Chemical Resistance ---
        elif Category == "Chemical Resistance":
            st.subheader("Chemical Resistance Comparison")
            chemical_df = pd.DataFrame({
                "Material": ["PP", "PAHT-CF", "TPU", "PETG", "PC", "ABS", "PLA"],
                "Resistance Level": ["Excellent", "Very High", "High", "Good", "Moderate", "Moderate", "Low"],
                "Notable Resistances": [
                    "Almost all chemicals (acids, bases, organic solvents).",
                    "Most oils, greases, lubricants & corrosive chemicals.",
                    "Water, salts, glycols, and fuels.",
                    "Water, alcohols, weak acids & household chemicals.",
                    "Water and alcohols.",
                    "Water, alcohols, and some dilute acids/bases.",
                    "Water (at ambient temperatures)."],
                "Notable Vulnerabilities": [
                    "Acetone, fluorinated/chlorinated chemicals.",
                    "Strong acids & bases, some organic solvents.",
                    "Strong acids and bases.",
                    "Acetone, aromatic/halogen hydrocarbons.",
                    "Strong acids/bases & many organic solvents.",
                    "Acetone (degrades very quickly).",
                    "Most organic solvents and harsh chemicals."]})
            st.dataframe(chemical_df, width='stretch', hide_index=True, column_config={
            "Material": st.column_config.Column(width="small")})

        # --- Thermal Properties ---
        elif Category == "Thermal Properties":
            st.subheader("Thermal Properties Comparison")
            thermal_df = pd.DataFrame({
                "Material": ["PAHT-CF (Polyamide High-Temperature Carbon Fiber)", "PC (Polycarbonate)", "ABS (Acrylonitrile Butadiene Styrene)", "PP (Polypropylene)", "PETG (Polyethylene Terephthalate Glycol-modified)", "TPU (Thermoplastic Polyurethane)", "PLA (Polylactide)"],
                "Glass Transition (Tg)": ["120°C", "140°C", "100°C - 105°C", "-10°C to 0°C", "80°C - 85°C", "-38°C", "55°C - 60°C"],
                "Heat Deflection (HDT)": ["150°C - 190°C*", "130°C", "90°C - 98°C", "100°C - 105°C**", "65°C - 75°C", "N/A (Flexible)", "~55°C"],
                "Max Use Temp": ["<150°C", "<130°C", "<90°C", "<100°C", "<70°C", "<60°C", "<50°C"]})
            st.dataframe(thermal_df, width='stretch', hide_index=True,column_config={
            "Material": st.column_config.Column(width="large")})
            st.caption("*PAHT-CF & **PP based on specific manufacturer technical data sheets.")

        # --- Printing Parameters ---
        elif Category == "Printing Parameters":
            st.subheader("Printing Parameter Comparison")
            param_df = pd.DataFrame({
                "Material": ["PLA", "PETG", "PP", "ABS", "TPU", "PC", "PAHT-CF"],
                "Nozzle Temp (°C)": ["180–220", "220–250", "220–250", "230–250", "210–250", "260–310", "260–300"],
                "Bed Temp (°C)": ["20–60", "70–90", "85–100", "90–110", "30–60", "80–120", "80–110"],
                "Cooling Fan": ["100%", "30–50%", "Low/Off", "Off", "50–100%", "Off", "Low/Off"],
                "Enclosure Required?": ["No", "No", "Recommended", "Yes", "No", "Yes", "Yes"]})
            st.dataframe(param_df, width='stretch', hide_index=True, column_config={
            "Material": st.column_config.Column(width="small")})


        # --- Price Comparison ---
        elif Category == "Price Comparison":
            st.subheader("Filament Price Comparison (IDR per 1kg)")
            price_df = pd.DataFrame({
                "Material": ["PLA", "ABS", "PETG", "PP", "TPU", "PC", "PAHT-CF"],
                "Price Range (IDR per 1kg)": ["125,000 – 385,000", "121,000 – 400,000", "132,000 – 245,000", "132,000 – 140,000", "216,000 – 630,000", "258,000 – 1,000,000", "1,086,000+"],
                "Market Average": ["IDR181,000", "IDR266,000", "IDR209,000", "IDR135,000", "IDR348,000", "IDR863,000", "IDR1,086,000"],
                "Notes": [
                    "Most accessible and widely used.",
                    "Cost-effective for durable, heat-resistant parts.",
                    "Balanced price-to-performance ratio.",
                    "Competitive pricing for 0.8kg–1kg rolls.",
                    "Higher cost due to flexible Material properties.",
                    "Premium engineering plastic for high-strength use.",
                    "High-performance Carbon Fiber Nylon (typically 0.75kg-1kg)."]})
            st.dataframe(price_df, width='stretch', hide_index=True, column_config={
            "Notes": st.column_config.Column(width="large")})

        # --- General Recommendations ---
        elif Category == "General Recommendations":
            st.subheader("Filament Comparison & Recommendations")
            rec_df = pd.DataFrame({
                "Material": ["PLA", "PETG", "ABS", "TPU", "PP", "PC", "PAHT-CF"],
                "Key Properties": [
                    "Rigid, easy to print, biodegradable",
                    "Durable, water/chemical resistant",
                    "High impact/heat resistance",
                    "Flexible, high impact absorption",
                    "Chemical resistant, lightweight, tough",
                    "Extremely strong, very high heat resistance",
                    "Ultra-stiff, heat stable, high strength"],
                "Recommended Use Case": [
                    "Visual models, prototypes",
                    "Mechanical parts, containers",
                    "Functional parts, enclosures",
                    "Gaskets, wearables, phone cases",
                    "Living hinges, liquid containers",
                    "Engineering/Aerospace parts",
                    "High-load brackets, racing parts"],
                "Difficulty": ["Very Easy", "Easy", "Moderate", "Difficult", "Difficult", "Difficult", "Hard"]})
            st.dataframe(rec_df, width='stretch', hide_index=True, column_config={
            "Key Properties": st.column_config.Column(),
            "Recommended Use Case": st.column_config.Column()})

    with tab4:
        st.markdown("---")
        st.markdown("### 📈 Statistics Dashboard")

        df = load_Requests()

        if df.empty:
            st.info("No requests data available yet.")
            stats = {
                'total': 0,
                'completed': 0,
                'pending': 0,
                'buyoff': 0,
                'status_dist': {},
                'avg_lead_time': "0 Days"}
        else:   
            total = len(df)
            completed = len(df[df['Status'] == 'Completed'])
            buyoff = len(df[df['Status'] == 'Buy-off'])
            pending = len(df[~df['Status'].isin(['Completed', 'Rejected'])])
            status_dist = df['Status'].value_counts().to_dict()
            avg_lead_time = "N/A"

            if 'Request Date' in df.columns and 'Completed Date' in df.columns:
                try:
                    df['req_date'] = pd.to_datetime(df['Request Date'], format='%d/%m/%Y', errors='coerce')
                    df['comp_date'] = pd.to_datetime(df['Completed Date'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
                    
                    completed_df = df[(df['Status'] == 'Completed') & df['comp_date'].notna()].copy()
                    
                    if not completed_df.empty:
                        durations = (completed_df['comp_date'] - completed_df['req_date']).dt.days
                        avg_days = durations.mean()
                        avg_lead_time = f"{avg_days:.1f} Days" if not pd.isna(avg_days) else "N/A"
                except:
                    avg_lead_time = "N/A"

            stats = {
                'total': total,
                'completed': completed,
                'pending': pending,
                'buyoff': buyoff,
                'status_dist': status_dist,
                'avg_lead_time': avg_lead_time }

        # Metric Cards
        cols = st.columns(5, gap="small")
        metrics = [
            ("Buy-off", stats['buyoff']),
            ("In Progress", stats['pending']),
            ("Completed", stats['completed']),
            ("Total Requests", stats['total']),
            ("Avg. Process Time", stats['avg_lead_time'])
        ]

        for i, (label, value) in enumerate(metrics):
            with cols[i]:
                st.markdown(f"""
                    <div style="background: white; padding: 15px 10px; border-radius: 15px; 
                    border: 1px solid #e2e8f0; text-align: center; min-height: 110px; 
                    display: flex; flex-direction: column; justify-content: center;">
                        <p style="margin:0; color:#64748b; font-size: 1.0rem;">{label}</p>
                        <h3 style="margin:8px 0 0; color:#1e293b; font-size:1.4rem;">{value}</h3>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        
        # Status Distribution Chart
        st.markdown("#### 📊 Status Distribution")
        if stats['status_dist']:
            status_df = pd.DataFrame(list(stats['status_dist'].items()), columns=['Status', 'Count'])
            st.bar_chart(status_df.set_index('Status'), height=400)
        else:
            st.info("No status data available for chart.")


# ======================== REQUEST FORM ===========================
elif st.session_state.page == "Request Form":
    st.markdown("<h1>📝 New Request</h1>", unsafe_allow_html=True)
    st.markdown("---")
    with st.form("request_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            requestor = st.text_input("Requestor Name", value=Username.title(), disabled=True)
        with col2:
            email = "sitihanafinilam.sari@infineon.com"
            requestor_email = st.text_input("Requestor Email", value=email, disabled=True)

        col3, col4 = st.columns(2)
        with col3: category = st.selectbox("Category *", Category_OPTIONS)
        with col4: target_date = st.date_input("Target Date *", value=datetime.now() + timedelta(days=7))

        col5, col6 = st.columns(2)
        with col5: quantity = st.number_input("Quantity *", min_value=1, value=1)
        with col6: material = st.selectbox("Material *", Material_OPTIONS)

        col7, col8 = st.columns(2)
        with col7: color = st.selectbox("Color *", Color_OPTIONS)
        with col8: has_drawing = st.selectbox("3D Drawing Available?*", [" ", "YES", "NO"])

        details = st.text_area("Project Details *", height=180)

        uploaded_file = st.file_uploader(
                    "📎 Upload 3D File Attachment (PNG/JPG only)", 
                    type=['png', 'jpg', 'jpeg'],
                    key="attachment_upload")
        
        agree = st.checkbox("✅ I confirm that the information provided is correct.")

        # ==================== SUBMIT BUTTON ====================
        # Submit button - enabled when required fields filled
        if st.form_submit_button("🚀 Submit Request", type="primary"):
            # Validation
            if has_drawing == "YES" and not uploaded_file:
                st.error("❌ Upload required when 3D Drawing = YES!")
                st.stop()
            if not details or not agree:
                st.error("❌ Complete all required fields!")
                st.stop()

            # Create request
            result, message = add_or_update_Request(
                Requestor=requestor,
                Requestor_email=requestor_email,
                Category=category,
                Details=details,
                Target_Date=target_date.strftime("%d/%m/%Y"),
                Quantity=quantity,
                Material=material,
                Color=color
            )

            if isinstance(result, int):
                # Safe attachment save
                attachment_path = None
                if uploaded_file:
                    attachment_path = f"static/request_{result}_{uploaded_file.name}"
                    try:
                        with open(attachment_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.success(f"📎 Attachment saved: {os.path.basename(attachment_path)}")
                    except Exception as e:
                        st.error(f"Attachment save failed: {e}")

                # Send admin notification
                send_new_request_notification_to_admin(
                    record_id=result,
                    requestor=requestor,
                    requestor_email=requestor_email,
                    category=category,
                    details=details,
                    quantity=quantity,
                    material=material,
                    color=color,
                    target_date=target_date,
                    attachment_path=attachment_path
                )
                
                st.success(f"✅ Request #{result} created successfully!")
                st.session_state.page = "My Requests"
                st.rerun()
            else:
                st.error(f"Request failed: {message}")


# ======================== MY REQUESTS ===========================
elif st.session_state.page == "My Requests":
    st.markdown("<h1>📝 My Requests</h1>", unsafe_allow_html=True)
    st.markdown("---")

    df = load_Requests()
    
    if df.empty:
        st.info("No requests found.")
    else:
        my_requests = df[df['Requestor_email'].str.lower() == st.session_state.current_email.lower()]
        for _, row in my_requests.iterrows():
                with st.expander(f"#{row['No']} | {row['Status']}", expanded=False):
                    dynamic_progress_tracker(row)  
                    st.write(f"**Category:** {row.get('Category', '')}")
                    st.write(f"**Material:** {row.get('Material', '')} | **Color:** {row.get('Color', '')}")
                    st.write(f"**Details:** {row.get('Details', '')}")
                    
                    if st.session_state.current_role == "admin":           
                        new_status = st.selectbox("Update Status", STATUS_OPTIONS, 
                                                  index=STATUS_OPTIONS.index(row['Status']) if row['Status'] in STATUS_OPTIONS else 0,
                                                  key=f"status_{row['No']}")
                        admin_comment = st.text_area("Admin Comments", key=f"comment_{row['No']}")
                        if st.button("Update Status", key=f"upd_{row['No']}"):
                            success, msg = add_or_update_Request(
                                record_id=row['No'],
                                Status=new_status,
                                Admin_Comments=admin_comment
                            )
                            if success:
                                st.success(msg)
                                st.rerun()


# ======================== ADMIN PANEL ===========================
elif st.session_state.page == "Admin Panel":
    st.markdown("<h1>🛠️ Admin Panel</h1>", unsafe_allow_html=True)
    st.markdown("---")
    
    df = load_Requests()
    
    # ===== FILTER SECTION =====
    st.markdown("### 📋 All Requests")
    st.markdown("---")

    # Filter by Date Range 
    col_date1, col_date2, col_f = st.columns([2, 2, 4], vertical_alignment='bottom')
    with col_date1:
        start_date = st.date_input(
            "From Date", 
            value=datetime.now() - timedelta(days=30),
            key="start_date")
    with col_date2:
        end_date = st.date_input(
            "To Date", 
            value=datetime.now(),
            key="end_date")
    with col_f:
        status_filter = st.multiselect("Filter Status", STATUS_OPTIONS)

    # Export Button
    export_name = f"All_Requests_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    df.to_excel(export_name, index=False)
    with open(export_name, "rb") as f:
        st.download_button(
            label="✅ Download Excel",
            data=f,
            file_name=export_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("---")

    # ==================== APPLY FILTERS ====================
    filtered_df = df.copy()

    # Date Range Filter
    if not filtered_df.empty:
        try:
            filtered_df['Request Date'] = pd.to_datetime(
                filtered_df['Request Date'], 
                format='%d/%m/%Y', 
                errors='coerce'
            )
            filtered_df = filtered_df[
                (filtered_df['Request Date'] >= pd.to_datetime(start_date)) &
                (filtered_df['Request Date'] <= pd.to_datetime(end_date))
            ]
        except:
            pass

    # Status Filter
    if status_filter:
        filtered_df = filtered_df[filtered_df['Status'].isin(status_filter)]

    if filtered_df.empty:
        st.info("No requests found.")
    else:
        for _, row in filtered_df.iterrows():
            with st.expander(f"#{row['No']} | {row['Requestor']} | {row['Status']}", expanded=False):
                dynamic_progress_tracker(row)
                st.write(f"**Category:** {row.get('Category', '')}")
                st.write(f"**Material:** {row.get('Material', '')} | **Color:** {row.get('Color', '')}")
                st.write(f"**Details:** {row.get('Details', '')}")

                with st.container(border=True):
                    st.markdown("### 🔄 Perbarui Status")
                    new_status = st.selectbox(
                        "New Status", 
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(row['Status']) if row['Status'] in STATUS_OPTIONS else 0,
                        key=f"status_{row['No']}"
                    )
                    
                    admin_comment = st.text_area(
                        "Admin Comments", 
                        value=row.get('Admin Comments', ''), 
                        key=f"comment_{row['No']}"
                    )
                    
                    if st.button("✅ Update & Notify User", 
                                key=f"upd_{row['No']}", 
                                type="primary"):
                        with st.spinner("Update and send notifications..."):
                            success, msg = add_or_update_Request(
                                record_id=row['No'],
                                Status=new_status,
                                Admin_Comments=admin_comment
                            )
                            if success:
                                st.success(msg)
                                st.rerun()
                            else:
                                st.error(msg)


# ======================== USER MANAGEMENT ===========================
elif st.session_state.page == "User Management":
    if Username != "sarsitihanaf": 
        st.error("You do not have access to this page.")
        st.stop()

    st.markdown("<h1>👥 User Management</h1>", unsafe_allow_html=True)
    st.markdown("---")

    if 'user_df' not in st.session_state:
        st.session_state.user_df = load_user_data()

    # Header + Search + Add Button
    col1, col2 = st.columns([4, 0.5], vertical_alignment='bottom')
    with col1:
        search_term = st.text_input("🔍 Search User", placeholder="Username atau Email...")
    with col2:
        if st.button("➕ Add New User", type="secondary", use_container_width=True):
            st.session_state.show_add_user = True
            st.rerun()   

    # Filter data
    user_df = st.session_state.user_df.copy()
    if search_term:
        mask = (
            user_df['Username'].astype(str).str.contains(search_term, case=False, na=False) |
            user_df['Requestor_email'].astype(str).str.contains(search_term, case=False, na=False)
        )
        user_df = user_df[mask].reset_index(drop=True)

    # Header Tabel
    st.markdown("---")
    h = st.columns([0.8, 2.5, 3.5, 2, 2])
    with h[0]: st.markdown("**ID**")
    with h[1]: st.markdown("**Username**")
    with h[2]: st.markdown("**Email**")
    with h[3]: st.markdown("**Role**")
    with h[4]: st.markdown("**Actions**")
    st.markdown("---")

    # Tampilkan daftar user
    for i, row in user_df.iterrows():
        orig_idx = st.session_state.user_df[st.session_state.user_df['User_ID'] == row['User_ID']].index[0]

        c = st.columns([0.8, 2.5, 3.5, 2, 2])
        with c[0]: st.write(f"**#{int(row['User_ID'])}**")
        with c[1]: st.write(row['Username'])
        with c[2]: st.write(row['Requestor_email'])
        with c[3]: st.write(row['Role'])
        
        with c[4]:
            col_e, col_d = st.columns(2)
            with col_e:
                if st.button("✏️ Edit", key=f"edit_{orig_idx}", use_container_width=True):
                    st.session_state.edit_index = orig_idx
                    st.session_state.show_edit_dialog = True
                    st.rerun()                    
            with col_d:
                if st.button("🗑️ Delete", key=f"del_{orig_idx}", use_container_width=True):
                    st.session_state.delete_index = orig_idx
                    st.session_state.delete_username = row['Username']
                    st.session_state.show_delete_dialog = True
                    st.rerun()                    

    # ==================== DIALOG FUNCTIONS ====================
    @st.dialog("➕ Add New User")
    def add_user_dialog():
        with st.form("add_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Username *")
                new_email = st.text_input("Email *")
            with col2:
                new_role = st.selectbox("Role", ["User", "Admin"])

            if st.form_submit_button("💾 Save User", type="primary"):
                if not new_username or not new_email:
                    st.error("Username and email address are required!")
                elif (not st.session_state.user_df.empty and 
                      new_username.lower() in st.session_state.user_df['Username'].str.lower().values):
                    st.error(f"Username '{new_username}' already exists!")
                else:
                    new_id = int(st.session_state.user_df['User_ID'].max()) + 1 if not st.session_state.user_df.empty else 1
                    
                    new_row = pd.DataFrame([{
                        'User_ID': new_id,
                        'Username': new_username.strip(),
                        'Requestor_email': new_email.strip(),
                        'Role': new_role,
                        'Domain': 'infineon.com'
                    }])
                    
                    updated = pd.concat([st.session_state.user_df, new_row], ignore_index=True)
                    if save_user_data(updated):
                        st.session_state.user_df = updated
                        st.success(f"✅ User **{new_username}** has been successfully added!")
                        st.session_state.show_add_user = False
                        st.rerun()

    @st.dialog("✏️ Edit User")
    def edit_user_dialog():
        idx = st.session_state.get('edit_index')
        if idx is None or idx >= len(st.session_state.user_df):
            st.error("No data found")
            st.stop()

        row = st.session_state.user_df.loc[idx]

        with st.form("edit_form"):
            col1, col2 = st.columns(2)
            with col1:
                edit_name = st.text_input("Username", value=row['Username'])
                edit_email = st.text_input("Email", value=row['Requestor_email'])
            with col2:
                edit_role = st.selectbox("Role", ["User", "Admin"], 
                                       index=0 if row['Role'] == "User" else 1)

            if st.form_submit_button("💾 Save Changes", type="primary"):
                st.session_state.user_df.at[idx, 'Username'] = edit_name.strip()
                st.session_state.user_df.at[idx, 'Requestor_email'] = edit_email.strip()
                st.session_state.user_df.at[idx, 'Role'] = edit_role
                
                if save_user_data(st.session_state.user_df):
                    st.success(f"✅ Changes to **{edit_name}** saved successfully!")
                    st.session_state.show_edit_dialog = False
                    st.rerun()

    @st.dialog("🗑️ Confirm Delete")
    def delete_dialog():
        username = st.session_state.get('delete_username', '')
        idx = st.session_state.get('delete_index')

        st.warning(f"Are you sure you want to delete the user? **{username}**?")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("🗑️ Yes, Delete", type="primary"):
                if idx is not None:
                    updated = st.session_state.user_df.drop(idx).reset_index(drop=True)
                    if save_user_data(updated):
                        st.session_state.user_df = updated
                        st.success(f"✅ User **{username}** has been deleted.")
                        st.session_state.show_delete_dialog = False
                        st.rerun()
        with c2:
            if st.button("Cancel", type="secondary"):
                st.session_state.show_delete_dialog = False
                st.rerun()

    # ==================== SHOW DIALOG ====================
    if st.session_state.get('show_add_user', False):
        add_user_dialog()

    elif st.session_state.get('show_edit_dialog', False):     
        edit_user_dialog()

    elif st.session_state.get('show_delete_dialog', False):   
        delete_dialog()


# ===================== ACTIVITY LOG =====================
elif st.session_state.page == "Activity Log":
    if Username != "sarsitihanaf":
        st.error("You do not have access to this page.")
        st.stop()

    st.markdown("""
    <h1 style="text-align:left;">📊 Activity Log</h1>
    """, unsafe_allow_html=True)
    st.markdown("---")
    
    @st.cache_data(ttl=60)
    def parse_activity_log(requests_df):
        def extract_events(row):
            history_raw = row.get('Status History', '')
            try:
                history = json.loads(history_raw) if history_raw.strip() else []
                requestor = row.get('Requestor', 'Unknown')
                req_id = row.get('No', 'Unknown')
                
                events = []
                for i, event in enumerate(history):
                    time_str = event.get('Date', '')
                    try:
                        event_time = datetime.strptime(time_str, '%d/%m/%y %H:%M')
                    except:
                        event_time = datetime.now()
                    
                    events.append({
                        'Time': event_time,
                        'Username': requestor if i == 0 else f"{getpass.getuser().title()} (Admin)",
                        'Action': 'REQUEST CREATED' if i == 0 else 'STATUS UPDATED',
                        'Description': f"Request #{req_id}: {event.get('Status', 'Unknown')}" + 
                                    (f" | Comment: {event.get('Admin Comments', '')}" if event.get('Admin Comments') else ''),
                        'Request_ID': req_id
                    })
                return events
            except:
                return []
        
        # Vectorized extraction
        all_events = []
        for _, row in requests_df.iterrows():
            all_events.extend(extract_events(row))
        
        if not all_events:
            return pd.DataFrame(columns=['Request_ID','Time', 'Username', 'Action', 'Description'])
            
        log_df = pd.DataFrame(all_events).sort_values('Time', ascending=False).reset_index(drop=True)
        return log_df.head(100)

    log_df = parse_activity_log(load_Requests())

    st.dataframe(
        log_df,
            width='stretch',
            hide_index=True,
            column_config={
                "Time": st.column_config.DatetimeColumn("🕒 Time", width="medium"),
                "Username": st.column_config.TextColumn("👤 Username", width="mediums"),
                "Action": st.column_config.TextColumn("🏷️ Action", width="medium"),
                "Description": st.column_config.TextColumn("📝 Description", width="large")})

    col1, col2 = st.columns(2)
    col1.button("🔄 Refresh", on_click=lambda: st.cache_data.clear() or st.rerun())
    col2.metric("Total Events", len(log_df))

    st.caption("💡 Real activity from Status History")