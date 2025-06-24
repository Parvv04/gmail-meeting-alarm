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
from transformers import pipeline
import pytz 

# Load a local NLP model
ner_model = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

# Define timezone mappings to resolve ambiguity
TIMEZONE_MAP = {
    'IST': pytz.timezone('Asia/Kolkata'),  # India Standard Time
    'EST': pytz.timezone('America/New_York'),  # US Eastern Time
    'PST': pytz.timezone('America/Los_Angeles'),  # US Pacific Time
    'CST': pytz.timezone('America/Chicago'),  # Central Time
    'UTC': pytz.UTC,
    'GMT': pytz.UTC,
    'EDT': pytz.timezone('America/New_York'),
    'PDT': pytz.timezone('America/Los_Angeles'),
    'CDT': pytz.timezone('America/Chicago')  # Central Daylight Time
}

def extract_meeting_details_ai(email_body):
    """Use local NLP model to extract entities with improved processing"""
    try:
        entities = ner_model(email_body)
        print(f"[DEBUG] Raw NER entities: {entities}")
        
        # Extract and clean entity text
        date_texts = []
        time_texts = []
        person_texts = []
        
        for entity in entities:
            entity_text = entity['word'].strip()
            confidence = entity.get('score', 0)
            
            # Lower confidence threshold since standard NER models struggle with dates/times
            if confidence < 0.7:
                continue
                
            entity_group = entity['entity_group'].upper()
            
            if entity_group in ['DATE', 'TIME']:
                # Clean up subword tokens (remove ## prefixes)
                clean_text = entity_text.replace('##', '')
                
                if entity_group == 'DATE':
                    date_texts.append(clean_text)
                elif entity_group == 'TIME':
                    time_texts.append(clean_text)
            elif entity_group in ['PER', 'PERSON']:
                person_texts.append(entity_text.replace('##', ''))
        
        print(f"[DEBUG] Processed - Dates: {date_texts}, Times: {time_texts}")
        
        # Try to combine date and time
        meeting_time = None
        if date_texts and time_texts:
            try:
                # Take the first/best date and time
                date_str = date_texts[0]
                time_str = time_texts[0]
                
                # Try different combinations
                for date_part in date_texts:
                    for time_part in time_texts:
                        try:
                            combined = f"{date_part} {time_part}"
                            meeting_time = parse(combined, fuzzy=True)
                            print(f"[DEBUG] Successfully parsed: {combined} -> {meeting_time}")
                            break
                        except:
                            continue
                    if meeting_time:
                        break
                        
            except Exception as e:
                print(f"[DEBUG] AI date/time parsing error: {e}")
        
        return {
            'time': meeting_time,
            'date_entities': date_texts,
            'time_entities': time_texts,
            'person_entities': person_texts,
            'all_entities': entities
        }
        
    except Exception as e:
        print(f"[DEBUG] NER model error: {e}")
        return {
            'time': None,
            'date_entities': [],
            'time_entities': [],
            'person_entities': [],
            'all_entities': []
        }

def decode_body(payload):
    """Decode email body from base64"""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                return base64.urlsafe_b64decode(data).decode()
    return ""

def contains_meeting(email_body, keywords=None):
    """Improved meeting detection with better rule-based patterns"""
    
    # First try AI-based detection (though it's not working well for dates/times)
    ai_result = extract_meeting_details_ai(email_body)
    has_ai_datetime = ai_result['time'] is not None
    has_date_entities = len(ai_result['date_entities']) > 0
    has_time_entities = len(ai_result['time_entities']) > 0
    
    # Enhanced rule-based meeting word detection
    meeting_words = [
        r'\bmeeting\b', r'\bcall\b', r'\bappointment\b', r'\bconference\b', r'\bwebinar\b',
        r'\bsession\b', r'\bdiscussion\b', r'\bsync\b', r'\bcatch up\b', r'\bstandup\b',
        r'\breview\b', r'\binterview\b', r'\bzoom\b', r'\bteams\b', r'\bgoogle meet\b', 
        r'\bwebex\b', r'\bschedule\b', r'\binvite\b', r'\bmeet\b', r'\bmasterclass\b',
        r'\bworkshop\b', r'\btraining\b', r'\bevent\b', r'\bclass\b', r'\bseminar\b'
    ]
    
    body_lower = email_body.lower()
    has_meeting_word = any(re.search(word, body_lower) for word in meeting_words)
    
    # Enhanced time/date pattern detection
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
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b',
        r'\b\d{4}-\d{1,2}-\d{1,2}\b',
        # Special pattern for "May 20th" format
        r'\b(?:May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?\b'
    ]
    
    has_time_pattern = any(re.search(pattern, email_body, re.IGNORECASE) for pattern in time_patterns)
    has_date_pattern = any(re.search(pattern, email_body, re.IGNORECASE) for pattern in date_patterns)
    
    # Debug logging
    print(f"[DEBUG] Meeting detection:")
    print(f"  - Email body snippet: {email_body[:200]}...")
    print(f"  - AI datetime extracted: {has_ai_datetime}")
    print(f"  - AI date entities: {has_date_entities}")
    print(f"  - AI time entities: {has_time_entities}")
    print(f"  - Has meeting words: {has_meeting_word}")
    print(f"  - Has time patterns: {has_time_pattern}")
    print(f"  - Has date patterns: {has_date_pattern}")
    
    # Check for specific date mentions
    date_matches = []
    for pattern in date_patterns:
        matches = re.findall(pattern, email_body, re.IGNORECASE)
        date_matches.extend(matches)
    
    time_matches = []
    for pattern in time_patterns:
        matches = re.findall(pattern, email_body, re.IGNORECASE)
        time_matches.extend(matches)
    
    print(f"  - Date matches found: {date_matches}")
    print(f"  - Time matches found: {time_matches}")
    
    # Decision logic: it's a meeting if we have meeting context AND time/date info
    is_meeting = (has_meeting_word and (has_time_pattern or has_date_pattern)) or \
                 has_ai_datetime or \
                 (has_meeting_word and (has_date_entities or has_time_entities))
    
    print(f"[DEBUG] Final decision: is_meeting = {is_meeting}")
    return is_meeting

def extract_meeting_link(email_body):
    """Extract meeting links from email body"""
    patterns = [
        r'(https:\/\/zoom.us\/j\/\d+[^\s]*)',
        r'(https:\/\/teams.microsoft.com\/l\/meetup-join\/[^\s]+)',
        r'(https:\/\/meet.google.com\/[a-z]{3}-[a-z]{4}-[a-z]{3})',
        r'(https:\/\/[^\s]*webex.com[^\s]*)',
        # Add more generic meeting link patterns
        r'(https:\/\/[^\s]*meeting[^\s]*)',
        r'(https:\/\/[^\s]*join[^\s]*)',
        r'(https:\/\/[^\s]*event[^\s]*)'
    ]
    for pattern in patterns:
        match = re.search(pattern, email_body, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

def extract_meeting_details(email_body):
    """
    Enhanced meeting details extraction with better regex patterns and timezone handling
    """
    print(f"[DEBUG] Extracting meeting details from: {email_body[:200]}...")
    
    # First, try AI-based extraction
    ai_result = extract_meeting_details_ai(email_body)
    
    # If AI found a complete datetime, use it
    if ai_result['time']:
        print(f"[DEBUG] Using AI-extracted time: {ai_result['time']}")
        return {
            'title': extract_meeting_title(email_body),
            'time': ai_result['time'],
            'link': extract_meeting_link(email_body)
        }
    
    # Rule-based extraction with improved patterns
    body_lower = email_body.lower()
    
    # 1. Title Extraction
    title = extract_meeting_title(email_body)

    # 2. Timezone Support
    tz_match = re.search(r'\b(EST|PST|CST|IST|UTC|EDT|PDT|CDT|GMT)\b', email_body, re.IGNORECASE)
    timezone_str = tz_match.group(1).upper() if tz_match else None

    # 3. Enhanced patterns for date/time extraction
    patterns_to_try = [
        # Pattern 0: "this Thursday, 12th June 2025 from 3:00 pm"
        r'(?:this|next)?\s*(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|July|August|September|October|November|December)[a-z]*\s*(\d{4})?\s*(?:from|at)?\s*(\d{1,2}:\d{2}|\d{1,2})\s*(AM|PM|am|pm)?',
        # Pattern 1: "May 20th" or "May 20, 2024" format, now stricter for time
        r'(?:on\s+)?(?:May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(?:(\d{4}))?\s*(?:at|time[:]?|from)?\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))?',
        
        # Pattern 2: "on [date] at [time]"
        r'(?:on\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(?:\d{4})?)\s*(?:at|@)\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)',
        
        # Pattern 3: "[date] [time]" format
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*(?:at\s*)?(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?)',
        
        # Pattern 4: "Date: [date]" followed by "Time: [time]" (multiline)
        r'Date:\s*([^\n]+)\s*.*?Time:\s*([^\n]+)',
        
        # Pattern 5: Look for month day combination
        r'(?:on\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\s*(?:,\s*(\d{4}))?\s*(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?)?'
    ]
    
    for i, pattern in enumerate(patterns_to_try):
        match = re.search(pattern, email_body, re.IGNORECASE | re.DOTALL)
        if match:
            try:
                groups = match.groups()
                print(f"[DEBUG] Pattern {i+1} matched: {groups}")
                if i == 0:  # Our new pattern
                    weekday, day, month, year, time_part, ampm = groups
                    year = year if year else str(datetime.now().year)
                    time_str = f"{time_part} {ampm}".strip() if ampm else time_part
                    datetime_str = f"{month} {day}, {year} {time_str}"
                elif i == 1:  # May 20th format
                    day = groups[0]
                    year = groups[1] if groups[1] else str(datetime.now().year)
                    time_part = groups[2] if groups[2] else "09:00 AM"
                    
                    # Extract month from the original match
                    month_match = re.search(r'(May|June|July|August|September|October|November|December)', email_body, re.IGNORECASE)
                    month = month_match.group(1) if month_match else "May"
                    
                    datetime_str = f"{month} {day}, {year} {time_part}"
                    
                elif i == 4:  # Month day format
                    day = groups[0]
                    year = groups[1] if groups[1] else str(datetime.now().year)
                    time_part = groups[2] if groups[2] else "09:00 AM"
                    
                    # Extract month from the original match
                    month_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', email_body, re.IGNORECASE)
                    month = month_match.group(0) if month_match else "May"
                    
                    datetime_str = f"{month} {day}, {year} {time_part}"
                    
                else:
                    date_part = groups[0]
                    time_part = groups[1] if len(groups) > 1 and groups[1] else "09:00 AM"
                    
                    # Clean up date part
                    date_part = re.sub(r'\[.*?\]', '', date_part).strip()
                    date_part = re.sub(r'(\d{1,2})(st|nd|rd|th)', r'\1', date_part)
                    
                    datetime_str = f"{date_part} {time_part}"
                
                print(f"[DEBUG] Trying to parse: {datetime_str}")
                
                # Parse datetime with timezone handling
                if timezone_str and timezone_str in TIMEZONE_MAP:
                    # Parse without timezone first, then localize
                    meeting_time = parse(datetime_str, fuzzy=True)
                    # Convert to timezone-aware datetime
                    tz = TIMEZONE_MAP[timezone_str]
                    if meeting_time.tzinfo is None:
                        meeting_time = tz.localize(meeting_time)
                    print(f"[DEBUG] Applied timezone {timezone_str}: {meeting_time}")
                else:
                    # Parse normally (will still work but may show warning for unknown timezones)
                    meeting_time = parse(datetime_str, fuzzy=True)
                
                print(f"[DEBUG] Extracted time (pattern {i+1}): {meeting_time}")
                return {
                    'title': title,
                    'time': meeting_time,
                    'link': extract_meeting_link(email_body)
                }
                
            except Exception as e:
                print(f"[DEBUG] Pattern {i+1} parse error: {e}")
                continue

    print(f"[DEBUG] No time extracted from email body")
    return {
        'title': title,
        'time': None,
        'link': extract_meeting_link(email_body)
    }

def extract_meeting_title(email_body):
    """Extract meeting title from email body with better patterns"""
    # Try different title patterns
    title_patterns = [
        r'(?:subject|title):\s*([^\n]+)',
        r'^([^\n]*(?:masterclass|workshop|training|meeting|event|class|seminar)[^\n]*)',
        r'"([^"]*(?:masterclass|workshop|training|meeting|event|class|seminar)[^"]*)"',
        r'(?:join us for|attend|register for)\s+(?:the\s+)?([^\n]+?)(?:\s+on|\s+at|$)',
        r'(?:meeting|event)\s*(?:about|for|on|:|title)\s*["\']?(.*?)(?=["\']?\s*(?:on|at|for|date|time)|[.!?]|$)',
    ]
    
    for pattern in title_patterns:
        match = re.search(pattern, email_body, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            if len(title) > 3 and len(title) < 150:  # Reasonable title length
                # Clean up the title
                title = re.sub(r'\s+', ' ', title)  # Replace multiple spaces with single space
                title = title.strip('.,!?')  # Remove trailing punctuation
                return title
    
    return "Scheduled Meeting"

def send_notification(sender, meeting_title, start_time, meeting_link=None):
    """Show a desktop notification on Linux (tkinter), MacOS (osascript), or Windows (ctypes)."""
    time_str = start_time.strftime("%I:%M %p") if start_time else "Time not specified"
    date_str = start_time.strftime("%A, %d %B %Y") if start_time else "Date not specified"
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
    message = f"📢 {meeting_title}\n👤 From: {sender}\n⏰ Time: {time_str}\n📅 Date: {date_str}\n🌐 Platform: {platform_name}"
    sys_platform = platform.system()
    if sys_platform == 'Windows':
        # Windows native alert
        response = ctypes.windll.user32.MessageBoxW(
            0,
            f"{message}\n\n{'Click OK to join' if meeting_link else ''}",
            "MEETING ALERT",
            0x40 | 0x1  # Info icon + OK/Cancel buttons
        )
        if response == 1 and meeting_link:  # IDOK = 1
            webbrowser.open(meeting_link)
    elif sys_platform == 'Darwin':  # MacOS
        os.system(f'osascript -e \'display notification "{message}" with title "MEETING ALERT"\'')
        if meeting_link:
            webbrowser.open(meeting_link)
    else:  # Linux/other - use tkinter popup
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