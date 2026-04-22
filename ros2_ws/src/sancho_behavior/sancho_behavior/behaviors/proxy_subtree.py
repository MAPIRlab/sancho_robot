from typing import Optional, Dict, Any
import py_trees
from py_trees.behaviour import Behaviour
from py_trees.common import Status

from sancho_behavior.behaviors.factories import SubtreeRegistry

class ProxySubtreeBehavior(Behaviour):
    """
    BTA-072: Encapsulates a complex subtree as a "leaf node" to its parent.
    
    This behavior uses a factory (via SubtreeRegistry) to instantiate an internal
    subtree. During the `update()` tick, it simply ticks its internal subtree
    and propagates the status (SUCCESS, FAILURE, RUNNING) back to the parent.
    
    This abstracts away the complexity of the subtree from the main tree,
    improving modularity and reusability.
    """

    def __init__(self, name: str, subtree_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name)
        self.subtree_id = subtree_id
        self.config = config
        self.internal_root: Optional[Behaviour] = None
        # We use a dummy BehaviourTree just to hold the tree structure,
        # but we could also just tick the root directly. We will tick the root.

    def setup(self, **kwargs):
        """Instantiate the subtree during setup and call its setup."""
        # Create the subtree using the registry
        self.internal_root = SubtreeRegistry.create(
            self.subtree_id, 
            name=f"{self.name}_root", 
            config=self.config
        )

        # Recursively setup descendants because this subtree is hidden behind
        # a proxy and therefore is not traversed by the parent BehaviourTree setup.
        visited: set[int] = set()

        def setup_recursive(node: Behaviour):
            node_id = id(node)
            if node_id in visited:
                return
            visited.add(node_id)

            if hasattr(node, "setup"):
                node.setup(**kwargs)

            decorated = getattr(node, "decorated", None)
            if decorated is not None:
                setup_recursive(decorated)

            for child in getattr(node, "children", []):
                setup_recursive(child)

        setup_recursive(self.internal_root)

    def initialise(self):
        """Called when this proxy enters the RUNNING state for the first time."""
        pass # The internal root will initialise itself when ticked.

    def update(self) -> Status:
        """Tick the internal subtree and return its status."""
        if self.internal_root is None:
            self.logger.error(f"[{self.name}] Proxy missing internal subtree!")
            return Status.FAILURE
        
        # Tick the internal subtree once
        self.internal_root.tick_once()
        
        # Mirror its status
        return self.internal_root.status

    def terminate(self, new_status: Status):
        """Called when this proxy stops running."""
        # If the proxy is being preempted or has finished, we might want to stop the internal tree
        if self.internal_root is not None and self.internal_root.status == Status.RUNNING:
            self.internal_root.stop(new_status)
