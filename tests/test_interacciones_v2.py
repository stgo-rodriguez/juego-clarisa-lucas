"""Fase 6: tests aislados de duelos y subastas con conservación económica."""
import random
import unittest
from simulador.movimiento_v2 import Coord, MovementCard, youth_cards
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, RuleHooks, SituationCard, Stage, PendingRuleError
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.transiciones_v2 import ProfileDecksV2
from simulador.interacciones_v2 import (
    InteractionV2, AuctionCard, Bid, SocialAuctionsV2, attach_social_situations)


def game(players, scenario=True, situations=None):
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts={r:0 for r in 'APKM'},neutral_situations=scenario))
    if situations is None:
        situations={(stage,role):CardPool(
            [SituationCard(f'{stage}-{role}-{i}',stage,role) for i in range(4)],random.Random(41),recycle=True)
            for stage in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ) for role in ('Clarisa','Lucas')}
    e=RoundEngine(players,situations,
        CardPool(youth_cards(),random.Random(41),recycle=True),
        CardPool([MovementCard(f'ad-{i}',1,2) for i in range(60)],random.Random(41),recycle=True),
        hooks=eco.hooks())
    return eco,e


def after_turn_adults(e, players):
    e.start_round()
    for p in players:
        e.play_turn(p.id,adult_choice=lambda x,c,h: __import__('simulador.turnos_v2',fromlist=['AdultChoice']).AdultChoice(h.cards[0].id,'A','N' if x.position.row>1 else 'S'))


class TestDuel(unittest.TestCase):
    def make(self, kind='ordinary'):
        p=[PlayerState(1,'Clarisa',Stage.JUVENTUD,1),PlayerState(2,'Lucas' if kind=='ordinary' else 'Clarisa',Stage.JUVENTUD,1)]
        eco,e=game(p)
        profiles=ProfileDecksV2(123)
        inter=InteractionV2(e,eco,profiles,rng=random.Random(23))
        for x in p:
            for r in 'APKM':eco.issue(x.id,r,20,'fixture')
        e.start_round()
        e.play_turn(1,youth_choice=lambda x,c,m:'A')
        p[1].position=p[0].position
        e.validate()
        return p,eco,e,inter

    def test_retirada_paga_personalidad_al_defensor(self):
        p,eco,e,inter=self.make('same_role')
        before=(eco.accounts[1].free['P'],eco.accounts[2].free['P'])
        result=inter.duel(1,2,'ordinario',stake_resource='M',stake=7,
                         defender_die=6,decide=lambda d:'retirada')
        self.assertEqual((result.result,result.challenger_die),('retirada',None))
        self.assertEqual((eco.accounts[1].free['P'],eco.accounts[2].free['P']),
                         (before[0]-1,before[1]+1))
        self.assertEqual(eco.accounts[1].free['M'],20)
        eco.audit()

    def test_ordinario_entre_roles_distintos_se_rechaza_sin_efectos(self):
        p,eco,e,inter=self.make()
        p[1].role='Lucas'
        money={pid:dict(eco.accounts[pid].free) for pid in (1,2)}
        events_before=len(inter.events)
        with self.assertRaisesRegex(ValueError, 'mismo rol'):
            inter.duel(1,2,'ordinario',stake_resource='M',stake=5,
                       defender_die=2,challenger_die=6)
        self.assertEqual(money,{pid:dict(eco.accounts[pid].free) for pid in (1,2)})
        self.assertEqual(len(inter.events),events_before)
        self.assertFalse(inter.used)
        eco.audit()

    def test_ordinario_gana_y_transfiere_recurso(self):
        p,eco,e,inter=self.make('same_role')
        r=inter.duel(1,2,'ordinario',stake_resource='M',stake=5,defender_die=2,challenger_die=6)
        self.assertEqual(r.result,'victoria')
        self.assertEqual((eco.accounts[1].free['M'],eco.accounts[2].free['M']),(25,15))
        eco.audit()

    def test_ordinario_pierde_y_empate_no_transfiere(self):
        for challenger_die,expected in [(1,(16,24)),(3,(20,20))]:
            p,eco,e,inter=self.make('same_role')
            before=(eco.accounts[1].free['K'],eco.accounts[2].free['K'])
            r=inter.duel(1,2,'ordinario',stake_resource='K',stake=4,
                         defender_die=3,challenger_die=challenger_die)
            self.assertEqual((eco.accounts[1].free['K'],eco.accounts[2].free['K']),
                             (before[0]-4,before[1]+4) if challenger_die==1 else before)
            self.assertEqual(r.result,'derrota' if challenger_die==1 else 'empate')

    def test_solvente_y_una_disputa_por_turno(self):
        p,eco,e,inter=self.make('same_role')
        with self.assertRaises(ValueError):inter.duel(1,2,'ordinario',stake_resource='M',stake=21)
        self.assertFalse(inter.used)
        inter.duel(1,2,'ordinario',stake_resource='M',stake=2,defender_die=3,challenger_die=3)
        with self.assertRaises(ValueError):inter.duel(1,2,'ordinario',stake_resource='M',stake=2)

    def test_no_duelo_fuera_turno_o_sin_coincidencia(self):
        p,eco,e,inter=self.make('same_role')
        p[1].position=1 if p[0].position!=1 else 2
        with self.assertRaises(ValueError):inter.duel(1,2,'ordinario',stake_resource='M',stake=1)
        p[1].position=p[0].position
        with self.assertRaises(ValueError):inter.duel(2,1,'ordinario',stake_resource='M',stake=1)

    def test_perfil_victoria_intercambia_cartas_fisicas(self):
        p,eco,e,inter=self.make('perfil')
        inter.profiles.award_utn(eco,p[0]);inter.profiles.award_utn(eco,p[1])
        before=(inter.profiles.active[1],inter.profiles.active[2])
        result=inter.duel(1,2,'perfil',defender_die=1,challenger_die=5)
        self.assertEqual(result.result,'victoria')
        self.assertEqual((inter.profiles.active[1],inter.profiles.active[2]),before[::-1])
        self.assertEqual(eco.accounts[1].affinity,before[1].affinity)
        inter.profiles.audit();eco.audit()

    def test_perfil_derrota_no_intercambia(self):
        p,eco,e,inter=self.make('perfil')
        for q in p:inter.profiles.award_utn(eco,q)
        previous=dict(inter.profiles.active)
        r=inter.duel(1,2,'perfil',defender_die=6,challenger_die=1)
        self.assertEqual(r.result,'derrota')
        self.assertEqual(previous,inter.profiles.active)

    def make_hito(self,kind='Titulo'):
        p,eco,e,inter=self.make('hito')
        project_id='t1'
        eco.new_project(project_id,kind)
        for index in range(3):
            actor=p[index%2]
            if kind!='Titulo':
                actor.role='Lucas' if kind=='Polonia' else 'Clarisa'
            eco.invest(actor,project_id,1,index+1)
        eco.projects[project_id].winner=2
        if kind=='Titulo':eco.accounts[2].title=True
        else:eco.accounts[2].passport=kind
        # Los recursos invertidos deben cerrarse al darse el hito (equivale a adjudicación previa).
        for rid in eco.projects[project_id].receipts:
            rec=eco.receipts[rid]
            eco.invested[rec.resource]-=rec.amount;eco.burned[rec.resource]+=rec.amount
        eco.audit()
        return p,eco,e,inter

    def test_titulo_entre_roles_distintos_sigue_permitido(self):
        p,eco,e,inter=self.make_hito('Titulo')
        p[1].role='Lucas'
        result=inter.duel(1,2,'hito',project_id='t1',
                          defender_die=1,challenger_die=6)
        self.assertEqual(result.result,'victoria')
        self.assertTrue(eco.accounts[1].title)
        self.assertFalse(eco.accounts[2].title)
        self.assertEqual(eco.projects['t1'].winner,1)
        eco.audit()

    def test_disputa_titulo_victoria_transfiere_hito(self):
        p,eco,e,inter=self.make_hito()
        r=inter.duel(1,2,'hito',project_id='t1',defender_die=2,challenger_die=6)
        self.assertEqual(r.result,'victoria')
        self.assertTrue(eco.accounts[1].title)
        self.assertFalse(eco.accounts[2].title)
        self.assertEqual(eco.projects['t1'].winner,1)
        eco.audit()

    def test_disputa_titulo_derrota_quema_cinco_conocimiento(self):
        p,eco,e,inter=self.make_hito()
        before=eco.accounts[1].free['K']
        r=inter.duel(1,2,'hito',project_id='t1',defender_die=5,challenger_die=1)
        self.assertEqual((r.result,eco.accounts[1].free['K']),('derrota',before-5))
        eco.audit()

    def test_disputa_titulo_empate_sin_coste(self):
        p,eco,e,inter=self.make_hito()
        before=dict(eco.accounts[1].free)
        r=inter.duel(1,2,'hito',project_id='t1',defender_die=3,challenger_die=3)
        self.assertEqual(r.result,'empate')
        self.assertEqual(before,eco.accounts[1].free)

    def test_disputa_sin_comprobante_rechazada(self):
        p,eco,e,inter=self.make_hito()
        for receipt in eco.receipts.values():receipt.owner=2
        with self.assertRaises(ValueError):inter.duel(1,2,'hito',project_id='t1')

    def test_pasaporte_coste_personalidad_y_elegibilidad(self):
        p,eco,e,inter=self.make_hito('Italia')
        before=eco.accounts[1].free['P']
        r=inter.duel(1,2,'hito',project_id='t1',defender_die=6,challenger_die=2)
        self.assertEqual((r.result,eco.accounts[1].free['P']),('derrota',before-5))
        eco.audit()

    def test_perdida_hito_adulta_regreso_explicito(self):
        p,eco,e,inter=self.make_hito()
        for q in p:q.stage=Stage.ADULTEZ;q.position=Coord(3,3)
        # La carta juvenil del activo ya se jugó, pero el defensor no; se descarta al cambiar de etapa.
        with self.assertRaises(PendingRuleError):
            inter.duel(1,2,'hito',project_id='t1',defender_die=1,challenger_die=6)
        self.assertEqual(eco.projects['t1'].winner,2)
        r=inter.duel(1,2,'hito',project_id='t1',defender_die=1,challenger_die=6,return_youth_pos=2)
        self.assertEqual(r.result,'victoria')
        self.assertEqual((p[1].stage,p[1].position),(Stage.JUVENTUD,2))
        self.assertTrue(eco.accounts[1].title)
        e.validate()

    def test_romper_pareja_y_liberar_reserva_juvenil(self):
        p,eco,e,inter=self.make()
        p[1].position=p[0].position
        self.assertTrue(eco.form_pair(*p))
        self.assertTrue(inter.break_pair(1))
        self.assertIsNone(p[0].partner_id)
        self.assertIsNone(p[1].partner_id)
        self.assertEqual((eco.accounts[1].pair_a,eco.accounts[2].pair_a),(0,0))
        eco.audit()

    def test_perdida_reserva_con_ayuda_inmediata_no_rompe(self):
        p,eco,e,inter=self.make()
        eco.form_pair(*p)
        held=eco.accounts[1].pair_a
        self.assertTrue(inter.affect_pair_reserve(1,2))
        self.assertEqual(eco.accounts[1].pair_a,held)
        self.assertEqual(p[0].partner_id,2)
        self.assertEqual(inter.events[-1]['action'],'pair_reserve_repaired')
        eco.audit()

    def test_perdida_reserva_sin_ayuda_rompe_y_conserva_hitos(self):
        p,eco,e,inter=self.make()
        eco.form_pair(*p)
        eco.accounts[1].title=True
        for q in p:
            ac=eco.accounts[q.id]
            for r,n in list(ac.free.items()):
                if r=='A' and n:
                    eco.spend(q.id,r,n,'fixture_agotar_amor')
        self.assertFalse(inter.affect_pair_reserve(1,2))
        self.assertEqual([q.partner_id for q in p],[None,None])
        self.assertTrue(eco.accounts[1].title)
        self.assertEqual(eco.accounts[1].pair_a,0)
        eco.audit()

    def test_romper_pareja_adulta_exige_posicion_retorno(self):
        p,eco,e,inter=self.make()
        eco.form_pair(*p)
        for q in p:q.stage=Stage.ADULTEZ;q.position=Coord(3,3)
        with self.assertRaises(PendingRuleError):inter.break_pair(1)
        self.assertTrue(inter.break_pair(1,return_youth_pos=4))
        self.assertEqual((p[0].position,p[1].position),(4,4))
        self.assertIsNone(p[1].partner_id)
        eco.audit()


class TestSocialAuctions(unittest.TestCase):
    def setup(self):
        players=[PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3)),
                 PlayerState(2,'Lucas',Stage.INFANCIA,1),
                 PlayerState(3,'Clarisa',Stage.JUVENTUD,1),
                 PlayerState(4,'Lucas',Stage.ADULTEZ,Coord(2,2))]
        eco,e=game(players)
        for q in players:
            for r in 'APKM':eco.issue(q.id,r,20,'fixture')
        auction=SocialAuctionsV2(eco,e)
        return players,eco,e,auction

    def card(self,**kw):
        base=dict(id='S1',benefit_resource='A',total=6,appropriable=4,
                  mode='fixed',bid_resources=('M',),bid_order=(2,3,4),
                  no_bid_effect='full',reject_effect='full')
        base.update(kw)
        return AuctionCard(**base)

    def test_apropiacion_pago_al_activo_unica_ronda(self):
        p,eco,e,auction=self.setup()
        offered=[]
        offers={2:Bid(2,'M',2),3:Bid(3,'M',4),4:Bid(4,'M',3)}
        def offer(q,high):
            offered.append(q.id)
            return offers[q.id]
        result=auction.run(1,self.card(),bid_for=offer,select_winner=lambda best:best[0].player_id)
        self.assertEqual(offered,[2,3,4])
        self.assertEqual(result.winner,3)
        self.assertEqual(result.passed,(4,))
        self.assertEqual(result.credited_active,2)
        self.assertEqual(result.credited_winner,4)
        self.assertEqual((eco.accounts[1].free['M'],eco.accounts[3].free['M']),(24,16))
        self.assertEqual((eco.accounts[1].free['A'],eco.accounts[3].free['A']),(22,24))
        self.assertEqual(eco.accounts[2].free['M'],20)
        eco.audit()

    def test_empates_lider_activo_elige(self):
        p,eco,e,auction=self.setup()
        offers={2:Bid(2,'M',4),3:Bid(3,'M',4),4:None}
        r=auction.run(1,self.card(),bid_for=lambda q,h:offers[q.id],
                      select_winner=lambda tied: 2)
        self.assertEqual((r.winner,len(r.bids)),(2,2))

    def test_modalidad_dos_recursos_el_activo_elige_antes(self):
        p,eco,e,auction=self.setup()
        c=self.card(mode='active_choice',bid_resources=('M','K'))
        with self.assertRaises(ValueError):
            auction.run(1,c,bid_for=lambda q,h:None,select_winner=lambda b:None)
        offers={2:Bid(2,'K',2),3:None,4:None}
        r=auction.run(1,c,bid_for=lambda q,h:offers[q.id],
                      select_winner=lambda b:2,chosen_currency='K')
        self.assertEqual((r.winner,r.best_bid.resource),(2,'K'))

    def test_heterogeneo_sin_oraculo_rechaza(self):
        p,eco,e,auction=self.setup()
        c=self.card(mode='heterogeneous',bid_resources=('M','P'))
        with self.assertRaises(PendingRuleError):
            auction.run(1,c,bid_for=lambda q,h:None,select_winner=lambda b:None)
        offers={2:Bid(2,'M',4),3:Bid(3,'P',2),4:None}
        r=auction.run(1,c,bid_for=lambda q,h:offers[q.id],
                      select_winner=lambda b:3,
                      compare_heterogeneous=lambda new,old: 1 if new.resource=='P' else -1)
        self.assertEqual(r.winner,3)
        self.assertEqual((eco.accounts[1].free['P'],eco.accounts[3].free['P']),(22,18))

    def test_rechazo_condicionado_a_carta(self):
        p,eco,e,auction=self.setup()
        c=self.card(allow_reject=True,reject_effect='none')
        r=auction.run(1,c,bid_for=lambda q,h:Bid(q.id,'M',1),select_winner=lambda b:None)
        self.assertIsNone(r.winner)
        self.assertEqual((r.reason,r.credited_active),('rejected',0))
        self.assertEqual(eco.accounts[1].free['M'],20)
        p,eco,e,auction=self.setup()
        with self.assertRaises(ValueError):
            auction.run(1,self.card(),bid_for=lambda q,h:Bid(q.id,'M',1),select_winner=lambda b:None)

    def test_no_duplicar_apropiacion_para_mismo_activo_y_ronda(self):
        p,eco,e,auction=self.setup()
        card=self.card()
        kwargs=dict(bid_for=lambda q,h:None,select_winner=lambda x:None)
        auction.run(1,card,**kwargs)
        with self.assertRaises(ValueError):auction.run(1,card,**kwargs)
        self.assertEqual(eco.accounts[1].free['A'],26)

    def test_no_ofertas_fija_efecto_de_carta(self):
        p,eco,e,auction=self.setup()
        r=auction.run(1,self.card(),bid_for=lambda q,h:None,select_winner=lambda b:None)
        self.assertEqual((r.reason,r.credited_active,r.winner),('no_bids',6,None))
        self.assertEqual(eco.accounts[1].free['A'],26)

    def test_no_una_segunda_oportunidad_para_pasantes(self):
        p,eco,e,auction=self.setup()
        called=[]
        def bid(q,h):
            called.append(q.id)
            return Bid(q.id,'M',1) if q.id==2 else (Bid(q.id,'M',0) if q.id==4 else None)
        with self.assertRaises(ValueError):
            auction.run(1,self.card(),bid_for=bid,select_winner=lambda b:2)
        self.assertEqual(called,[2,3,4])

    def test_beneficio_y_reservas_no_cuentan_para_puja(self):
        p,eco,e,auction=self.setup()
        eco.accounts[2].free['M']=0
        eco.burned['M']+=20
        eco.audit()
        with self.assertRaises(ValueError):
            auction.run(1,self.card(),bid_for=lambda q,h:Bid(q.id,'M',1),select_winner=lambda b:2)
        self.assertEqual(eco.accounts[1].free['A'],20)

    def test_orden_y_efectos_no_definidos_bloquean(self):
        p,eco,e,auction=self.setup()
        with self.assertRaises(PendingRuleError):self.card(no_bid_effect='UNDEFINED')
        with self.assertRaises(PendingRuleError):
            auction.run(1,self.card(bid_order=(2,4)),bid_for=lambda q,h:None,select_winner=lambda b:None)

    def test_companero_excluido(self):
        p,eco,e,auction=self.setup()
        # Pareja adulta 1+4 en la misma coordenada.
        p[3].position=p[0].position
        eco.form_pair(p[0],p[3]); e.validate()
        c=self.card(bid_order=(2,3))
        r=auction.run(1,c,bid_for=lambda q,h:None,select_winner=lambda b:None)
        self.assertEqual(r.passed,(2,3))


class TestIntegration(unittest.TestCase):
    def test_social_shared_card_twice_with_runtime_bid_order(self):
        """La misma carta Clarisa se ejecuta dos veces con órdenes válidos distintos."""
        players=[PlayerState(1,'Clarisa',Stage.ADULTEZ,Coord(5,3)),
                 PlayerState(2,'Clarisa',Stage.ADULTEZ,Coord(5,3)),
                 PlayerState(3,'Lucas',Stage.ADULTEZ,Coord(4,3))]
        shared=AuctionCard('C-A1','A',6,4,'fixed',('M',),
                           no_bid_effect='full',reject_effect='full')
        situation={(stage,role):CardPool([
            SituationCard(f'{stage.value}-{role}-{i}',stage,role,
                          shared if stage == Stage.ADULTEZ and role == 'Clarisa' else None)
            for i in range(4)],random.Random(10),recycle=True)
            for stage in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ)
            for role in ('Clarisa','Lucas')}
        eco,e=game(players,situations=situation)
        for pid in (1,2,3):eco.issue(pid,'M',10,'fixture')
        auctions=SocialAuctionsV2(eco,e)
        e.hooks=attach_social_situations(eco.hooks(),auctions,
              bid_for=lambda bidder,high:Bid(bidder.id,'M',1),
              select_winner=lambda best:best[0].player_id,
              order_for=lambda active,card,eligible:tuple(sorted(eligible)))
        e.start_round()
        from simulador.turnos_v2 import AdultChoice
        for player in players:
            e.play_turn(player.id,adult_choice=lambda p,s,h:
                AdultChoice(h.cards[0].id,'A','N' if p.position.row>1 else 'S'))
        self.assertEqual(len(auctions.events),2)
        self.assertEqual([x['active'] for x in auctions.events],[1,2])
        self.assertEqual([x['winner'] for x in auctions.events],[2,1])
        shared_reveals=[x for x in e.events if x['action']=='situation_revealed'
                        and x['role']=='Clarisa']
        self.assertEqual(len(shared_reveals),1)
        eco.audit()

    def test_auction_runtime_order_required_if_not_given(self):
        players,eco,e,auction=TestSocialAuctions().setup()
        card=AuctionCard('x','A',6,4,'fixed',('M',),
                         no_bid_effect='full',reject_effect='none')
        with self.assertRaises(PendingRuleError):
            auction.run(1,card,bid_for=lambda q,leader:None,
                        select_winner=lambda x:None)


if __name__=='__main__':unittest.main()