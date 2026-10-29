"""Diagnóstico previo a ejecutar Streamlit (solo biblioteca estándar).

Uso:
  python -m laboratorio.diagnostico
  python -m laboratorio.diagnostico --json
No modifica el motor, las reglas ni las simulaciones.
"""
from __future__ import annotations

import argparse
import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import tomllib

from laboratorio.ejecucion import ROOT
from laboratorio.verificar_baseline import REFERENCE_HASHES

MOTOR_VALIDADO = '9ea6c0b19c8ff7f76e07bf13ab8831b5d48e373a57c7e3fb2ea3d1d349f8ef32'
MAZO_VALIDADO = 'cc337a84d4b37af7d329784e1fa34d0b13652a6c26408885f56dde7ee65f784e'
DEPENDENCIAS = ('streamlit', 'pandas', 'plotly')


def diagnosticar(root: Path = ROOT, *, comprobar_dependencias: bool = True,
                comprobar_escritura: bool = True) -> dict:
    """Produce controles independientes, incluidos errores informativos para soporte.

    `apto` es true solo si todos los controles obligatorios resultan OK.
    Nunca ejecuta partidas ni hace conexiones de red.
    """
    root = Path(root)
    controles: list[dict] = []

    def control(nombre: str, accion) -> None:
        try:
            detalle = accion()
            controles.append({'control': nombre, 'estado': 'ok', 'detalle': str(detalle)})
        except Exception as exc:
            controles.append({'control': nombre, 'estado': 'error',
                              'detalle': f'{type(exc).__name__}: {exc}'})

    def version() -> str:
        if sys.version_info < (3, 11):
            raise RuntimeError('Se requiere Python 3.11 o posterior')
        return sys.version.split()[0]

    def dependencias() -> str:
        ausentes = [nombre for nombre in DEPENDENCIAS if importlib.util.find_spec(nombre) is None]
        if ausentes:
            raise RuntimeError('Faltan paquetes: ' + ', '.join(ausentes)
                               + '. Instalá: python -m pip install -r requirements.txt')
        return ', '.join(DEPENDENCIAS)

    def sha_relativa(nombre: str, esperado: str) -> str:
        ruta = root / nombre
        actual = sha256(ruta.read_bytes()).hexdigest()
        if actual != esperado:
            raise RuntimeError(f'Huella no coincide para {nombre}; archivo modificado o incompleto')
        return actual

    def referencias() -> str:
        for jugadores, esperado in REFERENCE_HASHES.items():
            archivo = root / 'referencias' / f'resultados_{jugadores}j.csv.gz'
            if sha256(gzip.decompress(archivo.read_bytes())).hexdigest() != esperado:
                raise RuntimeError(f'CSV de referencia {jugadores} jugadores no coincide')
        return '6 jugadores y 10 jugadores; 2.000 partidas históricas'

    def servidor_local() -> str:
        config = tomllib.loads((root / '.streamlit/config.toml').read_text(encoding='utf-8'))
        srv = config.get('server', {})
        if srv.get('address') != '127.0.0.1':
            raise RuntimeError('Streamlit debe escuchar únicamente en 127.0.0.1 para uso local')
        if srv.get('enableXsrfProtection') is not True:
            raise RuntimeError('Protección XSRF debe estar habilitada')
        if srv.get('maxUploadSize', 0) > 24:
            raise RuntimeError('El límite de carga no debe superar 24 MB')
        return '127.0.0.1; protección XSRF; carga máxima <=24 MB'

    def escritura() -> str:
        base = root / '.laboratorio'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='diagnostico-', dir=base) as ruta:
            (Path(ruta) / 'prueba.txt').write_text('ok', encoding='utf-8')
        return 'directorio local escribible (.laboratorio/)'

    control('Python', version)
    if comprobar_dependencias:
        control('Dependencias', dependencias)
    control('Motor v1.3 congelado', lambda: sha_relativa('simulador/motor_v13_base.py', MOTOR_VALIDADO))
    control('Mazo validado', lambda: sha_relativa('simulador/cards_v13_effects.txt', MAZO_VALIDADO))
    control('Referencias históricas', referencias)
    control('Servidor local', servidor_local)
    if comprobar_escritura:
        control('Historial local', escritura)
    return {'apto': all(c['estado'] == 'ok' for c in controles), 'controles': controles,
            'directorio': str(root)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Autodiagnóstico del Laboratorio de Balance')
    parser.add_argument('--json', action='store_true', help='Salida JSON para diagnóstico o soporte')
    parser.add_argument('--sin-dependencias', action='store_true', help='Verifica archivos sin instalar Streamlit')
    parser.add_argument('--sin-escritura', action='store_true', help='Evita crear archivos temporales')
    args = parser.parse_args(argv)
    resultado = diagnosticar(comprobar_dependencias=not args.sin_dependencias,
                            comprobar_escritura=not args.sin_escritura)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        for x in resultado['controles']:
            print(f"{'OK' if x['estado'] == 'ok' else 'ERROR'}  {x['control']}: {x['detalle']}")
        print('Laboratorio apto para iniciar.' if resultado['apto']
              else 'Instalación no apta. Corregí los controles con ERROR y repetí el diagnóstico.')
    return 0 if resultado['apto'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
