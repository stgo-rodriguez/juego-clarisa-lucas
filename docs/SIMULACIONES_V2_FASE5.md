# Simulaciones v2.x — Fase 5: decisiones automáticas y partidas sintéticas completas

**Reglamento rector:** Especificación Integral v2.0 Consolidada, 1/11/2026.  
**Código:** rama `feature/simulaciones-v2-movimiento` del repositorio `stgo-rodriguez/juego-clarisa-lucas`.

## 1. Qué se integró

- Dos políticas reproducibles: **aleatoria legal** y **planificador heurístico** (usa solo Situación del turno, recursos, posición, carta juvenil personal o mano adulta propia y Perfil público; no consulta cartas futuras).
- Secuencia económica completa en el prototipo: Infancia con D6 y Situaciones, examen UTN, carta de Perfil, inversión en proyectos Título/Pasaporte, adjudicación con dado y pago, encuentro y reserva de Pareja, ingreso Dublín, movimiento adulto, Casa y salida a Casamiento.
- Acción después del movimiento del jugador activo: adjudicar cuando aterriza exactamente en Universidad/Trámite; formar Pareja si coincide exactamente; financiar proyectos; comprar Casa si termina en (3,3); efectuar cambio voluntario de Perfil si es elegible.
- Mercado físico de Perfil-Afinidad: 16 cartas por personaje; elección entre primera carta tapada y primera visible; carta abandonada arriba de la pila visible o abajo del mazo tapado; **pago de 3 A + 3 P + 3 K + 3 M libres**; máximo un cambio por turno. Se comprueba conservación de las cartas, sin duplicación.
- **Error detectado y corregido en la Fase 4:** `RoundEngine.rng_dice` había quedado dentro de un comentario, de modo que las partidas sin dados inyectados fallaban. Se añadió un test que usa un D6 generado por el motor.
- Instrumentación: 6/10 jugadores, mano adulta de 3/4 cartas, número de turnos, hitos, intervenciones económicas básicas, perfiles cambiados, transferencias de Casa, frecuencia de victoria de la primera pareja, duración y trazas opcionales.

## 2. Escenario de prueba, no reglamento aprobado

Las seis barajas de Situación **NO están definidas para v2.0**. Para probar todos los hitos desde cero sin regalar títulos ni pasaportes, el laboratorio usa seis mazos sintéticos (20 cartas cada uno) con ganancias positivas y secuencia barajada. Se aplican al jugador activo; en Juventud se elige A/B junto con la distancia.

El tablero adulto rinde **2 unidades** por casillero A/P/K/M en este experimento. El mazo adulto sintético contiene **120 cartas** (cuatro copias distinguibles de los 30 pares ordenados distintos de 1 a 6). Se usa la política experimental Dublín `next_turn` y no se simulan disputas, duelos, subastas sociales, cambios de personaje ni pérdidas de hitos. Los proyectos se instancian uno por persona y clase para garantizar oferta suficiente; la adjudicación y competencia de inversión aún son simplificadas.

**Por tanto, las cifras no permiten aceptar ni rechazar el balance económico real del juego.** Sí sirven para comparar comportamientos de los agentes, verificar que el flujo puede alcanzar Casamiento y localizar situaciones de cuello de botella del propio simulador.

## 3. Ejecución local

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -v
python -m laboratorio.experimento_agentes_v2 --semillas 60 --rondas 80 --mano 3 --out resultados/fase5/mano3
python -m laboratorio.experimento_agentes_v2 --semillas 60 --rondas 80 --mano 4 --out resultados/fase5/mano4
```

Se completaron **72 pruebas unitarias** en el entorno local y **480 partidas sintéticas**: 60 semillas × dos tamaños × dos políticas × dos manos. El límite es de 80 rondas. La partida termina cuando una pareja logra casarse; si no, queda censurada en la ronda 80.

### Resultados agregados

| Participantes | Mano | Política | Partidas terminadas en Casamiento / 60 | Rondas medias* | Primera pareja gana | Traspasos Casa medios |
|---:|---:|---|---:|---:|---:|---:|
| 6 | 3 | Aleatorio | 60 | 32,92 | 34 | 0,18 |
| 6 | 3 | Planificador | 60 | 13,05 | 41 | 1,37 |
| 6 | 4 | Aleatorio | 58 | 34,10 | 30 | 0,17 |
| 6 | 4 | Planificador | 60 | 12,90 | 32 | 1,57 |
| 10 | 3 | Aleatorio | 60 | 27,42 | 19 | 0,27 |
| 10 | 3 | Planificador | 60 | 12,78 | 15 | 3,47 |
| 10 | 4 | Aleatorio | 60 | 27,28 | 22 | 0,52 |
| 10 | 4 | Planificador | 60 | 12,72 | 19 | 3,78 |

\* Rondas medias hasta ganar o alcanzar el límite de 80; el promedio incorpora partidas censuradas.

La tasa de éxito sintética es **478/480**, señal inequívoca de que estas Situaciones hipotéticas entregan demasiados recursos para evaluar dificultad de victoria. La métrica más informativa en esta fase es la **disparidad de duración por política**: el planificador finaliza sustancialmente antes, pero se desconoce cuánto de esa ventaja subsistirá con los mazos sociales reales y sin la inflación sintética de recursos.

Las diferencias entre manos de 3 y 4 son pequeñas en estas condiciones. **No se interpreta como equivalencia de balance**: algunas partidas duran apenas una docena de rondas y el agente explota información posicional muy básica.

La compra/transferencia repetida de Casa merece analizarse con la mecánica social real: los planificadores generan más competencia por la vivienda, incluso cuando una pareja ya cuenta con Casa. No se detectó un bypass del gasto por compra en las pruebas: la operación conserva la contabilidad y aplica duelos contra banco o propietarios; falta incorporar estrategias defensivas y pujas reales.

## 4. Limitaciones y prioridades

1. **Cambiar los seis mazos sintéticos por efectos versionados v2.0**. Incorporar las Situaciones sociales reales, sus tres modos de intervención, cooperación y subasta por apropiación de una sola ronda.
2. **Desarrollar un agente estratégico más riguroso**: simulación de acciones legales, inversión cooperativa, transferencias de comprobantes, valor de la Casa ante amenaza y plan conjunto de manos. El actual `planificador` es un algoritmo heurístico, no un agente óptimo.
3. **Implementar interacciones faltantes**: pérdida de hitos y retorno desde Adultez, duelos con retirada, ruptura/reemplazo de pareja, cambio de personaje y disputa de Perfil.
4. **Auditar en CI** el flujo de generación de dados y los 72 tests. El éxito local no implica GitHub Actions exitoso.
5. **Repetir la comparación contrafactual** con políticas de Dublín, escenarios económicos más exigentes y, finalmente, cartas oficiales antes de presentar conclusiones de duración y balance.

## 5. Archivos reproducibles

- `simulador/agentes_v2.py` — decisiones de A/B, dirección, economía y afinidad.
- `simulador/transiciones_v2.py` — mercado de Perfil con conservación física.
- `laboratorio/experimento_agentes_v2.py` — generador de seis mazos sintéticos, semillas, partidas y CSV.
- `tests/test_agentes_v2.py` — 8 tests nuevos, incluida regresión del D6 sin inyección.
- `docs/datos_fase5/comparacion_480_partidas.csv` — todas las partidas con sus campos de control.
- `docs/datos_fase5/resumen_global_fase5.json` — definiciones del escenario y medias.

**No se modificó** el simulador histórico v1.3.