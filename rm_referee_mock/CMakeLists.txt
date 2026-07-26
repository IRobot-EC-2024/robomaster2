cmake_minimum_required(VERSION 3.13)
project(rm_referee_mock)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# NOTE
# 目前这个mock功能包里没有C++代码，只有几个python写的rqt插件
# 但是为了保留以后添加C++代码的可能性，所以用了ament_cmake_python来管理构建，而不是直接用ament_python

install(DIRECTORY assets
  DESTINATION share/${PROJECT_NAME}
)

# Install plugin descriptor for rqt
install(FILES
  plugin.xml
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/rqt_clean_start
  DESTINATION lib/${PROJECT_NAME}
)

ament_python_install_package(${PROJECT_NAME}) # Install Python module

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(test_sentry_posture test/test_sentry_posture.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}
  )
  ament_add_pytest_test(test_sentry_protocol test/test_sentry_protocol.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}
  )
  ament_add_pytest_test(test_match_rules test/test_match_rules.py
    APPEND_ENV PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}
  )
endif()

ament_package()
