# Guía de usuario — Laboratorio de Balance de Clarisa & Lucas

Aplicación **local**, separada de la web pública del juego. Motor/reglas v1.3 congelados. Requiere Mac con Python 3.11 o superior; se verificó la instalación original con Python 3.13.

## 1. Primera instalación (macOS)

Abrí Terminal e ingresá:

```bash
cd ~/Documents
git clone -b feature/laboratorio-balance https://github.com/stgo-rodriguez/juego-clarisa-lucas.git
cd juego-clarisa-lucas
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m laboratorio.diagnostico
./iniciar_laboratorio.sh
```

Si ya tenés el repositorio, **no lo clones por segunda vez**. Usá el procedimiento de actualización. Si tu Python 3.11+ tiene otro nombre, reemplazá `python3.13` en la creación del entorno virtual.

Abre `http://localhost:8501` o `http://127.0.0.1:8501`. Para salir, presioná **Ctrl+C** en la Terminal; no alcanza con cerrar la pestaña.

## 2. Actualización desde versiones anteriores

Guardá primero los ZIP que quieras conservar. Detené Streamlit con **Ctrl+C**:

```bash
cd ~/Documents/juego-clarisa-lucas
git switch feature/laboratorio-balance
git pull --ff-only origin feature/laboratorio-balance
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m laboratorio.diagnostico
./iniciar_laboratorio.sh
```

**No uses** `git reset --hard` ni `git clean -fd` para actualizar: podrías perder cambios locales. Si `git pull` rechaza la actualización por modificaciones locales, primero revisá `git status` y conservá las modificaciones antes de continuar.

Para uso cotidiano, solo necesitás:

```bash
cd ~/Documents/juego-clarisa-lucas
./iniciar_laboratorio.sh
```

## 3. Recorrido recomendado

1. En **Configuración común**, elegí **6 jugadores / 20 partidas** para la primera prueba. Mantené la semilla inicial original y las condiciones económicas al 100%.
2. Pulsá **Ejecutar y comparar escenarios**. Base y experimento idénticos deben producir diferencia cero.
3. Modificá **Ganancias por cartas = 90%** y **Pérdidas por cartas = 110%**; volvé a ejecutar. Interpretá con cuidado censura e incertidumbre.
4. Desde los resultados podés reconstruir **una partida elegida**: Gantt de hitos, economía, interacciones y actividad de turnos. Esas reconstrucciones reejecutan solo esa partida y comprueban los resultados.
5. **Historial de experimentos (Fase 5)**: guardá las comparaciones en tu Mac, importá antiguos ZIP o recuperá dos experimentos para compararlos sin volver a simular.
6. **Sensibilidad e incertidumbre (Fase 6)**: elegí dos parámetros y una cuadrícula. Usá pocas partidas para explorar; ampliá únicamente los escenarios prometedores. Límite de 3.000 partidas presupuestadas por matriz.

**Importante:** la aplicación simula **bots**, no humanos. Más rondas, más acciones y mayor tasa de Duelos no son pruebas de mejor jugabilidad. Si hay partidas que no terminaron, diferenciá rondas **observadas hasta el horizonte** de duración final.

## 4. Persistencia y copias de seguridad

Los experimentos guardados quedan en:

- `.laboratorio/historial/`: comparaciones completas (ZIP).
- `.laboratorio/sensibilidad/`: matrices resumidas (ZIP).

Estas carpetas se ignoran en Git y **no se sincronizan automáticamente**. Respaldá/exportá los ZIP si actualizás de computadora. El caché de Streamlit no equivale a un archivo persistente. Importá únicamente ZIP de origen confiable: SHA-256 verifica integridad de bytes, **no** identidad del productor ni autenticidad.

## 5. Problemas frecuentes

| Síntoma | Diagnóstico / solución |
|---|---|
| `python3.13: command not found` | Usá el nombre de tu Python 3.11+ instalado (`python3` o `python3.12`). |
| `.venv/bin/python` no existe | Creá el entorno virtual con `python3.13 -m venv .venv` e instalá requisitos. |
| `No module named streamlit` | `source .venv/bin/activate` y `python -m pip install -r requirements.txt`. |
| Puerto `8501` ocupado | Cerrá el proceso anterior con **Ctrl+C** o inspeccioná `lsof -iTCP:8501 -sTCP:LISTEN`. |
| Pantalla en blanco | Confirmá que Terminal no muestre un traceback; recargá `http://127.0.0.1:8501`. |
| Diagnóstico de integridad falla | No ejecutes resultados de la instalación alterada. Actualizá desde Git con cambios locales respaldados. |
| ZIP incompatible | Verificá versión de motor/mazo, semillas, bots, horizonte y jugadores. No se fuerzan comparaciones incompatibles. |
| Almacenamiento no escribible | Verificá permisos sobre la carpeta del repositorio y espacio disponible. |
| Las simulaciones tardan | Probá 20 partidas antes de 500/1000. Usá `python -m laboratorio.benchmark_fase7` para medir tu equipo. |

Diagnóstico reproducible para adjuntar a un pedido de ayuda:

```bash
cd ~/Documents/juego-clarisa-lucas
source .venv/bin/activate
python -m laboratorio.diagnostico --json
python -m laboratorio.benchmark_fase7 --json
```

El diagnóstico no necesita internet. No incluye nombres de usuarios, contraseñas ni datos personales.

## 6. Privacidad y despliegue

Esta instalación escucha únicamente en **127.0.0.1**, con protección XSRF y límite de cargas. No se publica en internet y no incluye autenticación de usuarios. **No cambies la dirección a `0.0.0.0` para abrirla a terceros** sin un diseño de acceso, límites y tratamiento del historial. Un servidor público requiere una revisión separada y autorización expresa.
