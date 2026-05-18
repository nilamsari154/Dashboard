import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import getpass
import win32com.client
import json
import pythoncom


# =============== CONFIGURATION ===========================
COLUMNS = ["No", "Parent_No", "Request Date", "Target Date", "Requestor", "Requestor_email", "Category", "Details", "Status", 
           "Status Start Time", "Quantity", "Material", "Color", "Completed Date", "Status History", "Admin Comments"]

USER_COLUMNS = ["User_ID", "Username", "Requestor_email", "Role", "Domain", "Active"]
Category_OPTIONS = ["Innovation", "Spare Part Replacement", "YIP/Improvement", "Others"]
STATUS_OPTIONS = ["Review Drawing", "3D drawing processing", "Printing Process", "Buy-off", "Completed", "Rejected"]
Material_OPTIONS = ["PLA", "PETG", "ABS", "TPU", "PP", "PC", "PAHT-CF", "Nylon", "Other"]
Color_OPTIONS = ["Black", "White", "Grey", "Other"]


REQUESTS_FILE = "static/Requests.xlsx"
USER_FILE = "static/user_data.xlsx"

    
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
    ensure_file_exists(REQUESTS_FILE)
    try:
        if os.path.getsize(REQUESTS_FILE) == 0:
            return pd.DataFrame(columns=COLUMNS)
        df = pd.read_excel(REQUESTS_FILE, dtype=str)
        df['No'] = df['No'].astype(str)
        # Drop unexpected columns like 'Username', keep only known
        df = df.reindex(columns=COLUMNS, fill_value='')
        return clean_dataframe(df, COLUMNS)
    except Exception as e:
        st.error(f"Error loading requests: {e}")
        return pd.DataFrame(columns=COLUMNS)

@st.cache_data(ttl=2)
def load_user_data():
    ensure_file_exists(USER_FILE)
    try:
        if os.path.getsize(USER_FILE) == 0:
            return pd.DataFrame(columns=USER_COLUMNS)
        df = pd.read_excel(USER_FILE)
        return clean_dataframe(df, USER_COLUMNS)
    except:
        return pd.DataFrame(columns=USER_COLUMNS)

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
@st.cache_data
def save_Requests(df):
    try:
        # Pre-process data in batch
        df_clean = df.copy()
        date_cols = ['Request Date', 'Target Date', 'Completed Date', 'Status Start Time']
        for col in date_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].astype(str).str.replace('nan|NaT', '', regex=True)
        
        if 'Quantity' in df_clean.columns:
            df_clean['Quantity'] = pd.to_numeric(df_clean['Quantity'], errors='coerce').fillna(1).astype(int)
        
        # Single efficient write (faster than ExcelWriter for small datasets)
        df_clean.to_excel(REQUESTS_FILE, index=False, engine='openpyxl')
        return True
    except Exception as e:
        st.error(f"Failed to save requests: {e}")
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
st.set_page_config(page_title="3D Core e-form", layout="wide", page_icon="🖨️")

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
                    "📎 Upload 3D File Attachment", 
                    type=['dwg', 'stl', 'pptx', 'pdf', 'png', 'jpg', 'jpeg'],
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