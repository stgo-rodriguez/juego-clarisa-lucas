"""Interfaz local del Laboratorio de Balance v1.3 (Fase 3).

Iniciar desde la raíz del repositorio:
  streamlit run laboratorio/app.py
No modifica el sitio público index.html.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Soporta tanto `streamlit run laboratorio/app.py` como imports desde pruebas.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from simulador.economia import EconomyConfig, ScenarioConfig
from laboratorio.comparacion import (comparar, escenario_base, escenario_desde_dict,
                                     ejecutar, exportar_zip, signature)
from laboratorio.visualizaciones import tabla_distribucion, metricas_comparadas

st.set_page_config(page_title="Laboratorio de Balance · Clarisa & Lucas", page_icon="⚖️", layout="wide")


@st.cache_data(show_spinner=False, max_entries=12)
def correr_cacheado(config_json: str, codigo_json: str) -> dict:
    """Clave incluye configuración íntegra Y hashes del motor y del mazo."""
    _ = codigo_json
    config = escenario_desde_dict(json.loads(config_json))
    return ejecutar(config)


def correr(config: ScenarioConfig) -> dict:
    return correr_cacheado(
        json.dumps(config.as_dict(), ensure_ascii=False, sort_keys=True),
        json.dumps(signature(), sort_keys=True),
    )



st.title("Laboratorio de Balance · Clarisa & Lucas")
st.caption("Prototipo local · Fase 3 · Reglamentación v1.3 consolidada")
st.info("Se preservan las reglas, los costos de hitos y los bots auditados. "
        "Los resultados estiman el comportamiento de los bots, no la duración real ni la diversión humana.")

with st.form("ajustes"):
    st.subheader("1. Configuración común de la simulación")
    left, middle, right = st.columns(3)
    with left:
        jugadores = st.selectbox("Jugadores", options=[6, 10], index=0)
        partidas = st.selectbox("Partidas por escenario", options=[20, 100, 500, 1000], index=1,
                               help="20 para una verificación rápida; 100/500/1000 para análisis.")
    with middle:
        seed = st.number_input("Semilla inicial", min_value=0, max_value=2_000_000_000,
                               value=131028 if jugadores == 6 else 231028, step=1,
                               help="Mismas semillas en base y experimento.")
        max_rondas = st.number_input("Límite de rondas", min_value=10, max_value=500, value=120, step=10)
    with right:
        bot = st.selectbox("Política de bots", options=["mixed", "inversor", "oportunista", "planificador",
                                                       "competitivo", "cooperativo"], index=0)
        st.caption("Se utiliza la misma política en ambos escenarios.")
    st.subheader("2. Economía del escenario experimental")
    st.caption("La referencia queda fija: Perfiles, cartas e Infancia al 100%; "
               "casilleros de Juventud y Adultez desactivados.")
    one, two = st.columns(2)
    with one:
        perf = st.slider("Producción de Perfiles (%)", 50, 150, 100, step=5)
        cards_plus = st.slider("Ganancias por Cartas de Situación (%)", 50, 150, 100, step=5)
        cards_minus = st.slider("Pérdidas por Cartas de Situación (%)", 50, 150, 100, step=5)
    with two:
        inf = st.slider("Ingresos automáticos en Infancia (%)", 50, 150, 100, step=5)
        juv = st.checkbox("Habilitar ingresos por casilleros de Juventud (100 %)", value=False)
        adu = st.checkbox("Habilitar ingresos por casilleros de Adultez (100 %)", value=False)
    submit = st.form_submit_button("Ejecutar y comparar escenarios", type="primary")

if submit:
    try:
        base_config = escenario_base(jugadores, partidas, seed=int(seed), max_rondas=int(max_rondas), bot=bot)
        experimental_config = ScenarioConfig(
            id="experimento_interfaz", jugadores=jugadores, partidas=partidas, seed=int(seed),
            incremento_seed=base_config.incremento_seed, max_rondas=int(max_rondas), bot=bot,
            economia=EconomyConfig(perfiles_pct=perf, cartas_ganancias_pct=cards_plus,
                                   cartas_perdidas_pct=cards_minus, infancia_pct=inf,
                                   juventud_pct=100 if juv else 0,
                                   adultez_pct=100 if adu else 0),
        )
        with st.spinner(f"Ejecutando {2 * partidas:,} partidas con semillas apareadas…"):
            base_result = correr(base_config)
            variant_result = correr(experimental_config)
            diff = comparar(base_result, variant_result)
        st.session_state["ultima_comparacion"] = (base_result, variant_result, diff)
    except Exception as exc:
        st.error(f"No se pudo ejecutar la simulación: {exc}")
        st.session_state.pop("ultima_comparacion", None)

if "ultima_comparacion" not in st.session_state:
    st.markdown("**Ejecución pendiente.** Ajustá los controles y seleccioná «Ejecutar y comparar escenarios».")
else:
    baseline, experiment, comparison = st.session_state["ultima_comparacion"]
    st.divider()
    st.subheader("3. Resultados de la última ejecución")
    st.caption(f"{comparison['total']} semillas comunes · {baseline['escenario']['jugadores']} jugadores · "
               f"bot {baseline['escenario']['bot']} · límite {baseline['escenario']['max_rondas']} rondas")
    b = baseline["resumen"]["casamiento"]
    v = experiment["resumen"]["casamiento"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Mediana base (concluidas)", str(b["mediana"]) if b["mediana"] is not None else "Sin datos")
    c2.metric("Mediana experimento (concluidas)", str(v["mediana"]) if v["mediana"] is not None else "Sin datos",
              delta=f"{round(v['mediana']-b['mediana'], 2):+g} rondas" if b["mediana"] is not None and v["mediana"] is not None else None,
              delta_color="off")
    c3.metric("Pares concluidos en ambos", f"{comparison['ambas_finalizadas']}/{comparison['total']}")
    if comparison["alguna_censurada"]:
        st.warning(comparison["advertencia_censura"])
    else:
        st.caption("Sin censura: todas las partidas de ambos escenarios terminaron dentro del límite.")
    st.dataframe(metricas_comparadas(baseline, experiment), hide_index=True, use_container_width=True)
    st.plotly_chart(tabla_distribucion(baseline, experiment), use_container_width=True)
    st.markdown("**Comparación apareada de rondas**")
    st.write({"Media de diferencia (experimento − base)": comparison["delta_media_rondas_apareadas"],
              "Mediana de diferencia": comparison["delta_mediana_rondas_apareadas"],
              "Partidas que cambiaron ronda o finalización": comparison["variaron_rondas_o_estado"]})
    st.caption("La diferencia apareada no es lo mismo que restar las medianas agregadas. "
               "No se informan intervalos de confianza en este MVP.")
    st.download_button("Descargar resultados, muestras y configuración (ZIP)",
                       data=exportar_zip(baseline, experiment, comparison),
                       file_name="laboratorio_balance_comparacion.zip", mime="application/zip")
    with st.expander("Configuraciones reproducibles y huellas del motor"):
        st.json({"base": baseline["escenario"], "experimento": experiment["escenario"],
                 "firmas": baseline["codigo"]})
