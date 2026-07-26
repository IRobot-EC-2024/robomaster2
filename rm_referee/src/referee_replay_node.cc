#include "referee_node/referee_replay_node.hpp"

#include <algorithm>
#include <cmath>
#include <deque>
#include <fstream>

namespace {
constexpr uint32_t kMaxRecordSize = 16U * 1024U * 1024U;
}

RefereeReplayNode::RefereeReplayNode(const rclcpp::NodeOptions& options)
    : RefereeNode("referee_replay_node", options, false) {
  normal_data_file_ = declare_parameter("normal_data_file", "");
  vt_data_file_ = declare_parameter("vt_data_file", "");
  replay_rate_ = declare_parameter("replay_rate", 1.0);
  start_game_progress_ = declare_parameter("start_game_progress", -1);

  if (replay_rate_ < 0.0 || !std::isfinite(replay_rate_)) {
    RCLCPP_WARN(get_logger(), "Invalid replay_rate %.3f, using 1.0", replay_rate_);
    replay_rate_ = 1.0;
  }
  if (start_game_progress_ < -1 || start_game_progress_ > 5) {
    RCLCPP_WARN(get_logger(), "Invalid start_game_progress %lld, disabling stage seek",
                static_cast<long long>(start_game_progress_));
    start_game_progress_ = -1;
  }

  if (normal_data_file_.empty() && vt_data_file_.empty()) {
    RCLCPP_ERROR(get_logger(), "No replay file configured; set normal_data_file or vt_data_file");
    return;
  }

  if (!normal_data_file_.empty()) {
    normal_replay_thread_ = std::thread([this] { ReplayFile(normal_data_file_, true); });
  }
  if (!vt_data_file_.empty()) {
    vt_replay_thread_ = std::thread([this] { ReplayFile(vt_data_file_, false); });
  }
}

RefereeReplayNode::~RefereeReplayNode() {
  stop_replay_ = true;
  wait_condition_.notify_all();

  if (normal_replay_thread_.joinable()) {
    normal_replay_thread_.join();
  }
  if (vt_replay_thread_.joinable()) {
    vt_replay_thread_.join();
  }
}

void RefereeReplayNode::ReplayFile(const std::string& file_path, bool normal_link) {
  const char* link_name = normal_link ? "normal" : "VT";
  std::ifstream file(file_path, std::ios::binary);
  if (!file.is_open()) {
    RCLCPP_ERROR(get_logger(), "Failed to open %s replay file: %s", link_name, file_path.c_str());
    return;
  }

  file.seekg(0, std::ios::end);
  const std::streamoff total_bytes = file.tellg();
  file.seekg(0, std::ios::beg);
  if (!file || total_bytes <= 0) {
    RCLCPP_ERROR(get_logger(), "Failed to determine %s replay file size: %s", link_name, file_path.c_str());
    return;
  }

  std::streamoff replay_offset = 0;
  if (normal_link && start_game_progress_ >= 0) {
    if (!FindGameProgressOffset(file, static_cast<uint8_t>(start_game_progress_), replay_offset)) {
      RCLCPP_ERROR(get_logger(), "game_progress=%lld was not found in normal replay file",
                   static_cast<long long>(start_game_progress_));
      return;
    }
    file.clear();
    file.seekg(replay_offset, std::ios::beg);
    RCLCPP_INFO(get_logger(), "Starting replay at game_progress=%lld (file offset %lld)",
                static_cast<long long>(start_game_progress_), static_cast<long long>(replay_offset));
  }

  RCLCPP_INFO(get_logger(), "Replaying %s raw data from: %s (rate=%.3f)", link_name, file_path.c_str(),
              replay_rate_);

  bool first_record = true;
  uint64_t first_timestamp_us = 0;
  auto replay_start = std::chrono::steady_clock::now();
  auto last_progress_update = replay_start - std::chrono::seconds(1);
  size_t record_count = 0;

  const std::streamoff replay_bytes = total_bytes - replay_offset;
  PrintProgress(link_name, 0, replay_bytes, 0);

  while (!stop_replay_) {
    uint64_t timestamp_us = 0;
    uint32_t data_size = 0;

    file.read(reinterpret_cast<char*>(&timestamp_us), sizeof(timestamp_us));
    if (file.eof() && file.gcount() == 0) {
      break;
    }
    if (!file) {
      RCLCPP_ERROR(get_logger(), "Truncated timestamp in %s replay file after %zu records", link_name, record_count);
      return;
    }

    file.read(reinterpret_cast<char*>(&data_size), sizeof(data_size));
    if (!file) {
      RCLCPP_ERROR(get_logger(), "Truncated data length in %s replay file after %zu records", link_name, record_count);
      return;
    }
    if (data_size > kMaxRecordSize) {
      RCLCPP_ERROR(get_logger(), "Invalid %s replay record size: %u bytes", link_name, data_size);
      return;
    }
    // Some field recordings are zero-padded after the last valid record.
    // Treat the first empty zero-timestamp record as EOF instead of reporting
    // a non-monotonic timestamp error.
    if (record_count > 0 && timestamp_us == 0 && data_size == 0) {
      RCLCPP_INFO(get_logger(), "Reached trailing zero padding in %s replay file", link_name);
      break;
    }

    std::string data(data_size, '\0');
    file.read(data.data(), static_cast<std::streamsize>(data.size()));
    if (!file) {
      RCLCPP_ERROR(get_logger(), "Truncated payload in %s replay file after %zu records", link_name, record_count);
      return;
    }

    if (first_record) {
      first_timestamp_us = timestamp_us;
      replay_start = std::chrono::steady_clock::now();
      first_record = false;
    } else if (timestamp_us < first_timestamp_us) {
      RCLCPP_ERROR(get_logger(), "Non-monotonic timestamp in %s replay file after %zu records", link_name,
                   record_count);
      return;
    }

    if (!WaitForTimestamp(timestamp_us, first_timestamp_us, replay_start)) {
      return;
    }

    if (normal_link) {
      FeedNormalData(data);
    } else {
      FeedVtData(data);
    }
    ++record_count;

    const auto now = std::chrono::steady_clock::now();
    if (now - last_progress_update >= std::chrono::seconds(1)) {
      PrintProgress(link_name, file.tellg() - replay_offset, replay_bytes, record_count);
      last_progress_update = now;
    }
  }

  if (!stop_replay_) {
    PrintProgress(link_name, replay_bytes, replay_bytes, record_count, true);
    RCLCPP_INFO(get_logger(), "%s raw data replay completed: %zu records", link_name, record_count);
  }
}

bool RefereeReplayNode::FindGameProgressOffset(std::ifstream& file, uint8_t target_progress,
                                               std::streamoff& offset) {
  using Revision = rm::device::RefereeRevision;
  using CmdId = rm::device::RefereeCmdId<Revision::kNewV200>;
  rm::device::Referee<Revision::kNewV200> scanner;
  std::deque<std::streamoff> recent_origins;
  uint16_t progress_mask = 0;
  bool found = false;

  scanner.AttachCallback([&](uint16_t cmd_id, uint8_t) {
    if (cmd_id != CmdId::kGameStatus) {
      return;
    }
    const uint8_t progress = scanner.data().game_status.game_progress;
    progress_mask |= static_cast<uint16_t>(1U << progress);
    if (progress == target_progress) {
      // Start slightly before the matching frame so a frame split across raw
      // data records is fed to the decoder in full.
      offset = recent_origins.empty() ? 0 : recent_origins.front();
      found = true;
    }
  });

  file.clear();
  file.seekg(0, std::ios::beg);
  while (file && !found) {
    const std::streamoff record_offset = file.tellg();
    uint64_t timestamp_us = 0;
    uint32_t data_size = 0;
    file.read(reinterpret_cast<char*>(&timestamp_us), sizeof(timestamp_us));
    file.read(reinterpret_cast<char*>(&data_size), sizeof(data_size));
    if (!file) {
      break;
    }
    if (data_size > kMaxRecordSize) {
      return false;
    }

    std::string data(data_size, '\0');
    file.read(data.data(), data_size);
    if (!file) {
      return false;
    }

    for (const unsigned char byte : data) {
      recent_origins.push_back(record_offset);
      if (recent_origins.size() > 512) {
        recent_origins.pop_front();
      }
      scanner << byte;
      if (found) {
        break;
      }
    }
  }
  if (!found) {
    RCLCPP_WARN(get_logger(), "Stage scan did not find game_progress=%u; available mask: 0x%04x",
                target_progress, progress_mask);
  }
  return found;
}

void RefereeReplayNode::PrintProgress(const char* link_name, std::streamoff bytes_read,
                                      std::streamoff total_bytes, size_t record_count,
                                      bool force_newline) {
  constexpr int kBarWidth = 30;
  const double ratio = std::max(0.0, std::min(1.0, static_cast<double>(bytes_read) / total_bytes));
  const int completed = static_cast<int>(ratio * kBarWidth);
  std::string bar(kBarWidth, ' ');
  std::fill_n(bar.begin(), completed, '=');
  if (completed < kBarWidth) {
    bar[completed] = '>';
  }

  std::lock_guard<std::mutex> lock(progress_mutex_);
  RCLCPP_INFO(get_logger(), "[%s replay] [%s] %6.2f%%  %zu records%s", link_name, bar.c_str(),
              ratio * 100.0, record_count, force_newline ? " (completed)" : "");
}

bool RefereeReplayNode::WaitForTimestamp(uint64_t timestamp_us, uint64_t first_timestamp_us,
                                         const std::chrono::steady_clock::time_point& replay_start) {
  if (replay_rate_ == 0.0) {
    return !stop_replay_;
  }

  const auto elapsed_us = timestamp_us - first_timestamp_us;
  const auto scaled_us = static_cast<uint64_t>(static_cast<double>(elapsed_us) / replay_rate_);
  const auto target = replay_start + std::chrono::microseconds(scaled_us);
  std::unique_lock<std::mutex> lock(wait_mutex_);
  return !wait_condition_.wait_until(lock, target, [this] { return stop_replay_.load(); });
}

#include <rclcpp_components/register_node_macro.hpp>
RCLCPP_COMPONENTS_REGISTER_NODE(RefereeReplayNode)
