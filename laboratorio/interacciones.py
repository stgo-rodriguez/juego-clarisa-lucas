"""Fase 4.3: observador pasivo de interacciones v1.3.

Una reejecución con la semilla exacta. Solo captura eventos que el motor emite;
no cambia las reglas, dados, políticas ni secuencia RNG. No infiere ofertas
rechazadas, oportunidades legales o negociaciones humanas inexistentes.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from laboratorio.ejecucion import CARDS
from laboratorio.trazabilidad import JuegoObservado
from simulador.economia import ScenarioConfig
from simulador.motor import parse_cards

# El evento del motor es la fuente de verdad. El tipo forma parte del esquema.
TIPOS = {
    'duelo': ('Duelo', 'Conflicto'),
    'duelo_retirada': ('Retirada de duelo', 'Conflicto'),
    'venta_comprobante': ('Cesión de comprobante', 'Negociación'),
    'intercambio_recursos': ('Intercambio de recursos', 'Negociación'),
    'transferencia_hito': ('Transferencia de hito', 'Negociación'),
    'formacion_pareja': ('Formación de pareja', 'Pareja'),
    'ruptura': ('Ruptura de pareja', 'Pareja'),
    'transfer_pair': ('Ayuda automática entre pareja', 'Redistribución'),
    'compra_casa': ('Compra o transferencia de Casa', 'Casa'),
    'perdida_casa': ('Pérdida de Casa', 'Casa'),
}

# Algunos eventos tienen dos jugadores y otros a una pareja completa.
PARTICIPANTES = {
    'duelo': ('retador', 'defensor'),
    'duelo_retirada': ('retador', 'defensor'),
    'venta_comprobante': ('desde', 'hacia'),
    'intercambio_recursos': ('jugadores',),
    'transferencia_hito': ('desde', 'hacia'),
    'formacion_pareja': ('jugadores',),
    'ruptura': ('jugadores',),
    'transfer_pair': ('desde', 'hacia'),
    'compra_casa': ('pareja', 'expropietarios'),
    'perdida_casa': ('propietarios',),
}


def _personas(payload: dict, tipo: str) -> list[int]:
    resultado = []
    for campo in PARTICIPANTES[tipo]:
        valor = payload.get(campo)
        if isinstance(valor, (tuple, list)):
            resultado.extend(int(x) for x in valor)
        elif valor is not None:
            resultado.append(int(valor))
    return list(dict.fromkeys(resultado))


def _resultado_duelo(tipo: str, datos: dict) -> str | None:
    if tipo == 'duelo_retirada':
        return 'Retirada del retador'
    if tipo != 'duelo':
        return None
    a, b = datos['dado_retador'], datos['dado_defensor']
    if a > b:
        return 'Gana retador'
    if a < b:
        return 'Gana defensor'
    return 'Empate'


class JuegoInteracciones(JuegoObservado):
    """Registra eventos reales, incluso si el juego fue creado con log=False."""

    def __init__(self, *args, **kwargs):
        self.interacciones: list[dict] = []
        super().__init__(*args, **kwargs)

    def event(self, action, **kwargs):
        super().event(action, **kwargs)
        if action not in TIPOS:
            return
        detalles = deepcopy(kwargs)
        participantes = _personas(detalles, action)
        actores = {str(i): {'personaje': self.p(i).role, 'etapa': self.p(i).stage}
                   for i in participantes}
        e = {
            'secuencia': len(self.interacciones) + 1,
            'partida': self.id, 'semilla': self.seed,
            'ronda': self.round, 'turno': self.turn,
            'evento': action, 'tipo': TIPOS[action][0], 'categoria': TIPOS[action][1],
            'participantes': participantes, 'actores': actores,
            'modalidad': detalles.get('modalidad'),
            'resultado': _resultado_duelo(action, detalles),
            'es_traspaso_casa': bool(detalles.get('expropietarios')) if action == 'compra_casa' else False,
            'detalle': detalles,
        }
        self.interacciones.append(e)


def resumen_interacciones(juego: JuegoInteracciones) -> dict:
    """Resumen y auditoría contra contadores independientes del motor."""
    registros = juego.interacciones
    por_evento = Counter(e['evento'] for e in registros)
    por_modalidad = Counter(e['modalidad'] for e in registros if e['evento'] in ('duelo', 'duelo_retirada'))
    por_resultado = Counter(e['resultado'] for e in registros if e['resultado'])
    por_categoria = Counter(e['categoria'] for e in registros)
    por_etapa = Counter()
    por_ronda = Counter()
    por_jugador = Counter()
    duelos_por_jugador = Counter()
    for e in registros:
        # La etapa se toma del primer participante en el instante del evento.
        etapa = e['actores'].get(str(e['participantes'][0]), {}).get('etapa', 'No atribuible') if e['participantes'] else 'No atribuible'
        por_etapa[(etapa, e['categoria'])] += 1
        por_ronda[(e['ronda'], e['categoria'])] += 1
        for pid in e['participantes']:
            por_jugador[(pid, e['categoria'])] += 1
        if e['evento'] in ('duelo', 'duelo_retirada'):
            duelos_por_jugador[(e['detalle']['retador'], 'Iniciados')] += 1
            duelos_por_jugador[(e['detalle']['defensor'], 'Recibidos')] += 1

    defensas = por_resultado['Gana defensor'] + por_resultado['Empate']
    retiradas = por_evento['duelo_retirada']
    duelos = por_evento['duelo'] + retiradas
    auditoria = {
        'duels_started': duelos,
        'duels_won': por_resultado['Gana retador'],
        'duels_lost': por_resultado['Gana defensor'],
        'duels_tied': por_resultado['Empate'],
        'duel_retreats': retiradas,
        'receipts_traded': por_evento['venta_comprobante'],
        'resource_trades': por_evento['intercambio_recursos'],
        'hitos_traded': por_evento['transferencia_hito'],
        'rupturas': por_evento['ruptura'],
        'pair_formed': por_evento['formacion_pareja'],
        'house_bought': por_evento['compra_casa'],
        'house_transfers': sum(e['es_traspaso_casa'] for e in registros),
        'transfer_pair': por_evento['transfer_pair'],
    }
    auditoria.update({f'house_lost_{causa}': sum(e['evento'] == 'perdida_casa' and
                        e['detalle'].get('causa') == causa for e in registros)
                      for causa in set(x['detalle'].get('causa') for x in registros
                                       if x['evento'] == 'perdida_casa')})
    auditoria.update({f'duel_{kind}': n for kind, n in por_modalidad.items()})
    errores = [f'{k}: eventos={v}, motor={juego.stats.get(k,0)}'
               for k, v in auditoria.items() if v != juego.stats.get(k, 0)]
    # Esta identidad evita confundir retiradas con duelos resueltos por dos dados.
    if sum(por_resultado.values()) != duelos:
        errores.append('Desglose de resultados no conserva total de duelos')
    if sum(por_evento.values()) != len(registros):
        errores.append('Desglose de eventos no conserva total de registros')

    return {
        'partida': juego.id, 'semilla': juego.seed, 'jugadores': len(juego.players),
        'finalizada': bool(juego.finished), 'rondas_observadas': juego.round,
        'eventos': registros,
        'por_tipo': [{'Evento': TIPOS[k][0], 'Código': k, 'Categoría': TIPOS[k][1], 'Cantidad': v}
                     for k, v in sorted(por_evento.items())],
        'por_modalidad': [{'Modalidad': k, 'Cantidad': v} for k, v in sorted(por_modalidad.items())],
        'por_resultado': [{'Resultado': k, 'Cantidad': v} for k, v in sorted(por_resultado.items())],
        'por_categoria': [{'Categoría': k, 'Cantidad': v} for k,v in sorted(por_categoria.items())],
        'por_etapa': [{'Etapa': k[0], 'Categoría': k[1], 'Cantidad': v}
                      for k, v in sorted(por_etapa.items())],
        'por_ronda': [{'Ronda': k[0], 'Categoría': k[1], 'Cantidad': v}
                      for k, v in sorted(por_ronda.items())],
        'por_jugador': [{'Jugador': k[0], 'Categoría': k[1], 'Cantidad': v}
                        for k,v in sorted(por_jugador.items())],
        'duelos_por_jugador': [{'Jugador': k[0], 'Rol': k[1], 'Cantidad': v}
                              for k,v in sorted(duelos_por_jugador.items())],
        'total_eventos': len(registros), 'duelos': duelos,
        'retiradas': retiradas, 'defensas_sin_perder': defensas,
        'duelos_ganados_retador': por_resultado['Gana retador'],
        'cesiones_comprobante': por_evento['venta_comprobante'],
        'traspasos_casa': sum(e['es_traspaso_casa'] for e in registros),
        'auditoria_contadores': auditoria,
        'errores_auditoria': errores, 'errores_motor': list(juego.errors),
        'advertencia': ('Solo acciones que generaron eventos efectivos del motor. '
                        'No mide ofertas rechazadas, oportunidades legales ni negociaciones humanas. '
                        'La ayuda automática entre integrantes de una pareja se identifica por separado. '
                        '«Gana defensor» significa que el dado defensor superó al retador; '
                        'los empates se cuentan como defensas sin pérdida del duelo.'),
    }


def trazar_interacciones(config: ScenarioConfig, numero: int, fila_esperada: dict | None = None) -> dict:
    """Reejecuta solo una partida y contrasta su fila exacta con el lote original."""
    if not 1 <= numero <= config.partidas:
        raise ValueError(f'Partida fuera del intervalo 1..{config.partidas}: {numero}')
    semilla = config.seed + (numero - 1) * config.incremento_seed
    juego = JuegoInteracciones(numero, semilla, config.jugadores, parse_cards(CARDS),
                               log=False, max_rounds=config.max_rondas,
                               bot_mode=config.bot, economia=config.economia).run()
    if fila_esperada is not None and juego.summary() != fila_esperada:
        divergencias = [k for k in set(juego.summary()) | set(fila_esperada)
                        if juego.summary().get(k) != fila_esperada.get(k)]
        raise AssertionError(f'Interacciones divergentes en partida {numero}: {divergencias[:10]}')
    r = resumen_interacciones(juego)
    if r['errores_auditoria'] or r['errores_motor']:
        raise AssertionError(f'Interacciones sin conciliar: {r["errores_auditoria"][:8]} {r["errores_motor"][:8]}')
    r['equivalencia_fila'] = fila_esperada is not None
    r['alcance'] = 'Registro detallado de una partida por semilla, verificado contra su CSV de lote.'
    return r


def resumen_lote_interacciones(filas: list[dict]) -> list[dict]:
    """Agrega solamente métricas que el CSV verdaderamente contiene."""
    fuentes = {
        'duels_started': 'Duelos iniciados',
        'duel_retreats': 'Retiradas del retador',
        'duels_won': 'Duelos ganados por retador',
        'duels_lost': 'Duelos ganados por defensor',
        'duels_tied': 'Duelos empatados',
        'receipts_traded': 'Comprobantes cedidos',
        'resource_trades': 'Intercambios de recursos',
        'hitos_traded': 'Transferencias de hitos',
        'rupturas': 'Rupturas de pareja',
        'pair_formed': 'Parejas formadas',
        'house_transfers': 'Transferencias de Casa',
        'house_bought': 'Compras de Casa',
        'transfer_pair': 'Ayudas automáticas de pareja',
    }
    if not filas:
        return []
    total = len(filas)
    return [{'Métrica': nombre, 'Código': codigo,
             'Promedio por partida': round(sum(float(x.get(codigo, 0)) for x in filas) / total, 3),
             'Total': int(sum(int(x.get(codigo, 0)) for x in filas))}
            for codigo, nombre in fuentes.items()]
