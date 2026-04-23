#!/bin/bash
#
# install-neural-services.sh
#
# Install sim-session systemd user service
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
SERVICES=(
    "sim-session.service"
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
echo ""
echo "Quick Start (simulation):"
echo "  make sim                    # Start simulation (docker compose)"
echo ""
echo "Neural services (neural_gate, neural_infer) run in tmux."
echo "Use 'make install' only for sim-session.service management."
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
