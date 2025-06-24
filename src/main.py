from fastapi import FastAPI, Request, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import threading
import time
import os
from src.auth import authenticate, get_token_files
from src.mail_processor import decode_body, contains_meeting, extract_meeting_details

app = FastAPI()

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory state
meetings = []
settings = {
    "checkInterval": 5,
    "alertTime": 10,
    "emailKeywords": "meeting, zoom, conference, appointment, masterclass, workshop",
    "allowedMailIds": ""
}
stats = {
    "totalMeetings": 0,
    "upcomingMeetings": 0,
    "emailsScanned": 0,
    "successRate": 0
}
is_running = False
monitor_thread = None

class Meeting(BaseModel):
    id: Optional[str]
    title: str
    time: Optional[str]
    sender: str
    platform: Optional[str] = "Unknown"
    link: Optional[str] = None

class Settings(BaseModel):
    checkInterval: int
    alertTime: int
    emailKeywords: str
    isSystemRunning: Optional[bool] = False

class AccountRequest(BaseModel):
    email: str

@app.get("/api/meetings")
def get_meetings():
    return meetings

@app.post("/api/settings")
async def save_settings(req: Request):
    global settings
    data = await req.json()
    settings.update(data)
    return {"status": "ok", "settings": settings}

@app.get("/api/stats")
def get_stats():
    stats["upcomingMeetings"] = len([m for m in meetings if m.get("time") and parse_time(m["time"]) > time_now()])
    stats["successRate"] = stats["emailsScanned"] and int((stats["totalMeetings"] / stats["emailsScanned"]) * 100) or 0
    return stats

@app.post("/api/start")
def start_monitoring():
    global is_running, monitor_thread
    from src.auth import get_token_files
    if not is_running:
        is_running = True
        token_files = get_token_files()
        if not token_files:
            # Fallback to single token.json for backward compatibility
            token_files = [os.path.join(os.path.dirname(__file__), '../token.json')]
        for token_path in token_files:
            t = threading.Thread(target=monitor_emails_for_token, args=(token_path,), daemon=True)
            t.start()
    return {"status": "started"}

@app.post("/api/stop")
def stop_monitoring():
    global is_running
    is_running = False
    return {"status": "stopped"}

@app.get("/api/check-emails")
def api_check_emails():
    # Return meetings as the frontend expects
    return meetings

@app.post("/api/add-account")
def add_account(req: AccountRequest):
    email = req.email.strip().lower()
    # Start OAuth flow for this email, save token as token-<email>.json
    try:
        token_path = os.path.join(os.path.dirname(__file__), f"../token-{email}.json")
        if os.path.exists(token_path):
            return {"success": True, "message": "Account already authenticated."}
        # This should trigger the OAuth flow and save the token file
        creds = authenticate(token_path, email=email)
        if creds:
            # Start monitoring thread for this account
            t = threading.Thread(target=monitor_emails_for_token, args=(token_path,), daemon=True)
            t.start()
            return {"success": True}
        else:
            return {"success": False, "error": "Authentication failed."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/remove-account")
def remove_account(req: AccountRequest):
    email = req.email.strip().lower()
    token_path = os.path.join(os.path.dirname(__file__), f"../token-{email}.json")
    try:
        if os.path.exists(token_path):
            os.remove(token_path)
        # Optionally, stop monitoring thread for this account (if tracked)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/accounts")
def get_accounts():
    token_files = get_token_files()
    accounts = []
    for path in token_files:
        if path.endswith(".json"):
            name = os.path.basename(path)
            if name.startswith("token-") and name.endswith(".json"):
                email = name[len("token-"):-len(".json")]
                accounts.append(email)
    return {"accounts": accounts}

def parse_time(dt_str):
    from dateutil.parser import parse
    from datetime import datetime
    try:
        dt = parse(dt_str)
        # Convert to naive local time for comparison
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return time_now()

def time_now():
    from datetime import datetime
    return datetime.now()

def monitor_emails_for_token(token_path):
    from src.auth import authenticate
    creds = authenticate(token_path)
    from googleapiclient.discovery import build
    service = build('gmail', 'v1', credentials=creds)
    # Get the authenticated email address for this token
    profile = service.users().getProfile(userId='me').execute()
    account_email = profile.get('emailAddress')
    print(f"[DEBUG] Monitoring for account: {account_email}")
    processed_ids = set()
    # Use allowedMailIds from settings, fallback to config.json if empty
    allowed_mail_ids = [s.strip().lower() for s in settings.get("allowedMailIds", "").split(",") if s.strip()]
    if not allowed_mail_ids:
        import json
        import os
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
                allowed_mail_ids = [s.strip().lower() for s in config.get("allowed_senders", [])]
    check_interval = int(settings.get("checkInterval", 5)) * 60
    meeting_keywords = [kw.strip().lower() for kw in settings.get("emailKeywords", "meeting, zoom, conference, appointment, masterclass, workshop").split(",")]
    while is_running:
        try:
            query = " OR ".join([f'from:{sender}' for sender in allowed_mail_ids]) if allowed_mail_ids else None
            gmail_query = f'{query} is:unread' if query else 'is:unread'
            results = service.users().messages().list(
                userId='me',
                q=gmail_query
            ).execute()
            messages = results.get('messages', [])
            for msg in messages:
                if msg['id'] in processed_ids:
                    continue
                msg_data = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                sender = next((h['value'] for h in msg_data['payload']['headers'] if h['name'] == 'From'), None)
                subject = next((h['value'] for h in msg_data['payload']['headers'] if h['name'] == 'Subject'), None)
                print(f"[DEBUG] Checking email from: {sender} | Subject: {subject}")
                sender_email = sender.lower() if sender else ''
                # Only process if sender matches allowed_mail_ids (if set)
                if allowed_mail_ids and not any(mail_id in sender_email for mail_id in allowed_mail_ids):
                    processed_ids.add(msg['id'])
                    continue
                body = decode_body(msg_data['payload'])
                if contains_meeting(body, meeting_keywords):
                    details = extract_meeting_details(body)
                    meeting_obj = {
                        "id": msg['id'],
                        "title": details['title'],
                        "time": details['time'].isoformat() if details['time'] else None,
                        "sender": sender,
                        "platform": "Unknown",
                        "link": details['link'],
                        "account": account_email
                    }
                    meetings.append(meeting_obj)
                    stats["totalMeetings"] += 1
                    # Send desktop notification
                    from src.mail_processor import send_notification
                    send_notification(sender, details['title'], details['time'], details['link'])
                processed_ids.add(msg['id'])
            stats["emailsScanned"] += 1
            time.sleep(check_interval)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)