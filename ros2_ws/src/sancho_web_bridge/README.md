[← Back to Main README](../../../README.md)

# sancho_web_bridge

The `sancho_web_bridge` package exposes the Sancho robot's capabilities over the web. It provides a custom WebSocket-based ROS bridge server, a web-facing conversational assistant, a REST API for external integrations, a database manager for persistent storage, and a session manager for multi-user connections.

---

## Nodes

| Node | Description |
|------|-------------|
| `server` | WebSocket server bridging web clients to the ROS 2 topic/service graph for real-time browser GUIs |
| `sancho_web_assistant` | Web-accessible conversational assistant routing web chat through the SanchoAI pipeline |
| `api_rest` | REST API endpoint for external systems to interact with Sancho services over HTTP |
| `database_manager` | Persistent data storage for conversation logs and user session data |
| `session_manager` | Multi-user web session lifecycle: tracking connections and routing messages |

---

## ROS 2 API

### Services Consumed

| Service | Type | Description |
|---------|------|-------------|
| `sancho_hri/ai/prompt` | `sancho_interfaces/srv/SanchoPrompt` | Route web chat messages to AI |
| *(various topic subscriptions)* | *(via WebSocket bridge)* | Dynamic ROS topic bridging |

---

## Dependencies

- **Internal:** `sancho_interfaces`
- **External:** `rclpy`
