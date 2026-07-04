import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime
from streamlit_extras.add_vertical_space import add_vertical_space
import os
import mimetypes
from decouple import Config, RepositoryEnv
from smb.SMBConnection import SMBConnection
import socket
import io
import pandas as pd
from datetime import datetime, timedelta
import win32com.client
import pythoncom
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import ssl
from typing import Optional
import sys
from email.mime.base import MIMEBase
from email import encoders
import html
import sys
from smb.SMBConnection import SMBConnection


# =============== CONFIGURATION ===========================
COLUMNS = ["No", "Parent_No", "Request Date", "Target Date", "Requestor", "Requestor_email", "Category", "Details", "Status",
"Status Start Time", "Quantity", "Material", "Color", "Completed Date", "Status History", "Admin Comments"]

USER_COLUMNS = ["User_ID", "Username", "Requestor_email", "Role", "Domain", "Active"]
Category_OPTIONS = ["Innovation", "Spare Part Replacement", "YIP/Improvement", "Others"]
STATUS_OPTIONS = ["Review Drawing", "3D drawing processing", "Printing Process", "Buy-off", "Completed", "Rejected"]
Material_OPTIONS = ["PLA", "PETG", "ABS", "TPU", "PP", "PC", "PAHT-CF", "Nylon", "Other"]
Color_OPTIONS = ["Black", "White", "Grey", "Other"]


DOTENV_FILE = '.env'
env_config = Config(RepositoryEnv(DOTENV_FILE))

# Initialize folder credentials
user = env_config.get('UN')
print(user)
serverName = env_config.get('SERVERNAME')
shareName = env_config.get('SHARENAME')
folderName = env_config.get('FOLDERNAME')
print(folderName)
sk = env_config.get('APPKEY')
password = env_config.get('PASSWORD')
sender="sinbedevdigiz@infineon.com"


FILE_PATH_request ="dashboard_db/Requests.xlsx"
USER_FILE= "static/user_data.csv"

# Setting up connection with shared drive
try:
    conn = SMBConnection(username=user, password=password, my_name="icp", remote_name=serverName, use_ntlm_v2=True)
    ip_address = socket.gethostbyname(str(serverName) if serverName else "localhost")
    print(conn.connect(ip_address, 139))
except Exception as e:
    st.error(f"Failed to connect to shared drive: {e}")
    conn = None  # Set conn to None if connection fails

@st.cache_data(ttl=2)
def load_Requests():
    #ensure_file_exists(REQUESTS_FILE)
    try:
        read_buffer = io.BytesIO()
        conn = SMBConnection(username=user, password=password, my_name="icp", remote_name=serverName, use_ntlm_v2=True)
        ip_address = socket.gethostbyname(str(serverName) if serverName else "localhost")
        print(conn.connect(ip_address, 139))

        # Retrieve file binary from file share into the buffer
        conn.retrieveFile(shareName, FILE_PATH_request, read_buffer)

        # Reset the buffer pointer to the beginning before reading
        read_buffer.seek(0)
        df = pd.read_excel(read_buffer, dtype=str, engine='openpyxl')
        df['No'] = df['No'].astype(str)
        # Drop unexpected columns like 'Username', keep only known
        df = df.reindex(columns=COLUMNS, fill_value='')
        print("loading, request", df.head(10))
        conn.close()
        return clean_dataframe(df, COLUMNS)
    except Exception as e:
        st.error(f"Error loading requests: {e}")
        return pd.DataFrame(columns=COLUMNS)

# -----------------------------MAIL SETUP----------------------------------
class SMTPTester:
    """SMTP email testing utility."""
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        sender_email: str,
        sender_password: Optional[str] = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        require_auth: bool = True
        ):
        """
        Initialize SMTP tester.
        Args:
        smtp_server: SMTP server hostname
        smtp_port: SMTP server port
        sender_email: Email address to send from
        sender_password: Password or app-specific password (optional if no
        auth)
        use_tls: Use STARTTLS (default: True)
        use_ssl: Use SSL/TLS from the start (default: False)
        require_auth: Whether authentication is required (default: True)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.require_auth = require_auth
    def send_test_email(
        self,
        recipient_email: str,
        subject: str = "SMTP Test Email",
        body: str = "This is a test email sent via SMTP.",
        uploaded_file=None
        ) -> bool:
        """
        Send a test email.
        Args:
        recipient_email: Email address to send to
        subject: Email subject line
        body: Email body content
        Returns:
        True if email sent successfully, False otherwise
        """
        try:
            message = self._create_message(recipient_email, subject, body, uploaded_file)
            self._send_message(message, recipient_email)
            print(f"✓ Email sent successfully to {recipient_email}")
            return True
        except smtplib.SMTPAuthenticationError:
            print("✗ Authentication failed. Check your email and password.")
            return False
        except smtplib.SMTPException as e:
            print(f"✗ SMTP error occurred: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False
    def _create_message(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        uploaded_file = None
        ) -> MIMEMultipart:
        """Create email message."""
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = ", ".join(recipient_email)
        message["Subject"] = subject
        message.attach(MIMEText(body, "html"))  # send as html format

        # handle attachments
        if uploaded_file:
            #with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(uploaded_file.getvalue())

            encoders.encode_base64(part)

            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{uploaded_file.name}"'
            )

            message.attach(part)
        return message

    def _send_message(self, message: MIMEMultipart, recipient_email) -> None:

        """Send email message via SMTP."""
        if self.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                    self.smtp_server,
                    self.smtp_port,
                    context=context) as server:
                if self.require_auth:
                    server.login(self.sender_email, self.sender_password) if self.sender_password else None
                server.sendmail(
                    self.sender_email,
                    recipient_email,
                    message.as_string())
        else:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                if self.require_auth:
                    server.login(self.sender_email, self.sender_password) if self.sender_password else None
                server.sendmail(
                    self.sender_email,
                    recipient_email,
                    message.as_string())

    def test_connection(self) -> bool:
        """
        Test SMTP server connection without sending email.
        Returns:
        True if connection successful, False otherwise
        """
        # Display connection details
        print(f"\nConnection Details:")
        print(f" Server: '{self.smtp_server}'")
        print(f" Port: {self.smtp_port}")
        print(f" Email: {self.sender_email}")
        print(f" TLS: {self.use_tls}")
        print(f" SSL: {self.use_ssl}")
        print(f" Authentication: {'Required' if self.require_auth else 'Not Required'}\n")
        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                        self.smtp_server,
                        self.smtp_port,
                        context=context
                ) as server:
                    if self.require_auth:
                        server.login(self.sender_email, self.sender_password) if self.sender_password else None
                    print(f"✓ Successfully connected to {self.smtp_server}: {self.smtp_port}")
                    return True
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                    if self.require_auth:
                        server.login(self.sender_email, self.sender_password) if self.sender_password else None
                    print(f"✓ Successfully connected to {self.smtp_server}: {self.smtp_port}")
                    return True
        except smtplib.SMTPAuthenticationError:
            print("✗ Authentication failed. Check your email and password.")
            return False
        except smtplib.SMTPException as e:
            print(f"✗ SMTP error occurred: {e}")
            return False
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
        
def normalize_Requestor_email(emails):
    if not emails:
        return []
    if isinstance(emails, str):
        return [e.strip() for e in emails.split(',') if e.strip()]
    if isinstance(emails, list):
        return [str(e).strip() for e in emails if str(e).strip()]
    return [str(emails).strip()]

def is_valid_Requestor_email(emails):
    email_list = normalize_Requestor_email(emails)
    for email in email_list:
        if '@' not in email or '.' not in email.split('@')[-1]:
            return False
    return True

def send_email_notification(send_to,password, email_subject, body_html, uploaded_file=None):
    """Main function to run SMTP tests."""


    print("=== SMTP Test Script ===\n")
    # Configuration - Update these values for your SMTP server
    SMTP_SERVER = "mailrelay-internal.infineon.com"  # Remove any
    SMTP_PORT = 25  # 587 for TLS, 465 for SSL, 25 for no encryption
    SENDER_EMAIL = "sinbedevdigiz@infineon.com"
    SENDER_PASSWORD = password  # Set to None for no authentication
    RECIPIENT_EMAIL = send_to
    REQUIRE_AUTH = False  # Internal mail relays typically don't require auth
    # Create SMTP tester instance
    tester = SMTPTester(
        smtp_server=SMTP_SERVER.strip(),  # Strip whitespace
        smtp_port=SMTP_PORT,
        sender_email=SENDER_EMAIL.strip(),
        sender_password=SENDER_PASSWORD,
        use_tls=False,  # Set to True if using port 587
        use_ssl=False,  # Set to True if using port 465
        require_auth=False # Set to False for internal relays
    )
    # Test connection
    print("Testing SMTP connection...")
    if not tester.test_connection():
        print("\nConnection test failed. Please check your settings.")
        sys.exit(1)
    else:
        print("connection smtp passed")

    # Send test email
    print("\nSending test email...")
    success = tester.send_test_email(
    recipient_email=RECIPIENT_EMAIL,
    subject=email_subject,
    body=body_html,
    uploaded_file=uploaded_file)
    if success:
        print("\n✓ All tests passed successfully!")

    else:
        print("\n✗ Email sending failed.")

def ensure_file_exists(file_path):
    if not os.path.exists(file_path):
        os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
        cols = COLUMNS if "Requests" in file_path else USER_COLUMNS
        pd.DataFrame(columns=cols).to_excel(file_path, index=False)

def clean_dataframe(df, columns):
    """Unified data cleaning pipeline"""
    if df.empty:
        return df

    df = df.fillna('')

    # Column-specific processing
    if 'Quantity' in df.columns:
        df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(1).astype(int)

    # Ensure required columns exist
    for col in columns:
        if col not in df.columns:
            if col == "Quantity":
                df[col] = 1
            else:
                df[col] = ''

    return df

def get_logged_in_user():
    headers = st.context.headers
    email_get=headers.get("X-Forwarded-Email")
    email_get= email_get.strip().lower() if email_get else None
    return email_get

def load_user_data(csv_path=USER_FILE):
    full_path = os.path.abspath(csv_path)
    df = pd.read_csv(full_path, encoding='utf-8')
    print("Original columns:", df.columns.tolist())
    # Normalize (this avoids 90% of bugs)
    df["Username"] = df["Username"].astype(str).str.strip().str.lower()
    df["Requestor_email"] = df["Requestor_email"].astype(str).str.strip().str.lower()
    return df

def get_email_from_username(username, df):
    if not username:
        return None
    match = df[df["Username"] == username]
    if not match.empty:
        return match.iloc[0]["Requestor_email"]
    return None


st.set_page_config(page_title="BE DEV Dashboard", page_icon=":computer:", layout="wide")

def landing_page():
    # Hero Section
    st.markdown("""
    <div style="text-align: center; padding: 60px 20px; 
                background: linear-gradient(135deg, #0A8276 0%, #094f48 100%); 
                border-radius: 20px; color: white; margin-bottom: 50px;">
        <h1 style="font-size: 3.2rem; font-weight: 500; margin-bottom: 10px;">
            <strong>Welcome to BE DEV Dashboard</strong>
        </h1>
        <p style="font-size: 1.45rem; opacity: 0.92; max-width: 800px; margin: 0 auto;">
            Your Central Hub for Development Resources
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Description Section 
    st.markdown("""
    <div style="max-width: 1000px; margin: 0 auto; padding: 0 20px;">
        <p style="font-size: 1.15rem; line-height: 1.8; color: #333; text-align: justify;">
            BE DEV Dashboard is a comprehensive and intuitive platform designed to centralize all vital 
            resources for the Development team. In today's fast-paced environment, having immediate access to 
            critical links, comprehensive documentation, and essential tools is paramount. 
            <strong>Our mission is to eliminate the time wasted searching for dispersed information</strong>, 
            allowing you to focus on innovation and productivity.
        </p>

    </div>
    """, unsafe_allow_html=True)

    # Key Features Section
    st.markdown("---")
    st.markdown('<h2 class="key-features-header">Key Features</h2>', unsafe_allow_html=True)

    carousel_html = """
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.css" />
    <style>
        .swiper {
            padding: 100px 0;
        }
        .feature-slide {
            text-align: center;
            padding: 5px;
        }
        .feature-card {
            background: white;
            border-radius: 20px;
            padding: 40px 30px;
            box-shadow: 0 15px 40px rgba(0,0,0,0.1);
            height: 100%;
            transition: all 0.4s ease;
        }
        .feature-card:hover {
            transform: translateY(-12px);
            box-shadow: 0 25px 55px rgba(10,130,118,0.2);
        }
        .feature-icon {
            font-size: 5.5rem;
            margin-bottom: 25px;
            color: #0A8276;
        }
        .feature-title {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1e2937;
            margin-bottom: 15px;
        }
        .swiper-button-next, .swiper-button-prev {
            color: #0A8276;
        }
        .swiper-pagination-bullet-active {
            background: #0A8276;
        }
    </style>

    <div class="swiper mySwiper">
        <div class="swiper-wrapper">
            <div class="swiper-slide feature-slide">
                <div class="feature-card">
                    <div class="feature-icon">📊</div>
                    <h3 class="feature-title">Data System Monitoring</h3>
                    <p>Monthly monitoring reports (DEVSPACE, PV, NICA) with detailed analytics.</p>
                </div>
            </div>

            <div class="swiper-slide feature-slide">
                <div class="feature-card">
                    <div class="feature-icon">📚</div>
                    <h3 class="feature-title">Training & Knowledge</h3>
                    <p>Comprehensive library of training materials and process knowledge.</p>
                </div>
            </div>

            <div class="swiper-slide feature-slide">
                <div class="feature-card">
                    <div class="feature-icon">🛠️</div>
                    <h3 class="feature-title">Development Tools</h3>
                    <p>Centralized access to all essential development tools and applications.</p>
                </div>
            </div>
        </div>
        
        <!-- Navigation Buttons -->
        <div class="swiper-button-next"></div>
        <div class="swiper-button-prev"></div>
        <div class="swiper-pagination"></div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/swiper@11/swiper-bundle.min.js"></script>
    <script>
        var swiper = new Swiper(".mySwiper", {
            slidesPerView: 1,
            spaceBetween: 10,
            loop: true,
            autoplay: {
                delay: 5000,
                disableOnInteraction: false,
            },
            navigation: {
                nextEl: ".swiper-button-next",
                prevEl: ".swiper-button-prev",
            },
            pagination: {
                el: ".swiper-pagination",
                clickable: true,
            },
            breakpoints: {
                640: { slidesPerView: 2 },
                1024: { slidesPerView: 3 }
            }
        });
    </script>
    """

    import streamlit.components.v1 as components
    components.html(carousel_html, height=480)  


# ------------------------Data System Monitoring----------------------------------------
month_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]

image_dict = {
    "DEVSPACE": {
        year: {
            month: f"DEVSPACE_{month_names[month - 1]}_{year}.JPG"
            for month in range(1, 13)
        }
        for year in range(2023, 2050)
    },
    "NICA": {
        year: {
            month: f"NICA_{month_names[month - 1]}_{year}.JPG"
            for month in range(1, 13)
        }
        for year in range(2023, 2050)
    },
    "PV": {
        year: {
            month: f"PV_{month_names[month - 1]}_{year}.JPG"
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

    report_year = st.selectbox("Select Year", range(this_year, this_year - 3, -1), key="box8")
    report_month_str = st.radio(
        "Select Month", month_names, index=this_month - 3, horizontal=True
    )
    print(" report_month_str", report_month_str)
    report_month = month_names.index(report_month_str) + 1  # Convert month name to month number
    return report_year, report_month_str



# ---------------------------------Data System Monitoring---------------------------------------------------
def data_system_monitoring_page():
    report_year, report_month_str = show_report_month()
    try:
      if conn is not None:
        try:
            with open('static/devsmets.JPG', "wb") as dev_im_temp:
                res1_attributes, res1size = conn.retrieveFile(shareName, os.path.join(str(folderName), f'DEVSPACE_{report_month_str}_{report_year}.JPG'), dev_im_temp) 
        except FileNotFoundError:
            st.info(f":red[Image for Data systems **'{report_month_str} {report_year}'** is not yet available.]")
            return  # Exit the function if the image is not found
        try:                                                 
            with open('static/pv.JPG', "wb") as pv_im_temp:
                res2_attributes, res2size = conn.retrieveFile(shareName, os.path.join(str(folderName),
                f'PV_{report_month_str}_{report_year}.JPG'), pv_im_temp)
        except FileNotFoundError:
            st.info(f":red[Image for Data systems **'{report_month_str} {report_year}'** is not yet available.]")
            return  # Exit the function if the image is not found

        try:
            with open('static/nica.JPG', "wb") as nica_im_temp:
                res3_attributes, res3size = conn.retrieveFile(shareName, os.path.join(str(folderName),
                f'NICA_{report_month_str}_{report_year}.JPG'), nica_im_temp)
        except FileNotFoundError:
            st.info(f":red[Image for Data systems **'{report_month_str} {report_year}'** is not yet available.]")
            return  # Exit the function if the image is not found

        st.markdown("---")
        st.subheader(f"Devspace Monthly Monitoring report for {report_month_str}")
        st.image('static/devsmets.JPG')  
        st.markdown("---")
        st.subheader(f"PV Monthly Monitoring report for {report_month_str}")
        st.image('static/pv.JPG')  
        st.markdown("---")
        st.subheader(f"NICA Monthly Monitoring report for {report_month_str}")
        st.image('static/nica.JPG') 
    except FileNotFoundError:
        st.info(f":red[Image for Data systems **'{report_month_str} {report_year}'** is not yet available.]")

    print(os.getcwd())


# ------------------------DEV Training---------------------------------------------------------
def display_resources(resources, unique_key_prefix=""):
    num_cols = 3
    resource_items = list(resources.items())
    num_rows = (len(resource_items) + num_cols - 1) // num_cols

    # Ensure Font Awesome CSS is loaded once (can also be in global scope)
    st.markdown(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">',
        unsafe_allow_html=True)

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
    st.markdown(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css">',
        unsafe_allow_html=True)

    # --- General Training Resources Section ---
    st.header("General Training Resources")
    st.write("Training documentation available on the DEV Dashboard supports team learning and skill development.")
    add_vertical_space()

    general_training_resources = {
        "Success Factor": {"link": "https://infineon.plateau.com/learning", "icon": "fa fa-graduation-cap",
                           "type": "url"},
        "Linkedin Learning": {"link": "https://www.linkedin.com/learning/", "icon": "fa fa-linkedin", "type": "url"},
        "MyHR Training": {
            "link": "https://infineon.service-now.com/esc?id=emp_taxonomy_topic&topic_id=20f401211bec95100b9a11739b4bcbc9",
            "icon": "fa fa-user", "type": "url"},
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
            "Process Training": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Pre_Assy/Process/PA%20Handbook_20240808.pdf",
                "display_name": "Process"}
        },

        "DMC": {
            "Machine Manual": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDMC%2FEquipment",
                "display_name": "Equipment"},
            "Process": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDMC%2FProcess",
                "display_name": "Process"}
        },

        "Die Attach": {
            "Equipment Training": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDie%20Attach%2FEquipment%5FTraining",
                "display_name": "Equipment Training"},
            "Process Training": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDie%20Attach%2FProcess%5FTraining",
                "display_name": "Process Training"},
            "DA Material": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FDie%20Attach%2FDA%5FMaterials",
                "display_name": "DA Material"}
        },

        "Wire Bond": {
            "Machine Manual": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FWire%20Bond%2FMachine%5FManuals",
                "display_name": "Operation Manual"},
            "Process Training": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FWire%20Bond%2FProcess%5FKnowledge",
                "display_name": "Process"}
        },

        "A2 Plating": {
            "PBHB": {"link": "", "display_name": "PBHB"},
            "Process": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FA2%20Plating%2FProcess",
                "display_name": "Process"},
            "Equipment Process Specification": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FA2%20Plating%2FEquipment%20Process%20Sepcification",
                "display_name": "Equipment Process Specification"}
        },

        "Front of Line Autovision": {
            "Process": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/FAV/AutovisionHandout.pdf",
                "display_name": "Process"},
        },

        "Molding": {
            "Process": {
                "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Mold/Process/Introduction%20to%20Epoxy%20Mold%20Compound%20and%20Transfer%20Mold%20Process%20Application_R4.pdf",
                "display_name": "Process & Material"},
        },

        "CD-Plating": {
            "PBHB": {"link": "", "display_name": "PBHB"},
            "Process":
                {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/CD-PL/Process",
                 "display_name": "Process"},
            "Equipment Process Specification":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FCD%2DPL%2FEquipment%20Process%20Specification",
                    "display_name": "Equipment Process Specification"},
            "Operation Manual":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FCD%2DPL%2FOperation%20Manual ",
                    "display_name": "Operation Manual"},
            "Defect Criteria":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FCD%2DPL%2FDefect%20Criteria",
                    "display_name": "Defect Criteria"}
        },

        "Trim Form Singulation": {
            "Training Trim & Form":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FTrim%26Form%20Training",
                    "display_name": "Trim & Form Training"},
            "Process":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FProcess",
                    "display_name": "Process"},
            "Operation Manual":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FOperation%20Manual",
                    "display_name": "Operation Manual"},
            "Defect Criteria":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FTrim%20%26%20Form%2FDefect%20Criteria",
                    "display_name": "Defect Criteria"}
        },

        "Others": {
            "BE Digitalization":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FOthers%2FBE%20Digitalization",
                    "display_name": "BE Digitalization"},
            "Others Training":
                {
                    "link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2Fdev%2Ddashboard%2FShared%20Documents%2FOthers%2FOthers%20Training",
                    "display_name": "Others Training"}
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
                display_resources({list(materials_dict.keys())[0]: single_material_data},
                                  process_name.replace(" ", "_"))
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


# ---------------------------------Dev Tools---------------------------------------------------------------------------
links = {
    "IFX INTRANET": {"link": "https://intranet.infineon.com/", "icon": "home"},
    "MY LEAVE": {"link": "https://sappeslb.sap.infineon.com/sap/bc/ui5_ui5/sap/z_leaverequest/index.html", "icon": "paper-plane"},
    "MY IT": {"link": "https://webnetprod.muc.infineon.com/MyIT/", "icon": "windows"},
    "PICTURE VIEWER": {"link": "https://pictureviewer-bedev.infineon.com:8080/viewpictures", "icon": "image"},
    "Opcenter Portal (CAMSTAR Setup)": {"link": "https://opcenter.bth.infineon.com/OpcenterPortal/default.htm#/login", "icon": "paste"},
    "Opcenter Shopfloor (CAMSTAR UI)": {"link": "https://opcenter.bth.infineon.com/OpcenterWeb/login", "icon": "database"},
    "KLUSA": {"link": "https://klusa4.intra.infineon.com/klusa_ifx_projects/klusaweb/", "icon": "code"},
    "DEVSMETS": {"link": "https://jiradc.intra.infineon.com/secure/Dashboard.jspa?selectPageId=31412", "icon": "calendar"},
    "RDE Dashboard": {"link": "https://ishare.infineon.com/sites/BE_DEV_PO/SitePages/BE%20RDE%20Project%20Office.aspx", "icon": "folder-open"},
    "PBC with PBHB": {"link": "https://intranet-content.infineon.com/explore/operations/TechnologyExcellence/ComplexityManagement/ProcessBlockCatalogPBC/Pages/index_en.aspx", "icon": "book"},
    "FMEA": {"link": "https://intranet-content.infineon.com/explore/aboutinfineon/QM/QMProcesses/FMEA/SitePages/index_en.aspx", "icon": "table"},
    "BAT OE APPLICATION": {"link": "https://oe.bth.infineon.com/", "icon": "trophy"},
    "BAT Attire & Locker": {"link": "https://apps.bth.infineon.com/attiresystem", "icon": "user"},
    "BAT Permission System": {"link": "https://apps.bth.infineon.com/Pms_System/Permission_NonShopfloor.aspx", "icon": "unlock-alt"},
    "NICA": {"link": "https://nica.icp.infineon.com/en/search", "icon":"check-square"},
    "PLM Publishing": {"link": "https://plmpublishing.icp.infineon.com/searchtable", "icon": "eye"},
    "DEV Tooling System": {"link": "https://ishare.ap.infineon.com/sites/dev-dashboard/Shared%20Documents/IFBT_DEV_Spare-Part/IFBT_DEV_Spare_Part/Index.html", "icon": "wrench"},
    "HALO": {"link": "https://haloprd.icp.infineon.com/", "icon": "globe"},
    "PDR+ V1.0": {"link": "https://pdr-plus-prd.icp.infineon.com/", "icon": "file"},
    "ICRuM": {"link": "http://prodtest.bth.infineon.com:8081/login", "icon": "calculator"},
    "iFAct": {"link": "https://ifact.sin.infineon.com/myjobs", "icon": "flask"},
    "BAT Tableau URL": {"link": "https://tableau.infineon.com/#/site/ITFI/views/Batam_Tableau_URL/BAT_Tableau_URL?:iid=1", "icon": "list-ul"},
    "Opcenter ODS Report (BAT)": {"link": "https://tableau.infineon.com/#/site/ITFI/views/MESReportToC/BATMESreportToC", "icon": "list"},
    "inSig (AOI Log Data) " : {"link": "https://insig-productive-insig.ap-sg-1.icp.infineon.com/", "icon": "search"},
    "ESH APPLICATION": {"link": "https://hsse.bth.infineon.com/", "icon": "medkit"},
    "Equipment Reservation Tool": {"link": "https://ertprod.bth.infineon.com/ert/", "icon": "lock"},
    "CONCUR": {"link": "https://us2.concursolutions.com/nui/signin/pwd?signedout=inactivity&lang=en", "icon": "plane"},
    "VISIT - Visitor/Preregister Visit": {"link": "https://visitor-management.infineon.com/", "icon": "users"},
    "IDPF/SDHB Documents": {"link": "https://webnetprod.muc.infineon.com/ecmweb/dctmpublish/gen0001_sdhb4/gen0001_sdhb4.asp", "icon": "map"},
    "IFX Worldwide Packages": {"link": "https://www.infineon.com/cms/en/product/packages/", "icon": "microchip"},
    "OEE Report": {"link": "https://tableau.infineon.com/#/site/ITFI/views/OEEReportforPOB/OEEStandardReport?:iid=1", "icon": "gear"},
    "Statistical Platform": {"link": "https://rbgxv673.rbg.infineon.com/statistics/", "icon": "line-chart"},
    "IP Portal": {"link": "https://ipms.infineon.com/ipms/AppIpms.jsp?is-smart", "icon": "fa fa-lightbulb"},
    "SPIRAL": {"link": "https://spiral.muc.infineon.com/spiral", "icon": "spinner"},
    "GPT4IFX": {"link": "https://outsystems-muc-prod.infineon.com/GPT4IFX/", "icon": "comment"},
    "PDA Wafer Inventory": {"link": "https://ishare.ap.infineon.com/sites/WaferInventory/_layouts/15/WopiFrame2.aspx?sourcedoc=%7B15E1B4C2-181F-4369-9D79-7B9DF9366547%7D&file=PDA%20Wafer%20List%20DC26.xlsx&action=default", "icon": "inbox"},
    "DEV CT300 Request": {"link": "https://ishare.ap.infineon.com/sites/CT300WI/_layouts/15/WopiFrame.aspx?sourcedoc=%7B6de387d2-7b2d-4833-bf31-2b536d89ebe4%7D&action=default&slrid=3c338ca1-ddb1-8088-c64f-28eeb8c7d0f5", "icon": "clipboard"},
    "PLATO" : {"link": "https://mucsa1446.infineon.com/e1ns/portal/#action=clearFilter&cmd=CMD_E1ns_start_page", "icon": "bookmark"},
    "YIP" : {"link": "https://yiphlp56.intra.infineon.com:8443/app/", "icon": "lightbulb"},
    "NOSTAS Request" : {"link": "https://workflowgenerator.infineon.com/portal/DEV_NOSTAS_Request_eForm/home", "icon": "file-text"},
    "MyMD" : {"link": "https://mat-database-devlogdatabase.ap-sg-1.icp.infineon.com/", "icon": "barcode"},
    "iProjEx" : {"link": "https://plmapps.icp.infineon.com/iprojex/myItems/active", "icon": "key"},
    "Team Center" : {"link": "https://teamcenterhome.infineon.com/nermal.shtml", "icon": "star"},
    "Basic Evaluation in Automated Test System (BEATS)": {"link": "https://tableau.infineon.com/#/site/ITFI/views/BEATSFINALREPORTV1/ActualvsPlanUPH/49d34c7e-0acb-48bb-8710-18226e22bd67/BEATSBAT?:iid=1", "icon" : "building"},
    "Component Task Tracking (CTT)": {"link": "https://ctt.intra.infineon.com/RequestAccess", "icon" : "tasks"},
    "Lab Manager": {"link": "https://labmanager.intra.infineon.com/register", "icon" : "flask"},
    "RAVEN": {"link": "https://raven.icp.infineon.com/", "icon" : "shield-alt"},
    "FOL Magazine Check": {"link": "https://tableau.infineon.com/#/site/ITFI/views/BTH_FOL_Magazine_Checking_Point/MagCheck?:iid=1", "icon" : "clipboard-check"},
    "Abbreviation Finder": {"link": "https://rdtools.intra.infineon.com/AbbreviationFinder/#/search", "icon" : "search"},
    "BE Equipment Integration Request eForm": {"link": "https://workflowgenerator.infineon.com/portal/EAF_BAT/home", "icon" : "file-contract"},
}

def dev_tools_page():
    st.markdown(
        '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">',
        unsafe_allow_html=True)

    st.header("Development Tools")
    st.write(
        "Dev tools bring together different applications and data in one place, increasing developer efficiency and productivity")

    # Search
    search_query = st.text_input("**Search Tools**:", "", placeholder="Cari nama tool...", key="dev_search")
    search_lower = search_query.lower().strip()

    # ================== KATEGORI ==================
    categories = {
        "Unit Process Management": ["DEV Tooling System", "Opcenter Portal (CAMSTAR Setup)",
                                    "Opcenter Shopfloor (CAMSTAR UI)", "BAT OE APPLICATION", "iFAct", "ICRuM"],
        "Digitalization of Process Data": ["NICA", "PLM Publishing", "inSig (AOI Log Data) ", "PDR+ V1.0", "HALO",
                                           "BE Equipment Integration Request eForm", "Component Task Tracking (CTT)"],
        "Insight & Report": ["BAT Tableau URL", "Opcenter ODS Report (BAT)", "OEE Report", "Statistical Platform",
                             "Basic Evaluation in Automated Test System (BEAST)", "FOL Magazine Check"],
        "Administrative": ["MY LEAVE", "MY IT", "BAT Attire & Locker", "BAT Permission System", "ESH APPLICATION",
                           "CONCUR", "VISIT - Visitor/Preregister Visit", "Equipment Reservation Tool", "YIP"],
        "Project Management": ["KLUSA", "FMEA", "PBC with PBHB", "PLATO", "iProjEx", "Team Center", "RDE Dashboard"],
        "Planning & Scheduling": ["DEVSMETS", "MyMD", "PDA Wafer Inventory", "DEV CT300 Request", "NOSTAS Request"],
        "General": ["IFX INTRANET", "PICTURE VIEWER", "IDPF/SDHB Documents", "IFX Worldwide Packages", "IP Portal",
                    "GPT4IFX", "SPIRAL", "RAVEN", "Abbreviation Finder", "Lab Manager"]
    }

    # CSS Tambahan untuk Card Lebih Besar & Lega
    st.markdown("""
    <style>
        .tool-card {
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            padding: 28px 16px;
            text-align: center;
            height: 190px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
            border: 1px solid #e0e0e0;
            margin-bottom: 20px;
        }
        .tool-card:hover {
            transform: translateY(-8px);
            box-shadow: 0 12px 25px rgba(0, 0, 0, 0.15);
            border-color: #006838;
        }
        .tool-card .icon-wrapper {
            font-size: 52px;
            color: #0A8276;
            margin-bottom: 18px;
        }
        .tool-card .tool-name {
            font-size: 1.05rem;
            font-weight: 600;
            color: #1f2937;
            line-height: 1.8;
        }
    </style>
    """, unsafe_allow_html=True)

    # Tampilkan Kategori
    for cat_name, tool_list in categories.items():
        filtered_tools = [name for name in tool_list if name in links and
                          (not search_lower or search_lower in name.lower())]

        if not filtered_tools:
            continue

        st.markdown(f"""
            <div style="background:#0A8276; color:white; padding:14px 22px; border-radius:12px; 
                        margin: 32px 0 18px 0; font-weight:700; font-size:1.6rem;">
                {cat_name}
            </div>
        """, unsafe_allow_html=True)

        cols = st.columns(4)
        for idx, name in enumerate(filtered_tools):
            data = links[name]
            icon = data.get("icon", "wrench")
            link_url = data["link"]

            with cols[idx % 4]:
                st.markdown(f'''
                    <a href="{link_url}" target="_blank" style="text-decoration: none;">
                        <div class="tool-card">
                            <i class="fa fa-{icon} icon-wrapper"></i>
                            <span class="tool-name">{name}</span>
                        </div>
                    </a>
                ''', unsafe_allow_html=True)

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
        height: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ----------------------3D Core e-form Page------------------------------------------------------
def eform_page():
    def ensure_file_exists(file_path):
        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
            cols = COLUMNS if "Requests" in file_path else USER_COLUMNS
            pd.DataFrame(columns=cols).to_excel(file_path, index=False)

    def clean_dataframe(df, columns):
        """Unified data cleaning pipeline"""
        if df.empty:
            return df

        df = df.fillna('')

        # Column-specific processing
        if 'Quantity' in df.columns:
            df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(1).astype(int)

        # Ensure required columns exist
        for col in columns:
            if col not in df.columns:
                if col == "Quantity":
                    df[col] = 1
                else:
                    df[col] = ''

        return df

    @st.cache_data(ttl=2)
    def load_Requests():
        # ensure_file_exists(REQUESTS_FILE)
        try:
            read_buffer = io.BytesIO()
            conn = SMBConnection(username=user, password=password, my_name="icp", remote_name=serverName,
                                 use_ntlm_v2=True)
            ip_address = socket.gethostbyname(str(serverName) if serverName else "localhost")
            print(conn.connect(ip_address, 139))

            # Retrieve file binary from file share into the buffer
            conn.retrieveFile(shareName, FILE_PATH_request, read_buffer)

            # Reset the buffer pointer to the beginning before reading
            read_buffer.seek(0)
            df = pd.read_excel(read_buffer, dtype=str, engine='openpyxl')
            df['No'] = df['No'].astype(str)
            # Drop unexpected columns like 'Username', keep only known
            df = df.reindex(columns=COLUMNS, fill_value='')
            print("loading, request", df.head(10))
            conn.close()
            return clean_dataframe(df, COLUMNS)
        except Exception as e:
            st.error(f"Error loading requests: {e}")
            return pd.DataFrame(columns=COLUMNS)


    def save_user_data(df):
        try:
            df.to_excel(USER_FILE, index=False)
            return True
        except Exception as e:
            st.error(f"Error saving user data: {e}")
            return False
        
    def normalize_Requestor_email(emails):
        """Mengubah input email menjadi list yang bersih"""
        if emails is None:
            return []
        if isinstance(emails, str):
            return [e.strip() for e in emails.split(',') if e.strip()]
        if isinstance(emails, list):
            return [str(e).strip() for e in emails if str(e).strip()]
        return [str(emails).strip()]


    def is_valid_Requestor_email(emails):
        """Validasi email sederhana"""
        if not emails:
            return False
        
        email_list = normalize_Requestor_email(emails)
        
        for email in email_list:
            if '@' not in email or '.' not in email.split('@')[-1]:
                return False
        return True
    @st.cache_data(ttl=300)
    
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

    def send_new_request_notification_to_admin(record_id, requestor, requestor_email, category, details, quantity=1,
                                               material='N/A', color='N/A', target_date=None, uploaded_file=None):
        """Enhanced admin notification with improved HTML"""
        try:
            user_df = load_user_data(USER_FILE)
            #print("loading user data", user_df)
            admin_df = user_df[user_df['Role'].str.lower() == 'admin']

            admin_emails =["Rahmad.Hardiansyah@infineon.com", "Catur.Pranoto@infineon.com", "SitiHanafiNilam.Sari@infineon.com", "joemathew.john@infineon.com"]

            #admin_emails = ["joemathew.john@infineon.com"]
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
            #result = send_outlook_Requestor_email(
            #    to_Requestor_emails=admin_emails,  # "; ".join(admin_emails),
            #    subject=f"🖨️ NEW REQUEST #{record_id} - {requestor} - {category}",
            #    html_body=html_body,
            #    attach=attachment_path)
            em_notif_subject = f"🖨️ NEW REQUEST #{record_id} - {requestor} - {category}"

            send_email_notification(admin_emails, password, em_notif_subject, html_body, uploaded_file=uploaded_file)


            #print(f"[ADMIN NOTIF] ✅ Request #{record_id} notification sent")
            return print(f"[ADMIN NOTIF] ✅ Request #{record_id} notification sent")
        except Exception as e:
            error_msg = f"[ADMIN NOTIF ERROR #{record_id}] {str(e)}"
            print(error_msg)
            if 'st' in locals():
                st.error(error_msg)
            return False, error_msg

    def send_status_change_Requestor_email_to_user(record_id, requestor_email, new_status, old_status=None,
                                                   admin_comment=None):
        """Clean & Consistent Status Update Email"""
        try:

            df = load_Requests()
            current_email = get_logged_in_user()
            #username = "Mathewjo"
            user_df = load_user_data(USER_FILE)
            # print("loading user data", user_df)
            user_name= user_df.loc[user_df['Requestor_email'] == current_email, 'Username'].values[0]

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


            change_html_body = f"""
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
                <p style="font-size: 18px;">Hi <strong>{user_name}</strong> ,</p>
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
            change_em_sub=f"{status_info['emoji']} Request #{record_id} • {new_status}"
            send_email_notification(requestor_email, password, change_em_sub, change_html_body)
            return print("status changed")
        except Exception as e:
            print(f"Status update email error: {e}")
            return False, str(e)

    # ========================= FILE MANAGEMENT =========================
    @st.cache_data
    def save_Requests(df):
        print("saving request")
        try:
            # Pre-process data in batch
            conn = SMBConnection(username=user, password=password, my_name="icp", remote_name=serverName,
                                use_ntlm_v2=True)
            ip_address = socket.gethostbyname(str(serverName) if serverName else "localhost")
            print(conn.connect(ip_address, 139))
            df_clean = df.copy()
            print("printing df before saving request", df_clean.head())
            date_cols = ['Request Date', 'Target Date', 'Completed Date', 'Status Start Time']
            for col in date_cols:
                if col in df_clean.columns:
                    df_clean[col] = df_clean[col].astype(str).str.replace('nan|NaT', '', regex=True)

            if 'Quantity' in df_clean.columns:
                df_clean['Quantity'] = pd.to_numeric(df_clean['Quantity'], errors='coerce').fillna(1).astype(int)

            # Single efficient write (faster than ExcelWriter for small datasets)
            # --- 4. WRITE EXCEL BACK TO FILE SHARE ---
            # Create a fresh in-memory bytes buffer for writing
            write_buffer = io.BytesIO()
            # Save the modified DataFrame as an excel structure into our buffer
            with pd.ExcelWriter(write_buffer, engine='openpyxl') as writer:

                df_clean.to_excel(writer, index=False, engine='openpyxl')

            # Reset the buffer pointer to the beginning before uploading
            write_buffer.seek(0)

            print("writing file")

            # Push the binary file stream back to the remote share (overwriting the file)
            conn.storeFile(shareName, FILE_PATH_request, write_buffer)
            print(f"Successfully updated and saved {FILE_PATH_request} back to the share.")

            conn.close()

            return True
        except Exception as e:
            st.error(f"Failed to save requests: {e}")
            return False


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

                    current_email = get_logged_in_user()
                    #current_email = "joemathew.john@infineon.com"
                    st.write("Email:", current_email)
                    requestor_email = current_email

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
                    'Status History': json.dumps(
                        [{"Status": initial_status, "Date": datetime.now().strftime("%d/%m/%y %H:%M")}]),
                    'Quantity': int(kwargs.get('Quantity', 1)),
                    'Material': kwargs.get('Material', 'N/A'),
                    'Color': kwargs.get('Color', 'N/A'),
                    'Completed Date': '',
                    'Admin Comments': ''
                }

                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                if save_Requests(df):

                    pass  # no email option at the moment-- need to query from user data
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
            {"id": 1, "label": "Review Drawing", "icon": "📋", "detail": "Drawing reviewed"},
            {"id": 2, "label": "3D drawing processing", "icon": "📐", "detail": "Design processed"},
            {"id": 3, "label": "Printing Process", "icon": "🖨️", "detail": "Printing in progress"},
            {"id": 4, "label": "Buy-off", "icon": "✅", "detail": "Quality check"},
            {"id": 5, "label": "Completed", "icon": "🏆", "detail": "Fulfilled"}]

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


    # ====================== IDENTIFIKASI USER & ROLE ======================
    #Username = getpass.getuser().lower()  -- this wont work in Openshift
    user_df = load_user_data(USER_FILE)
    #print("loading user data", user_df)
    #st.write("All headers:", st.context.headers)
    current_email=get_logged_in_user()
    #current_email = "joemathew.john@infineon.com"
    st.write(f"Logged in as {current_email}")
    # read user data csv
    # find the email


    st.session_state.current_email = current_email
    st.session_state.user_df = user_df



    role_match = st.session_state.user_df[st.session_state.user_df["Requestor_email"] == current_email]
    print("role_match", role_match)
    if not role_match.empty:
        st.session_state.current_role= role_match.iloc[0]["Role"]
        with st.sidebar:
            st.image(image='static/logo.png')
            if st.button("🏠 Home", use_container_width=True):  
                st.session_state.page = "Home"
                st.rerun()
            if st.button("📝 New Request", use_container_width=True): 
                st.session_state.page = "Request Form"
                st.rerun()
            if st.button("📋 My Requests", use_container_width=True): 
                st.session_state.page = "My Requests"
                st.rerun()

            st.markdown("---")
            st.markdown("### ⚙️ Admin")
            if st.button("🛠️ Admin Panel", use_container_width=True):
                st.session_state.page = "Admin Panel"
                st.rerun()
            if st.button("👥 User Management", use_container_width=True):
                st.session_state.page = "User Management"
                st.rerun()
            if st.button("📊 Activity Log", use_container_width=True):
                st.session_state.page = "Activity Log"
                st.rerun()
            if 'page' not in st.session_state:
                st.session_state.page = "Home"

        
# -------DAILY QUOTES BANNER --------
        def get_daily_quote():
            hour_of_day = datetime.now().hour
            return DAILY_QUOTES[hour_of_day % len(DAILY_QUOTES)]

        DAILY_QUOTES = [
            "Innovation distinguishes between a leader and a follower.",
            "The best way to predict the future is to create it.",
            "3D printing is not just technology, it's a revolution.",
            "Every layer builds a better tomorrow.",
            "Design. Print. Innovate. Repeat.",
            "Make it happen. 3D printing makes it possible.",
            "From imagination to reality, one layer at a time.",
            "The future is additive."]

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
            col_left, col_right = st.columns(2, gap="medium")

            with col_left:
                st.markdown("#### 🖨️ Machine Appearance")
                st.image("static/machine.png", caption="3D Printer Machine", width='stretch')

            with col_right:
                st.markdown("#### 📋 Technical Specifications")
                st.image("static/spec.png", caption="Machine Specifications", width='stretch')

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
                "🔍 Select a Comparison Table to View:", [
                    "Impact Resistance",
                    "Chemical Resistance",
                    "Thermal Properties",
                    "Printing Parameters",
                    "Price Comparison",
                    "General Recommendations"], key="box7")

            # --- Impact Resistance ---
            if Category == "Impact Resistance":
                st.subheader("Impact Resistance Comparison")
                impact_df = pd.DataFrame({
                    "Material": ["TPU", "PP", "PC", "PAHT-CF", "PETG", "ABS", "PLA"],
                    "Impact Resistance": ["Excellent", "Excellent", "Very High", "High", "Moderate-High", "Moderate",
                                          "Low"],
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
                    "Material": ["PAHT-CF (Polyamide High-Temperature Carbon Fiber)", "PC (Polycarbonate)",
                                 "ABS (Acrylonitrile Butadiene Styrene)", "PP (Polypropylene)",
                                 "PETG (Polyethylene Terephthalate Glycol-modified)",
                                 "TPU (Thermoplastic Polyurethane)", "PLA (Polylactide)"],
                    "Glass Transition (Tg)": ["120°C", "140°C", "100°C - 105°C", "-10°C to 0°C", "80°C - 85°C", "-38°C",
                                              "55°C - 60°C"],
                    "Heat Deflection (HDT)": ["150°C - 190°C*", "130°C", "90°C - 98°C", "100°C - 105°C**",
                                              "65°C - 75°C", "N/A (Flexible)", "~55°C"],
                    "Max Use Temp": ["<150°C", "<130°C", "<90°C", "<100°C", "<70°C", "<60°C", "<50°C"]})
                st.dataframe(thermal_df, width='stretch', hide_index=True, column_config={
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
                    "Price Range (IDR per 1kg)": ["125,000 – 385,000", "121,000 – 400,000", "132,000 – 245,000",
                                                  "132,000 – 140,000", "216,000 – 630,000", "258,000 – 1,000,000",
                                                  "1,086,000+"],
                    "Market Average": ["IDR181,000", "IDR266,000", "IDR209,000", "IDR135,000", "IDR348,000",
                                       "IDR863,000", "IDR1,086,000"],
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
                        df['comp_date'] = pd.to_datetime(df['Completed Date'], format='%d/%m/%Y %H:%M:%S',
                                                         errors='coerce')

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
                    'avg_lead_time': avg_lead_time}

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
        user_df = load_user_data(USER_FILE)
        current_email = get_logged_in_user()

        st.session_state.current_email = current_email
        st.session_state.user_df = user_df
        st.session_state.current_role=""
        st.session_state.current_user = ""

        role_match = st.session_state.user_df[st.session_state.user_df["Requestor_email"] == current_email]
        print("role_match", role_match)
        if not role_match.empty:
            st.session_state.current_role = role_match.iloc[0]["Role"]
            st.session_state.current_user = role_match.iloc[0]["Username"]
            print("role", st.session_state.current_role)
            print("Username", st.session_state.current_user)


        st.markdown("<h1>📝 New Request</h1>", unsafe_allow_html=True)
        st.markdown("---")
        with st.form("request_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                requestor = st.text_input("Requestor Name", value=st.session_state.current_user, disabled=True)
            with col2:

                requestor_email = st.text_input("Requestor Email", value=st.session_state.current_email, disabled=True)

            col3, col4 = st.columns(2)
            with col3:
                category = st.selectbox("Category *", Category_OPTIONS, key="box6")
            with col4:
                target_date = st.date_input("Target Date *", value=datetime.now() + timedelta(days=7))

            col5, col6 = st.columns(2)
            with col5:
                quantity = st.number_input("Quantity *", min_value=1, value=1)
            with col6:
                material = st.selectbox("Material *", Material_OPTIONS)

            col7, col8 = st.columns(2)
            with col7:
                color = st.selectbox("Color *", Color_OPTIONS, key="box5")
            with col8:
                has_drawing = st.selectbox("3D Drawing Available?*", [" ", "YES", "NO"], key="box4")

            details = st.text_area("Project Details *", placeholder="Enter the project details",height=180)

            uploaded_file = st.file_uploader(
                "📎 Upload 3D File Attachment",
                type=['dwg', 'stl', 'pptx', 'pdf', 'png', 'JPG', 'jpeg'],
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
                       uploaded_file=uploaded_file
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
        user_df = load_user_data(USER_FILE)
        current_email = get_logged_in_user()
        #current_email = "joemathew.john@infineon.com"
        st.session_state.user_df=""
        st.session_state.current_email =""
        st.session_state.current_role=""
        st.session_state.current_email=current_email
        st.session_state.user_df = user_df

        role_match = st.session_state.user_df[st.session_state.user_df["Requestor_email"] == current_email]
        if not role_match.empty:
            st.session_state.current_role = role_match.iloc[0]["Role"]
            print("Role",st.session_state.current_role )


        if df.empty:
            st.info("No requests found.")
        else:
            my_requests = df[df['Requestor_email'].str.lower() == st.session_state.current_email.lower() if st.session_state.current_email else None]
            for _, row in my_requests.iterrows():
                with st.expander(f"#{row['No']} | {row['Status']}", expanded=False):
                    dynamic_progress_tracker(row)
                    st.write(f"**Category:** {row.get('Category', '')}")
                    st.write(f"**Material:** {row.get('Material', '')} | **Color:** {row.get('Color', '')}")
                    st.write(f"**Details:** {row.get('Details', '')}")

                    if st.session_state.current_role == "Admin":
                        new_status = st.selectbox("Update Status", STATUS_OPTIONS,
                                                  index=STATUS_OPTIONS.index(row['Status']) if row[
                                                                                                   'Status'] in STATUS_OPTIONS else 0,
                                                  key=f"status_{row['No']}")
                        admin_comment = st.text_area("Admin Comments", placeholder= "Enter Admin comments here", key=f"comment_{row['No']}")
                        if st.button("Update Status", key=f"upd_{row['No']}"):
                            print("updating status to ", new_status)
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

        current_email = get_logged_in_user()
        #current_email = "joemathew.john@infineon.com"
        #st.write("Email:", current_email)
        st.session_state.current_email = current_email

        role_match = st.session_state.user_df[st.session_state.user_df["Requestor_email"] == current_email]
        print(role_match)
        if not role_match.empty:
            st.session_state.current_role = role_match.iloc[0]["Role"]

        else:
            st.session_state.current_role = "User"

        if st.session_state.current_role == "Admin":
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
                            st.markdown("### 🔄  Status")
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

        else:
            st.error("You do not have access to this page.")
            st.stop()




    # ======================== USER MANAGEMENT ===========================
    elif st.session_state.page == "User Management":

        current_email = get_logged_in_user()
        #current_email = "joemathew.john@infineon.com"
        # st.write("Email:", current_email)
        st.session_state.current_email = current_email
        if st.session_state.current_email not in ["sitihanafinilam.sari@Infineon.com", "Rahmad.Hardiansyah@infineon.com", "Catur.Pranoto@infineon.com"]:
            st.error("You do not have access to this page.")
            st.stop()

        st.markdown("<h1>👥 User Management</h1>", unsafe_allow_html=True)
        st.markdown("---")

        if 'user_df' not in st.session_state:
            st.session_state.user_df = load_user_data(USER_FILE)

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
        with h[0]:
            st.markdown("**ID**")
        with h[1]:
            st.markdown("**Username**")
        with h[2]:
            st.markdown("**Email**")
        with h[3]:
            st.markdown("**Role**")
        with h[4]:
            st.markdown("**Actions**")
        st.markdown("---")

        # Tampilkan daftar user
        for i, row in user_df.iterrows():
            orig_idx = st.session_state.user_df[st.session_state.user_df['User_ID'] == row['User_ID']].index[0]

            c = st.columns([0.8, 2.5, 3.5, 2, 2])
            with c[0]:
                st.write(f"**#{int(row['User_ID'])}**")
            with c[1]:
                st.write(row['Username'])
            with c[2]:
                st.write(row['Requestor_email'])
            with c[3]:
                st.write(row['Role'])

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
                    new_role = st.selectbox("Role", ["User", "Admin"], key="box3")

                if st.form_submit_button("💾 Save User", type="primary"):
                    if not new_username or not new_email:
                        st.error("Username and email address are required!")
                    elif (not st.session_state.user_df.empty and
                          new_username.lower() in st.session_state.user_df['Username'].str.lower().values):
                        st.error(f"Username '{new_username}' already exists!")
                    else:
                        new_id = int(
                            st.session_state.user_df['User_ID'].max()) + 1 if not st.session_state.user_df.empty else 1

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
                                             index=0 if row['Role'] == "User" else 1, key="box2")

                if st.form_submit_button("💾 Save Changes", type="primary"):
                    st.session_state.user_df.at[idx, 'Username'] = edit_name.strip() if edit_name else row['Username']
                    st.session_state.user_df.at[idx, 'Requestor_email'] = edit_email.strip() if edit_email else row['Requestor_email']
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
        current_email = get_logged_in_user()
        #current_email = "joemathew.john@infineon.com"
        # st.write("Email:", current_email)
        st.session_state.current_email = current_email
        if st.session_state.current_email not in ["sitihanafinilam.sari@Infineon.com",
                                                  "Rahmad.Hardiansyah@infineon.com", "Catur.Pranoto@infineon.com"]:
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
                            'Username': requestor if i == 0 else f"{requestor} (Admin)",
                            'Action': 'REQUEST CREATED' if i == 0 else 'STATUS UPDATED',
                            'Description': f"Request #{req_id}: {event.get('Status', 'Unknown')}" +
                                           (f" | Comment: {event.get('Admin Comments', '')}" if event.get(
                                               'Admin Comments') else ''),
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
                return pd.DataFrame(columns=['Request_ID', 'Time', 'Username', 'Action', 'Description'])

            log_df = pd.DataFrame(all_events).sort_values('Time', ascending=False).reset_index(drop=True)
            return log_df.head(100)

        log_df = parse_activity_log(load_Requests())

        st.dataframe(
            log_df,
            width='stretch',
            hide_index=True,
            column_config={
                "Time": st.column_config.DatetimeColumn("🕒 Time", width="medium"),
                "Username": st.column_config.TextColumn("👤 Username", width="medium"),
                "Action": st.column_config.TextColumn("🏷️ Action", width="medium"),
                "Description": st.column_config.TextColumn("📝 Description", width="large")})

        col1, col2 = st.columns(2)
        col1.button("🔄 Refresh", on_click=lambda: st.cache_data.clear() or st.rerun())
        col2.metric("Total Events", len(log_df))

        st.caption("💡 Real activity from Status History")
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
        } 
            /* Logo styling */
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 50px; /* Add some space below the logo */
        }   
        .eform-logo {
            width: 300px; /* Adjust the size as needed */
            height: auto; /* Maintain aspect ratio */
        }
        </style>    
        """,
        unsafe_allow_html=True
    )

# -------------------------------------Main Page--------------------------------------------------------------
st.set_page_config(page_title="BE DEV Dashboard", page_icon=":computer:", layout="wide")

pages = {
    "Home": landing_page,
    "Data System Monitoring": data_system_monitoring_page,
    "Training & Knowledge": training_page,
    "Dev Tools": dev_tools_page,
    "3D Core e-form": eform_page
}

st.sidebar.title("**BE DEV Dashboard**")

with st.sidebar:
    selected_dash = option_menu(
        menu_title=None,
        options=list(pages.keys()),
        icons=["house", "database", "universal-access", "wrench", "printer"],
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