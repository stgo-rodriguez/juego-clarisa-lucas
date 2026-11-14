"""Importación local reproducible de las trazas SIMLOG-2.3 de GitHub Actions.

Fuente fijada: ejecución 42933927583 (350 partidas de 6 y 350 de 10).
No ejecuta el simulador, no altera corridas históricas y no requiere clonar ramas.
Requiere GitHub CLI (gh) autenticado en el Mac. Verifica esquema, semillas y
SHA256 de los archivos enumerados en cada manifiesto antes de publicar los datos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

REPO = "stgo-rodriguez/juego-clarisa-lucas"
RUN_ID = 42933927583
SCHEMA = "SIMLOG-2.3"
RULESET = "especificacion-integral-2026-11-10"
SEMILLAS = set(range(2001, 2351))
ARTIFACTS = {
    6: "SIMLOG_v23_utn_corregido_350_trazas_6jug_2001_2350",
    10: "SIMLOG_v23_utn_corregido_350_trazas_10jug_2001_2350",
}
CARPETA_FUENTE = f"SIMLOG_v23_UTN_CORREGIDO_gh_{RUN_ID}"


class ErrorImportacion(ValueError):
    """Descarga ausente, credenciales incorrectas o trazas no verificables."""


def validar_trazas(folder: Path, jugadores: int) -> dict:
    """Auditar todos los manifiestos de un artefacto antes de incorporarlo."""
    paths = sorted(folder.rglob("manifest.json"))
    if len(paths) != 350:
        raise ErrorImportacion(
            f"Mesa de {jugadores}: se esperaban 350 trazas y se encontraron "
            f"{len(paths)} en {folder}."
        )
    semillas = set()
    files_verified = 0
    for path in paths:
        try:
            manifest = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            raise ErrorImportacion(f"Manifiesto ilegible: {path}") from exc
        seed = int(manifest.get("seed") or 0)
        if (manifest.get("schema") != SCHEMA
                or manifest.get("ruleset") != RULESET
                or int(manifest.get("player_count") or 0) != jugadores
                or seed not in SEMILLAS
                or seed in semillas):
            raise ErrorImportacion(f"Identidad SIMLOG incompatible: {path}")
        semillas.add(seed)
        for filename in ("turnos.csv", "eventos.csv", "estados_jugadores.csv"):
            if not (path.parent / filename).is_file():
                raise ErrorImportacion(f"Falta {filename} en {path.parent}")
        hashes = manifest.get("file_sha256")
        if not isinstance(hashes, dict) or not hashes:
            raise ErrorImportacion(f"Manifiesto sin hashes: {path}")
        for filename, digest in hashes.items():
            if not isinstance(filename, str) or Path(filename).name != filename:
                raise ErrorImportacion(f"Nombre de archivo inseguro en {path}")
            source = path.parent / filename
            if not source.is_file():
                raise ErrorImportacion(f"Falta archivo auditado: {source}")
            checker = hashlib.sha256()
            with source.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    checker.update(chunk)
            if checker.hexdigest() != digest:
                raise ErrorImportacion(f"SHA256 incorrecto: {source}")
            files_verified += 1
    if semillas != SEMILLAS:
        raise ErrorImportacion(
            f"Mesa de {jugadores}: cobertura incompleta de semillas 2001–2350."
        )
    return {"jugadores": jugadores, "partidas": len(paths),
            "archivos_auditados": files_verified}


def verificar_github_cli() -> str:
    gh = shutil.which("gh")
    if not gh:
        raise ErrorImportacion(
            "No se encontró GitHub CLI (gh). Instalalo con 'brew install gh', "
            "luego ejecutá 'gh auth login' en la terminal e intentá de nuevo."
        )
    try:
        result = subprocess.run(
            [gh, "auth", "status", "-h", "github.com"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ErrorImportacion("No se pudo verificar la sesión de GitHub CLI.") from exc
    if result.returncode:
        raise ErrorImportacion(
            "GitHub CLI no tiene una sesión válida. Ejecutá 'gh auth login' "
            "en la terminal y volvé a importar."
        )
    return gh


def importar_run(resultados: str | Path, mesas=(6, 10)) -> list[dict]:
    """Descargar y publicar cada mesa tras una validación íntegra y atómica.

    Los datos se guardan bajo resultados/ sin tocar fuentes anteriores.
    Si una mesa ya está importada y verificada, se reutiliza.
    """
    dest = Path(resultados).expanduser().resolve() / CARPETA_FUENTE
    tamaños = tuple(mesas)
    if not tamaños or any(n not in ARTIFACTS for n in tamaños):
        raise ErrorImportacion("Mesas válidas: 6 y/o 10 jugadores.")
    estados = []
    for n in tamaños:
        target = dest / f"{n}_jugadores"
        if target.exists():
            try:
                state = validar_trazas(target, n)
                estados.append({**state, "estado": "reutilizada", "ruta": str(target)})
                continue
            except ErrorImportacion as exc:
                raise ErrorImportacion(
                    f"Existe una descarga incompleta en {target}. "
                    "Conservá la carpeta para diagnóstico antes de repetir."
                ) from exc
        gh = verificar_github_cli()
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f".descarga_{n}_", dir=dest) as temp:
            stage = Path(temp)
            command = [
                gh, "run", "download", str(RUN_ID), "-R", REPO,
                "-n", ARTIFACTS[n], "-D", str(stage),
            ]
            try:
                proc = subprocess.run(command, capture_output=True, text=True,
                                      timeout=1200, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ErrorImportacion(
                    f"No se pudo descargar la mesa de {n} jugadores."
                ) from exc
            if proc.returncode:
                detail = (proc.stderr or proc.stdout or "").strip()[-1200:]
                raise ErrorImportacion(
                    f"Falló GitHub Actions (mesa de {n}): {detail}"
                )
            state = validar_trazas(stage, n)
            stage.rename(target)
            estados.append({**state, "estado": "incorporada", "ruta": str(target)})
    return estados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resultados", type=Path, default=Path("resultados"))
    parser.add_argument("--mesa", type=int, choices=(6, 10),
                        help="Opcional: importar una sola configuración.")
    args = parser.parse_args()
    try:
        states = importar_run(args.resultados, (args.mesa,) if args.mesa else (6, 10))
    except ErrorImportacion as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    for state in states:
        print(
            f"{state['jugadores']} jugadores · {state['partidas']} partidas · "
            f"{state['estado']} · {state['ruta']}"
        )


if __name__ == "__main__":
    main()
