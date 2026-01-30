#include "sancho_bt_plugins/is_localized_condition.hpp"
#include "behaviortree_cpp_v3/bt_factory.h"

namespace sancho_bt_plugins
{

IsLocalized::IsLocalized(const std::string & name, const BT::NodeConfiguration & config)
: BT::ConditionNode(name, config)
{
  // 1. Obtener el nodo ROS del Blackboard
  if (!config.blackboard->get("node", node_)) {
    // Si no hay nodo, imprimimos error a consola estándar porque no tenemos logger de ROS
    std::cerr << "[IsLocalized] ERROR: No se encontró 'node' en el blackboard." << std::endl;
    return;
  }

  // 2. Obtener el nombre del topic (o usar default)
  std::string topic;
  if (!getInput("topic", topic)) {
    topic = "/amcl_pose";
  }

  // 3. Crear suscripción con QoS de SensorData (mejor rendimiento para sensores)
  // Usamos this->mutex_ para proteger la escritura en last_pose_
  subscription_ = node_->create_subscription<geometry_msgs::msg::PoseWithCovarianceStamped>(
    topic,
    rclcpp::SensorDataQoS(),
    [this](const geometry_msgs::msg::PoseWithCovarianceStamped::SharedPtr msg) {
      std::lock_guard<std::mutex> lock(mutex_);
      last_pose_ = msg;
    });
}

BT::PortsList IsLocalized::providedPorts()
{
  return {
    BT::InputPort<double>("max_covariance", 0.10, "Umbral máximo de incertidumbre (x+y+yaw)"),
    BT::InputPort<std::string>("topic", "/amcl_pose", "Topic de pose con covarianza")
  };
}

BT::NodeStatus IsLocalized::tick()
{
  // Bloqueamos el mutex para leer de forma segura
  std::lock_guard<std::mutex> lock(mutex_);

  if (!last_pose_) {
    // Aún no hemos recibido datos
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

  // Mensaje de log cada 1s
  RCLCPP_INFO_THROTTLE(node_->get_logger(), *node_->get_clock(), 1000, 
      "IsLocalized Check -> Covarianza Actual: %.4f / Umbral: %.4f | Estado: %s", 
      current_cov, 
      max_cov,
      (current_cov < max_cov) ? "OK (Success)" : "ALTA (Failure)");
  std::cout << "IsLocalized Check -> Covarianza Actual: " << current_cov << " / Umbral: " << max_cov << " | Estado: " << (current_cov < max_cov ? "OK (Success)" : "ALTA (Failure)") << std::endl;
  if (current_cov < max_cov) {
    return BT::NodeStatus::SUCCESS;
  } else {
    return BT::NodeStatus::FAILURE;
  }
}

}  // namespace sancho_bt_plugins

// --- REGISTRO DEL PLUGIN (FORMA MANUAL Y ROBUSTA) ---

// Usamos extern "C" para que el compilador no cambie el nombre de la función
// y Nav2 pueda encontrar el símbolo "BT_RegisterNodesFromPlugin"
extern "C" {
  
  void BT_RegisterNodesFromPlugin(BT::BehaviorTreeFactory& factory)
  {
    std::cout << "\n\n[!!!] LIBRERIA SANCHO_BT_PLUGINS CARGADA CON EXITO [!!!]\n\n" << std::endl;
    // Registramos tu nodo con el nombre que usas en el XML
    factory.registerNodeType<sancho_bt_plugins::IsLocalized>("IsLocalized");
  }

}