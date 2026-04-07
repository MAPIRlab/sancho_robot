import rclpy
from rclpy.qos import QoSProfile

import py_trees
import py_trees_ros
from py_trees.blackboard import Client

from std_msgs.msg import Float32

# Importamos nuestro subárbol personalizado
from trees.react_to_sound_tree import create_subtree


def create_root() -> py_trees.behaviour.Behaviour:
    """Crea el árbol de comportamiento principal del robot Sancho."""
    
    # 1. Raíz Principal: Ejecuta en paralelo sensores y decisiones
    # Usamos SuccessOnAll(synchronise=False) para no detener la ejecución
    root = py_trees.composites.Parallel(
        name="SanchoRoot", 
        policy=py_trees.common.ParallelPolicy.SuccessOnAll(synchronise=False)
    )

    # ==========================================
    # RAMA 1: Recolección continua de datos
    # ==========================================
    topics_parallel = py_trees.composites.Parallel(
        name="TopicsParallel",
        policy=py_trees.common.ParallelPolicy.SuccessOnAll()
    )

    # Envolvemos en SuccessIsRunning para que la recolección nunca termine (evita el reseteo de topics)
    topics2bb = py_trees.decorators.SuccessIsRunning(
        name="Topics2BB", 
        child=topics_parallel
    )

    # Suscriptor para la dirección de llegada del sonido (DoA)
    doa2bb = py_trees_ros.subscribers.ToBlackboard(
        name="DoA2BB",
        topic_name="/sancho_audio/doa",
        topic_type=Float32,
        qos_profile=QoSProfile(depth=10),
        blackboard_variables={"last_angle": "data"}
    )
    
    # Suscriptor para la palabra de activación (Hotword)
    hotword2bb = py_trees_ros.subscribers.EventToBlackboard(
        name="Hotword2BB",
        topic_name="/voice_events/hotword_detected",
        variable_name="hotword_event",
        qos_profile=QoSProfile(depth=10)
    )

    topics_parallel.add_children([doa2bb, hotword2bb])

    # ==========================================
    # RAMA 2: El Cerebro (Toma de decisiones)
    # ==========================================
    # Selector sin memoria que evalúa prioridades de arriba a abajo
    brain = py_trees.composites.Selector(name="Brain", memory=False)
    
    # Tarea de Prioridad 1: Orientarse al sonido (Nuestro subárbol)
    orientate_behavior = create_subtree()
    
    # Tarea Base/Prioridad mínima: Reposo (Mantiene el árbol en RUNNING si no hay nada más que hacer)
    idle = py_trees.behaviours.Running(name="Idle")

    brain.add_children([orientate_behavior, idle])

    # ==========================================
    # Montaje final del árbol principal
    # ==========================================
    root.add_children([topics2bb, brain])
    
    return root


def main():
    rclpy.init()

    # Inicializamos de forma segura la pizarra si lo necesitamos (opcional, pero buena práctica)
    # Los suscriptores escribirán aquí automáticamente, pero podemos inicializar valores por defecto.
    blackboard = Client(name="MainInit")
    blackboard.register_key(key="hotword_event", access=py_trees.common.Access.WRITE)
    blackboard.hotword_event = False

    # Creamos la raíz del árbol
    root = create_root()
    
    # Inicializamos el envoltorio de ROS 2 para el árbol
    tree = py_trees_ros.trees.BehaviourTree(
        root=root, 
        unicode_tree_debug=True
    )
    
    # Añadimos el visitante para debugear la pizarra y el árbol visualmente en la consola
    tree.visitors.append(py_trees.visitors.DisplaySnapshotVisitor(display_blackboard=True))

    try:
        # Setup del árbol (asigna el nodo de ROS subyacente, conecta action clients, etc.)
        tree.setup(timeout=15.0)
        print("\n--- Árbol de comportamiento principal de Sancho inicializado correctamente ---")
        
        # Comenzamos la ejecución periódica a 10 Hz (100 ms de ciclo)
        tree.tick_tock(period_ms=100)

        # Mantenemos vivo el nodo para que se procesen los callbacks de ROS 2
        rclpy.spin(tree.node)
        
    except (KeyboardInterrupt, py_trees_ros.exceptions.NotReadyError):
        print("\nDeteniendo la ejecución del árbol de comportamiento...")
    finally:
        tree.shutdown()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()