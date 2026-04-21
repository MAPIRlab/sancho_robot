import sys
import os
import importlib
import py_trees

def render_custom_tree(file_path):
    # 1. Clean up the input path
    module_name = os.path.basename(file_path).replace(".py", "")
    module_dir = os.path.dirname(os.path.abspath(file_path))
    
    # 2. Add the file's directory to sys.path so we can find it
    sys.path.append(module_dir)
    sys.path.append(os.getcwd())

    print(f"--- Attempting to render tree from: {module_name}.py ---")

    try:
        # 3. Dynamic Import
        module = importlib.import_module(module_name)
        
        if hasattr(module, 'create_root'):
            root = module.create_root()
        else:
            print(f"Error: The file '{module_name}.py' does not have a 'create_root()' function.")
            return

        # 4. Generate the Visualization
        output_name = f"Render_{module_name}"
        py_trees.display.render_dot_tree(
            root, 
            name=output_name, 
            target_directory=".",
            with_blackboard_variables=False
        )

        print(f"Success! Architecture saved as '{output_name}.svg'")
        print(f"You can also find the raw graph logic in '{output_name}.dot'")

    except Exception as e:
        print(f"Failed to render tree: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 render_tree.py <your_tree_file.py>")
    else:
        render_custom_tree(sys.argv[1])