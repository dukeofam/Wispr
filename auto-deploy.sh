#!/bin/bash
set -e

# --- Prompt for sudo at the start ---
if ! sudo -v; then
    echo "[!] This script requires sudo privileges. Please run as a user with sudo access."
    exit 1
fi

# --- Prompt for config ---
read -p "Enter your domain (e.g. example.com): " DOMAIN
while [[ -z "$DOMAIN" ]]; do
    echo "Domain cannot be blank."
    read -p "Enter your domain (e.g. example.com): " DOMAIN
done
read -p "Enter your email for SSL certificate (optional): " EMAIL
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
fi
sudo mkdir -p /var/www/wispr
sudo chown -R wispr:wispr /var/www/wispr

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
# Ensure eventlet is installed and up to date
sudo -u wispr ./wispr_env/bin/pip install 'eventlet>=0.33.0'

# --- Copy favicon.ico if present ---
if [ -f ./static/favicon.ico ]; then
    echo "[+] Copying favicon.ico to /var/www/wispr/static/"
    sudo cp ./static/favicon.ico /var/www/wispr/static/
    sudo chown wispr:wispr /var/www/wispr/static/favicon.ico
fi

# --- Write .env file ---
echo "[+] Writing .env file..."
sudo bash -c "cat > /var/www/wispr/.env" <<EOF
SESSION_SECRET=$SESSION_SECRET
FLASK_ENV=production
SESSION_TYPE=filesystem
SESSION_FILE_DIR=/var/www/wispr/sessions
DATABASE_URL=sqlite:///team_collaboration.db
CORS_ALLOWED_ORIGINS=https://$DOMAIN
LOG_FILE=/var/log/wispr/wispr.log
EOF
sudo chown wispr:wispr /var/www/wispr/.env

# --- Set up log directory ---
echo "[+] Setting up log directory..."
sudo mkdir -p /var/log/wispr
sudo touch /var/log/wispr/wispr.log
sudo chown -R wispr:wispr /var/log/wispr

# --- Remove old database for a clean deploy
if [ -f instance/team_collaboration.db ]; then
    echo "Removing old database..."
    rm instance/team_collaboration.db
fi

# --- Write temporary HTTP-only Nginx config ---
echo "[+] Writing temporary HTTP-only Nginx config..."
sudo bash -c "cat > /etc/nginx/sites-available/wispr" <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
    root /var/www/wispr/static;
    location /static/ {
        alias /var/www/wispr/static/;
        expires 1y;
        add_header Cache-Control 'public, immutable';
    }
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.replit.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.replit.com; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data:; connect-src 'self';" always;
}
EOF
sudo ln -sf /etc/nginx/sites-available/wispr /etc/nginx/sites-enabled/wispr
sudo nginx -t
if ! systemctl is-active --quiet nginx; then
    echo "[+] Nginx is not running. Starting nginx..."
    sudo systemctl start nginx
else
    echo "[+] Reloading nginx..."
    sudo systemctl reload nginx
fi

# --- Obtain SSL certificate with certbot ---
echo "[+] Obtaining SSL certificate with certbot..."
if [ -z "$EMAIL" ]; then
    sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --register-unsafely-without-email --agree-tos --non-interactive || true
else
    sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN -m $EMAIL --agree-tos --non-interactive || true
fi

# --- Write full HTTPS Nginx config ---
echo "[+] Writing full HTTPS Nginx config..."
sudo bash -c "cat > /etc/nginx/sites-available/wispr" <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;
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
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
    }
    location /static/ {
        alias /var/www/wispr/static/;
        expires 1y;
        add_header Cache-Control 'public, immutable';
    }
    add_header Strict-Transport-Security 'max-age=31536000; includeSubDomains' always;
    add_header X-Frame-Options 'SAMEORIGIN' always;
    add_header X-Content-Type-Options 'nosniff' always;
    add_header X-XSS-Protection '1; mode=block' always;
    add_header Referrer-Policy 'strict-origin-when-cross-origin' always;
    add_header Permissions-Policy 'geolocation=(), microphone=(), camera=()' always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.replit.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://fonts.googleapis.com https://cdn.replit.com; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data:; connect-src 'self';" always;
}
EOF
sudo nginx -t
if ! systemctl is-active --quiet nginx; then
    echo "[+] Nginx is not running. Starting nginx..."
    sudo systemctl start nginx
else
    echo "[+] Reloading nginx..."
    sudo systemctl reload nginx
fi

# --- Write systemd service file ---
echo "[+] Writing systemd service file..."
sudo bash -c "cat > /etc/systemd/system/wispr.service" <<EOF
[Unit]
Description=Wispr Team Collaboration Platform
After=network.target

[Service]
Type=simple
User=wispr
Group=wispr
WorkingDirectory=/var/www/wispr
EnvironmentFile=/var/www/wispr/.env
ExecStart=/var/www/wispr/wispr_env/bin/gunicorn -k eventlet -w 1 -b 127.0.0.1:5000 main:app
Restart=always
RestartSec=5
StandardOutput=append:/var/log/wispr/wispr.log
StandardError=append:/var/log/wispr/wispr.log

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable wispr.service
sudo systemctl restart wispr.service

# --- Final status ---
echo "[+] Deployment complete!"
echo "- Wispr should now be running at: https://$DOMAIN"
echo "- To check service status: sudo systemctl status wispr.service"
echo "- To check logs: sudo tail -f /var/log/wispr/wispr.log"
echo "- To re-run SSL: sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN"
echo "- To reload Nginx: sudo systemctl reload nginx" 
