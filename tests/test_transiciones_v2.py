"""Fase 4: transiciones físicas y económicas UTN → Juventud → Dublín → Adultez."""
import random
import unittest
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import (AdultChoice, CardPool, PlayerState, RoundEngine,
                                 SituationCard, Stage, PendingRuleError)
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.transiciones_v2 import ProfileDecksV2,transition_hooks


def build(players,*,seed=33):
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts={'A':1,'P':1,'K':1,'M':1},neutral_situations=True),
        rng=random.Random(seed))
    profiles=ProfileDecksV2(seed)
    deck={ (stage,role):CardPool(
        [SituationCard(f'{stage.value}:{role}:{i}',stage,role) for i in range(20)],
        random.Random(seed+i),recycle=True)
        for i,(stage,role) in enumerate((s,r) for s in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
                                          for r in ('Clarisa','Lucas')) }
    adult_cards=[MovementCard(f'ADULT-{i}',i%6+1,(i+2)%6+1) for i in range(100)]
    engine=RoundEngine(players,deck,
       CardPool(youth_cards(),random.Random(seed+8),recycle=True),
       CardPool(adult_cards,random.Random(seed+9),recycle=True),
       hooks=transition_hooks(eco,profiles))
    return engine,eco,profiles


class TestUTN(unittest.TestCase):
    def test_bifurcacion_utn_cobra_2p_antes_de_requisito_y_descarta_pasos(self):
        p=PlayerState(1,'Clarisa',Stage.INFANCIA,4)
        g,eco,profiles=build([p])
        eco.issue(1,'K',1,'fixture')
        g.start_round()
        out=g.play_turn(1,childhood_die=4,utn_die=6,choose_utn=True)
        self.assertEqual(out.target,Stage.UTN.value)
        self.assertEqual(p.position,Stage.UTN.value)
        self.assertTrue(p.utn_passed)
        self.assertEqual(eco.accounts[1].free['P'],2)
        self.assertEqual(eco.accounts[1].free['K'],1)
        self.assertEqual([e['discarded'] for e in g.events if e['action']=='enter_utn'],[3])
        self.assertEqual(len(profiles.active),1)
        g.start_round()
        self.assertEqual((p.stage,p.position),(Stage.JUVENTUD,1))
        self.assertIsNotNone(p.youth_movement)
        self.assertIn((Stage.JUVENTUD,'Clarisa'),g._revealed)

    def test_sin_k_no_ingresa_utn_y_sigue_circuito(self):
        p=PlayerState(1,'Lucas',Stage.INFANCIA,4)
        g,eco,profiles=build([p])
        g.start_round()
        out=g.play_turn(1,childhood_die=3,utn_die=6,choose_utn=True)
        self.assertEqual((p.stage,p.position),(Stage.INFANCIA,1))
        self.assertEqual(out.target,'casillero_infancia')
        self.assertEqual(eco.accounts[1].free['P'],2)
        self.assertFalse(p.utn_passed)
        self.assertEqual(len(profiles.active),0)

    def test_utn_desaprobado_reintenta_sin_situacion_ni_movimiento(self):
        p=PlayerState(1,'Lucas',Stage.INFANCIA,4)
        g,eco,profiles=build([p]);eco.issue(1,'K',1,'fixture')
        g.start_round()
        out=g.play_turn(1,childhood_die=2,utn_die=2,choose_utn=True)
        self.assertFalse(p.utn_passed)
        self.assertEqual(p.stage,Stage.UTN)
        initial=sum(e['action']=='situation_resolved' for e in g.events)
        g.start_round()
        attempt=g.play_turn(1,utn_die=6)
        self.assertEqual(attempt.situation_id,None)
        self.assertEqual(initial,sum(e['action']=='situation_resolved' for e in g.events))
        self.assertTrue(p.utn_passed)
        self.assertEqual((p.stage,p.position),(Stage.UTN,Stage.UTN.value))
        g.start_round()
        self.assertEqual(p.stage,Stage.JUVENTUD)
        self.assertEqual(len(profiles.active),1)
        self.assertEqual(eco.accounts[1].free['K'],1)

    def test_no_se_asigna_dos_veces_y_barajas_distintas(self):
        players=[PlayerState(i+1,'Clarisa' if i<5 else 'Lucas') for i in range(10)]
        g,eco,profiles=build(players)
        for p in players:
            card=profiles.award_utn(eco,p)
            self.assertEqual(card.role,p.role)
            self.assertEqual(eco.accounts[p.id].affinity,card.affinity)
        self.assertEqual(len({card.id for card in profiles.active.values()}),10)
        for p in players:
            self.assertEqual(eco.accounts[p.id].profile_production,
                __import__('simulador.economia_v2',fromlist=['PROFILE_PRODUCTIONS'])
                .PROFILE_PRODUCTIONS[p.role][profiles.active[p.id].tier])
        with self.assertRaises(ValueError):profiles.award_utn(eco,players[0])
        profiles.audit()

    def test_utn_sin_credito_de_perfil_sigue_bloqueada(self):
        p=PlayerState(1,'Clarisa',Stage.UTN,Stage.UTN.value)
        g,eco,profiles=build([p])
        g.hooks.utn_pass=None
        g.start_round()
        with self.assertRaises(PendingRuleError):g.play_turn(1,utn_die=6)
        self.assertEqual(len(g._played),0)


class TestDublin(unittest.TestCase):
    def _ready_couple(self):
        a=PlayerState(1,'Clarisa',Stage.JUVENTUD,1)
        b=PlayerState(2,'Lucas',Stage.JUVENTUD,1)
        g,eco,profiles=build([a,b])
        for p in (a,b):
            profiles.award_utn(eco,p)
            ac=eco.accounts[p.id]
            ac.title=True
            ac.passport='Italia' if p.role=='Clarisa' else 'Polonia'
            for r,n in {'A':5,'K':5,'M':5}.items():eco.issue(p.id,r,n,'fixture_hitos')
        self.assertTrue(eco.form_pair(a,b))
        eco.audit()
        return g,eco,profiles

    def test_llegada_exacta_tramite_y_siguiente_ronda_adulta(self):
        g,eco,profiles=self._ready_couple()
        a,b=g.players[1],g.players[2]
        g.start_round()
        # Ajustar la posición compartida para que A caiga exactamente en Trámite #2.
        distance=a.youth_movement.a
        origin=(2-distance-1)%6+1
        a.position=b.position=origin
        old_cash={p.id:dict(eco.accounts[p.id].free) for p in (a,b)}
        out=g.play_turn(1,youth_choice=lambda p,c,m:'A',choose_dublin=True)
        self.assertEqual(out.target,Stage.DUBLIN.value)
        self.assertEqual((a.stage,b.stage),(Stage.DUBLIN,Stage.DUBLIN))
        self.assertEqual((a.position,b.position),(Stage.DUBLIN.value,Stage.DUBLIN.value))
        for p in (a,b):
            self.assertGreaterEqual(eco.accounts[p.id].free['K'],old_cash[p.id]['K'])
            self.assertGreaterEqual(eco.accounts[p.id].free['M'],old_cash[p.id]['M'])
        remaining=g.play_turn(2)
        self.assertIsNone(remaining.movement_card_id)
        self.assertTrue(any(e['action']=='dublin_wait_experimental' for e in g.events))
        before={p.id:dict(eco.accounts[p.id].free) for p in (a,b)}
        g.start_round()
        self.assertEqual((a.stage,b.stage),(Stage.ADULTEZ,Stage.ADULTEZ))
        self.assertEqual((a.position,b.position),(Coord(5,3),Coord(5,3)))
        for p in (a,b):
            prod=eco.accounts[p.id].profile_production
            self.assertEqual(tuple(eco.accounts[p.id].free[r]-before[p.id][r]
                                   for r in ('A','P','K','M')),prod)
        self.assertEqual(sum(e['action']=='dublin_to_adult' for e in g.events),1)
        self.assertEqual(sum(e['action']=='situation_revealed' and e['stage']==Stage.ADULTEZ.value
                             for e in g.events),2)
        self.assertTrue(a.hand.exhausted and b.hand.exhausted)
        g.play_turn(1,adult_choice=lambda p,s,h:AdultChoice(h.cards[0].id,'A','N'))
        self.assertEqual(len(a.hand.cards),2)
        self.assertTrue(b.hand.exhausted)
        eco.audit()

    def test_requisito_individual_faltante_bloquea_dublin(self):
        g,eco,_=self._ready_couple()
        a,b=g.players[1],g.players[2]
        eco.accounts[2].passport=None  # Un hito faltante no puede recuperarse mediante producción.
        g.start_round()
        distance=a.youth_movement.a
        a.position=b.position=(2-distance-1)%6+1
        out=g.play_turn(1,youth_choice=lambda p,c,m:'A',choose_dublin=True)
        self.assertEqual(out.target,'Tramite')
        self.assertEqual(a.stage,Stage.JUVENTUD)
        self.assertEqual(b.stage,Stage.JUVENTUD)

    def test_no_se_paga_ni_se_reserva_por_dublin(self):
        g,eco,_=self._ready_couple();a=g.players[1];b=g.players[2]
        a.position=b.position=2
        free={pid:dict(eco.accounts[pid].free) for pid in (1,2)}
        self.assertTrue(eco.enter_dublin(a))
        for pid in (1,2):
            self.assertEqual(eco.accounts[pid].free,free[pid])
        eco.audit()

    def test_pareja_no_puede_tener_otra_actividad_antes_de_llegar(self):
        g,eco,_=self._ready_couple()
        a,b=g.players[1],g.players[2]
        self.assertEqual((a.stage,b.stage),(Stage.JUVENTUD,Stage.JUVENTUD))
        with self.assertRaises(ValueError):eco.land_from_dublin(a)


if __name__=='__main__':unittest.main()

class TestDublinPolicies(unittest.TestCase):
    def test_siguiente_turno_propio_sin_espera_y_revela_adultez_a_mitad_ronda(self):
        g,eco,_=TestDublin()._ready_couple()
        g.dublin_policy='next_turn'
        a,b=g.players[1],g.players[2]
        g.start_round()
        a.position=b.position=(2-a.youth_movement.a-1)%6+1
        original=g.play_turn(1,youth_choice=lambda p,s,m:'A',choose_dublin=True)
        self.assertEqual(original.target,Stage.DUBLIN.value)
        self.assertEqual(b.stage,Stage.DUBLIN)
        out=g.play_turn(2,adult_choice=lambda p,s,h:AdultChoice(h.cards[0].id,'A','N'))
        self.assertEqual(out.situation_id,g._revealed[(Stage.ADULTEZ,'Lucas')].id)
        self.assertEqual((a.stage,b.stage),(Stage.ADULTEZ,Stage.ADULTEZ))
        self.assertEqual(sum(e['action']=='dublin_wait_experimental' for e in g.events),0)
        self.assertEqual(sum(e['action']=='dublin_to_adult' for e in g.events),1)
        self.assertEqual(len(b.hand.cards),2)
        self.assertTrue(a.hand.exhausted)
        eco.audit()

    def test_individual_km_no_se_prestan_automaticamente(self):
        g,eco,_=TestDublin()._ready_couple()
        a,b=g.players[1],g.players[2]
        a.position=b.position=2
        # Hay 10 M combinados, pero el activo tiene 9 y el acompañante 1.
        eco.transfer(2,1,'M',4)
        before=(dict(eco.accounts[1].free),dict(eco.accounts[2].free))
        self.assertFalse(eco.enter_dublin(a))
        self.assertEqual(before,(eco.accounts[1].free,eco.accounts[2].free))
        eco.transfer(1,2,'M',4)
        self.assertTrue(eco.enter_dublin(a))
        eco.audit()

    def test_politica_fuera_de_catalogo_es_error(self):
        g,eco,_=TestDublin()._ready_couple()
        with self.assertRaises(ValueError):
            RoundEngine(list(g.players.values()),g.situation_decks,g.youth_deck,
                        g.adult_deck,hooks=g.hooks,dublin_policy='automatico')

class TestSharedAdultMidround(unittest.TestCase):
    def test_lucas_entrante_comparten_situacion_adulta_con_lucas_preexistente(self):
        c=PlayerState(1,'Clarisa',Stage.JUVENTUD,1,partner_id=2)
        existing=PlayerState(3,'Lucas',Stage.ADULTEZ,Coord(5,3))
        l=PlayerState(2,'Lucas',Stage.JUVENTUD,1,partner_id=1)
        # Orden global intencional: Clarisa, Lucas adulto, Lucas que llega.
        g,eco,profiles=build([c,existing,l])
        for p in (c,l):
            profiles.award_utn(eco,p)
            ac=eco.accounts[p.id]
            ac.title=True
            ac.passport='Italia' if p.role=='Clarisa' else 'Polonia'
            for r,n in {'A':5,'K':5,'M':5}.items():eco.issue(p.id,r,n,'fixture')
            eco.accounts[p.id].pair_a=5
            eco.accounts[p.id].free['A']-=5
        eco.audit()
        g.dublin_policy='next_turn'
        g.start_round()
        adult_lucas_situation=g._revealed[(Stage.ADULTEZ,'Lucas')].id
        c.position=l.position=(2-c.youth_movement.a-1)%6+1
        g.play_turn(1,youth_choice=lambda p,s,m:'A',choose_dublin=True)
        out_existing=g.play_turn(3,adult_choice=lambda p,s,h:AdultChoice(h.cards[0].id,'A','N'))
        out_new=g.play_turn(2,adult_choice=lambda p,s,h:AdultChoice(h.cards[0].id,'A','N'))
        self.assertEqual(out_existing.situation_id,adult_lucas_situation)
        self.assertEqual(out_new.situation_id,adult_lucas_situation)
        reveals=[e for e in g.events if e['action']=='situation_revealed'
                 and e['stage']==Stage.ADULTEZ.value and e['role']=='Lucas']
        self.assertEqual(len(reveals),1)
        eco.audit()