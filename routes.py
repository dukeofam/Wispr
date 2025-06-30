from flask import render_template, request, redirect, url_for, session, flash, jsonify, Response
from flask_socketio import emit, join_room, leave_room
from app import app, db, socketio, limiter
from models import User, ChatMessage, Task, ChatRoom, MessageAttachment, TaskActivityLog
from werkzeug.security import generate_password_hash
from datetime import datetime
from sqlalchemy import desc
import logging

# Store online users
online_users = set()


def login_required(f):
    """Decorator to require login for protected routes"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
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
        if not user or not user.is_admin:
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
            session['is_admin'] = user.is_admin
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
        'is_admin': msg.author.is_admin,
        'timestamp': msg.timestamp.isoformat()
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
        'is_admin': msg.author.is_admin,
        'timestamp': msg.timestamp.isoformat(),
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
        'is_admin': msg.author.is_admin,
        'timestamp': msg.timestamp.isoformat(),
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
    if message.user_id != session['user_id'] and not session.get('is_admin', False):
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
        
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
            except ValueError:
                pass

        if title:
            task = Task(title=title,
                        description=description,
                        priority=priority,
                        assigned_to=assigned_to,
                        due_date=due_date,
                        user_id=session['user_id'])
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

    # Get tasks organized by status
    todo_tasks = Task.query.filter_by(status='todo').order_by(
        Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    in_progress_tasks = Task.query.filter_by(status='in_progress').order_by(
        Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    done_tasks = Task.query.filter_by(status='done').order_by(
        Task.updated_at.desc()).all()
    
    # Get all users for assignment dropdown
    users = User.query.all()
    
    # Get project templates
    from models import ProjectTemplate
    templates = ProjectTemplate.query.all()

    return render_template('kanban.html',
                           todo_tasks=todo_tasks,
                           in_progress_tasks=in_progress_tasks,
                           done_tasks=done_tasks,
                           users=users,
                           templates=templates,
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
    if task.user_id == session['user_id'] or session.get('is_admin', False):
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


@app.route('/api/project_template', methods=['POST'])
@admin_required
def create_project_template():
    """Create a new project template"""
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    template_data = data.get('template_data', '[]')
    
    if not name:
        return jsonify({'success': False, 'error': 'Template name is required'})
    
    from models import ProjectTemplate
    template = ProjectTemplate(
        name=name,
        description=description,
        template_data=template_data,
        created_by=session['user_id']
    )
    
    db.session.add(template)
    db.session.commit()
    
    return jsonify({'success': True, 'template_id': template.id})


@app.route('/api/project_template/<int:template_id>/apply', methods=['POST'])
@login_required
def apply_project_template(template_id):
    """Apply a project template to create tasks"""
    from models import ProjectTemplate, TaskActivityLog
    import json
    
    template = ProjectTemplate.query.get_or_404(template_id)
    
    try:
        task_templates = json.loads(template.template_data)
        created_tasks = []
        
        for task_data in task_templates:
            task = Task(
                title=task_data.get('title', ''),
                description=task_data.get('description', ''),
                priority=task_data.get('priority', 'medium'),
                user_id=session['user_id']
            )
            db.session.add(task)
            db.session.flush()  # Get task ID
            
            # Log task creation
            activity = TaskActivityLog(
                action='task_created_from_template',
                details=json.dumps({'template': template.name, 'title': task.title}),
                task_id=task.id,
                user_id=session['user_id']
            )
            db.session.add(activity)
            created_tasks.append(task.id)
        
        db.session.commit()
        return jsonify({'success': True, 'created_tasks': created_tasks})
        
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'Invalid template data'})


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
    is_admin = 'is_admin' in request.form

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

    user = User(username=username, email=email, is_admin=is_admin)
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
        other_admins = User.query.filter(User.is_admin).count()
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
            'is_admin': user.is_admin,
            'timestamp': message.timestamp.isoformat(),
            'attachments': []
        }
        
        print(f"Emitting direct message to users {user.id} and {recipient_id}")
        emit('receive_message', message_data, room=f"user_{user.id}")
        emit('receive_message', message_data, room=f"user_{recipient_id}")
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
        'is_admin': user.is_admin,
        'timestamp': message.timestamp.isoformat(),
        'attachments': []
    }
    
    print(f"Emitting room message to room {room_name}")
    emit('receive_message', message_data, room=room_name)


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
