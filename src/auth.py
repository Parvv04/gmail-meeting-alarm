import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

def authenticate(token_path=None, email=None):
    creds = None
    # Determine token path
    if token_path is None:
        if email:
            base = os.path.dirname(__file__)
            token_path = os.path.join(base, "..", f"token-{email}.json")
        else:
            token_path = TOKEN_PATH
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds


def get_token_files():
    base = os.path.dirname(__file__)
    files = []
    for f in os.listdir(os.path.join(base, "..")):
        if f.startswith("token-") and f.endswith(".json"):
            files.append(os.path.join(base, "..", f))
    return files