#!/usr/bin/env python3

from rqt_gui_py.plugin import Plugin

from rm_referee_msgs.msg import KeyboardMouseControl

from rm_referee_mock.keyboard_publisher_widget import KeyboardPublisherWidget
from rm_referee_mock.publisher_pool import PublisherPool


class KeyboardPublisherPlugin(Plugin):
    """RQt Plugin for keyboard input publishing"""

    def __init__(self, context):
        super(KeyboardPublisherPlugin, self).__init__(context)
        self.setObjectName("KeyboardPublisherPlugin")

        self._widget = KeyboardPublisherWidget()

        if context.serial_number() > 1:
            self._widget.setWindowTitle(
                self._widget.windowTitle() + (" (%d)" % context.serial_number()))

        context.add_widget(self._widget)
        self._node = context.node

        # Initialize PublisherPool and timer
        self._publisher_pool = PublisherPool(self._node)
        self._timer = None
        self._current_rate = 0.0

        # Create initial timer
        self._update_timer()

        # Connect to widget's rate change signal to update timer
        self._widget.rate_edit.editingFinished.connect(
            self._update_timer)

        # Connect widget signal
        self._widget.keyboard_state_changed.connect(
            self._on_keyboard_state_changed)

    def _update_timer(self):
        """Update timer when rate changes"""
        new_rate = self._widget.get_publish_rate()

        # Check if we need to update
        rate_changed = abs(new_rate - self._current_rate) > 0.001

        if not rate_changed:
            return

        # Destroy old timer
        if self._timer:
            self._timer.cancel()
            self._timer = None

        # Create new timer
        timer_period = 1.0 / new_rate
        self._timer = self._node.create_timer(
            timer_period, self._timer_callback)
        self._current_rate = new_rate
        self._node.get_logger().info(
            f"Timer updated - Rate: {new_rate} Hz")

    def _timer_callback(self):
        """Timer callback to publish keyboard state periodically"""
        msg = KeyboardMouseControl()
        msg.header.stamp = self._node.get_clock().now().to_msg()
        msg.keyboard_value = self._widget.get_keyboard_value()
        msg.mouse_x = 0
        msg.mouse_y = 0
        msg.mouse_z = 0
        msg.left_button_down = False
        msg.right_button_down = False
        msg.mid_button_down = False

        topic = self._widget.get_publish_topic()
        self._publisher_pool.publish(topic, KeyboardMouseControl, msg)

    def _on_keyboard_state_changed(self, keyboard_value):
        """Callback when keyboard state changes in the widget"""
        # Could add immediate publishing here if needed, or just rely on timer
        pass

    def shutdown_plugin(self):
        """Clean up when plugin is closed"""
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def save_settings(self, plugin_settings, instance_settings):
        """Save the plugin settings"""
        # Could save topic name and rate here if needed
        pass

    def restore_settings(self, plugin_settings, instance_settings):
        """Restore the plugin settings"""
        # Could restore topic name and rate here if needed
        pass
