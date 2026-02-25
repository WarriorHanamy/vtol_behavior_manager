#!/bin/bash
# =============================================================================
# Setup TensorRT Virtual Environment for neural_pos_ctrl
# =============================================================================
#
# This script creates a Python virtual environment with TensorRT support
# using uv for fast package installation.
#
# Usage:
#   ./setup_tensorrt_venv.sh          # Create venv with default settings
#   ./setup_tensorrt_venv.sh --reinstall  # Reinstall existing venv
#
# The virtual environment will be created at:
#   .venv_tensorrt/
#
# =============================================================================

set -e  # Exit on error

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
VENV_PATH=".venv_tensorrt"
PYTHON_VERSION="3.10"

# Parse arguments
REINSTALL=false

for arg in "$@"; do
    case $arg in
        --reinstall)
            REINSTALL=true
            shift
            ;;
        *)
            ;;
    esac
done

echo -e "${BLUE}==================================================${NC}"
echo -e "${BLUE}neural_pos_ctrl - TensorRT Environment Setup${NC}"
echo -e "${BLUE}==================================================${NC}"
echo ""

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv not found. Installing uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo -e "${GREEN}✓${NC} uv found: $(uv --version)"

# Check if reinstall requested
if [ "$REINSTALL" = true ] && [ -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}Removing existing virtual environment...${NC}"
    rm -rf "$VENV_PATH"
fi

# Create virtual environment
if [ ! -d "$VENV_PATH" ]; then
    echo ""
    echo -e "${BLUE}Creating virtual environment at: $VENV_PATH${NC}"
    uv venv "$VENV_PATH" --python "$PYTHON_VERSION"
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${GREEN}✓${NC} Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"

# Upgrade pip
echo ""
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --upgrade pip setuptools wheel
echo -e "${GREEN}✓${NC} pip upgraded"

# Install core dependencies
echo ""
echo -e "${BLUE}Installing core dependencies...${NC}"
uv pip install --upgrade \
    numpy \
    pytest \
    pytest-cov \
    pytest-mock
echo -e "${GREEN}✓${NC} Core dependencies installed"

# Install ONNX Runtime
echo ""
echo -e "${BLUE}Installing ONNX Runtime...${NC}"
uv pip install --upgrade \
    onnx \
    onnxruntime-gpu
echo -e "${GREEN}✓${NC} ONNX Runtime installed"

# Install TensorRT
echo ""
echo -e "${BLUE}Installing TensorRT...${NC}"
# Check if TensorRT is available via system packages
if [ -d "/usr/local/lib/python3.10/dist-packages" ]; then
    # Try to use system TensorRT
    echo -e "${YELLOW}Attempting to use system TensorRT...${NC}"
    # Add system packages to Python path
    echo "import sys; sys.path.append('/usr/local/lib/python3.10/dist-packages')" >> "$VENV_PATH/lib/python*/site-packages/_tensorrt_path.pth"
fi

# Install TensorRT Python package (may not be available via pip)
uv pip install --upgrade \
    nvidia-tensorrt \
    nvidia-pyindex \
    pycuda || echo -e "${YELLOW}Warning: TensorRT installation may have failed. You may need to install from NVIDIA packages.${NC}"
echo -e "${GREEN}✓${NC} TensorRT installation complete"

# Install additional dependencies
echo ""
echo -e "${BLUE}Installing additional dependencies...${NC}"
uv pip install --upgrade \
    hydra-core \
    omegaconf
echo -e "${GREEN}✓${NC} Additional dependencies installed"

# Display summary
echo ""
echo -e "${BLUE}==================================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${BLUE}==================================================${NC}"
echo ""
echo -e "Virtual environment: ${GREEN}$VENV_PATH${NC}"
echo -e "Python executable:   ${GREEN}$(which python)${NC}"
echo -e "Python version:      ${GREEN}$(python --version)${NC}"
echo ""
echo -e "${BLUE}To activate the environment, run:${NC}"
echo -e "  ${GREEN}source $VENV_PATH/bin/activate${NC}"
echo ""
echo -e "${BLUE}To run tests with this environment:${NC}"
echo -e "  ${GREEN}./run_tests --env tensorrt${NC}"
echo ""
echo -e "${BLUE}To deactivate:${NC}"
echo -e "  ${YELLOW}deactivate${NC}"
echo ""
