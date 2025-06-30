#!/bin/bash
set -e

# --- Ensure sudo is available and prompt early ---
if ! sudo -v; then
    echo "[!] This script requires sudo privileges. Please run as a user with sudo access."
    exit 1
fi

# --- Prompt for config ---
read -p "Enter your domain (e.g. example.com): " DOMAIN
read -p "Enter your email for SSL certificate: " EMAIL
read -p "Enter a strong session secret (leave empty to generate one): " SESSION_SECRET
if [ -z "$SESSION_SECRET" ]; then
    SESSION_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')
    echo "[+] Generated session secret: $SESSION_SECRET"
fi

# --- Install system packages ---
echo "[+] Installing required packages..."
if command -v apt-get >/dev/null 2>&1; then
    if ! command -v python3.12 >/dev/null 2>&1; then
        echo "[+] Adding deadsnakes PPA for Python 3.12..."
        sudo apt-get update
        sudo apt-get install -y software-properties-common
        sudo add-apt-repository ppa:deadsnakes/ppa -y
        sudo apt-get update
    fi
    sudo apt-get install -y git python3.12 python3.12-venv python3.12-dev python3-pip nginx certbot python3-certbot-nginx
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y git python3 python3-pip python3-venv nginx certbot python3-certbot-nginx
else
    echo "[!] Unsupported OS. Please install git, python3.12, venv, nginx, and certbot manually."
    exit 1
fi

# --- Set up wispr user and /var/www/wispr ---
echo "[+] Setting up wispr user and /var/www/wispr..."
if ! id "wispr" &>/dev/null; then
    sudo useradd -r -m -d /var/www/wispr -s /usr/sbin/nologin wispr
    sudo mkdir -p /var/www/wispr
    sudo chown wispr:wispr /var/www/wispr
else
    echo "The system user \`wispr' already exists. Exiting."
fi

# --- Copy repo and set permissions ---
echo "[+] Copying current repo to /var/www/wispr..."
sudo rsync -a --delete ./ /var/www/wispr/
sudo chown -R wispr:wispr /var/www/wispr

# --- Set up Python virtual environment as wispr user ---
echo "[+] Setting up Python virtual environment..."
cd /var/www/wispr
if [ ! -d "wispr_env" ]; then
    sudo -u wispr python3.12 -m venv wispr_env
fi
sudo -u wispr ./wispr_env/bin/pip install --upgrade pip
sudo -u wispr ./wispr_env/bin/pip install -r requirements.txt

# --- Set permissions ---
sudo chown -R wispr:wispr /var/www/wispr
sudo find /var/www/wispr -type d -exec chmod 755 {} \;
sudo find /var/www/wispr -type f -exec chmod 644 {} \;
sudo chmod 700 /var/www/wispr/backup.sh /var/www/wispr/monitor.sh || true

# --- Create .env ---
cat <<EOF | sudo tee /var/www/wispr/.env
SESSION_SECRET=$SESSION_SECRET
FLASK_ENV=production
SESSION_TYPE=filesystem
SESSION_FILE_DIR=/var/www/wispr/sessions
DATABASE_URL=sqlite:///team_collaboration.db
CORS_ALLOWED_ORIGINS=https://$DOMAIN
LOG_FILE=/var/log/wispr/wispr.log
EOF
sudo chmod 600 /var/www/wispr/.env
sudo chown wispr:wispr /var/www/wispr/.env

# --- Set up systemd service ---
cat <<EOF | sudo tee /etc/systemd/system/wispr.service
[Unit]
Description=Wispr Team Collaboration Platform
After=network.target

[Service]
Type=simple
User=wispr
Group=wispr
WorkingDirectory=/var/www/wispr
EnvironmentFile=/var/www/wispr/.env
ExecStart=/var/www/wispr/deploy.sh
Restart=always
RestartSec=5
StandardOutput=append:/var/log/wispr/wispr.log
StandardError=append:/var/log/wispr/wispr.log

[Install]
WantedBy=multi-user.target
EOF

# --- Write Nginx config with sudo ---
echo "[+] Writing Nginx config..."
sudo bash -c "cat > /etc/nginx/sites-available/wispr" <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN www.$DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Static files
    location /static/ {
        alias /var/www/wispr/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://cdn.replit.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.replit.com;" always;
} 
EOF

# --- Symlink and reload Nginx with sudo ---
sudo ln -sf /etc/nginx/sites-available/wispr /etc/nginx/sites-enabled/wispr
sudo nginx -t && sudo systemctl reload nginx

# --- Obtain SSL certificate ---
echo "[+] Obtaining SSL certificate with certbot..."
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect || true

# --- Enable and start services ---
sudo systemctl daemon-reload
sudo systemctl enable wispr
sudo systemctl restart wispr
sudo systemctl restart nginx

# --- Final message ---
echo "[+] Wispr deployed!"
echo "- App: https://$DOMAIN"
echo "- Admin login: admin / admin123 (change password immediately)"
echo "- Systemd service: wispr"
echo "- Nginx config: /etc/nginx/sites-available/wispr"
echo "- .env: /var/www/wispr/.env"
echo "- Logs: /var/log/wispr/wispr.log" 
