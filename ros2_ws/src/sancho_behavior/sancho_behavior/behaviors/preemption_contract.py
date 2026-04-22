import enum
from typing import Callable, Optional

import py_trees
from py_trees.behaviour import Behaviour
from py_trees.common import Status


class PreemptionState(enum.Enum):
    READY = "READY"
    RUNNING = "RUNNING"
    PREEMPTED = "PREEMPTED"
    RESUMED = "RESUMED"
    ABORTED = "ABORTED"


class WithPreemptionContract(py_trees.decorators.Decorator):
    """
    BTA-081: A standard preemption API for long-running subtrees.
    
    Wraps a behavior (usually a Sequence with memory=True).
    When the parent selector preempts this branch, it calls `.stop(Status.INVALID)`.
    This decorator intercepts that call, fires an `on_preempt` callback, and 
    records its state as PREEMPTED.
    
    On the next tick, if the state is PREEMPTED, it checks if it's resumable.
    If yes, it fires `on_resume` and continues ticking its child.
    If no, it fires `on_abort` and forces a FAILURE to break the sequence memory.
    """
    def __init__(
        self,
        child: Behaviour,
        name: str = "WithPreemptionContract",
        resumable: bool = True,
        on_preempt: Optional[Callable[[], None]] = None,
        on_resume: Optional[Callable[[], None]] = None,
        on_abort: Optional[Callable[[], None]] = None
    ):
        super().__init__(name=name, child=child)
        self.resumable = resumable
        self.cb_preempt = on_preempt
        self.cb_resume = on_resume
        self.cb_abort = on_abort
        
        self.preemption_state = PreemptionState.READY

    def initialise(self):
        """
        Called when the decorator transitions from not running to running.
        If we were previously preempted, this is a resume.
        """
        if self.preemption_state == PreemptionState.PREEMPTED:
            if self.resumable:
                print(f"[PREEMPTION_API] [{self.name}] Resuming after preemption.")
                self.preemption_state = PreemptionState.RESUMED
                if self.cb_resume:
                    self.cb_resume()
            else:
                print(f"[PREEMPTION_API] [{self.name}] Aborting. Non-resumable branch.")
                self.preemption_state = PreemptionState.ABORTED
                if self.cb_abort:
                    self.cb_abort()
        else:
            self.preemption_state = PreemptionState.RUNNING

    def update(self) -> Status:
        """
        Tick the child, unless we are aborting.
        """
        if self.preemption_state == PreemptionState.ABORTED:
            # We were preempted and cannot resume. We return FAILURE to break
            # the parent Sequence's memory and reset the branch.
            return Status.FAILURE
            
        return self.decorated.status

    def stop(self, new_status: Status):
        """
        Intercepts the stop signal from py_trees.
        If new_status == INVALID, it means we are being preempted by a higher priority.
        """
        print(f"[DEBUG] {self.name}.stop({new_status}) called. Current state: {self.preemption_state}")
        super().stop(new_status)
        
        # If interrupted by a higher priority branch (Status.INVALID)
        if new_status == Status.INVALID and self.preemption_state in (PreemptionState.RUNNING, PreemptionState.RESUMED):
            print(f"[PREEMPTION_API] [{self.name}] PREEMPTED by higher priority.")
            self.preemption_state = PreemptionState.PREEMPTED
            if self.cb_preempt:
                self.cb_preempt()
        elif new_status != Status.INVALID:
            # Normal completion (SUCCESS or FAILURE)
            self.preemption_state = PreemptionState.READY
