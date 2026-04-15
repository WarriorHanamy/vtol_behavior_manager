#!/bin/bash
#
# install-neural-services.sh
#
# Install neural_executor and neural_infer systemd user services
# This script links repo-managed unit files into ~/.config/systemd/user
#

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory (repo root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_SERVICES_DIR="${SCRIPT_DIR}"
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"

# Check if we're running as root (should NOT run as root)
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${RED}Error: This script should NOT be run as root.${NC}"
    echo -e "${YELLOW}Systemd user services should be installed for the current user.${NC}"
    exit 1
fi

# Create user systemd directory if it doesn't exist
mkdir -p "${USER_SYSTEMD_DIR}"

# Function to install a service
install_service() {
    local service_name="$1"
    local source="${REPO_SERVICES_DIR}/${service_name}"
    local target="${USER_SYSTEMD_DIR}/${service_name}"

    if [ ! -f "${source}" ]; then
        echo -e "${RED}Error: Service file not found: ${source}${NC}"
        return 1
    fi

    # Remove existing symlink if present
    if [ -L "${target}" ]; then
        echo "Removing existing symlink: ${target}"
        rm -f "${target}"
    elif [ -f "${target}" ]; then
        echo -e "${YELLOW}Warning: Regular file exists at ${target} - skipping${NC}"
        echo -e "${YELLOW}Manually remove the file if you want to install from repo${NC}"
        return 1
    fi

    # Create symbolic link
    echo "Installing ${service_name}..."
    ln -s "${source}" "${target}"
    echo -e "${GREEN}✓ Linked ${service_name} to ${target}${NC}"

    return 0
}

echo "=================================================="
echo "Installing Neural Services (User Systemd Units)"
echo "=================================================="
echo "Repo: ${SCRIPT_DIR}"
echo "Target: ${USER_SYSTEMD_DIR}"
echo ""

# Install services
# Order matters: targets before services, sim-session first
SERVICES=(
    "sim-session.service"
    "neural.target"
    "test.target"
    "neural_executor.service"
    "neural_infer.service"
    "test_executor.service"
)
FAILED=()

for service in "${SERVICES[@]}"; do
    if ! install_service "${service}"; then
        FAILED+=("${service}")
    fi
done

echo ""

# Reload systemd user daemon
echo "Reloading systemd user daemon..."
systemctl --user daemon-reload
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Systemd user daemon reloaded${NC}"
else
    echo -e "${RED}✗ Failed to reload systemd user daemon${NC}"
    echo "You may need to run: systemctl --user daemon-reload"
fi

echo ""

# Report results
if [ ${#FAILED[@]} -eq 0 ]; then
    echo -e "${GREEN}=================================================="
    echo "All services installed successfully!"
    echo "==================================================${NC}"
    echo ""
    echo "Architecture:"
    echo "  sim-session.service  (main service, controls docker compose)"
    echo "  ├── neural.target    (Group A: neural_executor only)"
    echo "  └── test.target      (Group B: test_executor with joystick)"
    echo ""
    echo "Quick Start:"
    echo "  systemctl --user start sim-session.service    # Start sim + Group A (default)"
    echo "  systemctl --user stop sim-session.service     # Stop everything"
    echo ""
    echo "Switch Groups (mutually exclusive):"
    echo "  systemctl --user isolate neural.target        # Switch to Group A"
    echo "  systemctl --user isolate test.target          # Switch to Group B"
    echo ""
    echo "Check status:"
    echo "  systemctl --user status sim-session.service"
    echo "  systemctl --user status neural.target"
    echo "  systemctl --user status test.target"
    exit 0
else
    echo -e "${RED}=================================================="
    echo "Some services failed to install"
    echo "==================================================${NC}"
    for service in "${FAILED[@]}"; do
        echo -e "  ${RED}✗ ${service}${NC}"
    done
    echo ""
    echo "Check for conflicts in ${USER_SYSTEMD_DIR}"
    exit 1
fi
