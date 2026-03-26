#include "sancho_bt_plugins/is_localized_condition.hpp"
#include "behaviortree_cpp_v3/bt_factory.h"

namespace sancho_bt_plugins
{

IsLocalized::IsLocalized(const std::string & name, const BT::NodeConfiguration & config)
: BT::ConditionNode(name, config)
{
  std::cout << "[BT_PLUGIN] IsLocalized constructor called" << std::endl;
  // Obtener el nodo ROS del Blackboard
  if (!config.blackboard->get("node", node_)) {
    throw std::runtime_error("[IsLocalized] Missing 'node' in blackboard");
  }

  // Obtener el nombre del topic (o usar default)
  std::string topic;
  getInput("topic", topic);  // ya tienes default en providedPorts

  // Crear Callback Group independiente
  callback_group_ = node_->create_callback_group(
    rclcpp::CallbackGroupType::MutuallyExclusive,
    false);

  // Añadir el grupo a ejecutor local
  callback_group_executor_.add_callback_group(
    callback_group_,
    node_->get_node_base_interface());

  // Opciones de suscripción
  rclcpp::SubscriptionOptions sub_options;
  sub_options.callback_group = callback_group_;

  // QoS
  rclcpp::QoS qos_profile(10);
  qos_profile.reliability(rclcpp::ReliabilityPolicy::Reliable);
  qos_profile.durability(rclcpp::DurabilityPolicy::Volatile);

  // Suscripción
  subscription_ = node_->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
    topic,
    qos_profile,
    std::bind(&IsLocalized::poseCallback, this, std::placeholders::_1),
    sub_options
  );
}

void IsLocalized::poseCallback(
  const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg)
{
  last_pose_ = msg;
}

BT::PortsList IsLocalized::providedPorts()
{
  return {
    BT::InputPort<double>("max_covariance", 0.10, "Maximum pose covariance allowed (x+y+yaw)"),
    BT::InputPort<std::string>("topic", "/amcl_pose", "Pose with covariance topic")
  };
}

BT::NodeStatus IsLocalized::tick()
{
  callback_group_executor_.spin_some(std::chrono::milliseconds(10));

  if (!last_pose_) {
    return BT::NodeStatus::FAILURE;
  }

  double max_cov;
  getInput("max_covariance", max_cov);  // default ya definido

  // Covarianza: x (0), y (7), yaw (35)
  double current_cov =
    last_pose_->pose.covariance[0] +
    last_pose_->pose.covariance[7] +
    last_pose_->pose.covariance[35];

  RCLCPP_INFO(node_->get_logger(), "[IsLocalized] Returning %s",
    (current_cov < max_cov) ? "SUCCESS" : "FAILURE");

  return (current_cov < max_cov)
    ? BT::NodeStatus::SUCCESS
    : BT::NodeStatus::FAILURE;
}

}  // namespace sancho_bt_plugins


// --- REGISTRO DEL PLUGIN ---
BT_REGISTER_NODES(factory)
{
  std::cout << "[BT_PLUGIN] sancho_bt_plugins loaded and registered" << std::endl;
  factory.registerNodeType<sancho_bt_plugins::IsLocalized>("IsLocalized");
}