#!/usr/bin/env python3

import math
from os import path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout,
    QGroupBox, QFormLayout, QLabel, QComboBox, QDoubleSpinBox, QGridLayout
)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer
from PyQt5.QtGui import QPainter, QPixmap, QPen, QColor, QFont, QMouseEvent

from rm_referee_mock.widget_confirmed_line_edit import ConfirmedLineEdit
from ament_index_python.packages import get_package_share_directory

PACKAGE_SHARE = get_package_share_directory("rm_referee_mock")

# Referee-system official field coordinates, matching GroundRobotPosition:
# origin at the lower-left corner of the map, +X right, +Y up.
FIELD_MIN_X = 0.0
FIELD_MAX_X = 28.0
FIELD_MIN_Y = 0.0
FIELD_MAX_Y = 15.0
FIELD_WIDTH = FIELD_MAX_X - FIELD_MIN_X
FIELD_HEIGHT = FIELD_MAX_Y - FIELD_MIN_Y


class MapWidget(QWidget):
    """Widget for displaying map and robot positions"""

    # Robot IDs
    ROBOTS = {
        'hero': {'id': 1, 'name': '英雄', 'color': QColor(255, 0, 0)},
        'engineer': {'id': 2, 'name': '工程', 'color': QColor(255, 100, 0)},
        'standard_3': {'id': 3, 'name': '步兵3', 'color': QColor(255, 200, 0)},
        'standard_4': {'id': 4, 'name': '步兵4', 'color': QColor(0, 255, 0)},
        'sentry': {'id': 7, 'name': '哨兵', 'color': QColor(0, 200, 255)},
    }

    def __init__(self, map_image_path):
        super().__init__()
        self.map_pixmap = QPixmap(map_image_path)
        self.sentry_id = 7

        # Initialize robot positions (in field coordinates)
        self.robot_positions = {
            'hero': {'x': 17.5, 'y': 5.0, 'angle': 0.0},
            'engineer': {'x': 15.0, 'y': 3.0, 'angle': 0.0},
            'standard_3': {'x': 15.0, 'y': 7.0, 'angle': 0.0},
            'standard_4': {'x': 12.0, 'y': 5.0, 'angle': 0.0},
            'sentry': {'x': 20.0, 'y': 5.0, 'angle': 0.0},
        }

        self.dragging_robot = None
        self.dragging_angle = None  # For right-click angle dragging
        self.setMinimumSize(400, 400)
        self._scaled_rect = QRect()  # Store the actual rendered map rectangle

    def _get_scaled_map_rect(self):
        """Get the rectangle where the map is actually drawn (keeping aspect ratio)"""
        if self.map_pixmap.isNull():
            return self.rect()

        # Calculate scaled size keeping aspect ratio
        widget_size = self.size()
        pixmap_size = self.map_pixmap.size()

        # Calculate scale factor to fit the map in the widget
        scale_w = widget_size.width() / pixmap_size.width()
        scale_h = widget_size.height() / pixmap_size.height()
        scale = min(scale_w, scale_h)

        # Calculate actual map size
        map_width = int(pixmap_size.width() * scale)
        map_height = int(pixmap_size.height() * scale)

        # Center the map in the widget
        offset_x = (widget_size.width() - map_width) // 2
        offset_y = (widget_size.height() - map_height) // 2

        return QRect(offset_x, offset_y, map_width, map_height)

    def field_to_widget(self, field_x, field_y):
        """Convert field coordinates to widget pixel coordinates
        Field: (0, 0) at bottom-left, (28, 15) at top-right
        Widget: (0, 0) at top-left
        """
        map_rect = self._scaled_rect

        # Map field coordinates to map rectangle coordinates
        # x: 0 -> map_rect.left, 28 -> map_rect.right
        # y: 0 -> map_rect.bottom, 15 -> map_rect.top (flip y-axis)
        widget_x = map_rect.left() + ((field_x - FIELD_MIN_X) / FIELD_WIDTH) * map_rect.width()
        widget_y = map_rect.bottom() - ((field_y - FIELD_MIN_Y) / FIELD_HEIGHT) * map_rect.height()

        return int(widget_x), int(widget_y)

    def widget_to_field(self, widget_x, widget_y):
        """Convert widget pixel coordinates to field coordinates"""
        map_rect = self._scaled_rect

        # Clamp to map bounds
        widget_x = max(map_rect.left(), min(widget_x, map_rect.right()))
        widget_y = max(map_rect.top(), min(widget_y, map_rect.bottom()))

        # Map widget coordinates to field coordinates
        field_x = FIELD_MIN_X + ((widget_x - map_rect.left()) /
                                 map_rect.width()) * FIELD_WIDTH
        field_y = FIELD_MIN_Y + ((map_rect.bottom() - widget_y) /
                                 map_rect.height()) * FIELD_HEIGHT

        # Clamp to field bounds
        field_x = max(FIELD_MIN_X, min(field_x, FIELD_MAX_X))
        field_y = max(FIELD_MIN_Y, min(field_y, FIELD_MAX_Y))

        return field_x, field_y

    def paintEvent(self, event):
        """Paint the map and robot positions"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background with gray
        painter.fillRect(self.rect(), QColor(50, 50, 50))

        # Draw map background (keeping aspect ratio)
        if not self.map_pixmap.isNull():
            # Calculate the rectangle where map will be drawn
            self._scaled_rect = self._get_scaled_map_rect()

            # Scale and draw the map
            scaled_pixmap = self.map_pixmap.scaled(
                self._scaled_rect.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            painter.drawPixmap(self._scaled_rect.topLeft(), scaled_pixmap)
        else:
            # If map image not loaded, draw a simple background
            painter.fillRect(self.rect(), QColor(200, 200, 200))
            painter.setPen(QPen(QColor(100, 100, 100), 1))
            painter.drawText(self.rect(), Qt.AlignCenter, "地图图片未加载")
            self._scaled_rect = self.rect()

        # Draw robots
        for robot_key, robot_info in self.ROBOTS.items():
            pos = self.robot_positions[robot_key]
            widget_x, widget_y = self.field_to_widget(pos['x'], pos['y'])

            # Draw robot as a red dot with ID
            # Draw larger circle if being dragged
            radius = 8 if self.dragging_robot == robot_key else 6

            # Draw outer circle (highlight)
            if self.dragging_robot == robot_key:
                painter.setPen(QPen(QColor(255, 255, 0), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(
                    QPoint(widget_x, widget_y), radius + 3, radius + 3)

            # Draw robot dot
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(robot_info['color'])
            painter.drawEllipse(QPoint(widget_x, widget_y), radius, radius)

            # Draw direction triangle
            angle_rad = math.radians(pos['angle'])
            triangle_distance = 15  # Distance from robot center to triangle
            triangle_size = 6

            # Calculate triangle tip position
            tip_x = widget_x + triangle_distance * math.cos(angle_rad)
            tip_y = widget_y - triangle_distance * math.sin(angle_rad)

            # Calculate triangle base points (perpendicular to direction)
            perp_angle1 = angle_rad + math.pi * 2/3
            perp_angle2 = angle_rad - math.pi * 2/3

            base1_x = tip_x + triangle_size * math.cos(perp_angle1)
            base1_y = tip_y - triangle_size * math.sin(perp_angle1)
            base2_x = tip_x + triangle_size * math.cos(perp_angle2)
            base2_y = tip_y - triangle_size * math.sin(perp_angle2)

            # Draw triangle with same color as robot
            from PyQt5.QtGui import QPolygonF
            from PyQt5.QtCore import QPointF
            triangle = QPolygonF([
                QPointF(tip_x, tip_y),
                QPointF(base1_x, base1_y),
                QPointF(base2_x, base2_y)
            ])

            # Highlight if dragging angle
            if self.dragging_angle == robot_key:
                painter.setPen(QPen(QColor(255, 255, 0), 3))
            else:
                painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(robot_info['color'])
            painter.drawPolygon(triangle)

            # Draw robot ID/name below the dot
            painter.setPen(QPen(QColor(255, 255, 255), 3))  # White outline
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)

            robot_id = self.sentry_id if robot_key == 'sentry' else robot_info['id']
            text = f"{robot_id}"
            text_rect = QRect(widget_x - 20, widget_y + radius + 2, 40, 20)

            # Draw text outline (white)
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx != 0 or dy != 0:
                        painter.drawText(text_rect.adjusted(
                            dx, dy, dx, dy), Qt.AlignCenter, text)

            # Draw text (black)
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.drawText(text_rect, Qt.AlignCenter, text)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press to start dragging a robot or angle"""
        pos = event.pos()

        if event.button() == Qt.LeftButton:
            # Check if clicked on any robot
            for robot_key in self.ROBOTS.keys():
                robot_pos = self.robot_positions[robot_key]
                widget_x, widget_y = self.field_to_widget(
                    robot_pos['x'], robot_pos['y'])

                # Check if click is within robot radius
                dx = pos.x() - widget_x
                dy = pos.y() - widget_y
                distance = (dx * dx + dy * dy) ** 0.5

                # Triangle is at distance ~15 from center
                # Priority: triangle area for angle dragging, then center for position dragging
                if 8 <= distance <= 25:  # Click threshold for triangle area
                    self.dragging_angle = robot_key
                    break
                elif distance <= 10:  # Click threshold for robot center
                    self.dragging_robot = robot_key
                    break

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move to drag robot or angle"""
        pos = event.pos()

        if self.dragging_robot:
            field_x, field_y = self.widget_to_field(pos.x(), pos.y())
            self.robot_positions[self.dragging_robot]['x'] = field_x
            self.robot_positions[self.dragging_robot]['y'] = field_y
            self.update()
            # Notify parent widget to update position display
            parent = self.parent()
            while parent:
                if isinstance(parent, FakeLocationWidget):
                    parent.update_position_display()
                    break
                parent = parent.parent()

        elif self.dragging_angle:
            # Calculate angle from robot center to mouse position
            robot_pos = self.robot_positions[self.dragging_angle]
            widget_x, widget_y = self.field_to_widget(
                robot_pos['x'], robot_pos['y'])

            dx = pos.x() - widget_x
            dy = widget_y - pos.y()  # Flip y because widget y increases downward

            # Calculate angle in degrees (0 = right, 90 = up, counter-clockwise)
            angle_deg = math.degrees(math.atan2(dy, dx))

            self.robot_positions[self.dragging_angle]['angle'] = angle_deg
            self.update()
            # Notify parent widget to update angle display
            parent = self.parent()
            while parent:
                if isinstance(parent, FakeLocationWidget):
                    parent.update_position_display()
                    break
                parent = parent.parent()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release to stop dragging"""
        if event.button() == Qt.LeftButton:
            self.dragging_robot = None
            self.dragging_angle = None
            self.update()

    def get_robot_positions(self):
        """Get all robot positions in field coordinates"""
        return self.robot_positions.copy()

    def set_sentry_id(self, sentry_id):
        """Set the displayed sentry ID for the selected alliance."""
        if sentry_id in (7, 107):
            self.sentry_id = sentry_id
            self.update()


class FakeLocationWidget(QWidget):
    """Widget for fake location data publishing"""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Fake Location")

        main_layout = QVBoxLayout()

        # Settings group
        settings_group = QGroupBox("发布设置")
        settings_layout = QFormLayout()

        self.topic_prefix_edit = ConfirmedLineEdit("/rm_referee")
        self.topic_prefix_edit.setPlaceholderText("输入话题前缀")
        settings_layout.addRow("话题前缀:", self.topic_prefix_edit)

        self.rate_edit = ConfirmedLineEdit("10.0")
        self.rate_edit.setPlaceholderText("输入发布频率 (Hz)")
        settings_layout.addRow("发布频率 (Hz):", self.rate_edit)

        self.current_robot_combo = QComboBox()
        self.current_robot_combo.addItems([
            "1 - 英雄",
            "2 - 工程",
            "3 - 步兵3",
            "4 - 步兵4",
            "7 - 红方哨兵",
            "107 - 蓝方哨兵"
        ])
        self.current_robot_combo.setCurrentIndex(4)
        self.current_robot_combo.currentIndexChanged.connect(
            self._on_current_robot_changed)
        settings_layout.addRow("当前机器人:", self.current_robot_combo)

        self.noise_scale_spinbox = QDoubleSpinBox()
        self.noise_scale_spinbox.setRange(0.0, 1.0)
        self.noise_scale_spinbox.setDecimals(3)
        self.noise_scale_spinbox.setSingleStep(0.01)
        self.noise_scale_spinbox.setValue(0.0)
        self.noise_scale_spinbox.setSuffix(" m")
        self.noise_scale_spinbox.setToolTip("高斯噪声的标准差（0表示无噪声）")
        settings_layout.addRow("位置噪声 (σ):", self.noise_scale_spinbox)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group, 0)  # stretch=0, fixed size

        # Map display (create first so we can access robot_positions)
        map_group = QGroupBox("场地地图")
        map_layout = QVBoxLayout()

        # Map widget
        map_path = path.join(PACKAGE_SHARE, "assets", "map.jpg")
        self.map_widget = MapWidget(map_path)
        # stretch=1, take remaining space
        map_layout.addWidget(self.map_widget, 1)

        # Position display group (create after map_widget)
        position_group = QGroupBox("机器人位置信息")
        position_layout = QGridLayout()

        # Create header labels
        header_labels = ["机器人", "X", "Y", "朝向 (°)"]
        for col, text in enumerate(header_labels):
            label = QLabel(text)
            label.setStyleSheet("font-weight: bold; padding: 5px;")
            label.setAlignment(Qt.AlignCenter)
            position_layout.addWidget(label, 0, col)

        # Create spinboxes for each robot
        self.robot_spinboxes = {}
        robot_info = [
            ('hero', '1 - 英雄'),
            ('engineer', '2 - 工程'),
            ('standard_3', '3 - 步兵3'),
            ('standard_4', '4 - 步兵4'),
            ('sentry', '7 - 哨兵')
        ]

        for row, (robot_key, display_name) in enumerate(robot_info, start=1):
            # Robot name label
            name_label = QLabel(display_name)
            name_label.setStyleSheet("padding: 5px;")
            position_layout.addWidget(name_label, row, 0)

            # X coordinate spinbox
            x_spinbox = QDoubleSpinBox()
            x_spinbox.setRange(FIELD_MIN_X, FIELD_MAX_X)
            x_spinbox.setDecimals(2)
            x_spinbox.setSingleStep(0.1)
            x_spinbox.setValue(self.map_widget.robot_positions[robot_key]['x'])
            x_spinbox.valueChanged.connect(
                lambda value, key=robot_key: self._on_x_spinbox_changed(
                    key, value)
            )
            position_layout.addWidget(x_spinbox, row, 1)

            # Y coordinate spinbox
            y_spinbox = QDoubleSpinBox()
            y_spinbox.setRange(FIELD_MIN_Y, FIELD_MAX_Y)
            y_spinbox.setDecimals(2)
            y_spinbox.setSingleStep(0.1)
            y_spinbox.setValue(self.map_widget.robot_positions[robot_key]['y'])
            y_spinbox.valueChanged.connect(
                lambda value, key=robot_key: self._on_y_spinbox_changed(
                    key, value)
            )
            position_layout.addWidget(y_spinbox, row, 2)

            # Angle spinbox
            angle_spinbox = QDoubleSpinBox()
            angle_spinbox.setRange(-180.0, 180.0)
            angle_spinbox.setDecimals(1)
            angle_spinbox.setSingleStep(1.0)
            angle_spinbox.setValue(
                self.map_widget.robot_positions[robot_key]['angle'])
            angle_spinbox.setWrapping(True)  # Allow wrapping from 180 to -180
            angle_spinbox.valueChanged.connect(
                lambda value, key=robot_key: self._on_angle_spinbox_changed(
                    key, value)
            )
            position_layout.addWidget(angle_spinbox, row, 3)

            # Store spinboxes for later updates
            self.robot_spinboxes[robot_key] = {
                'x': x_spinbox, 'y': y_spinbox, 'angle': angle_spinbox}

        position_group.setLayout(position_layout)
        main_layout.addWidget(position_group, 0)  # stretch=0, fixed size

        map_group.setLayout(map_layout)
        main_layout.addWidget(map_group, 1)  # stretch=1, expand to fill window

        self.setLayout(main_layout)

        # Update position display initially
        self.update_position_display()

        # Set up timer to update position display periodically
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self.update_position_display)
        self.display_timer.start(100)  # Update every 100ms

    def update_position_display(self):
        """Update the spinbox values with current robot positions from map"""
        positions = self.map_widget.get_robot_positions()

        # Block signals to prevent feedback loop
        for robot_key, spinboxes in self.robot_spinboxes.items():
            pos = positions[robot_key]
            spinboxes['x'].blockSignals(True)
            spinboxes['y'].blockSignals(True)
            spinboxes['angle'].blockSignals(True)
            spinboxes['x'].setValue(pos['x'])
            spinboxes['y'].setValue(pos['y'])
            spinboxes['angle'].setValue(pos['angle'])
            spinboxes['x'].blockSignals(False)
            spinboxes['y'].blockSignals(False)
            spinboxes['angle'].blockSignals(False)

    def _on_x_spinbox_changed(self, robot_key, value):
        """Handle X spinbox value change"""
        self.map_widget.robot_positions[robot_key]['x'] = value
        self.map_widget.update()

    def _on_y_spinbox_changed(self, robot_key, value):
        """Handle Y spinbox value change"""
        self.map_widget.robot_positions[robot_key]['y'] = value
        self.map_widget.update()

    def _on_angle_spinbox_changed(self, robot_key, value):
        """Handle angle spinbox value change"""
        self.map_widget.robot_positions[robot_key]['angle'] = value
        self.map_widget.update()

    def _on_current_robot_changed(self, _index):
        """Update the sentry marker ID when switching simulated alliance."""
        if self.get_current_robot_key() == 'sentry':
            self.map_widget.set_sentry_id(self.get_current_robot_id())

    def get_topic_prefix(self):
        """Get the topic prefix"""
        return self.topic_prefix_edit.text()

    def get_publish_rate(self):
        """Get the publish rate"""
        try:
            return float(self.rate_edit.text())
        except ValueError:
            return 10.0

    def get_noise_scale(self):
        """Get the noise scale (standard deviation) for backend to use"""
        return self.noise_scale_spinbox.value()

    def get_current_robot_key(self):
        """Get the key of currently selected robot"""
        index = self.current_robot_combo.currentIndex()
        robot_keys = [
            'hero', 'engineer', 'standard_3', 'standard_4', 'sentry', 'sentry']
        return robot_keys[index]

    def get_current_robot_id(self):
        """Get the official referee-system ID of the selected robot."""
        index = self.current_robot_combo.currentIndex()
        robot_ids = [1, 2, 3, 4, 7, 107]
        return robot_ids[index]

    def get_robot_pos_data(self):
        """Get RobotPos data (single robot position, typically for the current robot)
        Uses the robot selected in current_robot_combo
        """
        positions = self.map_widget.get_robot_positions()
        current_robot_key = self.get_current_robot_key()
        current_pos = positions[current_robot_key]

        return {
            'x': current_pos['x'],
            'y': current_pos['y'],
            'angle': current_pos['angle']  # Angle in degrees
        }

    def get_ground_robot_position_data(self):
        """Get GroundRobotPosition data (all ground robots)"""
        positions = self.map_widget.get_robot_positions()

        return {
            'hero_x': positions['hero']['x'],
            'hero_y': positions['hero']['y'],
            'engineer_x': positions['engineer']['x'],
            'engineer_y': positions['engineer']['y'],
            'standard_3_x': positions['standard_3']['x'],
            'standard_3_y': positions['standard_3']['y'],
            'standard_4_x': positions['standard_4']['x'],
            'standard_4_y': positions['standard_4']['y'],
            'reserved': 0.0,
            'reserved_2': 0.0
        }
