import random
import unittest

from engine import Position, game_status, legal_moves, move_to_text, parse_move_text
from search import (
    LEVELS,
    MATE,
    analyse,
    clamp_score,
    evaluate,
    find_best_move,
    pick_engine_move,
    score_after,
)


class EvaluationTests(unittest.TestCase):
    def test_start_position_is_balanced(self):
        self.assertEqual(evaluate(Position()), 0)

    def test_extra_queen_is_good_for_its_owner(self):
        pos = Position.from_fen("4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
        self.assertGreater(evaluate(pos), 800)
        self.assertLess(evaluate(Position.from_fen("4k3/8/8/8/8/8/8/3QK3 b - - 0 1")), -800)

    def test_bare_kings_and_lone_minor_are_draws(self):
        self.assertEqual(evaluate(Position.from_fen("4k3/8/8/8/8/8/8/4K3 w - - 0 1")), 0)
        self.assertEqual(evaluate(Position.from_fen("4k3/8/8/8/8/8/8/3BK3 w - - 0 1")), 0)

    def test_passed_pawn_is_worth_more_when_advanced(self):
        far = Position.from_fen("4k3/8/4P3/8/8/8/8/4K3 w - - 0 1")
        near = Position.from_fen("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
        self.assertGreater(evaluate(far), evaluate(near))


class SearchTests(unittest.TestCase):
    def test_finds_mate_in_one(self):
        pos = Position.from_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
        move, score, _ = find_best_move(pos, 3)
        self.assertEqual(move_to_text(move), "a1a8")
        self.assertGreater(score, MATE - 100)

    def test_finds_mate_in_two(self):
        # Two rooks: Ra7 then Rb8#
        pos = Position.from_fen("7k/8/8/8/8/8/R7/1R4K1 w - - 0 1")
        move, score, _ = find_best_move(pos, 4)
        self.assertGreater(score, MATE - 100)

    def test_wins_a_hanging_queen(self):
        pos = Position.from_fen("4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1")
        move, _, _ = find_best_move(pos, 3)
        self.assertEqual(move_to_text(move), "d1d5")

    def test_does_not_hang_its_queen(self):
        # Qxd5 would lose the queen to the pawn on e6
        pos = Position.from_fen("4k3/8/4p3/3p4/8/8/8/3QK3 w - - 0 1")
        move, _, _ = find_best_move(pos, 3)
        self.assertNotEqual(move_to_text(move), "d1d5")

    def test_returns_none_when_game_is_over(self):
        mated = Position.from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        self.assertEqual(game_status(mated), "stalemate")
        self.assertIsNone(find_best_move(mated, 2)[0])

    def test_time_limit_is_respected(self):
        import time
        pos = Position.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        start = time.perf_counter()
        move, _, depth = find_best_move(pos, 10, seconds=0.5)
        self.assertLess(time.perf_counter() - start, 2.5)
        self.assertIn(move, legal_moves(pos))
        self.assertGreaterEqual(depth, 1)

    def test_prefers_castling_style_development_over_nothing(self):
        move, _, _ = find_best_move(Position(), 3)
        self.assertIn(move, legal_moves(Position()))

    def test_score_after_and_analyse(self):
        pos = Position.from_fen("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
        best, score = analyse(pos, 3, 1.0)
        self.assertEqual(move_to_text(best), "a1a8")
        self.assertGreater(score_after(pos, best), MATE - 100)
        self.assertLess(score_after(pos, parse_move_text("g1f1")), 500)

    def test_clamp(self):
        self.assertEqual(clamp_score(MATE - 3), 1500)
        self.assertEqual(clamp_score(-MATE + 3), -1500)
        self.assertEqual(clamp_score(40), 40)


class LevelTests(unittest.TestCase):
    def test_there_are_nine_levels(self):
        self.assertEqual(sorted(LEVELS), list(range(1, 10)))

    def test_every_level_returns_a_legal_move(self):
        random.seed(1)
        pos = Position.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        legal = legal_moves(pos)
        for level in range(1, 7):
            self.assertIn(pick_engine_move(pos, level), legal)

    def test_clock_pressure_makes_the_engine_faster(self):
        import time
        pos = Position.from_fen("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
        start = time.perf_counter()
        move = pick_engine_move(pos, 8, seconds_left=3.0)  # only 3 seconds on the clock
        self.assertLess(time.perf_counter() - start, 2.0)
        self.assertIn(move, legal_moves(pos))

    def test_high_level_beats_low_level(self):
        """Level 6 should win (or at least not lose) most games against level 1."""
        random.seed(7)
        results = {"high": 0, "low": 0, "draw": 0}
        for game in range(2):
            high_is_white = game == 0
            pos = Position()
            keys = []
            for _ply in range(120):
                if game_status(pos) != "playing":
                    break
                white_moves = pos.white_to_move
                level = 6 if white_moves == high_is_white else 1
                move = pick_engine_move(pos, level, keys)
                pos = pos.make_move(move)
                keys.append(pos.key())
            if game_status(pos) == "checkmate":
                loser_is_white = pos.white_to_move
                results["low" if loser_is_white == high_is_white else "high"] += 1
            else:
                results["draw"] += 1
        self.assertEqual(results["low"], 0, results)


if __name__ == "__main__":
    unittest.main()
