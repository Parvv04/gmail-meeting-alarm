from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import threading
import time
import os
from src.auth import authenticate, get_token_files, get_authorization_url, exchange_code
import urllib.parse
from src.mail_processor import decode_body, contains_meeting, extract_meeting_details

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _get_redirect_uri():
    """Read the registered redirect URI from credentials.json."""
    import json
    creds_path = os.path.join(os.path.dirname(__file__), "../credentials.json")
    with open(creds_path) as f:
        data = json.load(f)
    # Supports both 'web' and 'installed' credential types
    client = data.get("web") or data.get("installed") or {}
    uris = client.get("redirect_uris", [])
    if uris:
        return uris[0]
    raise ValueError("No redirect_uris found in credentials.json")

meetings = []
settings = {
    "checkInterval": 5,
    "alertTime": 10,
    "emailKeywords": "meeting, zoom, conference, appointment, masterclass, workshop, meet, gmeet, google meet",
    "allowedMailIds": ""
}
stats = {
    "totalMeetings": 0,
    "upcomingMeetings": 0,
    "emailsScanned": 0,
    "successRate": 0
}
is_running = False

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
    global is_running
    if not is_running:
        is_running = True
        token_files = get_token_files()
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
    return meetings

@app.get("/api/accounts")
def get_accounts():
    token_files = get_token_files()
    accounts = []
    for path in token_files:
        name = os.path.basename(path)
        if name.startswith("token-") and name.endswith(".json"):
            email = name[len("token-"):-len(".json")]
            accounts.append(email)
    return {"accounts": accounts}

@app.post("/api/add-account")
async def add_account(req: Request):
    """Start the OAuth flow — returns a URL for the user to visit."""
    data = await req.json()
    email = data.get("email", "").strip().lower()
    token_path = os.path.join(os.path.dirname(__file__), f"../token-{email}.json")
    if os.path.exists(token_path):
        return {"success": True, "message": "Account already authenticated.", "already_done": True}
    try:
        redirect_uri = _get_redirect_uri()
        auth_url = get_authorization_url(redirect_uri, email=email)
        return {"success": True, "auth_url": auth_url}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/oauth/callback")
async def oauth_callback(request: Request):
    """Handle the OAuth redirect from Google."""
    code = request.query_params.get("code")
    state = request.query_params.get("state", "default")
    error = request.query_params.get("error")

    if error:
        return HTMLResponse(f"""
        <html><body style="font-family:sans-serif;padding:40px;text-align:center">
        <h2>❌ Authentication failed</h2><p>{error}</p>
        <script>window.close();</script>
        </body></html>""")

    if not code:
        return HTMLResponse("""
        <html><body style="font-family:sans-serif;padding:40px;text-align:center">
        <h2>❌ No authorization code received</h2>
        <script>window.close();</script>
        </body></html>""")

    redirect_uri = _get_redirect_uri()
    email = state if "@" in state else None
    if email:
        token_path = os.path.join(os.path.dirname(__file__), f"../token-{email}.json")
    else:
        token_path = os.path.join(os.path.dirname(__file__), "../token.json")

    try:
        creds = exchange_code(code, redirect_uri, state, token_path)
        # Start monitoring thread for this account
        t = threading.Thread(target=monitor_emails_for_token, args=(token_path,), daemon=True)
        t.start()
        return HTMLResponse(f"""
        <html><body style="font-family:sans-serif;padding:40px;text-align:center;background:#f0fdf4">
        <h2>✅ Account connected!</h2>
        <p><strong>{email or 'Your account'}</strong> has been authenticated successfully.</p>
        <p>You can close this tab and return to MailMinder.</p>
        <script>
          if (window.opener) {{
            window.opener.postMessage({{type:'oauth_success', email:'{email or ''}'}}, '*');
            setTimeout(() => window.close(), 1500);
          }}
        </script>
        </body></html>""")
    except Exception as e:
        print(f"[ERROR] OAuth callback failed: {e}")
        return HTMLResponse(f"""
        <html><body style="font-family:sans-serif;padding:40px;text-align:center;background:#fef2f2">
        <h2>❌ Authentication error</h2><p>{str(e)}</p>
        <p>Make sure your redirect URI is registered in Google Cloud Console.</p>
        <script>window.close();</script>
        </body></html>""")

@app.post("/api/remove-account")
async def remove_account(req: Request):
    data = await req.json()
    email = data.get("email", "").strip().lower()
    token_path = os.path.join(os.path.dirname(__file__), f"../token-{email}.json")
    try:
        if os.path.exists(token_path):
            os.remove(token_path)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def parse_time(dt_str):
    from dateutil.parser import parse
    from datetime import datetime
    try:
        dt = parse(dt_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return time_now()

def time_now():
    from datetime import datetime
    return datetime.now()

def monitor_emails_for_token(token_path):
    creds = authenticate(token_path)
    if not creds:
        print(f"[ERROR] Could not authenticate with token: {token_path}")
        return
    from googleapiclient.discovery import build
    service = build('gmail', 'v1', credentials=creds)
    profile = service.users().getProfile(userId='me').execute()
    account_email = profile.get('emailAddress')
    print(f"[DEBUG] Monitoring for account: {account_email}")
    processed_ids = set()
    allowed_mail_ids = [s.strip().lower() for s in settings.get("allowedMailIds", "").split(",") if s.strip()]
    if not allowed_mail_ids:
        import json
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                config = json.load(f)
                allowed_mail_ids = [s.strip().lower() for s in config.get("allowed_senders", [])]
    while is_running:
        try:
            # Read settings fresh on every scan so UI changes take effect
            check_interval = int(settings.get("checkInterval", 5)) * 60
            meeting_keywords = [kw.strip().lower() for kw in settings.get(
                "emailKeywords",
                "meeting, zoom, conference, appointment, masterclass, workshop, meet, gmeet, google meet"
            ).split(",") if kw.strip()]

            # Search subject OR body for any keyword (full-text, no subject: prefix)
            keyword_query = " OR ".join([f'"{kw}"' for kw in meeting_keywords[:12]])
            sender_filter = " OR ".join([f'from:{s}' for s in allowed_mail_ids]) if allowed_mail_ids else None
            if sender_filter:
                gmail_query = f'({sender_filter}) ({keyword_query}) newer_than:30d'
            else:
                gmail_query = f'({keyword_query}) newer_than:30d'
            print(f"[DEBUG] Gmail query: {gmail_query}")
            results = service.users().messages().list(userId='me', q=gmail_query, maxResults=50).execute()
            messages = results.get('messages', [])
            for msg in messages:
                if msg['id'] in processed_ids:
                    continue
                msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                sender = next((h['value'] for h in msg_data['payload']['headers'] if h['name'] == 'From'), None)
                subject = next((h['value'] for h in msg_data['payload']['headers'] if h['name'] == 'Subject'), None)
                print(f"[DEBUG] Checking email from: {sender} | Subject: {subject}")
                sender_email = sender.lower() if sender else ''
                if allowed_mail_ids and not any(mail_id in sender_email for mail_id in allowed_mail_ids):
                    processed_ids.add(msg['id'])
                    continue
                body = decode_body(msg_data['payload'])
                # Prepend subject so extraction can parse time/date from it too
                text_to_parse = f"Subject: {subject}\n\n{body}" if subject else body
                if contains_meeting(text_to_parse, meeting_keywords):
                    details = extract_meeting_details(text_to_parse)
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
                    from src.mail_processor import send_notification
                    send_notification(sender, details['title'], details['time'], details['link'])
                processed_ids.add(msg['id'])
            stats["emailsScanned"] += 1
            time.sleep(check_interval)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@app.get("/app.css")
def serve_css():
    return FileResponse(os.path.join(BASE_DIR, "app.css"))

@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(BASE_DIR, "app.js"))

@app.get("/")
def serve_frontend():
    return FileResponse(os.path.join(BASE_DIR, "app.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=5000, reload=False)
