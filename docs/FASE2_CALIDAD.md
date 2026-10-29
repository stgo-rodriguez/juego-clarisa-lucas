# Laboratorio de Balance de Clarisa & Lucas — Fase 2

**Fecha:** 28/10/2026 (línea base de especificación).  
**Ámbito:** validación técnica del motor de simulación y del adaptador económico.  
**Rama:** `feature/laboratorio-balance`.

## Resultado de aceptación

- **62 pruebas automatizadas superadas**: 40 preexistentes y 22 nuevas en `tests/test_invariantes_fase2.py` (incluye una prueba con verificaciones tras cada turno).
- **2.000/2.000 partidas reproducidas** mediante `python -m laboratorio.verificar_baseline --full`.
- CSV idénticos byte a byte a los originales: para 6 jugadores `820168f1c8006ec2f143e44098cca0b6cac67a55a28ecc63423d2747451c5059`; para 10 jugadores `4442427c133e590be062cfdde61163afcaac719bbc27e3dc7aad95f673ee00f8`.
- **200 partidas de extremos** (25 por escenario, 4 configuraciones, 6 y 10 jugadores): 200 completadas, sin censuras y sin errores de contabilidad/invariantes. Detalle en `docs/DIAGNOSTICO_EXTREMOS_FASE2.json`.
- **Sin cambios en las reglas ni en las políticas de bots**. Se mantuvo intacto el código congelado `simulador/motor_v13_base.py` (`SHA-256 9ea6c0b19c8ff7f76e07bf13ab8831b5d48e373a57c7e3fb2ea3d1d349f8ef32`).

## Qué se probó adicionalmente

1. Esquema y límites válidos de parámetros, semillas, escenarios y bots.
2. Redondeo estocástico en fichas enteras (reproducibilidad, acotación, esperanza y consumo nulo de RNG al 100 %).
3. Independencia de dados, mazos y bots respecto del RNG económico.
4. Inmutabilidad de las cartas fuente frente al escalado de efectos.
5. Activación independiente de ingresos de Juventud y Adultez.
6. Separación de fuentes de ingresos y costos; contabilidad de producción y consumo.
7. Conservación de recursos y detección deliberada de corrupción del libro mayor.
8. Censura correcta al agotar el horizonte sin victoria.
9. Correspondencia de eventos de producción con los contadores económicos.
10. Integridad de saldos y estados tras cada turno en partidas de muestra.
11. Comportamiento y finalización en extremos de producción, cartas e ingresos automáticos.
12. Trazabilidad de CSV, configuración y hashes en el manifiesto de cada corrida.

## Advertencia metodológica

La prueba de 200 partidas de extremos es una **verificación técnica**, no un estudio de balance. Cada combinación tiene 25 observaciones y se usaron semillas iniciales diferentes: no permite atribuir diferencias en medianas exclusivamente al parámetro cambiado. El estudio de sensibilidad con semillas apareadas, estimaciones de incertidumbre y muestras suficientes pertenece a fases posteriores.

## Cambios en integración continua

`.github/workflows/laboratorio-tests.yml` agrega la reproducción íntegra de 2.000 partidas después de la suite unitaria. El resultado local está verificado; el estado de ejecución remota de GitHub Actions debe comprobarse por separado.

## Limitaciones pendientes

- La política de bots continúa físicamente integrada al motor v1.3 congelado: extraerla sin una regresión propia podría cambiar la línea base.
- La partición I01–I12 Clarisa e I13–I24 Lucas permanece como supuesto del simulador; no se redefinió el reglamento.
- Los resultados de los bots no equivalen a partidas humanas observadas.
- La Fase 3 construirá la interfaz Streamlit **solo** sobre el adaptador y los escenarios ya validados, sin editar `main` ni modificar los parámetros oficiales en silencio.

## Ejecutar localmente

Desde la raíz del repositorio, con Python 3.11 o posterior:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m laboratorio.verificar_baseline --full
python -m laboratorio.ejecucion --escenario escenarios/experimento_10pct_menos.json --out resultados/experimento_10pct
```

Los resultados específicos de los extremos se consignan en el JSON versionado; son descriptivos y no modifican la especificación v1.3.
