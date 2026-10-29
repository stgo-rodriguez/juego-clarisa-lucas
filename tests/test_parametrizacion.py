import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path
from simulador.economia import EconomyConfig,ScenarioConfig,scaled_int
from simulador import motor_v13_base as base
from simulador.motor import Game,run_batch,write_csv,parse_cards
from laboratorio.ejecucion import run,ROOT

CARDS=parse_cards(ROOT/'simulador/cards_v13_effects.txt')

class Parametrizacion(unittest.TestCase):
    def test_configuracion_estricta(self):
        with self.assertRaises(ValueError):EconomyConfig(perfiles_pct=49)
        with self.assertRaises(ValueError):EconomyConfig(perfiles_pct=True)
        with self.assertRaises(ValueError):EconomyConfig(juventud_pct=50)
        with self.assertRaises(ValueError):EconomyConfig.from_dict({'inventado':1})

    def test_redondeo_neutro_no_consume_rng(self):
        rng=random.Random(100)
        state=rng.getstate()
        for n in range(8):self.assertEqual(scaled_int(n,100,rng),n)
        self.assertEqual(state,rng.getstate())

    def test_redondeo_reproducible_y_sin_sesgo_obvio(self):
        def serie(seed):
            r=random.Random(seed)
            return [scaled_int(1,90,r) for _ in range(10000)]
        a=serie(1)
        self.assertEqual(a,serie(1))
        self.assertTrue(8900<sum(a)<9100)

    def test_base_igual_a_original_100_partidas(self):
        # Idéntico resumen por partida y orden de columnas sin depender de la web.
        orig,_=base.run_batch(100,6,131028,CARDS,log_samples=0)
        new,_=run_batch(100,6,131028,CARDS,log_samples=0)
        self.assertEqual(orig,new)
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'orig.csv';b=Path(d)/'new.csv';write_csv(a,orig);write_csv(b,new)
            self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_juventud_adultez_desactivados(self):
        g=Game(1,101,6,CARDS)
        p=g.players[0];p.stage='Juventud';before=p.r.copy()
        g.square_gain([p],'Juventud',1,True)
        self.assertEqual(before,p.r)
        g2=Game(1,101,6,CARDS,economia=EconomyConfig(juventud_pct=100))
        p2=g2.players[0];p2.stage='Juventud';g2.square_gain([p2],'Juventud',1,True)
        self.assertNotEqual(p2.r['K'],0)

    def test_perfil_reducido_y_carta_modificada(self):
        g=Game(1,101,6,CARDS,economia=EconomyConfig(perfiles_pct=50,cartas_ganancias_pct=50,cartas_perdidas_pct=150))
        p=g.players[0];p.stage='Juventud';p.profile=g.market.take(p.role,'tapada')
        g.produce(p,'A',4,'profile');self.assertEqual(p.r['A'],2)
        self.assertEqual(g.resource_flow['profile_A'],2)
        g.card_at(p)
        self.assertTrue(g.stats['cards'])
        self.assertTrue(g.validate())

    def test_escenario_identico_repetido(self):
        econ=EconomyConfig(perfiles_pct=90,cartas_ganancias_pct=95,cartas_perdidas_pct=110)
        a,_=run_batch(10,6,131028,CARDS,log_samples=0,economia=econ)
        b,_=run_batch(10,6,131028,CARDS,log_samples=0,economia=econ)
        self.assertEqual(a,b)
        self.assertTrue(all(r['errores']==0 for r in a))

    def test_escenario_serializa(self):
        s=ScenarioConfig.load(ROOT/'escenarios/base_v13_6j.json')
        self.assertEqual(s.economia,EconomyConfig())
        with tempfile.TemporaryDirectory() as d:
            x=run(ScenarioConfig(**{**s.__dict__,'partidas':1}),d)
            manifest=json.loads((Path(d)/'manifiesto.json').read_text())
            self.assertEqual(x['sha256'],manifest['salida_sha256'])
            self.assertEqual(manifest['escenario']['seed'],131028)

if __name__=='__main__':unittest.main()
