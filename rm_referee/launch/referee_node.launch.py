from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [
            Node(
                package='rm_referee',
                executable='referee_node',
                output='screen',
                parameters=[{
                    "enable_normal": True,                 # 启用电源管理常规链路
                    "enable_vt": False,                      # 启用图传链路
                    "new_vt": True,                        # 如果是VT03新图传，把这一项设置为True，串口波特率会调整为921600，否则为115200
                    "normal_tty_device": "/dev/ttyUSB0",    # 常规链路对应的串口设备
                    "vt_tty_device": "/dev/ttyUSB0",        # 图传链路对应的串口设备
                    "record_raw_data": False,                  # 是否记录收到的原始数据
                    "raw_data_path": "/tmp/rm_referee_data",   # 原始数据保存目录
                }],
            )
        ]
    )
