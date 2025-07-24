import ast

from rclpy.node import Node
from abc import ABC, abstractmethod
from ros2web_msgs.srv import R2WSubscribe


class DynamicSubscribableNode(Node, ABC):

    def __init__(self, node_name):
        super().__init__(node_name)

        self.dynamic_subscriptions = []

        topics_str = self.declare_parameter('topics', "[]").get_parameter_value().string_value
        for [topic_name, name] in self.parse_topics(topics_str):
            self.subscribe_to_topic(topic_name, name)
        
        self.subscribe_serv = self.create_service(R2WSubscribe, "ros2web/subscribe", self.subscribe_service)

    def subscribe_to_topic(self, topic_name, name=None):
        name = name if name else topic_name # Prepara name
        topic_name = topic_name if topic_name.startswith("/") else "/" + topic_name # Prepara topic name
        topic_types = dict(self.get_topic_names_and_types()) # Diccionario topic: tipo

        actual_topics = [t.topic_name for t in self.dynamic_subscriptions] # Comprueba si ya esta subscrito
        if topic_name in actual_topics:
            self.get_logger().warn(f"Already subscribed to {topic_name}")
            return 0
        
        if topic_name not in topic_types: # Comprueba si el topic esta disponible, si no, reintenta subscribirse al segundo
            self.get_logger().warn(f"Topic {topic_name} not found. Will retry in 1 second.")

            def retry_callback():
                self.subscribe_to_topic(topic_name, name)
                retry_timer.cancel() # ver como hacer mejor sin timer que se cancela algo que sea como setTimeout en javascript

            retry_timer = self.create_timer(1.0, retry_callback)
            return 0
        
        topic_type = topic_types[topic_name][0] # Saca el tipo y lo importa
        data = topic_type.split('/')
        msg_module_name = ".".join(data[:-1])
        msg_class_name = data[-1]

        try:
            msg_module = __import__(msg_module_name, fromlist=[msg_class_name])
            msg_class = getattr(msg_module, msg_class_name)
        except (ImportError, AttributeError) as e:
            self.get_logger().error(f"Cannot import type {topic_type}: {e}")
            return 0

        callback = lambda msg, tn=topic_name, nm=name: self.generic_callback(tn, nm, msg) # callback
        auto_subscription = self.create_subscription(msg_class, topic_name, callback, 1) # se subscribe
        self.dynamic_subscriptions.append(auto_subscription) # guarda la subscripcion
        self.get_logger().info(f"Succesfully subscribed to topic {topic_name}")

        return 1

    def subscribe_service(self, request, response):
        success = self.subscribe_to_topic(request.topic, request.name)
        response.value = success
        return response

    def parse_topics(self, raw_string):
        return ast.literal_eval(raw_string)

    @abstractmethod
    def generic_callback(self, topic, name, value):
        pass