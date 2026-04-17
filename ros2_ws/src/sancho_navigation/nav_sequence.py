import rclpy
from nav2_simple_commander.robot_navigator import BasicNavigator
from geometry_msgs.msg import PoseStamped

def main():
    rclpy.init()
    nav = BasicNavigator()

    # Define your three points
    points = [
        [38.49, 3.78, 0.0],
        [-48.51, -4.45, 0.0],
        [-0.35, -0.07, 0.19]
    ]

    # Helper to create PoseStamped
    def create_pose(coords):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = nav.get_clock().now().to_msg()
        pose.pose.position.x = coords[0]
        pose.pose.position.y = coords[1]
        pose.pose.position.z = coords[2]
        pose.pose.orientation.w = 1.0
        return pose

    # Wait for Nav2 to be active
    nav.waitUntilNav2Active()

    for pt in points:
        goal_pose = create_pose(pt)
        print(f"Sending goal: {pt}")
        
        nav.goToPose(goal_pose)

        # Loop until the goal is finished
        while not nav.isTaskComplete():
            # You can add feedback processing here if needed
            pass

        result = nav.getResult()
        print(f"Goal finished with result: {result}")

    rclpy.shutdown()

if __name__ == '__main__':
    main()