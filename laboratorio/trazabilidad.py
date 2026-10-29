"""Fase 4.1 — cronología de una partida, por reejecución determinista.

No cambia el motor, los bots, los pagos ni las fuentes de azar. Solo observa
estados tras los eventos relevantes y turnos, incluso con log=False.
Los indicadores originales de primera consecución no equivalen a propiedad vigente.
"""
from __future__ import annotations

from dataclasses import dataclass

from simulador.motor import Game, parse_cards
from simulador.economia import ScenarioConfig
from laboratorio.ejecucion import CARDS

EVENTOS_RELEVANTES = frozenset({
    'utn_aprobada', 'hito_adjudicado', 'formacion_pareja', 'ruptura',
    'entrada_adultez', 'retroceso_juventud', 'compra_casa', 'perdida_casa',
    'casamiento', 'cambio_perfil', 'cambio_personaje', 'duelo',
    'transferencia_hito', 'duelo_retirada',
})


class JuegoObservado(Game):
    """Observador pasivo; no consume RNG ni altera el flujo de la partida."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instantaneas: list[dict] = []
        self._firma_previa = None
        self._registrar('inicio')

    def _registrar(self, causa: str) -> None:
        jugadores = {
            p.id: {
                'personaje': p.role,
                'etapa': p.stage,
                'utn': bool(p.utn),
                'titulo': bool(p.title),
                'pasaporte': bool(p.passport and p.passport_kind == p.role),
                'pareja': p.pair,
                'perfil': p.profile.uid if p.profile else None,
                'afinidad': p.profile.affinity if p.profile else None,
            }
            for p in self.players
        }
        casa = tuple(self.house_owner) if self.house_owner is not None else None
        ganadores = tuple(self.win) if self.win is not None else None
        firma = (tuple((pid, tuple(state.values())) for pid, state in jugadores.items()),
                 casa, ganadores, bool(self.finished))
        if firma == self._firma_previa:
            return
        self._firma_previa = firma
        self.instantaneas.append({
            'ronda': self.round, 'turno': self.turn, 'causa': causa,
            'jugadores': jugadores, 'casa': casa,
            'ganadores': ganadores, 'finalizada': bool(self.finished),
        })

    def event(self, action, **kwargs):
        super().event(action, **kwargs)
        if action in EVENTOS_RELEVANTES and hasattr(self, 'instantaneas'):
            self._registrar(action)

    def do_turn(self, p):
        super().do_turn(p)
        self._registrar('fin_turno')

    def run(self):
        result = super().run()
        self._registrar('fin_partida')
        return result


def _estado(instantanea: dict, ganadores: tuple[int, int], clave: str) -> bool:
    p, q = (instantanea['jugadores'][i] for i in ganadores)
    emparejados = p['pareja'] == ganadores[1] and q['pareja'] == ganadores[0]
    if clave.startswith('utn_'):
        return instantanea['jugadores'][int(clave[4:])]['utn']
    if clave.startswith('titulo_'):
        return instantanea['jugadores'][int(clave[7:])]['titulo']
    if clave.startswith('pasaporte_'):
        return instantanea['jugadores'][int(clave[10:])]['pasaporte']
    if clave == 'pareja':
        return emparejados
    if clave == 'ambos_hitos':
        return emparejados and all(x['titulo'] and x['pasaporte'] for x in (p, q))
    if clave == 'afinidad':
        return (emparejados and p['afinidad'] is not None and
                p['afinidad'] == q['afinidad'])
    if clave == 'adultez':
        return emparejados and p['etapa'] == q['etapa'] == 'Adultez'
    if clave == 'casa':
        return emparejados and instantanea['casa'] == ganadores
    if clave == 'casamiento':
        return instantanea['finalizada'] and instantanea['ganadores'] == ganadores
    raise ValueError(f'Hito no reconocido: {clave}')


def _ronda_decimal(snap: dict, jugadores: int) -> float:
    if snap['ronda'] == 0:
        return 0.0
    turno_en_ronda = snap['turno'] - (snap['ronda'] - 1) * jugadores
    turno_en_ronda = min(max(turno_en_ronda, 0), jugadores)
    return snap['ronda'] - 1 + turno_en_ronda / (jugadores + 1)


def obtener_periodos(instantaneas: list[dict], ganadores: tuple[int, int],
                     claves: list[tuple[str, str, str]], jugadores: int) -> list[dict]:
    """Intervalos de posesión real; conserva las recuperaciones y pérdidas.

    Se grafica el tiempo dentro de una ronda por posición del turno. Los
    episodios de varios eventos dentro del mismo turno tienen ancho mínimo
    visual y se identifican con su ronda y turno exactos al inspeccionarlos.
    """
    if not instantaneas:
        return []
    episodios = []
    for key, etiqueta, grupo in claves:
        inicio = None
        for snap in instantaneas:
            actual = _estado(snap, ganadores, key)
            if actual and inicio is None:
                inicio = snap
            if not actual and inicio is not None:
                episodios.append(_episodio(key, etiqueta, grupo, inicio, snap, jugadores))
                inicio = None
        if inicio is not None:
            episodios.append(_episodio(key, etiqueta, grupo, inicio, instantaneas[-1], jugadores))
    return episodios


def _episodio(key, etiqueta, grupo, inicio, fin, jugadores):
    x0 = _ronda_decimal(inicio, jugadores)
    x1 = _ronda_decimal(fin, jugadores)
    return {
        'clave': key, 'hito': etiqueta, 'grupo': grupo,
        'ronda_inicio': inicio['ronda'], 'turno_inicio': inicio['turno'],
        'ronda_fin': fin['ronda'], 'turno_fin': fin['turno'],
        'x_inicio': x0, 'x_fin': max(x1, x0 + 0.06),
    }


def construir_cronologia(juego: JuegoObservado) -> dict:
    """Solo la pareja realmente ganadora, nunca la primera pareja de la mesa."""
    if not juego.finished or juego.win is None:
        return {
            'partida': juego.id, 'semilla': juego.seed, 'finalizada': False,
            'ganadores': [], 'ronda_casamiento': None, 'periodos': [],
            'hitos': [], 'advertencia': 'Partida censurada: no existe pareja ganadora.',
            'estados_observados': len(juego.instantaneas),
        }
    ganadores = tuple(juego.win)
    p, q = (juego.p(pid) for pid in ganadores)
    def quien(x): return f'{x.role} #{x.id}'
    definiciones = []
    for x in (p, q):
        definiciones.extend([
            (f'utn_{x.id}', f'UTN · {quien(x)}', 'Individual'),
            (f'titulo_{x.id}', f'Título · {quien(x)}', 'Individual'),
            (f'pasaporte_{x.id}', f'Pasaporte · {quien(x)}', 'Individual'),
        ])
    definiciones += [
        ('pareja', 'Pareja formada', 'Pareja'),
        ('ambos_hitos', 'Ambos: Título + Pasaporte', 'Pareja'),
        ('afinidad', 'Afinidad compatible', 'Afinidad'),
        ('adultez', 'Adultez', 'Pareja'),
        ('casa', 'Casa en propiedad', 'Casa'),
        ('casamiento', 'Casamiento', 'Final'),
    ]
    periodos = obtener_periodos(juego.instantaneas, ganadores, definiciones, len(juego.players))
    tabla = []
    for clave, hito, grupo in definiciones:
        episodios = [x for x in periodos if x['clave'] == clave]
        tabla.append({
            'Hito': hito, 'Grupo': grupo,
            'Primera ronda': episodios[0]['ronda_inicio'] if episodios else None,
            'Ronda vigente final': episodios[-1]['ronda_inicio'] if episodios else None,
            'Recuperaciones': max(0, len(episodios) - 1),
        })
    return {
        'partida': juego.id, 'semilla': juego.seed, 'finalizada': True,
        'ganadores': [{'id': x.id, 'personaje': x.role, 'perfil_final': x.profile.uid if x.profile else None,
                       'afinidad_final': x.profile.affinity if x.profile else None} for x in (p,q)],
        'ronda_casamiento': juego.round, 'periodos': periodos, 'hitos': tabla,
        'advertencia': ('La cronología registra cambios observables tras los eventos importantes y al finalizar cada turno. '
                         'Los hitos que se pierden y recuperan aparecen como intervalos separados. '
                         'Los indicadores históricos «primera vez» pueden diferir del estado vigente al casarse.'),
        'estados_observados': len(juego.instantaneas),
        'errores_integridad': list(juego.errors),
    }


def trazar_partida(config: ScenarioConfig, numero: int, fila_esperada: dict | None = None) -> dict:
    """Reejecuta únicamente la semilla de una partida del lote y verifica igualdad."""
    if not 1 <= numero <= config.partidas:
        raise ValueError(f'Partida fuera del intervalo 1..{config.partidas}: {numero}')
    semilla = config.seed + (numero - 1) * config.incremento_seed
    juego = JuegoObservado(numero, semilla, config.jugadores, parse_cards(CARDS),
                          log=False, max_rounds=config.max_rondas,
                          bot_mode=config.bot, economia=config.economia).run()
    fila = juego.summary()
    if fila_esperada is not None and fila != fila_esperada:
        diferentes = sorted(k for k in set(fila) | set(fila_esperada)
                           if fila.get(k) != fila_esperada.get(k))
        raise AssertionError(f'Divergencia de trazabilidad en partida {numero}: {diferentes[:12]}')
    resultado = construir_cronologia(juego)
    resultado['equivalencia_fila'] = fila_esperada is not None
    return resultado
