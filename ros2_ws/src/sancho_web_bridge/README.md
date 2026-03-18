# sancho_web_bridge

**Role:** The `sancho_web_bridge` package exposes the Sancho robot's capabilities over the web. It provides a custom WebSocket-based ROS bridge server, a web-facing conversational assistant, a REST API for external integrations, a database manager for persistent storage, and a session manager for multi-user web connections.

## Core Nodes

### `server`
- **Specific Function:** A custom WebSocket server that bridges web clients to the ROS 2 topic/service graph, enabling browser-based GUIs to subscribe and publish to ROS topics in real-time.

### `sancho_web_assistant`
- **Specific Function:** A web-accessible version of the conversational assistant, routing web chat messages through the Sancho AI pipeline.

### `api_rest`
- **Specific Function:** Exposes a REST API endpoint for external systems to interact with Sancho's services (e.g., triggering prompts, querying models) over HTTP.

### `database_manager`
- **Specific Function:** Manages persistent data storage for the web bridge, including conversation logs and user session data.

### `session_manager`
- **Specific Function:** Handles multi-user web session lifecycle, tracking active connections and routing messages to the correct chat contexts.

---

## Dependencies

- `rclpy`
- `sancho_interfaces`
