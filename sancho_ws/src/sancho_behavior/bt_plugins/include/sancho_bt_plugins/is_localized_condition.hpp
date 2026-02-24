#ifndef SANCHO_BT_PLUGINS__IS_LOCALIZED_CONDITION_HPP_
#define SANCHO_BT_PLUGINS__IS_LOCALIZED_CONDITION_HPP_

#include <string>

#include "rclcpp/rclcpp.hpp"
#include "behaviortree_cpp_v3/condition_node.h"
#include "geometry_msgs/msg/pose_with_covariance_stamped.hpp"

namespace sancho_bt_plugins
{

class IsLocalized : public BT::ConditionNode
{
public:
  // Constructor
  IsLocalized(const std::string & name, const BT::NodeConfiguration & config);

  // Callback
  void poseCallback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg);

  // Método principal
  BT::NodeStatus tick() override;

  // Definición de puertos
  static BT::PortsList providedPorts();

private:
  // Puntero al nodo de ROS (obtenido del Blackboard)
  rclcpp::Node::SharedPtr node_;
  
  // Suscriptor
  rclcpp::Subscription<geometry_msgs::msg::PoseWithCovarianceStamped>::SharedPtr subscription_;
  geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr last_pose_;

  rclcpp::CallbackGroup::SharedPtr callback_group_;
  rclcpp::executors::SingleThreadedExecutor callback_group_executor_;
};

}  // namespace sancho_bt_plugins

#endif  // SANCHO_BT_PLUGINS__IS_LOCALIZED_CONDITION_HPP_