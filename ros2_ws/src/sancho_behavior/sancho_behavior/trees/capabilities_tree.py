import py_trees

from sancho_behavior.behaviors.capabilities_runtime import (
    ActiveLayerResourceRequests,
    ManageTrackingCapability,
    ResourceArbiter,
)


def create_capabilities_runtime_subtree() -> py_trees.behaviour.Behaviour:
    """
    Persistent runtime for shared capabilities.

    This branch is intentionally non-intrusive: it maintains capability state,
    TTL windows and resource ownership, but does not command actuators directly.
    """
    runtime = py_trees.composites.Sequence(name="CapabilitiesRuntime", memory=False)

    runtime.add_children(
        [
            ActiveLayerResourceRequests(name="ActiveLayerResourceRequests"),
            ManageTrackingCapability(name="ManageTrackingCapability"),
            ResourceArbiter(name="ResourceArbiter"),
        ]
    )

    return runtime
