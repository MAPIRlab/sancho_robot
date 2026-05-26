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

        self.blackboard.register_key(
            "mission/request", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            "mission/status", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            "mission/status", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            "mission/feedback", access=py_trees.common.Access.READ
        )
        self.blackboard.register_key(
            "mission/active", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            "mission/type", access=py_trees.common.Access.WRITE
        )
        self.blackboard.register_key(
            "mission/cancel_requested", access=py_trees.common.Access.WRITE
        )

        self.mission_queue: list = []
        self.active_mission = None
        self.queue_lock = asyncio.Lock()

        # Latch de estado leído en cada update() del árbol
        self.latched_status = "IDLE"
        self.node = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self, **kwargs):
        self.node = kwargs.get("node")
        cb_group = ReentrantCallbackGroup()

        self.action_server = ActionServer(
            self.node,
            Mission,
            "mission_action",
            execute_callback=self.execute_callback,
            goal_callback=lambda request: GoalResponse.ACCEPT,
            cancel_callback=self.cancel_callback,
            callback_group=cb_group,
        )

        self.get_srv = self.node.create_service(
            GetMission, "/bt/get_mission", self.get_cb, callback_group=cb_group
        )
        self.pop_srv = self.node.create_service(
            Trigger, "/bt/pop_mission", self.pop_cb, callback_group=cb_group
        )
        self.clear_srv = self.node.create_service(
            Trigger, "/bt/clear_missions", self.clear_cb, callback_group=cb_group
        )

        self.logger.debug(f"[{self.name}] Priority Action Server initialized.")

    # ------------------------------------------------------------------
    # ROS 2 cancel callback (cliente externo usa el protocolo de acción)
    # ------------------------------------------------------------------

    def cancel_callback(self, cancel_request):
        """
        Acepta cancelaciones provenientes del cliente de la acción.
        También señaliza cancel_event para que update() lo propague
        al BB de forma síncrona (misma ruta que pop/clear).
        """
        self.node.get_logger().info("Received ROS 2 cancel request for mission.")
        if self.active_mission:
            self.active_mission["cancel_event"].set()
        return CancelResponse.ACCEPT

    # ------------------------------------------------------------------
    # Service callbacks
    # ------------------------------------------------------------------

    async def get_cb(self, request, response):
        async with self.queue_lock:
            response.success = True
            if self.active_mission:
                response.mission_type = self.active_mission["request"].mission_type
                response.json_parameters = json.dumps(
                    self.active_mission["params"]
                )
                response.status = "RUNNING"
                response.message = f"Queue length: {len(self.mission_queue)}"
            else:
                response.mission_type = "none"
                response.json_parameters = "{}"
                response.status = "IDLE"
                response.message = "Queue is empty."
        return response

    async def pop_cb(self, request, response):
        """
        Cancela la misión activa señalizando su cancel_event.
        El update() síncrono del BT detecta la señal en el siguiente tick
        y propaga mission/cancel_requested al blackboard.
        """
        async with self.queue_lock:
            if self.active_mission:
                self.active_mission["cancel_event"].set()
                response.success = True
                response.message = (
                    "Pop requested: active mission will cancel shortly."
                )
            else:
                response.success = False
                response.message = "Nothing to pop."
        return response

    async def clear_cb(self, request, response):
        """
        Cancela la misión activa Y todas las misiones en cola señalizando
        sus respectivos cancel_event.  La cola se vacía aquí mismo; cada
        execute_callback en espera de cola detectará la señal y retornará.
        """
        async with self.queue_lock:
            # Señalizar y vaciar la cola primero
            for mission in self.mission_queue:
                mission["cancel_event"].set()
            self.mission_queue.clear()

            # Señalizar la misión activa
            if self.active_mission:
                self.active_mission["cancel_event"].set()

            response.success = True
            response.message = "Clear requested: all missions will cancel shortly."
        return response

    # ------------------------------------------------------------------
    # Action execute callback
    # ------------------------------------------------------------------

    async def execute_callback(self, goal_handle):
        request = goal_handle.request

        priority = 5
        params = {}
        if request.json_parameters:
            try:
                params = json.loads(request.json_parameters)
                priority = int(params.get("priority", 5))
            except json.JSONDecodeError:
                self.node.get_logger().error(
                    "Invalid JSON in mission request. Using default priority."
                )

        # Cada misión lleva su propio evento de cancelación interna
        cancel_event = asyncio.Event()
        # Evento para despertar execute_callback cuando update() latchea terminal
        done_event = asyncio.Event()

        mission_record = {
            "handle": goal_handle,
            "priority": priority,
            "params": params,
            "request": request,
            "cancel_event": cancel_event,
            "done_event": done_event,
        }

        async with self.queue_lock:
            if self.active_mission is None:
                self.active_mission = mission_record
                self.node.get_logger().info(
                    f"Starting new mission. Priority: {priority}"
                )
            elif self.active_mission["cancel_event"].is_set():
                # Active mission is already cancelled (zombie) — replace directly
                self.node.get_logger().info(
                    f"Replacing cancelled mission with new mission."
                    f" Priority: {priority}"
                )
                self.active_mission = mission_record
            else:
                if priority <= self.active_mission["priority"]:
                    self.node.get_logger().info(
                        f"Preempting priority {self.active_mission['priority']}"
                        f" with priority {priority}"
                    )
                    self.mission_queue.append(self.active_mission)
                    self.active_mission = mission_record
                else:
                    self.node.get_logger().info(
                        f"Enqueueing mission. Priority: {priority}"
                    )
                    self.mission_queue.append(mission_record)
                self.mission_queue.sort(key=lambda x: x["priority"])

        result = Mission.Result()

        # Flag para no escribir en el BB más de una vez por activación
        has_written_to_bb = False

        while goal_handle.is_active:

            # ── 1. Cancelación interna (pop_cb / clear_cb) ──────────────
            if cancel_event.is_set():
                self.node.get_logger().info(
                    f"Mission priority {priority}: internal cancel signal received."
                )
                if goal_handle.is_active:
                    goal_handle.canceled()
                result.success = False
                result.final_message = "Cancelled (internal pop/clear)"
                await self._handle_cancellation(mission_record)
                return result

            # ── 2. Cancelación externa (cliente ROS 2) ──────────────────
            if goal_handle.is_cancel_requested:
                self.node.get_logger().info(
                    f"Mission priority {priority}: ROS 2 cancel request received."
                )
                goal_handle.canceled()
                result.success = False
                result.final_message = "Cancelled (ROS 2 client request)"
                await self._handle_cancellation(mission_record)
                return result

            # ── 3. Misión en cola, aún no es la activa ──────────────────
            if self.active_mission != mission_record:
                has_written_to_bb = False
                fb = Mission.Feedback()
                fb.current_state = f"Queued (Priority {priority})"
                goal_handle.publish_feedback(fb)
                await asyncio.sleep(0.5)
                continue

            # ── 4. Misión activa: escribir en el BB una sola vez ────────
            if not has_written_to_bb:
                self._write_to_blackboard(mission_record)
                has_written_to_bb = True

            # ── 5. Publicar feedback y comprobar resultado del árbol ────
            status = self.latched_status

            fb = Mission.Feedback()
            try:
                fb.current_state = str(self.blackboard.get("mission/feedback"))
            except KeyError:
                fb.current_state = f"Running (Priority {priority})"
            goal_handle.publish_feedback(fb)

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

            # Wait for done_event (set by update() on terminal latch)
            # or timeout after 100ms to check cancel/queue changes
            try:
                await asyncio.wait_for(
                    mission_record["done_event"].wait(), timeout=0.1
                )
            except asyncio.TimeoutError:
                pass

        # El handle dejó de estar activo por motivos externos
        self.node.get_logger().warn(
            f"Mission priority {priority}: exited loop with inactive handle."
        )
        await self._handle_cancellation(mission_record)
        result.success = False
        result.final_message = "Cancelled (handle became inactive)"
        return result

    # ------------------------------------------------------------------
    # Blackboard helpers
    # ------------------------------------------------------------------

    def _write_to_blackboard(self, mission_record):
        req = mission_record["request"]
        params = mission_record["params"]

        self.latched_status = "RUNNING"
        self.blackboard.set("mission/request", req.mission_type)
        self.blackboard.set("mission/status", "RUNNING")
        self.blackboard.set("mission/type", req.mission_type)
        self.blackboard.set("mission/active", True)
        self.blackboard.set("mission/cancel_requested", False)

        for key, value in params.items():
            if key != "priority":
                bb_key = f"mission/{key}"
                self.blackboard.register_key(
                    key=bb_key, access=py_trees.common.Access.WRITE
                )
                self.blackboard.set(bb_key, value)

    def _clear_blackboard(self):
        self.blackboard.set("mission/request", "idle")
        self.blackboard.set("mission/status", "IDLE")
        self.blackboard.set("mission/type", "")
        self.blackboard.set("mission/active", False)
        self.blackboard.set("mission/cancel_requested", False)
        self.latched_status = "IDLE"

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def _promote_next_mission_helper(self):
        """Promueve la siguiente misión de la cola. Debe llamarse bajo queue_lock."""
        self._clear_blackboard()
        if self.mission_queue:
            self.active_mission = self.mission_queue.pop(0)
            self.node.get_logger().info(
                f"Promoting queued mission."
                f" Priority {self.active_mission['priority']}"
            )
        else:
            self.active_mission = None

    async def _promote_next_mission(self):
        async with self.queue_lock:
            self._promote_next_mission_helper()

    async def _handle_cancellation(self, mission_record):
        """
        Limpia la referencia a mission_record tanto si era la activa
        como si seguía en cola, y promueve la siguiente si procede.
        No llama a goal_handle.canceled(): eso ya lo hace el execute_callback
        antes de invocar este método.
        """
        async with self.queue_lock:
            if self.active_mission == mission_record:
                self._promote_next_mission_helper()
            elif mission_record in self.mission_queue:
                self.mission_queue.remove(mission_record)

    # ------------------------------------------------------------------
    # py_trees update  (tick síncrono del árbol)
    # ------------------------------------------------------------------

    def update(self):
        """
        Se ejecuta en cada tick del árbol de comportamiento.

        1. Si la misión activa tiene cancel_event activado, propaga la señal
           de cancelación al blackboard (mission/cancel_requested=True) para
           que el MissionCancelGuard del BT la detecte en este mismo tick.
        2. Atrapa el estado SUCCESS / FAILURE escrito por MissionStatusTracker
           en el BB y lo almacena en latched_status para que el
           execute_callback asíncrono lo pueda leer de forma segura.
        """
        # ── Propagación síncrona de cancelación ─────────────────────────
        # Señalizamos cancel_requested Y cortamos la admisión (active=False,
        # request=idle) para que MissionAdmissionGate bloquee L3 de
        # inmediato.  NO tocamos mission/status aquí: MissionStatusTracker
        # es idempotente y no sobreescribirá un SUCCESS previo.
        # La limpieza final del BB la hace execute_callback →
        # _handle_cancellation() → _clear_blackboard().
        if self.active_mission and self.active_mission["cancel_event"].is_set():
            self.node.get_logger().info(
                "[MissionActionServer] cancel_event detected in update()."
                " Blocking L3 admission and setting cancel flag."
            )
            self.blackboard.set("mission/cancel_requested", True)
            self.blackboard.set("mission/active", False)
            self.blackboard.set("mission/request", "idle")
            self.blackboard.set("mission/type", "")

        # ── Latch de estado terminal ────────────────────────────────────
        # Cuando MissionStatusTracker escribe SUCCESS o FAILURE en el BB,
        # lo latcheamos para execute_callback Y cortamos la admisión para
        # evitar que el BT re-entre en la misión antes de que
        # execute_callback llame a _clear_blackboard().
        # Es seguro poner active=False porque MissionStatusTracker ya es
        # idempotente: no sobreescribirá un SUCCESS/FAILURE latched.
        try:
            current_status = self.blackboard.get("mission/status")
            if current_status in ("SUCCESS", "FAILURE"):
                self.latched_status = current_status
                # Cortar admisión para evitar re-entrada
                self.blackboard.set("mission/active", False)
                self.blackboard.set("mission/request", "idle")
                self.blackboard.set("mission/type", "")
                self.blackboard.set("mission/cancel_requested", False)
                # Despertar execute_callback para que procese el resultado
                if self.active_mission:
                    self.active_mission["done_event"].set()
        except KeyError:
            pass

        return py_trees.common.Status.SUCCESS