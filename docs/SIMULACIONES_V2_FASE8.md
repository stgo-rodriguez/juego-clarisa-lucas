# Simulaciones v2.x — Fase 8: sensibilidad económica y progreso estratégico

**Documento rector:** Especificación Integral v2.0 Consolidada, 1/11/2026.  
**Estado:** experimentos **sintéticos**, no balance oficial.  
**Rama:** `feature/simulaciones-v2-movimiento`.  
**Ejecución:** 2/11/2026.

## Objetivo y alcance

Medir separadamente el impacto de variar los premios de Situación, la producción de Perfil, las casillas adultas y pérdidas de recursos **libres**. Se mantienen idénticas las semillas, preparación de mazos y condiciones iniciales para las comparaciones apareadas. Se emplean bots aleatorio y planificador, con competencia activada/desactivada, 6/10 jugadores, mano adulta de tres cartas y política experimental de Dublín `next_turn`.

La arquitectura del motor, hitos, Casa y Casamiento no se alteró; se agregó una **capa de laboratorio** para definir `StressScenario`. El motor v1.3 sigue intacto.

## Matriz experimental

| ID | Premio de Situaciones | Pérdidas libres extra | Casillero A/P/K/M adulto | Producción de Perfil |
|---|---:|---|---:|---:|
| `base_sintetica` | 100% | ninguna | 2 | 100% |
| `situaciones_menos_10` | 90% | ninguna | 2 | 100% |
| `situaciones_menos_20` | 80% | ninguna | 2 | 100% |
| `menos_20_perdidas` | 80% | −2 unidades en ~25% de las cartas | 2 | 100% |
| `menos_20_perdidas_casilla1` | 80% | idénticas | 1 | 100% |
| `menos_40_perdidas_casilla1` | 60% | idénticas | 1 | 100% |
| `estres_fuerte_tres_fuentes` | 50% | idénticas | 1 | 50% |
| `estres_extremo_diagnostico` | 25% | idénticas | 0 | 25% |

Las unidades enteras se reducen mediante una **selección reproducible por unidad de recurso**, identificada por semilla y carta; no se redondea el 10% de una sola unidad siempre hacia arriba. En subastas de apropiación se garantiza el **mínimo estructural de 1 unidad** para que la carta siga teniendo un beneficio apropiable: esto es un límite artificial experimental y debe considerarse al interpretar escenarios extremos. Las pérdidas nunca descuentan más recursos libres que los disponibles. **No atacan reservas ni hitos adjudicados.**

No se han modificado los importes de producción por casillero de Infancia ni Juventud; son los establecidos por el reglamento. Las cartas de Situación son **las sintéticas de Fase 7**, con 12 subastas por mazo adulto de 20 cartas, no mazos aprobados. La política de reciclado de cartas continúa siendo experimental.

## Corrida

- **20 semillas** por configuración, cada una observada en **8 escenarios × 2 tamaños × 2 agentes × 2 estados de competencia**, para **1.280 partidas**.
- Límite de **100 rondas** por partida, con censura explícita cuando no hubo Casamiento.
- **1.241 Casamientos y 39 partidas truncadas** en los 1.280 ensayos.
- La comparación se hizo por semillas emparejadas. Una partida truncada cuenta como 100 rondas al informar la media **con censura**; no se atribuye una duración real mayor ni una victoria futura.
- **126 pruebas locales** superadas, junto con la regresión de las fases 1–7.
- Corrección hallada: un bot que deseaba cambiar Perfil desde un mazo tapado agotado ahora intenta la pila visible cuando existe; si ambas fuentes se agotaron, no cambia. **No aparecen cartas artificiales** ni se reduce el costo del mercado.

### Planificador con competencia habilitada — resultados de referencia

| Escenario | 6 jugadores: casamientos/20 | Rondas medias (cap 100) | 10 jugadores: casamientos/20 | Rondas medias (cap 100) |
|---|---:|---:|---:|---:|
| Base sintética | 20 | 12,90 | 20 | 12,20 |
| Situaciones −10% | 20 | 13,15 | 20 | 13,10 |
| Situaciones −20% | 20 | 13,90 | 20 | 13,20 |
| −20% y pérdidas | 20 | 14,75 | 20 | 13,25 |
| −20%, pérdidas, casilla adulta 1 | 20 | 14,90 | 20 | 13,50 |
| −40%, pérdidas, casilla adulta 1 | 20 | 16,10 | 20 | 14,35 |
| Tres fuentes bajo estrés | 20 | 20,60 | 20 | 19,95 |
| Extremo diagnóstico | 16 | 47,95 | 16 | 48,85 |

La disminución del 10% aislada aumenta solamente 0,25 rondas (6 jugadores) o 0,90 rondas (10 jugadores). Al reducir también Perfil y casillas adultas, se observan diferencias mucho mayores. En el extremo, **8 de 40 partidas** de planificador competitivo no llegan a Casamiento antes del límite (4 por tamaño); no confundir una partida censurada con un empate reglamentario.

### Bot aleatorio y riesgo de partidas prolongadas

En el escenario de tres fuentes bajo estrés, el aleatorio sin competencia completó 20/20 partidas de 6 jugadores en 36,95 rondas promedio, frente a 20,45 del planificador sin competencia. Con diez jugadores: 39,10 frente a 21,00. Por lo tanto, la calidad de la política pesa mucho más en el resultado que el cambio de tamaño en estas condiciones experimentales.

En el extremo, **35 de 160 partidas** de todos los tratamientos quedaron truncadas. Las partidas inconclusas suelen conservar parte de los hitos individuales, pero no llegan a reunir los recursos y los requisitos conjuntos para acceder a la victoria. **Es una señal de un cuello de botella colectivo, no una estimación de la dificultad final del juego.**

## Métricas de calidad y límites interpretativos

Además de rondas y tasa de Casamiento, el CSV registra: turnos totales; porcentaje de turnos sin incremento de un **índice de progreso duradero** (comprobantes, hitos, pareja, Adultez, Casa); Títulos y Pasaportes obtenidos y conservados; primera pareja ganadora; transferencias de Casa; duelos por tipo, pujas, subastas, pérdidas de recursos libres y estados de salida.

**Índice de progreso:** no equivale a "turnos inútiles". Acumular un recurso para una compra futura puede ser una acción útil pero no aumenta el índice duradero. Por eso el indicador se llama `turns_without_durable_progress` y no debe interpretarse como porcentaje de turnos improductivos.

**Tiempo de mesa:** no hay cronometraje humano ni datos para asignar segundos a cada puja o duelo. Se entregan cantidades de eventos y tasas por 100 turnos, no estimaciones arbitrarias de minutos.

**Pérdida de reservas/hitos:** el módulo `interacciones_v2.py` ya contiene los procedimientos de ruptura y disputa; este experimento **no** activó pérdidas directas de reservas ni caídas de hito por cartas. La coordenada de retorno a Juventud sigue pendiente y no se inventó. El escenario `estres_extremo_diagnostico` no debe proponerse como configuración de juego.

**Intervalos y tamaño de muestra:** veinte semillas por celda sirven como señal exploratoria; para decisiones de balance, ampliar el conjunto de semillas y probar mazos con efectos definitivos.

## Implementación y reproducción

- `laboratorio/sensibilidad_v2.py`: generación de mazos y escenarios, evaluación de partida, resultados por grupo y diferencias apareadas; incluye reducciones de producción de Perfil en el ingreso desde Dublín.
- `laboratorio/consolidar_sensibilidad_v2.py`: concatena corridas y verifica que cada semilla tiene los ocho tratamientos en ambos tamaños, estrategias y condiciones competitivas.
- `tests/test_sensibilidad_v2.py`: tests de semilla estable, monotonicidad del ajuste, conservación de cartas, identidad de mazos entre tratamientos, igualdad con Fase 7, censura, reproducibilidad y agotamiento legal de perfiles.
- `simulador/agentes_v2.py`: corrección de disponibilidad de fuente del mercado de Perfil en modo sintético y general.
- `docs/datos_fase8/partidas_sensibilidad_v2.csv`: 1.280 observaciones.
- `docs/datos_fase8/resumen_sensibilidad_v2.json`: escenarios, resúmenes y diferencias por pares de semilla.

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -q
python -m laboratorio.sensibilidad_v2 --semillas 20 --rondas 100 --ambos-agentes --out resultados/fase8
```

Para distribución por lotes, usar `--desde-semilla 1`, `6`, `11` o `16` con `--semillas 5`, y luego ejecutar:

```bash
python -m laboratorio.consolidar_sensibilidad_v2 \
  --inputs batch_1/partidas_sensibilidad_v2.csv batch_2/partidas_sensibilidad_v2.csv \
           batch_3/partidas_sensibilidad_v2.csv batch_4/partidas_sensibilidad_v2.csv \
  --out resultados/fase8
```

## Conclusiones y próximos ensayos

1. La **producción de Perfil** y el flujo de recursos por destinos compensan las reducciones aisladas de Situaciones. No intentar balancear v2.0 modificando únicamente premios narrativos.
2. Conviene evaluar una grilla factorial controlada para separar causalmente Perfil, casilleros adultos y Situaciones, manteniendo constante el grado de competencia.
3. Las cartas sociales definitivas deben incorporar pérdidas y efectos apropiados con su frecuencia real. Diseñar una batería específica de reservas, pérdida de hitos y reingreso, una vez definido su caso límite.
4. Debe medirse **carga temporal de interacción** mediante observaciones reales de mesa; los recuentos de duelos/pujas, por sí solos, no prueban mejora de calidad.
5. Para decidir balance, proponer primero escenarios que produzcan tiempos y tasas intermedios y expandir al menos 100–200 semillas por celda; 20 semillas no justifican un ajuste definitivo.

**Integración continua:** el workflow existente se ampliará con tests y un smoke de Fase 8. Un resultado local no afirma éxito remoto de GitHub Actions.
