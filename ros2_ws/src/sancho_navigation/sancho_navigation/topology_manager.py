import yaml
import networkx as nx
from geometry_msgs.msg import PoseStamped

class TopologyManager:
    """Manage a topological graph loaded from a YAML file.

    Expected YAML format:
    ```yaml
    nodes:
      - id: 0
        label: "room_a"
        type: "room"
        x: 1.0
        y: 2.0
        yaw: 0.0
      - id: 1
        label: "room_b"
        type: "room"
        x: 5.0
        y: 2.0
        yaw: 0.0
    edges:
      - from: 0
        to: 1
        type: "door"
        weight: 1.0
    ```
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_lookup = {}

    def load_graph(self, yaml_path: str) -> bool:
        """Load graph from a YAML file.
        Returns True on success, False otherwise.
        """
        try:
            with open(yaml_path, "r") as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"[TopologyManager] Failed to read {yaml_path}: {e}")
            return False

        self.graph.clear()
        self.node_lookup.clear()
        # Load nodes
        for node in data.get("nodes", []):
            nid = node["id"]
            self.graph.add_node(nid, **node)
            self.node_lookup[node["label"]] = nid
        # Load edges
        for edge in data.get("edges", []):
            src = edge["from"]
            dst = edge["to"]
            self.graph.add_edge(src, dst, **edge)
        return True

    def get_node_by_label(self, label: str):
        return self.node_lookup.get(label)

    def find_path(self, start_label: str, goal_label: str):
        """Return a list of node IDs representing the shortest path.
        Uses Dijkstra's algorithm with edge weight.
        """
        start = self.get_node_by_label(start_label)
        goal = self.get_node_by_label(goal_label)
        if start is None or goal is None:
            return []
        try:
            path = nx.dijkstra_path(self.graph, start, goal, weight="weight")
            return path
        except nx.NetworkXNoPath:
            return []

    def nearest_node(self, pose: PoseStamped, tolerance: float = 0.5):
        """Find the nearest node to a given pose (euclidean distance).
        Returns the node label or None if no node within tolerance.
        """
        min_dist = float("inf")
        nearest = None
        for nid, data in self.graph.nodes(data=True):
            dx = pose.pose.position.x - data.get("x", 0.0)
            dy = pose.pose.position.y - data.get("y", 0.0)
            dist = (dx ** 2 + dy ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                nearest = data.get("label")
        if min_dist <= tolerance:
            return nearest
        return None
