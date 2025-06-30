import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_session import Session
from logging.handlers import RotatingFileHandler
from datetime import timedelta

# Set up logging
if os.environ.get("FLASK_ENV") == "production":
    log_level = logging.INFO
    log_file = os.environ.get("LOG_FILE", "wispr.log")
    handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    handler.setFormatter(formatter)
    logging.basicConfig(level=log_level, handlers=[handler])
else:
    logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)

# Enforce secure session secret in production
if os.environ.get("FLASK_ENV") == "production" and os.environ.get("SESSION_SECRET") in (None, "", "dev-secret-key-change-in-production"):
    raise RuntimeError("SESSION_SECRET must be set to a secure value in production!")

# Debug prints for troubleshooting
print("SESSION_SECRET env:", os.environ.get("SESSION_SECRET"))
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
print("Flask app.secret_key:", app.secret_key)

# Secure session cookies
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
# Session timeout: 30 minutes idle, 8 hours absolute
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["SESSION_REFRESH_EACH_REQUEST"] = True

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///team_collaboration.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# Initialize SocketIO with session handling
if os.environ.get("FLASK_ENV") == "production":
    cors_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "https://yourdomain.com").split(",")
else:
    cors_origins = "*"
socketio = SocketIO(app, cors_allowed_origins=cors_origins, manage_session=False)

# Enable CSRF protection
csrf = CSRFProtect(app)

# Use server-side session storage in production only
if os.environ.get("FLASK_ENV") == "production":
    app.config["SESSION_TYPE"] = os.environ.get("SESSION_TYPE", "filesystem")  # Recommend 'redis' in production
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_USE_SIGNER"] = True
    app.config["SESSION_FILE_DIR"] = os.environ.get("SESSION_FILE_DIR", "/tmp/wispr_sessions")
    # For Redis: set SESSION_TYPE='redis' and configure SESSION_REDIS
    Session(app)

# Rate limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

with app.app_context():
    # Import models to ensure tables are created
    import models
    db.create_all()
    
    # Create default admin user if it doesn't exist
    from werkzeug.security import generate_password_hash
    admin_user = models.User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_user = models.User(
            username='admin',
            email='admin@company.com',
            password_hash=generate_password_hash('admin123'),
            is_admin=True
        )
        db.session.add(admin_user)
        db.session.commit()
        logging.info("Created default admin user (username: admin, password: admin123)")

# Import routes
import routes

@app.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=generate_csrf)
