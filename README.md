# rm_referee_ros2

本项目包含了一些在 ROS2 下开发 RM 的裁判系统必要的一些基建。

仓库的分支/tag 对应官方发布的协议文件版本，带 `legacy-` 前缀的 tag 为 26 赛季“串口协议”改为“通信协议”之前的版本，不带 `legacy-` 前缀的 tag 为 26 赛季改版为“通信协议”之后的版本。例如：

- `legacy-v1.7.0` 对应 《RoboMaster 裁判系统串口协议附录 V1.7.0（20241225）》。

- `v1.2.0` 对应 《RoboMaster 2026 机甲大师高校系列赛通信协议 V1.2.0（20260209）》。

`main`分支为最新开发版本，可能包含不稳定的改动。

## Build test matrix

<table>
<tr>
<td>foxy</td>
<td rowspan=2>
    <a href="https://github.com/XDU-IRobot/rm_referee_ros2/actions/workflows/build_eol.yaml">
        <img src="https://github.com/XDU-IRobot/rm_referee_ros2/actions/workflows/build_eol.yaml/badge.svg">
    </a>
</td>
</tr>
<tr>
<td>galactic</td>
</tr>
<tr>
<td>humble</td>
<td rowspan=4>
    <a href="https://github.com/XDU-IRobot/rm_referee_ros2/actions/workflows/build.yaml">
        <img src="https://github.com/XDU-IRobot/rm_referee_ros2/actions/workflows/build.yaml/badge.svg">
    </a>
</td>
</tr>
<tr>
<td>iron</td>
</tr>
<tr>
<td>jazzy</td>
</tr>
<tr>
<td>rolling</td>
</tr>
</table>

## 串口驱动

1. clone 本仓库到工作空间里，必须加 `--recursive` 参数以获取子模块：

```bash
git clone --recursive https://github.com/XDU-IRobot/rm_referee_ros2.git
```

2. `colcon build`编译，然后复制一份`rm_referee/launch/referee_node.launch.py`到你自己的项目里，按需修改里面的参数，运行即可。可供配置的参数如下表：

| 参数名              | 说明                                                                              | 默认值                 |
| ------------------- | --------------------------------------------------------------------------------- | ---------------------- |
| `enable_normal`     | 启用常规链路（电源管理模块上的串口）                                              | `True`                 |
| `enable_vt`         | 启用图传链路（图传模块上的串口）                                                  | `False`                |
| `new_vt`            | 如果是 VT03 新图传，把这一项设置为 True，串口波特率会调整为 921600，否则为 115200 | `False`                |
| `normal_tty_device` | 常规链路对应的串口设备                                                            | `/dev/ttyUSB0`         |
| `vt_tty_device`     | 图传链路对应的串口设备                                                            | `/dev/ttyUSB0`         |
| `record_raw_data`   | 是否将收到的原始数据字节流写到文件中                                              | `False`                |
| `raw_data_path`     | 如果启用了记录原始数据，指定保存文件的路径                                        | `/tmp/rm_referee_data` |

裁判系统通过串口发送的数据会被封装成消息发布到对应话题上，反之可以通过请求`/rm_referee/tx`服务向裁判系统串口发送数据。

### 原始数据回放

`referee_replay_node` 可以按录制时间间隔读取 `record_raw_data` 生成的文件，复用串口节点的解包和话题发布逻辑。回放节点不会打开串口，也不会创建 `/rm_referee/tx` 服务。

| 参数名                | 说明                                                                  | 默认值 |
| --------------------- | --------------------------------------------------------------------- | ------ |
| `normal_data_file`    | 常规链路原始数据文件；留空时不回放该链路                              | `""` |
| `vt_data_file`        | 图传链路原始数据文件；留空时不回放该链路                              | `""` |
| `replay_rate`         | 回放倍速；`1.0` 为原速，`2.0` 为两倍速，`0.0` 表示不等待录制时间间隔 | `1.0`  |
| `start_game_progress` | 从指定 `game_status.game_progress` 首次出现的位置开始回放             | `-1`   |

`start_game_progress` 设置为 `-1` 时不进行阶段定位，从文件开头回放；设置为 `0` 到 `5` 时，节点会先扫描常规链路文件，并从目标阶段首次出现的位置开始回放。如果文件中不存在指定阶段，节点会输出错误信息并停止该文件的回放。

例如，从比赛进行阶段（`game_progress=4`）开始回放：

```bash
ros2 launch rm_referee referee_replay.launch.py \
  normal_data_file:=/tmp/rm_referee_data/normal_raw_data_YYYYMMDD_HHMMSS.bin \
  replay_rate:=1.0 \
  start_game_progress:=4
```

### 话题列表

#### 常规链路

| 话题名                            | 消息类型                                | 说明                 |
| --------------------------------- | --------------------------------------- | -------------------- |
| /rm_referee/buff                  | rm_referee_msgs/msg/Buff                | 机器人增益信息       |
| /rm_referee/dart_client_cmd       | rm_referee_msgs/msg/DartClientCmd       | 飞镖信息 1           |
| /rm_referee/dart_info             | rm_referee_msgs/msg/DartInfo            | 飞镖信息 2           |
| /rm_referee/event_data            | rm_referee_msgs/msg/EventData           | 比赛信息 1           |
| /rm_referee/game_result           | rm_referee_msgs/msg/GameResult          | 比赛结果             |
| /rm_referee/game_robot_hp         | rm_referee_msgs/msg/GameRobotHP         | 己方机器人血量       |
| /rm_referee/game_status           | rm_referee_msgs/msg/GameStatus          | 比赛信息 2           |
| /rm_referee/ground_robot_position | rm_referee_msgs/msg/GroundRobotPosition | 我方地面机器人位置   |
| /rm_referee/hurt_data             | rm_referee_msgs/msg/HurtData            | 扣血信息             |
| /rm_referee/power_heat_data       | rm_referee_msgs/msg/PowerHeatData       | 功率和枪口热量信息   |
| /rm_referee/projectile_allowance  | rm_referee_msgs/msg/ProjectileAllowance | 允许发弹量和剩余金币 |
| /rm_referee/radar_info            | rm_referee_msgs/msg/RadarInfo           | 雷达双倍易伤相关信息 |
| /rm_referee/radar_mark_data       | rm_referee_msgs/msg/RadarMarkData       | 对方机器人被标记进度 |
| /rm_referee/referee_warning       | rm_referee_msgs/msg/RefereeWarning      | 判罚信息             |
| /rm_referee/rfid_status           | rm_referee_msgs/msg/RFIDStatus          | RFID 检测信息        |
| /rm_referee/robot_pos             | rm_referee_msgs/msg/RobotPos            | 本机器人的位置和朝向 |
| /rm_referee/robot_status          | rm_referee_msgs/msg/RobotStatus         | 本机器人状态         |
| /rm_referee/sentry_info           | rm_referee_msgs/msg/SentryInfo          | 哨兵兑换信息         |
| /rm_referee/shoot_data            | rm_referee_msgs/msg/ShootData           | 弹丸信息             |
| /rm_referee/map_command           | rm_referee_msgs/msg/MapCommand          | 选手端小地图交互数据 |

#### 图传链路

| 话题名                          | 消息类型                             | 说明                           |
| ------------------------------- | ------------------------------------ | ------------------------------ |
| /rm_referee/custom_robot_data   | rm_referee_msgs/msg/CustomRobotData  | 自定义控制器与机器人交互数据       |
| /rm_referee/robot_custom_data   | rm_referee_msgs/msg/RobotCustomData  | 自定义控制器接收机器人数据         |
| /rm_referee/robot_custom_data_2 | rm_referee_msgs/msg/RobotCustomData2 | 机器人发送给自定义客户端的数据     |
| /rm_referee/custom_control      | rm_referee_msgs/msg/CustomControl    | 自定义客户端发送给机器人的自定义指令 |

> [!NOTE]  
> V1.3.0 协议已删除旧的 `0x0304` 键鼠遥控数据包，因此串口驱动不再发布 `/rm_referee/remote_control`。如需本地模拟自定义客户端的键鼠输入，可使用 `rm_referee_mock` 提供的 `rm_referee_msgs/KeyboardMouseControl`。

### 服务列表

| 服务名         | 服务类型               | 说明                   |
| -------------- | ---------------------- | ---------------------- |
| /rm_referee/tx | rm_referee_msgs/srv/Tx | 向裁判系统串口发送数据 |

## TF Publisher

目前规则版本下，服务器会：

1. 向所有机器人发布本机器人位置的数据；

2. 向哨兵机器人发送所有己方地面机器人位置的数据。

为了方便利用这些信息，本项目包含一个 `tf_publisher` 节点。它订阅 `rm_referee_msgs/RobotPos` 和 `rm_referee_msgs/GroundRobotPosition` 类型的话题，并将其中的机器人位置信息发布到 tf 上：

![tf_publisher](docs/tf_publisher.jpg)

具体的，节点会发布以下变换：

- `<root_frame_id>` -> `<child_frame_prefix>self`：本机器人位置。
- `<root_frame_id>` -> `<child_frame_prefix>hero`：己方英雄机器人位置。
- `<root_frame_id>` -> `<child_frame_prefix>engineer`：己方工程机器人位置。
- `<root_frame_id>` -> `<child_frame_prefix>standard_3`：己方步兵 3 号机器人位置。
- `<root_frame_id>` -> `<child_frame_prefix>standard_4`：己方步兵 4 号机器人位置。

> [!NOTE]  
> 根据裁判系统协议定义，只有“本机器人位置”(`rm_referee_msgs/RobotPos`)消息包含朝向信息。
> TF Publisher 对此的处理方式是，`map->robot_self` 这个变换包含朝向，其他变换无朝向信息（即朝向为 0）。

同理，复制一份`rm_referee/launch/tf_publisher.launch.py`到自己的项目里，按需修改参数然后运行即可。可供配置的参数如下表：

| 参数名                   | 说明                                | 默认值                              |
| ------------------------ | ----------------------------------- | ----------------------------------- |
| `robot_pos_topic`        | 订阅本机器人位置的 ROS 话题名       | `/rm_referee/robot_pos`             |
| `ground_robot_pos_topic` | 订阅己方地面机器人位置的 ROS 话题名 | `/rm_referee/ground_robot_position` |
| `root_frame_id`          | TF 根坐标系的 frame id              | `map`                               |
| `child_frame_prefix`     | 机器人坐标系的 frame id 前缀        | `robot_`                            |

## Mock

`rm_referee_mock`包里提供了一些 Mock 组件，用来模拟裁判系统的数据发送行为，方便在没有真实裁判系统或者不便搭建环境的情况下进行开发和测试。

使用方法参见 [`rm_referee_mock/README.md`](rm_referee_mock/README.md)。
