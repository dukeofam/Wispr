# Wispr

A secure, modern Flask-based team collaboration platform with real-time chat and kanban task management. Designed for small teams who need a private, self-hosted workspace.

## Features
- Secure authentication (admin/member roles)
- Real-time team chat (Socket.IO)
- Kanban board for task management
- Admin panel for user management
- Dashboard for team activity
- Modern, responsive UI (Bootstrap 5)

## Tech Stack
- **Backend:** Flask (Python 3.12+)
- **Database:** SQLite (default) or PostgreSQL
- **Frontend:** HTML5, CSS3, Bootstrap 5
- **WebSocket:** Flask-SocketIO
- **Deployment:** Gunicorn + eventlet

## Quick Start (Development)

1. **Clone and install:**
   ```bash
   git clone https://github.com/dukeofam/Wispr.git
   cd Wispr
   sudo chmod +x fix_install.sh && sudo ./fix_install.sh
   sudo chmod +x install.sh && sudo ./install.sh
   ```
2. **Run locally:**
   ```bash
   sudo chmod +x run.sh && sudo ./run.sh
   # or
   python3 main.py
   ```
3. **Login:**
   - Open [http://localhost:5000](http://localhost:5000)
   - Username: `admin`  Password: `admin123`

## Automated Production Deployment

You can deploy Wispr to a fresh VPS in minutes using the provided `auto-deploy.sh` script. **First, clone the Wispr repo to your local machine or server:**
```bash
git clone https://github.com/dukeofam/Wispr.git
cd Wispr
```
Then run:
```bash
chmod +x auto-deploy.sh
./auto-deploy.sh
```
This script:
- Installs all required packages (git, python3.12, venv, nginx, certbot, etc)
- Creates a dedicated `wispr` system user and sets up `/var/www/wispr`
- Copies your current repo to `/var/www/wispr` and installs dependencies
- Sets permissions and creates a secure `.env` file
- Configures systemd and Nginx for your domain (with SSL and security headers)
- Obtains a free SSL certificate with Certbot
- Enables and starts all services

Follow the prompts for your domain, email, and session secret. The script is safe to re-run and will not overwrite existing data/configs unless you change your answers.

## Production Deployment

### 1. Prepare Environment
- Use `install.sh` to set up Python, dependencies, and virtualenv.
- Create a `.env` file with your production secrets (see below).

### 2. Deploy with systemd
- Use the provided `deploy.sh` script for production startup.
- Example systemd unit (`/etc/systemd/system/wispr.service`):
  ```ini
  [Unit]
  Description=Wispr Team Collaboration Platform
  After=network.target

  [Service]
  Type=simple
  User=wispr
  WorkingDirectory=/var/www/wispr
  EnvironmentFile=/var/www/wispr/.env
  ExecStart=/var/www/wispr/deploy.sh
  Restart=always
  RestartSec=5
  StandardOutput=append:/var/log/wispr/wispr.log
  StandardError=append:/var/log/wispr/wispr.log

  [Install]
  WantedBy=multi-user.target
  ```
- Enable and start:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable wispr
  sudo systemctl start wispr
  sudo systemctl status wispr
  ```

### 3. Reverse Proxy (Nginx recommended)
- Proxy requests to `localhost:5000` and serve static files.
- Ensure WebSocket and security headers are set (see sample Nginx config in repo or Flask docs).

### 4. Monitoring & Logs
- Logs: `/var/log/wispr/wispr.log` (configurable via `LOG_DIR` or `LOG_FILE`)
- Health check: `GET /healthz`

## Configuration

### .env Example
```
SESSION_SECRET=your-very-secret-key
FLASK_ENV=production
SESSION_TYPE=filesystem  # or redis
SESSION_FILE_DIR=/var/www/wispr/sessions
DATABASE_URL=sqlite:///team_collaboration.db
# DATABASE_URL=postgresql://user:password@localhost:5432/wispr_db
CORS_ALLOWED_ORIGINS=https://yourdomain.com
LOG_FILE=/var/log/wispr/wispr.log
```

### Security & Best Practices
- **Change the default admin password immediately.**
- **Set a strong SESSION_SECRET in production.**
- **Use server-side sessions (filesystem or Redis) in production.**
- **All forms are CSRF-protected.**
- **All user content is escaped before rendering.**
- **Rate limiting is enabled for login, user creation, and API endpoints.**
- **CORS is restricted in production.**
- **Logs are rotated automatically.**
- **/healthz endpoint for monitoring.**

## File Structure
```
Wispr/
├── app.py           # Flask app setup
├── main.py          # Entry point
├── models.py        # Database models
├── routes.py        # Routes and logic
├── requirements_standalone.txt
├── install.sh       # Installer
├── run.sh           # Dev runner
├── deploy.sh        # Production runner
├── wispr.service    # Example systemd unit
├── static/
├── templates/
└── README.md
```

## Customization
- Add routes in `routes.py`, models in `models.py`, templates in `templates/`, and styles in `static/style.css`.
- Use Bootstrap classes for UI tweaks.

## License
This project is provided as-is for private team use. Modify and distribute as needed.

## Production Extras

### Nginx Example
See `nginx-wispr.conf` for a sample Nginx config with WebSocket support, static file serving, and security headers.

### Backup Script
- Use `backup.sh` to back up the app, database, and clean up old backups.
- Example daily cron:
  ```cron
  0 2 * * * /var/www/wispr/backup.sh
  ```

### Health Monitoring
- Use `monitor.sh` for uptime/health checks and auto-restart (with systemd).
- Example 5-min cron:
  ```cron
  */5 * * * * /var/www/wispr/monitor.sh
  ```

---
