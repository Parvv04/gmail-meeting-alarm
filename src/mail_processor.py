import base64
import re
from dateutil.parser import parse
from datetime import datetime, timedelta
import platform
import os
import webbrowser

TIMEZONE_MAP = {
    'IST': 'Asia/Kolkata',
    'EST': 'America/New_York',
    'PST': 'America/Los_Angeles',
    'CST': 'America/Chicago',
    'UTC': 'UTC',
    'GMT': 'UTC',
    'EDT': 'America/New_York',
    'PDT': 'America/Los_Angeles',
    'CDT': 'America/Chicago'
}

def decode_body(payload):
    """Decode email body from base64"""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    body_data = payload.get('body', {}).get('data', '')
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
    return ""

def contains_meeting(email_body, keywords=None):
    """Meeting detection with rule-based patterns"""
    meeting_words = [
        r'\bmeeting\b', r'\bcall\b', r'\bappointment\b', r'\bconference\b', r'\bwebinar\b',
        r'\bsession\b', r'\bdiscussion\b', r'\bsync\b', r'\bcatch up\b', r'\bstandup\b',
        r'\breview\b', r'\binterview\b', r'\bzoom\b', r'\bteams\b', r'\bgoogle meet\b',
        r'\bwebex\b', r'\bschedule\b', r'\binvite\b', r'\bmeet\b', r'\bmasterclass\b',
        r'\bworkshop\b', r'\btraining\b', r'\bevent\b', r'\bclass\b', r'\bseminar\b'
    ]

    if keywords:
        for kw in keywords:
            meeting_words.append(r'\b' + re.escape(kw.strip()) + r'\b')

    body_lower = email_body.lower()
    has_meeting_word = any(re.search(word, body_lower) for word in meeting_words)

    time_patterns = [
        r'\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)\b',
        r'\b\d{1,2}\s*(?:AM|PM|am|pm)\b',
        r'\bat\s+\d{1,2}(?::\d{2})?\b',
        r'\b(?:today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
        r'\b\d{1,2}(?::\d{2})?\s*(?:IST|EST|PST|CST|UTC|GMT|EDT|PDT|CDT)\b'
    ]

    date_patterns = [
        r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\b',
        r'\b\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b',
        r'\b\d{4}-\d{1,2}-\d{1,2}\b',
        r'\b(?:May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\b'
    ]

    has_time_pattern = any(re.search(pattern, email_body, re.IGNORECASE) for pattern in time_patterns)
    has_date_pattern = any(re.search(pattern, email_body, re.IGNORECASE) for pattern in date_patterns)

    # Strong platform signals — time alone is enough with these
    platform_words = [r'\bgmeet\b', r'\bgoogle meet\b', r'\bzoom\b', r'\bwebex\b',
                      r'\bmicrosoft teams\b', r'\bmeet\.google\b', r'\bzoom\.us\b']
    has_strong_platform = any(re.search(p, body_lower) for p in platform_words)

    if has_strong_platform and has_time_pattern:
        is_meeting = True
    else:
        # General case: need meeting word + time + date (all three to avoid newsletters)
        is_meeting = has_meeting_word and has_time_pattern and has_date_pattern

    print(f"[DEBUG] Meeting detection: has_meeting_word={has_meeting_word}, has_time={has_time_pattern}, has_date={has_date_pattern}, has_platform={has_strong_platform}, result={is_meeting}")
    return is_meeting

def extract_meeting_link(email_body):
    """Extract meeting links from email body"""
    patterns = [
        r'(https:\/\/zoom\.us\/j\/\d+[^\s]*)',
        r'(https:\/\/teams\.microsoft\.com\/l\/meetup-join\/[^\s]+)',
        r'(https:\/\/meet\.google\.com\/[a-z]{3}-[a-z]{4}-[a-z]{3})',
        r'(https:\/\/[^\s]*webex\.com[^\s]*)',
        r'(https:\/\/[^\s]*meeting[^\s]*)',
        r'(https:\/\/[^\s]*join[^\s]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

def extract_meeting_title(email_body):
    """Extract meeting title from email body"""
    title_patterns = [
        r'(?:subject|title):\s*([^\n]+)',
        r'^([^\n]*(?:masterclass|workshop|training|meeting|event|class|seminar)[^\n]*)',
        r'"([^"]*(?:masterclass|workshop|training|meeting|event|class|seminar)[^"]*)"',
        r'(?:join us for|attend|register for)\s+(?:the\s+)?([^\n]+?)(?:\s+on|\s+at|$)',
    ]

    for pattern in title_patterns:
        match = re.search(pattern, email_body, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            if 3 < len(title) < 150:
                title = re.sub(r'\s+', ' ', title)
                title = title.strip('.,!?')
                return title

    return "Scheduled Meeting"

def extract_meeting_details(email_body):
    """Extract meeting details using regex patterns with fuzzy fallback."""
    print(f"[DEBUG] Extracting meeting details from: {email_body[:200]}...")

    title = extract_meeting_title(email_body)
    link = extract_meeting_link(email_body)

    # Time value: \d{1,2}(:\d{2})?\s*(AM|PM) — handles both "5pm" and "5:00pm"
    TIME_RE = r'\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)'
    DATE_RE = r'(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{1,2}-\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s*(?:\d{4})?|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?:\s+\d{4})?)'

    patterns_to_try = [
        # Pattern 0: "at 5pm 11-06-2025" or "5pm 11-06-2025"
        (rf'(?:at\s+)?({TIME_RE})\s+({DATE_RE})', lambda g: f"{g[0]} {g[1]}"),
        # Pattern 1: "11-06-2025 at 5pm" or "11-06-2025 5pm"
        (rf'({DATE_RE})\s+(?:at\s+)?({TIME_RE})', lambda g: f"{g[0]} {g[1]}"),
        # Pattern 2: "Date: ... Time: ..." (multiline)
        (r'Date:\s*([^\n]+)\n.*?Time:\s*([^\n]+)', lambda g: f"{g[0]} {g[1]}"),
        # Pattern 3: weekday + ordinal month date + time
        (r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|July|August|September|October|November|December)[a-z]*\s*(\d{4})?\s*(?:at|from)?\s*(' + TIME_RE + r')',
         lambda g: f"{g[1]} {g[0]}, {g[2] or datetime.now().year} {g[3]}"),
    ]

    for i, (pattern, builder) in enumerate(patterns_to_try):
        match = re.search(pattern, email_body, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                groups = match.groups()
                datetime_str = builder(groups)
                print(f"[DEBUG] Pattern {i+1} matched → '{datetime_str}'")
                meeting_time = parse(datetime_str, fuzzy=True, dayfirst=True)
                print(f"[DEBUG] Extracted time: {meeting_time}")
                return {'title': title, 'time': meeting_time, 'link': link}
            except Exception as e:
                print(f"[DEBUG] Pattern {i+1} parse error: {e}")
                continue

    # Fuzzy fallback: try parsing each line that contains both a time and a date hint
    for line in email_body.splitlines():
        line = line.strip()
        if not line:
            continue
        has_time = re.search(TIME_RE, line, re.IGNORECASE)
        has_date = re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', line, re.IGNORECASE)
        if has_time and has_date:
            try:
                meeting_time = parse(line, fuzzy=True, dayfirst=True)
                print(f"[DEBUG] Fuzzy line parse: '{line}' → {meeting_time}")
                return {'title': title, 'time': meeting_time, 'link': link}
            except Exception:
                continue

    # Last resort: try fuzzy parsing the whole text
    try:
        meeting_time = parse(email_body[:500], fuzzy=True, dayfirst=True)
        print(f"[DEBUG] Fuzzy full-text parse → {meeting_time}")
        return {'title': title, 'time': meeting_time, 'link': link}
    except Exception:
        pass

    print(f"[DEBUG] No time extracted")
    return {'title': title, 'time': None, 'link': link}

def send_notification(sender, meeting_title, start_time, meeting_link=None):
    """Log notification (desktop notifications not available in web environment)"""
    time_str = start_time.strftime("%I:%M %p") if start_time else "Time not specified"
    date_str = start_time.strftime("%A, %d %B %Y") if start_time else "Date not specified"
    print(f"[NOTIFICATION] Meeting Alert!")
    print(f"  Title: {meeting_title}")
    print(f"  From: {sender}")
    print(f"  Time: {time_str} on {date_str}")
    if meeting_link:
        print(f"  Link: {meeting_link}")
