# Clarisa & Lucas — Auditoría del duelo ordinario y simulaciones corregidas (10-11-2026)

**Defecto:** la sección 18.1 de la especificación v2.2/v2.3 exige que un duelo ordinario enfrente jugadores del mismo rol. El controlador elegía adversarios de cualquier rol y el ejecutor no verificaba la restricción.

**Hallazgo histórico aportado en auditoría:** 1.339 duelos ordinarios inválidos distribuidos en 326 de las 350 partidas de seis jugadores de la corrida original v2.2 (93,1%). Estos datos se refieren **solo** a duelos ordinarios; una disputa de Título entre personajes de diferente rol sí está permitida por la sección 09.1.

## Cambios implementados

1. **Motor:** `simulador/interacciones_v2.py`, `InteractionV2.duel`: para `kind='ordinario'`, rechazo temprano cuando `challenger.role != defender.role`, antes de dados, retiro, uso de duelo o transferencia.
2. **Bots:** `simulador/competencia_v2.py`, `_choose_duel`: excluir rivales del otro rol exclusivamente de la elección de duelo ordinario; conservar disputas de Título entre roles diferentes y duelos de Perfil de mismo rol.
3. **SIMLOG:** cada evento de duelo indica `challenger_role`, `defender_role` y `same_role`; el validador rechaza cualquier duelo ordinario con roles distintos tanto en la v2.2 auditada como en v2.3.
4. **Pruebas:** rechazo sin consumo de turno ni transferencia, selección por bot, duelo ordinario válido entre roles iguales y disputa de Título cruzada válida. Regresión aprobada en Python 3.11/3.13.

## Reejecución auditada

[Ver ejecución de las 1.400 partidas en GitHub Actions](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42893664186)

**Diseño:** 350 partidas por combinación versión × cantidad de jugadores (4 combinaciones), semillas 2001–2350 en cada una, 100 rondas máximas, todos los agentes `planificador`, mano de 3 cartas, conversión bancaria deshabilitada y cartas adultas SYN-A sintéticas. Es una comparación controlada **entre las ramas auditadas** (2.2 y 2.3) con el mismo motor corregido y misma semilla, no una reproducción bit a bit de las trazas iniciales defectuosas.

| Métrica | v2.2 — 6 | v2.3 — 6 | v2.2 — 10 | v2.3 — 10 |
|---|---:|---:|---:|---:|
| Partidas iniciadas | 350 | 350 | 350 | 350 |
| Casamientos | 350 | 350 | 350 | 350 |
| Reglas pendientes bloqueantes | 0 | 0 | 0 | 0 |
| Mediana de rondas | 21 | 20 | 20 | 20 |
| P80 de rondas | 24 | 24 | 22 | 22 |
| Media de rondas | 21,000 | 20,880 | 19,957 | 19,720 |
| Turnos | 43.196 | 42.910 | 68.168 | 67.521 |
| Duelos totales | 2.384 | 2.457 | 6.197 | 6.199 |
| Duelos ordinarios **válidos** | 1.902 | 1.967 | 4.927 | 4.937 |
| Duelos de hito | 72 | 72 | 119 | 117 |
| Duelos de Perfil | 410 | 418 | 1.151 | 1.145 |
| Duelos de hito entre roles distintos, legales | 9 | 9 | 11 | 10 |
| **Duelos ordinarios entre roles distintos** | **0** | **0** | **0** | **0** |
| Encuentros con propietarios de Casa | — | 943 | — | 2.041 |
| Intentos de disputa de Casa | — | 909 | — | 1.969 |
| Cambios de propietario de Casa | — | 403 | — | 836 |

**Totales:** 1.400 partidas, 1.400 Casamientos, 1.400 trazas completas auditadas, 13.733 duelos ordinarios válidos, **0** inválidos. Hubo 39 disputas de hito legales entre roles diferentes. En v2.3 corregida se produjeron **1.239** cambios de propietario (403+836).

## Comparación con resultados anteriores a la corrección

Los resultados históricos v2.2/v2.3 se consideran **provisionales por defecto de duelos**. La duración agregada permanece similar, lo cual **no** hace irrelevante el defecto: las transferencias de recursos y la identidad de los participantes afectados cambian, aunque una mediana sea parecida.

La v2.3 anterior registró 1.290 cambios de propietario (415 mesas de seis, 875 mesas de diez). La v2.3 corregida registró 1.239 (403 y 836), **51 menos en total**. No atribuir causalidad exclusivamente a los duelos en indicadores que también dependen de trayectorias y decisiones posteriores.

En la reejecución de seis jugadores, el P80 de v2.3 es 24 en lugar de 23 de la corrida previa. Las medianas de v2.3 son 20 rondas para ambos tamaños de mesa.

## Validación automática por partida

El workflow verificó que:
- Cada configuración posee exactamente 350 semillas únicas, 2001–2350, sin ausencias ni duplicaciones.
- Cada traza completa declara la versión y reglas correctas y pasa SHA-256 de archivos declarados.
- Se auditan eventos `duel` con retador/defensor, roles y tipo; el campo `same_role` debe coincidir con ambos roles.
- Un duelo ordinario con roles diferentes causa error de la auditoría; **ninguno fue encontrado**.
- Se permiten disputas de hito entre roles diferentes, con proyecto identificable.
- Se preserva la restricción de mismo rol para disputas de Perfil.
- Las partidas bloqueadas por P4 se identificarían como `rule_pending`, pero no se presentaron.

## Enlaces y entregables

- [CI de corrección común, Python 3.11/3.13](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42893438431)
- [CI rama v2.2](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42893857305)
- [Pull request v2.2 #8](https://github.com/stgo-rodriguez/juego-clarisa-lucas/pull/8)
- [Pull request v2.3 #9](https://github.com/stgo-rodriguez/juego-clarisa-lucas/pull/9)
- [Resultados y trazas por versión y mesa](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42893664186)

Los ocho artefactos de GitHub Actions (cuatro resúmenes CSV/JSON y cuatro conjuntos de trazas) tienen retención limitada, **30 días**. Este documento y el CSV de comparación quedan preservados en el repositorio, sin necesidad de extraer ZIP para revisar los indicadores.

Las modificaciones permanecen en PRs abiertos hasta revisión e integración. No se reescriben simulaciones históricas, y P4/mazo adulto siguen siendo pendientes de especificación.
