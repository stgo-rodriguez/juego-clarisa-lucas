import unittest
from laboratorio.verificar_baseline import verify

class ReferenciasCongeladas(unittest.TestCase):
    def test_integridad_csv_historicos_y_semillas(self):
        result=verify(full=False)
        self.assertEqual(set(result),{'6','10'})
        self.assertEqual(sum(item['partidas'] for item in result.values()),2000)

if __name__=='__main__':unittest.main()
