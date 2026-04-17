#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <map>
#include <boost/algorithm/string.hpp>
#include <rclcpp/rclcpp.hpp>
#include <behaviortree_cpp_v3/action_node.h>
#include <behaviortree_cpp_v3/bt_factory.h>
#include <nav_msgs/msg/path.hpp>
#include <geometry_msgs/msg/pose_stamped.hpp>
#include <tf2/LinearMath/Quaternion.h>
#include <tf2_geometry_msgs/tf2_geometry_msgs.hpp>
#include <tf2_ros/buffer.h>
#include <tf2_ros/transform_listener.h>
#include <topology_graph/srv/graph.hpp>

// A Critical Passage is defined by its center (CP/CNP node location)
// and its safe approach waypoints (ING points on each side of the passage).
struct CriticalPassage {
    std::string label;
    geometry_msgs::msg::Point node_center;     // CP or CNP center
    std::vector<geometry_msgs::msg::Point> waypoints;  // ING points (safe approach waypoints)
};

class InjectWaypoints : public BT::SyncActionNode
{
public:
    InjectWaypoints(const std::string& name, const BT::NodeConfiguration& config)
        : BT::SyncActionNode(name, config), 
          graph_loaded_(false), 
          graph_request_pending_(false),
          retry_count_(0)
    {
        if (!config.blackboard->get<rclcpp::Node::SharedPtr>("node", node_)) {
            RCLCPP_ERROR(rclcpp::get_logger("InjectWaypoints"), "Failed to get ROS node");
            return;
        }

        RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] Constructor called, creating service client...");
        
        // Create the client but DO NOT block here. Let Nav2 boot unhindered.
        graph_client_ = node_->create_client<topology_graph::srv::Graph>("topology_graph/graph");
        // Use transient_local so RViz can see it even if subscription starts after publication
        auto qos = rclcpp::QoS(10).transient_local();
        path_pub_ = node_->create_publisher<nav_msgs::msg::Path>("modified_plan", qos);
    }

    static BT::PortsList providedPorts()
    {
        return {
            BT::InputPort<nav_msgs::msg::Path>("input_path"),
            BT::OutputPort<nav_msgs::msg::Path>("output_path")
        };
    }

    BT::NodeStatus tick() override
    {
        nav_msgs::msg::Path path;
        if (!getInput("input_path", path)) {
            RCLCPP_ERROR(node_->get_logger(), "[InjectWaypoints] Failed to get input_path from blackboard");
            return BT::NodeStatus::FAILURE;
        }

        // ===================================================================
        // LAZY INITIALIZATION: Non-blocking graph loading with retry logic
        // ===================================================================
        if (!graph_loaded_) {
            
            auto now = std::chrono::steady_clock::now();
            static auto last_print_time = now;
            bool should_print = std::chrono::duration_cast<std::chrono::seconds>(now - last_print_time).count() >= 2;

            if (!graph_request_pending_) {
                if (graph_client_->service_is_ready()) {
                    RCLCPP_INFO(node_->get_logger(), 
                        "[InjectWaypoints] Topology service detected! Sending 'GetAllNodes' request (attempt %d)...", 
                        retry_count_ + 1);
                    
                    auto request = std::make_shared<topology_graph::srv::Graph::Request>();
                    request->cmd = "GetAllNodes"; 
                    
                    // Use a temporary isolated node to avoid deadlocks with the bt_navigator executor.
                    // This was identified as a source of previous communication failures.
                    temp_node_ = rclcpp::Node::make_shared("inject_wp_graph_client_temp");
                    temp_client_ = temp_node_->create_client<topology_graph::srv::Graph>("topology_graph/graph");
                    
                    if (!temp_client_->wait_for_service(std::chrono::seconds(2))) {
                        RCLCPP_WARN(node_->get_logger(), "[InjectWaypoints] Temp client could not reach service, will retry...");
                        temp_node_.reset();
                        temp_client_.reset();
                        // Pass-through
                        setOutput("output_path", path);
                        return BT::NodeStatus::SUCCESS;
                    }
                    
                    request_future_ = temp_client_->async_send_request(request).future.share();
                    graph_request_pending_ = true;
                } else {
                    if (should_print) {
                        RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] Waiting for /topology_graph/graph service...");
                        last_print_time = now;
                    }
                }
            } else {
                // We have a pending request. Try to spin the temp node to get the response.
                if (request_future_.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
                    RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] Response received! Parsing graph data...");
                    auto response = request_future_.get();
                    
                    if (response->success && !response->result.empty()) {
                        parseGraphResponse(response);
                        graph_loaded_ = true;
                        retry_count_ = 0;
                        
                        RCLCPP_INFO(node_->get_logger(), 
                            "===================================\n"
                            "Topology Graph successfully loaded!\n"
                            "Cached %zu Critical Passages.\n"
                            "Waypoint Injection is ACTIVE.\n"
                            "===================================", cached_cps_.size());
                        
                        // Log details of each CP
                        for (const auto& cp : cached_cps_) {
                            RCLCPP_INFO(node_->get_logger(), 
                                "  CP '%s': center=(%.2f, %.2f), %zu ING waypoints",
                                cp.label.c_str(), cp.node_center.x, cp.node_center.y, cp.waypoints.size());
                            for (size_t i = 0; i < cp.waypoints.size(); ++i) {
                                RCLCPP_INFO(node_->get_logger(), 
                                    "    ING[%zu]: (%.2f, %.2f)", i, cp.waypoints[i].x, cp.waypoints[i].y);
                            }
                        }
                    } else {
                        RCLCPP_WARN(node_->get_logger(), 
                            "[InjectWaypoints] Server responded but success=%d, result_size=%zu. Retrying...",
                            response->success, response->result.size());
                        retry_count_++;
                        graph_request_pending_ = false;
                    }
                    
                    // Clean up temp node
                    temp_node_.reset();
                    temp_client_.reset();
                    
                } else {
                    // Still pending
                    if (should_print) {
                        RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] Request pending, waiting for server reply...");
                        last_print_time = now;
                    }
                    // Spin the temp node to process the response callback
                    rclcpp::spin_some(temp_node_);
                }
            }

            // While graph is loading, pass the path through unmodified
            RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] Graph not loaded yet, passing path through (size=%zu)", path.poses.size());
            setOutput("output_path", path);
            return BT::NodeStatus::SUCCESS;
        }

        // ===================================================================
        // GET ROBOT POSITION via TF (needed to skip already-passed waypoints)
        // ===================================================================
        geometry_msgs::msg::Point robot_position;
        bool have_robot_pose = false;
        {
            std::shared_ptr<tf2_ros::Buffer> tf_buffer;
            if (config().blackboard->get<std::shared_ptr<tf2_ros::Buffer>>("tf_buffer", tf_buffer)) {
                try {
                    auto transform = tf_buffer->lookupTransform("map", "base_link", tf2::TimePointZero);
                    robot_position.x = transform.transform.translation.x;
                    robot_position.y = transform.transform.translation.y;
                    robot_position.z = 0.0;
                    have_robot_pose = true;
                } catch (tf2::TransformException &ex) {
                    RCLCPP_WARN(node_->get_logger(), "[InjectWaypoints] TF lookup failed: %s. Will inject all waypoints.", ex.what());
                }
            } else {
                RCLCPP_WARN(node_->get_logger(), "[InjectWaypoints] No tf_buffer on blackboard. Will inject all waypoints.");
            }
        }

        // ===================================================================
        // MAIN LOGIC: Check if path crosses any Critical Passage
        // ===================================================================
        
        // Structure to hold data for splicing
        struct Insertion {
            size_t start_index;   // First pose in the passage region
            size_t end_index;     // Last pose in the passage region
            std::vector<geometry_msgs::msg::PoseStamped> poses;  // Replacement poses
        };
        std::vector<Insertion> pending_insertions;

        // How close the global path must get to a CP center to trigger injection
        const double PROXIMITY_THRESHOLD = 1.0; 
        
        RCLCPP_INFO(node_->get_logger(), 
            "[InjectWaypoints] Evaluating path (size=%zu) against %zu cached CPs (robot at %.2f, %.2f)...", 
            path.poses.size(), cached_cps_.size(),
            have_robot_pose ? robot_position.x : 0.0, have_robot_pose ? robot_position.y : 0.0);

        for (const auto& cp : cached_cps_) {
            // Safety check: need at least 2 ING points
            if (cp.waypoints.size() < 2) {
                RCLCPP_WARN(node_->get_logger(), 
                    "[InjectWaypoints] CP '%s' has only %zu ING waypoints, skipping",
                    cp.label.c_str(), cp.waypoints.size());
                continue; 
            }

            double min_dist = std::numeric_limits<double>::max();
            size_t closest_index = 0;

            // Find the closest pose in the path to the CP center
            for (size_t i = 0; i < path.poses.size(); ++i) {
                double dist = std::hypot(
                    path.poses[i].pose.position.x - cp.node_center.x,
                    path.poses[i].pose.position.y - cp.node_center.y
                );
                if (dist < min_dist) {
                    min_dist = dist;
                    closest_index = i;
                }
            }

            RCLCPP_INFO(node_->get_logger(), 
                "[InjectWaypoints] CP '%s': closest path distance = %.3f m (threshold = %.1f m)",
                cp.label.c_str(), min_dist, PROXIMITY_THRESHOLD);

            // Only inject if the path actually passes near this CP
            if (min_dist > PROXIMITY_THRESHOLD) continue;

            RCLCPP_INFO(node_->get_logger(), 
                "[InjectWaypoints] PATH CROSSES CP '%s'! Preparing waypoint injection...",
                cp.label.c_str());

            // Find the segment of the path that is within the passage region.
            // We define the passage region as poses within a radius that encompasses 
            // the CP center and its ING waypoints.
            double passage_radius = 0.0;
            for (const auto& wp : cp.waypoints) {
                double d = std::hypot(wp.x - cp.node_center.x, wp.y - cp.node_center.y);
                passage_radius = std::max(passage_radius, d);
            }
            // Add some margin
            passage_radius += 0.3;

            size_t region_start = closest_index;
            size_t region_end = closest_index;

            // Expand backwards to find where path enters the passage region
            for (size_t i = closest_index; i > 0; --i) {
                double dist = std::hypot(
                    path.poses[i].pose.position.x - cp.node_center.x,
                    path.poses[i].pose.position.y - cp.node_center.y
                );
                if (dist > passage_radius) break;
                region_start = i;
            }
            // Expand forwards to find where path exits the passage region
            for (size_t i = closest_index; i < path.poses.size(); ++i) {
                double dist = std::hypot(
                    path.poses[i].pose.position.x - cp.node_center.x,
                    path.poses[i].pose.position.y - cp.node_center.y
                );
                if (dist > passage_radius) break;
                region_end = i;
            }

            RCLCPP_INFO(node_->get_logger(), 
                "[InjectWaypoints] Passage region: poses [%zu - %zu] (passage_radius=%.2f m)",
                region_start, region_end, passage_radius);

            // Build the injection sequence: [ING1, CP_center, ING2]
            // Determine direction of travel to order the ING points correctly
            Insertion inst;
            inst.start_index = region_start;
            inst.end_index = region_end;

            std::vector<geometry_msgs::msg::Point> points_to_inject = cp.waypoints;

            // --- DIRECTION OF TRAVEL LOGIC ---
            // Look at where the path EXITS the passage region.
            // When navigating, path.poses[region_end] is where we leave the passage.
            double dist_end_to_first = std::hypot(
                path.poses[region_end].pose.position.x - points_to_inject.front().x,
                path.poses[region_end].pose.position.y - points_to_inject.front().y
            );
            double dist_end_to_last = std::hypot(
                path.poses[region_end].pose.position.x - points_to_inject.back().x,
                path.poses[region_end].pose.position.y - points_to_inject.back().y
            );

            // We want points_to_inject.back() to be the EXIT waypoint.
            if (dist_end_to_first < dist_end_to_last) {
                std::reverse(points_to_inject.begin(), points_to_inject.end());
                RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] Reversed ING order based on path exit");
            }

            // Build raw passage sequence: ING_approach → CP_center → ING_exit
            std::vector<geometry_msgs::msg::Point> raw_sequence;
            raw_sequence.push_back(points_to_inject[0]);      // ING approach
            raw_sequence.push_back(cp.node_center);           // CP center (passage midpoint)
            raw_sequence.push_back(points_to_inject[1]);      // ING exit

            // --- SKIP ALREADY-PASSED WAYPOINTS ---
            if (have_robot_pose) {
                double robot_to_cp = std::hypot(
                    robot_position.x - cp.node_center.x,
                    robot_position.y - cp.node_center.y
                );

                // Check if we are inside the passage zone
                if (robot_to_cp <= passage_radius) {
                    
                    // Define a 1D axis along the passage from ING_approach to ING_exit
                    double dx = raw_sequence.back().x - raw_sequence.front().x;
                    double dy = raw_sequence.back().y - raw_sequence.front().y;
                    double axis_len_sq = dx*dx + dy*dy;
                    
                    if (axis_len_sq > 0.001) {
                        // Project robot onto this axis
                        double rx = robot_position.x - raw_sequence.front().x;
                        double ry = robot_position.y - raw_sequence.front().y;
                        
                        // robot_progress is the fraction of distance along the axis [0.0 = ING_approach, 1.0 = ING_exit]
                        double robot_progress = (rx*dx + ry*dy) / axis_len_sq;
                        
                        // CP_progress is where the CP center is along this axis (usually ~0.5)
                        double cx = cp.node_center.x - raw_sequence.front().x;
                        double cy = cp.node_center.y - raw_sequence.front().y;
                        double cp_progress = (cx*dx + cy*dy) / axis_len_sq;

                        RCLCPP_INFO(node_->get_logger(),
                            "[InjectWaypoints] Robot 1D progress=%.2f, CP 1D progress=%.2f",
                            robot_progress, cp_progress);

                        // If robot has passed CP, keep ONLY the exit waypoint
                        if (robot_progress > cp_progress) {
                            RCLCPP_INFO(node_->get_logger(),
                                "[InjectWaypoints] Robot is past CP center. Keeping ONLY exit waypoint.");
                            raw_sequence.erase(raw_sequence.begin(), raw_sequence.begin() + 2);
                        }
                        // Drop ING_approach aggressively if within 20% distance of it (robot_progress > -0.2)
                        // This prevents dogleg sharp turns if the path/robot is approaching from the side.
                        else if (robot_progress > -0.20) {
                            RCLCPP_INFO(node_->get_logger(),
                                "[InjectWaypoints] Robot is near or mid-passage. Aiming straight for CP.");
                            raw_sequence.erase(raw_sequence.begin(), raw_sequence.begin() + 1);
                        }
                    }
                }
            }

            // Build the FINAL anchored sequence bridging the global path cuts
            std::vector<geometry_msgs::msg::Point> full_sequence;
            
            // Anchor 1: Where the global path was cut
            full_sequence.push_back(path.poses[region_start].pose.position);
            
            // Insert the remaining passage points
            full_sequence.insert(full_sequence.end(), raw_sequence.begin(), raw_sequence.end());
            
            // Anchor 2: Where the global path resumes
            if (region_end < path.poses.size()) {
                full_sequence.push_back(path.poses[region_end].pose.position);
            }

            // --- INTERPOLATE & YAW CALCULATION ---
            // SimpleSmoother requires dense paths. We linearly interpolate between the waypoints 
            // to restore density (e.g. 5cm spacing).
            double desired_spacing = 0.05; // 5 cm

            for (size_t w = 0; w < full_sequence.size(); ++w) {
                // Determine direction to the NEXT waypoint for yaw calculation
                double yaw = 0.0;
                geometry_msgs::msg::Point current_pt = full_sequence[w];
                geometry_msgs::msg::Point next_pt;
                bool has_next = false;

                if (w < full_sequence.size() - 1) {
                    next_pt = full_sequence[w+1];
                    has_next = true;
                    yaw = std::atan2(next_pt.y - current_pt.y, next_pt.x - current_pt.x);
                } else if (region_end + 1 < path.poses.size()) {
                    next_pt = path.poses[region_end + 1].pose.position;
                    has_next = true;
                    yaw = std::atan2(next_pt.y - current_pt.y, next_pt.x - current_pt.x);
                } else if (full_sequence.size() > 1) {
                    // Very end of path, just use previous direction
                    yaw = std::atan2(current_pt.y - full_sequence[w-1].y, current_pt.x - full_sequence[w-1].x);
                }

                // Add the exact waypoint
                geometry_msgs::msg::PoseStamped new_pose;
                new_pose.header = path.header;
                new_pose.pose.position = current_pt;
                tf2::Quaternion q;
                q.setRPY(0, 0, yaw);
                new_pose.pose.orientation = tf2::toMsg(q);
                inst.poses.push_back(new_pose);

                RCLCPP_INFO(node_->get_logger(), 
                    "[InjectWaypoints] Waypoint %zu: (%.3f, %.3f) yaw=%.2f rad",
                    w, current_pt.x, current_pt.y, yaw);

                // Interpolate dense points up to the next waypoint
                if (has_next) {
                    double dist = std::hypot(next_pt.x - current_pt.x, next_pt.y - current_pt.y);
                    int num_interpolated = std::floor(dist / desired_spacing);
                    
                    if (num_interpolated > 0) { // Don't interpolate if they are identical
                        double dx = (next_pt.x - current_pt.x) / (num_interpolated + 1);
                        double dy = (next_pt.y - current_pt.y) / (num_interpolated + 1);
                        
                        for (int k = 1; k <= num_interpolated; ++k) {
                            geometry_msgs::msg::PoseStamped interp_pose;
                            interp_pose.header = path.header;
                            interp_pose.pose.position.x = current_pt.x + dx * k;
                            interp_pose.pose.position.y = current_pt.y + dy * k;
                            interp_pose.pose.position.z = current_pt.z; // Usually 0
                            interp_pose.pose.orientation = new_pose.pose.orientation; // Keep same yaw along segment
                            inst.poses.push_back(interp_pose);
                        }
                    }
                }
            }
            pending_insertions.push_back(inst);
        }

        nav_msgs::msg::Path modified_path = path;

        // If no CPs were crossed, return the path untouched but still publish for RViz
        if (pending_insertions.empty()) {
            RCLCPP_INFO(node_->get_logger(), "[InjectWaypoints] No passages crossed, path unchanged (size=%zu)", path.poses.size());
            modified_path.header.frame_id = "map";
            modified_path.header.stamp = node_->get_clock()->now();
            path_pub_->publish(modified_path);
            setOutput("output_path", modified_path);
            return BT::NodeStatus::SUCCESS;
        }

        // Sort insertions descending by start_index so we can splice from the end
        // without invalidating earlier indices
        std::sort(pending_insertions.begin(), pending_insertions.end(), 
                [](const Insertion& a, const Insertion& b) { return a.start_index > b.start_index; });

        // Replace the passage region in the path with the ING waypoints
        for (const auto& inst : pending_insertions) {
            // Erase the passage region from the path
            auto erase_begin = modified_path.poses.begin() + inst.start_index;
            auto erase_end = modified_path.poses.begin() + inst.end_index + 1;
            modified_path.poses.erase(erase_begin, erase_end);
            
            // Insert the waypoints at the same position
            modified_path.poses.insert(
                modified_path.poses.begin() + inst.start_index,
                inst.poses.begin(),
                inst.poses.end()
            );
        }

        RCLCPP_INFO(node_->get_logger(), 
            "===================================\n"
            "WAYPOINTS INJECTED!\n"
            "Original Path Size: %zu\n"
            "New Path Size: %zu\n"
            "Passages Crossed: %zu\n"
            "===================================", 
            path.poses.size(), modified_path.poses.size(), pending_insertions.size());

        modified_path.header.frame_id = "map"; 
        modified_path.header.stamp = node_->get_clock()->now();
        path_pub_->publish(modified_path);

        setOutput("output_path", modified_path);
        return BT::NodeStatus::SUCCESS;
    }

private:
    rclcpp::Node::SharedPtr node_;
    rclcpp::Publisher<nav_msgs::msg::Path>::SharedPtr path_pub_;
    bool graph_loaded_;
    bool graph_request_pending_;
    int retry_count_;
    std::vector<CriticalPassage> cached_cps_;
    rclcpp::Client<topology_graph::srv::Graph>::SharedPtr graph_client_;
    
    // Temporary node and client for non-blocking service calls (avoids executor deadlocks)
    rclcpp::Node::SharedPtr temp_node_;
    rclcpp::Client<topology_graph::srv::Graph>::SharedPtr temp_client_;
    rclcpp::Client<topology_graph::srv::Graph>::SharedFuture request_future_;

    void parseGraphResponse(const topology_graph::srv::Graph::Response::SharedPtr& response)
    {
        cached_cps_.clear();
        std::map<std::string, CriticalPassage> temp_cp_map;
        
        // PASS 1: Find all CP and CNP nodes (critical passages)
        for (const auto& n : response->result) {
            std::vector<std::string> node_data;
            boost::split(node_data, n, boost::is_any_of(" \t\n\r"), boost::token_compress_on);
            if (node_data.size() < 5) continue;
            
            std::string label = node_data[1];
            std::string type = node_data[2];

            if (type == "CP" || type == "CNP") {
                CriticalPassage cp;
                cp.label = label;
                cp.node_center.x = std::stod(node_data[3]);
                cp.node_center.y = std::stod(node_data[4]);
                cp.node_center.z = 0.0;
                temp_cp_map[label] = cp;
                
                RCLCPP_INFO(node_->get_logger(), 
                    "[InjectWaypoints] Found %s node: label='%s' at (%.2f, %.2f)",
                    type.c_str(), label.c_str(), cp.node_center.x, cp.node_center.y);
            }
        }

        // PASS 2: Find all ING nodes (safe waypoints) that share a label with a CP/CNP
        for (const auto& n : response->result) {
            std::vector<std::string> node_data;
            boost::split(node_data, n, boost::is_any_of(" \t\n\r"), boost::token_compress_on);
            if (node_data.size() < 5) continue;

            std::string label = node_data[1];
            std::string type = node_data[2];

            if (type == "ING" && temp_cp_map.count(label) > 0) {
                geometry_msgs::msg::Point p;
                p.x = std::stod(node_data[3]);
                p.y = std::stod(node_data[4]);
                p.z = 0.0;
                temp_cp_map[label].waypoints.push_back(p);
                
                RCLCPP_INFO(node_->get_logger(), 
                    "[InjectWaypoints] Found ING for '%s' at (%.2f, %.2f)",
                    label.c_str(), p.x, p.y);
            }
        }

        // PASS 3: Build final array, only keep CPs that have exactly 2 ING waypoints
        for (auto& pair : temp_cp_map) {
            CriticalPassage& cp = pair.second;
            if (cp.waypoints.size() == 2) {
                cached_cps_.push_back(cp);
            } else {
                RCLCPP_WARN(node_->get_logger(), 
                    "[InjectWaypoints] CP '%s' has %zu ING waypoints (expected 2), skipping",
                    cp.label.c_str(), cp.waypoints.size());
            }
        }
    }
};


BT_REGISTER_NODES(factory)
{
  RCLCPP_INFO(rclcpp::get_logger("InjectWaypoints"), "[BT_PLUGIN] inject_waypoints_node loaded and registered");
  factory.registerNodeType<InjectWaypoints>("InjectWaypoints");
}