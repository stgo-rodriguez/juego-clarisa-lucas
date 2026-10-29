"""Prueba visual real de Streamlit con Chromium (no solo AppTest).

Valida alto del panel, único scroll, navegación con selector fijo y tablas
a ancho completo en tamaños representativos de escritorio.
Ejecutar: python tests/visual_smoke_lab.py
Requiere: pip install playwright; navegador Google Chrome instalado.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 8517
URL = f"http://127.0.0.1:{PORT}"
CAPTURES = ROOT / "test-results" / "browser"
CAPTURES.mkdir(parents=True, exist_ok=True)


def esperar_servidor(proc: subprocess.Popen) -> None:
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError(f"Streamlit finalizó con código {proc.returncode}")
        try:
            with urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            time.sleep(0.3)
    raise TimeoutError("Streamlit no inició antes del límite de la prueba")


def geometria(page, selector: str) -> dict:
    return page.locator(selector).first.evaluate("""el => {
        const r = el.getBoundingClientRect();
        return {
            top: r.top, bottom: r.bottom, width: r.width, height: r.height,
            scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
            overflowY: getComputedStyle(el).overflowY
        };
    }""")


def validar_vista(page, ancho: int, alto: int) -> None:
    page.set_viewport_size({"width": ancho, "height": alto})
    page.wait_for_timeout(700)

    cabecera = geometria(page, ".st-key-selector_analisis")
    panel = geometria(page, '[data-testid="stTabs"] [role="tabpanel"]:visible')
    assert cabecera['top'] <= 4, f"El selector no está fijo: {cabecera}"
    assert cabecera['bottom'] < alto * .23, f"El encabezado ocupa demasiado alto: {cabecera}"
    assert panel['bottom'] >= alto - 8, f"Panel recortado al pie: {panel}"
    assert panel['height'] >= alto - cabecera['bottom'] - 75, (
        f"Panel desaprovecha altura: {panel}; cabecera={cabecera}"
    )
    assert panel['overflowY'] in ("auto", "scroll"), f"Sin scroll nativo: {panel}"

    # La solapa debe desplazarse, sin mover el selector superior.
    locator = page.locator('[data-testid="stTabs"] [role="tabpanel"]:visible')
    locator.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
    page.wait_for_timeout(350)
    scroll = locator.evaluate("(el) => el.scrollTop")
    assert scroll > 100, f"El panel no permite bajar: scrollTop={scroll}, panel={panel}"
    cabecera_final = geometria(page, ".st-key-selector_analisis")
    assert abs(cabecera_final['top'] - cabecera['top']) < 3, "El selector se desplazó al bajar"

    tablas = locator.locator('[data-testid="stDataFrame"]')
    assert tablas.count() >= 3, "Faltan las tablas de actividad"
    dimensiones = [
        tablas.nth(i).evaluate("""el => {
            const r=el.getBoundingClientRect();
            return {x:r.x,y:r.y,width:r.width,height:r.height}
        }""")
        for i in range(2)
    ]
    assert all(x["width"] >= panel['width'] * .76 for x in dimensiones), (
        f"Tablas demasiado estrechas: {dimensiones}, panel={panel}"
    )
    assert dimensiones[1]["y"] >= dimensiones[0]["y"] + dimensiones[0]["height"] - 10, (
        f"Tablas superpuestas o una al lado de la otra: {dimensiones}"
    )
    page.screenshot(path=str(CAPTURES / f"actividad_{ancho}x{alto}.png"), full_page=False)


def ejecutar() -> None:
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            "laboratorio/app.py", "--server.headless=true",
            f"--server.port={PORT}", "--server.address=127.0.0.1",
        ],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        esperar_servidor(proc)
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel="chrome", headless=True, args=["--no-sandbox"])
            pagina = navegador.new_page(viewport={"width": 1600, "height": 900})
            pagina.set_default_timeout(120000)
            pagina.goto(URL)
            pagina.get_by_role("button", name="Ejecutar y comparar escenarios").click()
            pagina.get_by_role("button", name="Pantalla de análisis").click()
            pagina.get_by_role("tab", name="Actividad de turnos").click()
            pagina.get_by_text("Actividad validada", exact=False).first.wait_for(state="visible")
            validar_vista(pagina, 1600, 900)
            validar_vista(pagina, 1280, 720)
            navegador.close()
        print("OK: navegador real · encabezado fijo · scroll al pie · tablas a ancho completo.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    ejecutar()
