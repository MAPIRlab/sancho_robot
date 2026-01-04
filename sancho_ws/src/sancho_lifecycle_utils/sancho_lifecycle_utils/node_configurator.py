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
        self.declare_parameter("activate", False)
        self.should_activate = self.get_parameter("activate").value 
        param = self.get_parameter("node_names")
        
        self.node_names = list(param.get_parameter_value().string_array_value)
        
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
        #           pending_activate_id[node_name]  → int | None
        #           change_in_flight[node_name]     → bool
        #           configured[node_name]           → bool
        #           activated[node_name]           → bool
        self._node_clients = {}
        self.get_in_flight = {}
        self.pending_configure_id = {}
        self.pending_activate_id = {}
        self.change_in_flight = {}
        self.configured = {}
        self.activated = {}

        for node_name in self.node_names:
            srv_get = f"/{node_name}/get_available_transitions"
            srv_chg = f"/{node_name}/change_state"

            cli_get = self.create_client(GetAvailableTransitions, srv_get)
            cli_chg = self.create_client(ChangeState, srv_chg)

            self._node_clients[node_name] = {"get_avail": cli_get, "change": cli_chg}
            # Flags iniciales:
            self.get_in_flight[node_name] = False
            self.pending_configure_id[node_name] = None
            self.pending_activate_id[node_name] = None
            self.change_in_flight[node_name] = False
            self.configured[node_name] = False
            self.activated[node_name] = False

        # Conjunto de nodos que aún no están configurados:
        self._pending = set(self.node_names)

        # 3) Timer periódico cada 1 segundo:
        self._timer = self.create_timer(1.0, self._on_timer)
        self.get_logger().info(f"NodeConfigurator iniciado sobre: {self.node_names}")

    def _on_timer(self):
        """Cada segundo revisamos todos los nodos pendientes. Para cada nodo pendiente:
          A) Si no hay get_in_flight y no hemos identificado aún configure_id o activate_id:
             - Si el servicio get_available_transitions está listo, enviamos la petición
               asíncrona y marcamos get_in_flight=True.
          B) Si ya tenemos pending_configure_id[node] != None y aún no hemos enviado el ChangeState:
             - Si el servicio change_state está listo, enviamos la petición asíncrona de configure.
          C) Si self.should_activate=True, el nodo está configurado y tenemos pending_activate_id:
             - Si el servicio change_state está listo, enviamos la petición asíncrona de activate.
        Cuando el conjunto _pending queda vacío y no hay activaciones pendientes, hacemos shutdown.
        """
        # Si no hay nodos pendientes y no queremos activar o todos están activados, terminamos
        all_done = not self._pending and (not self.should_activate or all(
            self.activated[node] for node in self.node_names
        ))
        
        if all_done:
            self.get_logger().info(
                "Todos los nodos han sido configurados" +
                (" y activados" if self.should_activate else "") +
                ". Finalizando node_configurator."
            )
            rclpy.shutdown()
            return

        for node_name in list(self._pending):

            cli_get = self._node_clients[node_name]["get_avail"]
            cli_chg = self._node_clients[node_name]["change"]

            # Flujo 1: CONFIGURE
            if not self.configured[node_name]:
                # A) ¿Necesitamos descubrir id de "configure"?
                if self.pending_configure_id[node_name] is None:
                    if not self.get_in_flight[node_name]:
                        if cli_get.service_is_ready():
                            self.get_logger().debug(
                                f"→ Solicitando transiciones de {node_name} (buscar 'configure')"
                            )
                            req = GetAvailableTransitions.Request()
                            fut = cli_get.call_async(req)
                            fut.add_done_callback(partial(self._on_get_available, node_name))
                            self.get_in_flight[node_name] = True
                        else:
                            self.get_logger().debug(
                                f'Servicio "get_available_transitions" de {node_name} NO listo aún.'
                            )
                    # Esperando respuesta de GET
                else:
                    # B) Ya tenemos id de configure → ejecutar ChangeState
                    if not self.change_in_flight[node_name]:
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
                # Pasamos al siguiente nodo
                continue

            # Flujo 2: ACTIVATE (sólo si se ha pedido activar y aún no está activado)
            if self.should_activate and not self.activated[node_name]:
                # C) ¿Necesitamos descubrir id de "activate"?
                if self.pending_activate_id[node_name] is None:
                    if not self.get_in_flight[node_name]:
                        if cli_get.service_is_ready():
                            self.get_logger().debug(
                                f"→ Solicitando transiciones de {node_name} (buscar 'activate')"
                            )
                            req = GetAvailableTransitions.Request()
                            fut = cli_get.call_async(req)
                            fut.add_done_callback(partial(self._on_get_available, node_name))
                            self.get_in_flight[node_name] = True
                        else:
                            self.get_logger().debug(
                                f'Servicio "get_available_transitions" de {node_name} NO listo aún.'
                            )
                else:
                    # D) Ya tenemos id de activate → ejecutar ChangeState
                    if not self.change_in_flight[node_name]:
                        if cli_chg.service_is_ready():
                            tid = self.pending_activate_id[node_name]
                            self.get_logger().debug(
                                f"→ Solicitando ChangeState(activate={tid}) en {node_name}"
                            )
                            reqa = ChangeState.Request()
                            reqa.transition.id = tid
                            futa = cli_chg.call_async(reqa)
                            futa.add_done_callback(partial(self._on_change_state, node_name))
                            self.change_in_flight[node_name] = True
                        else:
                            self.get_logger().debug(
                                f'Servicio "change_state" de {node_name} NO listo aún.'
                            )
                continue

    def _on_get_available(self, node_name, future):
        """Callback de ‘get_available_transitions’ para <node_name>.
        - Desmarca get_in_flight.
        - Según el estado del nodo:
            • Si no está configurado: busca “configure” y guarda pending_configure_id[node_name].
            • Si hay que activar y no está activado: busca “activate” y guarda pending_activate_id[node_name].
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

        # Determinar qué transición necesitamos ahora
        need_configure = not self.configured[node_name]
        need_activate = (self.should_activate and self.configured[node_name] and not self.activated[node_name])

        if need_configure:
            found = False
            for t in resp.available_transitions:
                if t.transition.label.lower() == "configure":
                    self.pending_configure_id[node_name] = t.transition.id
                    self.get_logger().info(
                        f'→ Nodo "{node_name}" ofrece transition "configure" con id={t.transition.id}'
                    )
                    found = True
                    break
            if not found:
                self.get_logger().debug(
                    f'El nodo "{node_name}" NO tiene todavía la transición "configure" disponible.'
                )
            return

        if need_activate:
            found = False
            for t in resp.available_transitions:
                if t.transition.label.lower() == "activate":
                    self.pending_activate_id[node_name] = t.transition.id
                    self.get_logger().info(
                        f'→ Nodo "{node_name}" ofrece transition "activate" con id={t.transition.id}'
                    )
                    found = True
                    break
            if not found:
                self.get_logger().debug(
                    f'El nodo "{node_name}" NO tiene todavía la transición "activate" disponible.'
                )
            return

    def _on_change_state(self, node_name, future):
        """Callback de 'change_state' para <node_name>.
        - Desmarca change_in_flight.
        - Si resp.success == True, marca configurado/activado según corresponda.
        - En caso contrario, deja pending_*_id como estaba para reintentar.
        """
        self.change_in_flight[node_name] = False

        try:
            resp = future.result()
        except Exception as e:
            self.get_logger().warning(
                f"Error al llamar a ChangeState en {node_name}: {e}"
            )
            return

        if resp is None:
            self.get_logger().error(f"ChangeState devolvió None para {node_name}.")
            return

        if resp.success:
            if self.pending_configure_id[node_name] is not None:
                self.get_logger().info(f'✔ Nodo "{node_name}" configurado EXITOSAMENTE.')
                self.configured[node_name] = True
                self.pending_configure_id[node_name] = None
                if not self.should_activate:
                    self._pending.discard(node_name)
            elif self.pending_activate_id[node_name] is not None:
                self.get_logger().info(f'✔ Nodo "{node_name}" activado EXITOSAMENTE.')
                self.activated[node_name] = True
                self.pending_activate_id[node_name] = None
                self._pending.discard(node_name)
        else:
            action = "configure" if self.pending_configure_id[node_name] is not None else "activate"
            self.get_logger().error(
                f"Fallo al ejecutar ChangeState({action}) en {node_name}. Intentaremos de nuevo."
            )
            # dejamos pending_*_id intacto para reintentar en el siguiente tick


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
