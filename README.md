# Gmail Meeting Alarm

Automatically sends notification for your upcoming meetings by scanning your Gmail notifications. Never miss an important meeting again!

---

# Features ✨

- 🔔 Automatic meeting detection from Gmail notifications
- 🔒 Secure OAuth 2.0 authentication
- 🧩 Easy setup with Google API
- 💻 Cross-platform desktop app (Windows, macOS, Linux) using Electron + FastAPI
- 📨 Sender filtering (allows only mail IDs that have been input)
- 🖥️ Desktop notifications (native)
- 🕑 Customizable scan and alert intervals
- ✅ Click detected meetings to open the original email in Gmail (opens in your default browser)

---

# Prerequisites 📋

- Python 3.8+
- Node.js & npm (for Electron)
- Google account
- At least one web browser installed (required for opening Gmail links)
- Active internet connection

---

# Installation 🚀

Clone the repository:
~~~
git clone https://github.com/Parvv04/gmail-meeting-alarm.git
cd gmail-meeting-alarm
~~~

Install required Python packages:
~~~
pip install -r requirements.txt
~~~

Install Electron dependencies:
~~~
npm install
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
- Start the backend:
~~~
python3 src/main.py
~~~
- On first run, a browser window will open for Google login and permissions.
- After authentication, a token.json file will be created in the project directory.

---

# Usage 🖥️

1. **Start the backend (FastAPI):**
~~~
python3 src/main.py
~~~
2. **Start the Electron desktop app:**
~~~
npm run electron
~~~
3. Use the UI to:
   - Start/stop monitoring
   - Set allowed mail IDs, scan interval, and alert time
   - View detected meetings and logs
   - Click "View Email" to open the original Gmail message in your browser
   - Click "Join Meeting" to open the meeting link

**Note:**
- You must have a web browser installed for "View Email" to work. Electron will use your system's default browser.
- On Linux, ensure `xdg-utils` is installed (usually by default) and at least one browser (e.g., Firefox, Chromium).

---

# Configuration ⚙️

You can modify these parameters in the UI or in `src/config.json`:
- Allowed sender email addresses
- Scan interval (minutes)
- Alert before meeting (minutes)
- Meeting keywords

---

# Troubleshooting

- **No notifications?**
  - Check your system's notification settings.
  - Ensure emails contain the keywords set in the UI.
- **Links not opening?**
  - Make sure you have a browser installed and set as default.
  - On Linux, install `xdg-utils` and a browser (e.g., `sudo apt install firefox`).
- **Backend not reachable?**
  - Make sure `python3 src/main.py` is running and accessible at `http://127.0.0.1:8000`.

---

# Security 🔒
- Your credentials are stored locally and never transmitted
- The app only requests minimum required permissions (read-only for Gmail)
- You can revoke access anytime at Google Account Security

---

# Contributing 🤝
Contributions are welcome! Please open an issue or submit a pull request.

---

# License 📄
This project is licensed under the MIT License - see the LICENSE file for details.

