"""Fase 4.2: contabilidad pasiva por jugador, etapa, recurso y origen.

Reejecuta UNA semilla: no sustituye ni modifica el motor, los bots ni sus RNG.
Los registros de flujo se concilian con cada variación de stocks (incluidas
redistribuciones directas, liquidaciones de Casa y pérdidas compartidas).
"""
from __future__ import annotations

from collections import defaultdict

from simulador.motor import parse_cards
from simulador.economia import ScenarioConfig
from laboratorio.ejecucion import CARDS
from laboratorio.trazabilidad import JuegoObservado

RECURSOS = ('A', 'P', 'K', 'M')
ETAPAS = ('Infancia', 'UTN', 'Juventud', 'Adultez')


def _total_por_recurso(entradas):
    total = defaultdict(int)
    for e in entradas:
        total[e['recurso']] += e['delta']
    return dict(total)


class JuegoEconomico(JuegoObservado):
    """Observación de mutaciones reales: no da instrucciones al motor."""

    def __init__(self, *args, **kwargs):
        self.movimientos = []
        self.existencias_turno = []
        self.desajustes = []
        self._secuencia = 0
        super().__init__(*args, **kwargs)

    def _mov(self, pid, recurso, delta, clase, fuente, etapa=None, contraparte=None):
        if delta == 0:
            return
        self._secuencia += 1
        p = self.p(pid)
        self.movimientos.append({
            'secuencia': self._secuencia, 'partida': self.id,
            'ronda': self.round, 'turno': self.turn, 'jugador': pid,
            'personaje': p.role, 'etapa': etapa if etapa is not None else p.stage,
            'recurso': recurso, 'delta': int(delta), 'cantidad': abs(int(delta)),
            'clase': clase, 'fuente': fuente, 'contraparte': contraparte,
        })

    def _transferir(self, origen, destino, recurso, cantidad, fuente, etapas=None):
        if not cantidad:
            return
        etapas = etapas or {}
        self._mov(origen, recurso, -cantidad, 'transferencia', fuente,
                  etapas.get(origen), destino)
        self._mov(destino, recurso, cantidad, 'transferencia', fuente,
                  etapas.get(destino), origen)

    def event(self, action, **kw):
        super().event(action, **kw)
        if action == 'produce':
            self._mov(kw['jugador'], kw['recurso'], kw['n'], 'ingreso', kw['fuente'])
        elif action == 'pago':
            fuente = kw['causa']
            clase = 'inversion' if fuente == 'inversion' else 'pago'
            self._mov(kw['jugador'], kw['recurso'], -kw['n'], clase, fuente)
        elif action == 'transfer_pair':
            self._transferir(kw['desde'], kw['hacia'], kw['recurso'],
                            kw['n'], 'ayuda_pareja')
        elif action == 'compra_casa' and kw.get('expropietarios'):
            # El motor paga la Casa desde la nueva pareja y acredita a vendedores.
            # Las acreditaciones no tienen una llamada a produce, por lo que se observan aquí.
            for pid in kw['expropietarios']:
                self._mov(pid, 'M', kw['precio_personal'], 'ingreso', 'venta_casa')

    def _stock(self):
        return {(p.id, r): p.r[r] for p in self.players for r in RECURSOS}

    def _etapas(self):
        return {p.id: p.stage for p in self.players}

    def _conciliar(self, antes, inicio, metodo, etapas):
        """Completa solo movimientos directos aún no observados en otros métodos.

        Su resultado debe ser CERO, incluso para intercambios, reservas y Casa.
        No reescribe el estado: solo añade registros de transferencias detectadas.
        """
        despues = self._stock()
        explicado = defaultdict(int)
        for e in self.movimientos[inicio:]:
            explicado[(e['jugador'], e['recurso'])] += e['delta']
        faltan = {k: despues[k] - antes[k] - explicado[k] for k in antes}
        for recurso in RECURSOS:
            pendientes = [[pid, -val] for (pid, r), val in faltan.items()
                          if r == recurso and val < 0]
            receptores = [[pid, val] for (pid, r), val in faltan.items()
                          if r == recurso and val > 0]
            i = j = 0
            while i < len(pendientes) and j < len(receptores):
                src, deficit = pendientes[i]
                dst, credito = receptores[j]
                n = min(deficit, credito)
                self._transferir(src, dst, recurso, n, f'redistribucion_{metodo}', etapas)
                pendientes[i][1] -= n
                receptores[j][1] -= n
                if pendientes[i][1] == 0:
                    i += 1
                if receptores[j][1] == 0:
                    j += 1
            sobrantes = [(pid, -n) for pid, n in pendientes[i:] if n] + [
                (pid, n) for pid, n in receptores[j:] if n]
            # Único reintegro directo conocido: cambio de personaje pagado
            # que no se realiza si se agotaron los Perfiles del mercado.
            if metodo == 'cambio_personaje' and recurso == 'P':
                restantes = []
                for pid, delta in sobrantes:
                    if delta > 0 and delta == 3:
                        self._mov(pid, recurso, delta, 'ingreso',
                                  'reintegro_cambio_personaje', etapas[pid])
                    else:
                        restantes.append((pid, delta))
                sobrantes = restantes
            for pid, delta in sobrantes:
                self.desajustes.append({'ronda': self.round, 'turno': self.turn,
                                        'jugador': pid, 'recurso': recurso,
                                        'delta': delta, 'metodo': metodo})
        # Comprobación final de todas las posiciones, no solo conservación global.
        neto = defaultdict(int)
        for e in self.movimientos[inicio:]:
            neto[(e['jugador'], e['recurso'])] += e['delta']
        for key in antes:
            diferencia = despues[key] - antes[key] - neto[key]
            if diferencia and not any(x['metodo'] == metodo and x['ronda'] == self.round and
                                      x['turno'] == self.turn and x['jugador'] == key[0] and
                                      x['recurso'] == key[1] for x in self.desajustes):
                self.desajustes.append({'ronda': self.round, 'turno': self.turn,
                                        'jugador': key[0], 'recurso': key[1],
                                        'delta': diferencia, 'metodo': metodo})

    def _observar(self, metodo, fn, *args, **kwargs):
        antes = self._stock()
        etapas = self._etapas()
        inicio = len(self.movimientos)
        resultado = fn(*args, **kwargs)
        self._conciliar(antes, inicio, metodo, etapas)
        return resultado

    def loss(self, p, r, n, source='carta'):
        return self._observar_perdida(p, r, n, source)

    def _observar_perdida(self, p, r, n, source):
        antes = {x.id: x.r[r] for x in self.players}
        etapas = self._etapas()
        result = super().loss(p, r, n, source)
        for x in self.players:
            cambio = x.r[r] - antes[x.id]
            if cambio:
                self._mov(x.id, r, cambio, 'perdida', source, etapas[x.id])
        return result

    def rebalance_pair(self, a, b):
        return self._observar('formacion_pareja', super().rebalance_pair, a, b)

    def enter_adult(self, p):
        return self._observar('entrada_adultez', super().enter_adult, p)

    def try_house(self, p):
        return self._observar('compra_casa', super().try_house, p)

    def try_marriage(self, p):
        return self._observar('casamiento', super().try_marriage, p)

    def transfer_duel(self, src, dst, r, n):
        return self._observar('duelo', super().transfer_duel, src, dst, r, n)

    def transfer_receipt(self, seller, buyer, receipt_id, price=0, resource='M'):
        return self._observar('comprobante', super().transfer_receipt,
                             seller, buyer, receipt_id, price, resource)

    def trade_resources(self, seller, buyer, gives, receives):
        return self._observar('intercambio', super().trade_resources,
                             seller, buyer, gives, receives)

    def change_character(self, p):
        return self._observar('cambio_personaje', super().change_character, p)

    def do_turn(self, p):
        # Detecta movimientos futuros sin instrumentar (fuente desconocida), no los oculta.
        antes = self._stock()
        inicio = len(self.movimientos)
        resultado = super().do_turn(p)
        self._conciliar(antes, inicio, 'turno', self._etapas())
        for x in self.players:
            for r in RECURSOS:
                self.existencias_turno.append({
                    'ronda': self.round, 'turno': self.turn, 'jugador': x.id,
                    'personaje': x.role, 'etapa': x.stage, 'recurso': r,
                    'stock': x.r[r], 'libre': x.free(r),
                    'reserva_pareja': x.pair_res if r == 'A' else 0,
                    'reserva_casa': (x.house_a if r == 'A' else
                                    x.house_p if r == 'P' else 0),
                })
        return resultado


def resumen_economia(juego: JuegoEconomico) -> dict:
    """Agrega flujo observado sin confundir gastos, inversiones y transferencias."""
    resumen = defaultdict(lambda: {'ingresos': 0, 'pagos': 0, 'inversiones': 0,
                                  'perdidas': 0, 'transferencias_recibidas': 0,
                                  'transferencias_enviadas': 0})
    for e in juego.movimientos:
        v = resumen[(e['etapa'], e['recurso'], e['fuente'], e['clase'])]
        tipo = e['clase']
        if tipo == 'ingreso':
            v['ingresos'] += e['cantidad']
        elif tipo == 'pago':
            v['pagos'] += e['cantidad']
        elif tipo == 'inversion':
            v['inversiones'] += e['cantidad']
        elif tipo == 'perdida':
            v['perdidas'] += e['cantidad']
        elif tipo == 'transferencia':
            v['transferencias_recibidas' if e['delta'] > 0 else 'transferencias_enviadas'] += e['cantidad']
    saldos = defaultdict(lambda: {'stock': 0, 'libre': 0, 'reserva_pareja': 0,
                                 'reserva_casa': 0, 'observaciones': 0})
    for s in juego.existencias_turno:
        k = (s['etapa'], s['recurso'])
        for campo in ('stock', 'libre', 'reserva_pareja', 'reserva_casa'):
            saldos[k][campo] += s[campo]
        saldos[k]['observaciones'] += 1
    return {
        'movimientos': list(juego.movimientos),
        'tabla_flujos': [{'Etapa': k[0], 'Recurso': k[1], 'Fuente': k[2],
                         'Clase': k[3], **v} for k, v in sorted(resumen.items())],
        'stock_por_etapa': [
            {'Etapa': k[0], 'Recurso': k[1], 'Stock medio': round(v['stock']/v['observaciones'], 3),
             'Libre medio': round(v['libre']/v['observaciones'], 3),
             'Reservado pareja medio': round(v['reserva_pareja']/v['observaciones'], 3),
             'Reservado casa medio': round(v['reserva_casa']/v['observaciones'], 3),
             'Observaciones': v['observaciones']}
            for k, v in sorted(saldos.items())],
        'stock_final': {r: sum(p.r[r] for p in juego.players) for r in RECURSOS},
        'errores_conciliacion': list(juego.desajustes),
        'errores_motor': list(juego.errors),
    }


def trazar_economia(config: ScenarioConfig, numero: int, fila_esperada: dict | None = None) -> dict:
    if not 1 <= numero <= config.partidas:
        raise ValueError(f'Partida fuera del intervalo 1..{config.partidas}: {numero}')
    semilla = config.seed + (numero - 1) * config.incremento_seed
    juego = JuegoEconomico(numero, semilla, config.jugadores, parse_cards(CARDS),
                          log=False, max_rounds=config.max_rondas,
                          bot_mode=config.bot, economia=config.economia).run()
    if fila_esperada is not None and juego.summary() != fila_esperada:
        raise AssertionError(f'Economía divergente en partida {numero}')
    resultado = resumen_economia(juego)
    if resultado['errores_conciliacion']:
        raise AssertionError(f'Movimientos económicos sin explicar: {resultado["errores_conciliacion"][:8]}')
    resultado.update({'partida': numero, 'semilla': semilla,
                      'terminada': juego.finished, 'jugadores': config.jugadores,
                      'rondas_observadas': juego.round,
                      'equivalencia_fila': fila_esperada is not None,
                      'alcance': ('Trazabilidad de UNA partida reejecutada. Stock medio = media '
                                  'sobre jugadores y fines de turno observados en cada etapa; '
                                  'no equivale al saldo de cierre ni a una media por ronda.'),
                      'advertencia': ('Inversiones separadas de pagos: los recursos financiados '
                                      'dejan el stock personal, pero el proyecto puede seguir abierto. '
                                      'Los ingresos de venta de Casa son transferencias originadas '
                                      'en los pagos de compradores. Solo se registran variaciones de fichas.')})
    return resultado
