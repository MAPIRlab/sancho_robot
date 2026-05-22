import py_trees
import os
# Importa la función que crea el árbol completo
from sancho_behavior.trees.main_tree import create_root 

def main():
    print("Instanciando el árbol...")
    root = create_root() 
    
    print("Generando gráficos...")
    # Esta es la función correcta en py_trees (v2.x / ROS 2)
    py_trees.display.render_dot_tree(
        root,
        name="full_sancho_tree",      # Nombre base para los archivos
        target_directory=os.getcwd()  # Guarda en la carpeta desde donde ejecutes el script
    )
    
    print(f"¡Éxito! Revisa la carpeta {os.getcwd()}")
    print("Deberías ver 'full_sancho_tree.dot' y 'full_sancho_tree.svg'")

if __name__ == "__main__":
    main()