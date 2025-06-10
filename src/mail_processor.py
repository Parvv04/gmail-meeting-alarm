import base64
import re
from dateutil.parser import parse
from datetime import datetime, timedelta
import platform
import ctypes
import os
import tkinter as tk
from tkinter import messagebox
import webbrowser

def decode_body(payload):
    """Decode email body from base64"""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                return base64.urlsafe_b64decode(data).decode()
    return ""

def contains_meeting(email_body, keywords):
    """Check if email contains meeting keywords"""
    body_lower = email_body.lower()
    return any(keyword in body_lower for keyword in keywords)

def extract_meeting_link(email_body):
    """Extract meeting links from email body"""
    patterns = [
        r'(https:\/\/zoom.us\/j\/\d+)',
        r'(https:\/\/teams.microsoft.com\/l\/meetup-join\/[^\s]+)',
        r'(https:\/\/meet.google.com\/[a-z]{3}-[a-z]{4}-[a-z]{3})',
        r'(https:\/\/[^\s]*webex.com[^\s]*)'
    ]
    for pattern in patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

def extract_meeting_details(email_body):
    """
    Extract meeting details from email body with support for:
    - Natural language dates
    - Timezones
    - Today/tomorrow references
    - Meeting titles
    """
    # 1. Title Extraction
    title_match = re.search(
        r'(?:meeting|event)\s*(?:about|for|on|:)\s*["\']?(.*?)(?=["\']?\s*(?:on|at|for)|[.!?]|$)',
        email_body, 
        re.IGNORECASE
    )
    title = title_match.group(1).strip() if title_match else "Scheduled Meeting"

    # 2. Timezone Support
    tz_match = re.search(r'\b(EST|PST|CST|IST|UTC|EDT|PDT|CDT)\b', email_body, re.IGNORECASE)
    timezone = tz_match.group(1) if tz_match else None

    # 3. Today/Tomorrow Handling
    base_date = None
    if 'today' in email_body.lower():
        base_date = datetime.now()
    elif 'tomorrow' in email_body.lower():
        base_date = datetime.now() + timedelta(days=1)

    # 4. Natural Language Parsing
    natural_match = re.search(
        r'(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?(?:\s+of\s+)?(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*)(?:\s+)?(?:\d{4})?.*?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)|(\d{1,2}\s*(?:AM|PM|am|pm)))',
        email_body,
        re.IGNORECASE
    )

    if natural_match:
        day = natural_match.group(1)
        month = natural_match.group(2)
        time_part = natural_match.group(3) or natural_match.group(4)
        year_match = re.search(r'(\d{4})', email_body)
        year = year_match.group(1) if year_match else str(datetime.now().year)
        
        try:
            date_str = f"{day} {month} {year}" if not base_date else base_date.strftime("%d %B %Y")
            time_str = time_part.replace(' ', '')
            
            if timezone:
                time_str += f" {timezone}"
                
            meeting_time = parse(f"{date_str} {time_str}")
            return {
                'title': title,
                'time': meeting_time,
                'link': extract_meeting_link(email_body)
            }
        except Exception as e:
            print(f"Parse error: {e}")

    # 5. Structured Format Fallback
    structured_time = re.search(
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}).*?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)',
        email_body,
        re.IGNORECASE
    )

    if structured_time:
        try:
            meeting_time = parse(f"{structured_time.group(1)} {structured_time.group(2)}")
            if timezone:
                meeting_time = parse(f"{structured_time.group(1)} {structured_time.group(2)} {timezone}")
            return {
                'title': title,
                'time': meeting_time,
                'link': extract_meeting_link(email_body)
            }
        except Exception as e:
            print(f"Structured parse error: {e}")

    return {
        'title': title,
        'time': None,
        'link': extract_meeting_link(email_body)
    }

def send_notification(sender, meeting_title, start_time, meeting_link=None):
    """Show platform-appropriate meeting notification"""
    # Format time and date
    time_str = start_time.strftime("%I:%M %p") if start_time else "Time not specified"
    date_str = start_time.strftime("%A, %d %B %Y") if start_time else "Date not specified"
    
    # Detect platform from link
    platform_name = "Unknown Platform"
    if meeting_link:
        if "zoom.us" in meeting_link.lower():
            platform_name = "Zoom"
        elif "teams.microsoft" in meeting_link.lower():
            platform_name = "Microsoft Teams"
        elif "meet.google" in meeting_link.lower():
            platform_name = "Google Meet"
        elif "webex.com" in meeting_link.lower():
            platform_name = "Webex"
    
    # Build message
    message = f"""📢 {meeting_title}
👤 From: {sender}
⏰ Time: {time_str}
📅 Date: {date_str}
🌐 Platform: {platform_name}"""
    
    # Platform-specific notifications
    if platform.system() == 'Windows':
        # Windows native alert
        response = ctypes.windll.user32.MessageBoxW(
            0,
            f"{message}\n\n{'Click OK to join' if meeting_link else ''}",
            "MEETING ALERT",
            0x40 | 0x1  # Info icon + OK/Cancel buttons
        )
        if response == 1 and meeting_link:  # IDOK = 1
            webbrowser.open(meeting_link)
    
    elif platform.system() == 'Darwin':  # MacOS
        os.system(f"""
        osascript -e 'display notification "{message}" with title "MEETING ALERT"'
        """)
        if meeting_link:
            webbrowser.open(meeting_link)
    
    else:  # Linux/other - use tkinter fallback
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        if meeting_link:
            response = messagebox.askyesno(
                "MEETING ALERT",
                f"{message}\n\nJoin now?",
                icon='info'
            )
            if response:
                webbrowser.open(meeting_link)
        else:
            messagebox.showinfo(
                "MEETING ALERT",
                message,
                icon='info'
            )
        # Auto-close after 30 seconds
        root.after(30000, root.destroy)
        root.mainloop()