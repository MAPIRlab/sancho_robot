"""
BTA-002 — Layer observability behaviour.

LayerReporter is placed as the *first* child of each priority-layer subtree.
Every tick it:
  1. Derives the current reason string from a configurable blackboard key.
  2. Writes ``active_layer`` and ``active_reason`` to the blackboard.
  3. Emits an INFO log **only on transition** (layer or reason changed).
  4. Always returns SUCCESS — it must never block the layer it decorates.

Usage (see survival_tree.py, preemption_tree.py, etc.):

    reporter = LayerReporter(layer="L1", reason_key="battery_critical")
"""

import py_trees


class LayerReporter(py_trees.behaviour.Behaviour):
    """
    Observability behaviour that records which priority layer is currently
    active and the reason why.

    Blackboard Reads:
        /<reason_key>   (any): Optional key whose value is appended to the
                               reason string for human-readable traceability.

    Blackboard Writes:
        /active_layer   (str): One of "L1", "L2", "L3", "L4".
        /active_reason  (str): Short human-readable description of why this
                               layer is executing.

    Parameters:
        layer (str):      Layer tag, e.g. "L1".
        reason_key (str): Blackboard key to read as supplementary reason info.
                          Pass ``None`` for layers that are unconditional
                          catch-alls (e.g. L4 Idle).
        reason_label (str): Human-readable label for the reason key value.
    """

    # Map from layer tag to descriptive label used in log messages
    _LAYER_LABELS = {
        "L1": "Survival (critical battery)",
        "L2": "HumanPreemption (hotword)",
        "L3": "Mission (L3 active)",
        "L4": "Idle (default)",
    }

    def __init__(
        self,
        layer: str,
        reason_key: str | None = None,
        reason_label: str = "",
        name: str = "",
    ):
        super().__init__(name=name or f"LayerReporter[{layer}]")

        self.layer = layer
        self.reason_key = reason_key
        self.reason_label = reason_label or (reason_key or "unconditional")

        # Internal state for transition detection
        self._prev_layer: str = ""
        self._prev_reason: str = ""

        # Blackboard client
        self.bb = self.attach_blackboard_client(name=self.name)

        self.bb.register_key(key="active_layer",  access=py_trees.common.Access.WRITE)
        self.bb.register_key(key="active_reason", access=py_trees.common.Access.WRITE)

        if reason_key is not None:
            self.bb.register_key(key=reason_key, access=py_trees.common.Access.READ)

    # ------------------------------------------------------------------
    # py_trees API
    # ------------------------------------------------------------------

    def update(self) -> py_trees.common.Status:
        # --- Build reason string ---
        reason_value = ""
        if self.reason_key is not None:
            try:
                val = self.bb.get(self.reason_key)
                reason_value = f" [{self.reason_label}={val}]"
            except KeyError:
                reason_value = f" [{self.reason_label}=<unset>]"

        layer_label = self._LAYER_LABELS.get(self.layer, self.layer)
        reason_str = f"{layer_label}{reason_value}"

        # --- Write to blackboard ---
        self.bb.active_layer = self.layer
        self.bb.active_reason = reason_str

        # --- Log only on transition ---
        if self.layer != self._prev_layer or reason_str != self._prev_reason:
            self.logger.info(
                f"[LayerTransition] {self._prev_layer or 'none'} → {self.layer} | {reason_str}"
            )
            self._prev_layer = self.layer
            self._prev_reason = reason_str

        return py_trees.common.Status.SUCCESS
