# Clarisa & Lucas v2.x — Fase 10 · Importación de cartas y calibración preliminar

**Reglamento rector:** Especificación Integral v2.0 Consolidada (01-11-2026).  
**Tipo de experimento:** comparativo y exploratorio; **NO es un mazo aprobado ni una validación de balance**.  
**Rama:** `feature/simulaciones-v2-movimiento`.

## 1. Fuentes reales recuperadas

1. [Cartas de Situación v0.1](https://docs.google.com/spreadsheets/d/1C3s3lXEJ10VPtnvjhAtxkFGE1SuaEOVcH-dGkHefXJI/edit): **78 cartas históricas**: 24 Infancia/Adolescencia, 24 Juventud, 30 Adultez. Las 30 de Adultez históricas se conservan como respaldo, pero **no** se combinan con los diseños multiverso en los mazos de esta fase.
2. [Mazos Adultez v2.0 · 15 Clarisa + 15 Lucas](https://docs.google.com/spreadsheets/d/15t9oPXdH2hkh5asGXPZsC3E3TMkF_fKU2TyC60BaJbA/edit): **30 propuestas v0.2 MULTIVERSO NO APROBADAS**, con los JSON de efectos, restricciones de objetivos, reglas específicas de puja y las correspondientes cartas espejo.

Ambos documentos se recuperaron desde Google Drive, de solo lectura, y se importaron a `docs/datos_fase10/catalogo_fuentes_situaciones_v2.json`, conservando títulos, textos, efectos y estado de propuesta. La auditoría permite vincular cada carta con su identificador original.

## 2. Configuración de seis mazos para ensayo

| Etapa | Clarisa | Lucas | Fuente y condición |
|---|---:|---:|---|
| Infancia | 24 | 24 | 24 históricas I01–I24 duplicadas por rol (solo hipótesis) |
| Juventud | 24 | 24 | 24 históricas J01–J24 duplicadas por rol (solo hipótesis) |
| Adultez | 15 | 15 | 15 pares espejo v0.2 propuestos (no aprobados) |
| **Total** | **63** | **63** | **126 cartas físicas experimentales** |

**Adultez por personaje:** 3 elecciones individuales, 5 conflictos con otra versión, 3 cooperaciones y 4 subastas de apropiación. Los pares espejo usan los mismos efectos JSON, pero títulos y narraciones propios de Clarisa o Lucas.

### Convenciones de simulación, no decisiones de diseño

- Infancia: la elección A/B del texto histórico se realiza en el turno sin afectar el dado D6.
- Juventud: **una sola letra A/B** determina a la vez el desenlace de la Situación histórica y la distancia de la carta de Movimiento propia.
- Los mazos compartidos de Juventud/Adultez se revelan por personaje y ronda, se barajan y reciclan sin modificación del contenido. El reciclado es una convención experimental.
- Pérdidas ordinarias afectan **solo recursos libres**, hasta agotar el saldo; no invaden reservas de Pareja o Casa sin texto explícito.
- Los efectos de los conflictos y cooperaciones afectan a **otra versión del mismo personaje** según el rango de etapas de cada carta. El bot elige objetivos y opciones con una heurística temporal.
- La cooperación acepta o rechaza según solvencia de ambas partes y política del bot, no por una obligación universal.
- Las subastas adultas usan UNA SOLA RONDA y la modalidad de cada ficha: recurso único, elección previa entre dos recursos u ofertas heterogéneas evaluadas subjetivamente por el activo. Solo el ganador paga al activo. Cuando se rechazan todas las ofertas o no hay oferentes, las cuatro cartas propuestas especifican cobrar el beneficio completo.
- Importes de casilleros adultos: **2 por casilla**, experimental. Mazo adulto A/B de movimiento, política `next_turn` de Dublín y comportamiento de bots continúan experimentales. No se agregan Tiempo, muros, depósitos ni nuevas reglas.
- Las cartas adultas de este origen **no dañan expresamente reservas de pareja**: la ausencia de rupturas por esas cartas no permite juzgar la mecánica de ruptura.

## 3. Comparación de 320 partidas

40 semillas por mesa (6/10), bot (aleatorio/planificador) e intervención competitiva (apagada/activada). Para cada configuración se ejecutó una partida con las propuestas documentadas y un control **apareado por semilla** con el escenario sintético base de la Fase 9. Máximo de 100 rondas. Se obtuvieron 320/320 matrimonios con propuestas y 320/320 con controles sintéticos.

| Mesa | Bot | Competencia | Rondas sintéticas | Rondas propuestas | Diferencia propuesta − sintética |
|---|---|---|---:|---:|---:|
| 6 | Aleatorio | No | 32,58 | 36,92 | +4,35 |
| 6 | Aleatorio | Sí | 33,08 | 35,50 | +2,42 |
| 6 | Planificador | No | 13,00 | 15,75 | +2,75 |
| 6 | Planificador | Sí | 13,00 | 15,65 | +2,65 |
| 10 | Aleatorio | No | 27,88 | 31,88 | +4,00 |
| 10 | Aleatorio | Sí | 27,60 | 30,35 | +2,75 |
| 10 | Planificador | No | 12,45 | 14,43 | +1,98 |
| 10 | Planificador | Sí | 12,43 | 13,97 | +1,55 |

Los intervalos aproximados de 95% del cambio medio son más estrechos para el planificador que para el bot aleatorio. No se deben extrapolar fuera de los mazos y bots utilizados. Los resultados **no** evalúan el atractivo humano de una decisión, solo su secuencia, economía y duración.

### Interacción social y posible sobrecarga

| Mesa, bot competitivo | Conflictos adultos/partida | Cooperaciones/partida | Subastas/partida | Ofertas/partida | Duelos/partida |
|---|---:|---:|---:|---:|---:|
| 6, Aleatorio | 19,83 | 12,33 | 16,68 | 24,88 | 27,48 |
| 6, Planificador | 3,18 | 2,68 | 2,78 | 5,10 | 4,17 |
| 10, Aleatorio | 27,63 | 16,08 | 21,80 | 65,88 | 67,42 |
| 10, Planificador | 3,30 | 2,33 | 3,05 | 11,62 | 9,03 |

La carga del agente aleatorio con diez jugadores es especialmente alta. Es una alerta para cronometrar el turno y verificar la frecuencia de activación de cartas compartidas, **no** una prueba suficiente para eliminar subastas o duelos.

## 4. Diagnóstico y límites

1. **Persistencia de economía abundante:** todas las partidas se casan bajo 100 rondas, incluso con los textos recuperados. Las seis barajas no están balanceadas por el solo hecho de existir; no aprobar premios ni pérdidas todavía.
2. **Adultos con interacción real:** las 30 propuestas de Adultez v0.2 son mucho más específicas que los efectos genéricos anteriores; ahora se pueden medir subastas/cooperaciones/conflictos de forma separada.
3. **Doble identidad de documentos:** los 78 históricos **no** equivalen a los 126 registros físicos de esta prueba. Se duplican 48 cartas de I/J para producir seis mazos y se sustituyen las 30 históricas adultas por 30 propuestas más recientes, conservando su procedencia.
4. **Sesgo de decisión:** el bot planificador selecciona opciones según escasez de recursos y puede rechazar intervenciones que jugadores humanos sí elegirían. La comparación no prueba causalidad pura; cambiar las cartas altera las decisiones futuras.
5. **Reglas abiertas:** seis mazos definitivos, ajuste de premios, cantidades adultas, sincronización Dublín, política de reciclado, elección de objetivos y evaluación de ofertas heterogéneas. No se consideran resueltas por el código.
6. **Caso de ruptura adulta:** no se introduce ataque a reservas porque la propuesta de Adultez no lo define; sigue pendiente decidir el casillero de retorno y la secuencia del turno después de un retroceso.

## 5. Próximas pruebas propuestas (sin reabrir decisiones cerradas)

- Comparar tres niveles de ingresos de las **cartas documentadas** mediante ajuste independiente de premios positivos, preservando costos, pérdidas y estructura narrativa.
- Someter la composición 3/5/3/4 de Adultez a análisis de exposición social por ronda y duración de interacción humana, especialmente con diez participantes.
- Diseñar y validar las **48 situaciones I/J por rol** sin duplicar necesariamente el mismo texto entre personajes; se requiere trabajo editorial, no solo balance numérico.
- Probar consecuencias de rupturas adultas una vez especificados posición de retorno y continuidad, sin inventar esas reglas en la implementación.

## 6. Reproducción

```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_*_v2.py' -v
PYTHONPATH=. python -m laboratorio.auditoria_mazos_propuestos_v2 --out resultados/fase10_auditoria
PYTHONPATH=. python -m laboratorio.experimento_mazos_propuestos_v2 --semillas 40 --rondas 100 --out resultados/fase10
```

Archivos: `simulador/mazos_propuestos_v2.py`, `laboratorio/experimento_mazos_propuestos_v2.py`, `laboratorio/auditoria_mazos_propuestos_v2.py`, `tests/test_mazos_propuestos_v2.py`, `docs/datos_fase10/`.

**Pruebas locales:** 148/148 aprobadas. **CI remoto:** configurarlo y comprobar resultado de GitHub Actions antes de afirmar que está aprobado en CI.