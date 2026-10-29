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
from laboratorio.trazabilidad import trazar_partida
from laboratorio.gantt import grafico_gantt

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

    st.divider()
    st.subheader("4. Cronología de hitos de la pareja ganadora (Gantt)")
    st.caption("Elegí una partida concluida de cualquiera de los escenarios. "
               "El laboratorio vuelve a ejecutar solamente esa semilla con observación pasiva "
               "y comprueba que el resultado completo sea idéntico al de la simulación original.")
    lado = st.radio("Escenario del Gantt", ["Base", "Experimento"], horizontal=True,
                    key="gantt_lado")
    resultado = baseline if lado == "Base" else experiment
    opciones = [i + 1 for i, fila in enumerate(resultado["filas"]) if int(fila["terminada"])]
    if not opciones:
        st.info("No hay partidas concluidas en este escenario; no existe pareja ganadora que graficar.")
    else:
        numero = st.selectbox(
            "Partida concluida", options=opciones, key="gantt_numero",
            format_func=lambda n: (f"Partida {n} · semilla {resultado['filas'][n-1]['semilla']} "
                                   f"· casamiento en ronda {resultado['filas'][n-1]['rondas_observadas']}")
        )
        identificador = json.dumps({"escenario": resultado["escenario"], "partida": numero},
                                   sort_keys=True, ensure_ascii=False)
        if st.button("Construir Gantt y verificar partida", key="gantt_reconstruir"):
            try:
                with st.spinner(f"Reejecutando únicamente la partida {numero} para reconstruir sus hitos…"):
                    trazado = trazar_partida(escenario_desde_dict(resultado["escenario"]),
                                             numero, resultado["filas"][numero - 1])
                st.session_state["gantt_ultimo"] = (identificador, trazado)
            except Exception as exc:
                st.session_state.pop("gantt_ultimo", None)
                st.error(f"No se pudo validar el Gantt: {exc}")
        previo = st.session_state.get("gantt_ultimo")
        if previo is not None and previo[0] == identificador:
            trazado = previo[1]
            st.success("Partida reconstruida y comprobada: todos los indicadores coinciden con el motor original.")
            nombres = " + ".join(f"{x['personaje']} #{x['id']}" for x in trazado['ganadores'])
            st.markdown(f"**Pareja ganadora:** {nombres} · **Casamiento:** ronda {trazado['ronda_casamiento']}")
            st.plotly_chart(grafico_gantt(trazado), use_container_width=True)
            st.caption("Las barras indican períodos en los que se conservó el hito. "
                       "Una interrupción muestra pérdida y posterior recuperación. "
                       "El tiempo horizontal registra rondas y orden de los turnos.")
            st.dataframe(trazado["hitos"], use_container_width=True, hide_index=True)
            st.info(trazado["advertencia"])
            st.download_button(
                "Descargar cronología verificada (JSON)",
                data=json.dumps(trazado, ensure_ascii=False, indent=2).encode("utf-8"),
                mime="application/json",
                file_name=f"gantt_partida_{numero}_{lado.lower()}.json",
                key="descargar_gantt")
        elif previo is not None:
            st.caption("Seleccionaste otra partida o escenario. Elegí «Construir Gantt» para actualizar el gráfico.")
