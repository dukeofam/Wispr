// Chat logic for Wispr

// The following variables must be set in the template before loading this script:
// window.CHAT_CONTEXT = { username: '...', is_admin: true/false };

// Initialize Socket.IO
const socket = io();
let currentRoom = 'general';
let currentDMUser = null;
let typingTimer;
let isTyping = false;

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

// Message form submission
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

            console.log('Sending message:', data);
            socket.emit('send_message', data);
            messageInput.value = '';

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

function addMessageToChat(data) {
    const messagesContainer = document.getElementById('messages-container');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message-item border-bottom pb-3 mb-3';
    messageDiv.setAttribute('data-message-id', data.id);

    const isOwnMessage = data.username === window.CHAT_CONTEXT.username;
    const timestamp = new Date(data.timestamp).toLocaleString();

    messageDiv.innerHTML = `
        <div class="d-flex justify-content-between align-items-start">
            <div>
                <strong>${escapeHtml(data.username)}</strong>
                ${data.is_admin ? '<span class="badge bg-danger ms-1">Admin</span>' : ''}
                <small class="text-muted ms-2">${timestamp}</small>
            </div>
            ${isOwnMessage ? `
            <div class="message-actions">
                <button class="btn btn-sm btn-outline-primary me-1" onclick="editMessage(${data.id}, '${escapeHtml(data.content).replace(/'/g, "\\'")}')">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-sm btn-outline-danger" onclick="deleteMessage(${data.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
            ` : ''}
        </div>
        <div class="message-content mt-2">
            <p class="mb-0" id="message-content-${data.id}">${escapeHtml(data.content).replace(/\n/g, '<br>')}</p>
            ${data.attachments ? renderAttachments(data.attachments) : ''}
        </div>
    `;

    // Add click handler
    messageDiv.addEventListener('click', function(e) {
        if (e.target.closest('.message-actions') || e.target.closest('button')) {
            return; // Don't toggle if clicking on action buttons
        }
        if (isOwnMessage) {
            // Clear other selected messages
            document.querySelectorAll('.message-item').forEach(item => {
                item.classList.remove('selected');
            });
            // Toggle selected state
            this.classList.toggle('selected');
        }
    });

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

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
                // If currently in the deleted room, switch to general
                if (currentRoom == roomId) {
                    switchRoom('general', 'General Chat');
                }
                // Remove the room from the UI
                const roomElement = document.querySelector(`[data-room="${roomId}"]`);
                if (roomElement) {
                    roomElement.remove();
                }
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

// Clear all chat data function
function clearAllChatData() {
    if (confirm('Are you sure you want to delete all chat data? This action cannot be undone.')) {
        fetch('/api/clear_all_chat_data', {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Clear messages from UI
                clearMessages();
                alert('All chat data has been cleared.');
            } else {
                alert('Error: ' + data.error);
            }
        })
        .catch(error => {
            alert('An error occurred while clearing all chat data.');
        });
    }
}

// Load initial messages for general room
loadRoomMessages('general');

// Edit message function
function editMessage(messageId, currentContent) {
    const newContent = prompt('Edit your message:', currentContent.replace(/<br>/g, '\n'));
    if (newContent !== null && newContent.trim() !== '' && newContent !== currentContent) {
        fetch(`/api/edit_message/${messageId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                content: newContent
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update the message content in the UI
                const messageContent = document.getElementById(`message-content-${messageId}`);
                if (messageContent) {
                    messageContent.innerHTML = newContent.replace(/\n/g, '<br>');
                }
                // Clear selection
                document.querySelector(`[data-message-id="${messageId}"]`).classList.remove('selected');
            } else {
                alert('Error editing message: ' + data.error);
            }
        })
        .catch(error => {
            alert('An error occurred while editing the message.');
        });
    }
}

// Delete message function
function deleteMessage(messageId) {
    if (confirm('Are you sure you want to delete this message?')) {
        fetch(`/api/delete_message/${messageId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove the message from the UI
                const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
                if (messageElement) {
                    messageElement.remove();
                }
            } else {
                alert('Error deleting message: ' + data.error);
            }
        })
        .catch(error => {
            alert('An error occurred while deleting the message.');
        });
    }
}

// Close message actions when clicking elsewhere
document.addEventListener('click', function(e) {
    if (!e.target.closest('.message-item')) {
        document.querySelectorAll('.message-item').forEach(item => {
            item.classList.remove('selected');
        });
    }
});

// Load initial online count
fetch('/api/online_count')
    .then(response => response.json())
    .then(data => {
        document.getElementById('online-users').textContent = data.count + ' online';
    }); 