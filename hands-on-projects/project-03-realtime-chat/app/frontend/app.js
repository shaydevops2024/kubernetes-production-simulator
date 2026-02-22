// ===== Config =====
const API = {
    chat:          '/api/chat',
    presence:      '/api/presence',
    notifications: '/api/notifications',
    files:         '/api/files',
};

const SERVICES = [
    { name: 'Chat Service',         key: 'chat',          port: 8020, path: '/health' },
    { name: 'Presence Service',     key: 'presence',      port: 8021, path: '/health' },
    { name: 'Notification Service', key: 'notifications', port: 8022, path: '/health' },
    { name: 'File Service',         key: 'files',         port: 8023, path: '/health' },
];

// ===== State =====
let currentUser   = null;  // { id, username }
let currentRoom   = null;  // { id, name, description }
let ws            = null;
let wsReconnectTimer = null;
let typingTimer   = null;
let isTyping      = false;
let presenceTimer = null;
let notifTimer    = null;
let rooms         = [];
let typingUsers   = {};   // room_id → Set of usernames

// ===== Init =====

document.addEventListener('DOMContentLoaded', () => {
    const saved = localStorage.getItem('chatflow_user');
    if (saved) {
        try {
            currentUser = JSON.parse(saved);
            launchApp();
        } catch {
            localStorage.removeItem('chatflow_user');
        }
    }
    // If no saved user, the username modal is shown by default
});

function setUsername(e) {
    e.preventDefault();
    const name = document.getElementById('username-input').value.trim();
    if (!name) return;

    currentUser = {
        id: name.toLowerCase().replace(/\s+/g, '-'),
        username: name,
    };
    localStorage.setItem('chatflow_user', JSON.stringify(currentUser));
    launchApp();
}

function launchApp() {
    document.getElementById('username-overlay').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');
    document.getElementById('current-username').textContent = currentUser.username;

    loadRooms();
    startPresenceHeartbeat();
    startNotificationPolling();
}


// ===== Rooms =====

async function loadRooms() {
    try {
        const res  = await fetch(`${API.chat}/rooms`);
        rooms = await res.json();
        renderRooms(rooms);
        // Auto-join first room
        if (rooms.length > 0) joinRoom(rooms[0]);
    } catch {
        document.getElementById('rooms-list').innerHTML = '<div class="loading-small">Failed to load rooms</div>';
    }
}

function renderRooms(roomList) {
    const el = document.getElementById('rooms-list');
    el.innerHTML = roomList.map(r => `
        <div class="room-item ${currentRoom?.id === r.id ? 'active' : ''}"
             id="room-item-${r.id}" onclick="joinRoom(${JSON.stringify(r).replace(/"/g, '&quot;')})">
            ${escHtml(r.name)}
        </div>
    `).join('');
}

function joinRoom(room) {
    if (currentRoom?.id === room.id) return;
    currentRoom = room;

    // Update UI
    renderRooms(rooms);
    document.getElementById('current-room-name').textContent = room.name;
    document.getElementById('current-room-desc').textContent = room.description || '';
    document.getElementById('message-input').placeholder = `Message ${room.name}…`;

    // Close existing WebSocket
    if (ws) {
        ws.close();
        ws = null;
    }

    // Load history then open WebSocket
    loadMessages(room.id).then(() => connectWebSocket(room.id));
}

async function createRoom(e) {
    e.preventDefault();
    const id   = document.getElementById('new-room-id').value.trim();
    const name = document.getElementById('new-room-name').value.trim();
    const desc = document.getElementById('new-room-desc').value.trim();
    try {
        const res = await fetch(`${API.chat}/rooms`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, name, description: desc }),
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to create room');
        }
        const room = await res.json();
        rooms.push(room);
        hideNewRoomModal();
        joinRoom(room);
        toast('Room created!', 'success');
    } catch (e) {
        toast(e.message, 'error');
    }
}

function showNewRoomModal() { document.getElementById('new-room-overlay').classList.remove('hidden'); }
function hideNewRoomModal() { document.getElementById('new-room-overlay').classList.add('hidden'); }


// ===== Messages =====

async function loadMessages(roomId) {
    const container = document.getElementById('messages');
    container.innerHTML = '<div class="loading">Loading history...</div>';
    try {
        const res  = await fetch(`${API.chat}/rooms/${roomId}/messages?limit=100`);
        const msgs = await res.json();
        container.innerHTML = '';

        let lastDate = null;
        for (const msg of msgs) {
            const date = new Date(msg.created_at).toLocaleDateString();
            if (date !== lastDate) {
                container.appendChild(buildDayDivider(date));
                lastDate = date;
            }
            container.appendChild(buildMessage(msg));
        }
        scrollToBottom();
    } catch {
        container.innerHTML = '<div class="loading">Failed to load messages</div>';
    }
}

function buildDayDivider(dateStr) {
    const el = document.createElement('div');
    el.className = 'day-divider';
    el.textContent = dateStr;
    return el;
}

function buildMessage(msg) {
    const el       = document.createElement('div');
    const isSystem = msg.message_type === 'system' || msg.type === 'user_joined' || msg.type === 'user_left';
    el.className   = `message${isSystem ? ' system' : ''}`;

    const time  = new Date(msg.created_at || msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const init  = (msg.username || '?')[0].toUpperCase();
    const color = avatarColor(msg.user_id || msg.username);

    let contentHtml = '';
    if (msg.message_type === 'file' && msg.file_url) {
        contentHtml = buildFileAttachment(msg.content, msg.file_url);
    } else {
        contentHtml = `<span class="message-content">${escHtml(msg.content)}</span>`;
    }

    el.innerHTML = `
        <div class="message-avatar" style="background:${color};">${isSystem ? '⚙' : init}</div>
        <div class="message-body">
            <div class="message-header">
                <span class="message-username">${isSystem ? 'System' : escHtml(msg.username)}</span>
                <span class="message-time">${time}</span>
            </div>
            ${contentHtml}
        </div>
    `;
    return el;
}

function buildFileAttachment(filename, url) {
    const ext = filename.split('.').pop().toLowerCase();
    const isImg = ['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext);
    if (isImg) {
        return `<a class="file-attachment" href="${escHtml(url)}" target="_blank" rel="noopener">
            <img src="${escHtml(url)}" alt="${escHtml(filename)}" loading="lazy">
        </a>`;
    }
    return `<a class="file-attachment" href="${escHtml(url)}" target="_blank" rel="noopener">
        📄 ${escHtml(filename)}
    </a>`;
}

function appendMessage(msg) {
    const container = document.getElementById('messages');
    const el        = buildMessage(msg);
    container.appendChild(el);
    scrollToBottom();
}

function scrollToBottom() {
    const el = document.getElementById('messages');
    el.scrollTop = el.scrollHeight;
}


// ===== WebSocket =====

function connectWebSocket(roomId) {
    const proto    = location.protocol === 'https:' ? 'wss' : 'ws';
    const url      = `${proto}://${location.host}/ws/${roomId}/${encodeURIComponent(currentUser.id)}?username=${encodeURIComponent(currentUser.username)}`;

    clearTimeout(wsReconnectTimer);
    ws = new WebSocket(url);

    ws.onopen = () => {
        console.log(`[WS] Connected to room: ${roomId}`);
    };

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWsMessage(msg);
    };

    ws.onclose = (event) => {
        console.log(`[WS] Disconnected from ${roomId} (code ${event.code})`);
        // Auto-reconnect unless we intentionally closed (room switch)
        if (currentRoom?.id === roomId && event.code !== 1000) {
            wsReconnectTimer = setTimeout(() => connectWebSocket(roomId), 3000);
        }
    };

    ws.onerror = (err) => {
        console.warn('[WS] Error:', err);
    };
}

function handleWsMessage(msg) {
    switch (msg.type) {
        case 'message':
            appendMessage(msg);
            // Create notification if mentioned
            if (msg.content.includes(`@${currentUser.username}`) && msg.user_id !== currentUser.id) {
                createNotification(`@${msg.username} mentioned you`, msg.content, msg.room_id);
            }
            break;

        case 'typing':
            if (msg.user_id !== currentUser.id) {
                typingUsers[msg.room_id] = typingUsers[msg.room_id] || new Set();
                typingUsers[msg.room_id].add(msg.username);
                renderTyping(msg.room_id);
            }
            break;

        case 'stop_typing':
            if (typingUsers[msg.room_id]) {
                typingUsers[msg.room_id].delete(msg.username);
                renderTyping(msg.room_id);
            }
            break;

        case 'user_joined':
            if (msg.user_id !== currentUser.id) {
                appendMessage({
                    type: 'user_joined',
                    user_id: 'system',
                    username: 'System',
                    content: `${msg.username} joined the room.`,
                    message_type: 'system',
                    created_at: msg.timestamp,
                });
            }
            break;

        case 'user_left':
            if (msg.user_id !== currentUser.id) {
                appendMessage({
                    type: 'user_left',
                    user_id: 'system',
                    username: 'System',
                    content: `${msg.username} left the room.`,
                    message_type: 'system',
                    created_at: msg.timestamp,
                });
            }
            break;
    }
}

function renderTyping(roomId) {
    const bar   = document.getElementById('typing-bar');
    const users = [...(typingUsers[roomId] || [])];
    if (users.length === 0) {
        bar.classList.add('hidden');
        bar.textContent = '';
    } else {
        const names = users.slice(0, 3).join(', ');
        const suffix = users.length === 1 ? 'is typing…' : 'are typing…';
        bar.textContent = `${names} ${suffix}`;
        bar.classList.remove('hidden');
    }
}


// ===== Sending Messages =====

function sendMessage() {
    const input   = document.getElementById('message-input');
    const content = input.value.trim();
    if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;

    ws.send(JSON.stringify({ type: 'message', content }));
    input.value = '';

    // Stop typing indicator
    stopTyping();
}

function handleTyping() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    if (!isTyping) {
        isTyping = true;
        ws.send(JSON.stringify({ type: 'typing' }));
    }

    clearTimeout(typingTimer);
    typingTimer = setTimeout(stopTyping, 2000);
}

function stopTyping() {
    if (!isTyping) return;
    isTyping = false;
    clearTimeout(typingTimer);
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'stop_typing' }));
    }
}


// ===== File Upload =====

async function uploadFile(event) {
    const file = event.target.files[0];
    event.target.value = '';  // reset input
    if (!file) return;

    toast(`Uploading ${file.name}…`);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch(
            `${API.files}/upload?uploaded_by=${encodeURIComponent(currentUser.id)}&room_id=${encodeURIComponent(currentRoom?.id || '')}`,
            { method: 'POST', body: formData }
        );
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Upload failed');
        }
        const info = await res.json();

        // Send as file message in chat
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'message',
                content: info.original_name,
                message_type: 'file',
                file_url: info.download_url,
            }));
        }
        toast('File uploaded!', 'success');
    } catch (e) {
        toast(`Upload failed: ${e.message}`, 'error');
    }
}


// ===== Presence =====

function startPresenceHeartbeat() {
    const beat = async () => {
        try {
            await fetch(
                `${API.presence}/${encodeURIComponent(currentUser.id)}/heartbeat?username=${encodeURIComponent(currentUser.username)}`,
                { method: 'POST' }
            );
        } catch { /* ignore */ }
        await loadOnlineUsers();
    };

    beat();
    presenceTimer = setInterval(beat, 15000);  // every 15s

    // Send offline signal on page unload
    window.addEventListener('beforeunload', () => {
        navigator.sendBeacon(`${API.presence}/${encodeURIComponent(currentUser.id)}`, JSON.stringify({ method: 'DELETE' }));
    });
}

async function loadOnlineUsers() {
    try {
        const res   = await fetch(`${API.presence}`);
        const users = await res.json();
        document.getElementById('online-count').textContent = users.length;
        document.getElementById('online-users').innerHTML = users.length === 0
            ? '<div class="loading-small">Just you</div>'
            : users.map(u => `
                <div class="online-user">
                    <div class="dot dot-online"></div>
                    <span style="font-size:13px;color:#c9cdd4;">${escHtml(u.username)}</span>
                </div>
            `).join('');
    } catch { /* ignore */ }
}


// ===== Notifications =====

async function createNotification(title, body, roomId) {
    try {
        await fetch(`${API.notifications}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUser.id, title, body, room_id: roomId, notif_type: 'mention' }),
        });
    } catch { /* ignore */ }
}

function startNotificationPolling() {
    const poll = async () => {
        try {
            const res   = await fetch(`${API.notifications}/${encodeURIComponent(currentUser.id)}/unread-count`);
            const data  = await res.json();
            const badge = document.getElementById('notif-badge');
            if (data.unread_count > 0) {
                badge.textContent = data.unread_count;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        } catch { /* ignore */ }
    };
    poll();
    notifTimer = setInterval(poll, 20000);
}

async function toggleNotifications() {
    const panel = document.getElementById('notif-panel');
    if (panel.classList.contains('hidden')) {
        await loadNotifications();
        panel.classList.remove('hidden');
    } else {
        panel.classList.add('hidden');
    }
}

async function loadNotifications() {
    const list = document.getElementById('notif-list');
    try {
        const res   = await fetch(`${API.notifications}/${encodeURIComponent(currentUser.id)}?limit=20`);
        const notifs = await res.json();
        if (!notifs.length) {
            list.innerHTML = '<div class="empty-state-small">No notifications</div>';
            return;
        }
        list.innerHTML = notifs.map(n => `
            <div class="notif-item ${n.read ? '' : 'unread'}" onclick="markRead('${n.id}', this)">
                <div class="notif-title">${escHtml(n.title)}</div>
                <div class="notif-body">${escHtml(n.body)}</div>
                <div class="notif-time">${new Date(n.created_at).toLocaleString()}</div>
            </div>
        `).join('');
    } catch {
        list.innerHTML = '<div class="empty-state-small">Failed to load notifications</div>';
    }
}

async function markRead(id, el) {
    el.classList.remove('unread');
    try {
        await fetch(`${API.notifications}/${id}/read`, { method: 'PATCH' });
    } catch { /* ignore */ }
}

async function markAllRead() {
    try {
        await fetch(`${API.notifications}/${encodeURIComponent(currentUser.id)}/read-all`, { method: 'PATCH' });
        document.querySelectorAll('.notif-item').forEach(el => el.classList.remove('unread'));
        document.getElementById('notif-badge').classList.add('hidden');
    } catch { /* ignore */ }
}


// ===== Services Health =====

function switchPage(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    if (page === 'services') checkServices();
}

async function checkServices() {
    const grid = document.getElementById('services-grid');
    grid.innerHTML = SERVICES.map(s => `
        <div class="service-card" id="svc-${s.key}">
            <div class="service-card-header">
                <span class="service-card-name">${s.name}</span>
                <span class="service-card-port">:${s.port}</span>
            </div>
            <div class="status-row">
                <div class="status-indicator checking"></div>
                <span>Checking…</span>
            </div>
        </div>
    `).join('');

    SERVICES.forEach(async s => {
        const card   = document.getElementById(`svc-${s.key}`);
        const status = card.querySelector('.status-row');
        try {
            const res     = await fetch(`${API[s.key]}${s.path}`, { signal: AbortSignal.timeout(3000) });
            const healthy = res.ok;
            const data    = await res.json();
            status.innerHTML = `
                <div class="status-indicator ${healthy ? 'healthy' : 'down'}"></div>
                <span>${healthy ? 'Healthy' : 'Unhealthy'}</span>
            `;
            if (data.minio) {
                const extra = document.createElement('div');
                extra.style.cssText = 'font-size:12px;color:#6b7280;margin-top:4px;';
                extra.textContent = `MinIO: ${data.minio}`;
                card.appendChild(extra);
            }
        } catch {
            status.innerHTML = `<div class="status-indicator down"></div><span>Unreachable</span>`;
        }
    });
}


// ===== Helpers =====

function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const AVATAR_COLORS = ['#5865f2','#eb459e','#ed4245','#faa61a','#57f287','#1abc9c','#3498db','#9b59b6'];
function avatarColor(str) {
    let hash = 0;
    for (const c of String(str)) hash = c.charCodeAt(0) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

let toastTimer;
function toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast ${type}`;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}
