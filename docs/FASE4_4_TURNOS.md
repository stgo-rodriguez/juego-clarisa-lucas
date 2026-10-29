# Fase 4.4 — Actividad de turnos y oportunidades observadas

## Alcance

**Entregable:** panel **«7. Actividad de turnos y oportunidades detectadas»** de Streamlit. Reejecuta únicamente la partida seleccionada con la misma semilla, política de bot, economía y número de jugadores. Antes de mostrar el resultado compara `Game.summary()` con la fila original, exige cero errores del motor y concilia los eventos de decisiones con sus contadores.

**No se modifica** `simulador/motor_v13_base.py`, `simulador/motor.py`, el mazo, la política de bots, las fuentes de azar ni el sistema de hitos. El observador se instala por subclase y llama a `super()` en cada método. Se compara también el estado final de los cuatro RNG (dados, cartas, bots y economía), los contadores y el `eventlog`.

## Definiciones operativas (sin equivalencia automática con diversión)

1. **Turno individual:** llamada efectiva a `do_turn` de un jugador; la fase se asigna a la etapa **al comienzo del turno**. Las partidas pueden finalizar antes de completar una ronda.
2. **Decisión ejecutada del bot:** evento efectivo de carta (desenlace A/B), financiación, examen de adjudicación, cambio de perfil o personaje, duelo o retirada, negociación o conversión 2:1. Cada evento cuenta una vez. Una financiación doble en el mismo turno cuenta dos decisiones pero una sola familia disponible.
3. **Evento automático:** consecuencia del motor (producción, pagos, ayuda automática de pareja, acceso UTN, entrada Adultez, hitos concedidos, formación de pareja, Casa o casamiento). La tirada de movimiento se registra separadamente como `movimientos_dado`. **Evento automático no equivale a decisión del bot.**
4. **Familia disponible:** predicado observacional satisfecho en el instante en que el motor consulta la acción correspondiente; se cuenta **máximo una vez por turno**. Se incluyen exactamente diez familias: carta, financiar, adjudicar, formar pareja, comprar Casa, intentar casamiento, cambiar perfil, iniciar duelo, negociar comprobante y convertir en banco. Estos predicados no hacen sorteos, no mutan estado y no representan el conjunto exhaustivo de jugadas legales.
5. **Turno con decisión:** al menos un evento de la lista de decisiones. **Turno sin decisión registrada** no significa que el humano no pudiera elegir, sino que los bots no ejecutaron decisiones incluidas en esta taxonomía.
6. **Turno con ejecución/resolución de una familia:** familia con uno o más eventos del tipo correspondiente durante ese turno. Incluye consecuencias automáticas explícitamente etiquetadas (formar pareja, Casa, casamiento). Comparar esta magnitud con las familias disponibles no presupone que el bot deliberó.

### Límites de cobertura

- No se reconstruyen todas las jugadas legalmente posibles, opciones de un intercambio bilateral, propuestas rechazadas, motivaciones ni decisiones humanas.
- Las diez familias se inspeccionan cuando el motor llega a su punto de evaluación; no son diez opciones necesariamente simultáneas al inicio del turno.
- La política de bot no propone transferencias voluntarias de hitos ni intercambios bilaterales en todas las circunstancias. Esas acciones se cuentan **si ocurren**, pero no se afirma que el modelo haya enumerado sus alternativas.
- La opción de cambiar de personaje se cuenta cuando ocurre; su elegibilidad completa no está entre las diez familias instrumentadas.
- Un mismo turno puede registrar más de una decisión, y no todas requieren una tirada. No se interpretan los conteos como puntuación de calidad o de profundidad estratégica.
- Para observar la etapa, jugador y el orden de las oportunidades hay que reconstruir una partida. Los CSV del lote original **no contienen** estos campos; la interfaz no fabrica agregaciones detalladas a partir de ellos.

## Salidas

- KPIs: total de turnos, turnos con decisiones ejecutadas, turnos sin decisiones registradas, familias disponibles promedio por turno.
- Barras apiladas: turnos con/sin decisión por etapa al comienzo del turno.
- Barras agrupadas: familias disponibles en turnos versus turnos con ejecuciones o resoluciones.
- Tablas por etapa, política de bot y secuencia individual de turnos (con filtros por jugador/etapa), exportación JSON.
- Auditorías: `errores_auditoria`, `errores_motor`, `equivalencia_fila`; tablas de decisiones efectivas y oportunidades.

## Validación

- Suite automatizada local: **116 casos**, 111 superados y cinco omitidos localmente porque Streamlit no está instalado en ese intérprete. Las cinco se ejecutan en CI con Streamlit instalado.
- Regresión completa: 1.000 partidas de 6 y 1.000 de 10 jugadores con hashes SHA-256 idénticos a los archivos originales.
- Prueba adicional: **150 partidas** (25 por combinación: 6/10 jugadores × economía base/escasa/abundante), con igualdad exacta por fila, **0 errores de auditoría**, 0 eventos no clasificados y 0 errores del motor. Fuente: `docs/DIAGNOSTICO_TURNOS_FASE4_4.json`.

**No interpretar** la variación de familias de acción observadas como prueba causal de mayor diversión: sólo representa las decisiones tomadas por los bots y la cobertura explícita de este observador.
