"""Smoke test con Google Chrome: pantalla fija, ronda navegable y tablero SIMLOG.

Inicia Streamlit sobre los fixtures históricos del repositorio, sin generar
partidas nuevas ni escribir en los CSV.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8529"
CAPTURES = ROOT / "test-results" / "simlog-inspector"
CAPTURES.mkdir(parents=True, exist_ok=True)


def _health(proc):
    for _ in range(120):
        if proc.poll() is not None:
            raise AssertionError(f"Streamlit murió antes de iniciar: {proc.returncode}")
        try:
            with urlopen(f"{BASE}/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(.3)
    raise TimeoutError("Streamlit no alcanzó /_stcore/health")


def _geometry(page, selector):
    return page.locator(selector).first.evaluate("""el => {
        const r=el.getBoundingClientRect();
        return {top:r.top,bottom:r.bottom,height:r.height,
                width:r.width,overflowY:getComputedStyle(el).overflowY,
                clientHeight:el.clientHeight,scrollHeight:el.scrollHeight}
    }""")


def _verify_viewport(page):
    header = _geometry(page, ".st-key-inspector_header")
    body = _geometry(page, ".st-key-inspector_content")
    viewport = page.viewport_size["height"]
    assert header["top"] <= 3, header
    assert header["height"] <= 125, header
    assert body["bottom"] >= viewport - 3, body
    assert body["top"] >= header["top"] + 50, (header,body)
    assert body["height"] >= viewport - 135, body
    assert body["overflowY"] in ("auto","scroll"), body


def run():
    env = os.environ.copy()
    env["SIMLOG_RESULTS_ROOT"] = str(
        ROOT/"docs"/"datos_simlog_v2"/"ejemplo_cuatro_partidas")
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"]="false"
    proc = subprocess.Popen([
        sys.executable,"-m","streamlit","run",
        "laboratorio/pages/1_Visualizador_SIMLOG_v21.py",
        "--server.headless=true","--server.address=127.0.0.1",
        "--server.port=8529",
    ],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
    try:
        _health(proc)
        with sync_playwright() as p:
            browser=p.chromium.launch(channel="chrome",headless=True,
                                      args=["--no-sandbox"])
            page=browser.new_page(viewport={"width":1510,"height":850})
            page.set_default_timeout(40000)
            page.goto(BASE)
            page.get_by_role("button",name="Abrir inspección de rondas y tablero").click()
            page.locator(".st-key-inspector_header").wait_for(state="visible")
            page.wait_for_timeout(650)
            _verify_viewport(page)
            page.screenshot(path=str(CAPTURES/"resumen.png"))
            assert page.locator(".inspector-player").count() >= 2
            page.get_by_role("button",name="▶").click()
            page.wait_for_timeout(250)
            assert page.locator(".st-key-inspector_header input").first.input_value() == "2"
            page.get_by_text("Tablero",exact=True).click()
            page.locator('[data-testid="stPlotlyChart"]').first.wait_for(state="visible")
            page.wait_for_timeout(450)
            _verify_viewport(page)
            assert page.locator('[data-testid="stDataFrame"]').count() >= 1
            page.screenshot(path=str(CAPTURES/"tablero.png"))
            page.set_viewport_size({"width":1280,"height":720})
            page.wait_for_timeout(350)
            _verify_viewport(page)
            page.screenshot(path=str(CAPTURES/"tablero_1280.png"))
            page.get_by_text("Detalle",exact=True).click()
            page.locator(".st-key-inspector_content").wait_for(state="visible")
            page.wait_for_timeout(550)
            area=page.locator(".st-key-inspector_content")
            data=_geometry(page,".st-key-inspector_content")
            if data["scrollHeight"]>data["clientHeight"]+100:
                area.evaluate("el=>el.scrollTop=el.scrollHeight")
                assert area.evaluate("el=>el.scrollTop") > 50
                _verify_viewport(page)
            page.screenshot(path=str(CAPTURES/"detalle.png"))
            browser.close()
        print("OK visual: 2 resoluciones, 3 vistas, navegación y scroll independiente.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    run()
