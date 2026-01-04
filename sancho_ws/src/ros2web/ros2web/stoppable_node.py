import rclpy
from abc import ABC, abstractmethod


class StoppableNode(ABC):

    def __init__(self):
        self.run_node = True

    def stop(self):
        self.run_node = False

    def run(self):
        try:
            while rclpy.ok() and self.run_node:
                self.spin()
                rclpy.spin_once(self.node)
        except Exception as e:
            print("ERROR ON SPIN:", e)
    
    @abstractmethod
    def spin(self):
        pass