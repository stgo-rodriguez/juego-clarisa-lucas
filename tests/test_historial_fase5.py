"""Fase 5: integridad, intercambio, persistencia y recuperación de escenarios."""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from laboratorio.comparacion import (ejecutar, escenario_base, exportar_zip,
                                    comparar)
from laboratorio.historial import (MAX_ARCHIVO, abrir_local, cargar_archivo, crear_archivo,
                                  guardar_local, listar_local, comparar_guardados)
from simulador.economia import EconomyConfig


class TestHistorialFase5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = escenario_base(6, 12)
        cls.base = ejecutar(cls.config)
        cls.experimento = ejecutar(replace(cls.config, id='test-90-110',
            economia=EconomyConfig(cartas_ganancias_pct=90, cartas_perdidas_pct=110)))
        cls.payload = crear_archivo(cls.base, cls.experimento, nombre='Prueba 90/110')

    def test_roundtrip_integro(self):
        z = cargar_archivo(self.payload)
        self.assertEqual(z['base'], json.loads(json.dumps(self.base)))
        self.assertEqual(z['variante'], json.loads(json.dumps(self.experimento)))
        self.assertEqual(z['comparacion'], comparar(self.base, self.experimento))
        self.assertEqual(z['meta']['nombre'], 'Prueba 90/110')

    def test_archivo_recuperado_no_ejecuta_motor(self):
        with patch('simulador.motor.run_batch', side_effect=AssertionError('No ejecutar')):
            result = cargar_archivo(self.payload)
            comparado = comparar_guardados(result['base'], result['variante'])
        self.assertEqual(comparado['total'], 12)

    def test_hereda_zip_fase3_original(self):
        zipped = exportar_zip(self.base, self.experimento,
                             comparar(self.base, self.experimento))
        result = cargar_archivo(zipped)
        self.assertEqual(result['comparacion']['total'], 12)
        self.assertEqual(result['meta']['formato'], 'fase3-mvp')
        self.assertTrue(result['meta']['advertencias'])
        upgraded = crear_archivo(result['base'], result['variante'], nombre='Importado')
        self.assertEqual(cargar_archivo(upgraded)['meta']['formato'],
                         'clarisa-lucas-experimento-v1')

    def test_persistencia_local_abrir_listar(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            a = guardar_local(d, self.payload, nombre='Experimento A')
            b = guardar_local(d, self.payload, nombre='Experimento A')
            self.assertNotEqual(a, b)
            self.assertEqual(len(listar_local(d)), 2)
            self.assertEqual(abrir_local(d, a.name), self.payload)
            self.assertEqual(cargar_archivo(abrir_local(d, b.name))['comparacion']['total'], 12)

    def test_no_permite_rutas_ajenas_en_historial(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            guardar_local(p, self.payload)
            for bad in ('../archivo.zip', '/tmp/archivo.zip', 'inexistente.zip'):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    abrir_local(p, bad)

    def test_comparacion_no_apareada_rechazada(self):
        b = ejecutar(replace(self.config, seed=2026))
        with self.assertRaisesRegex(ValueError, 'seed'):
            comparar_guardados(self.base, b)

    def test_comparacion_otra_politica_rechazada(self):
        b = ejecutar(replace(self.config, bot='inversor'))
        with self.assertRaisesRegex(ValueError, 'bot'):
            comparar_guardados(self.base, b)

    def test_comparacion_motores_diferentes_rechazada(self):
        b = dict(self.experimento)
        b['codigo'] = {**self.experimento['codigo'], 'motor_sha256':'otra-version'}
        with self.assertRaisesRegex(ValueError, 'Motor'):
            comparar_guardados(self.base, b)

    def test_hash_resultado_corrupto_rechazado(self):
        with ZipFile(BytesIO(self.payload)) as z:
            files = {p.filename: z.read(p.filename) for p in z.infolist()}
        data = bytearray(files['base/filas.json'])
        data[10] ^= 1
        files['base/filas.json'] = bytes(data)
        tamper = BytesIO()
        with ZipFile(tamper,'w',ZIP_DEFLATED) as z:
            for name, content in files.items():z.writestr(name, content)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            cargar_archivo(tamper.getvalue())

    def test_zip_no_firmado_ni_otro_formato(self):
        z = BytesIO()
        with ZipFile(z,'w') as f:f.writestr('foo.txt','hola')
        with self.assertRaises(ValueError):cargar_archivo(z.getvalue())

    def test_zip_traversal_bloqueado(self):
        z = BytesIO()
        with ZipFile(z,'w') as f:f.writestr('../afuera.txt', 'hola')
        with self.assertRaisesRegex(ValueError, 'inseguro'):
            cargar_archivo(z.getvalue())

    def test_zip_miembros_duplicados_bloqueados(self):
        from warnings import catch_warnings, simplefilter
        z = BytesIO()
        with catch_warnings():
            simplefilter('ignore', UserWarning)
            with ZipFile(z,'w') as f:
                f.writestr('manifiesto.json','{}')
                f.writestr('manifiesto.json','{}')
        with self.assertRaisesRegex(ValueError, 'duplicadas'):
            cargar_archivo(z.getvalue())

    def test_archivo_demasiado_grande(self):
        with self.assertRaisesRegex(ValueError, 'grande'):
            cargar_archivo(b'x'*(MAX_ARCHIVO+1))

    def test_escenario_no_reproducible_rechazado(self):
        bad = {**self.base, 'filas':list(self.base['filas'])}
        bad['filas'][0] = {**bad['filas'][0], 'semilla':999}
        with self.assertRaisesRegex(ValueError, 'Semillas'):
            crear_archivo(bad,self.experimento)

    def test_resumen_adulterado_rechazado(self):
        bad = {**self.base, 'resumen':{**self.base['resumen'],'partidas':999}}
        with self.assertRaisesRegex(ValueError, 'Resumen'):
            crear_archivo(bad,self.experimento)

    def test_nombre_invalido_rechazado(self):
        with self.assertRaisesRegex(ValueError, 'nombre'):
            crear_archivo(self.base,self.experimento,nombre='')


class TestInterfazHistorial(unittest.TestCase):
    def test_seccion_visible(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no disponible en el entorno local')
        root = Path(__file__).resolve().parents[1]
        app = AppTest.from_file(str(root/'laboratorio/app.py'),default_timeout=120).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Historial de experimentos' in h.value for h in app.subheader))
        self.assertTrue(any('historial' in caption.value.lower()
                            for caption in app.caption))


if __name__=='__main__':
    unittest.main()
