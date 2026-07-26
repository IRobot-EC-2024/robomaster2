from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("normal_data_file", default_value=""),
            DeclareLaunchArgument("vt_data_file", default_value=""),
            DeclareLaunchArgument("replay_rate", default_value="1.0"),
            DeclareLaunchArgument("start_game_progress", default_value="-1"),
            Node(
                package="rm_referee",
                executable="referee_replay_node",
                output="screen",
                emulate_tty=True,
                parameters=[
                    {
                        "normal_data_file": LaunchConfiguration("normal_data_file"),
                        "vt_data_file": LaunchConfiguration("vt_data_file"),
                        "replay_rate": ParameterValue(LaunchConfiguration("replay_rate"), value_type=float),
                        "start_game_progress": ParameterValue(
                            LaunchConfiguration("start_game_progress"), value_type=int
                        ),
                    }
                ],
            ),
        ]
    )
