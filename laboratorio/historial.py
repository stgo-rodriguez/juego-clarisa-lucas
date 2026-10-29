"""Archivo local, intercambio y recuperación verificable de experimentos (Fase 5).

Sin motor ni Streamlit. Los resultados se conservan íntegros: recuperar y comparar
no ejecuta partidas. Los ZIPs externos se consideran datos no confiables.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, BadZipFile

from laboratorio.comparacion import comparar, escenario_desde_dict, signature
from simulador.motor import aggregate

FORMATO = 'clarisa-lucas-experimento-v1'
MAX_ARCHIVO = 24 * 1024 * 1024
MAX_DESCOMPRIMIDO = 70 * 1024 * 1024
MAX_MIEMBRO = 45 * 1024 * 1024
MAX_PARTIDAS = 20000
SUBARCHIVOS = ('escenario.json', 'filas.json', 'resumen.json', 'muestras.json', 'codigo.json')
NOMBRES = [f'{lado}/{nombre}' for lado in ('base', 'variante') for nombre in SUBARCHIVOS]


def _json(data: object) -> bytes:
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('utf-8')


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _validar_resultado(resultado: dict) -> None:
    if not isinstance(resultado, dict):
        raise ValueError('Resultado inválido')
    escenario = escenario_desde_dict(resultado['escenario'])
    filas = resultado['filas']
    if not isinstance(filas, list) or len(filas) != escenario.partidas or len(filas) > MAX_PARTIDAS:
        raise ValueError('Cantidad de partidas distinta de la configuración')
    if not isinstance(resultado.get('codigo'), dict) or not resultado['codigo']:
        raise ValueError('Falta la identidad del motor y del mazo')
    if not isinstance(resultado.get('muestras'), list):
        raise ValueError('Faltan registros de muestra')
    for i, fila in enumerate(filas):
        if not isinstance(fila, dict):
            raise ValueError('Fila de partida inválida')
        if int(fila['partida']) != i + 1:
            raise ValueError('Número de partida inesperado')
        if int(fila['semilla']) != escenario.seed + i * escenario.incremento_seed:
            raise ValueError('Semillas incompatibles con la configuración')
        if int(fila['jugadores']) != escenario.jugadores:
            raise ValueError('Cantidad de jugadores incompatible')
        if int(fila['terminada']) not in (0, 1) or int(fila['censurada']) != 1 - int(fila['terminada']):
            raise ValueError('Estado de finalización/censura contradictorio')
        if not 0 < int(fila['rondas_observadas']) <= escenario.max_rondas:
            raise ValueError('Rondas fuera del horizonte')
        if int(fila.get('errores', 0)) < 0:
            raise ValueError('Contador de errores negativo')
    actual = aggregate(filas)
    if resultado.get('resumen') != actual:
        raise ValueError('Resumen no coincide con las partidas; archivo alterado o inconsistente')


def _validar_pareja(base: dict, variante: dict) -> dict:
    _validar_resultado(base)
    _validar_resultado(variante)
    if base['codigo'] != variante['codigo']:
        raise ValueError('Los escenarios provienen de versiones de motor/mazo diferentes')
    return comparar(base, variante)


def crear_archivo(base: dict, variante: dict, *, nombre: str = 'Experimento') -> bytes:
    diferencia = _validar_pareja(base, variante)
    if not isinstance(nombre, str) or not 1 <= len(nombre.strip()) <= 100:
        raise ValueError('El nombre debe tener entre 1 y 100 caracteres')
    archivos = {}
    for lado, result in (('base', base), ('variante', variante)):
        for member, key in [('escenario.json', 'escenario'), ('filas.json', 'filas'),
                            ('resumen.json', 'resumen'), ('muestras.json', 'muestras'),
                            ('codigo.json', 'codigo')]:
            archivos[f'{lado}/{member}'] = _json(result[key])
    archivos['comparacion.json'] = _json(diferencia)
    manifiesto = {'formato': FORMATO, 'nombre': nombre.strip(),
                  'fecha_utc': datetime.now(timezone.utc).isoformat(),
                  'codigo': base['codigo'],
                  'archivos_sha256': {k: _sha(v) for k, v in archivos.items()}}
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=6) as zf:
        for path, raw in archivos.items():
            zf.writestr(path, raw)
        zf.writestr('manifiesto.json', _json(manifiesto))
    payload = output.getvalue()
    if len(payload) > MAX_ARCHIVO:
        raise ValueError('El experimento excede el límite de almacenamiento')
    return payload


def _leer_zip(payload: bytes) -> dict[str, bytes]:
    if not isinstance(payload, bytes) or len(payload) > MAX_ARCHIVO:
        raise ValueError('Archivo ZIP demasiado grande o inválido')
    try:
        with ZipFile(BytesIO(payload)) as zf:
            infos = zf.infolist()
            if not 1 <= len(infos) <= 25:
                raise ValueError('Cantidad de entradas ZIP inválida')
            nombres = [i.filename for i in infos]
            if len(nombres) != len(set(nombres)):
                raise ValueError('Entradas duplicadas en ZIP')
            if any(i.is_dir() or i.filename.startswith('/') or '..' in Path(i.filename).parts
                   or '\\' in i.filename or (i.external_attr >> 16) & 0o170000 == 0o120000
                   for i in infos):
                raise ValueError('Ruta o enlace inseguro dentro del ZIP')
            if any(i.file_size > MAX_MIEMBRO or i.compress_size < 0 for i in infos):
                raise ValueError('Entrada ZIP demasiado grande')
            if sum(i.file_size for i in infos) > MAX_DESCOMPRIMIDO:
                raise ValueError('Descompresión total demasiado grande')
            return {info.filename: zf.read(info) for info in infos}
    except (BadZipFile, OSError, RuntimeError, EOFError) as exc:
        raise ValueError(f'ZIP ilegible: {exc}') from exc


def _json_archivo(archivos: dict[str, bytes], nombre: str):
    try:
        return json.loads(archivos[nombre].decode('utf-8'))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ValueError(f'Falta o no se puede leer {nombre}') from exc


def _parse_csv_original(raw: bytes) -> list[dict]:
    text = raw.decode('utf-8-sig')
    reader = csv.DictReader(StringIO(text, newline=''))
    if not reader.fieldnames or 'semilla' not in reader.fieldnames or 'rondas_observadas' not in reader.fieldnames:
        raise ValueError('CSV histórico sin columnas requeridas')
    out = []
    for row in reader:
        if len(out) >= MAX_PARTIDAS:
            raise ValueError('Demasiadas partidas en CSV')
        parsed = {}
        for k, value in row.items():
            if k is None:
                raise ValueError('Columnas CSV mal formadas')
            if value == '' or value is None:
                parsed[k] = ''
            elif re.fullmatch(r'-?\d+', value):
                parsed[k] = int(value)
            elif re.fullmatch(r'-?\d+\.\d+', value):
                parsed[k] = float(value)
            else:
                parsed[k] = value
        for numeric in ('proyectos', 'proyectos_completados', 'proyectos_adjudicados',
                        'funded_subhitos', 'bank_conversions', 'duels_started',
                        'profile_changes', 'receipts_traded', 'house_attempts', 'blocked_affinity'):
            if parsed.get(numeric) == '':
                parsed[numeric] = 0
        out.append(parsed)
    return out


def cargar_archivo(payload: bytes, *, exigir_codigo_actual: bool = True) -> dict:
    """Carga formatos propio F5 o ZIP F3 anterior. Nunca llama al simulador."""
    archivos = _leer_zip(payload)
    manifest = _json_archivo(archivos, 'manifiesto.json')
    advertencias = []
    if manifest.get('formato') == FORMATO:
        hashes = manifest.get('archivos_sha256')
        expected = set(NOMBRES + ['comparacion.json'])
        if not isinstance(hashes, dict) or set(hashes) != expected or set(archivos) != expected | {'manifiesto.json'}:
            raise ValueError('Manifiesto incompleto o archivos extra no previstos')
        for name, expected_hash in hashes.items():
            if _sha(archivos[name]) != expected_hash:
                raise ValueError(f'Hash SHA-256 incorrecto: {name}')
        result = {}
        for lado in ('base', 'variante'):
            result[lado] = {
                'escenario': _json_archivo(archivos, f'{lado}/escenario.json'),
                'filas': _json_archivo(archivos, f'{lado}/filas.json'),
                'resumen': _json_archivo(archivos, f'{lado}/resumen.json'),
                'muestras': _json_archivo(archivos, f'{lado}/muestras.json'),
                'codigo': _json_archivo(archivos, f'{lado}/codigo.json'),
            }
        comparacion = _validar_pareja(result['base'], result['variante'])
        if comparacion != _json_archivo(archivos, 'comparacion.json'):
            raise ValueError('Comparación guardada no coincide con las partidas')
        if manifest.get('codigo') != result['base']['codigo']:
            raise ValueError('Identidad del motor alterada en manifiesto')
        resultado = {'base': result['base'], 'variante': result['variante'],
                     'comparacion': comparacion,
                     'meta': {'nombre': str(manifest.get('nombre', 'Experimento')),
                              'fecha_utc': manifest.get('fecha_utc'),
                              'formato': FORMATO, 'advertencias': advertencias}}
    elif manifest.get('version') == 'fase3-mvp':
        expected = {'manifiesto.json', 'comparacion.json'}
        expected |= {f'{lado}/{x}' for lado in ('base', 'variante')
                     for x in ('resultados.csv', 'escenario.json', 'resumen.json', 'muestra_eventos.json')}
        if set(archivos) != expected:
            raise ValueError('Formato histórico desconocido o incompleto')
        files_hash = manifest.get('archivos', {})
        for lado in ('base', 'variante'):
            name = f'{lado}/resultados.csv'
            if _sha(archivos[name]) != files_hash.get(name):
                raise ValueError(f'Hash CSV histórico incorrecto: {name}')
        if not isinstance(manifest.get('motor'), dict):
            raise ValueError('Manifiesto histórico sin identidad del motor')
        results = {}
        for lado in ('base', 'variante'):
            results[lado] = {
                'escenario': _json_archivo(archivos, f'{lado}/escenario.json'),
                'filas': _parse_csv_original(archivos[f'{lado}/resultados.csv']),
                'resumen': _json_archivo(archivos, f'{lado}/resumen.json'),
                'muestras': _json_archivo(archivos, f'{lado}/muestra_eventos.json'),
                'codigo': manifest['motor'],
            }
        comparacion = _validar_pareja(results['base'], results['variante'])
        # El formato anterior solo firmaba los CSV: el resto se valida semánticamente.
        advertencias.append('Formato Fase 3: SHA-256 solo cubre los CSV, no el resto del ZIP.')
        resultado = {'base': results['base'], 'variante': results['variante'],
                     'comparacion': comparacion,
                     'meta': {'nombre': 'Experimento importado (Fase 3)', 'fecha_utc': None,
                              'formato': 'fase3-mvp', 'advertencias': advertencias}}
    else:
        raise ValueError('Versión del ZIP no reconocida')
    if exigir_codigo_actual and resultado['base']['codigo'] != signature():
        raise ValueError('Versión de motor/mazo incompatible con la instalación actual')
    if resultado['base']['codigo'] != signature():
        resultado['meta']['advertencias'].append('Motor/mazo diferente: no se permite combinar con los escenarios actuales.')
    return resultado


def guardar_local(directorio: Path, payload: bytes, *, nombre: str = 'Experimento') -> Path:
    """Guarda un ZIP válido con escritura atómica; no sobrescribe experimentos."""
    cargar_archivo(payload)
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)
    title = re.sub(r'[^a-zA-Z0-9_-]+', '-', nombre.strip())[:50].strip('-') or 'experimento'
    slug = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = directorio / f'{slug}_{title}_{_sha(payload)[:10]}.zip'
    fd, temp = tempfile.mkstemp(prefix='.tmp-', suffix='.zip', dir=directorio)
    try:
        with os.fdopen(fd, 'wb') as writer:
            writer.write(payload)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return target


def listar_local(directorio: Path) -> list[Path]:
    if not Path(directorio).is_dir():
        return []
    return sorted((p for p in Path(directorio).glob('*.zip') if p.is_file() and not p.is_symlink()),
                  key=lambda p: p.name, reverse=True)


def abrir_local(directorio: Path, archivo: str) -> bytes:
    """Acepta únicamente un nombre de archivo existente en el directorio del historial."""
    if not isinstance(archivo, str) or Path(archivo).name != archivo:
        raise ValueError('Nombre de archivo inválido')
    path = Path(directorio) / archivo
    if path not in listar_local(directorio):
        raise ValueError('El archivo no pertenece al historial local')
    if path.stat().st_size > MAX_ARCHIVO:
        raise ValueError('Archivo local demasiado grande')
    return path.read_bytes()


def comparar_guardados(a: dict, b: dict) -> dict:
    """Compara dos resultados individuales importados sin simular. Solo mismo código/mazo."""
    _validar_resultado(a)
    _validar_resultado(b)
    if a['codigo'] != b['codigo'] or a['codigo'] != signature():
        raise ValueError('Motor, adaptador, economía o mazo distintos: comparación bloqueada')
    return comparar(a, b)
