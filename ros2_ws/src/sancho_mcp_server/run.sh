#!/usr/bin/env bash
# ------------------------------------------------------------------
# run.sh — Launch the Sancho MCP Server.
#
# Creates and activates a virtual environment (with system site-packages
# enabled for ROS 2 compatibility), installs dependencies,
# and starts the FastMCP server.
# ------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

# Create virtual environment if it does not exist.
if [ ! -d "${VENV_DIR}" ]; then
    echo "📦 Creating virtual environment in ${VENV_DIR}..."
    python3 -m venv --system-site-packages "${VENV_DIR}"
fi

# Source ROS 2 base and workspace overlay if available.
WORKSPACE_SETUP="$(cd "${SCRIPT_DIR}/../../" && pwd)/install/setup.bash"
set +u
if [ -f "${WORKSPACE_SETUP}" ]; then
    echo "🔄 Sourcing ROS 2 workspace overlay at ${WORKSPACE_SETUP}..."
    # shellcheck disable=SC1090
    source "${WORKSPACE_SETUP}"
elif [ -f "/opt/ros/humble/setup.bash" ]; then
    echo "🔄 Sourcing global ROS 2 setup..."
    # shellcheck disable=SC1091
    source "/opt/ros/humble/setup.bash"
fi
set -u

# Activate virtual environment.
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# Install / update dependencies.
echo "📦 Installing dependencies..."
pip install --quiet -r "${REQUIREMENTS}"

# Launch the MCP server.
echo "🚀 Starting Sancho MCP server..."
python3 -m sancho_mcp_server.server "$@"
