import unittest

from engine import Position, game_status, is_in_check, legal_moves
from notation import move_to_san
from openings import (
    ENDGAMES,
    OPENINGS,
    book_move,
    opening_end_position,
    opening_moves,
    opening_name,
)


class OpeningLineTests(unittest.TestCase):
    def test_there_are_enough_openings_for_both_colours(self):
        self.assertGreaterEqual(len(OPENINGS), 12)
        self.assertGreaterEqual(len([o for o in OPENINGS if o.side == "white"]), 5)
        self.assertGreaterEqual(len([o for o in OPENINGS if o.side == "black"]), 5)

    def test_ids_are_unique(self):
        ids = [o.id for o in OPENINGS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_line_is_legal(self):
        for opening in OPENINGS:
            moves = opening_moves(opening)  # raises ValueError on an illegal move
            self.assertGreaterEqual(len(moves), 7, opening.name)
            end = opening_end_position(opening)
            self.assertEqual(game_status(end), "playing", opening.name)

    def test_comment_labels_match_the_moves(self):
        """A label like '4.c3' must really be White's 4th move c3."""
        for opening in OPENINGS:
            pos = Position()
            sans = []
            for move in opening_moves(opening):
                sans.append(move_to_san(pos, move).rstrip("+#"))
                pos = pos.make_move(move)
            self.assertTrue(opening.comments, opening.name)
            for ply, (san, text) in opening.comments.items():
                self.assertLess(ply, len(sans), opening.name)
                self.assertEqual(sans[ply], san, "{}: comment for ply {}".format(opening.name, ply))
                self.assertTrue(text.strip())

    def test_every_opening_has_teaching_text(self):
        for opening in OPENINGS:
            self.assertTrue(opening.idea and opening.structure, opening.name)
            self.assertGreaterEqual(len(opening.plans), 3, opening.name)

    def test_side_matches_who_the_line_is_for(self):
        for opening in OPENINGS:
            self.assertIn(opening.side, ("white", "black"))


class OpeningNameTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(opening_name(["e4"]), "King's Pawn Game")
        self.assertEqual(opening_name(["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"]), "Ruy Lopez: Morphy Defense")
        self.assertEqual(opening_name(["d4", "d5", "c4", "e6"]), "Queen's Gambit Declined")
        self.assertEqual(opening_name(["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]),
                         "Sicilian Defense: Najdorf")

    def test_checks_in_san_are_ignored(self):
        self.assertEqual(opening_name(["e4", "c5+"]), "Sicilian Defense")

    def test_unknown_opening(self):
        self.assertIsNone(opening_name(["a3"]))
        self.assertIsNone(opening_name([]))


class BookTests(unittest.TestCase):
    def test_start_position_has_book_moves(self):
        for _ in range(20):
            self.assertIn(book_move(Position()), legal_moves(Position()))

    def test_book_follows_known_lines(self):
        pos = Position()
        for move in opening_moves(OPENINGS[0])[:4]:
            self.assertIsNotNone(book_move(pos))
            pos = pos.make_move(move)

    def test_out_of_book_returns_none(self):
        pos = Position.from_fen("8/8/4k3/8/8/8/8/Q3K3 w - - 0 1")
        self.assertIsNone(book_move(pos))


class EndgameDrillTests(unittest.TestCase):
    def test_every_drill_is_valid(self):
        self.assertGreaterEqual(len(ENDGAMES), 5)
        for drill in ENDGAMES:
            pos = Position.from_fen(drill.fen)
            self.assertEqual(pos.white_to_move, drill.learner_white, drill.name)
            self.assertEqual(game_status(pos), "playing", drill.name)
            self.assertFalse(is_in_check(pos, not pos.white_to_move), drill.name + ": the side NOT to move is in check")
            self.assertIn(drill.goal, ("mate", "promote"))
            self.assertGreaterEqual(len(drill.tips), 3)
            self.assertIn(pos.board.count("K"), (1,))
            self.assertIn(pos.board.count("k"), (1,))

    def test_mate_drills_have_no_pawns_and_promote_drills_have_a_pawn(self):
        for drill in ENDGAMES:
            has_pawn = "P" in Position.from_fen(drill.fen).board
            self.assertEqual(has_pawn, drill.goal == "promote", drill.name)


if __name__ == "__main__":
    unittest.main()
