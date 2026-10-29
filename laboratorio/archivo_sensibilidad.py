"""Intercambio y archivo local de grillas de Fase 6 (sin reejecutar partidas)."""
from __future__ import annotations

import csv
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from laboratorio.sensibilidad import GridConfig, MAX_CELDAS, PARAMETROS

FORMATO = 'clarisa-lucas-sensibilidad-v1'
MAX_ZIP = 3_000_000
MAX_JSON = 2_000_000
ARCHIVOS = ('grilla.json', 'resultados.json', 'resultados.csv')


def _jdata(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def _csv(celdas: list[dict]) -> bytes:
    keys = ['x', 'y', 'n', 'finalizadas_base', 'finalizadas_variante',
            'censuradas_base', 'censuradas_variante', 'delta_rondas_observadas',
            'ic95_rondas_observadas_inf', 'ic95_rondas_observadas_sup',
            'delta_finalizacion_pp', 'ic95_finalizacion_pp_inf',
            'ic95_finalizacion_pp_sup', 'delta_rondas_pares_concluidos',
            'mediana_base_concluidas', 'mediana_variante_concluidas',
            'p90_base_concluidas', 'p90_variante_concluidas']
    stream = StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=keys, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(celdas)
    return ('\ufeff' + stream.getvalue()).encode('utf-8')


def validar_resultados(grilla: dict) -> GridConfig:
    if not isinstance(grilla, dict) or grilla.get('formato') != 'sensibilidad-v1':
        raise ValueError('No es un resultado de sensibilidad compatible')
    cfg = GridConfig.from_dict(grilla.get('configuracion'))
    if not isinstance(grilla.get('motor'), dict) or not all(
            isinstance(grilla['motor'].get(k), str) and len(grilla['motor'][k]) == 64
            for k in ('motor_sha256', 'adaptador_sha256', 'mazo_sha256', 'economia_sha256')):
        raise ValueError('Falta identidad comprobable de motor, adaptador, mazo o economía')
    cells = grilla.get('celdas')
    if not isinstance(cells, list) or len(cells) != len(cfg.valores_x) * len(cfg.valores_y):
        raise ValueError('Cantidad de celdas inconsistente')
    for i, item in enumerate(cells):
        if not isinstance(item, dict):
            raise ValueError('Celda inválida')
        if item.get('x') != cfg.valores_x[i % len(cfg.valores_x)] or item.get('y') != cfg.valores_y[i // len(cfg.valores_x)]:
            raise ValueError('Coordenadas de grilla incompatibles')
        if item.get('n') != cfg.partidas:
            raise ValueError('Cantidad de partidas de la celda inválida')
        econ = item.get('economia')
        if (not isinstance(econ, dict) or econ.get(cfg.parametro_x) != item['x']
                or econ.get(cfg.parametro_y) != item['y']):
            raise ValueError('Variables económicas inconsistentes')
        for field in ('delta_rondas_observadas', 'delta_finalizacion_pp'):
            v = item.get(field)
            if not isinstance(v, (int, float)) or not (-cfg.max_rondas <= v <= cfg.max_rondas if field == 'delta_rondas_observadas' else -100 <= v <= 100):
                raise ValueError(f'Métrica inválida: {field}')
        for f in ('finalizadas_base','finalizadas_variante','ambas_finalizadas','censuradas_base','censuradas_variante'):
            if type(item.get(f)) is not int or not 0 <= item[f] <= cfg.partidas:
                raise ValueError(f'Contador inválido: {f}')
        if item['finalizadas_base']+item['censuradas_base'] != cfg.partidas or item['finalizadas_variante']+item['censuradas_variante'] != cfg.partidas:
            raise ValueError('Censura no cuadra con finalizaciones')
    return cfg


def exportar_grilla(grilla: dict) -> bytes:
    validar_resultados(grilla)
    payload = {'grilla.json': _jdata(grilla['configuracion']),
               'resultados.json': _jdata(grilla),
               'resultados.csv': _csv(grilla['celdas'])}
    manifest = {'formato': FORMATO, 'archivos': {k: sha256(v).hexdigest() for k, v in payload.items()}}
    buf = BytesIO()
    with ZipFile(buf, 'w', ZIP_DEFLATED, compresslevel=7) as z:
        for name, body in payload.items():
            z.writestr(name, body)
        z.writestr('manifiesto.json', _jdata(manifest))
    if len(buf.getvalue()) > MAX_ZIP:
        raise ValueError('El archivo de sensibilidad supera el tamaño máximo permitido')
    return buf.getvalue()


def importar_grilla(data: bytes) -> dict:
    if not isinstance(data, bytes) or len(data) > MAX_ZIP:
        raise ValueError('Archivo demasiado grande o inválido')
    try:
        with ZipFile(BytesIO(data)) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or set(names) != set(ARCHIVOS) | {'manifiesto.json'}:
                raise ValueError('Miembros duplicados o inesperados')
            if any(i.file_size > MAX_JSON for i in infos):
                raise ValueError('Miembro demasiado grande')
            bodies = {name: z.read(name) for name in names}
    except (BadZipFile, OSError, UnicodeDecodeError) as exc:
        raise ValueError('ZIP inválido') from exc
    manifest = json.loads(bodies['manifiesto.json'])
    if manifest.get('formato') != FORMATO:
        raise ValueError('Formato de sensibilidad no reconocido')
    if manifest.get('archivos') != {k: sha256(bodies[k]).hexdigest() for k in ARCHIVOS}:
        raise ValueError('Verificación SHA-256 incorrecta')
    grilla = json.loads(bodies['resultados.json'])
    cfg = validar_resultados(grilla)
    if cfg.as_dict() != json.loads(bodies['grilla.json']) or bodies['resultados.csv'] != _csv(grilla['celdas']):
        raise ValueError('Configuración o CSV inconsistentes')
    return grilla


def guardar_grilla(directorio: Path, contenido: bytes, *, nombre: str='Sensibilidad') -> Path:
    importar_grilla(contenido)  # rechazar ZIP no validado
    folder = Path(directorio)
    folder.mkdir(parents=True, exist_ok=True)
    clean = re.sub(r'[^a-zA-Z0-9_-]+', '-', nombre.strip())[:50].strip('-') or 'Sensibilidad'
    digest = sha256(contenido).hexdigest()[:12]
    target = folder / f'{clean}-{digest}.zip'
    if not target.exists():
        target.write_bytes(contenido)
    return target


def listar_grillas(directorio: Path) -> list[Path]:
    folder = Path(directorio)
    return sorted(folder.glob('*.zip')) if folder.is_dir() else []


def leer_grilla(directorio: Path, nombre: str) -> dict:
    if not isinstance(nombre, str) or Path(nombre).name != nombre or not nombre.endswith('.zip'):
        raise ValueError('Nombre de archivo inseguro')
    p = Path(directorio) / nombre
    if not p.is_file() or p.is_symlink():
        raise ValueError('Archivo inexistente o enlace no admitido')
    return importar_grilla(p.read_bytes())
