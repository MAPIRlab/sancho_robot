#!/usr/bin/env bash
# Crea/actualiza el venv de assistant_helper desde requirements.txt
# Uso:
#   ./create_venv.sh                # crea/actualiza
#   ./create_venv.sh --recreate     # borra y crea de cero
#   ./create_venv.sh --lock         # genera requirements.lock.txt (pip freeze)
#   ./create_venv.sh --python /usr/bin/python3.10  # elige intérprete

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${BASE_DIR}/venv"
REQS="${BASE_DIR}/requirements.txt"
LOCK="${BASE_DIR}/requirements.lock.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"
USE_SYSTEM_SITE="--system-site-packages"
RECREATE="no"
DO_LOCK="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate) RECREATE="yes"; shift ;;
    --lock) DO_LOCK="yes"; shift ;;
    --python) PYTHON_BIN="$2"; shift 2 ;;
    --no-system-site) USE_SYSTEM_SITE=""; shift ;;
    *) echo "Opción no reconocida: $1"; exit 2 ;;
  esac
done

if [[ "$RECREATE" == "yes" && -d "$VENV" ]]; then
  echo "🔁 Borrando venv existente: $VENV"
  rm -rf "$VENV"
fi

if [[ ! -d "$VENV" ]]; then
  echo "🆕 Creando venv en $VENV (python: $PYTHON_BIN) $USE_SYSTEM_SITE"
  "$PYTHON_BIN" -m venv "$VENV" $USE_SYSTEM_SITE
fi

# Activar venv
# shellcheck disable=SC1090
source "$VENV/bin/activate"

python -m pip install --upgrade pip wheel

# Si hay lock, priorízalo; si no, usa requirements.txt
if [[ -f "$LOCK" ]]; then
  echo "📦 Instalando desde $LOCK"
  python -m pip install --upgrade -r "$LOCK"
elif [[ -f "$REQS" ]]; then
  echo "📦 Instalando/actualizando desde $REQS"
  python -m pip install --upgrade -r "$REQS"
else
  echo "⚠️ No hay $REQS ni $LOCK. Instalando mínimos…"
  python -m pip install openwakeword numpy
fi

if [[ "$DO_LOCK" == "yes" ]]; then
  echo "🧾 Generando $LOCK"
  pip freeze > "$LOCK"
fi

deactivate
echo "✅ Venv listo/actualizado en $VENV"
