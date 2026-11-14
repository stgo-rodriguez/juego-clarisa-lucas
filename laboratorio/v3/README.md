# Laboratorio de Balance v3.0 — Fase 1: matriz económica integral

**Estado:** entregable inicial de parametrización, **no** es un simulador v3.0 ni una calibración ejecutada.

**Documento rector:** [Clarisa_y_Lucas_Especificacion_Conceptual_v3_0.docx](https://docs.google.com/document/d/1AfX65pZX_XmXwsPLMwkXAqg5gL1BfzKB/edit) (14/11/2026).

## Propósito que no debe perderse

Determinar, con matemáticas, experimentación y simulaciones, **cuánto debe generar, consumir, reservar o requerir cada mecanismo** para equilibrar economía, ritmo de las etapas y caminos de victoria de Clarisa & Lucas v3.0. La optimización modifica **cantidades**; no rediseña las mecánicas. Los importes de v2.x no se importan automáticamente.

## Archivos

- `matriz_economica_v3.json`: fuente canónica del catálogo de 181 parámetros sin valores numéricos.
- `matriz_economica_v3.csv`: exportación tabular para revisar en Excel/Sheets.
- `catalogo.py`: lector, auditor de integridad, exportador CSV y calculador de emisión esperada, sujeto a frecuencias y cantidades explícitas.
- `tests/test_matriz_economica_v3.py`: pruebas de identidad, cobertura, control de omisiones y contabilidad básica del primer modelo.

Las 96 filas `SIT_*` corresponden a **plantillas** etapa × rol × opción × recurso × signo (ganancia/pérdida). No son 96 cartas distintas ni reemplazan el catálogo final de cartas. Las ocho filas `PERFIL_*` representan una plantilla por rol × recurso; en la siguiente fase se expandirán por tipo real de Perfil.

## Glosario de flujos

| Flujo | Relevancia para la contabilidad | Cuenta como creación? |
|---|---|---|
| EMISION | Aumenta el saldo libre | Sí |
| CONSUMO | Reduce recursos disponibles definitivamente | No |
| RESERVA | Pasa recursos libres a reserva, sin destruir fichas | No |
| INVERSION | Pasa recursos libres a proyecto, protegido | No |
| REQUISITO | Comprueba saldo sin mover fichas | No |
| TRANSFERENCIA | Mueve fichas entre jugadores, total global igual | No |
| CONSUMO/TRANSFERENCIA | Casa: banca o propietarios según resultado | No |
| CONVERSION | Banco: retira origen y crea destino según tasa; contabilizar ambos lados | No como creación externa neta sin compensación |
| OBJETIVO | Cuota a alcanzar para ganar, sin importe aprobado | No |
| CONTROL | Decisión reglamentaria abierta, no cuantificar aún | N/A |
| OBJETIVO_ANALITICO | Meta de tiempo o de participación, no una regla | N/A |

Cada unidad solo puede encontrarse en **un estado**: libre, reservada, invertida o consumida/transferida.

## Contrato matemático para la siguiente fase

Para jugador `i`, recurso `r` y turno `t`:

```text
Libre_fin = Libre_inicio
          + Emisiones
          + Transferencias_entrantes - Transferencias_salientes
          - Consumos - Perdidas_efectivas
          - Nuevas_reservas + Reservas_liberadas
          - Nuevas_inversiones + Reintegros_legales
          + Conversión_recibida - Conversión_entregada

Reserva_fin = Reserva_inicio + Nuevas_reservas - Reservas_liberadas - Perdidas_de_reserva
Inversión_fin = Inversión_inicio + Nuevas_inversiones - Inversiones_liquidadas
```

No sumar `REQUISITO` a `CONSUMO`; no contar `TRANSFERENCIA` como producción de la mesa.

Para fuente `m`, etapa `s`, recurso `r`:

```text
Emisión_esperada(s,m,r) = frecuencia_observada(s,m) * premio_medio(s,m,r)
Emisión_bruta(s,r)      = sum_m Emisión_esperada(s,m,r)
Participación(s,r)      = Emisión_bruta(s,r) / sum_k Emisión_bruta(s,k)
```

Las frecuencias se estimarán con SIMLOG-3.0; las cantidades se optimizan y **permanecen vacías** hasta que existan escenarios explícitos. La función `emisiones_esperadas` exige cantidades conocidas para cualquier evento con frecuencia positiva.

### Evaluación de objetivos

- **UTN/Dublín**: son umbrales, no pagos (salvo nueva regla expresa).
- **Título/Pasaporte**: subhitos invertidos y adjudicación individual, con variabilidad y disputas.
- **Pareja/Casa**: reservas inmovilizadas pero no consumidas por el solo hecho de reservar.
- **Cartas de Afinidad**: mismo recurso = cuota única; distintos recursos = dos cuotas. La cantidad sigue abierta. Pago terminal B es contabilidad de cierre, sin suponer que altera la fecha de victoria frente a simple tenencia.
- **Falso Lucas**: objetivo individual de Dinero más Casa vigente, no una cuota compartida con Clarisa.

Los tres tipos de victoria deben analizarse por separado, sin asumir que tienen idéntica probabilidad óptima.

## Límites explícitos de la Fase 1

1. **No** se asignaron cantidades, frecuencias, costos ni distribuciones históricas.
2. La definición final de premios por paso/destino en Juventud sigue abierta.
3. Los casilleros A/P/K/M de Adultez se identifican según el tablero conceptual v3.0, no v2.3.
4. No se han resuelto por implicación reglas de consentimiento, devolución de reservas, empate de victorias, reciclado de cartas o cambio de rol de Falso Lucas.
5. No se ha calibrado ni simulado v3.0; el resultado actual es una **matriz inspeccionable**, no una recomendación numérica.

## Comandos locales

```bash
python -m laboratorio.v3.catalogo --validar
python -m laboratorio.v3.catalogo --csv /tmp/matriz_economica_v3.csv
python -m unittest discover -s tests -p 'test_matriz_economica_v3.py' -v
```

## Condición para pasar a Fase 2

Cobertura auditada de todas las fuentes, consumos, reservas, umbrales y objetivos de la v3.0, identidades únicas, descripciones trazables y cero valores heredados. A continuación: medir las frecuencias de activación, modelar la demanda por etapa e introducir escenarios de calibración sin modificar v2.x.
