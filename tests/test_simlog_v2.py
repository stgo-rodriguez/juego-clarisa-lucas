"""SIMLOG v2.0: observabilidad de todos los turnos sin cambiar el juego."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from laboratorio.ejecutar_simlog_v2 import aggregate_ab, execute
from laboratorio.experimento_mazos_propuestos_v2 import run_proposal
from simulador.mazos_propuestos_v2 import BalanceVariant


def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


class SIMLOGTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._temp.name)
        cls.baseline = run_proposal(6,1,'planificador',True,rounds=60)
        cls.with_log = run_proposal(6,1,'planificador',True,rounds=60,
                                    simlog_dir=cls.out/'p6')
        cls.turns = read_csv(cls.out/'p6'/'turnos.csv')
        cls.events = read_csv(cls.out/'p6'/'eventos.csv')
        cls.states = read_csv(cls.out/'p6'/'estados_jugadores.csv')
        cls.globals = read_csv(cls.out/'p6'/'estados_globales.csv')
        cls.manifest = json.loads((cls.out/'p6'/'manifest.json').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls._temp.cleanup()

    def test_tracing_does_not_change_game_outcomes(self):
        self.assertEqual(self.baseline,self.with_log)
        self.assertEqual(len(self.turns),self.baseline['turns_executed'])

    def test_full_history_all_players_before_and_after(self):
        self.assertEqual(len(self.states),len(self.turns)*6*2)
        self.assertEqual(len(self.globals),len(self.turns)*2)
        for turn_no in (1,2,10,len(self.turns)):
            states=[x for x in self.states if int(x['Turno_global'])==turn_no]
            self.assertEqual(len(states),12)
            self.assertEqual({x['Momento'] for x in states},{'antes','despues'})
            self.assertEqual({int(x['Jugador']) for x in states},{1,2,3,4,5,6})

    def test_situation_juvenile_matches_movement(self):
        youth=[x for x in self.turns if x['Etapa_antes']=='Juventud']
        childhood=[x for x in self.turns if x['Etapa_antes']=='Infancia']
        self.assertTrue(youth)
        self.assertTrue(childhood)
        self.assertTrue(all(x['Desenlace_elegido']==x['Desenlace_movimiento']
                            and x['Desenlace_elegido'] in ('A','B') for x in youth))
        self.assertTrue(all(x['Desenlace_elegido'] in ('A','B') and x['Desenlace_movimiento']==''
                            and x['Desenlace_texto'] for x in childhood))

    def test_adult_situation_and_movement_are_separate(self):
        adults=[x for x in self.turns if x['Etapa_antes']=='Adultez']
        self.assertTrue(adults)
        self.assertTrue(all(x['Carta_Movimiento'] and x['Desenlace_movimiento'] in ('A','B')
                            for x in adults))
        self.assertTrue(any(x['Resultado_situacion'].startswith('coop') or x['Resultado_situacion']=='auction'
                            for x in adults))
        self.assertTrue(any(x['Direccion'] or x['Salida_despues_de']!=''
                            for x in adults))

    def test_all_events_in_order_with_real_economy_changes(self):
        sequences=[int(x['Secuencia']) for x in self.events]
        self.assertEqual(sequences,list(range(1,len(sequences)+1)))
        self.assertTrue(any(x['Fuente']=='economia' and x['Accion']=='transfer' for x in self.events))
        self.assertTrue(any(x['Fuente']=='observador' and x['Accion']=='paso_por_casillero' for x in self.events))
        self.assertTrue(any(x['Fuente']=='duelo' and x['Accion']=='duel' for x in self.events))
        self.assertTrue(any(x['Fuente']=='subasta' and x['Accion']=='social_auction' for x in self.events))
        self.assertTrue(any(x['Fuente']=='situacion' and x['Accion']=='proposed_situation' for x in self.events))
        for row in self.turns:
            num=int(row['Turno_global'])
            actual=[int(e['Secuencia']) for e in self.events
                    if e['Turno_global'] and int(e['Turno_global'])==num]
            listed=json.loads(row['Eventos_ID_JSON'])
            self.assertEqual(actual,listed)
            self.assertEqual(len(listed),int(row['Eventos_cantidad']))

    def test_passive_players_state_capture(self):
        by_key={(int(x['Turno_global']),int(x['Jugador']),x['Momento']):x for x in self.states}
        found=False
        for ev in self.events:
            if ev['Fuente']!='economia' or ev['Accion']!='issue':continue
            action=json.loads(ev['Detalle_JSON'])
            if not ev['Turno_global'] or not ev['Jugador_activo'] or int(ev['Jugador_activo'])==action['player']:
                continue
            no=int(ev['Turno_global']);pid=action['player']
            old=by_key[(no,pid,'antes')]
            new=by_key[(no,pid,'despues')]
            if any(int(old[r+'_libre'])!=int(new[r+'_libre']) for r in 'APKM'):
                found=True;break
        self.assertTrue(found,'El registro debe capturar efectos sobre participantes pasivos')

    def test_prefs_match_recorded_choices(self):
        prefs=read_csv(self.out/'p6'/'preferencias_situaciones.csv')
        self.assertEqual(sum(int(x['Veces_resuelta']) for x in prefs),
                         sum(bool(t['Carta_ID']) for t in self.turns))
        ab=sum(int(x['Elecciones_A'])+int(x['Elecciones_B']) for x in prefs)
        self.assertEqual(ab,sum(x['Desenlace_elegido'] in ('A','B') for x in self.turns))
        moves=read_csv(self.out/'p6'/'preferencias_movimientos.csv')
        self.assertEqual(sum(int(x['Veces_resuelta']) for x in moves),
                         sum(bool(t['Carta_Movimiento']) for t in self.turns))

    def test_integrity_sha_metadata_and_csv_files(self):
        self.assertEqual(self.manifest['schema'],'SIMLOG-2.0')
        self.assertEqual(self.manifest['validation'],'PASS')
        self.assertEqual(self.manifest['counts']['turnos.csv'],len(self.turns))
        self.assertEqual(self.manifest['counts']['eventos.csv'],len(self.events))
        for file,checksum in self.manifest['file_sha256'].items():
            self.assertEqual(hashlib.sha256((self.out/'p6'/file).read_bytes()).hexdigest(),checksum)

    def test_another_seed_ten_players_and_variant_replays(self):
        kwargs=dict(rounds=45,balance=BalanceVariant(.6,.7,1.0))
        pure=run_proposal(10,2,'aleatorio',False,**kwargs)
        with_trace=run_proposal(10,2,'aleatorio',False,simlog_dir=self.out/'ten',**kwargs)
        self.assertEqual(pure,with_trace)
        turns=read_csv(self.out/'ten'/'turnos.csv')
        self.assertEqual(len(turns),with_trace['turns_executed'])
        self.assertEqual(len(read_csv(self.out/'ten'/'estados_jugadores.csv')),len(turns)*20)

    def test_cli_multigame_index_and_ab(self):
        out=self.out/'batch'
        index=execute(out=out,seeds=(1,),rounds=35,sizes=(6,),
                      policies=('aleatorio','planificador'),competitions=(False,True),
                      scenario='original')
        self.assertEqual(index['n_games'],4)
        self.assertEqual(len(read_csv(out/'partidas.csv')),4)
        self.assertTrue(read_csv(out/'preferencias_por_carta.csv'))
        self.assertEqual(index['turns'],sum(int(x['turns']) for x in read_csv(out/'partidas.csv')))

    def test_sentinel_old_export_columns_available(self):
        names=set(self.turns[0])
        old={'Partida','Ronda','Turno_global','Jugador','Rol','Pareja_antes','Pareja_despues',
             'Etapa_antes','Pos_antes','Dado','Casillero_resuelto','Etapa_despues','Pos_despues',
             'Carta_ID','Situacion','Desenlace_elegido','Canje','Eventos','A_antes','A_despues',
             'Titulo','Pasaporte','Casa','Casamiento'}
        self.assertTrue(old.issubset(names))


if __name__ == '__main__':unittest.main()