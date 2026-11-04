import unittest
from simulador.afinidad_v2 import zone,compatible,shift
from simulador.mazos_vigentes_v2 import load_current,new_decks,CurrentResolver
from simulador.turnos_v2 import Stage,PlayerState,SituationCard
from simulador.economia_v2 import EconomyV2

class CardsNewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=load_current()
    def test_all_102_cards_and_symmetry(self):
        self.assertEqual(102,len(self.catalog['cards']))
        for stage,count in [('Infancia',12),('Juventud',24),('Adultez',15)]:
            c=[x for x in self.catalog['cards'] if x['stage']==stage and x['role']=='Clarisa']
            l=[x for x in self.catalog['cards'] if x['stage']==stage and x['role']=='Lucas']
            self.assertEqual(count,len(c));self.assertEqual(count,len(l))
            self.assertEqual([x['effects'] for x in c],[x['effects'] for x in l])
    def test_role_shuffle_independent_seeds(self):
        for seed in range(1,101):
            decks=new_decks(self.catalog,seed)
            for stage in (Stage.INFANCIA,Stage.JUVENTUD,Stage.ADULTEZ):
                a=[x.id[-2:] for x in decks[(stage,'Clarisa')]._deck]
                b=[x.id[-2:] for x in decks[(stage,'Lucas')]._deck]
                self.assertNotEqual(a,b)
    def test_affinity_regions_and_shifts(self):
        self.assertEqual([zone(v) for v in (-3,-2,0,2,3)],['A','Neutro','Neutro','Neutro','B'])
        self.assertEqual(shift('A'),-1);self.assertEqual(shift('B'),1)
        self.assertTrue(compatible({1:-3,2:-4},1,2));self.assertFalse(compatible({1:-3,2:-2},1,2))
    def test_marriage_dynamic_checks_zones(self):
        p=[PlayerState(1,'Clarisa'),PlayerState(2,'Lucas')]
        eco=EconomyV2(p);eco.dynamic_affinity={1:-3,2:-2}
        self.assertFalse(eco.affinity_compatible(1,2))
        eco.dynamic_affinity[2]=-5
        self.assertTrue(eco.affinity_compatible(1,2))
        eco.dynamic_affinity[1]=0;eco.dynamic_affinity[2]=2
        self.assertTrue(eco.affinity_compatible(1,2))
    def test_early_loss_truncated(self):
        p=PlayerState(1,'Clarisa')
        eco=EconomyV2([p]);eco.dynamic_affinity={1:0}
        r=CurrentResolver(eco)
        self.assertEqual(0,eco.accounts[1].free['M'])
        r._apply(p,{'A':1,'M':-3})
        self.assertEqual(0,eco.accounts[1].free['M'])
        self.assertEqual(1,eco.accounts[1].free['A'])
    def test_no_adult_auctions(self):
        a=[x for x in self.catalog['cards'] if x['stage']=='Adultez']
        self.assertEqual(30,len(a))
        self.assertTrue(all(set(x['effects'])=={'A','B'} for x in a))

if __name__=='__main__':unittest.main()
