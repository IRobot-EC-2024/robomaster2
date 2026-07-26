#!/usr/bin/env python3

from rclpy.node import Node


class PublisherPool:
    """A simple publisher pool to manage multiple ROS2 publishers."""

    def __init__(self, node: Node):
        self.node = node
        self.publishers = {}

    def publish(self, topic, msg_type, msg):
        if topic not in self.publishers:
            self.publishers[topic] = self.node.create_publisher(
                msg_type, topic, 10)
            self.node.get_logger().info(
                f"Created publisher for topic: {topic}, type: {msg_type.__name__}, qos: 10")
        self.publishers[topic].publish(msg)
