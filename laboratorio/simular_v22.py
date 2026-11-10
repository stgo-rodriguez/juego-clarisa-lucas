"""Monte Carlo v2.2: situaciones vigentes, casilleros juveniles/adultos sin premios.

Seis mazos barajados individualmente, por rol y etapa; no cambia las versiones
previas ni mezcla el catálogo histórico. Reglas económicas y perfil restantes:
supuestos experimentales del simulador v2.0. No son reglas aprobadas.
"""
from __future__ import annotations
import argparse,csv,json,hashlib,random,statistics
from collections import Counter,defaultdict
from pathlib import Path

from simulador.agentes_v2 import AgentConfig
from simulador.experimento_politicas_v22 import (
    EconomyBankV22, RoundEngineAuditV22, CurrentResolverPoliciesV22,
    AgentRosterV22, SIMLogAuditV22, assign_policies,
)
from simulador.competencia_v2 import CompetitionConfig,CompetitiveController
from simulador.economia_v2 import EconomyScenario,EconomyV2,PASSPORT_KIND
from simulador.interacciones_v2 import InteractionV2,SocialAuctionsV2
from simulador.movimiento_v2 import youth_cards
from simulador.mazos_vigentes_v2 import CurrentResolver,new_decks,load_current
from simulador.afinidad_v2 import zone
from simulador.simlog_v22 import SIMLogV22
from simulador.reglas_v21 import transition_hooks_v21, CurrentResolverV21
from simulador.reglas_v22 import EconomyV22, RoundEngineV22
from simulador.transiciones_v2 import ProfileDecksV2,transition_hooks
from simulador.turnos_v2 import CardPool,PlayerState,RoundEngine,SituationCard,Stage
from laboratorio.experimento_agentes_v2 import adult_cards
from laboratorio.sensibilidad_v2 import progress_score
from simulador.mazos_propuestos_v2 import BalanceVariant
from simulador.turnos_v2 import PendingRuleError


def write_rows(file,rows):
    file=Path(file);file.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    with file.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)

def run_game(size,seed,round_limit=100,competition=True,trace_dir=None,catalog=None,policy='planificador',affinity_weight=8.0,hand_size=3,bank_enabled=True):
    if size not in (6,10):raise ValueError(size)
    catalog=catalog or load_current()
    players=[PlayerState(i+1,'Clarisa' if i<size//2 else 'Lucas') for i in range(size)]
    policies=assign_policies(players,policy,seed)
    eco=EconomyBankV22(players,scenario=EconomyScenario(adult_square_amounts=None,neutral_situations=False),rng=random.Random(seed*97+14))
    eco.dynamic_affinity={p.id:0 for p in players}
    profiles=ProfileDecksV2(seed*23+14)
    hooks=transition_hooks_v21(eco,profiles)
    decks=new_decks(catalog,seed*37)
    shuffled={f'{stage.value}_{role}':[c.id for c in d._deck[::-1]] for (stage,role),d in decks.items()}
    engine=RoundEngineAuditV22(players,decks,CardPool(youth_cards(),random.Random(seed*97+44),recycle=True),
         CardPool(adult_cards(),random.Random(seed*97+45),recycle=True),
         hand_size=hand_size,rng_dice=random.Random(seed*97+32),hooks=hooks,dublin_policy='next_round')
    for p in players:
        eco.new_project(f'Titulo-{p.id}','Titulo')
        eco.new_project(f'{PASSPORT_KIND[p.role]}-{p.id}',PASSPORT_KIND[p.role])
    agent=AgentRosterV22(engine,eco,policies,seed*97+64,profiles)
    interactions=InteractionV2(engine,eco,profiles,rng=random.Random(seed*97+65))
    auctions=SocialAuctionsV2(eco,engine)
    controller=CompetitiveController(engine,eco,agent,interactions,auctions,
         CompetitionConfig(enabled=competition,youth_return_pos=None),seed*97+66)
    resolver=CurrentResolverPoliciesV22(eco,interactions,policies,seed*97+99,affinity_weight)
    hooks.apply_situation=resolver.resolve
    prev=hooks.after_turn
    bank_rng={p.id:random.Random(seed*4507+p.id*137+11) for p in players}
    def after(e,p,out):
        agent.after_turn(e,p,out)
        controller.after_turn(e,p,out)
        prev(e,p,out)
        if bank_enabled and p.stage != Stage.CASAMIENTO:
            decision=eco.choose_conversion(p,policies[p.id],e.round_no,bank_rng[p.id])
            if decision is not None:
                eco.convert(p.id,*decision,round_no=e.round_no)
    hooks.after_turn=after
    def youth(p,situation,movement):
        proxy=SituationCard(situation.id,Stage.JUVENTUD,p.role,situation.payload['effects'])
        return agent.choose_youth(p,proxy,movement)
    logger=None
    if trace_dir is not None:
        logger=SIMLogAuditV22(engine,eco,profiles,resolver,interactions,auctions,controller,
            run_id=f'simlog_v22_econaudit_{size}p_s{seed}_{policy}_h{hand_size}_b{int(bank_enabled)}',
            seed=seed,policy=policy,competition=competition,round_limit=round_limit,
            catalog=catalog,balance=BalanceVariant(),
            policy_by_player=policies,hand_size=hand_size,bank_enabled=bank_enabled)
        logger.new_sources=catalog['sources'];logger.attach_hooks(hooks)
    rounds=0;turns=0;no_progress=0;stop='round_limit'
    blocked_reason=None
    blocked_player=None
    for _ in range(round_limit):
        try:
            if logger:logger.begin_round()
            engine.start_round()
            if logger:logger.end_round_start()
            for p in players:
                before=progress_score(engine,eco)
                if logger:logger.begin_turn(p.id)
                outcome=engine.play_turn(p.id,
                    youth_choice=logger.wrap_youth_choice(youth) if logger else youth,
                    adult_choice=logger.wrap_adult_choice(agent.choose_adult) if logger else agent.choose_adult,
                    choose_utn=True,choose_dublin=True)
                if logger:logger.end_turn(outcome)
                turns+=1
                if progress_score(engine,eco)<=before:no_progress+=1
                if eco.married is not None:
                    stop='marriage'
                    break
            if logger:logger.end_round(ended=stop=='marriage')
            if stop=='marriage':
                break
        except PendingRuleError as exc:
            blocked_reason=str(exc)
            blocked_player=p.id if 'p' in locals() else None
            stop='rule_pending'
            break
    eco.audit();profiles.audit()
    for d in engine.situation_decks.values():d.assert_conservation()
    engine.youth_deck.assert_conservation();engine.adult_deck.assert_conservation()
    decisions=Counter((p['stage'],p['result']) for p in resolver.events)
    pair=eco.married
    pair_final=(list(pair) if pair else None)
    pair_zone=zone(eco.dynamic_affinity[pair[0]]) if pair else None
    if pair and zone(eco.dynamic_affinity[pair[1]])!=pair_zone:raise AssertionError('Casamiento incompatible')
    result={'size':size,'seed':seed,'policy':policy,'policies_by_player':json.dumps(policies,sort_keys=True),
            'hand_size':hand_size,'bank_enabled':bank_enabled,
            'bank_conversions':sum(e['action']=='conversion_bancaria' for e in eco.events),
            'competition':competition,
            'rounds':engine.round_no,'turns':turns,'won':pair is not None,'stop':stop,
            'blocked_reason':blocked_reason,'blocked_player':blocked_player,
            'winning_pair':json.dumps(pair_final),'winning_zone':pair_zone,
            'no_progress_ratio':round(no_progress/turns,5) if turns else 0,
            'situations_resolved':len(resolver.events),
            'choices_A':sum(v for (stage,choice),v in decisions.items() if choice=='A'),
            'choices_B':sum(v for (stage,choice),v in decisions.items() if choice=='B'),
            'adult_auctions':len(auctions.events),'duels':sum(ev.get('action')=='duel' for ev in interactions.events),
            'affinity_final_positions':json.dumps(eco.dynamic_affinity,sort_keys=True),
            'affinity_final_zones':json.dumps({pid:zone(pos) for pid,pos in eco.dynamic_affinity.items()},sort_keys=True),
            'shuffled_decks_sha256':hashlib.sha256(json.dumps(shuffled,sort_keys=True).encode()).hexdigest()}
    if logger and stop!='rule_pending':
        logger.write(trace_dir,status=stop,summary=result)
        (Path(trace_dir)/'orden_mazos.json').write_text(json.dumps(shuffled,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    elif trace_dir is not None and stop=='rule_pending':
        Path(trace_dir).mkdir(parents=True,exist_ok=True)
        (Path(trace_dir)/'bloqueo_reglamentario.json').write_text(
            json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        # Únicamente turnos previamente cerrados: sin manifiesto ni eventos
        # del turno que fue interrumpido. No se exponen como partida completa.
        if logger and logger.turns:
            write_rows(Path(trace_dir)/'turnos_completados.csv',logger.turns)
    return result


def execute(out:Path,seeds:int=20,sizes=(6,10),round_limit=100,competition=True,affinity_weight=8.,policy='planificador',start_seed=1,hand_size=3,bank_enabled=True):
    catalog=load_current()
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for n in sizes:
        for seed in range(start_seed,start_seed+seeds):
            sub=out/'trazas'/f'n{n}_s{seed}'
            x=run_game(n,seed,round_limit,competition,sub,catalog,policy,affinity_weight,hand_size,bank_enabled)
            rows.append(x)
            if seed==start_seed or seed%10==0:
                print(f'n={n}, semilla={seed}/{seeds}, rondas={x["rounds"]}, ganó={x["won"]}',flush=True)
    write_rows(out/'partidas.csv',rows)
    # Preferencias agregadas SEPARADAS por carta y rol, derivadas del SIMLOG persistido.
    preference=defaultdict(lambda:Counter())
    affine=defaultdict(Counter)
    group_choices=defaultdict(Counter)
    group_contexts=defaultdict(set)
    assigned_cards={}
    for x in rows:
        root=out/'trazas'/f'n{x["size"]}_s{x["seed"]}'
        turn_file=root/'turnos.csv'
        if not turn_file.is_file():
            if x['stop']!='rule_pending':
                raise AssertionError('Falta traza de una partida no bloqueada')
            turn_file=root/'turnos_completados.csv'
            if not turn_file.is_file():
                continue
        with turn_file.open(newline='',encoding='utf-8-sig') as f:
            for t in csv.DictReader(f):
                stage=t['Etapa_situacion'];role=t['Rol'];card=t['Carta_ID'];choice=t['Desenlace_elegido']
                if card and choice in ('A','B'):
                    preference[(stage,role,card)][choice]+=1
                    affine[(stage,role)][choice]+=1
                    group_key=(x['size'],x['seed'],int(t['Ronda']),
                               t['Situacion_grupo_etapa'],t['Situacion_grupo_rol'])
                    previous=assigned_cards.setdefault(group_key,card)
                    if previous!=card:
                        raise AssertionError('Grupo etapa/rol/ronda con dos Situaciones')
                    group_choices[group_key][choice]+=1
                    if t['Recursos_antes_AB_JSON']:
                        group_contexts[group_key].add(t['Recursos_antes_AB_JSON'])
    prefs=[]
    for (stage,role,card),c in sorted(preference.items()):
        total=c['A']+c['B']
        prefs.append({'etapa':stage,'rol':role,'carta':card,'n':total,'A':c['A'],'B':c['B'],
                      'porcentaje_A':round(c['A']/total*100,2),
                      'dominancia_porcentaje':round(max(c['A'],c['B'])/total*100,2)})
    write_rows(out/'preferencias_por_carta.csv',prefs)
    groups=[]
    for (size,seed,round_no,stage,role),choices in sorted(group_choices.items()):
        a,b=choices['A'],choices['B']
        groups.append({'size':size,'seed':seed,'ronda':round_no,
                       'etapa':stage,'rol':role,
                       'carta':assigned_cards[(size,seed,round_no,stage,role)],
                       'participantes':a+b,'A':a,'B':b,
                       'ambas_opciones':int(a>0 and b>0),
                       'contextos_economicos_distintos':len(group_contexts[(size,seed,round_no,stage,role)]),
                       'recursos_diversos':int(len(group_contexts[(size,seed,round_no,stage,role)])>1)})
    write_rows(out/'diversidad_decisiones_por_grupo.csv',groups)
    bygroup=[]
    for key,cs in sorted(affine.items()):
        bygroup.append({'etapa':key[0],'rol':key[1],'A':cs['A'],'B':cs['B'],
                        'porcentaje_A':round(100*cs['A']/(cs['A']+cs['B']),2)})
    write_rows(out/'preferencias_por_etapa_rol.csv',bygroup)
    zones=Counter(x['winning_zone'] for x in rows if x['won'])
    aggregated=[]
    for n in sizes:
        subset=[x for x in rows if x['size']==n]
        aggregated.append({'size':n,'games':len(subset),'wins':sum(x['won'] for x in subset),
            'win_rate':round(sum(x['won'] for x in subset)/len(subset)*100,2),
            'avg_rounds_censored':round(statistics.mean(x['rounds'] for x in subset),2),
            'median_rounds_censored':statistics.median(x['rounds'] for x in subset),
            'avg_turns_censored':round(statistics.mean(x['turns'] for x in subset),2)})
    first=[g for g in groups if g['etapa']=='Infancia' and g['ronda']==1
           and g['participantes']>=2]
    first_diversity={'grupos_evaluados':len(first),
                     'grupos_contextos_distintos':sum(g['recursos_diversos'] for g in first),
                     'grupos_con_ambas_elecciones':sum(g['ambas_opciones'] for g in first),
                     'porcentaje_grupos_con_A_y_B':round(
                         100*sum(g['ambas_opciones'] for g in first)/len(first),2)
                         if first else None}
    result={'schema':'simlog-v22-20261109-dynamic-affinity','status':'experimental',
            'sources':catalog['sources'],'cards_total':len(catalog['cards']),
            'counts_by_stage_role':{'Infancia':12,'Juventud':24,'Adultez':15},
            'config':{'seeds_per_table':seeds,'sizes':list(sizes),'round_limit':round_limit,
                      'competition':competition,'policy':policy,'hand_size':hand_size,
                      'bank_enabled':bank_enabled,'affinity_neutral':[-2,2],
                      'affinity_weight':affinity_weight,'adult_situation_auctions':False,
                      'deck_shuffles':'independent random seed per stage and role',
                      'ruleset':'especificacion-integral-2026-11-09',
                      'situation_assignment':'one shared card per stage and role per round',
                      'childhood_income':'destination_only',
                      'youth_squares_income':'disabled',
                      'adult_squares_income':'disabled_except_profile',
                      'source_document_id':'1XvdzvRGT5ZGtgljpn5vVJYS4A0KDpqkw'},
            'summary':aggregated,'winners_by_zone':dict(zones),
            'total_decisions':sum(x['choices_A']+x['choices_B'] for x in rows),
            'total_games':len(rows),'total_marriages':sum(x['won'] for x in rows),
            'total_blocked_by_pending_rules':sum(x['stop']=='rule_pending' for x in rows),
            'bank_conversions':sum(x['bank_conversions'] for x in rows),
            'diversidad_infancia_primera_ronda':first_diversity}
    (out/'resumen.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser()
    a.add_argument('--out',type=Path,default=Path('resultados/simlog_v22'))
    a.add_argument('--semillas',type=int,default=20)
    a.add_argument('--inicio',type=int,default=1)
    a.add_argument('--rondas',type=int,default=100)
    a.add_argument('--afinidad-peso',type=float,default=8.0)
    a.add_argument('--sin-competencia',action='store_true')
    args=a.parse_args()
    print(json.dumps(execute(args.out,seeds=args.semillas,round_limit=args.rondas,
               competition=not args.sin_competencia,affinity_weight=args.afinidad_peso,start_seed=args.inicio),
                     ensure_ascii=False,indent=2))
