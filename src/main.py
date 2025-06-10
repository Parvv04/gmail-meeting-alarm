import time
import json
from googleapiclient.discovery import build
from auth import authenticate
from mail_processor import (
    decode_body, 
    contains_meeting, 
    send_notification,
    extract_meeting_details
)

# Load configuration
with open('src/config.json') as config_file:
    config = json.load(config_file)

def monitor_emails():
    creds = authenticate()
    service = build('gmail', 'v1', credentials=creds)
    processed_ids = set()

    while True:
        try:
            query = " OR ".join([f'from:{sender}' for sender in config['allowed_senders']])
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
                
                if contains_meeting(body, config['meeting_keywords']):
                    details = extract_meeting_details(body)
                    send_notification(
                        sender=sender,
                        meeting_title=details['title'],
                        start_time=details['time'],
                        meeting_link=details['link']
                    )
                
                processed_ids.add(msg['id'])
            
            time.sleep(config['check_interval'])
        
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    monitor_emails()