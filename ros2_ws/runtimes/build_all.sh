#!/bin/bash

# Array of packages that have specific venvs
# Format: "package_name:venv_path"
PACKAGES=(
  "sancho_perception:venvs/sancho_perception"
  # Add your other venv-dependent packages here
)

for entry in "${PACKAGES[@]}"; do
  PKG_NAME="${entry%%:*}"
  VENV_PATH="${entry##*:}"

  echo "========================================"
  echo "Building $PKG_NAME with $VENV_PATH..."
  echo "========================================"

  # Activate the specific venv
  source "$VENV_PATH/bin/activate"

  # Build only this package
#    --symlink-install \
  colcon build \
    --event-handlers console_cohesion+ \
    --base-paths src \
    --packages-select "$PKG_NAME"

  # Deactivate to ensure a clean slate for the next iteration
  deactivate
done

echo "========================================"
echo "Building remaining standard ROS 2 packages..."
echo "========================================"
# Build everything else that doesn't have a custom venv requirement
# --packages-skip prevents rebuilding the ones we just did
colcon build --symlink-install --packages-skip sancho_perception