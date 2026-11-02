"""Fase 1: invariantes geométricas y de manos del motor v2.0."""
import random
import unittest

from simulador.movimiento_v2 import (
    AdultHand, BOARD, CASAMIENTO, Coord, MovementCard, MovementPile,
    adult_options, cell_at, play_paired_turn, valid_directions,
    walk_adult, walk_circuit, youth_cards,
)


class TestAdultGeometry(unittest.TestCase):
    def test_tablero_cerrado(self):
        self.assertEqual(tuple(len(row) for row in BOARD), (5,) * 5)
        self.assertEqual(cell_at(Coord(3, 3)), 'Casa')
        self.assertEqual(cell_at(Coord(5, 3)), 'Perfil')
        tally = {c: sum(row.count(c) for row in BOARD) for c in ('A', 'P', 'K', 'M', '.')}
        self.assertEqual(tally, {'A': 2, 'P': 1, 'K': 1, 'M': 2, '.': 17})

    def test_cantidad_de_direcciones(self):
        counts = [len(valid_directions(Coord(r, c))) for r in range(1, 6) for c in range(1, 6)]
        self.assertEqual(counts.count(8), 9)
        self.assertEqual(counts.count(5), 12)
        self.assertEqual(counts.count(3), 4)

    def test_exhaustivo_864_movimientos_internos(self):
        checked = 0
        for r in range(1, 6):
            for c in range(1, 6):
                start = Coord(r, c)
                for d in range(1, 7):
                    for direction in valid_directions(start):
                        route = walk_adult(start, d, direction)
                        self.assertEqual(len(route.visited), d)
                        self.assertEqual(route.consumed, d)
                        self.assertEqual(route.discarded, 0)
                        self.assertEqual(route.destination, route.visited[-1])
                        self.assertEqual(route.activation, cell_at(route.destination))
                        checked += 1
        self.assertEqual(checked, 864)

    def test_rebote_no_cuenta_paso(self):
        route = walk_adult(Coord(3, 4), 3, 'E')
        self.assertEqual(route.visited, (Coord(3, 5), Coord(3, 4), Coord(3, 3)))
        self.assertEqual(route.reflections, ((2, 'columna'),))
        self.assertEqual(route.activation, 'Casa')

    def test_rebote_en_esquina_diagonal(self):
        route = walk_adult(Coord(1, 1), 5, 'SE')
        self.assertEqual(route.visited, (Coord(2, 2), Coord(3, 3), Coord(4, 4), Coord(5, 5), Coord(4, 4)))
        self.assertEqual(route.reflections, ((5, 'ambos'),))
        self.assertEqual(route.activation, '.')

    def test_no_activar_casillas_intermedias(self):
        route = walk_adult(Coord(5, 3), 3, 'N')
        self.assertEqual(route.visited, (Coord(4, 3), Coord(3, 3), Coord(2, 3)))
        self.assertEqual(route.activation, '.')  # Pasar por Casa no permite comprar.

    def test_retorno_al_origen_si_se_consumen_todos_los_pasos(self):
        route = walk_adult(Coord(5, 3), 4, 'O')
        self.assertEqual(route.destination, Coord(5, 3))
        self.assertEqual(route.activation, 'Perfil')

    def test_prohibida_direccion_inicial_fuera(self):
        with self.assertRaises(ValueError):
            walk_adult(Coord(1, 3), 2, 'N')
        with self.assertRaises(ValueError):
            walk_adult(Coord(1, 1), 2, 'NO')

    def test_salir_directamente_desde_puertas(self):
        for c in (2, 3, 4):
            route = walk_adult(Coord(1, c), 6, None, marriage_eligible=True, exit_after=0)
            self.assertEqual(route.destination, CASAMIENTO)
            self.assertEqual(route.consumed, 1)
            self.assertEqual(route.discarded, 5)
            self.assertEqual(route.visited, ())
        with self.assertRaises(ValueError):
            walk_adult(Coord(1, 1), 6, None, marriage_eligible=True, exit_after=0)
        with self.assertRaises(ValueError):
            walk_adult(Coord(1, 3), 6, None, exit_after=0)

    def test_salida_intermedia_descarta_sobrantes(self):
        route = walk_adult(Coord(5, 3), 6, 'N', marriage_eligible=True, exit_after=4)
        self.assertEqual(route.visited[-1], Coord(1, 3))
        self.assertEqual(route.destination, CASAMIENTO)
        self.assertEqual((route.consumed, route.discarded), (5, 1))
        self.assertEqual(route.activation, CASAMIENTO)
        self.assertTrue(any(r.destination == CASAMIENTO for r in adult_options(Coord(5, 3), 6, marriage_eligible=True)))
        self.assertFalse(any(r.destination == CASAMIENTO for r in adult_options(Coord(5, 3), 6)))

    def test_parametros_invalidos(self):
        for distance in (0, -1, 7, 1.5):
            with self.assertRaises(ValueError):
                walk_adult(Coord(3, 3), distance, 'N')
        with self.assertRaises(ValueError):
            walk_adult(Coord(1, 3), 2, None)
        with self.assertRaises(ValueError):
            walk_adult(Coord(1, 3), 2, 'S', marriage_eligible=True, exit_after=2)


class TestCircuits(unittest.TestCase):
    def test_crossing_mark_and_exact_stop(self):
        path = walk_circuit(4, 5)
        self.assertEqual(path.visited, (5, 6, 1, 2, 3))
        self.assertEqual(path.lap_crossings, 1)
        self.assertEqual(path.destination, 3)
        stop = walk_circuit(4, 6, early_exit_at=5)
        self.assertEqual((stop.visited, stop.discarded), ((5,), 5))

    def test_no_salida_en_casillero_inicial_sin_visitarlo(self):
        path = walk_circuit(5, 2, early_exit_at=5)
        self.assertEqual(path.destination, 1)
        self.assertEqual(path.discarded, 0)


class TestCardsAndHands(unittest.TestCase):
    def test_30_pares_ordenados_y_36_alternativos(self):
        cards = youth_cards()
        self.assertEqual(len(cards), 30)
        self.assertEqual(len(youth_cards(include_equal=True)), 36)
        self.assertTrue(all(c.a != c.b for c in cards))
        self.assertIn((2, 5), [(c.a, c.b) for c in cards])
        self.assertIn((5, 2), [(c.a, c.b) for c in cards])
        self.assertEqual(len({c.id for c in cards}), 30)

    def test_mazo_barajado_sin_reemplazo(self):
        deck1 = MovementPile(youth_cards(), random.Random(99))
        deck2 = MovementPile(youth_cards(), random.Random(99))
        first = deck1.draw(6)
        self.assertEqual(first, deck2.draw(6))
        self.assertEqual(len({c.id for c in first}), 6)
        rest = deck1.draw(24)
        self.assertEqual(deck1.available, 0)
        with self.assertRaises(ValueError):
            deck1.draw()
        deck1.discard(first)
        deck1.discard(rest)
        deck1.recycle_discard()
        self.assertEqual(deck1.available, 30)
        self.assertEqual(deck1.discarded, 0)

    def test_pareja_conserva_mano_acompanante(self):
        cards = youth_cards()
        active = AdultHand(cards[:3])
        companion = AdultHand(cards[3:6])
        card, distance, remaining, untouched = play_paired_turn(active, companion, cards[1].id, 'B')
        self.assertEqual((card, distance), (cards[1], cards[1].b))
        self.assertEqual(len(remaining.cards), 2)
        self.assertIs(untouched, companion)
        with self.assertRaises(ValueError):
            remaining.renew(cards[6:9])
        for card in remaining.cards:
            _, _, remaining = remaining.play(card.id, 'A')
        self.assertTrue(remaining.exhausted)
        self.assertEqual(len(remaining.renew(cards[6:10]).cards), 4)

    def test_decisiones_a_b_misma_carta(self):
        card = MovementCard('test', 2, 5)
        self.assertEqual((card.distance('A'), card.distance('B')), (2, 5))
        with self.assertRaises(ValueError):
            card.distance('C')


if __name__ == '__main__':
    unittest.main()
