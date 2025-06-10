import time
from googleapiclient.discovery import build
from auth import authenticate
from mail_processor import decode_body, contains_meeting, send_notification, extract_meeting_details

def get_allowed_senders():
    """Prompt user to input allowed sender email addresses"""
    print("\n" + "="*50)
    print("Gmail Meeting Alarm Setup")
    print("="*50)
    print("Enter the email addresses you want to monitor for meetings")
    print("(Separate multiple addresses with commas)")
    
    while True:
        input_str = input("\nAllowed senders: ").strip()
        if input_str:
            addresses = [addr.strip() for addr in input_str.split(",")]
            if all("@" in addr for addr in addresses):
                return addresses
            print("⚠️ Please enter valid email addresses (must contain '@')")
        else:
            print("⚠️ You must specify at least one email address")

def monitor_emails():
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    processed_ids = set()
    
    # Get user input for configuration
    allowed_senders = get_allowed_senders()
    check_interval = int(input("\nCheck interval (minutes): ") or 5) * 60
    
    # Get meeting keywords
    keyword_input = input("\nMeeting keywords to look for (comma separated): ")
    meeting_keywords = [kw.strip().lower() for kw in keyword_input.split(",")] if keyword_input else ["meeting", "event","call", "appointment", "schedule", "zoom", "teams","AM", "PM", "meeting link", "meeting id", "join meeting", "video call", "conference call"]

    print("\n" + "="*50)
    print("Starting monitoring...")
    print(f"• Watching emails from: {', '.join(allowed_senders)}")
    print(f"• Checking every {check_interval//60} minutes")
    print(f"• Alert keywords: {', '.join(meeting_keywords)}")
    print("="*50 + "\n")

    while True:
        try:
            query = " OR ".join([f'from:{sender}' for sender in allowed_senders])
            results = service.users().messages().list(
                userId='me',
                q=f'{query} is:unread'
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
                
                sender = next(h['value'] for h in msg_data['payload']['headers'] 
                             if h['name'] == 'From')
                body = decode_body(msg_data['payload'])
                
                if contains_meeting(body, meeting_keywords):
                    details = extract_meeting_details(body)
                    send_notification(
                        sender=sender,
                        meeting_title=details['title'],
                        start_time=details['time'],
                        meeting_link=details['link']
                    )
                
                processed_ids.add(msg['id'])
            
            time.sleep(check_interval)
        
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    monitor_emails()