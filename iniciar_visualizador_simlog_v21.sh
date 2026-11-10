#!/usr/bin/env bash
# Preparación y arranque en un solo paso de Visualizador SIMLOG v2.1/v2.2 (macOS/Linux).
# Reutiliza .venv, no modifica el Python global y conserva las corridas existentes.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

say() { printf '\n%s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

say "=== Clarisa & Lucas · Visualizador SIMLOG v2.1/v2.2 ==="

[[ -f "requirements.txt" ]] || fail "No encuentro requirements.txt en $ROOT."
[[ -f "laboratorio/pages/1_Visualizador_SIMLOG_v21.py" ]] ||
  fail "No encuentro el visualizador v2.1. Actualizá la rama feature/visualizador-simlog-v21."

# Priorizar el entorno virtual del repositorio; no depende del comando 'python'.
VENV_PY="$ROOT/.venv/bin/python"
if [[ ! -x "$VENV_PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    SYSTEM_PY="$(command -v python3)"
  elif command -v python3.13 >/dev/null 2>&1; then
    SYSTEM_PY="$(command -v python3.13)"
  else
    fail "No se encontró Python 3. Instalá Python 3.11+ y volvé a ejecutar este mismo script."
  fi
  "$SYSTEM_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' ||
    fail "Se necesita Python 3.11 o posterior."
  say "[1/5] Creando entorno virtual local .venv"
  "$SYSTEM_PY" -m venv "$ROOT/.venv" ||
    fail "No pude crear .venv. Verificá permisos y la instalación de Python."
else
  say "[1/5] Reutilizando el entorno virtual .venv"
fi

"$VENV_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' ||
  fail "El entorno virtual usa Python anterior a 3.11. Renombrá .venv y repetí."
"$VENV_PY" -m pip --version >/dev/null 2>&1 ||
  "$VENV_PY" -m ensurepip --upgrade ||
  fail "No pude habilitar pip en el entorno virtual."

say "[2/5] Instalando/verificando las dependencias en .venv"
"$VENV_PY" -m pip install -r requirements.txt ||
  fail "Falló la instalación de dependencias. Revisá la conexión y el error de pip."

say "[3/5] Validando el laboratorio"
"$VENV_PY" -m laboratorio.diagnostico ||
  fail "El diagnóstico detectó errores; no iniciaré una instancia inválida."

# Solo generar datos de demostración si no existe ninguna partida compatible con ganadores.
# La generación se ejecuta localmente y produce trazas reales, sin alterar las existentes.
say "[4/5] Buscando partidas SIMLOG v2.1 y v2.2"
if "$VENV_PY" -c '
from pathlib import Path
import sys
from laboratorio.simlog_viewer_v21 import discover_games
games = discover_games(Path("resultados"))
winners = sum(bool(game["won"]) for game in games)
print(f"Partidas compatibles encontradas: {len(games)}; con ganadores: {winners}")
sys.exit(0 if winners else 1)
'; then
  say "Se reutilizarán las partidas compatibles existentes."
else
  say "No hay partidas ganadoras v2.1 locales; generando 10 partidas reales (5 semillas × 2 mesas)."
  "$VENV_PY" -m laboratorio.simular_mazos_vigentes_v2 \
    --semillas 5 --rondas 100 --out resultados/simlog_v21_20261108 ||
    fail "No se pudieron generar las partidas SIMLOG v2.1."
fi

# Streamlit permanece vinculado a loopback para acceso exclusivo desde este Mac.
PORT="$("$VENV_PY" -c '
import socket
for port in range(8501, 8601):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            continue
        print(port)
        break
else:
    raise SystemExit("No hay puertos libres entre 8501 y 8600")
')" || fail "No encontré un puerto disponible."

say "[5/5] Iniciando visualizador en http://127.0.0.1:$PORT"
say "Se abrirá en el navegador. Para detenerlo, presioná Ctrl+C en esta Terminal."
exec "$VENV_PY" -m streamlit run laboratorio/pages/1_Visualizador_SIMLOG_v21.py \
  --server.address=127.0.0.1 \
  --server.port="$PORT" \
  --server.headless=false \
  --browser.gatherUsageStats=false
