"""Gráficos económicos Fase 4.2. No contiene ni altera reglas."""
from __future__ import annotations
from collections import defaultdict
import plotly.graph_objects as go

RECURSO_NOMBRE = {'A': 'Amor', 'P': 'Personalidad', 'K': 'Conocimiento', 'M': 'Dinero'}


def resumen_lote(filas: list[dict]) -> list[dict]:
    """Flujos de los CSV originales (por fuente y recurso, SIN asignación por etapa)."""
    if not filas:
        return []
    acum = defaultdict(float)
    for fila in filas:
        for k, valor in fila.items():
            if not k.startswith('flujo_') or valor in ('', None):
                continue
            cuerpo = k[len('flujo_'):]
            if '_' not in cuerpo:
                continue
            fuente, r = cuerpo.rsplit('_', 1)
            if r not in RECURSO_NOMBRE:
                continue
            acum[(r, fuente)] += float(valor)
    return [
        {'Recurso': RECURSO_NOMBRE[r], 'Código': r, 'Fuente': fuente,
         'Fichas medias por partida': round(total/len(filas), 3)}
        for (r, fuente), total in sorted(acum.items())]


def figura_flujos(rows: list[dict], *, etapas: list[str] | None = None,
                  jugadores: list[int] | None = None) -> go.Figure:
    """Entradas arriba y salidas abajo; transferencias se muestran por separado."""
    filtrados = [x for x in rows
                 if (etapas is None or x['etapa'] in etapas)
                 and (jugadores is None or x['jugador'] in jugadores)]
    acum = defaultdict(int)
    for x in filtrados:
        clase = x['clase']
        if clase == 'transferencia':
            clase = 'transferencia recibida' if x['delta'] > 0 else 'transferencia enviada'
        acum[(x['recurso'], clase, x['fuente'])] += x['delta']
    fig = go.Figure()
    grupos = sorted({(clase, fuente) for _, clase, fuente in acum})
    for clase, fuente in grupos:
        valores = [acum[(r, clase, fuente)] for r in RECURSO_NOMBRE]
        if not any(valores):
            continue
        fig.add_bar(name=f'{clase} · {fuente}', x=list(RECURSO_NOMBRE.values()),
                    y=valores, hovertemplate='%{x}: %{y:+} fichas<extra>%{fullData.name}</extra>')
    fig.update_layout(barmode='relative', xaxis_title='Recurso', yaxis_title='Variación de fichas',
                      legend_title='Clase y origen', height=450)
    return fig


def figura_saldos(stock_etapas: list[dict]) -> go.Figure:
    """Stock medio observado vs libre/reservado; no confundir con cierre."""
    fig = go.Figure()
    estados = [('Libre medio', '#4682B4'),
               ('Reservado pareja medio', '#AD87BE'),
               ('Reservado casa medio', '#D49F55')]
    categorias = [f"{x['Etapa']} · {RECURSO_NOMBRE.get(x['Recurso'], x['Recurso'])}"
                  for x in stock_etapas]
    for columna, color in estados:
        fig.add_bar(name=columna, x=categorias,
                    y=[x[columna] for x in stock_etapas], marker_color=color)
    fig.update_layout(barmode='stack', xaxis_title='Etapa y recurso',
                      yaxis_title='Fichas medias por jugador y fin de turno',
                      height=475, xaxis_tickangle=-35)
    return fig
