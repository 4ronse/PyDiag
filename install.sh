#!/bin/bash

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logo and Branding
print_logo() {
    echo -e "${BLUE}"
    cat << "EOF"
 ____  _           _       _
|  _ \| |__  _   _(_)_ __ | |_
| |_) | '_ \| | | | | '_ \| __|
|  __/| | | | |_| | | | | | |_
|_|   |_| |_|\__,_|_|_| |_|\__|
    AUTOMATED INSTALLER
EOF
    echo -e "${NC}"
}

# Logging Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Determine the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set variables
SERVICE_NAME="pydiag"
PROJECT_DIR="${SCRIPT_DIR}"
VENV_PATH="${PROJECT_DIR}/venv"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_FILE="${PROJECT_DIR}/install.log"

# Clear previous log
> "${LOG_FILE}"

# Function to log and execute commands
execute_cmd() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Executing: $*" >> "${LOG_FILE}"
    log_info "[$(date '+%Y-%m-%d %H:%M:%S')] Executing: $*"
    "$@"
    local status=$?
    if [ $status -eq 0 ]; then
        log_info "Command executed successfully: $*"
    else
        log_error "Command failed with status $status: $*"
        exit 1
    fi
}

# Start installation
clear
print_logo
log_info "Starting Installation Process"
log_info "Project Directory: ${PROJECT_DIR}"

# Ensure script is run as root
if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root"
   exit 1
fi

# Create project directory if it doesn't exist
execute_cmd mkdir -p "${PROJECT_DIR}"
execute_cmd cd "${PROJECT_DIR}"

# Function to create or recreate Python virtual environment
create_venv() {
    log_info "Preparing Python Virtual Environment"

    # Remove existing venv if it exists
    if [ -d "${VENV_PATH}" ]; then
        log_warn "Existing virtual environment found. Removing..."
        execute_cmd rm -rf "${VENV_PATH}"
    fi

    # Create new virtual environment
    execute_cmd python3 -m venv "${VENV_PATH}"

    # Activate venv and install dependencies
    source "${VENV_PATH}/bin/activate"
    execute_cmd pip install --upgrade pip
    execute_cmd pip install -r requirements.txt
    deactivate

    log_info "Virtual Environment Created Successfully"
}

# Function to create systemd service
create_service() {
    log_info "Configuring Systemd Service"

    # Check if service already exists
    if [ -f "${SERVICE_FILE}" ]; then
        log_warn "Service file already exists. Skipping creation."
        return
    fi

    # Create systemd service file
    cat > "${SERVICE_FILE}" << EOL
[Unit]
Description=${SERVICE_NAME}
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${PROJECT_DIR}
ExecStart=${VENV_PATH}/bin/python ${PROJECT_DIR}/pydiag.py
Restart=always
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOL

    # Reload systemd to recognize new service
    execute_cmd systemctl daemon-reload
    log_info "Service Configuration Complete"
}

# Main script execution
create_venv

# Create service if it doesn't exist
create_service

# Enable and start service (or restart if it already exists)
log_info "Starting Service"
execute_cmd systemctl enable "${SERVICE_NAME}"
execute_cmd systemctl restart "${SERVICE_NAME}"

# Final status check
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    log_info "${SERVICE_NAME} is running successfully!"
else
    log_error "${SERVICE_NAME} failed to start. Check systemd status."
fi

echo -e "\n${GREEN}Installation Complete!${NC}"
echo "Detailed logs available at: ${LOG_FILE}"
