# 🎯 Wispr

A simple, secure Flask-based team collaboration platform featuring chat functionality and kanban task management. Perfect for small teams who need a private workspace without external dependencies.

## ✨ Features

- 🔐 **Secure Authentication** - Session-based login system with admin/member roles
- 💬 **Team Chat** - Real-time messaging for team communication
- 📋 **Kanban Board** - Visual task management with To Do, In Progress, and Done columns
- 👥 **User Management** - Admin panel for creating and managing team members
- 📊 **Dashboard** - Overview of team activity and task statistics
- 🎨 **Modern UI** - Clean, responsive design with Bootstrap
- 🔒 **Private Team** - No public registration, admin-controlled access only

## 🛠️ Tech Stack

- **Backend**: Flask (Python) 🐍
- **Database**: SQLite (default) or PostgreSQL 🗄️
- **Frontend**: HTML5, CSS3, Bootstrap 5 💻
- **Authentication**: Session-based with password hashing 🔑
- **Deployment**: Gunicorn WSGI server 🚀

## 🚀 Quick Start

### 📋 Prerequisites

- Python 3.8 or higher 🐍
- pip (Python package manager) 📦
- Git (for cloning the repository) 🌿

### ⚡ One-Command Setup

---

# 🚨❗ **At this moment, you have to clone the repo and:** ❗🚨

1) run the "fix_install.sh" script (runs the sed command to fix the install.sh file by removing Windows-style carriage returns (\r) from the end of each line)
2) delete the database file in /instances (NOT THE WHOLE DIR!)
3) ```chmod +x install.sh chmod +x run.sh```

These minor issues/inconveniences will be fixed ASAP, however bigger updates (new features) have higher priority. :)

---

For the fastest setup, copy and paste this into your terminal:

```bash
git clone https://github.com/dukeofam/Wispr.git && cd Wispr && chmod +x install.sh && ./install.sh && ./run.sh
```

This will clone the repository, install everything, and start Wispr automatically.

### 🤖 Automatic Installation (Recommended)

1. **📥 Clone the repository**
   ```bash
   git clone https://github.com/dukeofam/Wispr.git
   cd Wispr
   ```

2. **🎬 Run the automated installer**
   ```bash
   chmod +x install.sh && ./install.sh
   ```

3. **🎯 Start Wispr**
   ```bash
   ./run.sh
   ```

The automated installer will:
- 🔍 Detect your operating system
- 📦 Install Python 3.8+ and required system packages
- 🏠 Create a virtual environment
- ⚙️ Install all Python dependencies
- 📝 Generate the run script automatically

**🖥️ Supported Systems:**
- Ubuntu/Debian (uses apt-get) 🐧
- CentOS/RHEL (uses yum) 🔴
- Arch Linux (uses pacman) ⚡
- Other Linux distributions (fallback pip installation) 🌐

### 🔧 Manual Installation

If you prefer to install manually or the automatic script doesn't work:

1. **Clone the repository**
   ```bash
   git clone https://github.com/dukeofam/Wispr.git
   cd Wispr
   ```

2. **Check Python version**
   ```bash
   python3 --version
   # Should be 3.8 or higher
   ```

3. **Create virtual environment (recommended)**
   ```bash
   python3 -m venv wispr_env
   source wispr_env/bin/activate  # On Windows: wispr_env\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements_standalone.txt
   ```

5. **Set environment variables (optional)**
   ```bash
   # For production, set a secure secret key
   export SESSION_SECRET="your-super-secret-key-here"
   
   # For PostgreSQL database (optional)
   export DATABASE_URL="postgresql://username:password@localhost:5432/team_db"
   ```

6. **Run the application**
   ```bash
   # Development mode
   python main.py
   
   # Production mode with Gunicorn
   gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
   ```

7. **Access the application**
   - Open your browser to `http://localhost:5000`
   - Login with default admin credentials:
     - **Username**: `admin`
     - **Password**: `admin123`

## ⚙️ Configuration

### 🌍 Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SESSION_SECRET` | Secret key for session encryption 🔐 | `dev-secret-key-change-in-production` | Production |
| `DATABASE_URL` | Database connection string 🗄️ | `sqlite:///team_collaboration.db` | Optional |

### 🗄️ Database Setup

#### 📱 SQLite (Default - Recommended for Small Teams)

SQLite requires no additional setup and is perfect for teams of 5-50 users.

**Advantages:**
- Zero configuration
- Automatic database creation
- File-based storage
- No separate database server needed

**Setup:**
```bash
# No setup required - database file created automatically
# Database file: team_collaboration.db (created in app directory)
```

#### 🐘 PostgreSQL (Recommended for Production)

For larger teams or production deployments, PostgreSQL provides better performance and concurrent access.

**Step 1: Install PostgreSQL Server**

*Ubuntu/Debian:*
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

*CentOS/RHEL:*
```bash
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

*macOS:*
```bash
brew install postgresql
brew services start postgresql
```

**Step 2: Create Database and User**
```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE wispr_db;
CREATE USER wispr_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE wispr_db TO wispr_user;
\q
```

**Step 3: Configure Wispr for PostgreSQL**
```bash
# Uncomment PostgreSQL dependency in requirements_standalone.txt
sed -i 's/# psycopg2-binary/psycopg2-binary/' requirements_standalone.txt

# Install PostgreSQL adapter
pip install psycopg2-binary

# Set database URL
export DATABASE_URL="postgresql://wispr_user:your_secure_password@localhost:5432/wispr_db"
```

**Step 4: Test Connection**
```bash
# Test database connection
python3 -c "
import os
from sqlalchemy import create_engine
engine = create_engine(os.environ.get('DATABASE_URL'))
connection = engine.connect()
print('✅ PostgreSQL connection successful')
connection.close()
"
```

## 📖 Usage

### 🎯 Getting Started

1. **Login as Admin**
   - Use default credentials: `admin` / `admin123`
   - Change the default password immediately in production

2. **Create Team Members**
   - Go to Admin Panel
   - Add new users with usernames, emails, and passwords
   - Assign admin privileges as needed

3. **Start Collaborating**
   - Use the Dashboard to see team activity
   - Chat with team members in real-time
   - Create and manage tasks on the Kanban board

### User Roles

**Admin Users**
- Full access to all features
- Can create and delete users
- Can manage all tasks and messages
- Access to admin panel

**Regular Members**
- Can participate in team chat
- Can create and manage their own tasks
- Can move tasks between columns
- Dashboard access for team overview

### Features Overview

**Dashboard**
- Task statistics and recent activity
- Quick access to all major features
- Team collaboration overview

**Team Chat**
- Send messages to the entire team
- Real-time conversation (auto-refresh every 30 seconds)
- Message history with timestamps

**Kanban Board**
- Create tasks with titles, descriptions, and priorities
- Three columns: To Do, In Progress, Done
- Drag tasks between columns (via dropdown menus)
- Priority levels: Low, Medium, High
- Task ownership tracking

**Admin Panel**
- Create new team members
- Delete users (removes all their data)
- View system statistics
- User role management

## 🚀 Deployment

### 🧪 Development Mode

Development mode is perfect for testing, local development, and small team usage.

```bash
# Start in development mode (default)
./run.sh

# Or manually:
python main.py
```

**Development Features:**
- Runs on `http://localhost:5000`
- Debug mode enabled
- Auto-reloads on code changes
- Detailed error messages
- SQLite database (no setup required)

### 🏭 Production Deployment

For production environments, follow these steps for a secure, scalable deployment.

#### Step 1: Server Preparation

**Update System:**
```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install git python3 python3-pip python3-venv nginx supervisor
```

**Create Application User:**
```bash
sudo adduser --system --group wispr
sudo mkdir -p /var/www/wispr
sudo chown wispr:wispr /var/www/wispr
```

#### Step 2: Application Setup

**Deploy Application:**
```bash
# Switch to application user
sudo -u wispr -H bash
cd /var/www/wispr

# Clone and install
git clone https://github.com/dukeofam/Wispr.git .
chmod +x install.sh && ./install.sh
```

**Configure Environment:**
```bash
# Generate secure session secret
python3 -c "import secrets; print('SESSION_SECRET=' + secrets.token_hex(32))" > .env

# Add database configuration (if using PostgreSQL)
echo "DATABASE_URL=postgresql://wispr_user:your_secure_password@localhost:5432/wispr_db" >> .env
```

#### Step 3: Process Management with Supervisor

Create `/etc/supervisor/conf.d/wispr.conf`:
```ini
[program:wispr]
command=/var/www/wispr/wispr_env/bin/gunicorn --bind 127.0.0.1:5000 --workers 4 --timeout 120 main:app
directory=/var/www/wispr
user=wispr
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/wispr.log
environment=SESSION_SECRET="your-generated-secret-key",DATABASE_URL="your-database-url"
```

**Start Supervisor:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start wispr
sudo supervisorctl status wispr
```

#### Step 4: Reverse Proxy with Nginx

Create `/etc/nginx/sites-available/wispr`:
```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for future features)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static {
        alias /var/www/wispr/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

**Enable Site:**
```bash
sudo ln -s /etc/nginx/sites-available/wispr /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### Step 5: SSL/HTTPS Setup with Let's Encrypt

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Test automatic renewal
sudo certbot renew --dry-run
```

#### Step 6: Database Backup Setup

Create backup script `/var/www/wispr/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/wispr"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# SQLite backup
if [ -f "/var/www/wispr/team_collaboration.db" ]; then
    cp /var/www/wispr/team_collaboration.db $BACKUP_DIR/wispr_backup_$DATE.db
    # Keep only last 30 days
    find $BACKUP_DIR -name "wispr_backup_*.db" -mtime +30 -delete
fi

# PostgreSQL backup (if using PostgreSQL)
# pg_dump -h localhost -U wispr_user wispr_db > $BACKUP_DIR/wispr_pg_backup_$DATE.sql
```

**Setup Cron Job:**
```bash
sudo crontab -e
# Add this line for daily backups at 2 AM:
0 2 * * * /var/www/wispr/backup.sh
```

#### Step 7: Monitoring Setup

Create monitoring script `/var/www/wispr/monitor.sh`:
```bash
#!/bin/bash
# Simple health check script

if ! curl -f http://localhost:5000 > /dev/null 2>&1; then
    echo "$(date): Wispr is down, restarting..." >> /var/log/wispr-monitor.log
    sudo supervisorctl restart wispr
fi
```

**Setup Monitoring Cron:**
```bash
# Check every 5 minutes
*/5 * * * * /var/www/wispr/monitor.sh
```

#### Step 8: Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw --force enable
```

#### Step 9: Production Verification

**Test the deployment:**
```bash
# Check application status
sudo supervisorctl status wispr

# Check logs
sudo tail -f /var/log/wispr.log

# Test HTTP response
curl -I http://your-domain.com

# Test HTTPS (after SSL setup)
curl -I https://your-domain.com
```

#### Step 10: Post-Deployment Security

**Change Default Credentials:**
1. Access your domain in browser
2. Login with admin/admin123
3. Go to Admin Panel
4. Create new admin user with strong password
5. Delete default admin account

**Environment Security:**
```bash
# Secure the .env file
sudo chmod 600 /var/www/wispr/.env
sudo chown wispr:wispr /var/www/wispr/.env

# Secure application directory
sudo chmod -R 755 /var/www/wispr
sudo chown -R wispr:wispr /var/www/wispr
```

### 🔒 Security Checklist

**Essential Security Steps:**

1.    - Login with admin/admin123
   - Create new admin user with strong password
   - Delete default admin account

2. **Secure Session Management**
   ```bash
   # Generate cryptographically secure session secret
   export SESSION_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
   ```

3. **Database Security**
   - Use PostgreSQL for production environments
   - Create dedicated database user with limited privileges
   - Enable SSL connections for database
   - Regular automated backups

4. **Network Security**
   - Always use HTTPS in production
   - Configure proper firewall rules
   - Use reverse proxy (Nginx/Apache)
   - Implement rate limiting

5. **File System Security**
   - Run application as non-root user
   - Restrict file permissions (755 for directories, 644 for files)
   - Secure environment files (600 permissions)

6. **Application Security**
   - Keep dependencies updated
   - Monitor application logs
   - Implement automated health checks
   - Use process management (Supervisor/systemd)

## 📁 File Structure

```
Wispr/
├── app.py                 # Flask application setup 🏗️
├── main.py               # Application entry point 🎯
├── models.py             # Database models 🗃️
├── routes.py             # URL routes and logic 🛤️
├── requirements_standalone.txt  # Python dependencies 📦
├── install.sh            # Automatic installation script 🤖
├── run.sh                # Application runner script ▶️
├── README.md             # This file 📖
├── static/
│   └── style.css         # Custom CSS styles 🎨
└── templates/
    ├── base.html         # Base template 🏗️
    ├── login.html        # Login page 🔐
    ├── dashboard.html    # Dashboard 📊
    ├── chat.html         # Team chat 💬
    ├── kanban.html       # Kanban board 📋
    └── admin.html        # Admin panel ⚙️
```

## 🎨 Customization

### 🔧 Adding New Features

The application is built with a modular structure:
- Add new routes in `routes.py`
- Create database models in `models.py` 
- Add templates in `templates/`
- Custom styles in `static/style.css`

### Styling

The app uses Bootstrap 5 with a dark theme. Customize by:
- Modifying `static/style.css`
- Updating Bootstrap classes in templates
- Adding custom color schemes

### Database Schema

**Users Table**
- id, username, email, password_hash, is_admin, created_at

**Chat Messages Table**
- id, content, timestamp, user_id

**Tasks Table**
- id, title, description, status, priority, created_at, updated_at, user_id

## 🔬 Advanced Configuration

### 📄 Environment File Setup

For production deployments, create a `.env` file to manage configuration:

```bash
# Create environment file
cat > .env << 'EOF'
# Session Configuration
SESSION_SECRET=your-64-character-random-string

# Database Configuration (choose one)
DATABASE_URL=sqlite:///team_collaboration.db
# DATABASE_URL=postgresql://wispr_user:password@localhost:5432/wispr_db

# Application Settings
FLASK_ENV=production
FLASK_DEBUG=False

# Server Configuration
GUNICORN_WORKERS=4
GUNICORN_TIMEOUT=120
GUNICORN_BIND=127.0.0.1:5000
EOF

# Secure the file
chmod 600 .env
```

**Load Environment Variables:**
```bash
# Option 1: Source the file
source .env && ./run.sh

# Option 2: Use with systemd/supervisor (see production deployment)

# Option 3: Export manually
export $(cat .env | xargs) && ./run.sh
```

### 🌐 Custom Domain Setup

**Step 1: DNS Configuration**
Point your domain to your server's IP address:
```
A record: @ -> your.server.ip.address
A record: www -> your.server.ip.address
```

**Step 2: Update Nginx Configuration**
```nginx
# Add to /etc/nginx/sites-available/wispr
server_name yourdomain.com www.yourdomain.com;
```

**Step 3: SSL Certificate**
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### ⚡ Performance Optimization

**🗄️ Database Optimization:**
```bash
# For PostgreSQL, create indexes for better performance
sudo -u postgres psql wispr_db << 'EOF'
CREATE INDEX idx_chat_messages_timestamp ON chat_message(timestamp);
CREATE INDEX idx_tasks_status ON task(status);
CREATE INDEX idx_tasks_user_id ON task(user_id);
CREATE INDEX idx_users_username ON user(username);
EOF
```

**Gunicorn Configuration:**
```bash
# Create gunicorn.conf.py
cat > gunicorn.conf.py << 'EOF'
# Server socket
bind = "127.0.0.1:5000"
backlog = 2048

# Worker processes
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Restart workers
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Logging
accesslog = "/var/log/wispr/access.log"
errorlog = "/var/log/wispr/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "wispr"

# Server mechanics
daemon = False
pidfile = "/var/run/wispr.pid"
user = "wispr"
group = "wispr"
tmp_upload_dir = None
EOF
```

### 💾 Backup and Restore

**🔄 Automated Backup Script:**
```bash
#!/bin/bash
# /var/www/wispr/scripts/backup.sh

BACKUP_DIR="/var/backups/wispr"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p $BACKUP_DIR

# Application backup
tar -czf $BACKUP_DIR/wispr_app_$DATE.tar.gz \
    --exclude='wispr_env' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    /var/www/wispr

# Database backup
if [ -f "/var/www/wispr/team_collaboration.db" ]; then
    # SQLite backup
    sqlite3 /var/www/wispr/team_collaboration.db ".backup '$BACKUP_DIR/wispr_db_$DATE.db'"
fi

# PostgreSQL backup (if applicable)
if [ ! -z "$DATABASE_URL" ] && [[ $DATABASE_URL == postgresql* ]]; then
    pg_dump $DATABASE_URL > $BACKUP_DIR/wispr_pg_$DATE.sql
    gzip $BACKUP_DIR/wispr_pg_$DATE.sql
fi

# Cleanup old backups
find $BACKUP_DIR -name "wispr_*" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $DATE"
```

**Restore Process:**
```bash
# Stop application
sudo supervisorctl stop wispr

# Restore application files
cd /var/www
sudo rm -rf wispr
sudo tar -xzf /var/backups/wispr/wispr_app_YYYYMMDD_HHMMSS.tar.gz

# Restore database
# For SQLite:
cp /var/backups/wispr/wispr_db_YYYYMMDD_HHMMSS.db /var/www/wispr/team_collaboration.db

# For PostgreSQL:
# dropdb wispr_db && createdb wispr_db
# gunzip -c /var/backups/wispr/wispr_pg_YYYYMMDD_HHMMSS.sql.gz | psql wispr_db

# Fix permissions
sudo chown -R wispr:wispr /var/www/wispr

# Start application
sudo supervisorctl start wispr
```

### 📊 Monitoring and Logging

**📝 Log Management:**
```bash
# Create log rotation configuration
sudo tee /etc/logrotate.d/wispr << 'EOF'
/var/log/wispr/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 wispr wispr
    postrotate
        supervisorctl restart wispr
    endscript
}
EOF
```

**System Monitoring:**
```bash
# Create comprehensive monitoring script
cat > /var/www/wispr/scripts/monitor.sh << 'EOF'
#!/bin/bash

LOG_FILE="/var/log/wispr-monitor.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check application health
if ! curl -f -s http://localhost:5000/login > /dev/null; then
    echo "[$DATE] ERROR: Application not responding, restarting..." >> $LOG_FILE
    supervisorctl restart wispr
    sleep 30
fi

# Check disk space
DISK_USAGE=$(df /var/www/wispr | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "[$DATE] WARNING: Disk usage is ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check memory usage
MEM_USAGE=$(free | awk 'NR==2{printf "%.2f", $3*100/$2}')
if (( $(echo "$MEM_USAGE > 80" | bc -l) )); then
    echo "[$DATE] WARNING: Memory usage is ${MEM_USAGE}%" >> $LOG_FILE
fi

# Check database file (SQLite)
if [ -f "/var/www/wispr/team_collaboration.db" ]; then
    if ! sqlite3 /var/www/wispr/team_collaboration.db "SELECT 1;" > /dev/null 2>&1; then
        echo "[$DATE] ERROR: Database corruption detected" >> $LOG_FILE
    fi
fi

echo "[$DATE] Health check completed" >> $LOG_FILE
EOF

chmod +x /var/www/wispr/scripts/monitor.sh
```

### Multi-Instance Deployment

For high-availability setups:

**Load Balancer Configuration (HAProxy):**
```
# /etc/haproxy/haproxy.cfg
frontend wispr_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/wispr.pem
    redirect scheme https if !{ ssl_fc }
    default_backend wispr_backend

backend wispr_backend
    balance roundrobin
    option httpchk GET /login
    server wispr1 127.0.0.1:5001 check
    server wispr2 127.0.0.1:5002 check
```

**Session Storage (Redis):**
```bash
# Install Redis for shared sessions
sudo apt-get install redis-server

# Configure Wispr for Redis sessions (requires code modification)
# This is an advanced configuration requiring additional development
```

## 🔧 Troubleshooting

### ⚠️ Installation Issues

**Installation Script Fails**
```bash
# If install.sh fails, try manual installation
# Make sure you have internet connection
# Check if you have sudo/admin privileges (required for system packages)

# On Windows, use Git Bash or WSL
# On macOS, script uses automatic detection (no Homebrew required)
# For unsupported systems, script falls back to pip-only installation
```

**Python Version Issues**
```bash
# Check your Python version
python3 --version

# The installer automatically handles Python installation on:
# - Ubuntu/Debian: installs python3, python3-pip, python3-venv, python3-dev
# - CentOS/RHEL: installs python3, python3-pip
# - Arch Linux: installs python, python-pip

# If you have multiple Python versions, the installer detects automatically
# For Ubuntu 24.04+ compatibility, the installer includes python3.12-venv
```

**Virtual Environment Issues**
```bash
# The installer automatically creates and manages the virtual environment
# If you need to manually activate it:
# On Linux/macOS:
source wispr_env/bin/activate

# On Windows:
wispr_env\Scripts\activate

# The installer removes any existing environment and creates fresh one
# If manual recreation is needed:
rm -rf wispr_env && python3 -m venv wispr_env
```

**Database Connection Error**
```bash
# Make sure database URL is correct
echo $DATABASE_URL

# For SQLite, ensure write permissions
chmod 755 .

# Check if database file was created
ls -la *.db
```

**Session/Login Issues**
```bash
# Clear browser cookies and cache
# Check SESSION_SECRET is set
echo $SESSION_SECRET

# Try incognito/private browsing mode
```

**Port Already in Use**
```bash
# Find process using port 5000
lsof -i :5000
# Or on Windows:
netstat -ano | findstr :5000

# Kill the process
kill -9 <PID>
# Or on Windows:
taskkill /PID <PID> /F
```

**Permission Denied Errors**
```bash
# Make scripts executable (automatically handled by installer)
chmod +x install.sh run.sh

# If still having issues, run with explicit interpreter
bash install.sh
bash run.sh

# For system package installation, ensure you have sudo privileges
sudo -v  # Test sudo access
```

## 🆘 Support

This is a standalone application designed for private team use. For additional features or support:

1. 📋 Check the application logs for error details
2. ✅ Verify all dependencies are installed correctly
3. 🔐 Ensure proper file permissions
4. ⚙️ Review configuration settings

## 📄 License

This project is provided as-is for private team collaboration. Modify and distribute according to your needs.
