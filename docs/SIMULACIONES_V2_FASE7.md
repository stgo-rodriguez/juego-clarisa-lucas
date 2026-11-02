# Simulaciones v2.x — Fase 7 · Competencia integrada a los agentes

**Fecha de ejecución:** 2 de noviembre de 2026  
**Rama:** `feature/simulaciones-v2-movimiento`  
**Documento rector:** Especificación Integral v2.0 Consolidada, 1/11/2026.  
**Estado:** experimento de simulación, **NO** balance de la versión aprobada.

## Alcance implementado

- `simulador/competencia_v2.py`: `CompetitiveController` ejecuta **subastas antes del movimiento** mediante la Situación adulta y **duelos después del movimiento** del activo. No modifica la mano del compañero ni agrega turnos.
- `laboratorio/experimento_competencia_v2.py`: crea seis mazos sintéticos idénticos entre tratamientos; 12 de 20 cartas adultas de cada rol contienen subastas experimentales (4 de cada modalidad). El tratamiento sin competencia recibe el beneficio completo cuando nadie puja; el tratamiento con competencia permite pujas y duelos.
- `tests/test_competencia_v2.py`: validaciones de conservación, subastas compartidas, solvencia, pareja excluida, una ronda, ejecución en turno real, duelos, control sin ofertas, determinismo y regreso pendiente.
- `docs/datos_fase7/partidas_competencia_v2.csv`: 320 filas, identificadas por semilla, tamaño, política y tratamiento.
- `docs/datos_fase7/resumen_competencia_v2.json`: resultados agregados y diferencias **apareadas** por semilla.

### Reglas de diseño que se preservan

1. En una subasta existe **una sola oportunidad** por participante; una oferta nueva debe igualar o mejorar la vigente; el activo y su compañero están excluidos; solo el adjudicatario paga al activo y recibe la porción apropiable.
2. El **orden de puja por orden global de jugadores** es una convención exclusivamente experimental. Las preferencias de recursos (variables según la escasez del bot) son una estimación subjetiva del activo, **no** equivalencias automáticas del reglamento.
3. En cada duelo tira primero el defensor; el retador decide después si paga 1 P para retirarse o tira D6; un duelo iniciado por turno. Se exige solvencia libre; no se utilizan reservas.
4. Los bots intentan duelos de hito, Perfil y ordinarios si la coincidencia y los requisitos permiten ejecutarlos. Si un hito adulto implicaría retorno sin coordenada juvenil aprobada, **se omite** esa disputa; el motor no inventa la posición.
5. **No se simulan rupturas espontáneas.** Su motor existe en Fase 6, pero en este escenario no hay cartas que ataquen expresamente las reservas de pareja. La tasa cero de rupturas aquí no permite inferir nada del juego final.

## Diseño del experimento

- **320 partidas:** 40 semillas × 2 tamaños (6 y 10 jugadores) × 2 políticas (`aleatorio`, `planificador`) × 2 tratamientos (sin/con competencia).
- **80 rondas** máximas y mano adulta de **3 cartas**, política Dublín `next_turn` (experimental).
- Mismas cartas sintéticas y mismas semillas para los tratamientos comparados; se derivan resultados por pares de misma semilla.
- Se emplean cifras de Adultos **2 recursos por casillero A/P/K/M** como hipótesis, beneficios adultos muy generosos, y 12/20 situaciones adultas con subasta. No representan mazos oficiales.
- Las subastas sin ofertas hacen que el activo cobre todo el beneficio (`no_bid_effect=full`); con ofertas ganadoras se redistribuye entre activo y adjudicatario. Recurso y porción se fijan en cada carta sintética.
- Una política de bot fija puja máxima de 3 recursos y apuesta ordinaria de 2 M. Son **heurísticas**, no límites de reglas v2.0.
- Se cambia únicamente la disponibilidad de competencia dentro de cada par de partidas; el estado diverge naturalmente tras cada intervención.

## Resultados

| Jugadores | Bot | Competencia | Partidas casadas / 40 | Rondas medias | Duelos medios/partida | Ofertas medias/partida |
|---:|---|---|---:|---:|---:|---:|
| 6 | Aleatorio | No | 40 | 32,58 | 0 | 0 |
| 6 | Aleatorio | Sí | 40 | 33,08 | 24,98 | 96,22 |
| 6 | Planificador | No | 40 | 13,00 | 0 | 0 |
| 6 | Planificador | Sí | 40 | 13,00 | 7,25 | 26,07 |
| 10 | Aleatorio | No | 40 | 27,88 | 0 | 0 |
| 10 | Aleatorio | Sí | 40 | 27,60 | 67,62 | 225,00 |
| 10 | Planificador | No | 40 | 12,45 | 0 | 0 |
| 10 | Planificador | Sí | 40 | 12,43 | 19,82 | 84,88 |

### Diferencias por parejas de semilla (con competencia menos sin competencia)

| Configuración | Δ rondas | Competencia más rápida | Más lenta | Igual |
|---|---:|---:|---:|---:|
| 6 · Aleatorio | +0,50 | 13 | 10 | 17 |
| 6 · Planificador | 0,00 | 11 | 9 | 20 |
| 10 · Aleatorio | -0,275 | 20 | 19 | 1 |
| 10 · Planificador | -0,025 | 14 | 12 | 14 |

**Interpretación:** en estos escenarios, la competencia agrega interacción abundante pero **apenas altera las rondas hasta Casamiento**. No se midió la duración física real de cada duelo o subasta: las 67,62 disputas promedio por partida con 10 jugadores aleatorios pueden tener un costo importante en tiempo de mesa que esta simulación no refleja. La tasa de Casamiento de **320/320** indica que la economía sintética es demasiado generosa para extrapolar balance final.

El planificador realiza menos duelos que el aleatorio; esto tampoco establece calidad estratégica sin condiciones de economía más exigentes y objetivos adversariales bien calibrados.

## Calidad y reproducción

Suite real ejecutada en Python: **113/113 pruebas** superadas, incluyendo la línea de regresión previa. Se completaron las 320 partidas; los generadores de eventos y las cuentas verifican conservación de recursos y cartas en cada partida.

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -q
python -m laboratorio.experimento_competencia_v2 --semillas 40 --rondas 80 --mano 3 --out docs/datos_fase7
```

### Pendientes antes de evaluar balance definitivo

- Integrar cartas de Situación sociales reales y calibradas por rol; definir el orden de oferta y efectos para cada carta.
- Evaluar cartas que afecten reservas y causen rupturas, además de las negociaciones legales y la opción de reemplazo de pareja.
- Definir el punto de retorno juvenil al perder hito, la composición del mazo adulto y montos de casilleros.
- Mejorar la estrategia del bot: valor de ganancia probable por duelo, relación costo-beneficio de pujas, planificación compartida de manos de pareja, juego adversarial contra líder.
- Sustituir la economía sintética generosa por escenarios de sensibilidad (montos menores, situaciones con pérdidas, subastas menos frecuentes), siempre etiquetados como experimentos.
- Añadir duración estimada **humana** por duelo/subasta (no solo rondas) para medir ritmo real de 6 y 10 participantes.
- Verificar la ejecución de GitHub Actions: la ejecución local no implica que CI haya concluido satisfactoriamente.