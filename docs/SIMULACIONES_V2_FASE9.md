# Clarisa & Lucas v2.x — Fase 9: factores de economía y rupturas juveniles

**Reglamento rector:** Especificación Integral v2.0 Consolidada, 1/11/2026.  
**Rama:** `feature/simulaciones-v2-movimiento`.  
**Estado:** implementación y ejecución local de experimentos exploratorios, no revisión de las reglas aprobadas.

## 1. Objetivo y metodología

La Fase 8 demostró que reducir solo las Situaciones no era suficiente para desacelerar drásticamente el juego. La Fase 9 separa **tres fuentes de ingresos** mediante un diseño factorial completo `2^3`:

| Factor | Código 0 (referencia) | Código 1 (reducción) |
|---|---|---|
| Situaciones | 100% de beneficios sintéticos | 60% |
| Perfil | 100% de producción | 60% |
| Casilleros Adultez | 2 unidades al caer | 1 unidad |

El experimento contiene **8 tratamientos**, 12 semillas × mesas de 6/10 × agentes aleatorio/planificador × competencia sí/no = **768 partidas**. El motor usa semillas emparejadas por bloque y conserva la composición inicial de los mazos sintéticos. Las trayectorias divergen después de las decisiones, como corresponde.

Las métricas incluyen rondas al Casamiento con censura al límite de **100 rondas**, porcentaje que alcanza Casamiento, turnos sin avance duradero y efectos factoriales marginales. Las diferencias de efectos se estiman dentro de cada semilla, manteniendo los otros factores en ambos niveles. Se calculan interacciones dobles y triple. Los intervalos normales 95% en el JSON son **orientativos**: 12 bloques por estrato no justifican inferencia confirmatoria ni equivalencia económica entre factores.

## 2. Resultados factoriales

**Casamientos:** 764/768 partidas; 4 truncadas al límite de 100 rondas. La economía sintética original sigue siendo generosa.

Agente **planificador**, con **competencia** activada (12 partidas por tratamiento/tamaño):

| Tratamiento | 6 jugadores, rondas cap promedio | 10 jugadores, rondas cap promedio |
|---|---:|---:|
| F000 (referencia, sin reducción) | 12,92 | 11,92 |
| F100 (solo Situaciones 60%) | 15,42 | 14,00 |
| F010 (solo Perfil 60%) | 14,50 | 14,50 |
| F001 (solo casilleros 1) | 13,00 | 11,92 |
| F111 (tres factores reducidos) | 18,58 | 17,08 |

Efectos marginales promedio de la reducción (promediados sobre las otras cuatro combinaciones), expresados en **rondas adicionales** (planificador competitivo):

| Fuente reducida | 6 jugadores | 10 jugadores |
|---|---:|---:|
| Situaciones 100→60% | +3,23 | +2,00 |
| Perfil 100→60% | +2,27 | +2,67 |
| Casilleros 2→1 | +0,19 | +0,42 |

Las diferencias de factor no representan cambios porcentuales equivalentes: pasar un casillero de 2 a 1 es −50%, los otros dos factores son −40%. En el estrato de 6 jugadores, el contraste de interacción Situaciones×Perfil promedió **+1,29 rondas** adicionales frente a la suma de ambos cambios; en diez jugadores fue −0,33. Los intervalos de la muestra son amplios, por lo que esta interacción es **una hipótesis, no una regla general**.

## 3. Reservas, ayuda inmediata y ruptura de pareja

Se añadió un parámetro **solo experimental** a `laboratorio/sensibilidad_v2.py`:

- `youth_reserve_loss_rate`, con valores 0, 0,15 y 0,35: probabilidad determinista por clave de activar un **ataque de 5 Amor reservado** cuando el jugador activo está en Juventud y tiene pareja.
- La pérdida se procesa durante su **Situación previa al movimiento** usando `InteractionV2.affect_pair_reserve`; el compañero puede aportar Amor libre inmediatamente. Si es insuficiente, se rompe la pareja, se liberan las reservas supervivientes y el jugador activo realiza su desplazamiento individual normalmente.
- **No se aplica** la pérdida directa de reservas en Adultez; regresarlo a Juventud requiere fijar primero la coordenada de retorno y el régimen de carta de movimiento tras cambiar de etapa durante la Situación. No se inventa esa regla.

Se ejecutaron **288 partidas** (12 semillas × 2 tamaños × 2 agentes × competencia sí/no × 3 niveles). Resultados generales, por nivel (96 partidas cada uno):

| Tasa experimental | Ataques | Reparaciones | Rupturas | Casamientos |
|---|---:|---:|---:|---:|
| 0% | 0 | 0 | 0 | 96/96 |
| 15% | 1.117 | 1.050 | 67 | 96/96 |
| 35% | 2.695 | 2.474 | 221 | 96/96 |

En particular, con **planificador competitivo** (12 partidas por celda):

| Jugadores | Sin pérdidas: rondas medias | Ataques 15%: rondas medias | Ataques 35%: rondas medias |
|---|---:|---:|---:|
| 6 | 12,92 | 13,75 | 14,67 |
| 10 | 11,92 | 13,00 | 14,17 |

**Interpretación:** el daño a la reserva introduce rupturas verificables, pero la mayor parte de los ataques se repara por la ayuda legal inmediata. En estos mazos generosos el progreso de los agentes puede recuperarse. La cifra 35% NO es una frecuencia recomendada; genera un número muy elevado de ataques repetidos en una misma partida. La formación inmediata de una nueva pareja después de una ruptura también puede amortiguar el efecto, porque el reglamento no impone espera automática.

## 4. Invariantes y pruebas de regresión

- La base sin intervenciones juveniles reproduce exactamente la ejecución anterior con la misma semilla.
- Se conserva el total de recursos tras afectar la reserva: pérdida consumida, ayuda legal o liberación de remanentes.
- Los ataques se aplican antes del movimiento y **solo** a parejas juveniles.
- `reserve_events = reserve_repairs + reserve_breaks`, y cada ruptura queda registrada en eventos económicos.
- Los ocho tratamientos factoriales existen exactamente una vez por bloque; se rechazan bloques incompletos o duplicados.
- Los contrastes de dos y tres factores se prueban contra una función artificial con coeficientes matemáticos conocidos.
- **136/136 pruebas locales superadas**, incluidas 10 nuevas pruebas de Fase 9.

## 5. Archivos reproducibles

- `laboratorio/factorial_v2.py`: ejecución y contrastes factoriales; exporta `partidas_factorial_v2.csv`, `analisis_factorial_v2.json` y `efectos_factoriales_v2.csv`.
- `laboratorio/rupturas_v2.py`: eventos juveniles de pérdida de reserva, ayuda y ruptura; exporta partidas y resúmenes con comparación apareada.
- `laboratorio/sensibilidad_v2.py`: extensión retrocompatible para ataques a reserva juvenil optativos (0 por defecto).
- `tests/test_fase9_v2.py`: pruebas factoriales y de pérdidas; junto a tests de fases 1–8.
- `docs/datos_fase9/`: copias verificables de los resultados principales de esta ejecución.

Ejecutar desde raíz:

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -q
python -m laboratorio.factorial_v2 --semillas 12 --rondas 100 --out resultados/fase9_factorial
python -m laboratorio.rupturas_v2 --semillas 12 --rondas 100 --out resultados/fase9_reservas
```

## 6. Decisiones de diseño que permanecen pendientes

1. **Mazos definitivos**: cantidades, negativos, subastas, elegibilidad y efecto por etapa/personaje. Las 6 barajas actuales son sintéticas y ninguna prueba demuestra calidad final de v2.0.
2. **Regreso a Juventud** por pérdida de hito o reserva en Adultez: posición, obtención/descarte de manos en el turno y continuidad del desplazamiento. Mantenerlo parametrizado y no simular arbitrariamente.
3. **Balance temporal**: registrar la duración real de duelos, ofertas, elecciones de cartas y cambios de Perfil en pruebas de mesa; el número de turnos no mide el tiempo de jugador.
4. **Balance de agente y frecuencia**: repetir con 100–200 semillas por estrato solo después de adoptar mazos plausibles; comparar estrategias conocidas frente a decisiones menos informadas, sin bots con conocimiento del futuro.

**Conclusión técnica:** en este universo experimental, Perfil y Situaciones dominan el efecto marginal sobre las rondas. Los recursos por casilleros adultos tienen menor efecto marginal en las condiciones evaluadas. Los ataques a reservas generan interacción y rupturas reales, pero su frecuencia elevada puede aumentar el trabajo de mesa sin alterar las tasas de victoria bajo la economía generosa. No adoptar los valores experimentales como reglas aprobadas.
