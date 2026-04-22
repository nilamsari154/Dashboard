import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.colored_header import colored_header
import os
import requests
import mimetypes
from decouple import Config, RepositoryEnv
import smbclient
from smb.SMBConnection import *
import socket


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


# Setting up connection with shared drive
try:
    conn = SMBConnection(username=user, password=password, my_name="icp", remote_name=serverName, use_ntlm_v2=True)
    ip_address = socket.gethostbyname(serverName)
    print(conn.connect(ip_address, 139))
except Exception as e:
    st.error(f"Failed to connect to shared drive: {e}")
    conn = None  # Set conn to None if connection fails


# Create empty file objects for writing image contents
# Ensure the 'static' directory exists
if not os.path.exists('static'):
    os.makedirs('static')

dev_im = open('static/devsmets.jpg', "wb")
pv_im = open('static/pv.jpg', "wb")
nica_im = open('static/nica.jpg', "wb")

st.set_page_config(page_title="BE DEV Dashboard", page_icon=":computer:", layout="wide")


# --- Landing Page Function ---
def landing_page():
    st.markdown(
        """
        <style>
        .main-header {
            font-size: 4em;
            text-align: center;
            color: #007bff; /* Blue color */
            margin-bottom: 20px;
            font-weight: bold;
            animation: fadeIn 2s ease-in-out; /* Fade-in animation */
        }
        .subheader {
            font-size: 2.8em;
            text-align: center;
            color: #333;
            margin-bottom: 15px;
            animation: slideInUp 1.5s ease-out; /* Slide-in from bottom animation */
        }
        .description-text {
            font-size: 4.2em;
            line-height: 1.6;
            color: #555;
            text-align: justify;
            margin-bottom: 15px;
        }
        .key-features-header {
            font-size: 2.2em; /* Slightly larger for emphasis */
            color: #007bff;
            margin-bottom: 10px; /* More space below header */
            font-weight: bold;
            text-align: left; /* Keep left-aligned */
            animation: fadeIn 1.5s ease-in-out; /* Add fade-in for this header too */
        }
        .feature-card {
            background-color: #f0f2f6; /* Card background color */
            border-radius: 20px;
            padding: 25px; /* Slightly more padding */
            margin-bottom: 25px; /* More space between cards */
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease, opacity 0.5s ease, transform 0.5s ease; /* Added opacity and transform for slide-in */
            min-height: 300px; /* Explicit minimum height for consistency */
            display: flex;
            flex-direction: column;
            justify-content: flex-start; /* Align content to the top */
            opacity: 0; /* Start hidden for slide-in animation */
            transform: translateY(20px); /* Start slightly below for slide-in */
        }
        .feature-card:hover {
            transform: translateY(-5px); /* Move slightly up on hover */
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
        }
        .feature-card h3 {
            color: #0A8276; /* Feature title color */
            margin-bottom: 15px; /* More space below title */
            font-size: 1.6em; /* Slightly larger title */
            display: flex;
            align-items: center; /* Align icon and text vertically */
        }
        .feature-card p {
            font-size: 1.05em; /* Slightly larger text */
            color: #666;
            line-height: 1.6; /* Improve readability */
        }
        .feature-card i {
            margin-right: 12px; /* More space between icon and text */
            color: #0A8276;
            font-size: 1.8em; /* Slightly larger icon */
            transition: transform 0.3s ease, color 0.3s ease; /* Added transition for icon */
        }
        .feature-card:hover i {
            transform: scale(1.1); /* Slightly enlarge icon on hover */
            color: #0056b3; /* Change color on hover (darker blue) */
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
        @keyframes slideInFromLeft {
            from { transform: translateX(-50px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideInFromRight {
            from { transform: translateX(50px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        /* Animation for individual feature cards */
        .feature-card.animate-left {
            animation: slideInFromLeft 0.8s ease-out forwards;
        }
        .feature-card.animate-right {
            animation: slideInFromRight 0.8s ease-out forwards;
        }

        /* Adding animation delays for staggered effect */
        .feature-card:nth-child(1) { animation-delay: 0.2s; }
        .feature-card:nth-child(2) { animation-delay: 0.4s; }
        .feature-card:nth-child(3) { animation-delay: 0.6s; } /* If you add more cards */
        .feature-card:nth-child(4) { animation-delay: 0.8s; } /* If you add more cards */

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
            <div class="feature-card animate-left">
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
            <div class="feature-card animate-left">
                <h3><i class="fa fa-dashboard"></i> Dashboard Overview</h3>
                <p>Gain immediate insights with a high-level overview of critical project statuses,
                important announcements, and recent updates. This section serves as your daily briefing,
                keeping you informed without the need to navigate through multiple systems. Quickly identify
                key metrics and prioritize your tasks effectively.</p>
            </div>
            <div class="feature-card animate-left">
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
            <div class="feature-card animate-right">
                <h3><i class="fa fa-book"></i> Training & Knowledge Base</h3>
                <p>Empower yourself with a comprehensive library of general training resources and
                process-specific training materials. Whether you're onboarding new team members,
                upskilling existing talent, or seeking quick refreshers, this section provides structured
                learning paths and readily available documentation for various technical areas. From
                fundamental concepts to advanced methodologies, continuous learning is just a click away. </p>
            </div>
            <div class="feature-card animate-right">
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
    print(" report_month_str", report_month_str)
    report_month = month_names.index(report_month_str) + 1
    return report_year, report_month, report_month_str

#---------------------------------Data System Monitoring---------------------------------------------------
def data_system_monitoring_page():
    report_year, report_month, report_month_str = show_report_month()
    try:
        with open('static/devsmets.jpg', "wb") as dev_im_temp:
            res1_attributes, res1size = conn.retrieveFile(shareName, os.path.join(folderName, f'DEVSPACE_{report_month_str}_{report_year}.jpg'), dev_im_temp)
        with open('static/pv.jpg', "wb") as pv_im_temp:
            res2_attributes, res2size = conn.retrieveFile(shareName, os.path.join(folderName, f'PV_{report_month_str}_{report_year}.jpg'), pv_im_temp)
        with open('static/nica.jpg', "wb") as nica_im_temp:
            res3_attributes, res3size = conn.retrieveFile(shareName, os.path.join(folderName, f'NICA_{report_month_str}_{report_year}.jpg'), nica_im_temp)


        st.markdown("---")
        st.subheader(f"Devspace Monthly Monitoring report for {report_month_str}")
        st.image('static/devsmets.jpg') # Display image from the static folder
        st.markdown("---")
        st.subheader(f"PV Monthly Monitoring report for {report_month_str}")
        st.image('static/pv.jpg') # Display image from the static folder
        st.markdown("---")
        st.subheader(f"NICA Monthly Monitoring report for {report_month_str}")
        st.image('static/nica.jpg') # Display image from the static folder
    except OperationFailure:
        st.info(f":red[Image for Data systems **'{report_month_str} {report_year}'** is not yet available.]")

    print(os.getcwd())
    # st.subhe # Removed: Incomplete line

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
            height: center;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


#----------------------3D Core e-form Page------------------------------------------------------
def eform_page():
    st.header("3D Core e-form")
    st.info("This section provides access to the 3D Core e-form for streamlined data entry and management.")
    add_vertical_space(2)

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
        


#-------------------------------------Main Page--------------------------------------------------------------
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