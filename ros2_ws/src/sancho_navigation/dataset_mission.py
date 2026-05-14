#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
import time
import logging
from datetime import datetime

# --- SET UP FILE LOGGING ---
log_filename = f"mission_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler() # Also prints to the terminal
    ]
)

# Make sure this matches your actual package name!
from sancho_interfaces.action import RotateHead 

def set_head_angle(node, angle_deg, timeout=10.0):
    logging.info('Waiting for Head Action Server to become available...')
    action_client = ActionClient(node, RotateHead, '/head_controller/rotate')
    
    if not action_client.wait_for_server(timeout_sec=5.0):
        logging.error("CRITICAL: Head Action Server is NOT responding!")
        return False
    
    goal_msg = RotateHead.Goal()
    goal_msg.target_angle_deg = float(angle_deg)
    goal_msg.timeout_sec = timeout
    
    logging.info(f'Sending head goal: {angle_deg} degrees.')
    send_goal_future = action_client.send_goal_async(goal_msg)
    rclpy.spin_until_future_complete(node, send_goal_future)
    
    goal_handle = send_goal_future.result()
    if not goal_handle.accepted:
        logging.error('Head rotation goal was REJECTED by the server.')
        return False
        
    logging.info('Head goal accepted. Waiting for physical movement...')
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    
    result = result_future.result().result
    if result.success:
        logging.info('Head successfully locked in position.')
        return True
    else:
        logging.error(f'Head rotation failed. Message: {result.message}')
        return False

def main():
    rclpy.init()
    mission_node = rclpy.create_node('dataset_mission_node')
    logging.info("--- NEW MISSION STARTED ---")
    
    # 1. Lock the head at 90 degrees
    success = set_head_angle(mission_node, 90.0)
    if not success:
        logging.error("Aborting mission due to head failure.")
        mission_node.destroy_node()
        rclpy.shutdown()
        return

    # 2. Initialize Nav2 Navigator
    logging.info("Initializing Nav2 Simple Commander...")
    navigator = BasicNavigator()
    navigator.waitUntilNav2Active()
    logging.info("Nav2 is active and ready.")

    # 3. Trajectory Points
    target_points = [
        (-3.0670597553253174,   3.321981430053711),   # Point 0
        (-0.2223987579345703,  -0.09076118469238281), # Point 1
        #(39.46440124511719,     3.4076385498046875),  # Point 2
        (19.46440124511719,     1.7076385498046875),  # Point 2
        #(-49.349056243896484,  -4.626741409301758),   # Point 3
        (-25.349056243896484,  -2.326741409301758),
        (-0.6109123229980469,  -0.2106800079345703),  # Point 4
        (-7.275995254516602,    1.7265782356262207)   # Point 5
    ]

    waypoints = []
    for x, y in target_points:
        pt = PoseStamped()
        pt.header.frame_id = 'map'
        pt.pose.position.x = float(x)
        pt.pose.position.y = float(y)
        pt.pose.orientation.w = 1.0 
        waypoints.append(pt)

    # 4. Execute the Navigation 
    logging.info(f"Starting sequential navigation through {len(waypoints)} points.")
    
    for i, waypoint in enumerate(waypoints):
        waypoint.header.stamp = navigator.get_clock().now().to_msg()
        
        logging.info(f">>> SENDING GOAL {i}: X={waypoint.pose.position.x:.2f}, Y={waypoint.pose.position.y:.2f} <<<")
        navigator.goToPose(waypoint)
        
        # Monitor the execution loop without micromanaging distance
        while not navigator.isTaskComplete():
            feedback = navigator.getFeedback()
            
            # Print feedback if we have it, but don't cancel if it gets stuck/stale
            if feedback:
                logging.info(f"[Goal {i}] Distance remaining: {feedback.distance_remaining:.2f} meters")
            else:
                # This will only print if we haven't received a SINGLE feedback packet yet
                logging.warning(f"[Goal {i}] Waiting for initial feedback...")
            
            # Sleep longer to avoid spamming the logs when network is slow
            time.sleep(2.0) 
            
        # Evaluate the result of the point based on Nav2's internal logic
        result = navigator.getResult()
        if result == TaskResult.SUCCEEDED:
            logging.info(f"SUCCESS: Arrived safely at Point {i}.")
        elif result == TaskResult.CANCELED:
            logging.warning(f"CANCELED: Point {i} was canceled manually or by system. Moving to next.")
        elif result == TaskResult.FAILED:
            # If Nav2 couldn't recover, it will fail here.
            logging.error(f"FAILED: Nav2 completely rejected or failed Point {i}. Robot is genuinely stuck.")
        else:
            logging.error(f"UNKNOWN ERROR on Point {i}. Result code: {result}")

    logging.info("--- MISSION SCRIPT FINISHED ---")
    mission_node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()