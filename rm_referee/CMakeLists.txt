cmake_minimum_required(VERSION 3.13)
project(rm_referee)

set(CMAKE_EXPORT_COMPILE_COMMANDS true)
if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

find_package(ament_cmake_auto REQUIRED)
find_package(Boost REQUIRED COMPONENTS system)

ament_auto_find_build_dependencies()

add_subdirectory(libs)

# 创建 referee_node 组件库
ament_auto_add_library(referee_node_component SHARED
  src/referee_node.cc
  src/byte_stream_recorder.cc
)
target_link_libraries(referee_node_component ${PROJECT_NAME}_third_party ${Boost_LIBRARIES})
target_include_directories(referee_node_component PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
  ${Boost_INCLUDE_DIRS}
)
rclcpp_components_register_node(referee_node_component
  PLUGIN "RefereeNode"
  EXECUTABLE referee_node
)

# 创建裁判系统原始数据回放组件库
ament_auto_add_library(referee_replay_node_component SHARED src/referee_replay_node.cc)
target_link_libraries(referee_replay_node_component referee_node_component ${PROJECT_NAME}_third_party)
target_include_directories(referee_replay_node_component PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
rclcpp_components_register_node(referee_replay_node_component
  PLUGIN "RefereeReplayNode"
  EXECUTABLE referee_replay_node
)

# 创建 tf_publisher 组件库
ament_auto_add_library(tf_publisher_component SHARED src/tf_publisher.cc)
target_include_directories(tf_publisher_component PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
rclcpp_components_register_node(tf_publisher_component
  PLUGIN "TfPublisher"
  EXECUTABLE tf_publisher
)

# 安装库和可执行文件
install(TARGETS referee_node_component referee_replay_node_component tf_publisher_component
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
install(DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_auto_package()
