-- Wispr Database Schema

-- User table
CREATE TABLE user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    profile_pic TEXT,
    status TEXT DEFAULT 'online'
);

-- Project table
CREATE TABLE project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_by INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES user(id)
);

-- Task table
CREATE TABLE task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium',
    due_date DATETIME,
    assigned_to INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES user(id),
    FOREIGN KEY(assigned_to) REFERENCES user(id),
    FOREIGN KEY(project_id) REFERENCES project(id)
);

-- ChatRoom table
CREATE TABLE chat_room (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    is_private BOOLEAN DEFAULT 0,
    created_by INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES user(id)
);

-- ChatMessage table
CREATE TABLE chat_message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL,
    room_id INTEGER,
    recipient_id INTEGER,
    is_direct_message BOOLEAN DEFAULT 0,
    parent_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES user(id),
    FOREIGN KEY(room_id) REFERENCES chat_room(id),
    FOREIGN KEY(recipient_id) REFERENCES user(id),
    FOREIGN KEY(parent_id) REFERENCES chat_message(id)
);

-- MessageAttachment table
CREATE TABLE message_attachment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_type TEXT NOT NULL,
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(message_id) REFERENCES chat_message(id)
);

-- TaskComment table
CREATE TABLE task_comment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES task(id),
    FOREIGN KEY(user_id) REFERENCES user(id)
);

-- TaskActivityLog table
CREATE TABLE task_activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT,
    task_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(task_id) REFERENCES task(id),
    FOREIGN KEY(user_id) REFERENCES user(id)
);

-- MessageReaction table
CREATE TABLE message_reaction (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(message_id) REFERENCES chat_message(id),
    FOREIGN KEY(user_id) REFERENCES user(id),
    UNIQUE(message_id, user_id, emoji)
);

-- Insert a default admin user (password must be set manually)
INSERT INTO user (username, email, password_hash, is_admin) VALUES ('admin', 'admin@example.com', 'scrypt:32768:8:1$VOfpb9n6NzTO9zTg$65091b0a1558a65f18a25e332a783b7a4e52eef7e1ed861203e95346e4ab16e0e09744c5fd4d271e3345a35969fcb0044fd08b559e1a83d3f3855090965f9c15', 1);