#!/bin/bash
# Resolve the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Source ROS 2 if available
if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

# Source ROS 2 workspace installation if available
if [ -f "../../install/setup.bash" ]; then
    source ../../install/setup.bash
elif [ -f "/home/mapir/sancho_mcp/ros2_ws/install/setup.bash" ]; then
    source /home/mapir/sancho_mcp/ros2_ws/install/setup.bash
fi

# Activate local virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the client
python3 client.py "$@"
