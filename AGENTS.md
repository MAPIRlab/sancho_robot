# AGENTS.md

This file helps coding agents be productive in this repository.
Primary focus: `ros2_ws/src/sancho_behavior` and `ros2_ws/src/sancho_interfaces`.

## Read First

- Main project map: [README.md](README.md)
- ROS 2 workspace setup and build flow: [ros2_ws/README.md](ros2_ws/README.md)
- Behavior package API and launch files: [ros2_ws/src/sancho_behavior/README.md](ros2_ws/src/sancho_behavior/README.md)
- Interface catalog (msgs/srvs/actions): [ros2_ws/src/sancho_interfaces/README.md](ros2_ws/src/sancho_interfaces/README.md)
- Execution backlog for BT priority architecture: [ros2_ws/src/sancho_behavior/BACKLOG_BT_PRIORIDADES.md](ros2_ws/src/sancho_behavior/BACKLOG_BT_PRIORIDADES.md)

Do not duplicate those docs in PRs or generated explanations. Link to them.

## Scope And Boundaries

- `sancho_behavior` is an `ament_python` package with BT orchestration and interaction nodes.
- `sancho_interfaces` is an `ament_cmake` ROSIDL package that generates shared message/service/action contracts.
- `sancho_behavior` depends on `sancho_interfaces`; changes to interfaces often require rebuilding consumers.

## Fast Working Commands

Run commands from `ros2_ws/`.

```bash
source /opt/ros/humble/setup.bash

# Build interfaces and behavior in dependency order
colcon build --symlink-install --packages-select sancho_interfaces sancho_behavior

# Source overlay for runtime
source install/setup.bash

# Run core behavior executables
ros2 run sancho_behavior sancho_behavior_tree
ros2 run sancho_behavior interaction_manager_node
ros2 run sancho_behavior attention_manager_node

# Launch interaction stack
ros2 launch sancho_behavior sancho_interaction.launch.py
```

## Where To Edit

- Add or change interfaces in:
  - `ros2_ws/src/sancho_interfaces/msg`
  - `ros2_ws/src/sancho_interfaces/srv`
  - `ros2_ws/src/sancho_interfaces/action`
  - And register them in [ros2_ws/src/sancho_interfaces/CMakeLists.txt](ros2_ws/src/sancho_interfaces/CMakeLists.txt)
- Add behavior logic in:
  - `ros2_ws/src/sancho_behavior/sancho_behavior/trees`
  - `ros2_ws/src/sancho_behavior/sancho_behavior/behaviors`
  - `ros2_ws/src/sancho_behavior/sancho_behavior/interaction`
- If you add a new executable node, update [ros2_ws/src/sancho_behavior/setup.py](ros2_ws/src/sancho_behavior/setup.py) `console_scripts`.

## Conventions To Preserve

- Python style is defined in [ros2_ws/pyproject.toml](ros2_ws/pyproject.toml): black + ruff, line length 88, target py310.
- Keep module filenames in snake_case.
- Keep interface filenames in PascalCase to match existing ROS interface naming.
- Prefer small, composable BT behaviors instead of monolithic nodes.

## High-Value Files For Orientation

- [ros2_ws/src/sancho_behavior/sancho_behavior/trees/main_tree.py](ros2_ws/src/sancho_behavior/sancho_behavior/trees/main_tree.py)
- [ros2_ws/src/sancho_behavior/sancho_behavior/interaction/interaction_manager_node.py](ros2_ws/src/sancho_behavior/sancho_behavior/interaction/interaction_manager_node.py)
- [ros2_ws/src/sancho_behavior/sancho_behavior/behaviors/navigation.py](ros2_ws/src/sancho_behavior/sancho_behavior/behaviors/navigation.py)
- [ros2_ws/src/sancho_interfaces/CMakeLists.txt](ros2_ws/src/sancho_interfaces/CMakeLists.txt)

## Common Pitfalls

- After changing `.msg/.srv/.action`, rebuild and re-source before running Python nodes.
- If generated interface imports fail after schema changes, clean stale overlays (`build/`, `install/`) and rebuild.
- Keep ROS 2 Humble assumptions; avoid introducing distro-incompatible APIs.

## Validation Checklist For Agents

1. Build at least `sancho_interfaces` and `sancho_behavior` with `colcon`.
2. Source `install/setup.bash` in the same shell before `ros2 run` or `ros2 launch`.
3. For behavior changes, smoke-test one of:
   - `ros2 run sancho_behavior sancho_behavior_tree`
   - `ros2 launch sancho_behavior sancho_interaction.launch.py`
