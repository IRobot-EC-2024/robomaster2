#pragma once

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>

#include "referee_node/referee_node.hpp"

class RefereeReplayNode : public RefereeNode {
 public:
  explicit RefereeReplayNode(const rclcpp::NodeOptions& options = rclcpp::NodeOptions()
                                                                      .allow_undeclared_parameters(true)
                                                                      .automatically_declare_parameters_from_overrides(true));
  ~RefereeReplayNode() override;

 private:
  void ReplayFile(const std::string& file_path, bool normal_link);
  bool FindGameProgressOffset(std::ifstream& file, uint8_t target_progress, std::streamoff& offset);
  void PrintProgress(const char* link_name, std::streamoff bytes_read, std::streamoff total_bytes,
                     size_t record_count, bool force_newline = false);
  bool WaitForTimestamp(uint64_t timestamp_us, uint64_t first_timestamp_us,
                        const std::chrono::steady_clock::time_point& replay_start);

  std::string normal_data_file_;
  std::string vt_data_file_;
  double replay_rate_{1.0};
  int64_t start_game_progress_{-1};

  std::thread normal_replay_thread_;
  std::thread vt_replay_thread_;
  std::atomic<bool> stop_replay_{false};
  std::mutex wait_mutex_;
  std::condition_variable wait_condition_;
  std::mutex progress_mutex_;
};
