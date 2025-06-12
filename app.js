// Gmail Meeting Alarm JS
// (All JavaScript code from the <script> tag in your HTML goes here)

// Application State
let isSystemRunning = false;
let checkIntervalId = null;
let uiPollIntervalId = null;
let detectedMeetings = [];
let allowedMailIds = [];
let stats = {
    totalMeetings: 0,
    upcomingMeetings: 0,
    emailsScanned: 0,
    successRate: 0
};
let currentMeetingLink = null;

document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    updateStats();
    addLog('info', 'Application loaded successfully');
});

function toggleSystem() {
    if (isSystemRunning) {
        stopSystem();
    } else {
        startSystem();
    }
}

async function startSystem() {
    // Clear previous meetings and logs
    detectedMeetings = [];
    updateMeetingsDisplay();
    clearLogs();
    isSystemRunning = true;
    const interval = parseInt(document.getElementById('checkInterval').value) * 60000;
    document.getElementById('startBtn').innerHTML = '<span>⏸️</span> Stop Monitoring';
    document.getElementById('startBtn').classList.add('btn-danger');
    document.getElementById('systemStatus').classList.add('active');
    // Backend scan interval
    checkIntervalId = setInterval(checkEmails, interval);
    // UI poll interval (every 15s)
    if (uiPollIntervalId) clearInterval(uiPollIntervalId);
    uiPollIntervalId = setInterval(checkEmails, 15000);
    addLog('success', `System started - checking every ${interval/60000} minutes`);
    setTimeout(checkEmails, 2000);
    saveSettings();
    // Tell backend to start monitoring
    try {
       await fetch('http://127.0.0.1:8000/api/start', { method: 'POST' });
        addLog('info', 'Backend monitoring started');
    } catch (e) {
        addLog('error', 'Failed to start backend monitoring: ' + e.message);
    }
}

async function stopSystem() {
    isSystemRunning = false;
    if (checkIntervalId) {
        clearInterval(checkIntervalId);
        checkIntervalId = null;
    }
    if (uiPollIntervalId) {
        clearInterval(uiPollIntervalId);
        uiPollIntervalId = null;
    }
    document.getElementById('startBtn').innerHTML = '<span>▶️</span> Start Monitoring';
    document.getElementById('startBtn').classList.remove('btn-danger');
    document.getElementById('systemStatus').classList.remove('active');
    addLog('warning', 'System stopped');
    saveSettings();
    // Tell backend to stop monitoring
    try {
        await fetch('http://127.0.0.1:8000/api/stop', { method: 'POST' });
        addLog('info', 'Backend monitoring stopped');
    } catch (e) {
        addLog('error', 'Failed to stop backend monitoring: ' + e.message);
    }
}

function showMeetingAlert(meeting) {
    const notification = document.getElementById('notification');
    const content = document.getElementById('notificationContent');
    const joinBtn = document.getElementById('joinBtn');
    const timeStr = meeting.time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
    const dateStr = meeting.time.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    content.innerHTML = `
        <div style="margin-bottom: 10px;">
            <strong>📢 ${meeting.title}</strong>
        </div>
        <div style="color: #4a5568; line-height: 1.6;">
            👤 From: ${meeting.sender}<br>
            ⏰ Time: ${timeStr}<br>
            📅 Date: ${dateStr}<br>
            🌐 Platform: ${meeting.platform}
        </div>
    `;
    if (meeting.link) {
        joinBtn.style.display = 'inline-flex';
        currentMeetingLink = meeting.link;
    } else {
        joinBtn.style.display = 'none';
    }
    notification.classList.add('show');
    setTimeout(() => { hideNotification(); }, 10000);
    try {
        const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmMcAjaJ0fDVfC0EI3O/7+KTQQ0PVq7n4a5ZFgxEls7wm3cLQQ0PVq7n4a5ZFgxEls7wm3c=');
        audio.play().catch(() => {});
    } catch (e) {}
    addLog('success', `Meeting alert shown: ${meeting.title}`);
}

function hideNotification() {
    document.getElementById('notification').classList.remove('show');
    currentMeetingLink = null;
}

function joinMeeting() {
    if (currentMeetingLink) {
        window.open(currentMeetingLink, '_blank');
        addLog('info', 'Opened meeting link');
        hideNotification();
    }
}

function openGmailMessage(messageId) {
    if (!messageId) return;
    const url = `https://mail.google.com/mail/u/0/#inbox/${messageId}`;
    addLog('debug', 'Attempting to open Gmail message: ' + url);
    if (window.electronAPI && typeof window.electronAPI.openExternal === 'function') {
        window.electronAPI.openExternal(url).then(() => {
            addLog('info', 'Gmail message opened via Electron shell.');
        }).catch((err) => {
            addLog('error', 'Electron shell.openExternal failed: ' + err);
        });
    } else {
        addLog('error', 'Electron shell.openExternal is not available. Cannot open Gmail message.');
    }
}

function updateMeetingsDisplay() {
    const container = document.getElementById('meetingsContainer');
    if (detectedMeetings.length === 0) {
        container.innerHTML = `
            <p style="text-align: center; color: #a0aec0; padding: 20px;">
                No meetings detected yet. Start the system to begin scanning your emails.
            </p>
        `;
        return;
    }
    const sortedMeetings = [...detectedMeetings].sort((a, b) => {
        if (!a.time && !b.time) return 0;
        if (!a.time) return 1;
        if (!b.time) return -1;
        if (a.time instanceof Date && b.time instanceof Date) return a.time - b.time;
        return 0;
    });
    container.innerHTML = sortedMeetings.map(meeting => {
        let timeStr = 'Not specified';
        let isUpcoming = false;
        if (meeting.time instanceof Date && !isNaN(meeting.time)) {
            timeStr = meeting.time.toLocaleString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
            isUpcoming = meeting.time > new Date();
        }
        const statusColor = isUpcoming ? '#10b981' : '#a0aec0';
        return `
            <div class="meeting-card" style="border-left-color: ${statusColor}">
                <div class="meeting-title">${meeting.title}</div>
                <div class="meeting-details">
                    <div class="meeting-detail">
                        <span>⏰</span> ${timeStr}
                    </div>
                    <div class="meeting-detail">
                        <span>👤</span> ${meeting.sender || 'Unknown'}
                    </div>
                    <div class="meeting-detail">
                        <span>🌐</span> ${meeting.platform || 'Unknown'}
                    </div>
                    <div class="meeting-detail">
                        <span style="color: ${statusColor}">●</span> 
                        ${isUpcoming ? 'Upcoming' : 'Past'}
                    </div>
                </div>
                <div style="margin-top: 10px; display: flex; gap: 10px;">
                    ${meeting.link ? `
                        <button class="btn" onclick="window.open('${meeting.link}', '_blank')" style="font-size: 14px; padding: 8px 15px;">
                            Join Meeting
                        </button>
                    ` : ''}
                    ${meeting.id ? `
                        <button class="btn btn-success" onclick="openGmailMessage('${meeting.id}')" style="font-size: 14px; padding: 8px 15px;">
                            View Email
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function updateStats() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/stats');
        if (response.ok) {
            const backendStats = await response.json();
            stats = backendStats;
        }
    } catch (e) {
        addLog('error', 'Failed to fetch stats: ' + e.message);
    }
    document.getElementById('totalMeetings').textContent = stats.totalMeetings;
    document.getElementById('upcomingMeetings').textContent = stats.upcomingMeetings;
    document.getElementById('emailsScanned').textContent = stats.emailsScanned;
    document.getElementById('successRate').textContent = stats.successRate + '%';
}

function addLog(type, message) {
    const container = document.getElementById('logsContainer');
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    logEntry.textContent = `[${timestamp}] [${type.toUpperCase()}] ${message}`;
    container.appendChild(logEntry);
    container.scrollTop = container.scrollHeight;
    while (container.children.length > 50) {
        container.removeChild(container.firstChild);
    }
}

function clearLogs() {
    document.getElementById('logsContainer').innerHTML = '';
    addLog('info', 'Logs cleared');
}

function saveSettings() {
    const settings = {
        checkInterval: document.getElementById('checkInterval').value,
        alertTime: document.getElementById('alertTime').value,
        emailKeywords: document.getElementById('emailKeywords').value,
        allowedMailIds: document.getElementById('allowedMailIds').value,
        isSystemRunning: isSystemRunning
    };
    allowedMailIds = settings.allowedMailIds.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
    console.log('Settings saved:', settings);
    addLog('debug', 'Settings saved to backend');
}

function loadSettings() {
    const defaultSettings = {
        checkInterval: '5',
        alertTime: '10',
        emailKeywords: 'meeting, zoom, conference, appointment, masterclass, workshop',
        allowedMailIds: '',
        isSystemRunning: false
    };
    document.getElementById('checkInterval').value = defaultSettings.checkInterval;
    document.getElementById('alertTime').value = defaultSettings.alertTime;
    document.getElementById('emailKeywords').value = defaultSettings.emailKeywords;
    document.getElementById('allowedMailIds').value = defaultSettings.allowedMailIds;
    allowedMailIds = defaultSettings.allowedMailIds.split(',').map(s => s.trim().toLowerCase()).filter(Boolean);
    addLog('debug', 'Settings loaded from backend');
}

document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === ' ') {
        e.preventDefault();
        toggleSystem();
    }
});

setInterval(updateStats, 30000);

function showMeetingNotification(title, body) {
  if (window.electronAPI && window.electronAPI.showNotification) {
    window.electronAPI.showNotification(title, body);
  } else if (window.Notification) {
    if (Notification.permission === 'granted') {
      new Notification(title, { body });
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          new Notification(title, { body });
        }
      });
    }
  } else {
    alert(title + '\n' + body);
  }
}

// Example usage:
// showMeetingNotification('Meeting Alert', 'You have a meeting at 10:00 AM');

async function checkEmails() {
    addLog('info', 'Scanning Gmail for new emails...');
    try {
        const response = await fetch('http://127.0.0.1:8000/api/check-emails');
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        const data = await response.json();
        // data should be an array of meeting objects
        if (Array.isArray(data) && data.length > 0) {
            let newMeetings = 0;
            data.forEach(meeting => {
                // Convert meeting.time to Date object if it's a string
                if (typeof meeting.time === 'string') {
                    meeting.time = new Date(meeting.time);
                }
                // Avoid duplicates by checking id or time/title
                const exists = detectedMeetings.some(m => m.id === meeting.id || (m.title === meeting.title && m.time.getTime() === meeting.time.getTime()));
                // Filter by allowedMailIds if set
                const senderEmail = (meeting.sender || '').toLowerCase();
                const allowed = allowedMailIds.length === 0 || allowedMailIds.some(id => senderEmail.includes(id));
                if (!exists && allowed) {
                    detectedMeetings.push(meeting);
                    stats.totalMeetings++;
                    newMeetings++;
                    addLog('success', `Meeting detected: ${meeting.title}`);
                    const alertTime = parseInt(document.getElementById('alertTime').value) * 60000;
                    const timeUntilMeeting = meeting.time.getTime() - Date.now();
                    if (timeUntilMeeting > 0 && timeUntilMeeting <= alertTime) {
                        showMeetingAlert(meeting);
                    }
                }
            });
            if (newMeetings === 0) {
                addLog('debug', 'No new meetings found in recent emails');
            }
            updateMeetingsDisplay();
        } else {
            addLog('debug', 'No meetings detected by backend');
        }
    } catch (e) {
        addLog('error', 'Failed to check emails: ' + e.message);
    }
}
