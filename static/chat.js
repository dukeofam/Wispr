// Chat logic for Wispr

// The following variables must be set in the template before loading this script:
// window.CHAT_CONTEXT = { username: '...', is_admin: true/false };

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

// Handle receiving messages
socket.on('receive_message', function(data) {
    console.log('Received message:', data);
    addMessageToChat(data);
    document.getElementById('no-messages').style.display = 'none';
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

// Update message form submission to handle replies
if (document.getElementById('message-form')) {
    document.getElementById('message-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const messageInput = document.getElementById('message-input');
        const message = messageInput.value.trim();

        if (message) {
            const data = {
                message: message,
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

// Patch addMessageToChat to show status dot next to username (always use current status)
window.origAddMessageToChat_status = window.addMessageToChat;
window.addMessageToChat = function(data) {
    // Store the original username for status lookup
    data.raw_username = data.raw_username || data.username;
    const uname = (data.raw_username || data.username).toLowerCase();
    // No status dot in chat messages
    const messagesContainer = document.getElementById('messages-container');
    if (!data || typeof data !== 'object' || typeof data.username === 'undefined' || typeof data.content === 'undefined') {
        const msg = (data && data.message) ? data.message : '[system message]';
        const messageDiv = document.createElement('div');
        messageDiv.className = 'text-center text-muted mb-3';
        messageDiv.innerHTML = `<small><i>${escapeHtml(msg)}</i></small>`;
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        return;
    }
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
        parentPreview = `
            <div class="reply-preview mb-2 p-2 bg-light rounded" style="font-size: 0.9em; border-left: 3px solid #007bff;">
                <small class="text-muted">Replying to <strong>${escapeHtml(data.parent_username)}</strong></small>
                <div class="text-truncate">${escapeHtml(data.parent_content)}</div>
            </div>
        `;
    }
    let avatarUrl = data.profile_pic ? `/uploads/${data.profile_pic}` : '/static/default_avatar.png';
    messageDiv.innerHTML = `
        ${parentPreview}
        <div class="d-flex align-items-center mb-1">
            <img src="${avatarUrl}" class="rounded-circle me-2" width="32" height="32" alt="avatar">
            <strong class="me-2">${escapeHtml(data.username)}</strong>
            <span class="text-muted small">${timestamp}</span>
            <div class="ms-auto message-actions">
                ${isOwnMessage ? `
                <button class="btn btn-sm btn-outline-primary me-1" onclick="editMessage(${data.id}, '${escapeHtml(data.content).replace(/'/g, "\\'")}')">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteMessage(${data.id})">
                    <i class="bi bi-trash"></i>
                </button>
                ` : ''}
            </div>
        </div>
        <div class="message-content mt-2">
            <p class="mb-0" id="message-content-${data.id}">${escapeHtml(data.content).replace(/\n/g, '<br>')}</p>
            ${data.attachments ? renderAttachments(data.attachments) : ''}
        </div>
    `;
    messageDiv.addEventListener('click', function(e) {
        if (e.target.closest('.message-actions') || e.target.closest('button')) {
            return;
        }
        if (isOwnMessage) {
            document.querySelectorAll('.message-item').forEach(item => {
                item.classList.remove('selected');
            });
            this.classList.toggle('selected');
        }
    });
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

function switchRoom(roomId, roomName) {
    // Update active room
    document.querySelectorAll('.list-group-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-room="${roomId}"]`).classList.add('active');

    // Leave current room and join new one
    socket.emit('leave_room', {room: currentRoom});
    socket.emit('join_room', {room: roomId});

    currentRoom = roomId;
    currentDMUser = null;
    document.getElementById('chat-title').innerHTML = `<i class="bi bi-hash"></i> ${roomName}`;

    // Clear messages and load room messages
    clearMessages();
    loadRoomMessages(roomId);
}

function switchToDM(userId, username) {
    // Clear active room
    document.querySelectorAll('.list-group-item').forEach(item => {
        item.classList.remove('active');
    });

    currentDMUser = userId;
    currentRoom = null;
    document.getElementById('chat-title').innerHTML = `<i class="bi bi-person-circle"></i> ${username}`;

    // Clear messages and load DM
    clearMessages();
    loadDirectMessages(userId);
}

function clearMessages() {
    const container = document.getElementById('messages-container');
    container.innerHTML = '<div class="text-center text-muted py-5" id="no-messages"><i class="bi bi-chat-dots fs-1"></i><h4>No messages yet</h4><p>Be the first to start the conversation!</p></div>';
}

function loadRoomMessages(roomId) {
    fetch(`/api/room_messages/${roomId}`)
        .then(response => response.json())
        .then(messages => {
            if (messages.length > 0) {
                document.getElementById('no-messages').style.display = 'none';
                messages.forEach(message => addMessageToChat(message));
            }
        });
}

function loadDirectMessages(userId) {
    fetch(`/api/direct_messages/${userId}`)
        .then(response => response.json())
        .then(messages => {
            if (messages.length > 0) {
                document.getElementById('no-messages').style.display = 'none';
                messages.forEach(message => addMessageToChat(message));
            }
        });
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