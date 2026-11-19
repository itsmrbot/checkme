import unittest

from engine import Position, legal_moves, parse_move_text
from notation import move_to_san, parse_line, san_to_move


class SanTests(unittest.TestCase):
    def test_basic_moves(self):
        pos = Position()
        self.assertEqual(move_to_san(pos, parse_move_text("e2e4")), "e4")
        self.assertEqual(move_to_san(pos, parse_move_text("g1f3")), "Nf3")

    def test_parse_line_and_write_it_back(self):
        text = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6"
        pos = Position()
        sans = []
        for move in parse_line(pos, text):
            sans.append(move_to_san(pos, move))
            pos = pos.make_move(move)
        self.assertEqual(" ".join(sans), "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6")

    def test_capture_and_check_and_mate(self):
        pos = Position()
        for san in ["f3", "e5", "g4"]:
            pos = pos.make_move(san_to_move(pos, san))
        mate = san_to_move(pos, "Qh4#")
        self.assertEqual(move_to_san(pos, mate), "Qh4#")
        pos = Position()
        for san in ["e4", "d5"]:
            pos = pos.make_move(san_to_move(pos, san))
        self.assertEqual(move_to_san(pos, san_to_move(pos, "exd5")), "exd5")

    def test_disambiguation(self):
        pos = Position.from_fen("4k3/8/8/8/8/8/4K3/R6R w - - 0 1")
        self.assertEqual(move_to_san(pos, parse_move_text("a1d1")), "Rad1")
        self.assertEqual(move_to_san(pos, parse_move_text("h1d1")), "Rhd1")
        pos = Position.from_fen("4k3/8/8/R7/8/8/8/R3K3 w - - 0 1")
        self.assertEqual(move_to_san(pos, parse_move_text("a5a3")), "R5a3")

    def test_promotion(self):
        pos = Position.from_fen("8/P6k/8/8/8/8/8/K7 w - - 0 1")
        self.assertEqual(move_to_san(pos, parse_move_text("a7a8q")), "a8=Q")
        self.assertEqual(move_to_san(Position.from_fen("7k/P7/8/8/8/8/8/K7 w - - 0 1"),
                                     parse_move_text("a7a8q")), "a8=Q+")
        self.assertEqual(san_to_move(pos, "a8=N"), parse_move_text("a7a8n"))

    def test_castling_text(self):
        pos = Position.from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        self.assertEqual(move_to_san(pos, parse_move_text("e1g1")), "O-O")
        self.assertEqual(move_to_san(pos, parse_move_text("e1c1")), "O-O-O")
        self.assertEqual(san_to_move(pos, "O-O-O"), parse_move_text("e1c1"))

    def test_illegal_san_is_rejected(self):
        with self.assertRaises(ValueError):
            san_to_move(Position(), "Ke2")
        with self.assertRaises(ValueError):
            san_to_move(Position(), "banana")

    def test_round_trip_every_legal_move(self):
        """For many positions: SAN -> move gives back the original move."""
        fens = [
            "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
            "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
            "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
            "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
        ]
        for fen in fens:
            pos = Position.from_fen(fen)
            moves = legal_moves(pos)
            sans = [move_to_san(pos, m, moves) for m in moves]
            self.assertEqual(len(set(sans)), len(sans), "two moves got the same SAN in " + fen)
            for move, san in zip(moves, sans):
                self.assertEqual(san_to_move(pos, san), move, san)


if __name__ == "__main__":
    unittest.main()
