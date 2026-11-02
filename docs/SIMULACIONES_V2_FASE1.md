# Simulaciones v2.x — Fase 1: movimiento aislado

**Fuente normativa:** \`Clarisa_y_Lucas_Especificacion_Integral_v2.0_Consolidada.docx\`, edición 1/11/2026 (secciones 5, 7, 11–13 y anexo).  
**Rama:** \`feature/simulaciones-v2-movimiento\`.  
**Naturaleza:** implementación geométrica y pruebas, no simulación integral de partidas.

## Archivos nuevos

- \`simulador/movimiento_v2.py\`: motor puro de recorridos, rebotes, salidas, cartas A/B y manos individuales.
- \`tests/test_movimiento_v2.py\`: pruebas de invariantes y casos límite.
- \`laboratorio/analisis_movimiento_v2.py\`: enumerador de trayectorias, CSV y resumen JSON.

El motor v1.3, el adaptador económico, la interfaz Streamlit y la web pública no fueron modificados.

## Cobertura normativa

1. **Infancia y Juventud:** circuito de seis posiciones, desplazamiento paso a paso, conteo de cruce 6→1 y posibilidad de interrumpir un recorrido si la lógica de reglas autoriza una bifurcación.
2. **Juventud:** generador de 30 pares ordenados A/B con A ≠ B, con alternativa de 36 pares y mezcla aleatoria antes de repartir. Una carta individual diferente por extracción; la asociación con la Situación compartida se implementará en Fase 2.
3. **Adultez:** cuadrícula confirmada de 25 posiciones (Casa 3,3; Cobrar perfil 5,3; tres conexiones superiores).
4. **Geometría:** ocho direcciones internas posibles, primer paso siempre válido, rebote sin gasto, reflexión simultánea de ambas componentes en esquinas, longitud exacta, activación solo del destino y posibilidad de terminar en origen.
5. **Casamiento:** salida opcional desde (1,2), (1,3), (1,4), un paso consumido y descarte del resto. El motor recibe \`marriage_eligible=True\` **únicamente si** el motor integral ya verificó requisitos.
6. **Manos:** uso de una carta del jugador activo, A o B; el acompañante conserva íntegra su mano; nuevo lote únicamente al agotarse la mano anterior. Tamaño 3/4 como parámetro experimental.
7. **Mazos:** ningún reciclado silencioso. El motor deja su oportunidad/criterio pendiente; el descarte puede reciclarse mediante llamada explícita.

## Resultado técnico local

- **17 pruebas automatizadas: 17 superadas**.
- **864 trayectorias internas exhaustivas:** 25 orígenes × 6 distancias × (8/5/3 direcciones válidas por tipo de posición).
- Desde (5,3) existen **30** combinaciones dirección-distancia y **15** destinos distintos.
- Solo **2** de las 30 terminan en Casa: (distancia 2, norte) y (distancia 6, norte).
- Dos opciones terminan en Cobrar perfil. El cobro inicial al colocarse gratis desde Dublín corresponde a Fase 2, no a una ruta de la cuadrícula.
- Este conteo no implica que todas las distancias sean equiprobables: composición del mazo adulto aún sin aprobar.

## Reproducción

Desde la raíz del repositorio:

\`\`\`bash
python -m unittest discover -s tests -p 'test_movimiento_v2.py' -v
python -m laboratorio.analisis_movimiento_v2 --out resultados/movimiento_v2
\`\`\`

Se generan \`transiciones_adultez_v2.csv\` (864 filas) y \`resumen_geometria_v2.json\`.

## Deliberadamente fuera de esta fase

- Situaciones, economía y disponibilidad de recursos; evento de cobro al ingreso adulto.
- Reglas de UTN, proyecto, Casa, perfil, cambio de personaje y adjudicación, aún en el motor histórico.
- Momento del reparto/cambio de etapa dentro de ronda; gestión de regreso a Juventud.
- Composición/tamaño del mazo adulto y política de reciclado: por decidir.
- Inteligencia de bots, planificación de pareja y simulaciones Monte Carlo.
- Recurso Tiempo, muros, drop-off y alteraciones del tablero: no integran la base v2.0.

## Próximo paso recomendado

Implementar Fase 2 con un orquestador de turno y ronda por etapa que use este módulo, añada los **seis mazos de Situación** y mantenga explícitas las decisiones pendientes. A partir de allí, introducir un bot geométrico legal y comparar manos de 3 vs 4 bajo una composición de mazo experimental declarada, antes de incorporar economía completa.
