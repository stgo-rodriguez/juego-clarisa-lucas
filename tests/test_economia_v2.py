"""Fase 3: pruebas de recursos, reservas, proyectos, Casa y Casamiento."""
import random
import unittest
from simulador.economia_v2 import EconomyScenario, EconomyV2
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import (AdultChoice, CardPool, PendingRuleError,
                                 PlayerState, RoundEngine, SituationCard, Stage)


def players(stage=Stage.JUVENTUD, position=1):
    return [PlayerState(1,'Clarisa',stage,position),PlayerState(2,'Lucas',stage,position)]


def game(people, rules, *, adult_cards=None):
    situation_decks={(stage,role):CardPool([SituationCard(f'{stage.value}-{role}-{i}',stage,role)
                     for i in range(6)],random.Random(9),recycle=True)
                     for stage in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
                     for role in ('Clarisa','Lucas')}
    return RoundEngine(people,situation_decks,
                       CardPool(youth_cards(),random.Random(5),recycle=True),
                       CardPool(adult_cards or [MovementCard(f'A-{i}',i%6+1,(i+2)%6+1)
                                                 for i in range(20)],random.Random(3),recycle=True),
                       hooks=rules.hooks())


class TestEconomyV2(unittest.TestCase):
    def test_contabilidad_transferencias_reservas_y_saldos(self):
        ps=players()
        e=EconomyV2(ps)
        e.issue(1,'A',3,'test');e.issue(2,'A',7,'test')
        self.assertTrue(e.form_pair(*ps))
        self.assertEqual([e.accounts[i].pair_a for i in (1,2)],[5,5])
        self.assertTrue(e.audit())
        with self.assertRaises(ValueError):e.spend(1,'A',1,'ilegal')
        with self.assertRaises(ValueError):e.transfer(2,1,'A',1)

    def test_reglas_no_inventan_efectos_de_situacion(self):
        ps=players(Stage.INFANCIA)
        e=EconomyV2(ps)
        g=game(ps,e)
        g.start_round()
        with self.assertRaises(PendingRuleError):g.play_turn(1,childhood_die=2)

    def test_infancia_paso_no_duplica_casillero(self):
        ps=[PlayerState(1,'Clarisa',Stage.INFANCIA,1)]
        e=EconomyV2(ps,scenario=EconomyScenario(neutral_situations=True))
        g=game(ps,e)
        g.start_round()
        g.play_turn(1,childhood_die=4)
        self.assertEqual(e.accounts[1].free['A'],3)
        self.assertEqual(e.accounts[1].free['P'],2)
        self.assertTrue(e.audit())

    def test_juventud_caida_total_no_paso_mas_caida(self):
        ps=players(Stage.JUVENTUD,1)
        e=EconomyV2(ps,scenario=EconomyScenario(neutral_situations=True))
        g=game(ps,e)
        g.start_round()
        movement=g.players[1].youth_movement
        g.play_turn(1,youth_choice=lambda p,c,m:'A')
        expected_p=2 if movement.a==1 else sum(2 if idx==movement.a else 1
                      for idx in range(1,movement.a+1) if ((idx%6)+1) in (2,5))
        self.assertEqual(e.accounts[1].free['P'],expected_p)
        self.assertTrue(e.audit())

    def test_produccion_perfil_y_casillero_adulto(self):
        ps=players(Stage.ADULTEZ,Coord(5,3))
        e=EconomyV2(ps,scenario=EconomyScenario({'A':3,'P':2,'K':1,'M':4},True))
        e.set_profile(1,0)
        e.profile(1,'prueba_ingreso')
        self.assertEqual(e.accounts[1].free,{'A':2,'P':1,'K':2,'M':1})
        e.on_destination(None,ps[0],'M')
        self.assertEqual(e.accounts[1].free['M'],5)
        self.assertEqual(e.accounts[2].free['M'],0)

    def test_casilleros_adultos_pendientes(self):
        ps=players(Stage.ADULTEZ,Coord(2,1))
        e=EconomyV2(ps,scenario=EconomyScenario(neutral_situations=True))
        with self.assertRaises(PendingRuleError):e.on_destination(None,ps[0],'M')

    def test_inversion_por_subhito_pago_protegido(self):
        ps=players(Stage.JUVENTUD,1)
        e=EconomyV2(ps)
        e.issue(1,'K',10,'test')
        e.new_project('eng','Titulo')
        self.assertEqual(e.invest(ps[0],'eng',1,1),'eng-S1')
        with self.assertRaises(ValueError):e.invest(ps[0],'eng',1,1)
        self.assertEqual(e.invest(ps[0],'eng',1,2),'eng-S2')
        self.assertEqual(e.invest(ps[0],'eng',1,3),'eng-S3')
        self.assertEqual(e.invested['K'],6)
        self.assertEqual(e.accounts[1].free['K'],4)
        self.assertTrue(e.audit())
        self.assertTrue(e.adjudicate(ps[0],'eng',4,die=3))
        self.assertTrue(e.accounts[1].title)
        self.assertEqual(e.invested['K'],0)
        self.assertEqual(e.accounts[1].free['K'],0)
        self.assertTrue(e.audit())

    def test_fallo_adjudicacion_pierde_pago_no_inversion(self):
        ps=players(Stage.JUVENTUD,1)
        e=EconomyV2(ps)
        e.issue(1,'K',12,'test');e.new_project('eng','Titulo')
        for t in range(3):e.invest(ps[0],'eng',1,t)
        self.assertFalse(e.adjudicate(ps[0],'eng',1,die=1))
        self.assertEqual(e.invested['K'],6)
        self.assertTrue(e.projects['eng'].complete)
        self.assertFalse(e.accounts[1].title)
        e.transfer_receipt('eng-S3',1,2)
        self.assertEqual(e.receipts['eng-S3'].owner,2)

    def test_documentos_pasaporte_separados_por_personaje(self):
        ps=players(Stage.JUVENTUD,2)
        e=EconomyV2(ps)
        for i in (1,2):e.issue(i,'P',5,'test');e.issue(i,'M',2,'test')
        e.new_project('ita','Italia')
        with self.assertRaises(ValueError):e.invest(ps[1],'ita',1,1)
        for t in range(3):e.invest(ps[0],'ita',1,t)
        e.issue(1,'P',6,'test')
        self.assertTrue(e.adjudicate(ps[0],'ita',6,die=1))
        self.assertEqual(e.accounts[1].passport,'Italia')

    def test_dublin_sin_consumo_y_cobro_doble(self):
        ps=players(Stage.JUVENTUD,2)
        e=EconomyV2(ps)
        for p in ps:
            e.issue(p.id,'A',5,'test');e.issue(p.id,'K',5,'test');e.issue(p.id,'M',5,'test')
        e.form_pair(*ps)
        for p in ps:
            ac=e.accounts[p.id];ac.title=True;ac.passport='Italia' if p.role=='Clarisa' else 'Polonia'
            e.set_profile(p.id,0)
        before={i:dict(e.accounts[i].free) for i in (1,2)}
        self.assertTrue(e.enter_dublin(ps[0]))
        self.assertEqual(ps[0].stage,Stage.DUBLIN)
        self.assertEqual(e.accounts[1].free,before[1])
        e.land_from_dublin(ps[0])
        self.assertEqual(ps[0].position,Coord(5,3))
        self.assertEqual(ps[1].position,Coord(5,3))
        self.assertEqual(e.accounts[1].free['A'],2)
        self.assertEqual(e.accounts[2].free['A'],2)
        self.assertEqual(e.accounts[1].free['M'],6)
        self.assertTrue(e.audit())

    def test_compra_casa_precio_banco_y_reservas(self):
        ps=players(Stage.ADULTEZ,Coord(3,3))
        e=EconomyV2(ps)
        for p in ps:
            for r,n in {'A':13,'P':5,'M':20}.items():e.issue(p.id,r,n,'test')
        e.form_pair(*ps)
        self.assertTrue(e.buy_house(ps[0],dice=[(12,2)]))
        self.assertEqual(e.house_owner,(1,2))
        self.assertEqual(e.accounts[1].house_a,8)
        self.assertEqual(e.accounts[1].house_p,5)
        self.assertEqual(e.accounts[1].free['M'],5)
        self.assertTrue(e.audit())

    def test_compra_casa_escalada_solo_ganadora(self):
        ps=players(Stage.ADULTEZ,Coord(3,3))
        e=EconomyV2(ps)
        for p in ps:
            for r,n in {'A':13,'P':5,'M':20}.items():e.issue(p.id,r,n,'test')
        e.form_pair(*ps)
        self.assertTrue(e.buy_house(ps[0],dice=[(2,12),(12,2)],max_attempts=2))
        self.assertEqual(e.accounts[1].free['M'],0)
        self.assertEqual(e.burned['M'],40)

    def test_no_casa_desde_casillero_intermedio(self):
        ps=players(Stage.ADULTEZ,Coord(5,3))
        e=EconomyV2(ps)
        for p in ps:
            for r,n in {'A':13,'P':5,'M':15}.items():e.issue(p.id,r,n,'test')
        e.form_pair(*ps)
        with self.assertRaises(ValueError):e.buy_house(ps[0],dice=[(12,2)])

    def test_casamiento_consumo_bloqueado_por_afinidad(self):
        ps=players(Stage.ADULTEZ,Coord(3,3))
        e=EconomyV2(ps)
        for p in ps:
            for r,n in {'A':25,'P':15,'M':20}.items():e.issue(p.id,r,n,'test')
        e.form_pair(*ps)
        e.buy_house(ps[0],dice=[(12,2)])
        for p in ps:
            e.accounts[p.id].title=True
            e.accounts[p.id].passport='Italia' if p.role=='Clarisa' else 'Polonia'
        e.set_profile(1,0,affinity=0);e.set_profile(2,0,affinity=1)
        self.assertFalse(e.marriage_eligible(ps[0]))

    def test_casamiento_consume_libres_sin_tocar_reservas(self):
        ps=players(Stage.ADULTEZ,Coord(3,3))
        e=EconomyV2(ps)
        for p in ps:
            for r,n in {'A':25,'P':15,'M':20}.items():e.issue(p.id,r,n,'test')
        e.form_pair(*ps)
        self.assertTrue(e.buy_house(ps[0],dice=[(12,2)]))
        for p in ps:
            e.set_profile(p.id,0,affinity=1)
            e.accounts[p.id].title=True
            e.accounts[p.id].passport='Italia' if p.role=='Clarisa' else 'Polonia'
        self.assertTrue(e.marriage_eligible(ps[0]))
        for p in ps:
            p.position=Stage.CASAMIENTO.value;p.stage=Stage.CASAMIENTO
        self.assertTrue(e.marry(ps[0]))
        self.assertEqual(e.married,(1,2))
        self.assertEqual(e.accounts[1].pair_a,5)
        self.assertEqual(e.accounts[1].house_a,8)
        self.assertTrue(e.audit())


if __name__=='__main__':unittest.main()