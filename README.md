# Gmail Meeting Alarm

Automatically sends notification for your upcoming meetings by scanning your Gmail notifications. Never miss an important meeting again!

---

# Features ✨

- 🔔 Automatic meeting detection from Gmail notifications
- 🔒 Secure OAuth 2.0 authentication
- 🧩 Easy setup with Google API
- 💻 Cross-platform support (Windows, macOS, Linux)

---

# Prerequisites 📋

- Python 3.8+
- Google account 
- Active internet connection

---

# Installation 🚀

Clone the repository:
~~~
git clone https://github.com/Parvv04/gmail-meeting-alarm.git
cd gmail-meeting-alarm
~~~

Install required packages:
~~~
pip install -r requirements.txt
~~~

Google API Setup 🔑
- Go to the Google Cloud Console
- Create a new project
- Enable Gmail API:
     - Navigate to "APIs & Services" > "Library"
     - Search for "Gmail API" and enable
- Configure OAuth consent screen:
     - Select "External" user type
     - Add your email under "Test users"
- Create credentials:
     - Go to "Credentials" > "Create Credentials" > "OAuth client ID"
     - Application type: Desktop app
     - Name: Gmail Meeting Alarm
- Download credentials:
     - Click the download icon next to your new OAuth client
     - Rename the downloaded file to credentials.json
     - Place it in the project directory

First-Time Authentication 🔓
- Run the application:
~~~
bash
python main.py
~~~

On first run:
- A browser window will open asking you to log in to your Google account
- Grant permission for the app to access your Gmail and Calendar
- After authentication, a token.json file will be created in the project directory

---

# Usage 🖥️

Simply run the application:
~~~
bash
python main.py
~~~

The application will:
- Continuously monitor your Gmail for new invitations
- Show desktop notifications
- Run silently in the background

To run in the background:
- Windows: Create a shortcut in Startup folder
- macOS: Use launchd
- Linux: Add to startup applications

---

# Configuration ⚙️

You can modify these parameters in main.py:

- How often to check for new emails (seconds)
CHECK_INTERVAL = 300  # 5 minutes

- Meeting keywords to look for in email subjects
MEETING_KEYWORDS = ['invitation', 'meeting', 'event']

---

# No notifications:

Check your system's notification settings

Ensure emails contain the keywords mentioned in the main.py

---

# Security 🔒
- Your credentials are stored locally and never transmitted
- The app only requests minimum required permissions (read-only for Gmail, read-only for Calendar)
- You can revoke access anytime at Google Account Security

---

# Contributing 🤝
Contributions are welcome! Please open an issue or submit a pull request.

---

# License 📄
This project is licensed under the MIT License - see the LICENSE file for details.

