# sancho_mcp_server

`sancho_mcp_server` is a ROS 2 package that exposes Sancho robot capabilities through an MCP server built with `fastmcp==3.3.1`.

It bridges the robot's ROS 2 interfaces so an external MCP client can:
- query the topology graph used for navigation,
- send Nav2 goals to specific coordinates,
- capture an RGB camera frame and describe it with a vision-language model,
- request text to be spoken through the robot's TTS action server.

## What it uses

The package integrates with these ROS 2 interfaces:

- `nav2_msgs/action/NavigateToPose`
- `topology_graph/srv/Graph`
- `sancho_interfaces/action/PlayTTS`
- `sensor_msgs/msg/Image`
- `cv_bridge`

It also uses LangChain's OpenAI wrapper to connect to a local LMStudio server for vision-language inference.

The MCP server runs over HTTP using FastMCP's streamable HTTP transport, so it can be accessed from another machine on the network.

## Available MCP tools
- `get_topological_map`: returns the available navigation nodes from `/topology_graph/graph`.
- `navigate_to_pose(x, y, w=1.0, z=0.0, wait_for_result=true)`: sends a Nav2 goal in the `map` frame. By default it waits for completion.
- `rotate_in_place(degrees, time_allowance_sec=10.0, wait_for_result=true)`: rotates the base in place (positive CCW, negative CW). By default it waits for completion.
- `get_current_pose()`: returns the current robot pose from `/amcl_pose` in the `map` frame (falls back to TF `map -> base_link` and marks the source).
- `take_photo()`: waits for one RGB frame from `/sancho_camera/image_rect` and returns an MCP image payload.
- `interpret_photo()`: captures one RGB frame and returns a natural language description.
- `speak(text, model="", speaker="")`: sends a blocking TTS request through `/play_tts`.

## Requirements

- Ubuntu 22.04 with ROS 2 Humble.
- The Sancho workspace built and sourced.
- The local Python virtual environment (`.venv/`) located inside the `sancho_mcp_server` package.
- `langchain-openai==1.2.1` and `langchain-core==1.4.0` installed in this virtual environment.
- The relevant ROS 2 packages available in the workspace or underlaid environment.

The vision tool expects LMStudio to be reachable at `http://lmstudio.jemonra.uedge.mapir:1234` by default and uses the `google/gemma-4-31b` model unless overridden with environment variables.

## Build

From the workspace root:

```bash
cd /home/mapir/sancho_mcp/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select sancho_mcp_server
source install/setup.bash
```

## Run

Because `fastmcp` and its dependencies are installed inside the Python virtual environment (`.venv`), you must ensure the Python interpreter can locate them.

There are two ways to run the server:

### Option A: Direct Python Execution (Recommended)
Since sourcing `install/setup.bash` adds the ROS 2 packages to your `PYTHONPATH`, you can run the server directly using the virtual environment's Python interpreter. This is the simplest method.

```bash
# 1. Activate the local virtual environment
source /home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_server/.venv/bin/activate

# 2. Source the ROS 2 environment and workspace setup
source /opt/ros/humble/setup.bash
source /home/mapir/sancho_mcp/ros2_ws/install/setup.bash

# 3. Run the server module
python3 -m sancho_mcp_server.server \
  --transport http \
  --host 0.0.0.0 \
  --port 8000
```

### Option B: Running as a ROS 2 Node (`ros2 run`)
When you build the workspace, ROS 2 generates a script wrapper for the console entry points in `install/sancho_mcp_server/lib/sancho_mcp_server/sancho_mcp_server`. This script contains a hardcoded shebang `#!/usr/bin/python3`, which means `ros2 run` will execute it using the system Python interpreter instead of your virtual environment's interpreter. 

To use `ros2 run`, you must explicitly pass the virtual environment's `site-packages` directory in the `PYTHONPATH` environment variable:

```bash
# 1. Source ROS 2 and workspace setup
source /opt/ros/humble/setup.bash
source /home/mapir/sancho_mcp/ros2_ws/install/setup.bash

# 2. Run the node via ros2 run, extending PYTHONPATH with the virtual environment's dependencies
PYTHONPATH=$PYTHONPATH:/home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_server/.venv/lib/python3.10/site-packages \
ros2 run sancho_mcp_server sancho_mcp_server \
  --transport http \
  --host 0.0.0.0 \
  --port 8000
```

The MCP endpoint will be available at:

```text
http://<robot-ip>:8000/mcp
```

Replace `<robot-ip>` with the IP address of the robot or the machine running the server.

## Notes

- `http` is the default transport in this package.
- `stdio` remains available for local testing only.
- If the camera or navigation tools return errors, check that the corresponding ROS 2 nodes are already running.
- `get_current_pose` expects a localization node publishing `/amcl_pose` in the `map` frame. When the topic is idle, it returns the last known pose with `stale: true`. If no pose has ever been received, it falls back to TF lookup `map -> base_link`.
- If `cv_bridge` or the custom interfaces cannot be imported, make sure the ROS 2 environment and workspace overlays are sourced before starting the server.
- To override the vision backend, set `SANCHO_MCP_LMSTUDIO_BASE_URL`, `SANCHO_MCP_LVLM_MODEL`, `SANCHO_MCP_LVLM_MAX_TOKENS` (default 2048), or `SANCHO_MCP_LMSTUDIO_API_KEY` before starting the server.
