"""Pruebas de integración Fase 3 sin modificar el motor de reglas."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import gzip
import io
import json
import unittest
from zipfile import ZipFile
from pathlib import Path

from laboratorio.comparacion import (comparar, ejecutar, escenario_base,
                                     escenario_desde_dict, exportar_zip, _csv_bytes)
from laboratorio.ejecucion import ROOT, run
from laboratorio.visualizaciones import metricas_comparadas, tabla_distribucion
from simulador.economia import EconomyConfig, ScenarioConfig


class IntegracionFase3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=escenario_base(6, 20)
        cls.baseline=ejecutar(cls.config)
        cls.same=ejecutar(replace(cls.config, id='otro_nombre'))

    def test_json_reproduce_escenario(self):
        cfg=escenario_desde_dict(self.config.as_dict())
        self.assertEqual(cfg, self.config)
        with self.assertRaises(ValueError):
            escenario_desde_dict({**self.config.as_dict(),'campo_no_permitido':1})
        with self.assertRaises(ValueError):
            escenario_desde_dict({**self.config.as_dict(),'economia':{'perfiles_pct':151}})

    def test_comparacion_identica_semillas_apareadas(self):
        comparison=comparar(self.baseline,self.same)
        self.assertEqual(comparison['total'],20)
        self.assertEqual(comparison['filas_completamente_distintas'],0)
        self.assertEqual(comparison['variaron_rondas_o_estado'],0)
        self.assertEqual(comparison['delta_mediana_rondas_apareadas'],0)
        self.assertTrue(comparison['semillas_apareadas'])

    def test_rechaza_mesas_y_semillas_distintas(self):
        config_other=replace(self.config, seed=99999)
        modified={'escenario':config_other.as_dict(),'filas':self.same['filas']}
        with self.assertRaisesRegex(ValueError,'seed'):
            comparar(self.baseline,modified)
        rows=[dict(row) for row in self.same['filas']]
        rows[0]['semilla']+=1
        with self.assertRaisesRegex(ValueError,'semillas'):
            comparar(self.baseline,{'escenario':self.same['escenario'],'filas':rows})

    def test_censura_no_confundida_con_casamiento(self):
        a={'escenario':self.baseline['escenario'],
           'filas':[dict(x) for x in self.baseline['filas']]}
        b={'escenario':self.same['escenario'],
           'filas':[dict(x) for x in self.same['filas']]}
        b['filas'][0]['terminada']=0
        stats=comparar(a,b)
        self.assertEqual(stats['ambas_finalizadas'],19)
        self.assertEqual(stats['alguna_censurada'],1)
        self.assertIn('censuradas',stats['advertencia_censura'])

    def test_exportaciones_con_huella_y_config(self):
        result=comparar(self.baseline,self.same)
        payload=exportar_zip(self.baseline,self.same,result)
        with ZipFile(io.BytesIO(payload)) as archive:
            manifest=json.loads(archive.read('manifiesto.json'))
            self.assertEqual(archive.read('base/resultados.csv'),_csv_bytes(self.baseline['filas']))
            self.assertEqual(manifest['archivos']['base/resultados.csv'],
                             sha256(archive.read('base/resultados.csv')).hexdigest())
            self.assertEqual(json.loads(archive.read('variante/escenario.json'))['seed'],self.config.seed)
            self.assertEqual(json.loads(archive.read('comparacion.json'))['ambas_finalizadas'],20)

    def test_visualizaciones_correctamente_etiquetadas(self):
        frame=metricas_comparadas(self.baseline,self.same)
        self.assertEqual(frame.shape[0],2)
        self.assertEqual(list(frame['Escenario']),['Base','Experimento'])
        chart=tabla_distribucion(self.baseline,self.same)
        self.assertEqual(len(chart.data),2)
        for trace in chart.data:
            self.assertEqual(len(trace.x),self.config.partidas)

    def test_servicio_usa_el_mismo_motor_que_cli(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cli=run(self.config,d)
            self.assertEqual(Path(cli['csv']).read_bytes(),_csv_bytes(self.baseline['filas']))


class TestStreamlitSmoke(unittest.TestCase):
    """Se ejecuta en GitHub Actions con Streamlit instalado; localmente puede omitirse."""
    def test_app_render_y_ejecucion(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit no disponible en este intérprete')
        test=AppTest.from_file(str(ROOT/'laboratorio/app.py'),default_timeout=120).run()
        self.assertFalse(test.exception, f"Error inicial de interfaz: {test.exception}")
        self.assertTrue(any('Laboratorio de Balance' in t.value for t in test.title))
        # El botón pertenece a un formulario; las opciones predeterminadas son estables.
        self.assertTrue(len(test.button)>0)
        test.button[0].click().run(timeout=120)
        self.assertFalse(test.exception, f"Error al simular: {test.exception}")
        self.assertTrue(any('Resultados de la última ejecución' in x.value for x in test.subheader))
        self.assertGreaterEqual(len(test.metric),3)


if __name__ == '__main__':
    unittest.main()
