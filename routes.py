from flask import render_template, request, redirect, url_for, session, flash, jsonify, Response, send_from_directory
from flask_socketio import emit, join_room, leave_room
from app import app, db, socketio, limiter
from models import User, ChatMessage, Task, ChatRoom, MessageAttachment, TaskActivityLog, MessageReaction, Project
from werkzeug.security import generate_password_hash
from datetime import datetime
from sqlalchemy import desc
import logging
import re
from werkzeug.utils import secure_filename
from PIL import Image
import os

# Store online users
online_users = set()

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
PROFILE_PIC_FOLDER = os.path.join('static', 'profile_pics')
MAX_PROFILE_PIC_SIZE = 1 * 1024 * 1024  # 1MB
PROFILE_PIC_DIM = 256


def login_required(f):
    """Decorator to require login for protected routes"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


def moderator_required(f):
    """Decorator to require moderator or admin privileges"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role not in ('admin', 'moderator'):
            flash('Moderator or admin access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session.permanent = True  # Enable session timeout
            session.modified = True
            flash('Login successful', 'success')
            logging.info(f"User login: {username} (id={user.id}) from {request.remote_addr}")
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            logging.warning(f"Failed login attempt for username: {username} from {request.remote_addr}")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    session.modified = True
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    # Get recent messages and tasks for dashboard overview
    recent_messages = ChatMessage.query.order_by(
        ChatMessage.timestamp.desc()).limit(5).all()
    recent_tasks = Task.query.order_by(Task.updated_at.desc()).limit(5).all()

    # Task statistics
    total_tasks = Task.query.count()
    todo_tasks = Task.query.filter_by(status='todo').count()
    in_progress_tasks = Task.query.filter_by(status='in_progress').count()
    done_tasks = Task.query.filter_by(status='done').count()

    return render_template('dashboard.html',
                           recent_messages=recent_messages,
                           recent_tasks=recent_tasks,
                           total_tasks=total_tasks,
                           todo_tasks=todo_tasks,
                           in_progress_tasks=in_progress_tasks,
                           done_tasks=done_tasks)


@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    # Create default general room if it doesn't exist
    general_room = ChatRoom.query.filter_by(name='General Chat').first()
    if not general_room:
        general_room = ChatRoom(
            name='General Chat',
            description='Default chat room for all team members',
            created_by=session['user_id']
        )
        db.session.add(general_room)
        db.session.commit()
    
    # Get all chat rooms (including General Chat) and users
    chat_rooms = ChatRoom.query.filter_by(is_private=False).order_by(
        ChatRoom.name == 'General Chat').all()
    users = User.query.filter(User.id != session['user_id']).all()
    
    return render_template('chat.html', chat_rooms=chat_rooms, users=users)


@app.route('/api/messages')
@login_required
@limiter.limit("60 per minute")
def get_messages():
    """API endpoint to fetch latest messages for real-time updates"""
    since = request.args.get('since')

    query = ChatMessage.query.order_by(ChatMessage.timestamp.asc())

    if since:
        try:
            from datetime import datetime
            since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.filter(ChatMessage.timestamp > since_date)
        except:
            pass

    messages = query.all()

    return jsonify([{
        'id': msg.id,
        'content': msg.content,
        'username': msg.author.username,
        'is_admin': msg.author.role == 'admin',
        'status': msg.author.status or 'offline',
        'timestamp': msg.timestamp.isoformat(),
        'profile_pic': msg.author.profile_pic,
        'attachments': [{
            'id': att.id,
            'original_filename': att.original_filename,
            'file_size': att.file_size
        } for att in msg.attachments]
    } for msg in messages])


@app.route('/api/room_messages/<room_id>')
@login_required
@limiter.limit("60 per minute")
def get_room_messages(room_id):
    """Get messages for a specific room"""
    if room_id == 'general':
        room = ChatRoom.query.filter_by(name='General Chat').first()
        if not room:
            return jsonify([])
        room_id = room.id
    else:
        try:
            room_id = int(room_id)
        except ValueError:
            return jsonify([])
    
    messages = ChatMessage.query.filter_by(
        room_id=room_id, 
        is_direct_message=False
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return jsonify([{
        'id': msg.id,
        'content': msg.content,
        'username': msg.author.username,
        'is_admin': msg.author.role == 'admin',
        'status': msg.author.status or 'offline',
        'timestamp': msg.timestamp.isoformat(),
        'parent_id': msg.parent_id,
        'parent_username': msg.parent.author.username if msg.parent else None,
        'parent_content': msg.parent.content[:50] + ('...' if msg.parent and len(msg.parent.content) > 50 else '') if msg.parent else None,
        'profile_pic': msg.author.profile_pic,
        'attachments': [{
            'id': att.id,
            'original_filename': att.original_filename,
            'file_size': att.file_size
        } for att in msg.attachments]
    } for msg in messages])


@app.route('/api/online_count')
@login_required
def get_online_count():
    """Get count of online users"""
    return jsonify({'count': len(online_users)})


@app.route('/api/direct_messages/<int:user_id>')
@login_required
@limiter.limit("60 per minute")
def get_direct_messages(user_id):
    """Get direct messages between current user and specified user"""
    messages = ChatMessage.query.filter(
        ChatMessage.is_direct_message == True,
        db.or_(
            db.and_(ChatMessage.user_id == session['user_id'], ChatMessage.recipient_id == user_id),
            db.and_(ChatMessage.user_id == user_id, ChatMessage.recipient_id == session['user_id'])
        )
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return jsonify([{
        'id': msg.id,
        'content': msg.content,
        'username': msg.author.username,
        'is_admin': msg.author.role == 'admin',
        'status': msg.author.status or 'offline',
        'timestamp': msg.timestamp.isoformat(),
        'parent_id': msg.parent_id,
        'parent_username': msg.parent.author.username if msg.parent else None,
        'parent_content': msg.parent.content[:50] + ('...' if msg.parent and len(msg.parent.content) > 50 else '') if msg.parent else None,
        'profile_pic': msg.author.profile_pic,
        'attachments': [{
            'id': att.id,
            'original_filename': att.original_filename,
            'file_size': att.file_size
        } for att in msg.attachments]
    } for msg in messages])


@app.route('/api/create_room', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def create_room():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    is_private = request.form.get('is_private') == 'true'
    
    if not name:
        return jsonify({'success': False, 'error': 'Room name is required'})
    
    # Check if room already exists
    existing_room = ChatRoom.query.filter_by(name=name).first()
    if existing_room:
        return jsonify({'success': False, 'error': 'A room with this name already exists'})
    
    # Create new room
    new_room = ChatRoom(
        name=name,
        description=description,
        is_private=is_private,
        created_by=session['user_id']
    )
    
    try:
        db.session.add(new_room)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'room': {
                'id': new_room.id,
                'name': new_room.name,
                'description': new_room.description,
                'is_private': new_room.is_private
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/delete_room/<int:room_id>', methods=['DELETE'])
@admin_required
@limiter.limit("10 per hour")
def delete_room(room_id):
    """Delete a chat room (admin only)"""
    room = ChatRoom.query.get_or_404(room_id)
    
    # Prevent deletion of General Chat room
    if room.name == 'General Chat':
        return jsonify({'success': False, 'error': 'Cannot delete the General Chat room'})
    
    # Delete all messages in the room first
    ChatMessage.query.filter_by(room_id=room_id).delete()
    
    # Delete the room
    db.session.delete(room)
    db.session.commit()
    
    logging.info(f"Admin {session['username']} (id={session['user_id']}) deleted room: {room_id}")
    
    return jsonify({'success': True, 'message': f'Room "{room.name}" deleted successfully'})


@app.route('/api/clear_all_chat_data', methods=['DELETE'])
@admin_required
def clear_all_chat_data():
    """Clear all chat messages and rooms except General Chat (admin only)"""
    try:
        # Delete all message attachments first
        MessageAttachment.query.delete()
        
        # Delete all chat messages
        ChatMessage.query.delete()
        
        # Delete all chat rooms except General Chat
        ChatRoom.query.filter(ChatRoom.name != 'General Chat').delete()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'All chat data cleared successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@app.route('/upload_file', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def upload_file():
    """Handle file uploads for chat messages"""
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'})
    
    files = request.files.getlist('files')
    uploaded_files = []
    
    # Create uploads directory if it doesn't exist
    import os
    upload_dir = os.path.join(app.root_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    # Allowed file extensions and MIME types
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.txt', '.docx'}
    ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'application/pdf', 'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}

    for file in files:
        if file.filename:
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in ALLOWED_EXTENSIONS or (file.content_type and file.content_type not in ALLOWED_MIME_TYPES):
                logging.warning(f"Blocked upload of disallowed file type: {file.filename} ({file.content_type}) by user {session['username']} (id={session['user_id']})")
                continue  # Skip disallowed file types
            # Generate unique filename
            import uuid
            unique_filename = str(uuid.uuid4()) + file_extension
            file_path = os.path.join(upload_dir, unique_filename)
            # Save file
            file.save(file_path)
            # Get file size
            file_size = os.path.getsize(file_path)
            uploaded_files.append({
                'filename': unique_filename,
                'original_filename': file.filename,
                'file_size': file_size,
                'file_type': file.content_type or 'application/octet-stream'
            })
    logging.info(f"User {session['username']} (id={session['user_id']}) uploaded a file from {request.remote_addr}")
    return jsonify({'success': True, 'files': uploaded_files})


@app.route('/download/<int:attachment_id>')
@login_required
def download_file(attachment_id):
    """Download file attachment"""
    attachment = MessageAttachment.query.get_or_404(attachment_id)
    
    import os
    from flask import send_file
    upload_dir = os.path.join(app.root_path, 'uploads')
    file_path = os.path.join(upload_dir, attachment.filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=attachment.original_filename)
    else:
        flash('File not found', 'error')
        return redirect(url_for('chat'))


@app.route('/api/edit_message/<int:message_id>', methods=['PUT'])
@login_required
def edit_message(message_id):
    """Edit a message (only by the author)"""
    message = ChatMessage.query.get_or_404(message_id)
    
    # Check if user is the author
    if message.user_id != session['user_id']:
        return jsonify({'success': False, 'error': 'You can only edit your own messages'})
    
    data = request.get_json()
    new_content = data.get('content', '').strip()
    
    if not new_content:
        return jsonify({'success': False, 'error': 'Message content cannot be empty'})
    
    message.content = new_content
    message.timestamp = datetime.utcnow()  # Update timestamp to show it was edited
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Message updated successfully'})


@app.route('/api/delete_message/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(message_id):
    """Delete a message (only by the author or admin)"""
    message = ChatMessage.query.get_or_404(message_id)
    
    # Check if user is the author or admin
    if message.user_id != session['user_id'] and session.get('role') != 'admin':
        return jsonify({'success': False, 'error': 'You can only delete your own messages'})
    
    # Delete message attachments first
    MessageAttachment.query.filter_by(message_id=message_id).delete()
    
    # Delete the message
    db.session.delete(message)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Message deleted successfully'})


@app.route('/kanban', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour", methods=["POST"])
def kanban():
    if request.method == 'POST':
        logging.info(f"User {session['username']} (id={session['user_id']}) modified Kanban board from {request.remote_addr}")
        title = request.form['title'].strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        assigned_to = request.form.get('assigned_to') or None
        due_date_str = request.form.get('due_date')
        project_id = request.form.get('project_id')
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                pass

        if not project_id:
            flash('Project is required for each task.', 'error')
            return redirect(url_for('kanban'))

        if title:
            task = Task(title=title,
                        description=description,
                        priority=priority,
                        assigned_to=assigned_to,
                        due_date=due_date,
                        user_id=session['user_id'],
                        project_id=project_id)
            db.session.add(task)
            db.session.commit()
            
            # Log task creation
            from models import TaskActivityLog
            import json
            activity = TaskActivityLog(
                action='task_created',
                details=json.dumps({'title': title}),
                task_id=task.id,
                user_id=session['user_id']
            )
            db.session.add(activity)
            db.session.commit()
            
            flash('Task created successfully', 'success')
        return redirect(url_for('kanban'))

    # Get all users for assignment dropdown
    users = User.query.all()

    # Get all projects
    projects = Project.query.order_by(Project.created_at.desc()).all()

    # Query tasks with joined project for display
    todo_tasks = Task.query.filter_by(status='todo').order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    in_progress_tasks = Task.query.filter_by(status='in_progress').order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    done_tasks = Task.query.filter_by(status='done').order_by(Task.updated_at.desc()).all()

    return render_template('kanban.html',
                           todo_tasks=todo_tasks,
                           in_progress_tasks=in_progress_tasks,
                           done_tasks=done_tasks,
                           users=users,
                           projects=projects,
                           now=datetime.utcnow())


@app.route('/update_task_status/<int:task_id>/<status>')
@login_required
def update_task_status(task_id, status):
    task = Task.query.get_or_404(task_id)
    if status in ['todo', 'in_progress', 'done']:
        old_status = task.status
        task.status = status
        task.updated_at = datetime.utcnow()
        
        # Log status change
        from models import TaskActivityLog
        import json
        activity = TaskActivityLog(
            action='status_changed',
            details=json.dumps({'from': old_status, 'to': status}),
            task_id=task_id,
            user_id=session['user_id']
        )
        db.session.add(activity)
        db.session.commit()
        
        flash('Task status updated', 'success')
    return redirect(url_for('kanban'))


@app.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    # Only allow task creator or admin to delete
    if task.user_id == session['user_id'] or session.get('role') == 'admin':
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted', 'success')
    else:
        flash('You can only delete your own tasks', 'error')
    return redirect(url_for('kanban'))


@app.route('/api/task/<int:task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
        'creator': task.creator.username,
        'assignee': task.assignee.username if task.assignee else None,
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat()
    }


@app.route('/api/task/<int:task_id>/comment', methods=['POST'])
@login_required
def add_task_comment(task_id):
    """Add a comment to a task"""
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'success': False, 'error': 'Comment cannot be empty'})
    
    from models import TaskComment, TaskActivityLog
    import json
    
    comment = TaskComment(
        content=content,
        task_id=task_id,
        user_id=session['user_id']
    )
    db.session.add(comment)
    
    # Log comment activity
    activity = TaskActivityLog(
        action='commented',
        details=json.dumps({'comment': content[:100]}),
        task_id=task_id,
        user_id=session['user_id']
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'comment': {
            'id': comment.id,
            'content': comment.content,
            'author': comment.author.username,
            'created_at': comment.created_at.isoformat()
        }
    })


@app.route('/api/task/<int:task_id>/comments')
@login_required
def get_task_comments(task_id):
    """Get all comments for a task"""
    task = Task.query.get_or_404(task_id)
    comments = task.comments.order_by('created_at').all()
    
    return jsonify([{
        'id': comment.id,
        'content': comment.content,
        'author': comment.author.username,
        'created_at': comment.created_at.isoformat()
    } for comment in comments])


@app.route('/api/task/<int:task_id>/activity', methods=['GET'])
@login_required
def get_task_activity(task_id):
    """Get activity log for a task"""
    task = Task.query.get_or_404(task_id)
    activities = task.activity_logs.order_by(desc(TaskActivityLog.created_at)).all()
    
    return jsonify([{
        'id': activity.id,
        'action': activity.action,
        'details': activity.details,
        'user': activity.user.username,
        'created_at': activity.created_at.isoformat()
    } for activity in activities])


@app.route('/api/task/<int:task_id>/assign', methods=['POST'])
@login_required
def assign_task(task_id):
    """Assign a task to a user"""
    task = Task.query.get_or_404(task_id)
    data = request.get_json()
    user_id = data.get('user_id')
    
    old_assignee = task.assignee.username if task.assignee else 'Unassigned'
    task.assigned_to = user_id if user_id else None
    task.updated_at = datetime.utcnow()
    
    # Log assignment activity
    from models import TaskActivityLog
    import json
    new_assignee = task.assignee.username if task.assignee else 'Unassigned'
    activity = TaskActivityLog(
        action='assigned',
        details=json.dumps({'from': old_assignee, 'to': new_assignee}),
        task_id=task_id,
        user_id=session['user_id']
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True})


@app.route('/admin')
@admin_required
def admin():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin.html', users=users)


@app.route('/admin/create_user', methods=['POST'])
@admin_required
@limiter.limit("10 per hour")
def create_user():
    username = request.form['username'].strip()
    email = request.form['email'].strip()
    password = request.form['password'].strip()
    role = request.form.get('role', 'member')
    if role not in ('admin', 'moderator', 'member'):
        role = 'member'

    if not username or not email or not password:
        flash('All fields are required', 'error')
        return redirect(url_for('admin'))
    if len(password) < 8:
        flash('Password must be at least 8 characters long', 'error')
        return redirect(url_for('admin'))

    # Check if user already exists
    existing_user = User.query.filter((User.username == username)
                                      | (User.email == email)).first()
    if existing_user:
        flash('Username or email already exists', 'error')
        return redirect(url_for('admin'))

    user = User(username=username, email=email, role=role)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()
    flash('User created successfully', 'success')
    logging.info(f"Admin {session['username']} (id={session['user_id']}) created user: {username}")
    return redirect(url_for('admin'))


@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
@limiter.limit("10 per hour")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    # Prevent deleting the default admin account if no other admin exists
    if user.username == 'admin':
        other_admins = User.query.filter(User.role == 'admin').count()
        if other_admins == 1:  # Only one admin left
            flash('Cannot delete the default admin account unless another admin exists', 'error')
            return redirect(url_for('admin'))
    # Prevent deleting yourself
    if user.id == session['user_id']:
        flash('You cannot delete your own account', 'error')
        return redirect(url_for('admin'))
    # Handle user's chat rooms
    chat_rooms = ChatRoom.query.filter_by(created_by=user_id).all()
    for room in chat_rooms:
        # If applicable, you can either delete these rooms or reassign them to another admin
        db.session.delete(room)  # or room.created_by = new_admin_id
    # Delete related data
    ChatMessage.query.filter_by(user_id=user_id).delete()
    Task.query.filter_by(user_id=user_id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    logging.info(f"Admin {session['username']} (id={session['user_id']}) deleted user: {user.username} (id={user.id})")
    return redirect(url_for('admin'))


@app.route('/admin/change_role/<int:user_id>', methods=['POST'])
@admin_required
def change_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role not in ('admin', 'moderator', 'member'):
        flash('Invalid role', 'error')
        return redirect(url_for('admin'))
    # Prevent demoting yourself from admin
    if user.id == session['user_id'] and user.role == 'admin' and new_role != 'admin':
        flash('You cannot change your own admin role', 'error')
        return redirect(url_for('admin'))
    user.role = new_role
    db.session.commit()
    flash('User role updated', 'success')
    return redirect(url_for('admin'))


# Context processor to make current user available in templates
@app.context_processor
def inject_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return dict(current_user=user)
    return dict(current_user=None)


# WebSocket Events for Real-time Chat
@socketio.on('connect')
def on_connect():
    print(f"Client connected, session: {session}")
    if 'user_id' not in session:
        print("No user_id in session during connect")
        return False

    user = User.query.get(session['user_id'])
    if user:
        online_users.add(user.id)
        # Join user's personal room for direct messages
        join_room(f"user_{user.id}")
        print(f"User {user.username} connected and joined room user_{user.id}")
        emit('user_connected', {
            'username': user.username,
            'message': f'{user.username} joined the chat'
        }, broadcast=True)
        # Broadcast updated online count
        emit('online_count_updated', {'count': len(online_users)}, broadcast=True)
    else:
        print("User not found during connect")
        return False


@socketio.on('disconnect')
def on_disconnect():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            online_users.discard(user.id)
            # Leave user's personal room
            leave_room(f"user_{user.id}")
            emit('user_disconnected', {
                'username': user.username,
                'message': f'{user.username} left the chat'
            }, broadcast=True)
            # Broadcast updated online count
            emit('online_count_updated', {'count': len(online_users)}, broadcast=True)


@socketio.on('join_room')
def on_join_room(data):
    if 'user_id' not in session:
        return
    
    room_name = data.get('room')
    if room_name == 'general':
        # Find general room ID
        general_room = ChatRoom.query.filter_by(name='General Chat').first()
        if general_room:
            room_name = f"room_{general_room.id}"
        else:
            # Create general room if it doesn't exist
            user = User.query.get(session['user_id'])
            general_room = ChatRoom(
                name='General Chat',
                description='Default chat room for all team members',
                created_by=user.id
            )
            db.session.add(general_room)
            db.session.commit()
            room_name = f"room_{general_room.id}"
    elif room_name and room_name.isdigit():
        room_name = f"room_{room_name}"
    else:
        return
    
    join_room(room_name)
    user = User.query.get(session['user_id'])
    emit('user_connected', {
        'username': user.username,
        'message': f'{user.username} joined the room'
    }, room=room_name)


@socketio.on('leave_room')
def on_leave_room(data):
    if 'user_id' not in session:
        return
    
    room_name = data.get('room')
    
    # Skip leaving room for direct messages (room_name is None)
    if room_name is None:
        return
    
    if room_name == 'general':
        general_room = ChatRoom.query.filter_by(name='General Chat').first()
        if general_room:
            room_name = f"room_{general_room.id}"
        else:
            return
    elif str(room_name).isdigit():
        room_name = f"room_{room_name}"
    else:
        return
    
    leave_room(room_name)


@socketio.on('send_message')
def handle_message(data):
    if 'user_id' not in session:
        print("No user_id in session")
        return

    content = data.get('message', '').strip()
    room_id = data.get('room')
    recipient_id = data.get('recipient_id')
    
    print(f"Received message: content='{content}', room_id='{room_id}', recipient_id='{recipient_id}'")
    
    if not content:
        print("Empty content")
        return

    user = User.query.get(session['user_id'])
    if not user:
        print("User not found")
        return

    # --- Mention detection ---
    def extract_mentions(text):
        # Matches @username (alphanumeric and underscores)
        return set(re.findall(r'@([\w\d_]+)', text))

    mentioned_usernames = extract_mentions(content)
    mentioned_users = []
    if mentioned_usernames:
        mentioned_users = User.query.filter(User.username.in_(mentioned_usernames)).all()

    # Handle direct messages
    if recipient_id:
        message = ChatMessage(
            content=content, 
            user_id=user.id,
            recipient_id=recipient_id,
            is_direct_message=True
        )
        db.session.add(message)
        db.session.commit()
        
        # Send to both users
        message_data = {
            'id': message.id,
            'content': message.content,
            'username': user.username,
            'is_admin': user.role == 'admin',
            'status': user.status or 'offline',
            'timestamp': message.timestamp.isoformat(),
            'profile_pic': user.profile_pic,
            'attachments': []
        }
        
        print(f"Emitting direct message to users {user.id} and {recipient_id}")
        emit('receive_message', message_data, room=f"user_{user.id}")
        emit('receive_message', message_data, room=f"user_{recipient_id}")
        # Mention notifications for DMs
        for mentioned in mentioned_users:
            if mentioned.id != user.id:
                emit('mention_notification', {
                    'from': user.username,
                    'message': content
                }, room=f"user_{mentioned.id}")
        return

    # Handle room messages
    if room_id == 'general':
        general_room = ChatRoom.query.filter_by(name='General Chat').first()
        if general_room:
            room_id = general_room.id
        else:
            # Create general room if it doesn't exist
            general_room = ChatRoom(
                name='General Chat',
                description='Default chat room for all team members',
                created_by=user.id
            )
            db.session.add(general_room)
            db.session.commit()
            room_id = general_room.id
    
    # Convert room_id to int if it's a string
    try:
        room_id = int(room_id)
    except (ValueError, TypeError):
        print(f"Invalid room_id: {room_id}")
        return
    
    message = ChatMessage(
        content=content, 
        user_id=user.id,
        room_id=room_id,
        is_direct_message=False
    )
    db.session.add(message)
    db.session.commit()

    # Broadcast message to room
    room_name = f"room_{room_id}"
    message_data = {
        'id': message.id,
        'content': message.content,
        'username': user.username,
        'is_admin': user.role == 'admin',
        'status': user.status or 'offline',
        'timestamp': message.timestamp.isoformat(),
        'profile_pic': user.profile_pic,
        'attachments': []
    }
    
    print(f"Emitting room message to room {room_name}")
    emit('receive_message', message_data, room=room_name)
    # Mention notifications for room messages
    for mentioned in mentioned_users:
        if mentioned.id != user.id:
            emit('mention_notification', {
                'from': user.username,
                'message': content,
                'room': room_name
            }, room=f"user_{mentioned.id}")


@socketio.on('start_typing')
def handle_start_typing(data):
    if 'user_id' not in session:
        return
    
    user = User.query.get(session['user_id'])
    room_name = data.get('room')
    
    # Skip typing indicators for direct messages (room_name is None)
    if room_name is None:
        return
    
    if room_name == 'general':
        general_room = ChatRoom.query.filter_by(name='General Chat').first()
        if general_room:
            room_name = f"room_{general_room.id}"
        else:
            return
    elif str(room_name).isdigit():
        room_name = f"room_{room_name}"
    else:
        return
    
    emit('user_typing', {
        'username': user.username
    }, room=room_name, include_self=False)


@socketio.on('stop_typing')
def handle_stop_typing(data):
    if 'user_id' not in session:
        return
    
    room_name = data.get('room')
    
    # Skip typing indicators for direct messages (room_name is None)
    if room_name is None:
        return
    
    if room_name == 'general':
        general_room = ChatRoom.query.filter_by(name='General Chat').first()
        if general_room:
            room_name = f"room_{general_room.id}"
        else:
            return
    elif str(room_name).isdigit():
        room_name = f"room_{room_name}"
    else:
        return
    
    emit('user_stopped_typing', {}, room=room_name, include_self=False)


@app.route('/healthz')
def health_check():
    return 'OK', 200


@limiter.request_filter
def ip_whitelist():
    # Allow health checks from localhost without rate limiting
    return request.remote_addr == '127.0.0.1'


@app.errorhandler(429)
def ratelimit_handler(e):
    return Response('Rate limit exceeded. Please try again later.', status=429)


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


@app.route('/api/users')
@login_required
def get_users():
    users = User.query.with_entities(User.id, User.username, User.status, User.profile_pic).all()
    return jsonify([
        {
            'id': u.id,
            'username': u.username,
            'status': u.status or 'offline',
            'profile_pic': u.profile_pic
        } for u in users
    ])


@socketio.on('add_reaction')
def handle_add_reaction(data):
    print(f"ADD_REACTION: {data}")
    if 'user_id' not in session:
        print("No user_id in session")
        return
    user_id = session['user_id']
    message_id = data.get('message_id')
    emoji = data.get('emoji')
    ALLOWED_EMOJIS = {'👍', '😂', '😢', '❤️', '🎉'}
    if not message_id or emoji not in ALLOWED_EMOJIS:
        print(f"Invalid data: message_id={message_id}, emoji={emoji}")
        return
    message = ChatMessage.query.get(message_id)
    if not message:
        print(f"Message not found: {message_id}")
        return
    # Only allow reactions in rooms the user is in
    room_id = message.room_id
    if not room_id:
        print("Message has no room_id")
        return
    # Add or update reaction
    existing = MessageReaction.query.filter_by(message_id=message_id, user_id=user_id, emoji=emoji).first()
    if not existing:
        reaction = MessageReaction(message_id=message_id, user_id=user_id, emoji=emoji)
        db.session.add(reaction)
        db.session.commit()
        print(f"Added reaction: user={user_id}, message={message_id}, emoji={emoji}")
    else:
        print(f"Reaction already exists: user={user_id}, message={message_id}, emoji={emoji}")
    # Broadcast updated reactions
    broadcast_reactions_update(message_id, room_id)


@socketio.on('remove_reaction')
def handle_remove_reaction(data):
    print(f"REMOVE_REACTION: {data}")
    if 'user_id' not in session:
        print("No user_id in session")
        return
    user_id = session['user_id']
    message_id = data.get('message_id')
    emoji = data.get('emoji')
    ALLOWED_EMOJIS = {'👍', '😂', '😢', '❤️', '🎉'}
    if not message_id or emoji not in ALLOWED_EMOJIS:
        print(f"Invalid data: message_id={message_id}, emoji={emoji}")
        return
    from models import MessageReaction
    reaction = MessageReaction.query.filter_by(message_id=message_id, user_id=user_id, emoji=emoji).first()
    if reaction:
        db.session.delete(reaction)
        db.session.commit()
        print(f"Removed reaction: user={user_id}, message={message_id}, emoji={emoji}")
    else:
        print(f"Reaction not found: user={user_id}, message={message_id}, emoji={emoji}")
    # Find the message to get the room
    message = ChatMessage.query.get(message_id)
    if message and message.room_id:
        broadcast_reactions_update(message_id, message.room_id)


def broadcast_reactions_update(message_id, room_id):
    from models import MessageReaction
    # Get all reactions for this message
    reactions = MessageReaction.query.filter_by(message_id=message_id).all()
    # Format: {emoji: [user_id, ...]}
    reaction_counts = {}
    for r in reactions:
        reaction_counts.setdefault(r.emoji, []).append(r.user_id)
    emit('reactions_update', {
        'message_id': message_id,
        'reactions': {emoji: {'count': len(users), 'user_ids': users} for emoji, users in reaction_counts.items()}
    }, room=f"room_{room_id}")


@socketio.on('reply_message')
def handle_reply_message(data):
    if 'user_id' not in session:
        print("No user_id in session")
        return

    content = data.get('message', '').strip()
    parent_id = data.get('parent_id')
    room_id = data.get('room')
    recipient_id = data.get('recipient_id')
    
    print(f"Received reply: content='{content}', parent_id='{parent_id}', room_id='{room_id}', recipient_id='{recipient_id}'")
    
    if not content or not parent_id:
        print("Empty content or missing parent_id")
        return

    user = User.query.get(session['user_id'])
    if not user:
        print("User not found")
        return

    # Verify parent message exists
    parent_message = ChatMessage.query.get(parent_id)
    if not parent_message:
        print(f"Parent message not found: {parent_id}")
        return

    # Handle direct message replies
    if recipient_id:
        message = ChatMessage(
            content=content, 
            user_id=user.id,
            recipient_id=recipient_id,
            is_direct_message=True,
            parent_id=parent_id
        )
        db.session.add(message)
        db.session.commit()
        
        # Send to both users
        message_data = {
            'id': message.id,
            'content': message.content,
            'username': user.username,
            'is_admin': user.role == 'admin',
            'status': user.status or 'offline',
            'timestamp': message.timestamp.isoformat(),
            'profile_pic': user.profile_pic,
            'attachments': [],
            'parent_id': parent_id,
            'parent_username': parent_message.author.username,
            'parent_content': parent_message.content[:50] + ('...' if len(parent_message.content) > 50 else '')
        }
        
        print(f"Emitting direct reply to users {user.id} and {recipient_id}")
        emit('receive_message', message_data, room=f"user_{user.id}")
        emit('receive_message', message_data, room=f"user_{recipient_id}")
        return

    # Handle room message replies
    if room_id == 'general':
        general_room = ChatRoom.query.filter_by(name='General Chat').first()
        if general_room:
            room_id = general_room.id
        else:
            # Create general room if it doesn't exist
            general_room = ChatRoom(
                name='General Chat',
                description='Default chat room for all team members',
                created_by=user.id
            )
            db.session.add(general_room)
            db.session.commit()
            room_id = general_room.id
    
    # Convert room_id to int if it's a string
    try:
        room_id = int(room_id)
    except (ValueError, TypeError):
        print(f"Invalid room_id: {room_id}")
        return
    
    message = ChatMessage(
        content=content, 
        user_id=user.id,
        room_id=room_id,
        is_direct_message=False,
        parent_id=parent_id
    )
    db.session.add(message)
    db.session.commit()

    # Broadcast reply to room
    room_name = f"room_{room_id}"
    message_data = {
        'id': message.id,
        'content': message.content,
        'username': user.username,
        'is_admin': user.role == 'admin',
        'status': user.status or 'offline',
        'timestamp': message.timestamp.isoformat(),
        'profile_pic': user.profile_pic,
        'attachments': [],
        'parent_id': parent_id,
        'parent_username': parent_message.author.username,
        'parent_content': parent_message.content[:50] + ('...' if len(parent_message.content) > 50 else '')
    }
    
    print(f"Emitting room reply to room {room_name}")
    emit('receive_message', message_data, room=room_name)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        # Handle password change
        if 'old_password' in request.form and 'new_password' in request.form and 'confirm_password' in request.form:
            old_password = request.form['old_password']
            new_password = request.form['new_password']
            confirm_password = request.form['confirm_password']
            if not user.check_password(old_password):
                flash('Old password is incorrect.', 'danger')
            elif len(new_password) < 8:
                flash('New password must be at least 8 characters.', 'danger')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            else:
                user.set_password(new_password)
                db.session.commit()
                flash('Password updated successfully.', 'success')
        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    flash('Invalid file type. Only PNG and JPG allowed.', 'danger')
                elif file.content_length and file.content_length > MAX_PROFILE_PIC_SIZE:
                    flash('File too large (max 1MB).', 'danger')
                else:
                    # Save as user_<id>.ext
                    filename = f'user_{user.id}.{ext}'
                    filepath = os.path.join(PROFILE_PIC_FOLDER, filename)
                    # Ensure folder exists
                    os.makedirs(PROFILE_PIC_FOLDER, exist_ok=True)
                    # Resize/crop to 256x256
                    img = Image.open(file)
                    img = img.convert('RGB')
                    img = crop_center_resize(img, PROFILE_PIC_DIM, PROFILE_PIC_DIM)
                    img.save(filepath, quality=90)
                    user.profile_pic = filename
                    db.session.commit()
                    flash('Profile picture updated!', 'success')
            elif file:
                flash('Invalid file selected.', 'danger')
    return render_template('profile.html', user=user)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def crop_center_resize(img, width, height):
    # Crop to square, then resize
    min_dim = min(img.size)
    left = (img.width - min_dim) // 2
    top = (img.height - min_dim) // 2
    right = left + min_dim
    bottom = top + min_dim
    img = img.crop((left, top, right, bottom))
    return img.resize((width, height), Image.LANCZOS)

@app.route('/static/profile_pics/<filename>')
def profile_pic(filename):
    return send_from_directory(PROFILE_PIC_FOLDER, filename)

@app.route('/api/set_status', methods=['POST'])
@login_required
def set_status():
    status = request.json.get('status')
    if status not in ['online', 'away', 'dnd', 'offline']:
        return jsonify({'success': False, 'error': 'Invalid status'}), 400
    user = User.query.get(session['user_id'])
    user.status = status
    db.session.commit()
    # Broadcast to all users
    socketio.emit('user_status_update', {
        'user_id': user.id,
        'username': user.username,
        'status': status
    }, broadcast=True)
    return jsonify({'success': True, 'status': status})

@socketio.on('set_status')
def handle_set_status(data):
    if 'user_id' not in session:
        return
    status = data.get('status')
    if status not in ['online', 'away', 'dnd', 'offline']:
        return
    user = User.query.get(session['user_id'])
    user.status = status
    db.session.commit()
    # Broadcast to all users
    emit('user_status_update', {
        'user_id': user.id,
        'username': user.username,
        'status': status
    }, broadcast=True)

@app.route('/api/online_users')
@login_required
def get_online_users():
    users = User.query.filter(User.id.in_(online_users)).all()
    usernames = [u.username for u in users]
    return jsonify({'usernames': usernames})

@app.route('/api/projects', methods=['GET'])
@login_required
def get_projects():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'created_by': p.created_by,
        'created_at': p.created_at.isoformat()
    } for p in projects])

@app.route('/api/projects', methods=['POST'])
@moderator_required
def create_project():
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Project name is required'})
    project = Project(
        name=name,
        description=description,
        created_by=session['user_id']
    )
    db.session.add(project)
    db.session.commit()
    return jsonify({'success': True, 'project_id': project.id})

@app.route('/api/projects/<int:project_id>', methods=['PUT'])
@moderator_required
def edit_project(project_id):
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    project = Project.query.get_or_404(project_id)
    if name:
        project.name = name
    project.description = description
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/projects/<int:project_id>', methods=['DELETE'])
@moderator_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/projects/<int:project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    return jsonify({
        'id': project.id,
        'name': project.name,
        'description': project.description,
        'created_by': project.created_by,
        'created_at': project.created_at.isoformat()
    })
