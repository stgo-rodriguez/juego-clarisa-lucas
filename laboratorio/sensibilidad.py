"""Fase 6: grillas reproducibles y estimaciones de incertidumbre apareadas.

El módulo no modifica el simulador, no importa Streamlit y utiliza un generador
local para bootstrap que nunca afecta dados, cartas ni decisiones del juego.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
import random
import statistics
from typing import Callable

from laboratorio.comparacion import comparar, escenario_base, signature
from simulador.economia import EconomyConfig, ScenarioConfig


PARAMETROS = {
    'perfiles_pct': 'Producción de Perfiles',
    'cartas_ganancias_pct': 'Ganancias por cartas',
    'cartas_perdidas_pct': 'Pérdidas por cartas',
    'infancia_pct': 'Ingresos de Infancia',
    'juventud_pct': 'Ingresos de Juventud',
    'adultez_pct': 'Ingresos de Adultez',
}
LIMITE_PARTIDAS = 3000   # total máximo de partidas simuladas por exploración
MAX_CELDAS = 25
REMUESTREOS = 500


def _validar_valores(nombre: str, valores: tuple[int, ...]) -> None:
    if nombre not in PARAMETROS:
        raise ValueError(f'Parámetro económico desconocido: {nombre}')
    if not isinstance(valores, tuple) or not 1 <= len(valores) <= 5:
        raise ValueError('Seleccioná entre 1 y 5 valores por eje')
    if len(set(valores)) != len(valores):
        raise ValueError('No se admiten valores repetidos en un eje')
    for valor in valores:
        if type(valor) is not int:
            raise ValueError('Los valores de los ejes deben ser enteros')
        if nombre in ('juventud_pct', 'adultez_pct'):
            if valor not in (0, 100):
                raise ValueError('Juventud y Adultez solo admiten 0 o 100')
        elif not 50 <= valor <= 150:
            raise ValueError('Los multiplicadores deben estar entre 50 y 150 %')


@dataclass(frozen=True)
class GridConfig:
    jugadores: int = 6
    partidas: int = 20
    seed: int = 131028
    max_rondas: int = 120
    bot: str = 'mixed'
    parametro_x: str = 'cartas_ganancias_pct'
    valores_x: tuple[int, ...] = (90, 100, 110)
    parametro_y: str = 'cartas_perdidas_pct'
    valores_y: tuple[int, ...] = (90, 100, 110)
    remuestreos: int = REMUESTREOS

    def __post_init__(self):
        # Valida también las reglas de semillas/tamaño aplicadas al simulador.
        escenario_base(self.jugadores, self.partidas, seed=self.seed,
                       max_rondas=self.max_rondas, bot=self.bot)
        _validar_valores(self.parametro_x, self.valores_x)
        _validar_valores(self.parametro_y, self.valores_y)
        if self.parametro_x == self.parametro_y:
            raise ValueError('Los dos ejes de sensibilidad deben ser distintos')
        if not isinstance(self.remuestreos, int) or not 100 <= self.remuestreos <= 2000:
            raise ValueError('Bootstrap: entre 100 y 2000 remuestreos')
        n = len(self.valores_x) * len(self.valores_y)
        if n > MAX_CELDAS:
            raise ValueError(f'Máximo {MAX_CELDAS} celdas')
        # Una ejecución base más cada celda única no basal. Sobreestima
        # conservadoramente el trabajo cuando hay una celda igual a la base.
        if (n + 1) * self.partidas > LIMITE_PARTIDAS:
            raise ValueError(f'El estudio supera el presupuesto de {LIMITE_PARTIDAS} partidas')

    def as_dict(self) -> dict:
        return {'jugadores': self.jugadores, 'partidas': self.partidas,
                'seed': self.seed, 'max_rondas': self.max_rondas, 'bot': self.bot,
                'parametro_x': self.parametro_x, 'valores_x': list(self.valores_x),
                'parametro_y': self.parametro_y, 'valores_y': list(self.valores_y),
                'remuestreos': self.remuestreos}

    @classmethod
    def from_dict(cls, data: dict) -> 'GridConfig':
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError('Configuración de grilla inválida')
        d = dict(data)
        for key in ('valores_x', 'valores_y'):
            if key in d:
                if not isinstance(d[key], (list, tuple)):
                    raise ValueError('Valores de grilla inválidos')
                d[key] = tuple(d[key])
        return cls(**d)


def _bootstrap_media(values: list[float], reps: int, seed: int) -> tuple[float | None, float | None]:
    """IC percentil al 95% para media de diferencias apareadas.

    Re-muestrea pares (las diferencias, NO los escenarios por separado).
    Retorna None para n<5: demasiada imprecisión para mostrar IC fiable.
    """
    n = len(values)
    if n < 5:
        return (None, None)
    rng = random.Random(seed)
    draws = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(reps))
    # Índices discretos de percentiles de una muestra bootstrap ordenada.
    lo = draws[int(.025 * (reps - 1))]
    hi = draws[int(.975 * (reps - 1))]
    return (round(lo, 4), round(hi, 4))


def _estadisticas_celda(base: dict, variante: dict, *, remuestreos: int, seed_bootstrap: int) -> dict:
    # Compara exactamente las condiciones/semillas, rechazando lotes ajenos.
    if base['codigo'] != variante['codigo']:
        raise ValueError('Motor o mazo diferentes: no se pueden comparar')
    cmp = comparar(base, variante)
    aa, bb = base['filas'], variante['filas']
    obs = [int(y['rondas_observadas']) - int(x['rondas_observadas'])
           for x, y in zip(aa, bb)]
    finished = [int(y['terminada']) - int(x['terminada'])
                for x, y in zip(aa, bb)]
    full = [int(y['rondas_observadas']) - int(x['rondas_observadas'])
            for x, y in zip(aa, bb)
            if int(x['terminada']) and int(y['terminada'])]
    obs_ci = _bootstrap_media(obs, remuestreos, seed_bootstrap)
    rate_ci = _bootstrap_media(finished, remuestreos, seed_bootstrap + 1)
    full_ci = _bootstrap_media(full, remuestreos, seed_bootstrap + 2)
    summary_b, summary_v = base['resumen'], variante['resumen']
    return {
        'n': len(obs), 'finalizadas_base': cmp['finalizadas_base'],
        'finalizadas_variante': cmp['finalizadas_variante'],
        'ambas_finalizadas': cmp['ambas_finalizadas'],
        'censuradas_base': summary_b['censuradas'],
        'censuradas_variante': summary_v['censuradas'],
        'delta_rondas_observadas': round(statistics.mean(obs), 4),
        'ic95_rondas_observadas_inf': obs_ci[0],
        'ic95_rondas_observadas_sup': obs_ci[1],
        'delta_finalizacion_pp': round(100 * statistics.mean(finished), 4),
        'ic95_finalizacion_pp_inf': None if rate_ci[0] is None else round(100 * rate_ci[0], 3),
        'ic95_finalizacion_pp_sup': None if rate_ci[1] is None else round(100 * rate_ci[1], 3),
        'delta_rondas_pares_concluidos': round(statistics.mean(full), 4) if full else None,
        'ic95_pares_concluidos_inf': full_ci[0],
        'ic95_pares_concluidos_sup': full_ci[1],
        'mediana_base_concluidas': summary_b['casamiento']['mediana'],
        'mediana_variante_concluidas': summary_v['casamiento']['mediana'],
        'p90_base_concluidas': summary_b['casamiento']['p90'],
        'p90_variante_concluidas': summary_v['casamiento']['p90'],
    }


def _es_base(econ: EconomyConfig) -> bool:
    return econ == EconomyConfig()


def ejecutar_grilla(config: GridConfig, ejecutar: Callable[[ScenarioConfig], dict],
                   progreso: Callable[[int, int], None] | None = None) -> dict:
    """Ejecuta cuadrícula; conserva solo métricas, no miles de eventos.

    `ejecutar` es el adaptador ya existente; al usar `correr` en Streamlit se
    aprovecha su caché. Un callback opcional actualiza una barra de progreso.
    """
    base_cfg = escenario_base(config.jugadores, config.partidas, seed=config.seed,
                              max_rondas=config.max_rondas, bot=config.bot)
    base = ejecutar(base_cfg)
    if base['escenario'] != base_cfg.as_dict():
        raise ValueError('El ejecutor devolvió una configuración base inesperada')
    if base['codigo'] != signature():
        raise ValueError('El motor o mazo ejecutados no son los actuales')
    total = len(config.valores_x) * len(config.valores_y)
    resultados = []
    for idx, y in enumerate(config.valores_y):
        for j, x in enumerate(config.valores_x):
            current = idx * len(config.valores_x) + j
            economics = replace(EconomyConfig(), **{config.parametro_x: x,
                                                    config.parametro_y: y})
            if _es_base(economics):
                variant = base
            else:
                exp_cfg = replace(base_cfg, id=f'grilla_{current+1}', economia=economics)
                variant = ejecutar(exp_cfg)
                if variant['escenario'] != exp_cfg.as_dict():
                    raise ValueError('El ejecutor devolvió un escenario inesperado')
            # Semilla de bootstrap vinculada a los parámetros, con RNG independiente.
            key = json.dumps([config.seed, config.jugadores, x, y,
                              config.parametro_x, config.parametro_y])
            boot_seed = int.from_bytes(sha256(key.encode()).digest()[:8], 'big')
            summary = _estadisticas_celda(base, variant,
                                          remuestreos=config.remuestreos,
                                          seed_bootstrap=boot_seed)
            resultados.append({'x': x, 'y': y,
                               'economia': economics.__dict__.copy(),
                               'escenario': variant['escenario'], **summary})
            if progreso:
                progreso(current + 1, total)
    return {'formato': 'sensibilidad-v1', 'configuracion': config.as_dict(),
            'motor': base['codigo'], 'referencia': base_cfg.as_dict(),
            'n_celdas': total, 'celdas': resultados,
            'metodo': {'comparacion': 'semillas apareadas',
                       'duracion': 'rondas observadas hasta límite (censura)',
                       'incertidumbre': f'bootstrap percentil 95%, {config.remuestreos} resamples',
                       'cuantiles': 'calculados solo sobre partidas concluidas',
                       'riesgo': 'IC exploratorios; no corrigen comparaciones múltiples'}}
