"""Fase 8: sensibilidad económica con tratamientos comparables, NO mazos oficiales.

Solo modifica los premios y pérdidas de SITUACIONES sintéticas (incluidas
subastas); los ingresos por Perfil y los montos de casilleros quedan fijos.
Semillas, mazos A/B, orden inicial, perfiles y dados se conservan por
configuración. Eventos posteriores divergen naturalmente entre tratamientos.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from simulador.agentes_v2 import AgentConfig, GameAgent
from simulador.competencia_v2 import CompetitionConfig, CompetitiveController
from simulador.economia_v2 import EconomyScenario, EconomyV2, PASSPORT_KIND, RESOURCES
from simulador.interacciones_v2 import AuctionCard, InteractionV2, SocialAuctionsV2
from simulador.movimiento_v2 import youth_cards
from simulador.transiciones_v2 import ProfileDecksV2, transition_hooks
from simulador.turnos_v2 import CardPool, PlayerState, RoundEngine, SituationCard, Stage
from laboratorio.experimento_agentes_v2 import effect, adult_cards


@dataclass(frozen=True)
class StressScenario:
    id: str
    situation_yield: float
    extra_loss: int = 0
    loss_fraction: float = 0.0
    adult_square_amount: int = 2
    profile_yield: float = 1.0

    def __post_init__(self):
        if not self.id or not 0 < self.situation_yield <= 1:
            raise ValueError('Escala de Situaciones debe pertenecer a (0,1]')
        if type(self.extra_loss) is not int or self.extra_loss < 0:
            raise ValueError('Pérdida adicional inválida')
        if not 0 <= self.loss_fraction <= 1:
            raise ValueError('Fracción de pérdidas inválida')
        if type(self.adult_square_amount) is not int or self.adult_square_amount < 0:
            raise ValueError('Importe adulto de casillero inválido')
        if not 0 < self.profile_yield <= 1:
            raise ValueError('Factor de Perfil inválido')


SCENARIOS = (
    StressScenario('base_sintetica', 1.0),
    StressScenario('situaciones_menos_10', 0.90),
    StressScenario('situaciones_menos_20', 0.80),
    StressScenario('menos_20_perdidas', 0.80, extra_loss=2, loss_fraction=0.25),
    StressScenario('menos_20_perdidas_casilla1',0.80,extra_loss=2,loss_fraction=0.25,adult_square_amount=1),
    StressScenario('menos_40_perdidas_casilla1',0.60,extra_loss=2,loss_fraction=0.25,adult_square_amount=1),
    StressScenario('estres_fuerte_tres_fuentes',0.50,extra_loss=2,loss_fraction=0.25,adult_square_amount=1,profile_yield=0.50),
    StressScenario('estres_extremo_diagnostico',0.25,extra_loss=2,loss_fraction=0.25,adult_square_amount=0,profile_yield=0.25),
)


def _u01(*items: object) -> float:
    """Uniforme reproducible por clave; NO usa hash() variable de Python."""
    key='|'.join(map(str, items)).encode('utf-8')
    return int.from_bytes(hashlib.sha256(key).digest()[:8], 'big') / 2**64


def thin(amount: int, ratio: float, *key: object) -> int:
    """Reducción estocástica estable por unidad: -10% no redondea 1 a 1 siempre.

    Para una carta y semilla determinadas, bajar ratio nunca añade recursos.
    """
    if type(amount) is not int or amount < 0 or not 0 <= ratio <= 1:
        raise ValueError('Escala o importe inválido')
    return sum(_u01(*key, i) < ratio for i in range(amount))


def synthetic_decks(seed: int, scenario: StressScenario):
    decks = {}
    extra_losses = {}
    for k, (stage, role) in enumerate(
        (s, r) for s in (Stage.INFANCIA, Stage.JUVENTUD, Stage.ADULTEZ)
        for r in ('Clarisa', 'Lucas')
    ):
        cards = []
        for i in range(20):
            card_id = f'SYN-{stage.value}-{role}-{i}'
            payload = effect(stage, i)
            if stage == Stage.ADULTEZ and i % 5 in (0, 1, 2):
                mode=('fixed','heterogeneous','active_choice')[i%5]
                if mode == 'fixed':
                    resource, total, appropriable, currencies, reject, reject_effect = 'A', 6, 4, ('M',), False, 'full'
                elif mode == 'heterogeneous':
                    resource, total, appropriable, currencies, reject, reject_effect = 'M', 5, 3, ('A','P'), False, 'none'
                else:
                    resource, total, appropriable, currencies, reject, reject_effect = 'P', 5, 3, ('M','K'), True, 'full'
                adjusted_total = max(1, thin(total, scenario.situation_yield, seed,card_id,'auction-total'))
                adjusted_appropriable = min(
                    max(1,thin(appropriable,scenario.situation_yield,seed,card_id,'auction-part')),
                    adjusted_total)
                # All scales tested are >=0.8. Test value validity before creating.
                if adjusted_total < 1 or adjusted_appropriable < 1:
                    raise ValueError('Subasta experimental reducida a beneficio sin apropiación')
                payload = AuctionCard(f'AUC-{role}-{i}', resource, adjusted_total,
                    adjusted_appropriable, mode, currencies,
                    allow_reject=reject,no_bid_effect='full',reject_effect=reject_effect)
            else:
                payload = {
                    outcome: {res: thin(value,scenario.situation_yield,
                                       seed,card_id,outcome,res)
                              for res,value in values.items()}
                    for outcome,values in payload.items()
                }
            if scenario.extra_loss and _u01(seed,card_id,'loss-card') < scenario.loss_fraction:
                # Una pérdida libre por carta; se cobra a cada jugador al resolver.
                resource = 'APKM'[i % 4]
                extra_losses[card_id] = (resource, scenario.extra_loss)
            cards.append(SituationCard(card_id,stage,role,payload))
        decks[(stage,role)] = CardPool(cards,random.Random(seed+13*k),recycle=True)
    return decks, extra_losses


def progress_score(engine, eco):
    """Solo hitos/acciones durables, no flujo de recursos o beneficios pasajeros."""
    score=0
    for p in engine.players.values():
        ac=eco.accounts[p.id]
        score += (ac.title*3 + (ac.passport is not None)*3 +
                  (p.stage == Stage.ADULTEZ)*3 + (p.stage == Stage.CASAMIENTO)*5)
        score += sum(rec.owner == p.id for rec in eco.receipts.values())
    score += sum(p.partner_id is not None for p in engine.players.values())
    score += 4*(eco.house_owner is not None)
    return score


class StressEconomyV2(EconomyV2):
    """Adapta cobros de Perfil, incluida la colocación inicial desde Dublín."""

    def __init__(self, players, *, scenario, rng, stress, seed):
        super().__init__(players,scenario=scenario,rng=rng)
        self._stress=stress
        self._stress_seed=seed
        self._profile_occurrences=Counter()

    def profile(self, pid: int, reason: str):
        production=self._account(pid).profile_production
        if production is None:
            from simulador.turnos_v2 import PendingRuleError
            raise PendingRuleError('Perfil no asignado')
        event_index=self._profile_occurrences[pid]
        self._profile_occurrences[pid]+=1
        self.events.append({'action':'profile_activation', 'player':pid, 'reason':reason})
        for resource,amount in zip(RESOURCES,production):
            value=thin(amount,self._stress.profile_yield,self._stress_seed,'profile',pid,event_index,resource)
            if value:self.issue(pid,resource,value,reason)


def run_game(size: int, seed: int, policy: str, competition: bool,
             scenario: StressScenario, *, rounds: int=100, hand_size: int=3,
             with_events: bool=False) -> dict:
    if size not in (6,10) or policy not in ('planificador','aleatorio'):
        raise ValueError('Tamaño o agente inválido')
    if rounds < 1 or hand_size not in (3,4):
        raise ValueError('Rondas o mano inválidas')
    players=[PlayerState(i+1,'Clarisa' if i<size//2 else 'Lucas') for i in range(size)]
    eco=StressEconomyV2(players, scenario=EconomyScenario(
        adult_square_amounts=dict.fromkeys('APKM',scenario.adult_square_amount),neutral_situations=False),
        rng=random.Random(seed*97+14),stress=scenario,seed=seed)
    profiles=ProfileDecksV2(seed*23+14)
    hooks=transition_hooks(eco,profiles)
    decks,extra_losses=synthetic_decks(seed*37,scenario)
    engine=RoundEngine(players,decks,
        CardPool(youth_cards(),random.Random(seed*97+44),recycle=True),
        CardPool(adult_cards(),random.Random(seed*97+45),recycle=True),
        hand_size=hand_size,rng_dice=random.Random(seed*97+32),
        hooks=hooks,dublin_policy='next_turn')
    for p in players:
        eco.new_project(f'Titulo-{p.id}','Titulo')
        eco.new_project(f'{PASSPORT_KIND[p.role]}-{p.id}',PASSPORT_KIND[p.role])
    agent=GameAgent(engine,eco,AgentConfig(policy),seed*97+64,profiles)
    interactions=InteractionV2(engine,eco,profiles,rng=random.Random(seed*97+65))
    auctions=SocialAuctionsV2(eco,engine)
    controller=CompetitiveController(engine,eco,agent,interactions,auctions,
         CompetitionConfig(enabled=competition,youth_return_pos=None),seed*97+66)
    real_losses=0

    def normal_effect(e,p,card,letter):
        nonlocal real_losses
        key=letter if p.stage==Stage.JUVENTUD else 'base'
        delta=card.payload[key]
        for resource,amount in delta.items():
            if amount>0:eco.issue(p.id,resource,amount,'situacion_sintetica_estres')
            elif amount<0:
                spent=min(-amount,eco.accounts[p.id].free[resource])
                eco.spend(p.id,resource,spent,'situacion_sintetica_estres')
                real_losses+=spent

    def resolve(e,p,card,letter):
        nonlocal real_losses
        controller.resolve_social_situation(e,p,card,normal_effect,letter)
        if card.id in extra_losses:
            resource, requested=extra_losses[card.id]
            spent=min(requested,eco.accounts[p.id].free[resource])
            if spent:
                eco.spend(p.id,resource,spent,'perdida_adicional_sintetica')
                real_losses+=spent

    hooks.apply_situation=resolve
    old_after=hooks.after_turn
    def after(e,p,out):
        agent.after_turn(e,p,out)
        controller.after_turn(e,p,out)
        old_after(e,p,out)
    hooks.after_turn=after

    first_pair=None
    no_progress=0
    turns=0
    first_adult_round=None
    stop='round_limit'
    for _ in range(rounds):
        engine.start_round()
        for p in players:
            prior=progress_score(engine,eco)
            engine.play_turn(p.id,youth_choice=agent.choose_youth,
                adult_choice=agent.choose_adult,choose_utn=True,choose_dublin=True)
            turns+=1
            if progress_score(engine,eco)<=prior:
                no_progress+=1
            if first_pair is None:
                event=next((e for e in eco.events if e['action']=='pair'),None)
                if event is not None:
                    first_pair=tuple(event['players'])
            if first_adult_round is None and any(q.stage in (Stage.ADULTEZ,Stage.CASAMIENTO) for q in players):
                first_adult_round=engine.round_no
            if eco.married is not None:
                stop='marriage'
                break
        if stop=='marriage':
            break
        eco.audit()
    eco.audit()
    profiles.audit()
    engine.youth_deck.assert_conservation()
    engine.adult_deck.assert_conservation()
    for deck in engine.situation_decks.values():deck.assert_conservation()
    auction_counts=Counter(e['reason'] for e in auctions.events)
    duel_types=Counter(e['kind'] for e in interactions.events if e['action']=='duel')
    hito_events=[e for e in eco.events if e['action']=='adjudicate' and e['won']]
    result={
        'size':size,'seed':seed,'policy':policy,'competition':competition,
        'scenario':scenario.id,'situation_yield':scenario.situation_yield,
        'extra_loss':scenario.extra_loss,'loss_fraction':scenario.loss_fraction,
        'adult_square_amount':scenario.adult_square_amount,
        'profile_yield':scenario.profile_yield,
        'hand_size':hand_size,'max_rounds':rounds,'rounds':engine.round_no,
        'turns_executed':turns,'won':eco.married is not None,'stop':stop,
        'first_pair_won':first_pair is not None and eco.married == first_pair,
        'first_pair_formed':first_pair is not None,
        'first_adult_round':first_adult_round,
        'turns_without_durable_progress':no_progress,
        'no_progress_ratio':round(no_progress / turns,5) if turns else 0,
        'titles_awarded':sum(e['action']=='adjudicate' and e['won'] and e['project'].startswith('Titulo') for e in eco.events),
        'passports_awarded':sum(e['action']=='adjudicate' and e['won'] and not e['project'].startswith('Titulo') for e in eco.events),
        'final_titles':sum(ac.title for ac in eco.accounts.values()),
        'final_passports':sum(ac.passport is not None for ac in eco.accounts.values()),
        'adults_final':sum(p.stage in (Stage.ADULTEZ,Stage.CASAMIENTO) for p in players),
        'pair_formations':sum(e['action']=='pair' for e in eco.events),
        'house_purchases':sum(e['action']=='house_bought' for e in eco.events),
        'house_transfers':sum(e['action']=='house_bought' and e.get('prior') is not None for e in eco.events),
        'duels':sum(e['action']=='duel' for e in interactions.events),
        'duels_hito':duel_types['hito'],
        'duels_perfil':duel_types['perfil'],
        'duels_ordinarios':duel_types['ordinario'],
        'auctions':len(auctions.events),
        'bids':sum(len(e['bids']) for e in auctions.events),
        'auctions_awarded':auction_counts['awarded'],
        'free_resources_lost':real_losses,
        'pair_breaks':sum(e['action']=='pair_broken' for e in eco.events),
        'synthetic_scenarios':True,
    }
    if with_events:
        result['actions']=agent.actions
        result['interaction_events']=interactions.events
        result['economy_events']=eco.events
    return result


def _mean(values):
    return round(statistics.mean(values),3) if values else None


def _percentile(values, fraction: float):
    if not values: return None
    arr=sorted(values)
    ix=(len(arr)-1)*fraction
    lo=int(ix); hi=min(len(arr)-1,lo+1)
    return round(arr[lo]+(arr[hi]-arr[lo])*(ix-lo),2)


def summarize(rows):
    groups=defaultdict(list)
    for row in rows:
        groups[(row['scenario'],row['size'],row['policy'],row['competition'])].append(row)
    summary=[]
    for (scenario,size,policy,comp),group in sorted(groups.items()):
        wins=[r['rounds'] for r in group if r['won']]
        summary.append({
            'escenario':scenario,'jugadores':size,'agente':policy,'competencia':comp,
            'partidas':len(group),'casamientos':len(wins),
            'pct_casamiento':round(100*len(wins)/len(group),1),
            'rondas_promedio_con_censura':_mean([r['rounds'] for r in group]),
            'rondas_mediana_victorias':_percentile(wins,.5),
            'rondas_p90_victorias':_percentile(wins,.9),
            'frac_turnos_sin_progreso':_mean([r['no_progress_ratio'] for r in group]),
            'titulos_por_partida':_mean([r['titles_awarded'] for r in group]),
            'pasaportes_por_partida':_mean([r['passports_awarded'] for r in group]),
            'casas_por_partida':_mean([r['house_purchases'] for r in group]),
            'duelos_por_partida':_mean([r['duels'] for r in group]),
            'duelos_hito_por_partida':_mean([r['duels_hito'] for r in group]),
            'duelos_por_100_turnos':_mean([100*r['duels']/r['turns_executed'] for r in group]),
            'ofertas_por_100_turnos':_mean([100*r['bids']/r['turns_executed'] for r in group]),
            'ofertas_por_partida':_mean([r['bids'] for r in group]),
            'perdida_libre_media':_mean([r['free_resources_lost'] for r in group]),
            'primera_pareja_gana':sum(r['first_pair_won'] for r in group),
        })
    return summary


def paired_differences(rows):
    """Δ stress − base por MISMA semilla/política/competencia/tamaño."""
    index={(r['size'],r['policy'],r['competition'],r['seed'],r['scenario']):r for r in rows}
    if len(index)!=len(rows):raise ValueError('Partidas duplicadas')
    groups=defaultdict(list)
    for r in rows:
        if r['scenario']=='base_sintetica':continue
        key=(r['size'],r['policy'],r['competition'],r['seed'],'base_sintetica')
        if key not in index:raise ValueError('Falta pareja base para contrafactual')
        base=index[key]
        groups[(r['scenario'],r['size'],r['policy'],r['competition'])].append((r,base))
    out=[]
    for (scenario,size,policy,competition),pairs in sorted(groups.items()):
        delta=[s['rounds']-b['rounds'] for s,b in pairs]
        win_delta=[int(s['won'])-int(b['won']) for s,b in pairs]
        out.append({'escenario':scenario,'jugadores':size,'agente':policy,
                    'competencia':competition,'pares':len(pairs),
                    'delta_rondas_cap':_mean(delta),
                    'p90_delta_rondas_cap':_percentile(delta,.9),
                    'delta_victorias':sum(win_delta),
                    'empeoro':sum(d>0 for d in delta),
                    'mejoro':sum(d<0 for d in delta),
                    'igual':sum(d==0 for d in delta)})
    return out


def compare(seeds:int=20,rounds:int=100,hand_size:int=3,policies=('planificador',),competitions=(True,False),start_seed:int=1):
    if seeds<1 or rounds<1 or hand_size not in (3,4) or start_seed<1:
        raise ValueError('Escala de ensayo inválida')
    rows=[]
    for size in (6,10):
        for seed in range(start_seed,start_seed+seeds):
            for policy in policies:
                for competition in competitions:
                    for scenario in SCENARIOS:
                        rows.append(run_game(size,seed,policy,competition,scenario,
                                             rounds=rounds,hand_size=hand_size))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--semillas',type=int,default=20)
    parser.add_argument('--desde-semilla',type=int,default=1)
    parser.add_argument('--rondas',type=int,default=100)
    parser.add_argument('--mano',type=int,choices=(3,4),default=3)
    parser.add_argument('--ambos-agentes',action='store_true')
    parser.add_argument('--out',type=Path,default=Path('resultados/fase8'))
    args=parser.parse_args()
    policies=('aleatorio','planificador') if args.ambos_agentes else ('planificador',)
    rows=compare(args.semillas,args.rondas,args.mano,policies=policies,start_seed=args.desde_semilla)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/'partidas_sensibilidad_v2.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    report={
        'nota':'Cartas de Situación/Movimiento y valores adultos SINTÉTICOS; no es balance oficial.',
        'parametros':{'semillas':args.semillas,'desde_semilla':args.desde_semilla,'max_rounds':args.rondas,
                      'mano':args.mano,'agentes':list(policies),
                      'tratamientos':[s.__dict__ for s in SCENARIOS]},
        'partidas':len(rows),
        'resumen':summarize(rows),
        'contrafactual_apareado':paired_differences(rows),
    }
    (args.out/'resumen_sensibilidad_v2.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
