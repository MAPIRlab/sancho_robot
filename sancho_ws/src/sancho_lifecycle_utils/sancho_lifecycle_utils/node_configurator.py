#!/usr/bin/env python3
#
# node_configurator.py
#
# Nodo en Python para ROS 2 Humble que:
#  - Recibe, como parámetro, una lista de nombres de nodos lifecycle.
#  - Cada segundo revisa si la transición “configure” está disponible en cada uno,
#    y cuando lo esté, envía el ChangeState para configurarlo.
#  - Utiliza callbacks para todas las llamadas a servicio (sin spin_until_future_complete).
#  - Cuando todos los nodos estén configurados, se cierra automáticamente.

from functools import partial

import rclpy
from lifecycle_msgs.srv import ChangeState, GetAvailableTransitions
from rclpy.node import Node


class NodeConfigurator(Node):
    """
    NodeConfigurator for automatically transitioning ROS2 managed nodes to 'configured' state.

    This node takes a list of node names as a parameter and attempts to transition each of them
    to their 'configured' lifecycle state. It works by periodically:
    1. Querying each node's available transitions
    2. Finding the 'configure' transition ID when available
    3. Triggering the 'configure' transition
    4. Repeating until all nodes are successfully configured

    The node shuts down automatically once all target nodes have been successfully configured.

    Parameters:
    ----------
    node_names : list of str
        List of node names to configure. Each node must implement the lifecycle management
        services (get_available_transitions and change_state).

    Services Used:
    ------------
    For each node in node_names, the following services are called:
    - /{node_name}/get_available_transitions : Get available lifecycle transitions
    - /{node_name}/change_state : Trigger a lifecycle transition

    Behavior:
    --------
    - At initialization, all specified nodes are marked as pending configuration.
    - Every second, the node checks each pending node:
      - First, it queries available transitions to find the configure transition ID
      - Then it attempts to execute the configure transition when ready
      - Once a node is successfully configured, it is removed from the pending list
    - The node automatically shuts down when all nodes are configured.
    """
    def __init__(self):
        super().__init__("node_configurator")

        # 1) Declarar y obtener parámetro “node_names” (lista de cadenas)
        self.declare_parameter("node_names", ["placeholder"])
        param = self.get_parameter("node_names")
        self.node_names = list(param.get_parameter_value().string_array_value)

        # Limpia posibles 'placeholder' vacíos
        self.node_names = [n for n in self.node_names if n.strip() != ""]

        if not self.node_names:
            self.get_logger().error(
                'No se proporcionaron nodos válidos en "node_names".'
            )
            rclpy.shutdown()
            return

        # 2) Estructuras para manejar clientes de servicio y estados por nodo
        #    Para cada nodo, guardamos:
        #      - clients[node_name]['get_avail']   → cliente de GetAvailableTransitions
        #      - clients[node_name]['change']      → cliente de ChangeState
        #      - state flags:
        #           get_in_flight[node_name]        → bool
        #           pending_configure_id[node_name] → int | None
        #           change_in_flight[node_name]     → bool
        #           configured[node_name]           → bool
        self._node_clients = {}
        self.get_in_flight = {}
        self.pending_configure_id = {}
        self.change_in_flight = {}
        self.configured = {}

        for node_name in self.node_names:
            srv_get = f"/{node_name}/get_available_transitions"
            srv_chg = f"/{node_name}/change_state"

            cli_get = self.create_client(GetAvailableTransitions, srv_get)
            cli_chg = self.create_client(ChangeState, srv_chg)

            self._node_clients[node_name] = {"get_avail": cli_get, "change": cli_chg}
            # Flags iniciales:
            self.get_in_flight[node_name] = False
            self.pending_configure_id[node_name] = None
            self.change_in_flight[node_name] = False
            self.configured[node_name] = False

        # Conjunto de nodos que aún no están configurados:
        self._pending = set(self.node_names)

        # 3) Timer periódico cada 1 segundo:
        self._timer = self.create_timer(1.0, self._on_timer)
        self.get_logger().info(f"NodeConfigurator iniciado sobre: {self.node_names}")

    def _on_timer(self):
        """Cada segundo revisamos todos los nodos pendientes. Para cada nodo pendiente:
          A) Si no hay get_in_flight y no hemos identificado aún configure_id:
             - Si el servicio get_available_transitions está listo, enviamos la petición
               asíncrona y marcamos get_in_flight=True.
          B) Si ya tenemos pending_configure_id[node] != None (ya sabemos que existe la transición configure)
             y aún no hemos enviado el ChangeState (change_in_flight=False):
             - Si el servicio change_state está listo, enviamos la petición asíncrona de configure
               y marcamos change_in_flight=True.
        Cuando el conjunto _pending queda vacío, hacemos rclpy.shutdown().
        """
        if not self._pending:
            self.get_logger().info(
                "Todos los nodos han sido configurados. Finalizando node_configurator."
            )
            rclpy.shutdown()
            return

        for node_name in list(self._pending):
            # Si ya se configuró (por alguna razón adicional), lo saltamos
            if self.configured.get(node_name, False):
                continue

            cli_get = self._node_clients[node_name]["get_avail"]
            cli_chg = self._node_clients[node_name]["change"]

            # A) ¿Estamos a la espera de GetAvailableTransitions?
            if self.pending_configure_id[node_name] is None:
                if not self.get_in_flight[node_name]:
                    # Sólo enviamos la petición GET si el servicio está READY
                    if cli_get.service_is_ready():
                        self.get_logger().debug(
                            f"→ Solicitando transiciones de {node_name}"
                        )
                        req = GetAvailableTransitions.Request()
                        fut = cli_get.call_async(req)
                        # Asociamos callback parciales para saber de qué nodo viene
                        fut.add_done_callback(
                            partial(self._on_get_available, node_name)
                        )
                        self.get_in_flight[node_name] = True
                    else:
                        self.get_logger().debug(
                            f'Servicio "get_available_transitions" de {node_name} NO listo aún.'
                        )
                # Si get_in_flight = True → estamos esperando respuesta, nada más
                continue

            # B) Ya tenemos pending_configure_id[node_name] → enviamos ChangeState si no está en vuelo
            if (
                self.pending_configure_id[node_name] is not None
                and not self.change_in_flight[node_name]
            ):
                if cli_chg.service_is_ready():
                    tid = self.pending_configure_id[node_name]
                    self.get_logger().debug(
                        f"→ Solicitando ChangeState(configure={tid}) en {node_name}"
                    )
                    reqc = ChangeState.Request()
                    reqc.transition.id = tid
                    futc = cli_chg.call_async(reqc)
                    futc.add_done_callback(partial(self._on_change_state, node_name))
                    self.change_in_flight[node_name] = True
                else:
                    self.get_logger().debug(
                        f'Servicio "change_state" de {node_name} NO listo aún.'
                    )
                continue

    def _on_get_available(self, node_name, future):
        """Callback de ‘get_available_transitions’ para <node_name>.
        - Desmarca get_in_flight.
        - Si la respuesta contiene “configure” en available_transitions, guarda pending_configure_id[node_name].
        """
        self.get_in_flight[node_name] = False

        try:
            resp = future.result()
        except Exception as e:
            self.get_logger().warning(
                f"Error al llamar a GetAvailableTransitions en {node_name}: {e}"
            )
            return

        if resp is None:
            self.get_logger().warning(
                f"Respuesta nula de GetAvailableTransitions en {node_name}."
            )
            return

        # Buscar “configure” (puede venir como “configure” o “CONFIGURE”, etc.)
        found = False
        for t in resp.available_transitions:
            if t.transition.label.lower() == "configure":
                self.pending_configure_id[node_name] = t.transition.id
                self.get_logger().info(
                    f'→ Nodo "{node_name}" ofrece transition "configure" con id={t.transition.id}'
                )
                break

        if not found:
            self.get_logger().debug(
                f'El nodo "{node_name}" NO tiene todavía la transición "configure" disponible.'
            )
            # next timer tick volverá a preguntar

    def _on_change_state(self, node_name, future):
        """Callback de ‘change_state’ para <node_name>.
        - Desmarca change_in_flight.
        - Si resp.success == True, marca configurado y saca de _pending.
        - En caso contrario, deja pending_configure_id como estaba para reintentar.
        """
        self.change_in_flight[node_name] = False

        try:
            resp = future.result()
        except Exception as e:
            self.get_logger().warning(
                f"Error al llamar a ChangeState(configure) en {node_name}: {e}"
            )
            return

        if resp is None:
            self.get_logger().error(f"ChangeState devolvió None para {node_name}.")
            return

        if resp.success:
            self.get_logger().info(f'✔ Nodo "{node_name}" configurado EXITOSAMENTE.')
            self.configured[node_name] = True
            self._pending.discard(node_name)
        else:
            self.get_logger().error(
                f"Fallo al ejecutar ChangeState(configure) en {node_name}. Intentaremos de nuevo."
            )
            # dejamos pending_configure_id intacto para reintentar en el siguiente tick


def main(args=None):
    rclpy.init(args=args)
    node = NodeConfigurator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Interrumpido por usuario. Finalizando...")
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
