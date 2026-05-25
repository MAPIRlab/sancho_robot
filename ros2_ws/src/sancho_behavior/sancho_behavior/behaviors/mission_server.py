import rclpy
import py_trees
import json
import asyncio
from rclpy.action import ActionServer, GoalResponse, CancelResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from sancho_interfaces.srv import GetMission
from sancho_interfaces.action import Mission
from std_srvs.srv import Trigger

class MissionActionServer(py_trees.behaviour.Behaviour):
    def __init__(self, name="MissionActionServer", action_name="mission_action"):
        super().__init__(name)
        self.action_name = action_name
        self.blackboard = py_trees.blackboard.Client(name=name)
        
        self.blackboard.register_key("mission/request", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("mission/status", access=py_trees.common.Access.READ)
        self.blackboard.register_key("mission/status", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("mission/feedback", access=py_trees.common.Access.READ)

        # Queue Management
        self.mission_queue = []       # List of queued mission records
        self.active_mission = None    # The currently running mission record
        self.queue_lock = asyncio.Lock() # Prevents race conditions when modifying the queue

        self.node = None

    def setup(self, **kwargs):
        self.node = kwargs.get('node')
        cb_group = ReentrantCallbackGroup()
        # 1. Action Server (Receives missions)
        self.action_server = ActionServer(
            self.node, Mission, "mission_action",
            execute_callback=self.execute_callback,
            goal_callback=lambda request: GoalResponse.ACCEPT,
            cancel_callback=lambda handle: CancelResponse.ACCEPT,
            callback_group=cb_group
        )

        # 2. Srv Server (Legacy compatibility for MCP)
        self.get_srv = self.node.create_service(GetMission, "/bt/get_mission", self.get_cb, callback_group=cb_group)
        self.pop_srv = self.node.create_service(Trigger, "/bt/pop_mission", self.pop_cb, callback_group=cb_group)
        self.clear_srv = self.node.create_service(Trigger, "/bt/clear_missions", self.clear_cb, callback_group=cb_group)

        self.logger.debug(f"[{self.name}] Priority Action Server initialized.")

    async def get_cb(self, request, response):
        """AI asks: What are you doing?"""
        async with self.queue_lock:
            response.success = True
            if self.active_mission:
                response.mission_type = self.active_mission['request'].mission_type
                response.json_parameters = json.dumps(self.active_mission['params'])
                response.status = "RUNNING"
                response.message = f"Queue length: {len(self.mission_queue)}"
            else:
                response.mission_type = "none"
                response.json_parameters = "{}"
                response.status = "IDLE"
                response.message = "Queue is empty."
        return response

    async def pop_cb(self, request, response):
        """AI says: Skip the current task."""
        async with self.queue_lock:
            if self.active_mission:
                self.active_mission['handle'].canceled() # Abort current goal
                # execute_callback will naturally catch this and promote the next queue item
                response.success = True
                response.message = "Popped active mission."
            else:
                response.success = False
                response.message = "Nothing to pop."
        return response

    async def clear_cb(self, request, response):
        """AI says: Stop everything, wipe the queue."""
        async with self.queue_lock:
            self.mission_queue.clear() # 1. Delete all waiting tasks
            if self.active_mission:
                self.active_mission['handle'].canceled() # 2. Kill the active one
            response.success = True
            response.message = "All missions cleared."
        return response

    async def execute_callback(self, goal_handle):
        request = goal_handle.request
        
        # 1. Parse Priority (Default to 5 if not provided)
        priority = 5
        params = {}
        if request.json_parameters:
            try:
                params = json.loads(request.json_parameters)
                priority = int(params.get("priority", 5))
            except json.JSONDecodeError:
                self.node.get_logger().error("Invalid JSON. Using default priority.")
        
        # Create a record for this mission
        mission_record = {
            'handle': goal_handle,
            'priority': priority,
            'params': params,
            'request': request
        }
        
        # 2. Queue Logic
        async with self.queue_lock:
            if self.active_mission is None:
                # Track is clear, start immediately
                self.active_mission = mission_record
                self.node.get_logger().info(f"Starting new mission. Priority: {priority}")
            else:
                if priority < self.active_mission['priority']:
                    # PREEMPTION: New mission has higher priority (lower number)
                    self.node.get_logger().info(f"Preempting priority {self.active_mission['priority']} for priority {priority}")
                    # Push currently active mission back into the queue
                    self.mission_queue.append(self.active_mission)
                    # Take control
                    self.active_mission = mission_record
                else:
                    # ENQUEUE: Equal or lower priority (higher number) waits in line
                    self.node.get_logger().info(f"Enqueueing mission. Priority: {priority}")
                    self.mission_queue.append(mission_record)
                
                # Always keep queue sorted by priority (lowest number first)
                self.mission_queue.sort(key=lambda x: x['priority'])

        result = Mission.Result()

        # 3. Execution & Wait Loop
        while goal_handle.is_active:
            # Handle cancellation
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                await self._handle_cancellation(mission_record)
                result.success = False
                result.final_message = "Cancelled"
                return result

            # STATE A: We are queued. Wait in the background.
            if self.active_mission != mission_record:
                fb = Mission.Feedback()
                fb.current_state = f"Queued... (Priority {priority})"
                goal_handle.publish_feedback(fb)
                await asyncio.sleep(0.5)
                continue

            # STATE B: We are active. Ensure Blackboard has our data.
            current_bb_req = self.blackboard.get("mission/request")
            if current_bb_req != request.mission_type:
                self._write_to_blackboard(mission_record)

            # Check tree status
            status = self.blackboard.get("mission/status")
            fb = Mission.Feedback()
            fb.current_state = str(self.blackboard.get("mission/feedback"))
            goal_handle.publish_feedback(fb)

            # Completion criteria
            if status == "SUCCESS":
                goal_handle.succeed()
                result.success = True
                result.final_message = "Mission completed successfully"
                await self._promote_next_mission()
                return result
            elif status == "FAILURE":
                goal_handle.abort()
                result.success = False
                result.final_message = "Mission failed"
                await self._promote_next_mission()
                return result

            await asyncio.sleep(0.1)

    def _write_to_blackboard(self, mission_record):
        """Injects this mission's payload into the Blackboard."""
        req = mission_record['request']
        params = mission_record['params']
        
        self.blackboard.set("mission/request", req.mission_type)
        self.blackboard.set("mission/status", "RUNNING")
        
        for key, value in params.items():
            if key != "priority":
                bb_key = f"mission/{key}"
                self.blackboard.register_key(key=bb_key, access=py_trees.common.Access.WRITE)
                self.blackboard.set(bb_key, value)

    async def _promote_next_mission(self):
        """Pulls the next mission from the queue and activates it."""
        async with self.queue_lock:
            self._clear_blackboard()
            if self.mission_queue:
                self.active_mission = self.mission_queue.pop(0)
                self.node.get_logger().info(f"Resuming queued mission. Priority {self.active_mission['priority']}")
            else:
                self.active_mission = None

    async def _handle_cancellation(self, mission_record):
        """Cleans up if a mission is cancelled manually via CLI/LLM."""
        async with self.queue_lock:
            if self.active_mission == mission_record:
                await self._promote_next_mission()
            elif mission_record in self.mission_queue:
                self.mission_queue.remove(mission_record)

    def _clear_blackboard(self):
        self.blackboard.set("mission/request", "idle")
        self.blackboard.set("mission/status", "IDLE")

    def update(self):
        return py_trees.common.Status.SUCCESS