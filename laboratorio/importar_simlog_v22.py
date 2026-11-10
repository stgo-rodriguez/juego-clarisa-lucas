"""Importar ZIP de GitHub Actions al visualizador SIMLOG v2.1/v2.2.

Admite el ZIP de la partida o el ZIP envoltorio descargado desde
la sección Artifacts de GitHub Actions. No reescribe trazas.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import zipfile

SCHEMA = 'SIMLOG-2.2'
RULESET = 'especificacion-integral-2026-11-09'


def _zip_bytes(source: Path) -> bytes:
    if source.is_dir():
        archives = sorted(source.rglob('*.zip'))
        if len(archives) != 1:
            raise ValueError('La carpeta debe contener exactamente un archivo ZIP')
        source = archives[0]
    data = source.read_bytes()
    with zipfile.ZipFile(BytesIO(data)) as outer:
        names = outer.namelist()
        if any(name.endswith('/manifest.json') or name == 'manifest.json'
               for name in names):
            return data
        nested = [name for name in names if name.lower().endswith('.zip')
                  and not name.startswith('/') and '..' not in Path(name).parts]
        if len(nested) != 1:
            raise ValueError('ZIP no contiene trazas SIMLOG ni un único ZIP interno')
        return outer.read(nested[0])


def validate_simlog(data: bytes) -> tuple[int, str]:
    with zipfile.ZipFile(BytesIO(data)) as archive:
        files = set(archive.namelist())
        if any(name.startswith('/') or '..' in Path(name).parts for name in files):
            raise ValueError('El ZIP contiene rutas inseguras')
        manifests = sorted(name for name in files
                           if name == 'manifest.json' or name.endswith('/manifest.json'))
        if not manifests:
            raise ValueError('No se encontró manifest.json')
        for filename in manifests:
            manifest = json.loads(archive.read(filename).decode('utf-8-sig'))
            if manifest.get('schema') != SCHEMA or manifest.get('ruleset') != RULESET:
                raise ValueError(f'Esquema o reglas incompatibles en {filename}')
            if int(manifest.get('player_count', 0)) != 6:
                raise ValueError('La corrida importada no es de seis participantes')
            folder = filename.rsplit('/', 1)[0] if '/' in filename else ''
            for required in ('turnos.csv', 'eventos.csv'):
                name = f'{folder}/{required}' if folder else required
                if name not in files:
                    raise ValueError(f'Falta {name}')
            for basename, expected in (manifest.get('file_sha256') or {}).items():
                item = f'{folder}/{basename}' if folder else basename
                if item not in files:
                    raise ValueError(f'Falta archivo auditado {item}')
                actual = hashlib.sha256(archive.read(item)).hexdigest()
                if actual != expected:
                    raise ValueError(f'Checksum no válido en {item}')
        return len(manifests), hashlib.sha256(data).hexdigest()


def import_archive(source: Path, dest: Path) -> Path:
    content = _zip_bytes(source.expanduser())
    count, digest = validate_simlog(content)
    dest = dest.expanduser()
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / 'SIMLOG_v22_6j_max700_s701.zip'
    if target.exists() and target.read_bytes() != content:
        target = dest / f'SIMLOG_v22_6j_max700_s701_{digest[:10]}.zip'
    if not target.exists():
        target.write_bytes(content)
    print(f'Importadas {count} partida(s) SIMLOG-2.2')
    print(f'Archivo local: {target.resolve()}')
    print(f'SHA256: {digest}')
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archivo', type=Path,
                        help='ZIP descargado de GitHub Actions o carpeta con un ZIP')
    parser.add_argument('--resultados', type=Path, default=Path('resultados'))
    args = parser.parse_args(argv)
    import_archive(args.archivo, args.resultados)


if __name__ == '__main__':
    main()
