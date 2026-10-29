# Laboratorio de Balance — Fase 5: historial y comparación

**Fecha:** 29/10/2026  
**Rama:** `feature/laboratorio-balance`  
**Reglas:** v1.3, sin modificaciones a motor o bots.

## Objetivo y estado

Habilitar persistencia de experimentos sin depender de la sesión de Streamlit y
comparación entre escenarios antiguos mediante semillas comunes sin volver a
simular. La sesión y el caché del navegador no constituyen almacenamiento durable.

## Arquitectura

`laboratorio/historial.py` opera sin Streamlit ni ejecución del motor. Toda
comparación se realiza sobre las filas recuperadas y la función histórica
`comparar()`. El panel `laboratorio/app.py` utiliza los mismos gráficos y tablas
que los escenarios ejecutados.

### Formato F5 (ZIP portable)

- `manifiesto.json`: formato, nombre, fecha UTC, identidad del motor y hashes SHA-256.
- `base/` y `variante/`, cada uno con `escenario.json`, `filas.json`,
  `resumen.json`, `muestras.json`, `codigo.json`.
- `comparacion.json`: diferencias apareadas calculadas en el guardado.

Se verifican todas las entradas del manifiesto, los hashes y las relaciones
semánticas entre escenario, partidas, semillas, fin/censura, resumen y
comparación. La huella del motor/mazo debe coincidir con la instalación actual
para cargar el archivo o compararlo con otra corrida. El lector de ZIP rechaza
entradas extrañas, repetidas, rutas con traversal, enlaces, payloads excesivos
y formatos no reconocidos. Las huellas detectan alteraciones accidentales; no
proporcionan autenticidad frente a un atacante que reescriba el manifiesto.

### Compatibilidad con ZIPs anteriores

`cargar_archivo()` lee ZIP `fase3-mvp`, verificando la huella SHA-256 original de
cada CSV y el contenido/consistencia de las configuraciones y resúmenes. Se
muestra que ese formato antiguo no firmaba todas sus entradas. Al importarlo
se crea una copia en formato F5. Los CSV originales contienen un esquema de
columnas global del lote (celdas en blanco): la reconstrucción detallada de
un registro histórico no queda garantizada si no coincide con `summary()`
per-partida del motor actual. La comparación de resultados agregados sí es válida.

## Almacenamiento local

Ruta predeterminada: `<raíz del proyecto>/.laboratorio/historial/*.zip`.
Los archivos nunca se agregan a Git (`.gitignore`). Escritura atómica con
archivo temporal y `os.replace`; nombres con fecha UTC, nombre sanitizado y
hash del ZIP. No se sobrescriben archivos existentes. No se implementa nube,
base de datos, sincronización entre dispositivos ni cuentas de usuario.

## Flujo en Streamlit

1. Ejecutar dos escenarios desde los controles existentes.
2. Nombrar y guardar, o descargar el ZIP portable.
3. En otra sesión, seleccionar un archivo A y otro B, el escenario Base o
   Experimento de cada uno, y cargar la comparación sin simular.
4. Importar un archivo externo para incorporarlo al historial local.
5. Explorar las métricas, gráfico de duración y análisis por partida.

### Requisitos de comparabilidad

- Los archivos seleccionados deben usar el mismo motor, adaptador, esquema de
  economía y mazo (SHA-256).
- Se requiere igual cantidad de jugadores, partidas, seed inicial, incremento
  de seed, tope de rondas y política de bot.
- La comparación reaprovecha la metodología apareada existente; censura y
  ausencia de intervalos de confianza se siguen señalando explícitamente.
- No se infieren equivalencias entre versiones distintas de motor. Los nombres
  de escenario pueden diferir sin afectar la comparación.

## Pruebas de aceptación

- Serialización y recuperación del resultado completo; comparación idéntica
  a la original sin ejecutar partidas.
- Importación del ZIP F3 previo y conversión al formato F5.
- Persistencia, listado, lectura y rechazo de escapes del directorio local.
- Rechazo de ZIP modificado, duplicado, mal formado o excesivamente grande.
- Rechazo de semillas, bots, motores y resúmenes incompatibles.
- Suite histórica de reglas y regresión binaria de 2.000 partidas.
- Prueba de interfaz en CI, donde Streamlit está instalado.

## Fuera del alcance de Fase 5

- Histórico remoto o compartido, búsqueda multiproyecto y publicación web.
- Comparación estadística con intervalos de confianza, reservada a Fase 6.
- Ejecución masiva de reconstrucciones de eventos de todas las partidas.

## Riesgo residual

La lectura de ZIPs de gran tamaño consume memoria al descomprimir; los límites
restringen tamaño total y por entrada. Streamlit puede tener memoria limitada
al mostrar múltiples corridas de 1.000 partidas. Se evita almacenar muchas
partidas detalladas en caché; los ZIP contienen solo las muestras ya existentes.
