from typing import Callable, Dict, Any, Optional
import py_trees

# Signature for a subtree factory:
# create_subtree(name: str, config: Optional[Dict[str, Any]] = None) -> py_trees.behaviour.Behaviour
SubtreeFactory = Callable[[str, Optional[Dict[str, Any]]], py_trees.behaviour.Behaviour]

class SubtreeRegistry:
    """
    Registry for subtrees. Allows dynamic instantiation of complex subtrees
    without direct coupling.
    """
    _factories: Dict[str, SubtreeFactory] = {}

    @classmethod
    def register(cls, subtree_id: str):
        """Decorator to register a factory function."""
        def decorator(func: SubtreeFactory) -> SubtreeFactory:
            cls._factories[subtree_id] = func
            return func
        return decorator

    @classmethod
    def create(cls, subtree_id: str, name: str, config: Optional[Dict[str, Any]] = None) -> py_trees.behaviour.Behaviour:
        """Create a subtree using its registered factory."""
        if subtree_id not in cls._factories:
            raise ValueError(f"Subtree '{subtree_id}' not found in registry. Did you import it?")
        return cls._factories[subtree_id](name, config)

    @classmethod
    def list_factories(cls) -> list[str]:
        return list(cls._factories.keys())
