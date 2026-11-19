import unittest

from engine import (
    Position,
    START_FEN,
    game_end_reason,
    game_status,
    has_legal_move,
    insufficient_material,
    is_in_check,
    legal_moves,
    move_to_text,
    parse_move_text,
)


def perft(pos, depth):
    """Count every possible line of play to the given depth (a classic move-generator test)."""
    moves = legal_moves(pos)
    if depth == 1:
        return len(moves)
    return sum(perft(pos.make_move(m), depth - 1) for m in moves)


def play(pos, *texts):
    for text in texts:
        move = parse_move_text(text)
        assert move in legal_moves(pos) or any(
            m[:2] == move[:2] and m[2] == (move[2] or "q") for m in legal_moves(pos)), text
        if move not in legal_moves(pos):
            move = (move[0], move[1], "q")
        pos = pos.make_move(move)
    return pos


class PerftTests(unittest.TestCase):
    """Numbers from the Chess Programming Wiki perft suite. If these match, the rules are right."""

    def check(self, fen, expected):
        pos = Position.from_fen(fen)
        for depth, nodes in enumerate(expected, start=1):
            self.assertEqual(perft(pos, depth), nodes, f"depth {depth} of {fen}")

    def test_start_position(self):
        self.check(START_FEN, [20, 400, 8902])

    def test_kiwipete_castling_and_pins(self):
        self.check("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [48, 2039, 97862])

    def test_en_passant_and_checks_endgame(self):
        self.check("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238])

    def test_promotions_and_castling_rights(self):
        self.check("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", [6, 264, 9467])

    def test_position_5(self):
        self.check("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379])

    def test_position_6(self):
        self.check("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", [46, 2079, 89890])


class RuleTests(unittest.TestCase):
    def test_fen_round_trip(self):
        for fen in [START_FEN, "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
                    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"]:
            self.assertEqual(Position.from_fen(fen).to_fen(), fen)

    def test_castling_moves_the_rook(self):
        pos = play(Position(), "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1")
        self.assertEqual(pos.board[62], "K")
        self.assertEqual(pos.board[61], "R")
        self.assertEqual(pos.board[63], ".")
        self.assertNotIn("K", pos.castling)
        self.assertNotIn("Q", pos.castling)

    def test_cannot_castle_through_check(self):
        pos = Position.from_fen("4k3/8/8/8/8/5r2/8/4K2R w K - 0 1")  # rook on f3 attacks f1
        self.assertNotIn((60, 62, ""), legal_moves(pos))

    def test_cannot_castle_out_of_check(self):
        pos = Position.from_fen("4k3/8/8/8/8/8/4r3/R3K2R w KQ - 0 1")
        self.assertNotIn((60, 62, ""), legal_moves(pos))
        self.assertNotIn((60, 58, ""), legal_moves(pos))

    def test_castling_right_lost_after_rook_moves(self):
        pos = play(Position.from_fen("4k3/8/8/8/8/8/8/R3K2R w KQ - 0 1"), "h1h2", "e8d8", "h2h1")
        self.assertNotIn("K", pos.castling)
        self.assertIn("Q", pos.castling)

    def test_en_passant(self):
        pos = play(Position(), "e2e4", "a7a6", "e4e5", "d7d5")
        self.assertEqual(pos.ep, parse_move_text("d6d6")[0])
        self.assertIn(parse_move_text("e5d6"), legal_moves(pos))
        pos = play(pos, "e5d6")
        self.assertEqual(pos.board[parse_move_text("d5d5")[0]], ".")  # the captured pawn is gone

    def test_en_passant_only_right_after_double_push(self):
        pos = play(Position(), "e2e4", "a7a6", "e4e5", "d7d5", "h2h3", "h7h6")
        self.assertNotIn(parse_move_text("e5d6"), legal_moves(pos))

    def test_promotion_choices(self):
        pos = Position.from_fen("8/P6k/8/8/8/8/8/K7 w - - 0 1")
        promos = sorted(m[2] for m in legal_moves(pos) if m[:2] == parse_move_text("a7a8")[:2])
        self.assertEqual(promos, ["b", "n", "q", "r"])
        pos = play(pos, "a7a8n")
        self.assertEqual(pos.board[0], "N")

    def test_pinned_piece_cannot_move(self):
        pos = Position.from_fen("4r2k/8/8/8/8/8/4N3/4K3 w - - 0 1")
        self.assertEqual([m for m in legal_moves(pos) if m[0] == 52], [])

    def test_move_text(self):
        self.assertEqual(move_to_text(parse_move_text("e7e8q")), "e7e8q")
        self.assertIsNone(parse_move_text("hello"))
        self.assertIsNone(parse_move_text("e9e4"))


class GameEndTests(unittest.TestCase):
    def test_fools_mate(self):
        pos = play(Position(), "f2f3", "e7e5", "g2g4", "d8h4")
        self.assertTrue(is_in_check(pos))
        self.assertEqual(game_status(pos), "checkmate")
        self.assertFalse(has_legal_move(pos))

    def test_stalemate(self):
        pos = Position.from_fen("k7/8/1Q6/8/8/8/8/2K5 b - - 0 1")
        self.assertEqual(game_status(pos), "stalemate")

    def test_insufficient_material(self):
        self.assertTrue(insufficient_material(Position.from_fen("8/8/4k3/8/8/4K3/8/8 w - - 0 1")))
        self.assertTrue(insufficient_material(Position.from_fen("8/8/4k3/8/8/4K3/8/5B2 w - - 0 1")))
        self.assertTrue(insufficient_material(Position.from_fen("8/8/4k3/8/8/4K3/8/5N2 w - - 0 1")))
        self.assertFalse(insufficient_material(Position.from_fen("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")))
        self.assertFalse(insufficient_material(Position.from_fen("8/8/4k3/8/8/4K3/8/4R3 w - - 0 1")))

    def test_fifty_move_rule(self):
        pos = Position.from_fen("8/8/4k3/8/8/4K3/4P3/8 w - - 100 80")
        self.assertEqual(game_end_reason(pos), "fifty-move rule")

    def test_threefold_repetition(self):
        pos = Position()
        counts = {pos.key(): 1}
        for text in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
            pos = play(pos, text)
            counts[pos.key()] = counts.get(pos.key(), 0) + 1
        self.assertEqual(game_end_reason(pos, counts), "threefold repetition")


if __name__ == "__main__":
    unittest.main()
