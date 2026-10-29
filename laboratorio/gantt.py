"""Cronología de hitos: vista legible de logros y vista de vigencia (sin reglas).

Un hito es un evento puntual; una barra de *vigencia* muestra propiedad/estado.
Nunca se representa la barra de vigencia como duración necesaria para obtenerlo.
"""
from __future__ import annotations

from collections import defaultdict

import plotly.graph_objects as go

PALETA = {
    'Individual': '#5D92CF', 'Pareja': '#9A81BD',
    'Afinidad': '#44A89A', 'Casa': '#CB9658', 'Final': '#499D62',
}

PALETA_JUGADOR = ('#3979B4', '#D18B35')
COLOR_PAREJA = '#8061AB'
COLOR_FINAL = '#32946D'
COLOR_PERDIDA = '#BF4653'


def _filas(cronologia: dict) -> list[dict]:
    """Filas ordenadas por jugador, logros compartidos y final.

    No calcula nuevos hitos: utiliza exclusivamente los episodios observados.
    """
    hitos = {h['Hito']: h for h in cronologia.get('hitos', [])}
    ganadores = cronologia.get('ganadores', [])
    periodos = cronologia.get('periodos', [])
    by_key = defaultdict(list)
    for p in periodos:
        by_key[p['clave']].append(p)
    for episodios in by_key.values():
        episodios.sort(key=lambda x: (x['x_inicio'], x['turno_inicio']))

    filas = []
    posiciones = [14, 13, 12, 10, 9, 8, 6, 5, 4, 3, 2, 0]
    for i, ganador in enumerate(ganadores[:2]):
        pid = ganador['id']
        nombre = f"{ganador['personaje']} #{pid}"
        for tipo, clave in [('Ingreso UTN', 'utn'), ('Título', 'titulo'),
                            ('Pasaporte', 'pasaporte')]:
            k = f'{clave}_{pid}'
            filas.append(dict(pos=posiciones[len(filas)], clave=k, etiqueta=tipo,
                              grupo=nombre, color=PALETA_JUGADOR[i],
                              episodios=by_key[k]))
    compartidos = [
        ('Pareja formada', 'pareja'),
        ('Ambos: Título + Pasaporte', 'ambos_hitos'),
        ('Afinidad compatible', 'afinidad'),
        ('Entrada en Adultez', 'adultez'),
        ('Casa en propiedad', 'casa'),
        ('Casamiento', 'casamiento'),
    ]
    for etiqueta, clave in compartidos:
        filas.append(dict(pos=posiciones[len(filas)], clave=clave, etiqueta=etiqueta,
                          grupo='Pareja' if clave != 'casamiento' else 'Final',
                          color=COLOR_PAREJA if clave != 'casamiento' else COLOR_FINAL,
                          episodios=by_key[clave]))
    return filas


def grafico_gantt(cronologia: dict) -> go.Figure:
    """Vista principal: cuándo se alcanzó cada hito, no cuánto tiempo se tuvo.

    Punto relleno = primera obtención; rombo hueco = recuperación;
    cruz roja = pérdida entre episodios. La posición distingue turnos
    dentro de una misma ronda; el tooltip informa ronda/turno exactos.
    """
    fig = go.Figure()
    if not cronologia.get('finalizada') or not cronologia.get('periodos'):
        fig.add_annotation(text='Esta partida no tiene una pareja ganadora que representar',
                           x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False)
        fig.update_layout(height=260)
        return fig

    filas = _filas(cronologia)
    final = int(cronologia['ronda_casamiento'])
    limite = max(final + 1.5, 12)
    # Separadores suaves: tres bloques claramente identificables.
    for minimo, maximo, fondo in [(11.3, 14.55, 'rgba(57,121,180,.045)'),
                                  (7.3, 10.55, 'rgba(209,139,53,.055)'),
                                  (1.3, 6.55, 'rgba(128,97,171,.045)')]:
        fig.add_hrect(y0=minimo, y1=maximo, fillcolor=fondo, line_width=0, layer='below')
    for y in [11.25, 7.25, 1.25]:
        fig.add_hline(y=y, line_color='#BBC2CD', line_width=1, opacity=0.65)

    groups = {}
    recoveries = []
    losses = []
    for fila in filas:
        episodios = fila['episodios']
        if not episodios:
            continue
        grupo = fila['grupo']
        if grupo not in groups:
            groups[grupo] = {'x': [], 'y': [], 'text': [], 'customdata': [],
                             'color': fila['color']}
        first = episodios[0]
        x = first['x_inicio']
        groups[grupo]['x'].append(x)
        groups[grupo]['y'].append(fila['pos'])
        groups[grupo]['text'].append(f"R{first['ronda_inicio']}")
        groups[grupo]['customdata'].append([
            fila['etiqueta'], first['ronda_inicio'], first['turno_inicio'], grupo])
        for epi in episodios[1:]:
            recoveries.append((epi, fila))
        for epi in episodios[:-1]:
            losses.append((epi, fila))

    for grupo, d in groups.items():
        fig.add_trace(go.Scatter(
            name=grupo, x=d['x'], y=d['y'], mode='markers+text',
            marker=dict(symbol='circle', size=15, color=d['color'],
                        line=dict(color='white', width=1.3)),
            text=d['text'], textposition=['middle left' if x >= final - 3 else 'middle right'
                                         for x in d['x']],
            textfont=dict(size=11, color='#2F3640'),
            customdata=d['customdata'],
            hovertemplate=('<b>%{customdata[0]} · %{customdata[3]}</b>'
                           '<br>Primera obtención: ronda %{customdata[1]}'
                           '<br>Turno absoluto: %{customdata[2]}<extra></extra>'),
            cliponaxis=False,
        ))

    if recoveries:
        fig.add_trace(go.Scatter(
            name='Recuperación', mode='markers+text',
            x=[e['x_inicio'] for e, f in recoveries],
            y=[f['pos'] for e, f in recoveries],
            text=[f"R{e['ronda_inicio']}" for e, f in recoveries],
            textposition=['middle left' if e['x_inicio'] >= final - 3 else 'middle right'
                          for e, f in recoveries],
            textfont=dict(size=11, color='#2F3640'),
            marker=dict(symbol='diamond-open', size=16, color=COLOR_FINAL,
                        line=dict(width=2.5)),
            customdata=[[f['etiqueta'], e['ronda_inicio'], e['turno_inicio']]
                        for e, f in recoveries],
            hovertemplate=('<b>Recuperación · %{customdata[0]}</b>'
                           '<br>Ronda %{customdata[1]} · turno %{customdata[2]}'
                           '<extra></extra>'),
            cliponaxis=False,
        ))
    if losses:
        fig.add_trace(go.Scatter(
            name='Pérdida / ruptura', mode='markers',
            x=[e['x_fin'] for e, f in losses], y=[f['pos'] for e, f in losses],
            marker=dict(symbol='x', size=13, color=COLOR_PERDIDA,
                        line=dict(width=2)),
            customdata=[[f['etiqueta'], e['ronda_fin'], e['turno_fin']]
                        for e, f in losses],
            hovertemplate=('<b>Pérdida · %{customdata[0]}</b>'
                           '<br>Ronda %{customdata[1]} · turno %{customdata[2]}'
                           '<extra></extra>'),
        ))

    fig.add_vline(x=final, line_color=COLOR_FINAL, line_width=2, line_dash='dot')
    fig.add_annotation(x=final, y=15.05, text=f'CASAMIENTO · R{final}',
                       showarrow=False, font=dict(size=12, color=COLOR_FINAL),
                       xanchor='right', yanchor='bottom')
    fig.update_layout(
        title=dict(text='¿En qué ronda alcanzaron cada hito?', x=0, xanchor='left'),
        height=650, hovermode='closest',
        legend=dict(orientation='h', x=0, y=-0.13, yanchor='top',
                    title=None, font=dict(size=11)),
        xaxis=dict(title='Ronda de juego', range=[0, limite],
                   tickmode='linear', dtick=2 if final <= 30 else (5 if final <= 80 else 10),
                   showline=True, showgrid=True, gridcolor='#E2E6EB', zeroline=False),
        yaxis=dict(tickmode='array', tickvals=[r['pos'] for r in filas],
                   ticktext=[r['etiqueta'] for r in filas],
                   range=[-0.8, 15.8], showgrid=False, zeroline=False,
                   tickfont=dict(size=12)),
        margin=dict(l=190, r=50, t=90, b=95),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    )
    # Títulos visibles de cada bloque, sin depender de la leyenda inferior.
    for y, titulo, color in [(14.85, f"{filas[0]['grupo']}", PALETA_JUGADOR[0]),
                             (10.85, f"{filas[3]['grupo']}", PALETA_JUGADOR[1]),
                             (6.85, 'PAREJA Y FINAL', COLOR_PAREJA)]:
        fig.add_annotation(x=0, y=y, text=f'<b>{titulo}</b>',
                           showarrow=False, xanchor='left',
                           font=dict(size=12, color=color))
    return fig


def grafico_vigencia(cronologia: dict) -> go.Figure:
    """Vista secundaria: episodios de posesión, nunca tiempos de ejecución del hito."""
    fig = go.Figure()
    periodos = cronologia.get('periodos') or []
    hitos = cronologia.get('hitos') or []
    if not cronologia.get('finalizada') or not periodos:
        fig.add_annotation(text='No hay períodos de vigencia para esta partida',
                           x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False)
        fig.update_layout(height=260)
        return fig
    for grupo, color in PALETA.items():
        sub = [p for p in periodos if p['grupo'] == grupo]
        if not sub:
            continue
        fig.add_trace(go.Bar(
            name=grupo, orientation='h', y=[p['hito'] for p in sub],
            x=[p['x_fin']-p['x_inicio'] for p in sub],
            base=[p['x_inicio'] for p in sub], marker_color=color,
            customdata=[[p['ronda_inicio'], p['turno_inicio'],
                         p['ronda_fin'], p['turno_fin']] for p in sub],
            hovertemplate=('<b>%{y}</b><br>Desde ronda %{customdata[0]}, turno %{customdata[1]}'
                           '<br>Hasta ronda %{customdata[2]}, turno %{customdata[3]}'
                           '<extra></extra>'),
        ))
    fig.update_layout(title='Períodos de vigencia de los hitos (detalle técnico)',
                      height=max(430, 38 * len(hitos) + 110),
                      barmode='overlay', bargap=0.4, legend_title='Tipo de hito',
                      xaxis_title='Ronda (progresión dentro del turno)',
                      yaxis_title='', margin=dict(l=20, r=20, t=65, b=40))
    fig.update_yaxes(categoryorder='array',
                     categoryarray=list(reversed([h['Hito'] for h in hitos])))
    fig.update_xaxes(range=[0, cronologia['ronda_casamiento'] + 1], dtick=5)
    fig.add_vline(x=cronologia['ronda_casamiento'], line_dash='dot',
                  line_color='#777777', opacity=0.55)
    return fig
