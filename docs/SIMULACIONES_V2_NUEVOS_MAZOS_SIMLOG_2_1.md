# Clarisa & Lucas · Simulación de nuevos mazos · SIMLOG v2.1

**Fecha:** 4 nov 2026. **Estado:** experimental, no reglamento aprobado. **Corrida:** 200 partidas, 100 mesas de seis y 100 de diez participantes, **solo agentes planificadores**; 100 rondas máximas, competencia activada, mano de tres movimientos en Adultez.

## Fuentes de las cartas

- **Infancia v0.3:** `Clarisa_Lucas_Infancia_24_Cartas_v0_3_Narrativas.xlsx` (archivo original en Biblioteca), 12 Clarisa y 12 Lucas. Lectura de las pestañas Clarisa/Lucas, 16 columnas de ganancia/pérdida cotejadas.
- **Juventud v0.3:** <https://docs.google.com/spreadsheets/d/1DjLn42FWoPbiRivm9G0DLQ1Hk_PDz8K8xbh6s0B_vuY/edit>, 24+24, pestañas `Clarisa v0.3` y `Lucas v0.3`. Efectos A/B tomados de las columnas A/B Ganás/Pérdidas; comprobada simetría completa C/L.
- **Adultez v0.4:** <https://docs.google.com/spreadsheets/d/1BQUEqJiSOew7oT2SDMYUeuXSUwW_xyL0BylhQvKl_yc/edit>, 15+15, pestañas `v0.4 Clarisa` y `v0.4 Lucas`. Efectos de `Datos mecánicos JSON`, 30 cartas A/B sin pujas; simetría comprobada.

La extracción de texto de Infancia utilizada para reproducir el catálogo se conserva en `docs/datos_v2_nuevas_cartas/fuentes/Clarisa_Lucas_Infancia_24_Cartas_v0_3_Narrativas.txt`; su fuente de autoridad sigue siendo el Excel original de la Biblioteca. El catálogo de 102 cartas se materializa en `docs/datos_v2_nuevas_cartas/catalogo_102_v03_v04.json`. Su SHA-256 es `38e8ae238ff4e64d9657d12d461f64ae3fb5ac4d54f2c03d27a7d8dae52c8d64`. Las narraciones completas permanecen en los documentos originales; la simulación consume los IDs, títulos y efectos numéricos.

## Procedimiento de mezcla y mazos

- Se crean **seis CardPool independientes**, con semilla RNG independiente por etapa y por rol.
- Cada mazo se mezcla al comienzo. Si se agota, se vuelven a mezclar **sus propios descartes** antes de reutilizarlos. No se mezclan etapas, roles ni versiones.
- Si por coincidencia extrema dos roles hubieran quedado con una permutación de índices idéntica, se invierte el orden de las dos últimas cartas de uno de los mazos, garantizando que la secuencia total no sea idéntica. Esto **no prohíbe** que un mismo número de carta aparezca casualmente en ambos roles en una ronda concreta.
- La mezcla se audita en `orden_mazos.json` de **cada** partida. Se verificaron 600 pares de mazos (200 partidas × 3 etapas): ninguna coincidencia de orden.

## Afinidad dinámica

- Todos comienzan en posición `0`.
- Resolver Situación **A** modifica posición `−1`; **B**, `+1` (no confundir con Movimiento A/B independiente en Adultez).
- Zonas de esta prueba: **A** para posiciones ≤ −3; **Neutro** para −2 a +2, inclusive; **B** para ≥ +3. Los bordes numéricos fuera de Neutro no están limitados: no se impone recorte ni rebote sobre el eje de Afinidad.
- Dos jugadores en Pareja son compatibles si coinciden en **zona**, no en posición exacta. Pueden formarse como Pareja siendo incompatibles, pero Casamiento requiere compatibilidad al entrar al nodo exterior.
- El Perfil de UTN conserva su producción histórica, pero su elemento heredado **no** determina Afinidad. Se desactiva el antiguo intercambio de Perfil por elementos. La nueva heurística otorga un bonus de compatibilidad al resolver Situación en pareja; Juventud pondera posición al elegir su movimiento vinculado.

## Efectos y balance experimental

- Ganancias de Situación se acreditan al jugador activo; las pérdidas se **truncan al saldo libre disponible** y se aplican antes de los premios, sin deuda ni requisito de solvencia.
- Infancia: una carta propia del mazo de su rol por turno, antes del D6.
- Juventud y Adultez: una Situación **compartida por rol/ronda**, resuelta **individualmente** cuando cada jugador del rol hace su turno; no simultánea.
- Juventud A/B determina tanto el efecto de Situación como la distancia A/B de Movimiento.
- Adultez A/B de Situación es independiente de A/B de Movimiento; no hay subastas en las cartas vigentes.
- Continúan **provisionales** otros parámetros del motor: +2 unidades por casillero adulto de recursos, mano de tres cartas, Dublín `next_turn`, heurísticas del agente, régimen de competencia, asignación de Perfiles y economía del juego. La frecuencia de aciertos no constituye validación humana.

## Resultado — 200 partidas

| Indicador | Mesa 6 | Mesa 10 |
|---|---:|---:|
| Partidas | 100 | 100 |
| Casamientos dentro de 100 rondas | 100 | 100 |
| Media de rondas | 14,30 | 13,88 |
| Mediana | 14 | 14 |
| P90 | 17 | 16 |
| Media de turnos ejecutados | 83,42 | 134,58 |
| Zona final Neutro | 76 | 79 |
| Zona final A | 6 | 6 |
| Zona final B | 18 | 15 |

En total, **155** parejas casadas en **Neutro**, **33** en **B** y **12** en **A**. 125 parejas ganadoras pasaron al menos un turno emparejadas pero incompatibles antes de terminar compatibles. Las 200 parejas se validaron en la zona al finalizar.

## Preferencia A/B de las 20.286 resoluciones

| Etapa | Rol | A | B | % A | Cartas ≥90% dominante |
|---|---|---:|---:|---:|---:|
| Infancia | Clarisa | 1.533 | 2.171 | 41,39% | 3/12 |
| Infancia | Lucas | 845 | 1.222 | 40,88% | 3/12 |
| Juventud | Clarisa | 3.728 | 3.931 | 48,67% | 0/24 |
| Juventud | Lucas | 1.904 | 1.933 | 49,62% | 0/24 |
| Adultez | Clarisa | 877 | 627 | 58,31% | 0/15 |
| Adultez | Lucas | 914 | 601 | 60,33% | 1/15 |

**Siete de las 102 cartas** alcanzan ≥90% en alguna opción: seis infantiles y una adulta. Ninguna de Juventud, cuyo movimiento vinculado multiplica los motivos para elegir distinto. No equivale a una medición de preferencias humanas.

## Coincidencia exacta cuando varios resuelven la misma carta y ronda

| Etapa | Mesa | Casos con ≥2 jugadores | Todos A o todos B | % unanimidad |
|---|---:|---:|---:|---:|
| Juventud | 6 | 1.449 | 586 | 40,44% |
| Juventud | 10 | 1.864 | 517 | 27,74% |
| Adultez | 6 | 298 | 206 | 69,13% |
| Adultez | 10 | 576 | 330 | 57,29% |

**Infancia no comparte una misma carta por rol y ronda**: la coincidencia debe estimarse al comparar resoluciones de una misma carta en turnos o partidas diferentes (`coincidencia_condicional_por_carta.csv`). El porcentaje de unanimidad cae en mesas de diez porque puede haber más resolutores, no necesariamente por mayor balance intrínseco.

## Integridad de SIMLOG

- **21.800 turnos** y **511.194 eventos**, con secuencias ordinales y estados completos antes/después de cada turno.
- **200 manifiestos** con SHA-256 por archivo y estado de validación `PASS`; todos los hashes se recalcularon al consolidar.
- Verificación por turno: `Afinidad_posicion_despues - Afinidad_posicion_antes = −1` para A, `+1` para B, `0` cuando no se ejecuta Situación.
- Zona antes/después recomputada desde el eje; Pareja_compatible antes/después recomputada desde ambos saldos. Se conserva el evento instantáneo `afinidad_desplazamiento` con carta, opción, saldos, zonas y compatibilidad de la pareja.
- Se mantienen SIMLOG: `turnos.csv`, `eventos.csv`, `eventos.jsonl`, `estados_jugadores.csv`, `estados_globales.csv`, `hitos.csv`, `recursos_por_ronda.csv`, `preferencias_situaciones.csv`, `preferencias_movimientos.csv` y `manifest.json`. Se agrega `orden_mazos.json`.
- La ejecución también supera **177 pruebas locales** (171 previas + 6 del nuevo modelo). Ejecución remota de GitHub Actions no verificada.

## Interpretación y próximos ajustes

El planificador con incentivo de Afinidad terminó el 77,5% de las veces en Neutro. Eso muestra adaptación del agente al requisito, **no prueba** que Neutro sea la mejor zona para personas. La economía sigue ofreciendo acceso rápido a Casamiento y presenta riesgo de partidas cortas o poca diferenciación de objetivos. En Infancia persisten cartas de desenlace casi fijo, especialmente `INF-C/L-01` y `INF-C/L-07` (100% en esta heurística). Conviene examinar esos dilemas primero, después contrastar con un planificador alternativo y finalmente realizar pruebas humanas con tiempos medidos.

Para reproducir: el catálogo JSON inmutable incluido es suficiente para ejecutar `python -m laboratorio.simular_mazos_vigentes_v2 --semillas 100 --rondas 100 --out resultados/simlog_v21`. Opcionalmente `python build_new_cards.py` regenera el mismo catálogo desde la extracción de Infancia y las constantes verificadas de Juventud/Adultez. Para obtener el análisis consolidado de 200 partidas con `python -m laboratorio.analizar_corrida_v21 --root resultados_simlog_v21`, ejecutar la simulación en las mismas cinco carpetas `bloque_01`…`bloque_05` con `--inicio` respectivamente `1,11,31,51,71` y `--semillas` `10,20,20,20,30`.
