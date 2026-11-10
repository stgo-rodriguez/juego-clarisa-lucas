# SIMLOG v2.2 — Auditoría económica y comparación de políticas (10/11/2026)

**Estado:** experimento controlado completo, no balance definitivo.  
**Resultados sin ZIP en Drive:** [hoja de resultados (12 configuraciones)](https://docs.google.com/spreadsheets/d/1hnv3bKisbZNvu_t1UlyKQJ5ZKRuIlgfg/edit).  
**Semillas:** 3201–3240 en todas las configuraciones; máximo 100 rondas, 40 partidas por tamaño y escenario.  
**Total:** 480 partidas iniciadas, 455 casamientos, 11 interrupciones por regla pendiente y 14 partidas al límite sin casamiento. De ellas, 400 corresponden a la matriz de cinco escenarios y 80 al control sin banco.

## Matriz de resultados

| Esc. | Política | Mano | Banco | Jugadores | Casamientos | Bloqueos | Límite | Mediana | P80 | Diversidad A/B primera ronda |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| A | Planificador | 3 | Sí | 6 | 40/40 | 0 | 0 | 19,5 | 22 | 30% |
| A | Planificador | 3 | Sí | 10 | 40/40 | 0 | 0 | 19 | 20 | 40% |
| B | Mixto | 3 | Sí | 6 | 39/40 | 1 | 0 | 22 | 25 | 63,75% |
| B | Mixto | 3 | Sí | 10 | 40/40 | 0 | 0 | 20,5 | 24 | 85% |
| C | Aleatorio | 3 | Sí | 6 | 26/40 | 4 | 10 | 45 | 64 | 71,25% |
| C | Aleatorio | 3 | Sí | 10 | 31/40 | 5 | 4 | 56 | 71 | 97,5% |
| D | Mixto | 4 | Sí | 6 | 39/40 | 1 | 0 | 22 | 25 | 63,75% |
| D | Mixto | 4 | Sí | 10 | 40/40 | 0 | 0 | 21 | 24 | 85% |
| E | Planificador | 4 | Sí | 6 | 40/40 | 0 | 0 | 20 | 21 | 30% |
| E | Planificador | 4 | Sí | 10 | 40/40 | 0 | 0 | 19 | 20 | 40% |
| F | Planificador | 3 | **No** | 6 | 40/40 | 0 | 0 | 20 | 23 | 30% |
| F | Planificador | 3 | **No** | 10 | 40/40 | 0 | 0 | 20 | 22 | 40% |

**Todas las medianas y P80 corresponden solamente a partidas terminadas en Casamiento**. No se atribuye duración definitiva a las partidas bloqueadas o que agotaron 100 rondas.

## Hallazgos

1. **Banco implementado y activo:** tasa de 20,48–21,60 canjes/100 turnos en planificadores con mano de 3; 26,49–26,83 en mixtos; 34,44–34,58 en aleatorios. Canjes 2:1 entre recursos adyacentes, saldos libres, una operación por turno. Los saldos se auditan.
2. **Efecto del banco, emparejado por semilla:** en planificadores con mano 3, media de rondas 20,55→19,82 (6 jugadores) y 19,95→18,68 (10 jugadores) al activar banco. Diferencias de 0,73 y 1,27 rondas, respectivamente. No probar causalidad generalizable fuera del experimento.
3. **Diversidad A/B:** en 6 jugadores, planificadores 30% vs mixtos 63,75%; en 10, 40% vs 85%. Políticas 100% aleatorias muestran 71,25% y 97,5%, indicador esperado por azar y **no** evidencia de mayor profundidad estratégica.
4. **Planificadores ganan más en mesas mixtas:** con mano 3 constituyen 55 de 78 integrantes ganadores (70,51%) en 6 jugadores y 69 de 80 (86,25%) en 10. La mitad de los participantes son planificadores. Estas proporciones no son tasas de victoria individual causalmente ajustadas; pueden influir parejas mixtas, orden de turno y estructura de heurísticas.
5. **Mano 3 vs 4:** las medias cambian poco: planificadores 19,82→19,55 (6) y 18,68→18,38 (10). En mixtos 22,44→22,49 (6) y 21,15→21,00 (10). La evidencia disponible no justifica fijar cuatro cartas todavía.
6. **Problema reglamentario:** 11 partidas alcanzaron una ruptura adulta cuya posición de regreso a Juventud está pendiente (P4). Se registran como `rule_pending` y no como derrota. Ninguna continuación se inventa. De las 400 partidas de la matriz, 14 llegaron al límite sin casamiento (todas en escenario aleatorio).

## Trazabilidad

- [Validación del banco, A/B real, manos y agentes](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42859860216)
- [Matriz principal, 400 partidas](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42860124637)
- [Control sin banco, 80 partidas](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42860451663)
- [Revisión de diversidad incluyendo primeras rondas de partidas bloqueadas](https://github.com/stgo-rodriguez/juego-clarisa-lucas/actions/runs/42860904678)

**Alcances:** los archivos de resumen/partidas de cada trabajo están como artefactos de GitHub Actions (con retención limitada). El libro consolidado en Drive preserva estos resultados sin ZIP, pero no contiene todas las trazas de eventos. Las partidas bloqueadas conservan `turnos_completados.csv` separado y sin manifiesto de partida válida.

## Pendientes

- **P4 del reglamento:** posición de retorno y política de cartas cuando una pareja rompe en Adultez.
- Mazo físico de Movimiento adulto: se siguen usando cartas **`SYN-A` sintéticas** (30 pares ordenados, cuatro repeticiones), no composición aprobada.
- Políticas humanas: el bot aleatorio mantiene reglas heurísticas para algunos tipos de acciones. No extrapolar estas tasas a partidas humanas.
- Profundizar en consumo y sobrantes por etapa, fuentes y política antes de recalibrar Cartas de Situación.
- Repetir con más semillas y políticas intermedias antes de concluir sobre duración y balance.
