import asyncio

from fastmcp import FastMCP

from .bridge import SanchoBridgeNode

mcp = FastMCP("Sancho_MCP_Server")
sancho_node: SanchoBridgeNode | None = None
mock_mode: bool = False


def require_sancho_node() -> SanchoBridgeNode:
    if sancho_node is None:
        raise RuntimeError("ROS node is not initialized yet.")
    return sancho_node


def run_in_ros_thread(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


@mcp.tool()
async def get_topological_map() -> list:
    """Retrieves the list of available navigation points from the topology graph."""
    if mock_mode:
        return [
            {"id": 1, "name": "kitchen", "type": "space", "position": {"x": 1.0, "y": 2.0, "z": 0.0}},
            {"id": 2, "name": "living_room", "type": "space", "position": {"x": -3.0, "y": 4.5, "z": 0.0}},
            {"id": 3, "name": "office", "type": "space", "position": {"x": 5.0, "y": -1.5, "z": 0.0}},
            {"id": 4, "name": "corridor", "type": "space", "position": {"x": 0.0, "y": 0.0, "z": 0.0}},
            {"id": 5, "name": "charging_station", "type": "docking", "position": {"x": -1.0, "y": -1.0, "z": 0.0}},
        ]
    return await run_in_ros_thread(require_sancho_node().sync_get_topological_nodes)


@mcp.tool()
async def navigate_to_pose(
    x: float,
    y: float,
    w: float = 1.0,
    z: float = 0.0,
    wait_for_result: bool = True,
) -> str:
    """
    Sends the robot to a specific coordinate using Nav2.
    It expects map coordinates and optional orientation (w,z).
    Returns a human-readable status message when navigation finishes.
    """
    if mock_mode:
        await asyncio.sleep(0.5)
        return f"Navigation succeeded! Reached destination (mock: x={x}, y={y})."
    return await run_in_ros_thread(
        require_sancho_node().sync_navigate_to_pose,
        x,
        y,
        w,
        z,
        wait_for_result,
    )


@mcp.tool()
async def rotate_in_place(
    degrees: float,
    time_allowance_sec: float = 10.0,
    wait_for_result: bool = True,
) -> str:
    """
    Rotates the robot in place by the given degrees (positive CCW, negative CW).
    By default, waits for the action result.
    """
    if mock_mode:
        await asyncio.sleep(0.5)
        return f"Rotation of {degrees} degrees completed (mock)."
    return await run_in_ros_thread(
        require_sancho_node().sync_rotate_in_place,
        degrees,
        time_allowance_sec,
        wait_for_result,
    )


@mcp.tool()
async def take_photo() -> dict:
    """
    Captures an image from the robot's RGB camera and returns it as an MCP image payload.
    """
    if mock_mode:
        return {
            "type": "image",
            "mime_type": "image/jpeg",
            "data": "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=",
        }
    return await run_in_ros_thread(require_sancho_node().sync_take_photo_raw)


@mcp.tool()
async def get_current_pose() -> dict:
    """
    Returns the current robot pose from the localization stack (map frame).
    """
    if mock_mode:
        return {
            "frame_id": "map",
            "stamp": {"sec": 1716800000, "nanosec": 0},
            "stale": False,
            "source": "mock",
            "position": {"x": 1.2, "y": 3.4, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
        }
    return await run_in_ros_thread(require_sancho_node().sync_get_current_pose)


@mcp.tool()
async def speak(text: str, model: str = "", speaker: str = "") -> str:
    """
    Makes the robot speak out loud using the /play_tts Action Server.
    The action blocks until the robot finishes speaking and returns status.
    """
    if mock_mode:
        return f"TTS Success (mock): '{text}' spoken."
    return await run_in_ros_thread(require_sancho_node().sync_play_tts, text, model, speaker)

############################################################
# MISSION RELATED TOOLS
############################################################

@mcp.tool()
async def get_current_mission() -> dict:
    """Retrieves the currently active mission from the behavior tree blackboard."""
    if mock_mode:
        return {
            "mission_type": "idle",
            "status": "no_active_mission",
            "parameters": "{}",
            "queue_info": "No active mission (mock)",
        }
    return await run_in_ros_thread(require_sancho_node().sync_get_mission)

@mcp.tool()
async def pop_mission_from_blackboard() -> str:
    """Removes the next mission from the queue on the blackboard."""
    if mock_mode:
        return "popped: none (mock)"
    return await run_in_ros_thread(require_sancho_node().sync_pop_mission)

@mcp.tool()
async def clear_all_missions_from_blackboard() -> str:
    """Clears all pending missions from the behavior tree blackboard."""
    if mock_mode:
        return "cleared all missions (mock)"
    return await run_in_ros_thread(require_sancho_node().sync_clear_missions)

@mcp.tool()
async def mission_random_move(priority: int = 5) -> str:
    """Triggers the robot to execute a random exploration mission.
    
    Args:
        priority: Mission priority (lower = higher priority). Default is 5.
    """
    if mock_mode:
        return f"random move mission queued with priority {priority} (mock)"
    import json
    params = {"priority": priority}
    return await run_in_ros_thread(
        require_sancho_node().sync_execute_mission, 
        "roaming", 
        json.dumps(params)
    )

@mcp.tool()
async def mission_move_and_talk(target_pose: str, message: str, priority: int = 5) -> str:
    """
    Sends the robot to a named location (e.g. 'office', 'kitchen') or
    coordinates as 'x,y' and makes it speak the provided message upon arrival.
    
    Args:
        target_pose: A location name from the topological map, or coordinates as 'x,y'.
        message: The text the robot will speak when it arrives.
        priority: Mission priority (lower = higher priority). Default is 5.
    """
    if mock_mode:
        return f"move and talk mission to '{target_pose}' with message '{message}' queued with priority {priority} (mock)"
    import json
    params = {
        "target_pose": target_pose,
        "speech_text": message,
        "priority": priority,
    }

    #log the message and the target pose
    require_sancho_node().get_logger().info(f"Mission move and talk: {params}")
    
    return await run_in_ros_thread(
        require_sancho_node().sync_execute_mission, 
        "move_and_talk", 
        json.dumps(params)
    )

###################################################