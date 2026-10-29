#!/usr/bin/env bash
# Lanzador local de macOS/Linux, sin instalar paquetes ni descargar contenido.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  echo 'No se encontró .venv. Consultá docs/GUIA_USUARIO.md para instalarlo.' >&2
  exit 1
fi
.venv/bin/python -m laboratorio.diagnostico
exec .venv/bin/python -m streamlit run laboratorio/app.py \
  --server.address=127.0.0.1 --server.port=8501
