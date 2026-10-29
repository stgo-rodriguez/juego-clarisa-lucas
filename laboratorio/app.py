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
from laboratorio.historial import (crear_archivo, cargar_archivo, guardar_local,
                                  listar_local, abrir_local, comparar_guardados)
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

# Historial persistente solo en este equipo. La carpeta se excluye de Git.
HISTORIAL = ROOT / '.laboratorio' / 'historial'
st.divider()
st.subheader('Historial de experimentos · Fase 5')
st.caption('Guardá resultados completos en esta computadora y recuperalos sin volver a simular. '
           'El historial NO se sincroniza automáticamente con GitHub ni con otros equipos.')
archivos_historial = listar_local(HISTORIAL)
st.caption(f'{len(archivos_historial)} comparaciones guardadas en {HISTORIAL}')

if 'ultima_comparacion' in st.session_state:
    actual_base, actual_variante, actual_comparacion = st.session_state['ultima_comparacion']
    nombre_exp = st.text_input('Nombre del experimento', value='Comparación económica',
                               max_chars=100, key='historial_nombre')
    try:
        zip_actual = crear_archivo(actual_base, actual_variante, nombre=nombre_exp)
        csave, cexport = st.columns(2)
        with csave:
            if st.button('Guardar comparación en este equipo', key='historial_guardar'):
                ruta = guardar_local(HISTORIAL, zip_actual, nombre=nombre_exp)
                st.success(f'Experimento guardado: {ruta.name}')
                st.rerun()
        with cexport:
            st.download_button('Descargar experimento completo (ZIP)', data=zip_actual,
                               file_name='clarisa_lucas_experimento.zip',
                               mime='application/zip', key='historial_descargar')
    except Exception as exc:
        st.error(f'No se puede guardar la comparación: {exc}')

subido = st.file_uploader('Importar experimento exportado (Fase 3 o Fase 5)',
                          type=['zip'], key='historial_subir')
if subido is not None and st.button('Validar e incorporar archivo importado',
                                     key='historial_importar'):
    try:
        original = cargar_archivo(subido.getvalue())
        canonico = crear_archivo(original['base'], original['variante'],
                                nombre=original['meta']['nombre'])
        ruta = guardar_local(HISTORIAL, canonico, nombre=original['meta']['nombre'])
        st.session_state['historial_aviso_importado'] = (
            f'Importado correctamente: {ruta.name}', original['meta']['advertencias'])
        st.rerun()
    except Exception as exc:
        st.error(f'No se pudo importar el ZIP: {exc}')
if 'historial_aviso_importado' in st.session_state:
    mensaje, avisos = st.session_state.pop('historial_aviso_importado')
    st.success(mensaje)
    for aviso in avisos:
        st.warning(aviso)

if archivos_historial:
    st.markdown('**Recuperar y comparar resultados guardados**')
    izquierda, derecha = st.columns(2)
    opciones = [x.name for x in archivos_historial]
    with izquierda:
        archivo_a = st.selectbox('Experimento A', opciones, key='historial_izquierdo')
        variante_a = st.selectbox('Escenario A', ['Base', 'Experimento'],
                                  key='historial_tipo_a')
    with derecha:
        archivo_b = st.selectbox('Experimento B', opciones, key='historial_derecho')
        variante_b = st.selectbox('Escenario B', ['Experimento', 'Base'],
                                  key='historial_tipo_b')
    if st.button('Cargar y comparar sin simular', key='historial_comparar'):
        try:
            aa = cargar_archivo(abrir_local(HISTORIAL, archivo_a))
            bb = cargar_archivo(abrir_local(HISTORIAL, archivo_b))
            left = aa['base'] if variante_a == 'Base' else aa['variante']
            right = bb['base'] if variante_b == 'Base' else bb['variante']
            diff = comparar_guardados(left, right)
            st.session_state['ultima_comparacion'] = (left, right, diff)
            st.session_state['historial_recuperado'] = (archivo_a, archivo_b)
            st.success('Comparación cargada desde archivos verificados, sin repetir partidas.')
        except Exception as exc:
            st.error(f'No se pueden comparar estos resultados guardados: {exc}')
    if 'historial_recuperado' in st.session_state:
        a, b = st.session_state['historial_recuperado']
        st.caption(f'Última selección recuperada: {a} / {b}. '
                   'Los gráficos de las secciones siguientes usan estos datos almacenados.')

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

    st.divider()
    st.subheader("5. Economía de recursos por origen, etapa y jugador")
    st.caption("El lote completo aporta flujos agregados por fuente y recurso. "
               "El desglose por etapa/jugador se obtiene reejecutando una partida verificada: "
               "no se asignan etapas que los CSV originales no contienen.")
    from laboratorio.economia_trazable import trazar_economia
    from laboratorio.graficos_economia import (resumen_lote, figura_flujos,
                                               figura_saldos, RECURSO_NOMBRE)
    import pandas as pd

    with st.expander("Resumen de flujos del lote completo (sin desglose por etapa)"):
        df_base = pd.DataFrame(resumen_lote(baseline['filas']))
        df_exp = pd.DataFrame(resumen_lote(experiment['filas']))
        if not df_base.empty and not df_exp.empty:
            comun = df_base.merge(df_exp, on=['Recurso', 'Código', 'Fuente'],
                                  how='outer', suffixes=(' base', ' experimento')).fillna(0)
            comun['Diferencia'] = (comun['Fichas medias por partida experimento'] -
                                   comun['Fichas medias por partida base']).round(3)
            st.dataframe(comun.drop(columns='Código'), use_container_width=True,
                         hide_index=True)
            st.caption("Flujos brutos por partida. Inversiones, conversiones y ventas "
                       "de Casa no son ingresos externos netos; no sumar categorías "
                       "como si fueran beneficios independientes.")

    lado_ec = st.radio("Escenario de la economía", ['Base', 'Experimento'],
                       horizontal=True, key='economia_lado')
    elegido_ec = baseline if lado_ec == 'Base' else experiment
    opciones_ec = list(range(1, len(elegido_ec['filas']) + 1))
    numero_ec = st.selectbox(
        'Partida para auditar su economía', opciones_ec, key='economia_numero',
        format_func=lambda n: (f"Partida {n} · semilla {elegido_ec['filas'][n-1]['semilla']} "
                               f"· {elegido_ec['filas'][n-1]['rondas_observadas']} rondas"))
    identificador_ec = json.dumps(
        {'escenario': elegido_ec['escenario'], 'partida': numero_ec},
        ensure_ascii=False, sort_keys=True)
    if st.button('Reconstruir economía y auditar recursos', key='economia_reconstruir'):
        try:
            with st.spinner('Reconstruyendo movimientos y verificando stocks…'):
                detalle = trazar_economia(
                    escenario_desde_dict(elegido_ec['escenario']), numero_ec,
                    elegido_ec['filas'][numero_ec - 1])
            st.session_state['economia_ultima'] = (identificador_ec, detalle)
        except Exception as exc:
            st.session_state.pop('economia_ultima', None)
            st.error(f'Falló la auditoría económica: {exc}')
    previo_ec = st.session_state.get('economia_ultima')
    if previo_ec is not None and previo_ec[0] == identificador_ec:
        detalle = previo_ec[1]
        st.success('Economía verificada: movimientos, saldos y resultado coinciden con el motor.')
        st.caption(detalle['alcance'])
        etapas_activas = sorted({x['etapa'] for x in detalle['movimientos']})
        f1, f2, f3 = st.columns(3)
        with f1:
            etapas_filtradas = st.multiselect('Etapas', etapas_activas,
                                              default=etapas_activas, key='economia_etapas')
        with f2:
            jugadores_filtrados = st.multiselect('Jugadores',
                                                list(range(1, detalle['jugadores'] + 1)),
                                                default=list(range(1, detalle['jugadores'] + 1)),
                                                key='economia_jugadores')
        with f3:
            recursos_filtrados = st.multiselect('Recursos', list(RECURSO_NOMBRE),
                                                default=list(RECURSO_NOMBRE),
                                                format_func=lambda x: RECURSO_NOMBRE[x],
                                                key='economia_recursos')
        movimientos_filtrados = [e for e in detalle['movimientos']
                                 if e['etapa'] in etapas_filtradas and
                                 e['jugador'] in jugadores_filtrados and
                                 e['recurso'] in recursos_filtrados]
        st.plotly_chart(figura_flujos(movimientos_filtrados), use_container_width=True)
        st.caption('Barras positivas: ingresos y transferencias recibidas. '
                   'Barras negativas: pérdidas, pagos, inversiones y transferencias enviadas. '
                   'Los cambios 2:1 del banco se registran como salida e ingreso de distintos recursos.')
        st.markdown('**Saldos libres y reservados por etapa**')
        st.plotly_chart(figura_saldos([
            x for x in detalle['stock_por_etapa'] if
            x['Etapa'] in etapas_filtradas and x['Recurso'] in recursos_filtrados
        ]), use_container_width=True)
        st.caption('Son medias de fotografías de fin de turno por jugador/etapa, '
                   'no cifras de cierre ni medias por ronda.')
        with st.expander('Movimientos individuales y auditoría'):
            st.dataframe(pd.DataFrame(movimientos_filtrados),
                         hide_index=True, use_container_width=True)
            st.dataframe(pd.DataFrame(detalle['tabla_flujos']),
                         hide_index=True, use_container_width=True)
            st.json({'stock_final': detalle['stock_final'],
                     'errores_conciliacion': detalle['errores_conciliacion'],
                     'errores_motor': detalle['errores_motor']})
        st.info(detalle['advertencia'])
        st.download_button('Descargar auditoría económica (JSON)',
                           data=json.dumps(detalle, ensure_ascii=False, indent=2).encode('utf-8'),
                           file_name=f'economia_partida_{numero_ec}_{lado_ec.lower()}.json',
                           mime='application/json', key='descargar_economia')
    elif previo_ec is not None:
        st.caption('Cambiaste de partida o escenario. Volvé a reconstruir para actualizar los datos.')

    st.divider()
    st.subheader('6. Interacciones: Duelos, negociación, Pareja y Casa')
    st.caption('El lote completo muestra contadores por partida. Para conocer modalidad, '
               'participantes, resultado, ronda y etapa, reconstruí una partida específica '
               'con la misma semilla y compará su resultado exacto con el motor.')
    from laboratorio.interacciones import (resumen_lote_interacciones,
                                           trazar_interacciones)
    from laboratorio.graficos_interacciones import (figura_interacciones_por_tipo,
                                                    figura_interacciones_por_ronda)

    with st.expander('Interacciones agregadas de los dos escenarios'):
        tb = pd.DataFrame(resumen_lote_interacciones(baseline['filas']))
        te = pd.DataFrame(resumen_lote_interacciones(experiment['filas']))
        if not tb.empty and not te.empty:
            comp_int = tb.merge(te, on=['Métrica', 'Código'],
                                suffixes=(' base', ' experimento'))
            comp_int['Diferencia media'] = (
                comp_int['Promedio por partida experimento'] -
                comp_int['Promedio por partida base']).round(3)
            st.dataframe(comp_int.drop(columns='Código'),
                         use_container_width=True, hide_index=True)
            st.caption('Totales y promedios reales de los CSV; no se atribuyen '
                       'rondas, participantes ni causas que los CSV no registran.')

    lado_int = st.radio('Escenario de interacciones', ['Base', 'Experimento'],
                        horizontal=True, key='interacciones_lado')
    elegido_int = baseline if lado_int == 'Base' else experiment
    numero_int = st.selectbox(
        'Partida para reconstruir interacciones',
        list(range(1, len(elegido_int['filas']) + 1)),
        key='interacciones_numero',
        format_func=lambda n: (
            f"Partida {n} · semilla {elegido_int['filas'][n-1]['semilla']} "
            f"· {elegido_int['filas'][n-1]['rondas_observadas']} rondas"))
    marca_int = json.dumps({'escenario': elegido_int['escenario'],
                             'partida': numero_int}, sort_keys=True, ensure_ascii=False)
    if st.button('Reconstruir y auditar interacciones', key='interacciones_reconstruir'):
        try:
            with st.spinner('Reejecutando partida y conciliando los eventos con los contadores…'):
                detalle_int = trazar_interacciones(
                    escenario_desde_dict(elegido_int['escenario']), numero_int,
                    elegido_int['filas'][numero_int - 1])
            st.session_state['interacciones_ultimas'] = (marca_int, detalle_int)
        except Exception as exc:
            st.session_state.pop('interacciones_ultimas', None)
            st.error(f'Falló la reconstrucción de interacciones: {exc}')
    anterior_int = st.session_state.get('interacciones_ultimas')
    if anterior_int and anterior_int[0] == marca_int:
        detalle_int = anterior_int[1]
        st.success('Interacciones verificadas: cada evento y los contadores coinciden con el motor.')
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Duelos iniciados', detalle_int['duelos'])
        c2.metric('Retiradas', detalle_int['retiradas'])
        c3.metric('Defensas sin perder', detalle_int['defensas_sin_perder'])
        c4.metric('Comprobantes cedidos', detalle_int['cesiones_comprobante'])
        st.plotly_chart(figura_interacciones_por_tipo(detalle_int), use_container_width=True)
        st.plotly_chart(figura_interacciones_por_ronda(detalle_int), use_container_width=True)
        a, b = st.columns(2)
        with a:
            st.markdown('**Resultados de Duelos**')
            st.dataframe(pd.DataFrame(detalle_int['por_resultado']),
                         hide_index=True, use_container_width=True)
            st.markdown('**Modalidades de Duelo**')
            st.dataframe(pd.DataFrame(detalle_int['por_modalidad']),
                         hide_index=True, use_container_width=True)
        with b:
            st.markdown('**Duelos iniciados y recibidos por jugador**')
            st.dataframe(pd.DataFrame(detalle_int['duelos_por_jugador']),
                         hide_index=True, use_container_width=True)
            st.markdown('**Interacciones por etapa**')
            st.dataframe(pd.DataFrame(detalle_int['por_etapa']),
                         hide_index=True, use_container_width=True)
        eventos_int = detalle_int['eventos']
        categorias_int = sorted({e['categoria'] for e in eventos_int})
        filtros_int = st.multiselect('Filtrar por categorías', categorias_int,
                                     default=categorias_int,
                                     key='interacciones_categorias')
        participantes_int = st.multiselect('Filtrar por participantes',
                                           list(range(1, detalle_int['jugadores'] + 1)),
                                           default=list(range(1, detalle_int['jugadores'] + 1)),
                                           key='interacciones_jugadores')
        eventos_filtrados = [e for e in eventos_int if e['categoria'] in filtros_int and
                            any(pid in participantes_int for pid in e['participantes'])]
        st.dataframe(pd.DataFrame([{
            'Ronda': e['ronda'], 'Turno': e['turno'], 'Tipo': e['tipo'],
            'Categoría': e['categoria'], 'Jugadores': ', '.join(map(str,e['participantes'])),
            'Modalidad': e['modalidad'], 'Resultado': e['resultado'],
            'Detalles': json.dumps(e['detalle'], ensure_ascii=False)
        } for e in eventos_filtrados]), hide_index=True, use_container_width=True)
        st.info(detalle_int['advertencia'])
        st.download_button('Descargar auditoría de interacciones (JSON)',
                           data=json.dumps(detalle_int, ensure_ascii=False, indent=2).encode('utf-8'),
                           file_name=f'interacciones_partida_{numero_int}_{lado_int.lower()}.json',
                           mime='application/json', key='descargar_interacciones')
    elif anterior_int is not None:
        st.caption('Cambiaste de partida o escenario. Reconstruí la partida para actualizar el detalle.')

    st.divider()
    st.subheader('7. Actividad de turnos y oportunidades detectadas')
    st.caption('Medición descriptiva de bots: distingue desenlaces automáticos, '
               'acciones ejecutadas y familias de acciones disponibles en checkpoints. '
               'No es una puntuación de diversión, calidad o profundidad estratégica.')
    from laboratorio.turnos import trazar_turnos
    from laboratorio.graficos_turnos import figura_etapas, figura_familias

    lado_turno = st.radio('Escenario de actividad', ['Base', 'Experimento'],
                          horizontal=True, key='turnos_lado')
    elegido_turno = baseline if lado_turno == 'Base' else experiment
    numero_turno = st.selectbox(
        'Partida para auditar turnos',
        list(range(1, len(elegido_turno['filas']) + 1)),
        key='turnos_numero',
        format_func=lambda n: (
            f"Partida {n} · semilla {elegido_turno['filas'][n-1]['semilla']} "
            f"· {elegido_turno['filas'][n-1]['turnos_individuales']} turnos"))
    marca_turno = json.dumps({'escenario': elegido_turno['escenario'],
                               'partida': numero_turno},sort_keys=True,ensure_ascii=False)
    if st.button('Reconstruir actividad de turnos', key='turnos_reconstruir'):
        try:
            with st.spinner('Auditando decisiones, eventos y checkpoints de oportunidades…'):
                detalle_turno = trazar_turnos(
                    escenario_desde_dict(elegido_turno['escenario']), numero_turno,
                    elegido_turno['filas'][numero_turno - 1])
                if detalle_turno['errores_auditoria'] or detalle_turno['errores_motor']:
                    raise AssertionError(str(detalle_turno['errores_auditoria'] + detalle_turno['errores_motor']))
            st.session_state['turnos_ultimos'] = (marca_turno, detalle_turno)
        except Exception as exc:
            st.session_state.pop('turnos_ultimos', None)
            st.error(f'Falló la auditoría de turnos: {exc}')
    previo_turno = st.session_state.get('turnos_ultimos')
    if previo_turno is not None and previo_turno[0] == marca_turno:
        dt = previo_turno[1]
        st.success('Actividad validada: los contadores por decisión y el resultado coinciden con el motor.')
        a1,a2,a3,a4 = st.columns(4)
        a1.metric('Turnos individuales', dt['turnos'])
        a2.metric('Con alguna decisión de bot',dt['turnos_con_decision'])
        a3.metric('Sin decisión registrada',dt['turnos_solo_automaticos'])
        a4.metric('Familias disponibles por turno',dt['familias_disponibles_por_turno'])
        st.plotly_chart(figura_etapas(dt), use_container_width=True)
        st.plotly_chart(figura_familias(dt), use_container_width=True)
        st.caption('Cada barra compara turnos con una familia de acción disponible y '
                   'turnos donde hubo alguna ejecución o resolución de esa familia. '
                   'No cuenta todas las jugadas legales ni registra intentos rechazados.')
        x1,x2=st.columns(2)
        with x1:
            st.markdown('**Actividad por etapa al comenzar el turno**')
            st.dataframe(pd.DataFrame(dt['por_etapa']),hide_index=True,use_container_width=True)
        with x2:
            st.markdown('**Actividad por política de bot**')
            st.dataframe(pd.DataFrame(dt['por_bot']),hide_index=True,use_container_width=True)
        jugadores_turnos = st.multiselect('Jugadores del detalle',
                                          list(range(1, dt['jugadores']+1)),
                                          default=list(range(1,dt['jugadores']+1)),
                                          key='turnos_jugadores')
        etapas_turnos = st.multiselect('Etapas al comenzar el turno',
                                       sorted({t['etapa_inicio'] for t in dt['turnos_detalle']}),
                                       default=sorted({t['etapa_inicio'] for t in dt['turnos_detalle']}),
                                       key='turnos_etapas')
        filtrados = [t for t in dt['turnos_detalle'] if t['jugador'] in jugadores_turnos
                     and t['etapa_inicio'] in etapas_turnos]
        st.dataframe(pd.DataFrame([{
            'Ronda':t['ronda'],'Turno':t['turno'],'Jugador':t['jugador'],
            'Etapa':t['etapa_inicio'],'Bot':t['bot'],
            'Familias disponibles':t['familias_disponibles'],
            'Decisiones':t['decisiones_ejecutadas'],
            'Eventos automáticos':t['eventos_automaticos'],
            'Oportunidades':', '.join(t['oportunidades']),
            'Acciones de bot':', '.join(t['decisiones'])
        } for t in filtrados]),hide_index=True,use_container_width=True)
        st.info(dt['advertencia'])
        st.download_button('Descargar actividad de turnos (JSON)',
                           data=json.dumps(dt,ensure_ascii=False,indent=2).encode('utf-8'),
                           file_name=f'turnos_partida_{numero_turno}_{lado_turno.lower()}.json',
                           mime='application/json',key='descargar_turnos')
    elif previo_turno is not None:
        st.caption('Cambiaste de partida o escenario. Reconstruí la actividad para actualizar el panel.')

# Fase 6: interfaz independiente; permite explorar incluso sin correr el A/B principal.
from laboratorio.panel_sensibilidad import mostrar as mostrar_sensibilidad
mostrar_sensibilidad(st, correr, ROOT)
