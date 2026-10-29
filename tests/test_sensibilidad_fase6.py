"""Validación funcional/estadística de Fase 6 (sin Streamlit salvo AppTest)."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

from laboratorio.comparacion import ejecutar, signature
from laboratorio.sensibilidad import (GridConfig, _bootstrap_media, _estadisticas_celda,
                                       ejecutar_grilla, LIMITE_PARTIDAS)
from laboratorio.archivo_sensibilidad import (exportar_grilla, importar_grilla,
                                              guardar_grilla, listar_grillas, leer_grilla)
from laboratorio.graficos_sensibilidad import mapa_sensibilidad, tabla_grilla
from simulador.economia import EconomyConfig


class TestSensibilidadFase6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = GridConfig(partidas=20, valores_x=(90,100), valores_y=(100,110),
                                remuestreos=200)
        cls.calls = []
        def runner(cfg):
            cls.calls.append(cfg.as_dict())
            return ejecutar(cfg)
        cls.grilla = ejecutar_grilla(cls.config, runner)

    def test_grilla_celdas_y_semillas_comunes(self):
        self.assertEqual(self.grilla['n_celdas'], 4)
        self.assertEqual(len(self.calls), 4) # base + 3 variantes (100/100 se reutiliza)
        self.assertTrue(all(c['seed']==self.config.seed for c in self.calls))
        self.assertTrue(all(c['partidas']==20 for c in self.calls))
        self.assertTrue(all(c['bot']==self.config.bot for c in self.calls))
        self.assertEqual(self.grilla['motor'], signature())

    def test_baseline_celda_sin_efecto_identica(self):
        cell = next(c for c in self.grilla['celdas'] if c['x']==100 and c['y']==100)
        self.assertEqual(cell['delta_rondas_observadas'],0)
        self.assertEqual(cell['delta_finalizacion_pp'],0)
        self.assertEqual(cell['ic95_rondas_observadas_inf'],0)
        self.assertEqual(cell['ic95_rondas_observadas_sup'],0)
        self.assertEqual(cell['n'],20)

    def test_reproducibilidad_bootstrap_y_grilla(self):
        self.assertEqual(self.grilla, ejecutar_grilla(self.config, ejecutar))
        self.assertEqual(_bootstrap_media([1,-3,4,5,0],200,42),
                         _bootstrap_media([1,-3,4,5,0],200,42))

    def test_dos_ejes_distintos_valores_validos(self):
        for values in [(90,90),(0,100),(49,100),(100,151)]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                GridConfig(valores_x=values)
        with self.assertRaises(ValueError):GridConfig(parametro_x='infancia_pct',parametro_y='infancia_pct')
        with self.assertRaises(ValueError):GridConfig(parametro_x='un_parametro')
        with self.assertRaises(ValueError):GridConfig(parametro_x='juventud_pct',valores_x=(90,100))
        ok=GridConfig(parametro_x='juventud_pct',valores_x=(0,100))
        self.assertEqual(ok.valores_x,(0,100))
        self.assertEqual(GridConfig.from_dict(self.config.as_dict()),self.config)

    def test_presupuesto_computacional(self):
        with self.assertRaisesRegex(ValueError,'presupuesto'):
            GridConfig(partidas=1000)
        with self.assertRaisesRegex(ValueError,'presupuesto'):
            GridConfig(partidas=120,valores_x=(80,90,100,110,120),
                       valores_y=(80,90,100,110,120))
        self.assertLessEqual((len(self.config.valores_x)*len(self.config.valores_y)+1)*self.config.partidas,LIMITE_PARTIDAS)

    def test_resultados_pareados_sin_falsa_inferencia(self):
        for cell in self.grilla['celdas']:
            self.assertEqual(cell['n'],20)
            self.assertEqual(cell['finalizadas_variante']+cell['censuradas_variante'],20)
            self.assertLessEqual(cell['ambas_finalizadas'],20)
            self.assertLessEqual(cell['ic95_rondas_observadas_inf'],cell['ic95_rondas_observadas_sup'])

    def test_censura_con_horizonte_bajo(self):
        c=GridConfig(partidas=10,max_rondas=10,
                     valores_x=(90,),valores_y=(110,),remuestreos=100)
        z=ejecutar_grilla(c, ejecutar)['celdas'][0]
        self.assertEqual(z['n'],10)
        self.assertGreater(z['censuradas_base']+z['censuradas_variante'],0)
        if z['ambas_finalizadas'] == 0:
            self.assertIsNone(z['delta_rondas_pares_concluidos'])

    def test_incertidumbre_inferior_a_cinco_pares(self):
        self.assertEqual(_bootstrap_media([1,2,3,4],100,7),(None,None))

    def test_zip_reproducible_y_roundtrip(self):
        blob=exportar_grilla(self.grilla)
        self.assertEqual(importar_grilla(blob),self.grilla)
        self.assertEqual(exportar_grilla(self.grilla),blob)
        with patch('simulador.motor.run_batch',side_effect=RuntimeError('NO EJECUTAR')):
            self.assertEqual(importar_grilla(blob)['celdas'],self.grilla['celdas'])

    def test_zip_alterado_rechazado(self):
        with ZipFile(BytesIO(exportar_grilla(self.grilla))) as z:
            files={x.filename:z.read(x.filename) for x in z.infolist()}
        files['resultados.json']=files['resultados.json'].replace(b'"n":20',b'"n":19',1)
        tmp=BytesIO()
        with ZipFile(tmp,'w',ZIP_DEFLATED) as z:
            for k,v in files.items():z.writestr(k,v)
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            importar_grilla(tmp.getvalue())
        with self.assertRaisesRegex(ValueError,'grande'):
            importar_grilla(b'z'*3_000_001)

    def test_guardar_recuperar_sin_simular(self):
        blob=exportar_grilla(self.grilla)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            a=guardar_grilla(p,blob,nombre='Matriz 90 110')
            b=guardar_grilla(p,blob,nombre='Matriz 90 110')
            self.assertEqual(a,b)
            self.assertEqual(len(listar_grillas(p)),1)
            with patch('simulador.motor.run_batch',side_effect=RuntimeError('NO')):
                self.assertEqual(leer_grilla(p,a.name),self.grilla)
            with self.assertRaises(ValueError):leer_grilla(p,'../unsafe.zip')

    def test_grafico_tablas_y_mapa(self):
        fig=mapa_sensibilidad(self.grilla)
        self.assertEqual(len(fig.data),1)
        self.assertEqual(len(fig.data[0].z),2)
        self.assertEqual(tabla_grilla(self.grilla).shape[0],4)

    def test_ejecutor_incompatible_rechazado(self):
        from laboratorio.comparacion import escenario_base
        base=ejecutar(escenario_base(6,5))
        changed=dict(base)
        changed['codigo']={**base['codigo'],'mazo_sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'Motor'):
            _estadisticas_celda(base,changed,remuestreos=100,seed_bootstrap=1)


class TestStreamlitSensibilidad(unittest.TestCase):
    def test_panel_se_visualiza_y_permite_ejecutar(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest('Streamlit disponible en GitHub Actions')
        from laboratorio.ejecucion import ROOT
        test=AppTest.from_file(str(ROOT/'laboratorio/app.py'), default_timeout=150).run()
        self.assertFalse(test.exception, str(test.exception))
        self.assertTrue(any('Sensibilidad e incertidumbre' in x.value for x in test.subheader))
        next(x for x in test.button if x.label=='Ejecutar matriz de sensibilidad').click().run(timeout=150)
        self.assertFalse(test.exception, str(test.exception))
        self.assertGreaterEqual(len(test.success), 1)


if __name__=='__main__':unittest.main()
