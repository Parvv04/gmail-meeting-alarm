import base64
import re
from dateutil.parser import parse
from plyer import notification

def decode_body(payload):
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                return base64.urlsafe_b64decode(data).decode()
    return ""

def contains_meeting(email_body, keywords):
    body_lower = email_body.lower()
    return any(keyword in body_lower for keyword in keywords)

def send_notification(sender, meeting_time=None):
    title = "URGENT: Meeting Detected!"
    message = f"New meeting email from {sender}"
    if meeting_time:
        message += f"\nScheduled for: {meeting_time.strftime('%Y-%m-%d %H:%M')}"
    
    notification.notify(
        title=title,
        message=message,
        app_name="Gmail Meeting Alarm",
        timeout=10
    )