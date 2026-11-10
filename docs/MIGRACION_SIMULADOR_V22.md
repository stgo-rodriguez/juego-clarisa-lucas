# Preparación de la adaptación a Clarisa & Lucas v2.2

**Estado: bloqueada por ausencia de especificación v2.2 verificable. No constituye una implementación de v2.2.**

## Fuentes verificadas al 09/11/2026

- Especificación autónoma más reciente encontrada en Drive: `Clarisa_y_Lucas_Especificacion_Integral_v2_1_Consolidada_Autonoma_2026-11-08.docx`, encabezada explícitamente **VERSIÓN 2.1**, modificada el 09/11/2026.
- Código de referencia: `fix/simlog-v21-especificacion-20261108`, commit `29c7ec51fdf4144885e3ad3bf9ad995901445810`.
- No se encontró una especificación identificada como v2.2 en los archivos del proyecto, Drive o GitHub.

## Comportamiento del repositorio preparado

- Se crea `feature/simulador-v22` a partir del motor v2.1 auditado, **sin alterar** reglas ni resultados históricos.
- `simulador/versiones.py` declara v2.1 como versión disponible y v2.2 como pendiente de especificación.
- `laboratorio/simular_versionado.py` permite ejecutar explícitamente v2.1; solicitar v2.2 genera un error antes de crear archivos. No hay ejecución silenciosa del motor anterior con el nombre v2.2.
- Las pruebas de `tests/test_versiones_v22.py` verifican aislamiento de versiones, mensaje de bloqueo y ausencia de resultados engañosos.

## Lista de trabajo al disponer de la especificación v2.2

| Área | Versión 2.1 de referencia | Delta v2.2 |
|---|---|---|
| Situaciones | Una carta por etapa, rol y ronda; A/B individual | Sin fuente aprobada |
| Infancia | D6, cobro por destino y luego A/B; 6 casilleros | Sin fuente aprobada |
| UTN | Bifurcación consumiendo un paso; examen posterior | Sin fuente aprobada |
| Juventud | Situación A/B vinculada a Movimiento A/B | Sin fuente aprobada |
| Dublín | Salida con un paso; cobro de Perfil al entrar a Adultez | Sin fuente aprobada |
| Adultez | Tablero 5×5, rebotes, mano de Movimiento, Casa/Casamiento | Sin fuente aprobada |
| Parejas / duelos / reservas | Motor de referencia experimental con casos límite pendientes | Sin fuente aprobada |
| Afinidad | Zonas A–Neutro–B | Sin fuente aprobada |
| Economía | Premios de cartas y parámetros experimentales v2.1 | Sin fuente aprobada |
| SIMLOG | `turnos.csv`, `eventos.csv`, `situaciones_por_ronda.csv`, manifest | Sin fuente aprobada |

## Criterios de salida para una v2.2 válida

1. Identificar una fuente autoritativa y la lista exacta de cambios desde v2.1.
2. Crear módulos propios de motor, economía y SIMLOG v2.2 **solo si las reglas difieren**. Compartir código estable sin reetiquetar resultados.
3. Codificar pruebas que cubran cada cambio explícito, además de las regresiones v2.1.
4. Ejecutar muestras de 6 (3+3) y 10 (5+5) jugadores con semillas registradas.
5. Verificar eventos, movimientos, recursos, hitos, integridad de archivos, duraciones y decisiones A/B.
6. Identificar cada corrida con `ruleset: v2.2` únicamente tras activar un motor validado con fuente aprobada; preservar datos v2.1.
7. No resolver mecánicas pendientes por inferencia, ni tomar objetivos de balance como premios automáticos.

No se incluyen valores, efectos, reglas ni cambios inventados para v2.2.
