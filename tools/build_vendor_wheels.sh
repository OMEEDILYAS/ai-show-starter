#!/usr/bin/env bash
# Build/download vendor wheels for fast CI installs (Option A).
# Run once per Python version, then commit vendor/wheels/*.whl to the repo.
set -euo pipefail

PYTHON="${PYTHON:-python3}"
ROOT="$(cd "$(dirname "$0")/.."; pwd)"
VEN="$ROOT/.venv_wheels"
mkdir -p "$VEN" "$ROOT/vendor/wheels"

$PYTHON -m venv "$VEN"
source "$VEN/bin/activate"
pip install --upgrade pip wheel

# Build/download wheels for these packages and their deps.
# We keep the list small and rely on pip to pull needed deps.
PKGS=(
  numpy
  pillow
  matplotlib
  networkx
  graphviz   # python binding for graphviz
)

for p in "${PKGS[@]}"; do
  echo "===> Downloading wheels for $p"
  pip download --only-binary=:all: --dest "$ROOT/vendor/wheels" "$p"
done

echo "Done. Commit vendor/wheels/*.whl to the repo."
