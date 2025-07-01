// Chat logic for Wispr

// The following variables must be set in the template before loading this script:
// window.CHAT_CONTEXT = { username: '...', role: 'admin'|'moderator'|'member' };

// Initialize Socket.IO
const socket = io();
let currentRoom = 'general';
let currentDMUser = null;
let typingTimer;
let isTyping = false;

// --- Mention Autocomplete ---
let allUsernames = [];
let mentionDropdown = null;

// Fetch all usernames for autocomplete
fetch('/api/users')
    .then(response => response.json())
    .then(users => {
        allUsernames = users;
    });

function showMentionDropdown(matches, input, caretPos) {
    if (mentionDropdown) mentionDropdown.remove();
    if (!matches.length) return;
    mentionDropdown = document.createElement('div');
    mentionDropdown.className = 'mention-dropdown';
    mentionDropdown.style.position = 'absolute';
    mentionDropdown.style.zIndex = 1000;
    mentionDropdown.style.background = '#222';
    mentionDropdown.style.color = '#fff';
    mentionDropdown.style.border = '1px solid #444';
    mentionDropdown.style.borderRadius = '4px';
    mentionDropdown.style.fontSize = '1rem';
    mentionDropdown.style.minWidth = '120px';
    mentionDropdown.style.maxHeight = '200px';
    mentionDropdown.style.overflowY = 'auto';
    mentionDropdown.style.left = input.offsetLeft + 'px';
    mentionDropdown.style.top = (input.offsetTop + input.offsetHeight) + 'px';
    matches.forEach((username, idx) => {
        const item = document.createElement('div');
        item.className = 'mention-item';
        item.style.padding = '6px 12px';
        item.style.cursor = 'pointer';
        item.textContent = username;
        item.addEventListener('mousedown', function(e) {
            e.preventDefault();
            insertMention(input, username, caretPos);
            hideMentionDropdown();
        });
        mentionDropdown.appendChild(item);
    });
    input.parentElement.appendChild(mentionDropdown);
}

function hideMentionDropdown() {
    if (mentionDropdown) {
        mentionDropdown.remove();
        mentionDropdown = null;
    }
}

function insertMention(input, username, caretPos) {
    const value = input.value;
    const before = value.slice(0, caretPos);
    const after = value.slice(caretPos);
    // Replace the last @... with @username
    const newBefore = before.replace(/@([\w\d_]*)$/, '@' + username + ' ');
    input.value = newBefore + after;
    input.focus();
    // Move caret to after inserted mention
    const newPos = newBefore.length;
    input.setSelectionRange(newPos, newPos);
}

if (document.getElementById('message-input')) {
    const input = document.getElementById('message-input');
    input.addEventListener('input', function(e) {
        const caretPos = input.selectionStart;
        const value = input.value.slice(0, caretPos);
        const match = value.match(/@([\w\d_]*)$/);
        if (match) {
            const search = match[1].toLowerCase();
            const matches = allUsernames.filter(u => u.toLowerCase().startsWith(search) && u !== window.CHAT_CONTEXT.username);
            showMentionDropdown(matches, input, caretPos);
        } else {
            hideMentionDropdown();
        }
    });
    input.addEventListener('keydown', function(e) {
        if (mentionDropdown && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter')) {
            const items = Array.from(mentionDropdown.querySelectorAll('.mention-item'));
            let idx = items.findIndex(item => item.classList.contains('active'));
            if (e.key === 'ArrowDown') {
                if (idx >= 0) items[idx].classList.remove('active');
                idx = (idx + 1) % items.length;
                items[idx].classList.add('active');
                e.preventDefault();
            } else if (e.key === 'ArrowUp') {
                if (idx >= 0) items[idx].classList.remove('active');
                idx = (idx - 1 + items.length) % items.length;
                items[idx].classList.add('active');
                e.preventDefault();
            } else if (e.key === 'Enter') {
                if (idx >= 0) {
                    items[idx].dispatchEvent(new MouseEvent('mousedown'));
                    e.preventDefault();
                }
            }
        } else if (e.key === 'Escape') {
            hideMentionDropdown();
        }
    });
    document.addEventListener('click', function(e) {
        if (mentionDropdown && !mentionDropdown.contains(e.target)) {
            hideMentionDropdown();
        }
    });
}

// --- Toast Notification UI ---
function showToast(message) {
    let toast = document.createElement('div');
    toast.className = 'wispr-toast';
    toast.style.position = 'fixed';
    toast.style.bottom = '32px';
    toast.style.right = '32px';
    toast.style.background = '#222';
    toast.style.color = '#fff';
    toast.style.padding = '16px 24px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
    toast.style.fontSize = '1rem';
    toast.style.zIndex = 9999;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 500);
    }, 4000);
}

// Connect to socket
socket.on('connect', function() {
    console.log('Connected to server');
    socket.emit('join_room', {room: 'general'});
});

// --- Wispr Chat Main Logic (CSP-safe, robust) ---

// Defensive: Only call addMessageToChat for valid user messages
function isValidUserMessage(data) {
    return data && typeof data === 'object' && typeof data.username === 'string' && typeof data.content === 'string';
}

// Defensive: Only call addSystemMessage for system messages
function isSystemMessage(data) {
    return data && typeof data.message === 'string' && (typeof data.username === 'undefined');
}

// Socket event: receive_message
socket.on('receive_message', function(data) {
    if (isValidUserMessage(data)) {
        addMessageToChat(data);
        const noMsg = document.getElementById('no-messages');
        if (noMsg) noMsg.style.display = 'none';
    } else if (isSystemMessage(data)) {
        addSystemMessage(data.message);
    } else {
        console.warn('[receive_message] Ignored malformed or unknown message:', data);
    }
});

// Handle user connection/disconnection
socket.on('user_connected', function(data) {
    addSystemMessage(data.message);
});

socket.on('user_disconnected', function(data) {
    addSystemMessage(data.message);
});

// Handle typing indicators
socket.on('user_typing', function(data) {
    if (data.username !== window.CHAT_CONTEXT.username) {
        showTypingIndicator(data.username);
    }
});

socket.on('user_stopped_typing', function(data) {
    hideTypingIndicator();
});

// Handle online count updates
socket.on('online_count_updated', function(data) {
    document.getElementById('online-users').textContent = data.count + ' online';
});

// Listen for mention notifications
socket.on('mention_notification', function(data) {
    const from = escapeHtml(data.from || '');
    const msg = escapeHtml(data.message || '');
    let text = `You were mentioned by @${from}`;
    if (msg) text += `: ${msg}`;
    showToast(text);
});

// --- Message Threading ---
let replyingTo = null;

function showReplyForm(messageId, username, content) {
    replyingTo = { id: messageId, username, content };
    const messageInput = document.getElementById('message-input');
    const replyIndicator = document.getElementById('reply-indicator');
    
    // Show reply indicator
    replyIndicator.style.display = 'block';
    replyIndicator.innerHTML = `
        <div class="d-flex justify-content-between align-items-center">
            <div>
                <small class="text-muted">Replying to <strong>${escapeHtml(username)}</strong></small>
                <div class="text-truncate" style="max-width: 300px;">${escapeHtml(content)}</div>
            </div>
            <button type="button" class="btn btn-sm btn-outline-secondary" onclick="cancelReply()">
                <i class="bi bi-x"></i>
            </button>
        </div>
    `;
    
    messageInput.focus();
    messageInput.placeholder = `Reply to ${username}...`;
}

function cancelReply() {
    replyingTo = null;
    const messageInput = document.getElementById('message-input');
    const replyIndicator = document.getElementById('reply-indicator');
    
    replyIndicator.style.display = 'none';
    messageInput.placeholder = 'Type your message...';
}

// --- DM End-to-End Encryption ---
// Use a shared key derived from both user IDs (sorted, as string)
const DM_KEYS = {};

async function getDMKey(otherUserId) {
    // Deterministically derive a key from both user IDs (sorted)
    const ids = [window.CHAT_CONTEXT.user_id, otherUserId].map(String).sort().join(":");
    if (DM_KEYS[ids]) return DM_KEYS[ids];
    // For demo: use SHA-256 of ids as key material
    const enc = new TextEncoder();
    const keyMaterial = await window.crypto.subtle.digest('SHA-256', enc.encode(ids));
    const key = await window.crypto.subtle.importKey(
        'raw', keyMaterial, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']
    );
    DM_KEYS[ids] = key;
    return key;
}

async function encryptDM(plaintext, recipientId) {
    try {
        const key = await getDMKey(recipientId);
        const enc = new TextEncoder();
        const iv = window.crypto.getRandomValues(new Uint8Array(12));
        const ciphertext = await window.crypto.subtle.encrypt(
            { name: 'AES-GCM', iv },
            key,
            enc.encode(plaintext)
        );
        // Return base64(iv) + ':' + base64(ciphertext)
        return btoa(String.fromCharCode(...iv)) + ':' + btoa(String.fromCharCode(...new Uint8Array(ciphertext)));
    } catch (e) {
        alert('Encryption failed: ' + e);
        return plaintext;
    }
}

async function decryptDM(ciphertext, senderId) {
    try {
        const key = await getDMKey(senderId);
        const [ivB64, ctB64] = ciphertext.split(':');
        if (!ivB64 || !ctB64) return ciphertext;
        const iv = Uint8Array.from(atob(ivB64), c => c.charCodeAt(0));
        const ct = Uint8Array.from(atob(ctB64), c => c.charCodeAt(0));
        const dec = await window.crypto.subtle.decrypt(
            { name: 'AES-GCM', iv },
            key,
            ct
        );
        return new TextDecoder().decode(dec);
    } catch (e) {
        console.warn('Decryption failed:', e);
        return '[Encrypted message: could not decrypt]';
    }
}

// Patch message sending to encrypt DMs
if (document.getElementById('message-form')) {
    document.getElementById('message-form').addEventListener('submit', async function(e) {
        e.preventDefault();
        const messageInput = document.getElementById('message-input');
        let message = messageInput.value.trim();
        if (message) {
            let encrypted = message;
            if (currentDMUser) {
                encrypted = await encryptDM(message, currentDMUser);
            }
            const data = {
                message: encrypted,
                room: currentDMUser ? null : currentRoom,
                recipient_id: currentDMUser
            };
            // Add parent_id if replying
            if (replyingTo) {
                data.parent_id = replyingTo.id;
            }
            console.log('Sending message:', data);
            if (replyingTo) {
                socket.emit('reply_message', data);
            } else {
                socket.emit('send_message', data);
            }
            messageInput.value = '';
            cancelReply();
            if (isTyping) {
                socket.emit('stop_typing', {room: currentRoom});
                isTyping = false;
            }
        }
    });
}

// Defensive: Patch loadRoomMessages and loadDirectMessages
function loadRoomMessages(roomId) {
    fetch(`/api/room_messages/${roomId}`)
        .then(response => response.json())
        .then(messages => {
            if (Array.isArray(messages) && messages.length > 0) {
                const noMsg = document.getElementById('no-messages');
                if (noMsg) noMsg.style.display = 'none';
                messages.filter(isValidUserMessage).forEach(addMessageToChat);
                const malformed = messages.filter(m => !isValidUserMessage(m));
                if (malformed.length > 0) console.warn('[loadRoomMessages] Malformed:', malformed);
            }
        });
}
function loadDirectMessages(userId) {
    fetch(`/api/direct_messages/${userId}`)
        .then(response => response.json())
        .then(async messages => {
            if (Array.isArray(messages) && messages.length > 0) {
                const noMsg = document.getElementById('no-messages');
                if (noMsg) noMsg.style.display = 'none';
                for (const message of messages) {
                    if (isValidUserMessage(message) && message.is_direct_message) {
                        message.content = await decryptDM(message.content, message.username === window.CHAT_CONTEXT.username ? currentDMUser : message.username);
                        addMessageToChat(message);
                    } else if (!isValidUserMessage(message)) {
                        console.warn('[loadDirectMessages] Malformed:', message);
                    }
                }
            }
        });
}

// Typing detection
if (document.getElementById('message-input')) {
    document.getElementById('message-input').addEventListener('input', function() {
        if (!isTyping) {
            isTyping = true;
            socket.emit('start_typing', {room: currentRoom});
        }

        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => {
            if (isTyping) {
                socket.emit('stop_typing', {room: currentRoom});
                isTyping = false;
            }
        }, 1000);
    });
}

// File handling
if (document.getElementById('file-input')) {
    document.getElementById('file-input').addEventListener('change', function(e) {
        const files = e.target.files;
        if (files.length > 0) {
            showFilePreview(files);
        }
    });
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, function(m) { return map[m]; });
}

// --- Emoji Reaction Bar ---
const ALLOWED_EMOJIS = ['👍', '😂', '😢', '❤️', '🎉'];

function renderReactionBar(messageId, reactions) {
    const userId = window.CHAT_CONTEXT.user_id;
    let html = '<div class="reaction-bar mt-2 d-flex align-items-center">';
    
    // Show existing reactions with counts
    if (reactions) {
        Object.entries(reactions).forEach(([emoji, data]) => {
            if (data.count > 0) {
                const active = data.user_ids && data.user_ids.includes(userId);
                html += `<button class="reaction-btn btn btn-sm ${active ? 'btn-primary' : 'btn-outline-secondary'} me-1" data-emoji="${emoji}" data-message-id="${messageId}">${emoji} <span class="reaction-count">${data.count}</span></button>`;
            }
        });
    }
    
    // Add expandable emoji menu
    html += `
        <div class="emoji-menu-container ms-2">
            <button class="btn btn-sm btn-outline-secondary emoji-toggle" data-message-id="${messageId}">
                <i class="bi bi-plus"></i>
            </button>
            <div class="emoji-menu dropdown-menu" data-message-id="${messageId}" style="display: none;">
                <div class="d-flex flex-wrap p-2">
    `;
    
    ALLOWED_EMOJIS.forEach(emoji => {
        html += `<button class="btn btn-sm btn-outline-secondary me-1 mb-1 emoji-option" data-emoji="${emoji}" data-message-id="${messageId}">${emoji}</button>`;
    });
    
    html += `
                </div>
            </div>
        </div>
    `;
    
    html += '</div>';
    return html;
}

// Store reactions in memory for quick update
const messageReactions = {};

// Listen for reactions_update events
socket.on('reactions_update', function(data) {
    const {message_id, reactions} = data;
    messageReactions[message_id] = reactions;
    updateReactionBar(message_id);
});

function updateReactionBar(messageId) {
    const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!messageDiv) return;
    
    // Find existing reaction bar and replace it
    const existingBar = messageDiv.querySelector('.reaction-bar');
    if (existingBar) {
        existingBar.outerHTML = renderReactionBar(messageId, messageReactions[messageId] || {});
        attachReactionHandlers(messageId);
    }
}

function attachReactionHandlers(messageId) {
    const messageDiv = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!messageDiv) return;
    
    // Handle existing reaction buttons
    messageDiv.querySelectorAll('.reaction-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const emoji = this.getAttribute('data-emoji');
            const reactions = messageReactions[messageId] || {};
            const userId = window.CHAT_CONTEXT.user_id;
            const userReacted = reactions[emoji] && reactions[emoji].user_ids && reactions[emoji].user_ids.includes(userId);
            
            console.log('Reaction click:', {
                emoji,
                messageId,
                userId,
                reactions: reactions[emoji],
                userReacted,
                allReactions: reactions
            });
            
            if (userReacted) {
                console.log('Removing reaction');
                socket.emit('remove_reaction', {message_id: messageId, emoji});
            } else {
                console.log('Adding reaction');
                socket.emit('add_reaction', {message_id: messageId, emoji});
            }
        });
    });
    
    // Handle emoji menu toggle
    const toggleBtn = messageDiv.querySelector('.emoji-toggle');
    const emojiMenu = messageDiv.querySelector('.emoji-menu');
    
    if (toggleBtn && emojiMenu) {
        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const isVisible = emojiMenu.style.display !== 'none';
            emojiMenu.style.display = isVisible ? 'none' : 'block';
            toggleBtn.innerHTML = isVisible ? '<i class="bi bi-plus"></i>' : '<i class="bi bi-x"></i>';
        });
        
        // Handle emoji option clicks
        emojiMenu.querySelectorAll('.emoji-option').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const emoji = this.getAttribute('data-emoji');
                const reactions = messageReactions[messageId] || {};
                const userId = window.CHAT_CONTEXT.user_id;
                const userReacted = reactions[emoji] && reactions[emoji].user_ids && reactions[emoji].user_ids.includes(userId);
                
                console.log('Emoji option click:', {
                    emoji,
                    messageId,
                    userId,
                    reactions: reactions[emoji],
                    userReacted,
                    allReactions: reactions
                });
                
                if (userReacted) {
                    console.log('Removing reaction from menu');
                    socket.emit('remove_reaction', {message_id: messageId, emoji});
                } else {
                    console.log('Adding reaction from menu');
                    socket.emit('add_reaction', {message_id: messageId, emoji});
                }
                
                // Close menu after selection
                emojiMenu.style.display = 'none';
                toggleBtn.innerHTML = '<i class="bi bi-plus"></i>';
            });
        });
    }
}

// Close emoji menus when clicking outside
document.addEventListener('click', function(e) {
    if (!e.target.closest('.emoji-menu-container')) {
        document.querySelectorAll('.emoji-menu').forEach(menu => {
            menu.style.display = 'none';
        });
        document.querySelectorAll('.emoji-toggle').forEach(btn => {
            btn.innerHTML = '<i class="bi bi-plus"></i>';
        });
    }
});

// --- User Status/Presence ---
const STATUS_COLORS = {
    online: '🟢',
    away: '🟡',
    dnd: '🔴',
    offline: '⚫️'
};

let userStatusMap = {};

// Fetch all usernames and statuses for autocomplete and status map
fetch('/api/users')
    .then(response => response.json())
    .then(users => {
        allUsernames = users.map(u => u.username);
        users.forEach(u => { userStatusMap[u.username.toLowerCase()] = u.status; });
        // Update DM user list status dots
        document.querySelectorAll('.status-dot[data-username-status]').forEach(dot => {
            const uname = dot.getAttribute('data-username-status').toLowerCase();
            const status = userStatusMap[uname] || 'offline';
            dot.textContent = STATUS_COLORS[status] || '⚫️';
            dot.title = status.charAt(0).toUpperCase() + status.slice(1);
        });
    });

// Listen for status updates from server
socket.on('user_status_update', function(data) {
    const uname = data.username.toLowerCase();
    userStatusMap[uname] = data.status;
    document.querySelectorAll(`[data-username-status="${uname}"]`).forEach(dot => {
        dot.textContent = STATUS_COLORS[data.status] || '⚫️';
        dot.title = data.status.charAt(0).toUpperCase() + data.status.slice(1);
    });
});

// Defensive addMessageToChat
window.origAddMessageToChat_status = window.addMessageToChat;
window.addMessageToChat = function(data) {
    if (!data || typeof data !== 'object' || typeof data.username === 'undefined' || typeof data.content === 'undefined') {
        console.warn('[addMessageToChat] Malformed or system message:', data);
        return;
    }
    // Store the original username for status lookup
    data.raw_username = data.raw_username || data.username;
    const uname = (data.raw_username || data.username).toLowerCase();
    const messagesContainer = document.getElementById('messages-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-item border-bottom pb-3 mb-3';
    messageDiv.setAttribute('data-message-id', data.id);
    const isOwnMessage = data.username === window.CHAT_CONTEXT.username;
    const timestamp = new Date(data.timestamp).toLocaleString();
    const isReply = data.parent_id;
    const mentionRegex = new RegExp(`@${window.CHAT_CONTEXT.username}(?![\\w\\d_])`, 'i');
    const isMentioned = mentionRegex.test(data.content);
    if (isMentioned) {
        messageDiv.style.background = 'rgba(255, 230, 150, 0.25)';
        messageDiv.style.borderLeft = '4px solid #f7b731';
    }
    if (isReply) {
        messageDiv.style.marginLeft = '20px';
        messageDiv.style.borderLeft = '3px solid #007bff';
        messageDiv.style.paddingLeft = '10px';
    }
    let parentPreview = '';
    if (isReply && data.parent_username && data.parent_content) {
        parentPreview = `\n            <div class=\"reply-preview mb-2 p-2 bg-light rounded\" style=\"font-size: 0.9em; border-left: 3px solid #007bff;\">\n                <small class=\"text-muted\">Replying to <strong>${escapeHtml(data.parent_username)}</strong></small>\n                <div class=\"text-truncate\">${escapeHtml(data.parent_content)}</div>\n            </div>\n        `;
    }
    let avatarUrl = data.profile_pic ? `/uploads/${data.profile_pic}` : '/static/default_avatar.png';
    messageDiv.innerHTML = `\n        ${parentPreview}\n        <div class=\"d-flex align-items-center mb-1\">\n            <img src=\"${avatarUrl}\" class=\"rounded-circle me-2\" width=\"32\" height=\"32\" alt=\"avatar\">\n            <strong class=\"me-2\">${escapeHtml(data.username)}</strong>\n            <span class=\"text-muted small\">${timestamp}</span>\n            <div class=\"ms-auto message-actions\">\n                ${isOwnMessage ? `\n                <button class=\"btn btn-sm btn-outline-primary me-1\" onclick=\"editMessage(${data.id}, '${escapeHtml(data.content).replace(/'/g, "\\'")}')\">\n                    <i class=\"bi bi-pencil\"></i>\n                </button>\n                <button class=\"btn btn-sm btn-outline-danger\" onclick=\"deleteMessage(${data.id})\">\n                    <i class=\"bi bi-trash\"></i>\n                </button>\n                ` : ''}\n            </div>\n        </div>\n        <div class=\"message-content mt-2\">\n            <p class=\"mb-0\" id=\"message-content-${data.id}\">${escapeHtml(data.content).replace(/\n/g, '<br>')}</p>\n            ${data.attachments ? renderAttachments(data.attachments) : ''}\n        </div>\n    `;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
};

function addSystemMessage(message) {
    const messagesContainer = document.getElementById('messages-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'text-center text-muted mb-3';
    messageDiv.innerHTML = `<small><i>${message}</i></small>`;
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Patch switchToDM to always update chat area
function switchToDM(userId, username) {
    console.log('[DM] switchToDM called for userId:', userId, 'username:', username);
    // Clear active room highlight
    document.querySelectorAll('.list-group-item').forEach(item => {
        item.classList.remove('active');
    });
    // Highlight the selected DM
    const dmItem = document.querySelector(`.list-group-item[onclick*="switchToDM('${userId}'"]`);
    if (dmItem) dmItem.classList.add('active');
    currentDMUser = userId;
    currentRoom = null;
    document.getElementById('chat-title').innerHTML = `<i class="bi bi-person-circle"></i> ${username}`;
    clearMessages();
    loadDirectMessages(userId);
}
window.switchToDM = switchToDM;

// Patch switchRoom to always update chat area
function switchRoom(roomId, roomName) {
    document.querySelectorAll('.list-group-item').forEach(item => {
        item.classList.remove('active');
    });
    const roomItem = document.querySelector(`[data-room="${roomId}"]`);
    if (roomItem) roomItem.classList.add('active');
    socket.emit('leave_room', {room: currentRoom});
    socket.emit('join_room', {room: roomId});
    currentRoom = roomId;
    currentDMUser = null;
    document.getElementById('chat-title').innerHTML = `<i class="bi bi-hash"></i> ${roomName}`;
    clearMessages();
    loadRoomMessages(roomId);
}

function clearMessages() {
    const container = document.getElementById('messages-container');
    container.innerHTML = '<div class="text-center text-muted py-5" id="no-messages"><i class="bi bi-chat-dots fs-1"></i><h4>No messages yet</h4><p>Be the first to start the conversation!</p></div>';
}

function showTypingIndicator(username) {
    const indicator = document.getElementById('typing-indicator');
    indicator.textContent = `${username} is typing...`;
    indicator.style.display = 'inline';
}

function hideTypingIndicator() {
    document.getElementById('typing-indicator').style.display = 'none';
}

function showFilePreview(files) {
    const preview = document.getElementById('file-preview');
    preview.innerHTML = '';

    Array.from(files).forEach(file => {
        const fileDiv = document.createElement('div');
        fileDiv.className = 'badge bg-secondary me-2 mb-2';
        fileDiv.innerHTML = `<i class="bi bi-file-earmark"></i> ${file.name} <span onclick="removeFile(this)" style="cursor: pointer;">×</span>`;
        preview.appendChild(fileDiv);
    });

    preview.style.display = 'block';
}

function removeFile(element) {
    element.parentElement.remove();
    const preview = document.getElementById('file-preview');
    if (preview.children.length === 0) {
        preview.style.display = 'none';
        document.getElementById('file-input').value = '';
    }
}

function renderAttachments(attachments) {
    if (!attachments || attachments.length === 0) return '';

    return '<div class="mt-2">' + attachments.map(att => 
        `<a href="/download/${att.id}" class="badge bg-light text-dark me-2">
            <i class="bi bi-download"></i> ${att.original_filename}
        </a>`
    ).join('') + '</div>';
}

// Create room form
if (document.getElementById('create-room-form')) {
    document.getElementById('create-room-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData();
        formData.append('name', document.getElementById('room-name').value);
        formData.append('description', document.getElementById('room-description').value);
        formData.append('is_private', document.getElementById('room-private').checked);

        fetch('/api/create_room', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Add the new room to the UI dynamically
                const roomsContainer = document.querySelector('.list-group');
                const newRoomDiv = document.createElement('div');
                newRoomDiv.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
                newRoomDiv.setAttribute('data-room', data.room.id);
                newRoomDiv.innerHTML = 
                    '<a href="#" class="flex-grow-1 text-decoration-none text-reset" onclick="switchRoom(\'' + data.room.id + '\', \'" + data.room.name + "\')">' +
                    '<i class="bi bi-hash"></i> ' + data.room.name +
                    '</a>' +
                    '<button class="btn btn-sm btn-outline-danger ms-2" onclick="deleteRoom(' + data.room.id + ', \'" + data.room.name + "\')" title="Delete room">' +
                    '<i class="bi bi-trash"></i>' +
                    '</button>';
                // Insert after the first room (General Chat)
                const firstRoom = roomsContainer.querySelector('.list-group-item');
                roomsContainer.insertBefore(newRoomDiv, firstRoom.nextSibling);
                // Clear form and close modal
                document.getElementById('room-name').value = '';
                document.getElementById('room-description').value = '';
                document.getElementById('room-private').checked = false;
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('createRoomModal'));
                modal.hide();
                // Show success message
                alert('Room created successfully!');
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            alert('An error occurred while creating the room.');
        });
    });
}

// Delete room function
function deleteRoom(roomId, roomName) {
    if (confirm(`Are you sure you want to delete the room "${roomName}"? This will permanently delete all messages in this room.`)) {
        fetch(`/api/delete_room/${roomId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the room from the UI
                const roomsContainer = document.querySelector('.list-group');
                const roomToRemove = roomsContainer.querySelector(`[data-room="${roomId}"]`);
                if (roomToRemove) {
                    roomToRemove.remove();
                }
                // Show success message
                alert('Room deleted successfully!');
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            alert('An error occurred while deleting the room.');
        });
    }
}

setAwayAfterInactivity();

// --- Online Users Tooltip ---
const onlineUsersBadge = document.getElementById('online-users');
let onlineUsersTooltip = null;
let onlineUsersTimeout = null;

if (onlineUsersBadge) {
    onlineUsersBadge.addEventListener('mouseenter', function() {
        clearTimeout(onlineUsersTimeout);
        fetch('/api/online_users')
            .then(response => response.json())
            .then(data => {
                if (onlineUsersTooltip) onlineUsersTooltip.remove();
                onlineUsersTooltip = document.createElement('div');
                onlineUsersTooltip.className = 'wispr-tooltip';
                onlineUsersTooltip.style.position = 'absolute';
                onlineUsersTooltip.style.background = '#222';
                onlineUsersTooltip.style.color = '#fff';
                onlineUsersTooltip.style.padding = '8px 14px';
                onlineUsersTooltip.style.borderRadius = '6px';
                onlineUsersTooltip.style.boxShadow = '0 2px 8px rgba(0,0,0,0.2)';
                onlineUsersTooltip.style.fontSize = '1rem';
                onlineUsersTooltip.style.zIndex = 9999;
                onlineUsersTooltip.style.top = (onlineUsersBadge.getBoundingClientRect().bottom + window.scrollY + 8) + 'px';
                onlineUsersTooltip.style.left = (onlineUsersBadge.getBoundingClientRect().left + window.scrollX) + 'px';
                if (data.usernames.length === 0) {
                    onlineUsersTooltip.textContent = 'No users online';
                } else {
                    onlineUsersTooltip.innerHTML = '<strong>Online:</strong><br>' + data.usernames.map(u => `<span style="display:block;">${u}</span>`).join('');
                }
                document.body.appendChild(onlineUsersTooltip);
            });
    });
    onlineUsersBadge.addEventListener('mouseleave', function() {
        onlineUsersTimeout = setTimeout(() => {
            if (onlineUsersTooltip) {
                onlineUsersTooltip.remove();
                onlineUsersTooltip = null;
            }
        }, 100);
    });
}