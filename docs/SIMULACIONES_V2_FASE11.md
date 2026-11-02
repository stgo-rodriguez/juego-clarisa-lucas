# Clarisa & Lucas — Fase 11 · Calibración cuantitativa de cartas documentadas

**Estado:** experimento exploratorio; **NO constituye una aprobación de las cartas ni una actualización del reglamento v2.0**.  
**Reglamento rector:** Especificación Integral v2.0 Consolidada, 1/11/2026.  
**Base documentada:** 78 cartas históricas v0.1 + 30 propuestas adultas multiverso v0.2. En el ensayo físico se usan 126 cartas: dos mazos de 24 cartas históricas de Infancia, dos de 24 cartas históricas de Juventud y dos mazos adultos de 15 cartas originales espejo. Las 30 cartas históricas adultas siguen preservadas.  
**Rama de investigación:** `feature/simulaciones-v2-movimiento`.

## 1. Hipótesis y control de cambios

Aislar qué componente de los efectos de Situación determina la duración y las dificultades: los **premios I/J**, los **premios de Adultez** y las **pérdidas explícitas**. No se tocan posiciones, manos, decisiones A/B del Movimiento, costos del juego, precios, requisitos, Perfil productivo, montos adultos por casillero, dados, rutas ni las reglas de subasta de una ronda.

| Factor | Valor de referencia | Valor alternativo | Alcance del ajuste |
|---|---:|---:|---|
| Premio positivo Infancia/Juventud | 100% | 60% | Solo recursos **recibidos** en las 48 cartas históricas originales duplicadas por personaje |
| Premio positivo Adultez | 100% | 70% | Premios individuales, dirigidos, cooperativos y beneficio total apropiable de las 30 propuestas adultas |
| Pérdidas explícitas | 100% | 150% | Pérdidas de **recursos libres**, tanto del activo como de otro personaje, según la carta; no se alteran costos voluntarios |

Los valores se convierten a fichas enteras con `int(n × multiplicador + 0.5)`. Esto implica, por ejemplo, que un premio de 1 con factor 0,7 **sigue siendo 1** y una pérdida de 1 con factor 1,5 **pasa a 2**. La escala porcentual es **nominal**, no una disminución porcentual exacta de todas las unidades concedidas. No se alteran los JSON originales: el módulo `BalanceVariant` transforma los efectos al ejecutarlos, con el factor asociado a la etapa.

En subastas se modifica el beneficio total y luego se reparte proporcionalmente entre parte apropiable y remanente con conservación de unidades; permanecen intactos la oportunidad única de puja, las monedas ofertables y el pago exclusivo del adjudicatario al activo. **No se aplica una equivalencia automática** a ofertas heterogéneas.

## 2. Diseño del experimento

- **8 variantes:** factorial completo 2³. Un identificador `cal_abc` significa `a=1` reducción de premio I/J, `b=1` reducción de premio adulto y `c=1` aumento de pérdida.
- **20 semillas** en cada combinación de mesa de 6/10 jugadores, bot aleatorio/planificador y competencia desactivada/activada; las variantes de cada bloque usan el mismo número de semilla y la misma configuración externa.
- **1.280 partidas**; máximo 100 rondas. Se reporta tanto la fracción con Casamiento como las rondas **truncadas** para no confundir una media censurada con la duración de las partidas ganadoras.
- La económica por casillero adulto se mantiene en **2 unidades**, que sigue siendo un supuesto experimental; mazos de Movimiento adulto y política de Dublín `next_turn` siguen siendo experimentales.
- Cada partida verifica invariantes de contabilidad, conservación de cartas y legalidad económica. Las políticas del bot no equivalen a juego humano.

### Resultado global

**1.273 matrimonios de 1.280 partidas; 7 truncamientos.** Los siete ocurrieron exclusivamente en partidas **de seis jugadores, bot aleatorio y competencia activada** con pérdidas aumentadas. Los otros siete grupos por tamaño/estrategia/competencia no tuvieron truncamientos en estas veinte semillas.

| Variante | Premio I/J | Premio adulto | Pérdidas | Matrimonios / 160 | Rondas medias truncadas, todas las configuraciones |
|---|---:|---:|---:|---:|---:|
| `cal_000` | 100% | 100% | 100% | 160 | 25,16 |
| `cal_001` | 100% | 100% | 150% | 157 | 28,91 |
| `cal_010` | 100% | 70% | 100% | 160 | 26,15 |
| `cal_011` | 100% | 70% | 150% | 158 | 30,41 |
| `cal_100` | 60% | 100% | 100% | 160 | 26,66 |
| `cal_101` | 60% | 100% | 150% | 159 | 29,44 |
| `cal_110` | 60% | 70% | 100% | 160 | 27,82 |
| `cal_111` | 60% | 70% | 150% | 159 | 31,41 |

**Cuidado:** la media global mezcla agentes aleatorios y planificadores, y mesas de 6 y 10. Su utilidad es exploratoria; para decidir parámetros observar la desagregación y los contrastes por semilla.

### Planificador con competencia activada (20 semillas por celda)

| Variante | 6 jugadores: rondas | 10 jugadores: rondas | 6 jugadores: % turnos sin avance duradero | 10 jugadores: % turnos sin avance duradero |
|---|---:|---:|---:|---:|
| Base `cal_000` | 15,55 | 14,65 | 64,27% | 65,38% |
| Reducción I/J `cal_100` | 16,90 | 16,10 | 67,36% | 67,15% |
| Reducción adulto `cal_010` | 15,55 | 15,25 | 64,31% | 66,04% |
| Pérdidas elevadas `cal_001` | 17,65 | 16,00 | 67,58% | 67,92% |
| Ambas reducciones `cal_110` | 17,05 | 16,95 | 67,70% | 68,11% |
| Todos los cambios `cal_111` | 18,60 | 17,55 | 69,07% | 69,77% |

Los **turnos sin avance duradero** son aquellos que no incrementan la puntuación de hitos, comprobantes, pareja o Casa al final del turno. Una acumulación útil de recursos puede contar como un turno sin avance duradero; **no son turnos necesariamente inútiles**.

### Efectos marginales apareados por semilla — planificador competitivo

Se comparan dos tratamientos de un solo factor manteniendo constantes los otros dos, promediando sobre sus cuatro combinaciones. Para las bandas exploratorias se calcula primero la media del contraste **por semilla** y luego el error estándar sobre las **20 semillas independientes**; las cuatro comparaciones internas de una misma semilla no se consideran 80 unidades independientes.

| Factor alterado | Mesa de 6 | Mesa de 10 |
|---|---:|---:|
| Menores premios de I/J | **+0,85 rondas** (banda normal aprox. 0,27 a 1,43) | **+1,29** (0,36 a 2,22) |
| Menores premios adultos | **+0,38** (0,15 a 0,60) | **+0,64** (0,37 a 0,91) |
| Pérdidas más altas | **+1,75** (1,20 a 2,30) | **+0,94** (0,49 a 1,38) |

Las bandas normales con 20 semillas son únicamente una referencia exploratoria. La asignación de semillas es controlada pero las secuencias futuras divergen al cambiar las decisiones inducidas por cada efecto; los resultados **no son observaciones humanas ni predicciones de comercialización**.

## 3. Lectura de diseño

**Candidata para estudiar, no para aprobar: `cal_110`**, reducción de premios I/J y adultos sin elevar pérdidas. No produjo truncamientos en las 160 partidas de la muestra y alargó moderadamente el juego. No probar aún que sea superior en diversión o dinamismo; sus turnos sin hito aumentan.

**No recomendar por ahora aumentar pérdidas +50%.** Amplifica especialmente las pérdidas pequeñas debido a la indivisibilidad de las fichas, aumenta el tiempo sin nuevo hito y produjo los siete únicos truncamientos en un subgrupo. Una frecuencia distinta de duelos o una carta de pérdida de reservas puede cambiar la conclusión.

**Reducir premios adultos aporta relativamente poco en el planificador**, dado que a menudo la pareja ya tiene recursos productivos y acceso a Perfil, mientras que las cartas adultas contienen elecciones, cooperación y subastas que redistribuyen oportunidades. Tampoco se midieron minutos reales de negociación: no equivale a baja carga social.

## 4. Pendientes explícitos

1. Elegir o rediseñar las **48 cartas I/J por personaje**; la duplicación histórica por rol es experimental. Las 30 adultas multiverso son propuestas, no aprobadas.
2. Calibrar la **frecuencia de intervenciones** y medir duración real de las ofertas en una mesa, especialmente con diez jugadores.
3. Medir la interacción de cartas con Casa y Perfil bajo economías más exigentes, además de probar la ruptura adulta una vez definida la posición y continuidad de turno tras retroceso.
4. Definir los recursos adultos por casillero, tamaño definitivo de mano adulta, reciclado y Dublín. Esta fase no decide ninguno.
5. Usar alternativas que eviten redondear toda pérdida de 1 a 2 antes de descartar o adoptar una regla de pérdidas más severa.

## 5. Reproducción y archivos

Ejecutar desde raíz del repositorio (Python 3.11/3.13):

```bash
python -m unittest discover -s tests -p 'test_*v2.py' -v
python -m laboratorio.calibracion_cartas_v2 --semillas 20 --rondas 100 --out resultados/fase11
```

Para ejecutar por bloques (menor memoria y mejor diagnóstico):

```bash
python -m laboratorio.calibracion_cartas_v2 --semillas 20 --rondas 100 --mesa 6 --agente planificador --competencia si --out resultados/fase11_bloque
```

El consolidador `laboratorio/consolidar_calibracion_v2.py` acepta ocho CSV de bloques y comprueba que están todos los bloques completos, sin duplicación de semilla/mesa/bot/competencia/variante. Se acompaña un resultado consolidado con archivos `partidas_calibracion_v2.csv`, `resumen_por_variante_v2.csv`, `efectos_apareados_v2.csv` y `resumen_calibracion_v2.json`.

**Pruebas:** 159/159 en ejecución local. **Estado GitHub Actions:** no declarar ejecución remota exitosa sin reporte verificable. El simulador histórico v1.3 no se modifica.