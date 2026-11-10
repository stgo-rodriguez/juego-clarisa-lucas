#!/usr/bin/env bash
# Importar una partida SIMLOG v2.2 y abrir el visualizador local.
# Uso: ./visualizar_simlog_v22.sh ~/Downloads/SIMLOG_v22_6j_max700_s701.zip
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
  printf 'Uso: %s <archivo ZIP descargado de GitHub Actions>\n' "$0" >&2
  exit 2
fi
if [[ ! -e "$1" ]]; then
  printf 'No existe el archivo o carpeta: %s\n' "$1" >&2
  exit 2
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Necesitás Python 3 para importar el archivo." >&2
  exit 1
fi
python3 -m laboratorio.importar_simlog_v22 "$1" --resultados "$ROOT/resultados"
echo "Abriendo visualizador con la partida importada..."
exec "$ROOT/iniciar_visualizador_simlog_v21.sh"
