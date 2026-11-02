# Simulaciones v2.x — Fase 2 · Orquestador de rondas

**Reglamento rector:** Especificación Integral v2.0 Consolidada, edición 1/11/2026.
**Rama de trabajo:** `feature/simulaciones-v2-movimiento`.
**Alcance:** motor de secuencia y cartas de movimiento, no simulación integral ni economía calibrada.

## Archivos

- `simulador/movimiento_v2.py` — Fase 1: geometría y manos (sin modificaciones).
- `simulador/turnos_v2.py` — Fase 2: ronda global, seis mazos de Situación, movimiento y acciones externas mediante `RuleHooks`.
- `tests/test_turnos_v2.py` — pruebas de orden, reparto, A/B, parejas y errores explícitos.
- `.github/workflows/simulaciones-v2.yml` — pruebas automáticas de ambas fases, Python 3.11 y 3.13.

## Contrato de Fase 2

1. Un turno por jugador y ronda, en **orden global preexistente**; ninguna ronda se inicia antes de terminar la anterior.
2. Infancia: robo propio por turno, Situación antes de D6, movimiento en circuito.
3. Juventud: una Situación compartida por personaje y ronda; **una carta de Movimiento diferente para cada joven**; selección A/B durante el turno propio, vinculada simultáneamente a Situación y distancia.
4. Adultez: una Situación compartida por personaje y ronda, **independiente** de la elección A/B del Movimiento. Se usa exactamente una carta de la mano del activo.
5. Parejas: se mueven ambos a la misma posición, pero solo el activo resuelve Situación y gasta su carta. Los cobros automáticos notifican por integrante.
6. Cobro de Perfil juvenil: notificación por cada integrante al cruzar 6→1. Cobro en casillero Perfil adulto: notificación para ambos cuando el **destino** es Perfil.
7. Los mazos conservan identificadores únicos, cartas robadas, descartadas y retenidas. El reciclado es **opcional y explícitamente experimental**.
8. Los casilleros de llegada notifican a un adaptador de reglas. La inversión, compra de Casa, adjudicación y economía no se ejecutan sin este adaptador.
9. La salida a Casamiento exige una pareja válida y además una verificación externa de **todos los requisitos económicos**. La Fase 2 por sí sola no certifica victorias.

## Pendientes que bloquean una simulación integral

- Los **seis nuevos mazos reales** aún necesitan efectos calibrados y datos versionados.
- Falta definir transición a mitad de ronda (UTN, Dublín, cambio de etapa por Situación), incluido el reparto de cartas y la Situación de un recién llegado. Se lanza `PendingRuleError` en esos casos: **no se asume una regla silenciosa**.
- Falta integrar la colocación gratuita desde Dublín en (5,3) con el cobro inicial para ambos.
- No existe una composición definitiva del mazo adulto; para tests se proporcionan cartas de ejemplo a través de `CardPool`, sin declararlas oficiales.
- Falta unir el orquestador con el adaptador económico, proyectos, disputas, reservas, compras y negociaciones.
- El modelo `RuleHooks` es intencionalmente un punto de integración. No aplica todavía recursos, Situaciones sociales ni políticas de bots.

## Calidad y reproducibilidad

Las pruebas nuevas cubren secuencia Situación→Movimiento, reparto sin reemplazo, orden global, pareja, uso individual de mano, A/B conjunto en Juventud y políticas faltantes. Los ensayos locales de desarrollo del orquestador superaron 17 pruebas usando una **implementación de apoyo geométrica**, no el archivo completo real. Los tests versionados ejecutan con el archivo geométrico real en el workflow de GitHub; su éxito debe comprobarse en CI antes de calificar la integración como verificada.

Para ejecutar desde la raíz del repositorio:

```bash
python -m unittest discover -s tests -p 'test_movimiento_v2.py' -v
python -m unittest discover -s tests -p 'test_turnos_v2.py' -v
```

## Fase 3 recomendada

1. Resolver explícitamente las transiciones UTN/Dublín/reingreso y la política de reparto en mitad de ronda.
2. Implementar los efectos de los seis mazos versionados y la economía por destino, con invariantes de recursos.
3. Integrar los hitos, Casa y Casamiento con el motor v2 sin tocar el motor histórico.
4. Incorporar agentes aleatorio legal, táctico y de planificación de manos, antes de comparar 6 vs. 10 jugadores.

**No confundir esta fase con 2.000 partidas Monte Carlo v2.0:** todavía no hay agentes ni mazos definitivos.


## Smoke reproducible de turno y reparto (sin economía)

Se agregó `laboratorio/smoke_turnos_v2.py` con cartas neutrales y una composición adulta **sintética y expresamente experimental**. La prueba local del orquestador (con módulo geométrico de apoyo) produjo, en dos rondas:

| Configuración | Turnos | Situaciones resueltas | Revelaciones compartidas | Repartos juveniles | Nuevas manos adultas |
|---|---:|---:|---:|---:|---:|
| Juventud, 6 jugadores | 12 | 12 | 4 | 12 | 0 |
| Juventud, 10 jugadores | 20 | 20 | 4 | 20 | 0 |
| Adultez, 6 jugadores | 12 | 12 | 4 | 0 | 6 |
| Adultez, 10 jugadores | 20 | 20 | 4 | 0 | 10 |

Estos conteos reflejan el **ciclo de turnos y cartas**, no victorias, duración esperada ni balance. Reproducción:

```bash
python -m laboratorio.smoke_turnos_v2 --rondas 2
```

Se incluyó su ejecución en el workflow específico v2. La comprobación remota de GitHub Actions permanece pendiente.
