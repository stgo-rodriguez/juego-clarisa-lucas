"""Vista Streamlit de Fase 6, aislada de los módulos de estadísticas."""
from __future__ import annotations

import json
from pathlib import Path

from laboratorio.archivo_sensibilidad import (exportar_grilla, importar_grilla,
                                              guardar_grilla, listar_grillas, leer_grilla)
from laboratorio.graficos_sensibilidad import mapa_sensibilidad, tabla_grilla
from laboratorio.sensibilidad import (GridConfig, LIMITE_PARTIDAS, PARAMETROS,
                                     ejecutar_grilla)
from laboratorio.comparacion import signature


def mostrar(st, ejecutar, raiz: Path) -> None:
    st.divider()
    st.subheader('8. Sensibilidad e incertidumbre · Fase 6')
    st.caption('Explorá simultáneamente dos variables económicas con semillas comunes. '
               'El resultado estima el comportamiento de los bots, no de jugadores humanos.')

    campos = list(PARAMETROS)
    with st.form('config_grilla'):
        left, right = st.columns(2)
        with left:
            x = st.selectbox('Variable del eje horizontal', campos, index=1,
                             format_func=lambda v: PARAMETROS[v], key='sensi_x')
            allowed_x = [0,100] if x in ('juventud_pct','adultez_pct') else list(range(50,151,10))
            default_x = [0,100] if x in ('juventud_pct','adultez_pct') else [90,100,110]
            vx = st.multiselect('Valores eje horizontal (%)', options=allowed_x,
                                default=default_x, key='sensi_valores_x')
            num_players = st.selectbox('Jugadores de la grilla', [6,10], key='sensi_jugadores')
            partidas = st.selectbox('Partidas por celda', [20,50,100], index=0,
                                   key='sensi_partidas')
        with right:
            y = st.selectbox('Variable del eje vertical', campos, index=2,
                             format_func=lambda v: PARAMETROS[v], key='sensi_y')
            allowed_y = [0,100] if y in ('juventud_pct','adultez_pct') else list(range(50,151,10))
            default_y = [0,100] if y in ('juventud_pct','adultez_pct') else [90,100,110]
            vy = st.multiselect('Valores eje vertical (%)', options=allowed_y,
                                default=default_y, key='sensi_valores_y')
            seed = st.number_input('Semilla inicial de grilla', min_value=0,
                                   max_value=2_000_000_000, value=131028 if num_players==6 else 231028,
                                   step=1, key='sensi_seed')
            max_rondas = st.number_input('Horizonte (rondas)', min_value=10,max_value=500,
                                         value=120,step=10,key='sensi_horizonte')
            bot = st.selectbox('Bots de la grilla', ['mixed','inversor','oportunista',
                                                    'planificador','competitivo','cooperativo'],
                               key='sensi_bot')
        n = len(vx) * len(vy)
        st.caption(f'{n} celdas · hasta {(n+1)*partidas:,} simulaciones contando la base · '
                   f'límite {LIMITE_PARTIDAS:,}. Usá 20 partidas para explorar; 100 para confirmar.')
        submit = st.form_submit_button('Ejecutar matriz de sensibilidad', type='primary')
    if submit:
        try:
            cfg = GridConfig(jugadores=num_players, partidas=partidas, seed=int(seed),
                             max_rondas=int(max_rondas), bot=bot,
                             parametro_x=x, valores_x=tuple(sorted(vx)),
                             parametro_y=y, valores_y=tuple(sorted(vy)))
            progress = st.progress(0, text='Preparando escenario base…')
            with st.spinner('Simulando celdas y calculando intervalos de confianza apareados…'):
                grid = ejecutar_grilla(cfg, ejecutar,
                    progreso=lambda count, total: progress.progress(count/total,
                                         text=f'Celdas completadas: {count}/{total}'))
            progress.empty()
            st.session_state['sensibilidad_resultado'] = grid
            st.success(f'Matriz completada: {grid["n_celdas"]} escenarios con semillas comunes.')
        except Exception as exc:
            st.error(f'No se pudo ejecutar la matriz: {exc}')

    folder = raiz / '.laboratorio' / 'sensibilidad'
    with st.expander('Recuperar una exploración guardada o importar ZIP'):
        saved = listar_grillas(folder)
        if saved:
            name = st.selectbox('Exploraciones guardadas', [p.name for p in saved], key='sensi_historial')
            if st.button('Recuperar matriz sin simular', key='sensi_recuperar'):
                try:
                    st.session_state['sensibilidad_resultado'] = leer_grilla(folder, name)
                    st.success('Matriz recuperada sin ejecutar partidas.')
                except Exception as exc:
                    st.error(f'No se pudo recuperar la matriz: {exc}')
        upload = st.file_uploader('Importar matriz de sensibilidad (ZIP)',
                                  type=['zip'], key='sensi_importar')
        if upload is not None and st.button('Validar ZIP e importar matriz', key='sensi_validar'):
            try:
                st.session_state['sensibilidad_resultado'] = importar_grilla(upload.getvalue())
                st.success('Matriz importada sin ejecutar simulaciones.')
            except Exception as exc:
                st.error(f'Archivo de sensibilidad rechazado: {exc}')

    grid = st.session_state.get('sensibilidad_resultado')
    if grid is None:
        st.info('Configurá dos variables y ejecutá la matriz; también podés recuperar un ZIP guardado.')
        return

    if grid['motor'] != signature():
        st.warning('Los resultados fueron generados con otra versión del motor/mazo/economía. '
                   'Se muestran como documento histórico; no se reejecutan ni se mezclan automáticamente.')

    has_censor = any(c['censuradas_base'] or c['censuradas_variante']
                     for c in grid['celdas'])
    st.markdown('**Mapa de calor: cambio medio de rondas observadas respecto de la base**')
    st.plotly_chart(mapa_sensibilidad(grid), use_container_width=True)
    st.caption('Valores positivos: más rondas observadas hasta el horizonte. '
               'Los IC95 se estiman con bootstrap de pares de semillas independientes del RNG del juego.')
    if has_censor:
        st.warning('Hay partidas censuradas: la media de rondas observadas está restringida '
                   'al horizonte. NO representa el tiempo medio final hasta el casamiento. '
                   'La tabla informa la censura y el cambio de finalización por separado.')
    else:
        st.caption('Ninguna celda presenta censura. Las rondas observadas coinciden con rondas hasta el casamiento.')

    st.dataframe(tabla_grilla(grid), hide_index=True, use_container_width=True)
    st.caption('Los IC95 son exploratorios, sin corrección por comparaciones múltiples. '
               'Los cuantiles (mediana/P90) se calculan solo entre partidas concluidas.')
    z = exportar_grilla(grid)
    a,b = st.columns(2)
    with a:
        st.download_button('Descargar matriz y estadísticas (ZIP)', data=z,
                           file_name='sensibilidad_clarisa_lucas.zip',
                           mime='application/zip', key='sensi_descargar')
    with b:
        if st.button('Guardar matriz en este equipo', key='sensi_guardar'):
            try:
                path = guardar_grilla(folder,z,
                    nombre=f'Grilla-{grid["configuracion"]["jugadores"]}j')
                st.success(f'Matriz guardada: {path.name}')
            except Exception as exc:
                st.error(f'No se pudo guardar: {exc}')
    with st.expander('Método, configuraciones y firmas reproducibles'):
        st.json({'configuracion':grid['configuracion'], 'motor':grid['motor'],
                 'metodo':grid['metodo']})
