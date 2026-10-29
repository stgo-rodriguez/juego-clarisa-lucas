"""Fase 4.4: observación pasiva de turnos y oportunidades verificables.

Solo reejecuta una semilla. 'Oportunidad' es una familia de acción detectada
al llegar a su punto de evaluación; NO un conteo exhaustivo de jugadas legales.
No infiere decisiones humanas, diversión, agencia ni alternativas contrafactuales.
"""
from __future__ import annotations
from collections import Counter
from statistics import mean

from laboratorio.ejecucion import CARDS
from laboratorio.trazabilidad import JuegoObservado
from simulador.economia import ScenarioConfig
from simulador.motor import parse_cards
from simulador.motor_v13_base import SUBHITOS

# Se registra una acción de bot ejecutada por evento, no cada transferencia
# auxiliar de fichas o consecuencia mecánica de su decisión.
DECISIONES = {
    'carta': 'Elegir desenlace de carta',
    'inversion': 'Financiar subhito',
    'examen_adjudicacion': 'Intentar adjudicación',
    'cambio_perfil': 'Cambiar perfil',
    'cambio_personaje': 'Cambiar personaje',
    'duelo': 'Iniciar duelo',
    'duelo_retirada': 'Iniciar duelo',
    'venta_comprobante': 'Negociar comprobante',
    'intercambio_recursos': 'Intercambiar recursos',
    'transferencia_hito': 'Transferir hito',
    'conversion': 'Convertir en banco',
}
ACTIVACIONES_AUTOMATICAS = {'formacion_pareja': 'Formar pareja',
                           'compra_casa': 'Intentar comprar Casa',
                           'casamiento': 'Intentar casamiento'}
AUTOMATICOS = frozenset({
    'produce', 'pago', 'transfer_pair', 'utn_aprobada', 'utn_falla',
    'entrada_adultez', 'compra_casa', 'perdida_casa', 'retroceso_juventud',
    'ruptura', 'proyecto_abierto', 'proyecto_completo', 'hito_adjudicado',
    'casamiento', 'formacion_pareja',
})
# La lista incluye solo chequeos con predicados observables y sin RNG.
FAMILIAS = (
    'Elegir desenlace de carta', 'Financiar subhito', 'Intentar adjudicación',
    'Formar pareja', 'Intentar comprar Casa', 'Intentar casamiento',
    'Cambiar perfil', 'Iniciar duelo', 'Negociar comprobante',
    'Convertir en banco',
)


class JuegoTurnos(JuegoObservado):
    """Observa puntos de decisión sin modificar resoluciones ni RNG."""

    def __init__(self, *args, **kwargs):
        self.turnos_observados: list[dict] = []
        self._turno_actual: dict | None = None
        super().__init__(*args, **kwargs)

    def event(self, action, **kwargs):
        super().event(action, **kwargs)
        t = self._turno_actual
        if t is not None:
            if action in DECISIONES:
                t['decisiones'].append(DECISIONES[action])
                t['activaciones'].add(DECISIONES[action])
            elif action in AUTOMATICOS:
                if action in ACTIVACIONES_AUTOMATICAS:
                    t['activaciones'].add(ACTIVACIONES_AUTOMATICAS[action])
                t['eventos_automaticos'] += 1
            else:
                t['eventos_sin_clasificar'].append(action)

    def _op(self, familia: str, condicion: bool):
        t = self._turno_actual
        if t is not None and condicion:
            t['oportunidades'].add(familia)

    def roll_movement(self, p):
        if self._turno_actual is not None:
            self._turno_actual['movimientos_dado'] += 1
        return super().roll_movement(p)

    def card_at(self, p):
        self._op('Elegir desenlace de carta', True)  # Ambas opciones siempre ofrecidas.
        return super().card_at(p)

    def funding(self, p, funded):
        if p.utn and p.stage in ('Juventud', 'Adultez'):
            needs = ['Titulo' if not p.title else None,
                     ('Italia' if p.role == 'Clarisa' else 'Polonia') if not p.passport else None]
            has_option = False
            for kind in filter(None, needs):
                open_projects = self.project_for(kind)
                if any(pr.id not in funded and self.can_fund(p, pr) for pr in open_projects):
                    has_option = True
                elif not open_projects and len([pr for pr in self.projects.values() if pr.kind == kind]) < len(self.players):
                    resource, required = SUBHITOS[kind][0]
                    has_option |= self.feasible(p, {resource: required})
            self._op('Financiar subhito', has_option)
        return super().funding(p, funded)

    def try_adjudicate(self, p):
        kind = ('Titulo' if p.pos in (1, 4) else
                ('Italia' if p.role == 'Clarisa' else 'Polonia') if p.pos in (2, 5) else None)
        can = bool(not p.used_adjudication and p.stage == 'Juventud' and kind and
                   not (p.title if kind == 'Titulo' else p.passport) and
                   any(len(pr.subhitos) == 3 and self.owns_right(p, pr)
                       for pr in self.project_for(kind)) and
                   p.free('K' if kind == 'Titulo' else 'P') +
                   (self.partner(p).free('K' if kind == 'Titulo' else 'P') if p.pair else 0) >= 1)
        self._op('Intentar adjudicación', can)
        return super().try_adjudicate(p)

    def pair_encounters(self, p):
        can = (not p.pair and p.stage != 'Infancia' and
               any(x.id != p.id and not x.pair and x.role != p.role and
                   x.stage == p.stage and x.pos == p.pos and self.feasible_pair(p, x)
                   for x in self.players))
        self._op('Formar pareja', bool(can))
        return super().pair_encounters(p)

    def try_house(self, p):
        mate = self.partner(p)
        can = bool(mate and self.house_owner != self.pairkey(p) and
                   p.free('A') + mate.free('A') >= 16 and
                   p.free('P') + mate.free('P') >= 10 and
                   p.free('M') + mate.free('M') >= 30)
        self._op('Intentar comprar Casa', can)
        return super().try_house(p)

    def try_marriage(self, p):
        mate = self.partner(p)
        can = bool(mate and self.house_owner == self.pairkey(p) and
                   p.profile and mate.profile and p.profile.affinity == mate.profile.affinity and
                   all(x.title and x.passport and x.passport_kind == x.role and
                       x.pair_res == 5 and x.house_a == 8 and x.house_p == 5
                       for x in (p, mate)) and
                   all(p.free(r) + mate.free(r) >= 2*n for r,n in {'A':12, 'P':10, 'M':5}.items()))
        self._op('Intentar casamiento', can)
        return super().try_marriage(p)

    def change_profile(self, p):
        # Comprueba elegibilidad de coste y cartas; no presume que el bot quiera cambiar.
        has_card = bool(self.market.visible[p.role] or self.market.hidden[p.role])
        can = bool(p.profile and not p.used_profile_change and has_card and
                   all(self.feasible(p, {r:3}) for r in ('A','P','K','M')))
        self._op('Cambiar perfil', can)
        return super().change_profile(p)

    def duel_interaction(self, p):
        candidates = [x for x in self.players if x.id != p.id and x.role == p.role and
                      x.stage == p.stage and x.pos == p.pos]
        can = any(
            self.can_challenge_hito(p, x, kind) or
            (p.profile is not None and x.profile is not None and
             self.duel_legal(p, x, 'P', 1)) or
            (self.duel_legal(p, x, 'A', 1) and p.free('P') >= 1 and p.free('A') >= 1)
            for x in candidates for kind in ('Titulo','Pasaporte')
        )
        self._op('Iniciar duelo', can)
        return super().duel_interaction(p)

    def negotiate_receipt(self, p):
        can = False
        if p.free('M') >= 2:
            for target in self.players:
                if target.id == p.id or target.stage != p.stage or target.pos != p.pos or target.role == p.role:
                    continue
                for rec in self.receipts.values():
                    if rec.owner != target.id: continue
                    pr = self.projects[rec.project]
                    if pr.kind != 'Titulo' and pr.kind != ('Italia' if p.role == 'Clarisa' else 'Polonia'):
                        continue
                    if (p.title if pr.kind == 'Titulo' else p.passport) or self.owns_right(p, pr): continue
                    can = True
                    break
                if can:break
        self._op('Negociar comprobante', can)
        return super().negotiate_receipt(p)

    def bank(self, p):
        # Posibilidad general de un cambio 2:1 entre recursos adyacentes;
        # puede no ser elegido por el bot debido a sus prioridades.
        can = any(p.free(r) >= 2 for r in ('A','P','K','M'))
        self._op('Convertir en banco', can)
        return super().bank(p)

    def do_turn(self, p):
        # No se evalúa la disponibilidad por adelantado: cada punto se observa
        # en el instante en que el motor realmente lo consulta.
        assert self._turno_actual is None
        t = {'ronda': self.round, 'turno': self.turn+1, 'jugador': p.id,
             'personaje': p.role, 'bot': p.bot, 'etapa_inicio': p.stage,
             'oportunidades': set(), 'activaciones': set(), 'decisiones': [],
             'eventos_automaticos': 0, 'eventos_sin_clasificar': [],
             'movimientos_dado': 0}
        self._turno_actual = t
        try:
            super().do_turn(p)
        finally:
            t['etapa_fin'] = p.stage
            t['oportunidades'] = sorted(t['oportunidades'])
            t['activaciones'] = sorted(t['activaciones'])
            t['familias_disponibles'] = len(t['oportunidades'])
            t['decisiones_ejecutadas'] = len(t['decisiones'])
            t['tiene_decision'] = bool(t['decisiones'])
            t['solo_automatico'] = not t['decisiones']
            self.turnos_observados.append(t)
            self._turno_actual = None


def resumir_turnos(juego: JuegoTurnos) -> dict:
    filas = juego.turnos_observados
    decisiones = Counter(a for t in filas for a in t['decisiones'])
    ofertas = Counter(a for t in filas for a in t['oportunidades'])
    activaciones = Counter(a for t in filas for a in t['activaciones'])
    por_etapa = []
    por_bot = []
    def agregado(items, clave):
        grupos={}
        for t in items:grupos.setdefault(t[clave],[]).append(t)
        return [{'Grupo': k,'Turnos':len(v),
                 'Turnos con decisiones':sum(t['tiene_decision'] for t in v),
                 'Decisiones ejecutadas':sum(t['decisiones_ejecutadas'] for t in v),
                 'Familias disponibles medias':round(mean(t['familias_disponibles'] for t in v),3),
                 'Decisiones por turno':round(mean(t['decisiones_ejecutadas'] for t in v),3)}
                for k,v in sorted(grupos.items())]
    por_etapa=agregado(filas,'etapa_inicio')
    por_bot=agregado(filas,'bot')
    counts = {
        'cards':'Elegir desenlace de carta', 'funded_subhitos':'Financiar subhito',
        'adjudication_attempts':'Intentar adjudicación', 'profile_changes':'Cambiar perfil',
        'character_change':'Cambiar personaje', 'duels_started':'Iniciar duelo',
        'receipts_traded':'Negociar comprobante', 'resource_trades':'Intercambiar recursos',
        'hitos_traded':'Transferir hito', 'bank_conversions':'Convertir en banco',
    }
    errors=[]
    if len(filas)!=juego.turn:errors.append(f'Turnos registrados: {len(filas)} != {juego.turn}')
    for stat, name in counts.items():
        observed=decisiones[name]
        recorded=int(juego.stats[stat])
        if observed!=recorded:
            errors.append(f'{stat}: {observed} observados != {recorded} motor')
    if sum(t['decisiones_ejecutadas'] for t in filas) != sum(decisiones.values()):
        errors.append('Decisiones totales inconsistentes')
    # No se obliga a que una decisión aparezca en oportunidades: las acciones
    # como cambio de personaje, intercambio o transferencia no están cubiertas.
    return {
        'partida':juego.id, 'semilla':juego.seed, 'jugadores':len(juego.players),
        'rondas':juego.round,'turnos':len(filas),
        'turnos_con_decision':sum(t['tiene_decision'] for t in filas),
        'turnos_solo_automaticos':sum(t['solo_automatico'] for t in filas),
        'decisiones_ejecutadas':sum(decisiones.values()),
        'decisiones_por_turno':round(mean(t['decisiones_ejecutadas'] for t in filas),3) if filas else 0,
        'familias_disponibles_por_turno':round(mean(t['familias_disponibles'] for t in filas),3) if filas else 0,
        'turnos_sin_oportunidad_observada':sum(t['familias_disponibles']==0 for t in filas),
        'por_etapa':por_etapa, 'por_bot':por_bot,
        'por_decision':[{'Acción':k,'Cantidad':n} for k,n in sorted(decisiones.items())],
        'por_oportunidad':[{'Acción':k,'Turnos disponibles':ofertas[k],
                            'Turnos con ejecución':activaciones[k]} for k in FAMILIAS],
        'turnos_detalle':filas,
        'errores_auditoria':errors, 'errores_motor':list(juego.errors),
        'advertencia': ('Indicadores descriptivos de actividad del bot, NO medida objetiva de diversión, '
                        'calidad ni profundidad estratégica. Oportunidades = familias detectadas al '
                        'llegar a 10 puntos de evaluación; no son jugadas legales exhaustivas. '
                        'Las activaciones incluyen decisiones ejecutadas y resoluciones automáticas de hitos; '
                        'El motor no registra ofertas rechazadas ni deliberación humana.'),
    }


def trazar_turnos(config: ScenarioConfig, numero: int, fila_esperada: dict | None = None) -> dict:
    if not 1 <= numero <= config.partidas:
        raise ValueError(f'Partida fuera del intervalo 1..{config.partidas}: {numero}')
    semilla = config.seed + (numero - 1)*config.incremento_seed
    juego = JuegoTurnos(numero, semilla, config.jugadores, parse_cards(CARDS),
                       log=False, max_rounds=config.max_rondas,
                       bot_mode=config.bot, economia=config.economia).run()
    fila = juego.summary()
    if fila_esperada is not None and fila != fila_esperada:
        different=sorted(k for k in set(fila)|set(fila_esperada) if fila.get(k)!=fila_esperada.get(k))
        raise AssertionError(f'Divergencia de turnos en partida {numero}: {different[:12]}')
    out=resumir_turnos(juego)
    out['equivalencia_fila'] = fila_esperada is not None
    return out
