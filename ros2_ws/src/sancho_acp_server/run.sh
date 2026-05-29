#!/usr/bin/env bash
# ------------------------------------------------------------------
# run.sh — Launch the Sancho ACP TCP server.
#
# Creates and activates a virtual environment, installs dependencies,
# and starts the ACP server listening for TCP connections.
# ------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

# Create virtual environment if it does not exist.
if [ ! -d "${VENV_DIR}" ]; then
    echo "📦 Creating virtual environment in ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
fi

# Activate virtual environment.
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# Install / update dependencies.
echo "📦 Installing dependencies..."
pip install --quiet -r "${REQUIREMENTS}"

# Launch the ACP TCP server.
echo "🚀 Starting Sancho ACP server..."
python3 -m sancho_acp_server.tcp_server "$@"
