#!/bin/bash

# mcpbr one-liner installer
# Usage: curl -sSL https://raw.githubusercontent.com/greynewell/mcpbr/main/install.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  mcpbr - Quick Start Installer      ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════╝${NC}"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not installed${NC}"
    echo "Please install Python 3.11 or higher and try again"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.11"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python ${REQUIRED_VERSION} or higher is required${NC}"
    echo "Current version: ${PYTHON_VERSION}"
    exit 1
fi

echo -e "${GREEN}✓ Python ${PYTHON_VERSION} detected${NC}"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}Error: pip is required but not installed${NC}"
    echo "Please install pip and try again"
    exit 1
fi

echo -e "${GREEN}✓ pip detected${NC}"
echo ""

# Install mcpbr
echo -e "${CYAN}Installing mcpbr...${NC}"
if pip3 install --upgrade mcpbr > /dev/null 2>&1; then
    echo -e "${GREEN}✓ mcpbr installed successfully${NC}"
else
    echo -e "${RED}Error: Failed to install mcpbr${NC}"
    echo "Try running manually: pip3 install mcpbr"
    exit 1
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Installation Complete!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# Show next steps
echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo -e "  1. Run a quick test (1 task):"
echo -e "     ${YELLOW}mcpbr run -n 1${NC}"
echo ""
echo -e "  2. Edit the auto-generated mcpbr.yaml to configure your MCP server"
echo ""
echo -e "  3. Run a larger evaluation:"
echo -e "     ${YELLOW}mcpbr run -n 10${NC}"
echo ""
echo -e "${CYAN}Documentation:${NC} https://greynewell.github.io/mcpbr/"
echo -e "${CYAN}Need help?${NC} https://github.com/greynewell/mcpbr/issues"
echo ""

# Ask if user wants to run a quick test (only in interactive mode)
if [ -t 0 ] || [ -t 1 ]; then
    # Interactive mode: ask the user
    read -p "Would you like to run a quick test now? (y/N) " -n 1 -r </dev/tty
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${CYAN}Running quick test with 1 task...${NC}"
        echo -e "${YELLOW}Note: This will auto-create mcpbr.yaml if it doesn't exist${NC}"
        echo ""
        mcpbr run -n 1 -v
    fi
else
    # Non-interactive mode (piped): skip test
    echo -e "${YELLOW}Tip: Run 'mcpbr run -n 1' to test your installation${NC}"
fi
