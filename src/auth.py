import os
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")

# In-memory store for pending OAuth flows (keyed by state/email)
_pending_flows = {}

def get_token_files():
    base = os.path.dirname(__file__)
    parent = os.path.join(base, "..")
    files = []
    for f in os.listdir(parent):
        if f.startswith("token-") and f.endswith(".json"):
            files.append(os.path.join(parent, f))
    return files

def get_authorization_url(redirect_uri, email=None):
    """Generate an OAuth authorization URL and persist the flow for callback use."""
    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    state = email or "default"
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        state=state,
        login_hint=email or ''
    )
    # Persist the flow so we can retrieve code_verifier during callback
    _pending_flows[state] = flow
    return auth_url

def exchange_code(code, redirect_uri, state, token_path):
    """Exchange an auth code for credentials using the stored flow."""
    flow = _pending_flows.pop(state, None)
    if flow is None:
        # Fallback: create a fresh flow (PKCE won't match, but worth trying)
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_PATH,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
    else:
        # Update redirect_uri in case it changed
        flow.redirect_uri = redirect_uri

    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(token_path, 'w') as f:
        f.write(creds.to_json())
    return creds

def authenticate(token_path):
    """Load and refresh credentials from a saved token file."""
    if not os.path.exists(token_path):
        return None
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
        else:
            return None
    return creds
