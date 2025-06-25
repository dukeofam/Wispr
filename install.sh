#!/bin/bash

# Wispr Foolproof Automated Installer
set -e

echo "🚀 Starting Wispr Auto-Installer"
echo "=========================================="

# Detect OS
detect_os() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "ubuntu"
    elif command -v yum >/dev/null 2>&1; then
        echo "centos"
    elif command -v pacman >/dev/null 2>&1; then
        echo "arch"
    else
        echo "unknown"
    fi
}

# Install required Python + venv
install_python_and_venv() {
    os=$(detect_os)
    echo "📦 Installing Python 3.12 and venv..."

    case $os in
        ubuntu)
            sudo apt-get update
            sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip
            sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1
            ;;
        centos)
            sudo yum install -y python3 python3-pip python3-venv
            ;;
        arch)
            sudo pacman -Sy --noconfirm python python-pip
            ;;
        *)
            echo "❌ Unsupported OS. Install Python 3.12+ and venv manually."
            exit 1
            ;;
    esac
}

# Ensure python3 is available
ensure_python() {
    if ! command -v python3 >/dev/null 2>&1; then
        install_python_and_venv
    fi

    PYTHON_CMD="python3"
    PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

    if [[ "$PYTHON_VERSION" < "3.8" ]]; then
        echo "⚠️  Python version $PYTHON_VERSION too old. Installing Python 3.12..."
        install_python_and_venv
    fi

    # Ensure venv works
    if ! $PYTHON_CMD -m ensurepip --version >/dev/null 2>&1; then
        echo "⚠️  ensurepip missing. Installing python3.12-venv..."
        install_python_and_venv
    fi
}

# Set up virtualenv
setup_venv() {
    echo "🔧 Creating virtual environment..."
    rm -rf wispr_env
    $PYTHON_CMD -m venv wispr_env
}

# Activate venv
activate_venv() {
    source wispr_env/bin/activate
}

# Ensure pip
ensure_pip() {
    if ! command -v pip3 >/dev/null && ! command -v pip >/dev/null; then
        echo "📦 Installing pip..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py | $PYTHON_CMD
    fi
}

# Install Python dependencies
install_dependencies() {
    echo "📦 Installing Python dependencies..."
    if [ -f "requirements_standalone.txt" ]; then
        pip install -r requirements_standalone.txt
    else
        pip install Flask==3.0.0 Flask-SQLAlchemy==3.1.1 SQLAlchemy==2.0.23 Werkzeug==3.0.1 email-validator==2.1.0 gunicorn==21.2.0
    fi
}

# Create run.sh
create_run_script() {
    echo "📝 Creating run.sh..."
    cat > run.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting Wispr..."
source wispr_env/bin/activate
if [ ! -f "main.py" ]; then
    echo "❌ main.py not found!"
    exit 1
fi
if [ -z "$SESSION_SECRET" ]; then
    export SESSION_SECRET="dev-secret-key-change-in-production"
    echo "⚠️  Using default session secret!"
fi
echo "🌐 Running on http://localhost:5000"
echo "📋 Default login: admin / admin123"
python main.py
EOF
    chmod +x run.sh
}

# Test installation
test_install() {
    echo "🧪 Testing Python environment..."
    $PYTHON_CMD -c "
try:
    import flask, flask_sqlalchemy, sqlalchemy, werkzeug
    print('✅ All dependencies are correctly installed.')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
    exit(1)
"
}

### MAIN EXECUTION FLOW ###
ensure_python
ensure_pip
setup_venv
activate_venv
pip install --upgrade pip
install_dependencies
create_run_script
test_install

# Final message
echo ""
echo "🎉 Wispr installed successfully!"
echo "👉 Run Wispr with: ./run.sh"
echo "🌐 Open: http://localhost:5000"
echo "🔐 Login: admin / admin123"
echo "⚠️  Change your password in production!"
