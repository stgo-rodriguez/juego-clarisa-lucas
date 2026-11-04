"""Consolidación auditable de SIMLOG v2.1: 200 partidas, seis mazos nuevos."""
import csv,json,hashlib,statistics
from collections import defaultdict,Counter
from pathlib import Path
from simulador.afinidad_v2 import zone
from laboratorio.simular_mazos_vigentes_v2 import write_rows

def rows_from(path):
    with Path(path).open('r',newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def run(root:Path):
    blocks=sorted(root.glob('bloque_*/partidas.csv'))
    rows=[];turns=[];metadata=[]
    for block in blocks:
        b=block.parent
        for game in rows_from(block):
            rows.append(game)
            folder=b/'trazas'/f'n{game["size"]}_s{game["seed"]}'
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            assert manifest['affinity_model']=='zona_A_menos3_neutro_menos2_a2_B_mas3'
            assert manifest['validation']=='PASS'
            assert manifest['counts']['turnos.csv']==int(game['turns'])
            for filename,hexsha in manifest['file_sha256'].items():
                got=hashlib.sha256((folder/filename).read_bytes()).hexdigest()
                if got!=hexsha:raise AssertionError(f'{folder}/{filename}: digest mismatch')
            orders=json.loads((folder/'orden_mazos.json').read_text())
            for stage in ('Infancia','Juventud','Adultez'):
                a=[x.split('-')[-1] for x in orders[stage+'_Clarisa']]
                b2=[x.split('-')[-1] for x in orders[stage+'_Lucas']]
                assert a!=b2, (folder,stage)
                metadata.append({'mesa':game['size'],'semilla':game['seed'],'etapa':stage,
                                 'orden_igual':a==b2,'primera_C':orders[stage+'_Clarisa'][0],
                                 'primera_L':orders[stage+'_Lucas'][0]})
            game_turns=rows_from(folder/'turnos.csv')
            for t in game_turns:
                t['mesa']=game['size'];t['semilla']=game['seed']
                before=int(t['Afinidad_posicion_antes']);after=int(t['Afinidad_posicion_despues'])
                letter=t['Desenlace_elegido']
                if letter in ('A','B'):assert after-before==(-1 if letter=='A' else 1)
                else:assert after==before
                assert t['Afinidad_zona_antes']==zone(before)
                assert t['Afinidad_zona_despues']==zone(after)
                for mom in ('antes','despues'):
                    mate=t[f'Pareja_afinidad_posicion_{mom}']
                    comp=t[f'Pareja_compatible_{mom}']
                    if mate:
                        expected=zone(before if mom=='antes' else after)==zone(int(mate))
                        assert comp==str(expected),(folder,t['Turno_global'],mom,comp,expected)
                    else:assert comp in ('', 'None')
            assert len(game_turns)==int(game['turns'])
            if game['won']=='True':
                winner=json.loads(game['winning_pair'])
                final=json.loads(game['affinity_final_positions'])
                assert zone(final[str(winner[0])])==zone(final[str(winner[1])])==game['winning_zone']
            turns.extend(game_turns)
    assert len(rows)==200
    assert len({(r['size'],r['seed']) for r in rows})==200
    write_rows(root/'partidas_consolidadas.csv',rows)
    write_rows(root/'auditoria_barajado.csv',metadata)
    # Preferencias globales y coincidencia de misma carta por ronda (>=2 resolutores)
    counts=defaultdict(Counter);share=defaultdict(list);total=Counter()
    stagegroups=defaultdict(Counter)
    for t in turns:
        stage=t['Etapa_situacion'];role=t['Rol'];letter=t['Desenlace_elegido'];card=t['Carta_ID']
        if card and letter in ('A','B'):
            counts[(stage,role,card)][letter]+=1
            stagegroups[(stage,role)][letter]+=1
            total[stage]+=1
            if stage in ('Juventud','Adultez'):
                key=(t['mesa'],t['semilla'],t['Ronda'],stage,role,card)
                share[key].append(letter)
    prefs=[]
    for (stage,role,card),c in sorted(counts.items()):
        n=c['A']+c['B']
        prefs.append({'Etapa':stage,'Rol':role,'Carta_ID':card,'Resoluciones':n,'A':c['A'],'B':c['B'],
             'A_pct':round(100*c['A']/n,2),'Dominancia_pct':round(100*max(c['A'],c['B'])/n,2),
             'Opcion_mayoritaria':'A' if c['A']>c['B'] else ('B' if c['B']>c['A'] else 'Empate')})
    write_rows(root/'preferencias_por_carta.csv',prefs)
    bygroup=[]
    for (stage,role),c in sorted(stagegroups.items()):
        n=c['A']+c['B'];p=[x for x in prefs if x['Etapa']==stage and x['Rol']==role]
        bygroup.append({'Etapa':stage,'Rol':role,'Resoluciones':n,'A':c['A'],'B':c['B'],
             'A_pct':round(100*c['A']/n,2),
             'Cartas':len(p),'Cartas_dominancia_80':sum(x['Dominancia_pct']>=80 for x in p),
             'Cartas_dominancia_90':sum(x['Dominancia_pct']>=90 for x in p)})
    write_rows(root/'resumen_por_etapa_rol.csv',bygroup)
    shared=[]
    for key,choices in sorted(share.items()):
        if len(choices)<2:continue
        shared.append({'Mesa':key[0],'Semilla':key[1],'Ronda':key[2],'Etapa':key[3],
                       'Rol':key[4],'Carta':key[5], 'Resolutores':len(choices),
                       'A':choices.count('A'),'B':choices.count('B'),
                       'Todos_igual':len(set(choices))==1})
    write_rows(root/'coincidencia_carta_compartida.csv',shared)
    summary_shared=[]
    for stage in ('Juventud','Adultez'):
        for size in ('6','10'):
            g=[x for x in shared if x['Etapa']==stage and x['Mesa']==size]
            summary_shared.append({'Etapa':stage,'Mesa':size,'Ocasiones_con_dos_o_mas':len(g),
                        'Todos_igual':sum(x['Todos_igual'] for x in g),
                        'Porcentaje_igual':round(100*sum(x['Todos_igual'] for x in g)/len(g),2) if g else None})
    write_rows(root/'coincidencia_resumen.csv',summary_shared)
    # Tabla por carta: estimador probabilístico de coincidencia de 2 jugadores en estados reales
    probpairs=[]
    for p in prefs:
        n=p['Resoluciones'];a=p['A'];b=p['B']
        if n>1:prob=(a*(a-1)+b*(b-1))/(n*(n-1))
        else:prob=None
        probpairs.append({**p,'Prob_dos_iguales_pct':round(100*prob,2) if prob is not None else None})
    write_rows(root/'coincidencia_condicional_por_carta.csv',probpairs)
    sizes=[]
    for n in ('6','10'):
        rr=[r for r in rows if r['size']==n]; rds=[int(r['rounds']) for r in rr]
        sizes.append({'Jugadores':int(n),'Partidas':len(rr),'Casamientos':sum(r['won']=='True' for r in rr),
                      'Media_rondas':round(statistics.mean(rds),2),'Mediana_rondas':statistics.median(rds),
                      'P90_rondas':sorted(rds)[int(.9*len(rds))-1],
                      'Media_turnos':round(statistics.mean(int(r['turns']) for r in rr),2),
                      'Neutro':sum(r['winning_zone']=='Neutro' for r in rr),
                      'A':sum(r['winning_zone']=='A' for r in rr),
                      'B':sum(r['winning_zone']=='B' for r in rr)})
    write_rows(root/'resumen_mesas.csv',sizes)
    # Reconstruir situaciones de parejas ganadoras y sus trayectorias
    winners=[]
    for r in rows:
        pair=json.loads(r['winning_pair']) if r['won']=='True' else []
        if not pair:continue
        rr=[t for t in turns if t['mesa']==r['size'] and t['semilla']==r['seed'] and int(t['Jugador']) in pair]
        # Solo turnos donde YA son pareja (antes o después) para medir compatibilidad efectiva
        pg=[t for t in rr if t['Pareja_antes'] or t['Pareja_despues']]
        switches=sum(t['Pareja_compatible_antes']=='False' and t['Pareja_compatible_despues']=='True' for t in pg)
        winners.append({'Mesa':int(r['size']),'Semilla':int(r['seed']),
          'Ganadores':r['winning_pair'],'Zona_final':r['winning_zone'],
          'Turnos_ganadores_ya_emparejados':len(pg),
          'Turnos_incompatibles':sum(t['Pareja_compatible_despues']=='False' for t in pg),
          'Turnos_compatibles':sum(t['Pareja_compatible_despues']=='True' for t in pg),
          'Recuperaciones_compatibilidad_en_turno':switches,
          'Terminaron_compatibles':True})
    write_rows(root/'trayectorias_parejas_ganadoras.csv',winners)
    total_events=sum(json.loads((b.parent/'trazas'/f'n{x["size"]}_s{x["seed"]}'/'manifest.json').read_text())['counts']['eventos.csv'] for b in blocks for x in rows_from(b))
    report={'schema':'SIMLOG-2.1 analisis','n_partidas':len(rows),'semillas_por_tamano':100,
          'total_turnos':len(turns),'total_eventos':total_events,
          'total_situaciones_resueltas':sum(total.values()),
          'barajados_independientes_verificados':len(metadata),
          'marriages':sum(r['won']=='True' for r in rows),
          'winners_by_zone':dict(Counter(r['winning_zone'] for r in rows)),
          'tables_by_size':sizes,
          'stage_role':bygroup,
          'shared_choice_agreement':summary_shared,
          'incompatible_winner_turns':sum(x['Turnos_incompatibles'] for x in winners),
          'winning_pairs_ever_incompatible':sum(x['Turnos_incompatibles']>0 for x in winners),
          'cards_dominance_over_90':sum(p['Dominancia_pct']>=90 for p in prefs),
          'source_catalog_sha256':hashlib.sha256((root.parent/'docs/datos_v2_nuevas_cartas/catalogo_102_v03_v04.json').read_bytes()).hexdigest()}
    (root/'analisis_consolidado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':
    import argparse
    a=argparse.ArgumentParser();a.add_argument('--root',type=Path,required=True)
    args=a.parse_args();run(args.root)
