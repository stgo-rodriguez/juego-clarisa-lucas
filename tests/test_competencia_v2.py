"""Regresión Fase 7: bots interactivos, subastas reales y contrafactuales."""
import random
import unittest

from simulador.agentes_v2 import AgentConfig, GameAgent
from simulador.competencia_v2 import CompetitionConfig, CompetitiveController
from simulador.economia_v2 import EconomyV2, EconomyScenario
from simulador.interacciones_v2 import AuctionCard, InteractionV2, SocialAuctionsV2
from simulador.movimiento_v2 import Coord, youth_cards
from simulador.transiciones_v2 import ProfileDecksV2
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage
from laboratorio.experimento_competencia_v2 import create_situations, run_game, compare, summarize


def fixtures(n=6, seed=1, enable=True):
    players=[PlayerState(i+1,'Clarisa' if i<=n//2 else 'Lucas',Stage.ADULTEZ,Coord(5,3))
             for i in range(n)]
    eco=EconomyV2(players,scenario=EconomyScenario(
        adult_square_amounts=dict.fromkeys('APKM',1), neutral_situations=True))
    profiles=ProfileDecksV2(seed)
    engine=RoundEngine(players,create_situations(seed),
        CardPool(youth_cards(),random.Random(seed),recycle=True),
        CardPool(youth_cards(),random.Random(seed+1),recycle=True),hooks=eco.hooks())
    agent=GameAgent(engine,eco,AgentConfig('planificador'),seed,profiles)
    inter=InteractionV2(engine,eco,profiles,rng=random.Random(seed))
    auctions=SocialAuctionsV2(eco,engine)
    controller=CompetitiveController(engine,eco,agent,inter,auctions,CompetitionConfig(enable),seed)
    return players,eco,engine,controller


class TestCompetencia(unittest.TestCase):
    def test_config_no_inventa_posicion_de_regreso(self):
        self.assertIsNone(CompetitionConfig().youth_return_pos)
        with self.assertRaises(ValueError):CompetitionConfig(youth_return_pos=7)
        with self.assertRaises(ValueError):CompetitionConfig(order_policy='arbitrario')

    def test_decks_seis_y_cartas_sinteticas_de_subasta(self):
        decks=create_situations(17)
        self.assertEqual(len(decks),6)
        for (stage,role),pile in decks.items():
            pile.assert_conservation()
            self.assertEqual(pile.available,20)
            if stage==Stage.ADULTEZ:
                self.assertEqual(sum(isinstance(x.payload,AuctionCard) for x in pile._deck),12)

    def test_sin_competencia_no_oferta_y_recompensa_al_activo(self):
        players,eco,engine,bot=fixtures(enable=False)
        for p in players:eco.issue(p.id,'M',10,'fixture')
        engine.start_round()
        card=SituationCard('test',Stage.ADULTEZ,'Clarisa',AuctionCard('test-a','A',6,4,
                          'fixed',('M',),no_bid_effect='full',reject_effect='full'))
        def forbidden(*args):raise AssertionError('no debe acudir a resolución convencional')
        bot.resolve_social_situation(engine,players[0],card,forbidden,None)
        self.assertEqual(eco.accounts[1].free['A'],6)
        self.assertEqual(bot.auctions.events[0]['reason'],'no_bids')
        self.assertEqual(sum(x['amount'] for x in eco.events if x['action']=='transfer'),0)
        eco.audit()

    def test_con_competencia_pago_al_activo_y_apropiacion_real(self):
        players,eco,engine,bot=fixtures(enable=True)
        for p in players:eco.issue(p.id,'M',10,'fixture')
        engine.start_round()
        card=SituationCard('test',Stage.ADULTEZ,'Clarisa',AuctionCard('test-a','A',6,4,
                          'fixed',('M',),no_bid_effect='full',reject_effect='full'))
        bot.resolve_social_situation(engine,players[0],card,lambda *args:None,None)
        event=bot.auctions.events[0]
        self.assertEqual(event['reason'],'awarded')
        self.assertIsNotNone(event['winner'])
        self.assertEqual(eco.accounts[1].free['A'],2)
        self.assertEqual(eco.accounts[event['winner']].free['A'],4)
        self.assertGreater(eco.accounts[1].free['M'],10)
        self.assertEqual(len(event['bids']),5)
        self.assertEqual(event['offers_considered'],5)
        self.assertEqual(bot.events[0]['event'],'subasta')
        eco.audit()

    def test_mismo_mazo_sin_alterar_cartas_por_politica(self):
        a=create_situations(81);b=create_situations(81)
        for key in a:
            self.assertEqual([(x.id,x.payload) for x in a[key]._deck],
                             [(x.id,x.payload) for x in b[key]._deck])

    def test_replay_determinista_de_partida(self):
        a=run_game(6,3,'planificador',True,max_rounds=35)
        b=run_game(6,3,'planificador',True,max_rounds=35)
        self.assertEqual(a,b)
        self.assertGreaterEqual(a['auctions'],a['auctions_awarded'])
        self.assertEqual(a['duels'],sum(a[k] for k in ('ordinary_duels','profile_duels','milestone_duels')))

    def test_sin_intervencion_no_duelos_ni_pujas(self):
        a=run_game(6,3,'planificador',False,max_rounds=35)
        self.assertEqual(a['bids'],0)
        self.assertEqual(a['duels'],0)
        self.assertEqual(a['auctions_awarded'],0)
        self.assertEqual(a['auctions'],a['auctions_no_bids'])

    def test_ambas_politicas_y_tamanos_reproducibles(self):
        rows=compare(2,30,3)
        self.assertEqual(len(rows),16)
        self.assertEqual(len(summarize(rows)),8)
        self.assertTrue(all(r['max_rounds']==30 for r in rows))
        self.assertTrue(all(r['synthetic_scenarios'] for r in rows))
        self.assertTrue(all(r['experimental_return_youth_pos'] is None for r in rows))

    def test_bot_inicia_duelo_ordinario_en_turno_real(self):
        from simulador.turnos_v2 import AdultChoice
        players,eco,engine,bot=fixtures(enable=True)
        actor,target=players[0],players[1]  # Ambos son Clarisa
        for p in players:
            eco.issue(p.id,'P',3,'fixture')
            eco.issue(p.id,'M',10 if p is actor else 15,'fixture')
        engine.start_round()
        engine.play_turn(actor.id,adult_choice=lambda p,s,h:
                         AdultChoice(h.cards[0].id,'A','N'))
        target.position=actor.position  # Encuentro explícito para este test.
        bot.after_turn(engine,actor,None)
        self.assertEqual(bot.duel_attempts,1)
        self.assertEqual(len(bot.interactions.used),1)
        bot.after_turn(engine,actor,None)
        self.assertEqual(bot.duel_attempts,1)
        eco.audit()

    def test_bot_no_selecciona_duelo_ordinario_de_distinto_rol(self):
        players,eco,engine,bot=fixtures(enable=True)
        actor,target=players[0],players[3]  # Clarisa → Lucas
        for p in players:
            eco.issue(p.id,'P',5,'fixture')
            eco.issue(p.id,'M',10 if p is actor else 15,'fixture')
        # Sin comprobante, no hay hito legítimo que disputar.
        self.assertIsNone(bot._choose_duel(actor,target))
        # Los duelos de mismo rol siguen siendo posibles si la apuesta es legal.
        self.assertEqual(bot._choose_duel(actor,players[1])[0], 'ordinario')

    def test_bot_rechaza_encuentro_de_otro_rol_aun_tras_mover(self):
        from simulador.turnos_v2 import AdultChoice
        players,eco,engine,bot=fixtures(enable=True)
        actor,target=players[0],players[3]
        for p in players:
            eco.issue(p.id,'P',5,'fixture')
            eco.issue(p.id,'M',10 if p is actor else 15,'fixture')
        engine.start_round()
        engine.play_turn(actor.id,adult_choice=lambda p,s,h:
                         AdultChoice(h.cards[0].id,'A','N'))
        target.position=actor.position
        for p in players:
            if p.role==actor.role and p.id!=actor.id:
                p.position=Coord(5,3)
        bot.after_turn(engine,actor,None)
        self.assertEqual(bot.duel_attempts,0)
        self.assertFalse(bot.interactions.used)
        self.assertFalse(bot.interactions.events)
        eco.audit()

    def test_hito_adulto_no_se_disputa_sin_punto_regreso_definido(self):
        players,eco,engine,bot=fixtures(enable=True)
        a,b=players[0],players[3]
        for p in players:
            eco.issue(p.id,'P',10,'fixture')
            eco.issue(p.id,'K',20,'fixture')
        eco.new_project('Titulo-X','Titulo')
        for i in range(3):
            eco.invest(a,'Titulo-X',1,i+1)
        project=eco.projects['Titulo-X']
        project.winner=b.id
        eco.accounts[b.id].title=True
        for rid in project.receipts:
            rec=eco.receipts[rid]
            eco.invested[rec.resource]-=rec.amount
            eco.burned[rec.resource]+=rec.amount
        self.assertNotEqual((bot._choose_duel(a,b) or ('ninguno',))[0],'hito')
        # Solo se habilita el duelo de hito una vez que existe convención expresa.
        bot.config=CompetitionConfig(enabled=True,youth_return_pos=3)
        self.assertEqual(bot._choose_duel(a,b)[0],'hito')
        eco.audit()

    def test_una_ronda_de_ofertas_y_no_puja_companero(self):
        players,eco,engine,bot=fixtures(enable=True)
        a,b=players[0],players[-1]
        eco.issue(a.id,'A',10,'fixture');eco.issue(b.id,'A',10,'fixture')
        self.assertTrue(eco.form_pair(a,b))
        for p in players:eco.issue(p.id,'M',10,'fixture')
        engine.start_round()
        card=SituationCard('test',Stage.ADULTEZ,'Clarisa',AuctionCard('test-a','A',6,4,
                          'fixed',('M',),no_bid_effect='full',reject_effect='full'))
        bot.resolve_social_situation(engine,a,card,lambda *args:None,None)
        event=bot.auctions.events[0]
        self.assertEqual(event['offers_considered'],len(players)-2)
        self.assertNotIn(a.id,[x.player_id for x in event['bids']])
        self.assertNotIn(b.id,[x.player_id for x in event['bids']])
        with self.assertRaises(ValueError):
            bot.resolve_social_situation(engine,a,card,lambda *args:None,None)
        eco.audit()


if __name__=='__main__':unittest.main()