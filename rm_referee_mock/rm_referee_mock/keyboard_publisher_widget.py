#!/usr/bin/env python3

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QFormLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from rm_referee_mock.widget_confirmed_line_edit import ConfirmedLineEdit


class KeyboardPublisherWidget(QWidget):
    """Widget for keyboard input visualization and publishing"""
    
    # Signal emitted when keyboard state changes
    keyboard_state_changed = pyqtSignal(int)  # keyboard_value
    
    # Keyboard mapping based on KeyboardMouseControl message constants
    KEY_MAP = {
        Qt.Key_W: (0x01, "W"),
        Qt.Key_S: (0x02, "S"),
        Qt.Key_A: (0x04, "A"),
        Qt.Key_D: (0x08, "D"),
        Qt.Key_Shift: (0x10, "Shift"),
        Qt.Key_Control: (0x20, "Ctrl"),
        Qt.Key_Q: (0x40, "Q"),
        Qt.Key_E: (0x80, "E"),
        Qt.Key_R: (0x100, "R"),
        Qt.Key_F: (0x200, "F"),
        Qt.Key_G: (0x400, "G"),
        Qt.Key_Z: (0x800, "Z"),
        Qt.Key_X: (0x1000, "X"),
        Qt.Key_C: (0x2000, "C"),
        Qt.Key_V: (0x4000, "V"),
        Qt.Key_B: (0x8000, "B"),
    }
    
    def __init__(self):
        super().__init__()
        self.keyboard_value = 0
        self.key_labels = {}
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle("Keyboard Publisher")
        self.setFocusPolicy(Qt.StrongFocus)
        
        main_layout = QVBoxLayout()
        
        # Info label
        info_label = QLabel("Focus this window and press keys to publish keyboard events")
        info_label.setStyleSheet("font-weight: bold; padding: 10px;")
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)
        
        # Settings group
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()
        
        self.topic_edit = ConfirmedLineEdit("/rm_referee/mock/keyboard_mouse_control")
        self.topic_edit.setPlaceholderText("Enter topic name")
        settings_layout.addRow("Topic:", self.topic_edit)
        
        self.rate_edit = ConfirmedLineEdit("20.0")
        self.rate_edit.setPlaceholderText("Enter publish rate (Hz)")
        settings_layout.addRow("Rate (Hz):", self.rate_edit)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # Status display
        status_group = QGroupBox("Keyboard Status")
        status_layout = QVBoxLayout()
        
        self.status_label = QLabel("Press any supported key...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        status_layout.addWidget(self.status_label)
        
        self.value_label = QLabel("Value: 0x0000")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        status_layout.addWidget(self.value_label)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        # Key visualization grid
        keys_group = QGroupBox("Active Keys")
        keys_layout = QVBoxLayout()
        
        # Create key display buttons in rows
        key_rows = [
            ["Q", "W", "E", "R"],
            ["A", "S", "D", "F", "G"],
            ["Z", "X", "C", "V", "B"],
            ["Shift", "Ctrl"]
        ]
        
        for row in key_rows:
            row_layout = QHBoxLayout()
            for key_name in row:
                btn = QPushButton(key_name)
                btn.setCheckable(False)
                btn.setEnabled(False)
                btn.setMinimumWidth(60)
                btn.setStyleSheet(self._get_key_style(False))
                self.key_labels[key_name] = btn
                row_layout.addWidget(btn)
            row_layout.addStretch()
            keys_layout.addLayout(row_layout)
        
        keys_group.setLayout(keys_layout)
        main_layout.addWidget(keys_group)
        
        # Reset button
        reset_btn = QPushButton("Reset All Keys")
        reset_btn.clicked.connect(self._reset_keys)
        main_layout.addWidget(reset_btn)
        
        main_layout.addStretch()
        self.setLayout(main_layout)
        
        # Set minimum size
        self.setMinimumSize(400, 500)
    
    def _get_key_style(self, active):
        """Get stylesheet for key button based on active state"""
        if active:
            return """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 2px solid #45a049;
                    border-radius: 4px;
                    padding: 10px;
                    font-weight: bold;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #f0f0f0;
                    color: #666;
                    border: 2px solid #ccc;
                    border-radius: 4px;
                    padding: 10px;
                }
            """
    
    def _update_display(self):
        """Update the visual display of keyboard state"""
        # Update value label with both hex and binary
        hex_value = f"0x{self.keyboard_value:04X}"
        bin_value = f"0b{self.keyboard_value:016b}"
        self.value_label.setText(f"Hex: {hex_value} | Binary: {bin_value}")
        
        # Update active keys display
        active_keys = []
        for qt_key, (bit_value, key_name) in self.KEY_MAP.items():
            is_active = (self.keyboard_value & bit_value) != 0
            if key_name in self.key_labels:
                self.key_labels[key_name].setStyleSheet(self._get_key_style(is_active))
            if is_active:
                active_keys.append(key_name)
        
        # Update status text
        if active_keys:
            self.status_label.setText(f"Active: {', '.join(active_keys)}")
            self.status_label.setStyleSheet(
                "font-size: 14px; padding: 10px; color: green; font-weight: bold;")
        else:
            self.status_label.setText("No keys pressed")
            self.status_label.setStyleSheet("font-size: 14px; padding: 10px; color: #666;")
    
    def _reset_keys(self):
        """Reset all keys to unpressed state"""
        self.keyboard_value = 0
        self._update_display()
        self.keyboard_state_changed.emit(self.keyboard_value)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press events"""
        key = event.key()
        if key in self.KEY_MAP:
            bit_value, _ = self.KEY_MAP[key]
            if not event.isAutoRepeat():  # Ignore key repeat
                self.keyboard_value |= bit_value
                self._update_display()
                self.keyboard_state_changed.emit(self.keyboard_value)
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event: QKeyEvent):
        """Handle key release events"""
        key = event.key()
        if key in self.KEY_MAP:
            bit_value, _ = self.KEY_MAP[key]
            if not event.isAutoRepeat():  # Ignore key repeat
                self.keyboard_value &= ~bit_value
                self._update_display()
                self.keyboard_state_changed.emit(self.keyboard_value)
        super().keyReleaseEvent(event)
    
    def get_keyboard_value(self):
        """Get current keyboard value"""
        return self.keyboard_value
    
    def get_publish_topic(self):
        """Get the configured publish topic"""
        topic = self.topic_edit.text().strip()
        return topic if topic else "/rm_referee/mock/keyboard_mouse_control"
    
    def get_publish_rate(self):
        """Get the configured publish rate"""
        try:
            rate = float(self.rate_edit.text().strip())
            return max(0.1, min(rate, 1000.0))  # Clamp between 0.1 and 1000 Hz
        except ValueError:
            return 20.0  # Default rate
