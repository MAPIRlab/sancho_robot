#include "sancho_bt_plugins/is_localized_condition.hpp"

namespace sancho_bt_plugins
{

IsLocalized::IsLocalized(const std::string & name, const BT::NodeConfiguration & config)
: BT::ConditionNode(name, config)
{
  // Obtener el nodo ROS del Blackboard
  if (!config.blackboard->get("node", node_)) {
    std::cerr << "[IsLocalized] ERROR: Couldn't find 'node' in blackboard." << std::endl;
    return;
  }

  // Obtener el nombre del topic (o usar default)
  std::string topic;
  if (!getInput("topic", topic)) {
    topic = "/amcl_pose";
  }

  // Crear Callback Group que NO se asocia automáticamente al nodo (false)
  callback_group_ = node_->create_callback_group(
    rclcpp::CallbackGroupType::MutuallyExclusive, 
    false); // <--- IMPORTANTE: false

  // Añadir el grupo a NUESTRO ejecutor local
  callback_group_executor_.add_callback_group(
    callback_group_, 
    node_->get_node_base_interface());

  // Configurar las opciones de suscripción para usar ese grupo
  rclcpp::SubscriptionOptions sub_options;
  sub_options.callback_group = callback_group_;

  // Crear suscripción al topic de la pose con covarianza
  rclcpp::QoS qos_profile(10);
  qos_profile.reliability(rclcpp::ReliabilityPolicy::Reliable);
  qos_profile.durability(rclcpp::DurabilityPolicy::Volatile);

  subscription_ = node_->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
    topic,
    qos_profile,
    std::bind(&IsLocalized::poseCallback, this, std::placeholders::_1),
    sub_options
  );
}

void IsLocalized::poseCallback(const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg)
{
  std::cout << "[IsLocalized] Pose received" << std::endl;
  last_pose_ = msg;
}

BT::PortsList IsLocalized::providedPorts()
{
  return {
    BT::InputPort<double>("max_covariance", 0.10, "Maximun pose cavariance allowed (x+y+yaw)"),
    BT::InputPort<std::string>("topic", "/amcl_pose", "Pose with covariance topic")
  };
}

BT::NodeStatus IsLocalized::tick()
{
  callback_group_executor_.spin_some(std::chrono::milliseconds(10));

  if (!last_pose_) {
    // Aún no hemos recibido datos
    std::cout << "[IsLocalized] No pose data received yet." << std::endl;
    return BT::NodeStatus::FAILURE;
  }

  double max_cov;
  if (!getInput("max_covariance", max_cov)) {
    max_cov = 0.10;
  }

  // Suma de la diagonal de la covarianza (índices 0, 7, 35 para x, y, yaw)
  double current_cov = last_pose_->pose.covariance[0] +
                       last_pose_->pose.covariance[7] +
                       last_pose_->pose.covariance[35];

  // Loggeamos la covarianza
  std::cout << "[IsLocalized] Current Covariance: " << current_cov << " / Max Covariance: " << max_cov << " | State: " << (current_cov < max_cov ? "OK (Success)" : "ALTA (Failure)") << std::endl;
  
  return (current_cov < max_cov)? BT::NodeStatus::SUCCESS : BT::NodeStatus::FAILURE;
}

}  // namespace sancho_bt_plugins

// --- REGISTRO DEL PLUGIN ---
#include "behaviortree_cpp_v3/bt_factory.h"

BT_REGISTER_NODES(factory)
{
  std::cout << "[IsLocalized] Library loaded" << std::endl;
  factory.registerNodeType<sancho_bt_plugins::IsLocalized>("IsLocalized");
}