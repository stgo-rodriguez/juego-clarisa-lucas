# Fase 6 — Sensibilidad e incertidumbre (v1.0)

## Alcance y decisión de diseño

Se ejecutan grillas económicas bidimensionales contra una referencia v1.3 congelada. **No se modifican reglas, bots, costos, cartas, probabilidades de dados ni el motor existente.** Las simulaciones de cada celda usan *exactamente las mismas semillas* y la misma política de bots que la base; una celda idéntica a la base reutiliza sus resultados y evita trabajo redundante.

## Controles y límites

- Dos ejes diferentes seleccionados entre producción de Perfiles, ganancias de cartas, pérdidas de cartas, ingresos de Infancia, ingresos de Juventud e ingresos de Adultez.
- Escalas enteras del 50% al 150% para las primeras cuatro; 0/100% para Juventud y Adultez.
- Hasta 5 valores por eje (máximo 25 escenarios). La interfaz ofrece 20/50/100 partidas por celda, mesas de 6 o 10 jugadores, política de bots, semilla inicial y horizonte de rondas.
- Presupuesto máximo conservador de 3.000 partidas por grilla, incluyendo una base. El presupuesto se valida **antes de ejecutar**. Una barra de progreso informa celdas completadas; el botón «Stop» de Streamlit interrumpe una ejecución larga. La memoria retiene únicamente resultados **agregados** por celda, no miles de eventos del motor.
- La ejecución usa la caché por configuración y huella del motor existente en Streamlit. Los resultados se pueden exportar a ZIP o guardar localmente en `.laboratorio/sensibilidad/` (excluido del repositorio).

## Métricas e interpretación

Cada celda contiene: n, finalizadas/censuradas para ambos escenarios, deltas de rondas observadas, diferencia de finalización en puntos porcentuales, media apareada solo entre pares que finalizaron, mediana y P90 calculados **solo con las partidas finalizadas**, e intervalos de confianza al 95 %.

### Medida principal: rondas observadas restringidas al horizonte

Para cada semilla se calcula `rondas_observadas_variante - rondas_observadas_base`; si alguna partida se censura, el dato observado está truncado al límite de rondas. El promedio de esas diferencias **NO representa** la diferencia de duración final de las partidas censuradas. Nunca se asigna un número inventado de rondas al casamiento no observado. Las tasas de finalización se informan aparte.

Cuando ambos escenarios terminan en una semilla, su diferencia contribuye también al estimador de *pares concluidos*, que puede tener sesgo de selección si hubo censura. Los cuantiles no incorporan partidas censuradas: no se muestran como cuantiles de supervivencia.

### Incertidumbre estadística

Se usa *bootstrap percentil apareado* con 500 remuestreos por celda: en cada remuestreo se seleccionan **parejas de la misma semilla**, no filas independientes de base y variante. Los generadores de bootstrap se inicializan con una semilla derivada por SHA-256 de configuración y coordenadas; son independientes de los RNG de dados, cartas y bots. Se generan intervalos para:

- Diferencia media de rondas observadas, sobre todos los pares.
- Diferencia de porcentaje de finalización, sobre todos los pares.
- Diferencia media de rondas entre pares concluidos, con advertencia de selección.

Para menos de cinco pares se omite el IC. Los IC son **exploratorios y no están corregidos por comparaciones múltiples**; 25 celdas no equivalen a 25 pruebas confirmatorias independientes. La política de bots condiciona todas las conclusiones.

## Trazabilidad y persistencia

`laboratorio/sensibilidad.py` implementa validación, grilla, simulación y estadística. `laboratorio/graficos_sensibilidad.py` construye el mapa de calor y tabla; `laboratorio/panel_sensibilidad.py` implementa el panel; `laboratorio/archivo_sensibilidad.py` exporta/importa el ZIP verificable.

Cada ZIP contiene `grilla.json`, `resultados.json`, `resultados.csv` y `manifiesto.json` con SHA-256. Las métricas se guardan *sin filas por partida* para limitar tamaño y consumo; el archivo permite **reabrir, visualizar y analizar la grilla sin simular**, pero no reconstruir una partida de una celda sin volver a ejecutar su escenario. Los hashes verifican integridad, no identidad del emisor ni autenticidad de procedencia. Se validan miembros, tamaños, coordenadas, contadores y firma del motor; si una matriz importada proviene de otra versión, la interfaz la muestra con advertencia y no la mezcla silenciosamente.

La grilla de demostración 3×3 (ganancias 90/100/110%, pérdidas 90/100/110%, 100 partidas de seis jugadores, semilla 131028) se guardó en `docs/DIAGNOSTICO_SENSIBILIDAD_FASE6.json` y como ZIP independiente. Es una verificación funcional; sus diferencias no se recomiendan como reglas definitivas por incertidumbre y multiplicidad.

## Reproducir

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
python -m laboratorio.verificar_baseline --full
python -m streamlit run laboratorio/app.py
```

En Streamlit, abrí «8. Sensibilidad e incertidumbre», elegí dos parámetros y ejecutá la matriz. También podés recuperar ZIPs guardados sin simular. La carpeta `.laboratorio/` está ignorada por Git; no sube resultados privados ni incrementa el tamaño del repositorio.

## Criterios de aceptación

- [x] La combinación base (100% en ganancias y pérdidas, resto original) tiene diferencia exactamente cero.
- [x] Todas las celdas comparten semillas, horizonte, bots y tamaño de mesa.
- [x] Bootstrap independiente del RNG del juego; IC deterministas por configuración.
- [x] Límites de trabajo antes de ejecutar; 25 celdas como máximo.
- [x] Censura y conclusión correctamente diferenciadas.
- [x] Exportar/importar ZIP verificado sin ejecutar el motor; guardar localmente.
- [x] Regresión de 1.000 partidas de seis y 1.000 de diez: CSV binariamente idénticos.
- [ ] Pruebas de interfaz Streamlit y regresión en GitHub Actions (pendiente al escribir este documento; revisar ejecución de CI antes de declarar Fase 6 completada).
