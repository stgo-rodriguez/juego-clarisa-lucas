"""Validaciones de despliegue local; no tocan el motor del juego."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from laboratorio.diagnostico import (MOTOR_VALIDADO, MAZO_VALIDADO,
                                    diagnosticar, main)
from laboratorio.benchmark_fase7 import medir
from laboratorio.ejecucion import ROOT


class TestDiagnosticoFase7(unittest.TestCase):
    def test_entorno_sin_dependencias_en_ci_minima(self):
        info = diagnosticar(comprobar_dependencias=False, comprobar_escritura=False)
        self.assertTrue(info['apto'], info['controles'])
        self.assertEqual(len(info['controles']), 5)
        self.assertEqual(main(['--sin-dependencias', '--sin-escritura', '--json']), 0)

    def test_motor_y_mazo_congelados(self):
        self.assertEqual(sha256((ROOT/'simulador/motor_v13_base.py').read_bytes()).hexdigest(),
                         MOTOR_VALIDADO)
        self.assertEqual(sha256((ROOT/'simulador/cards_v13_effects.txt').read_bytes()).hexdigest(),
                         MAZO_VALIDADO)

    def test_detecta_archivo_corrupto_y_config_sin_proteccion(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'simulador').mkdir()
            (root/'referencias').mkdir()
            (root/'.streamlit').mkdir()
            (root/'simulador/motor_v13_base.py').write_text('corrupto')
            (root/'simulador/cards_v13_effects.txt').write_text('corrupto')
            (root/'.streamlit/config.toml').write_text('[server]\naddress="0.0.0.0"\n')
            info = diagnosticar(root, comprobar_dependencias=False,
                                comprobar_escritura=False)
        self.assertFalse(info['apto'])
        results = {x['control']:x for x in info['controles']}
        self.assertEqual(results['Motor v1.3 congelado']['estado'], 'error')
        self.assertEqual(results['Servidor local']['estado'], 'error')
        self.assertEqual(results['Referencias históricas']['estado'], 'error')

    def test_detecta_dependencia_ausente(self):
        with patch('laboratorio.diagnostico.importlib.util.find_spec', return_value=None):
            info = diagnosticar(comprobar_escritura=False)
        self.assertFalse(info['apto'])
        self.assertIn('streamlit', next(x['detalle'] for x in info['controles']
                                      if x['control'] == 'Dependencias'))

    def test_historial_crea_y_elimina_temporales(self):
        with TemporaryDirectory() as tmp:
            # Construcción de una raíz mínima con archivos válidos por copia.
            root = Path(tmp)
            for nombre in ('simulador/motor_v13_base.py',
                           'simulador/cards_v13_effects.txt',
                           'referencias/resultados_6j.csv.gz',
                           'referencias/resultados_10j.csv.gz',
                           '.streamlit/config.toml'):
                destino = root/nombre
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes((ROOT/nombre).read_bytes())
            info = diagnosticar(root, comprobar_dependencias=False)
            self.assertTrue(info['apto'], info['controles'])
            self.assertTrue((root/'.laboratorio').is_dir())
            self.assertEqual(list((root/'.laboratorio').iterdir()), [])

    def test_configuracion_solo_local(self):
        import tomllib
        config = tomllib.loads((ROOT/'.streamlit/config.toml').read_text())
        self.assertEqual(config['server']['address'], '127.0.0.1')
        self.assertTrue(config['server']['enableXsrfProtection'])
        self.assertTrue(config['server']['enableCORS'])
        self.assertLessEqual(config['server']['maxUploadSize'], 24)

    def test_lanzador_no_instala_dependencias_ni_hace_red(self):
        script = (ROOT/'iniciar_laboratorio.sh').read_text()
        self.assertIn('python -m laboratorio.diagnostico', script)
        self.assertIn('server.address=127.0.0.1', script)
        self.assertNotIn('pip install', script)
        self.assertNotIn('git pull', script)


class TestRendimientoFase7(unittest.TestCase):
    def test_benchmark_pequeno_es_descriptivo(self):
        r = medir(5)
        self.assertEqual(r['comparacion_ab']['partidas_ejecutadas'], 10)
        self.assertEqual(r['matriz_3x3']['celdas'], 9)
        self.assertGreaterEqual(r['comparacion_ab']['segundos'], 0)
        self.assertGreaterEqual(r['matriz_3x3']['segundos'], 0)
        self.assertIn('no equivalen', r['advertencia'])

    def test_benchmark_rechaza_valores_extremos(self):
        with self.assertRaises(ValueError): medir(5000)
        with self.assertRaises(ValueError): medir(True)


class TestInterfazFase7(unittest.TestCase):
    def test_guia_rapida_y_diagnostico_en_interfaz(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit se comprueba en GitHub Actions')
        app = AppTest.from_file(str(ROOT/'laboratorio/app.py'), default_timeout=90).run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any('Versión local estabilizada' in x.value for x in app.caption))
        self.assertTrue(any('Guía rápida' in x.label for x in app.get('expander')))


if __name__ == '__main__':
    unittest.main()
