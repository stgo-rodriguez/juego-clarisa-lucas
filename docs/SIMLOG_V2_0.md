# SIMLOG v2.0 — Trazabilidad integral de Clarisa & Lucas

**Estado:** implementado y probado en la rama `feature/simulaciones-v2-movimiento`.
**Reglamento:** los mazos actuales continúan siendo experimentales (I/J históricas v0.1 duplicadas por personaje; Adultez multiverso v0.2 NO APROBADO).
**Alcance:** observabilidad y exportación; no introduce reglas nuevas ni altera el azar, los bots o sus decisiones.

## 1. Motivación y compatibilidad histórica

Las exportaciones de 1.500 partidas antiguas (`Simulación 1500 - Nueva validación - Turnos Parte 1/2`) registraban **45 columnas útiles por turno**, incluidos `Partida`, `Ronda`, `Turno_global`, `Carta_ID`, `Situacion`, `Desenlace_elegido`, `Canje`, `Eventos`, recursos y reservas antes/después, hitos y estado de la pareja.

SIMLOG v2.0 conserva los nombres nucleares de esa estructura y añade información necesaria para la cuadrícula 5×5 y las situaciones sociales: **elección de Situación por un lado y elección A/B de Movimiento por otro**. Para evitar perder acciones que afectan a terceros, guarda instantáneas de todos los participantes antes y después de cada turno. Cada evento lleva `Secuencia` global estrictamente creciente.

Los nombres de algunos campos históricos no equivalen semánticamente a un nuevo proyecto compartido: los comprobantes/inversiones se almacenan en estructuras propias, sin disfrazarlos de reservas de la v0.33b.

## 2. Archivos que genera una partida

| Archivo | Grano y utilidad |
| --- | --- |
| `turnos.csv` | **Una fila por turno individual**. Identificación, carta y desenlace de Situación, carta A/B de Movimiento, dirección, ruta, posición, recursos del activo antes/después, reservas, hitos, referencias a eventos. |
| `eventos.csv` | **Una fila por evento** de motor, economía, Situación, duelo, subasta, competencia y activaciones de tablero. `Secuencia` refleja el orden en que cada módulo añadió realmente el evento. |
| `eventos.jsonl` | Los mismos eventos con detalle JSON íntegro, sin perder datos de ofertas, dados, retiradas o transferencias. |
| `estados_jugadores.csv` | **Dos filas por jugador y turno** (antes/después), incluso para jugadores pasivos afectados por transferencias o decisiones sociales. Incluye saldos libres, reservas, cartas en mano, Perfil, comprobantes y titularidad. |
| `estados_globales.csv` | Dos estados por turno: banco emitido/consumido, recursos invertidos, proyectos, titularidad de Casa y Casamiento. |
| `hitos.csv` | Cambios detectados por turno en parejas, etapas, posiciones, proyectos, comprobantes, Perfiles, Título, Pasaporte, Casa y Casamiento. |
| `recursos_por_ronda.csv` | Cierre de cada ronda: recuento por etapa, recursos libres por tipo y estado de propiedad/victoria. |
| `preferencias_situaciones.csv` | Frecuencia A/B **por carta de Situación**; los sucesos sin A/B, como subastas y cooperaciones, se cuentan bajo `Otras_resoluciones`. |
| `preferencias_movimientos.csv` | Frecuencia A/B de **cartas de Movimiento** por etapa y rol, separada de Situación. |
| `manifest.json` | Semilla, modelo, número de jugadores, escenario, política, balance, estado final, recuentos y SHA-256 de cada archivo exportado. |

Para varias partidas se generan `partidas.csv`, `preferencias_por_carta.csv` (agregado por carta/personaje/etapa/estrategia) e `indice_simlog.json` en la carpeta raíz.

## 3. Semántica de decisiones

- **Infancia:** `Desenlace_elegido=A/B` registra la opción de Situación; Movimiento se decide con D6 y no se inventa una opción A/B para ese dado.
- **Juventud:** `Desenlace_elegido` y `Desenlace_movimiento` coinciden por regla; se valida esa identidad en cada turno.
- **Adultez:** `Desenlace_elegido` registra A/B solo cuando la carta ofrece alternativas explícitas. `Resultado_situacion` distingue `choice_0`, `choice_target_1`, `coop_accepted`, `auction`, etc. `Desenlace_movimiento` registra **independientemente** A/B, carta, dirección, rebotes y pasos descartados.
- **UTN/Dublín:** si se está en un turno de tránsito sin Situación, la elección se deja nula, sin fabricar una carta.
- `Desenlace_texto` conserva el desenlace histórico narrativo cuando es A/B de Infancia/Juventud.
- `A_antes / A_despues` y `P_antes / P_despues` incluyen saldos libres y reservas propias de A/P; K/M contabilizan saldos libres. Las columnas `*_libre_antes` y `*_libre_despues` son explícitas. Recursos invertidos no se cuentan como recursos libres y están en `estados_globales.csv` y `estados_jugadores.csv`.

### Eventos y orden

Se observan `append()` de los seis flujos originales sin cambiar su contenido. A cada evento se le asigna un número de `Secuencia` en el instante de publicación, antes de cualquier reclasificación. Se añaden observaciones del recorrido por casillero y activaciones de Perfil/destino. Se registra el estado antes de llamar al motor y después de finalizar **todas** las acciones compatibles (`after_turn` incluido).

Al comenzar la ronda se registran aparte las revelaciones compartidas, repartos, cobros de Perfil y transiciones automáticas, con fase `round_start`, aunque esos eventos no correspondan al turno de un jugador concreto.

## 4. Ejecución y reproducibilidad

Desde la raíz del proyecto:

```bash
python -m unittest discover -s tests -p 'test_*_v2.py' -q

# Cuatro partidas: 6 y 10 jugadores, aleatorio y planificador, competencia activa
python -m laboratorio.ejecutar_simlog_v2 \
  --semillas 1 --rondas 100 --mesas 6 10 \
  --agentes aleatorio planificador --competencia si \
  --escenario original --out resultados/simlog_v2

# Variante de calibración Fase 11 y controles de competencia
python -m laboratorio.ejecutar_simlog_v2 \
  --semillas 2 --rondas 100 --mesas 6 10 \
  --agentes planificador --competencia ambas \
  --escenario cal_110 --out resultados/simlog_cal_110
```

Los directorios se nombran mediante semilla, tamaño, estrategia, competencia y variante. El `manifest.json` de cada partida y el `indice_simlog.json` de la corrida permiten trazar los archivos a su configuración.

**Instrumentación opcional:** `run_proposal(..., simlog_dir=..., simlog_run_id=...)` devuelve el mismo resumen que antes; si no se aporta directorio no se instala ningún observador ni se genera ninguna traza. Es posible repetir con la misma semilla y verificar igualdad exacta de resultados con o sin SIMLOG.

## 5. Verificaciones

Las pruebas cubren: igualdad de partidas con y sin registro, 6/10 jugadores, comparación en escenario calibrado, una fila por turno, estados de *todos* los jugadores antes/después, secuencia sin saltos, referencia de cada evento por turno, elecciones de Juventud A/B coincidentes, separación de decisiones adultas, cambios económicos de terceros, preferencias por carta obtenidas a partir de turnos, integridad de hashes y agrupación de varias partidas.

La suite completa consta de **170 pruebas locales aprobadas** (159 previas + 11 nuevas). La prueba de CI se configura por separado; no declararla exitosa sin comprobar el resultado remoto.

## 6. Diferencias y límites del modelo actual

- Los datos de Fases 1–11 guardados solo en CSV resumidos **no se reconstruyen retrospectivamente** sin volver a ejecutar las semillas.
- Las fuentes de cartas v0.1/v0.2 **no están aprobadas como mazos definitivos v2.0**; las magnitudes y perfiles productivos siguen siendo experimentales.
- El código económico vigente conserva un modelo heredado de **cuatro afinidades de Perfil**; no es la nueva propuesta de eje A–Neutro–B. SIMLOG lo etiqueta `Afinidad_heredada`, sin confundirlo con la afinidad nueva.
- La vuelta desde Adultez a Juventud por pérdida de hito tiene una coordenada juvenil pendiente. SIMLOG registra únicamente transiciones que el motor realmente permite.
- `Canje` puede quedar vacío porque el bot de esta versión no ejecuta una conversión bancaria en todos los turnos; SIMLOG no inventa un canje.
- Los eventos existentes no siempre identifican por sí mismos a todos los participantes de una acción. Los detalles completos permanecen en `Detalle_JSON`, y los estados antes/después permiten auditar el efecto sobre terceros.
- Las planillas históricas contenían 45 columnas útiles; SIMLOG v2 amplía el detalle y guarda datos complejos en hojas/archivos separados para evitar repetir grandes instantáneas globales en cada registro de turno.

## 7. Aplicación al Laboratorio de Balance

Esta estructura habilita directamente: **Cronología** (`turnos` + `hitos`), **Economía** (`estados_jugadores` + `estados_globales` + `recursos_por_ronda`), **Interacciones** (`eventos` con secuencia) y **Actividad** (`turnos`, `preferencias_situaciones`, `preferencias_movimientos`).

La conectividad de la interfaz web del Laboratorio a estos CSV queda como una tarea distinta; esta fase implementa la **producción persistente y auditable** de los datos, no modifica su interfaz actual.