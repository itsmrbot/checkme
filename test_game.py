import unittest

from engine import Position, parse_move_text
from game import (
    Game,
    OpeningTrainer,
    TIME_CONTROLS,
    captured_pieces,
    classify_loss,
    format_clock,
    material_balance,
)
from openings import OPENINGS, get_drill, opening_moves


def mv(text):
    return parse_move_text(text)


class ClockFormatTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_clock(600), "10:00")
        self.assertEqual(format_clock(83.4), "1:23")
        self.assertEqual(format_clock(60), "1:00")
        self.assertEqual(format_clock(9.94), "0:09.9")
        self.assertEqual(format_clock(0), "0:00.0")
        self.assertEqual(format_clock(-3), "0:00.0")

    def test_the_three_requested_time_formats_exist(self):
        seconds = [s for _name, s in TIME_CONTROLS]
        self.assertEqual(seconds, [None, 60, 180, 600])


class GradingTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(classify_loss(0), "best")
        self.assertEqual(classify_loss(30), "good")
        self.assertEqual(classify_loss(90), "inaccuracy")
        self.assertEqual(classify_loss(200), "mistake")
        self.assertEqual(classify_loss(600), "blunder")


class CapturedPiecesTests(unittest.TestCase):
    def test_start_position_nothing_captured(self):
        self.assertEqual(captured_pieces(Position()), {"white": [], "black": []})
        self.assertEqual(material_balance(Position()), 0)

    def test_after_a_capture(self):
        pos = Position()
        for t in ["e2e4", "d7d5", "e4d5"]:
            pos = pos.make_move(mv(t))
        self.assertEqual(captured_pieces(pos)["white"], ["p"])  # white captured a black pawn
        self.assertEqual(captured_pieces(pos)["black"], [])
        self.assertEqual(material_balance(pos), 1)

    def test_promotion_does_not_count_as_a_capture(self):
        # White has two queens and only seven pawns: one pawn promoted, nothing was captured.
        pos = Position.from_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPQ/RNBQKBNR w KQkq - 0 1")
        self.assertEqual(captured_pieces(pos)["black"], [])
        self.assertEqual(captured_pieces(pos)["white"], [])


class GameTests(unittest.TestCase):
    def test_play_records_san_and_history(self):
        game = Game()
        self.assertEqual(game.play(mv("e2e4")), "e4")
        self.assertEqual(game.play(mv("e7e5")), "e5")
        self.assertEqual(game.sans, ["e4", "e5"])
        self.assertEqual(game.ply, 2)
        self.assertTrue(game.learner_to_move())  # white to move again, learner is white

    def test_illegal_move_is_rejected(self):
        with self.assertRaises(ValueError):
            Game().play(mv("e2e5"))

    def test_checkmate_gives_the_win_to_the_mating_side(self):
        game = Game()
        for t in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            game.play(mv(t))
        self.assertTrue(game.is_over)
        self.assertEqual(game.result, {"winner": "black", "reason": "checkmate"})
        self.assertEqual(game.outcome(), "loss")  # learner is white
        self.assertEqual(game.result_text(), ("You lost", "Checkmate"))
        self.assertEqual(Game(learner_white=False).outcome(), None)

    def test_stalemate_is_a_draw(self):
        game = Game(Position.from_fen("k7/8/2Q5/8/8/8/8/2K5 w - - 0 1"))
        game.play(mv("c6b6"))
        self.assertEqual(game.result, {"winner": None, "reason": "stalemate"})
        self.assertEqual(game.outcome(), "draw")

    def test_threefold_repetition(self):
        game = Game()
        for t in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
            game.play(mv(t))
        self.assertEqual(game.result, {"winner": None, "reason": "threefold repetition"})

    def test_undo_goes_back_to_the_learners_turn(self):
        game = Game()
        game.play(mv("e2e4"))
        game.play(mv("e7e5"))
        game.play(mv("g1f3"))
        game.play(mv("b8c6"))
        self.assertEqual(game.undo(), 2)  # the computer's move and yours
        self.assertEqual(game.sans, ["e4", "e5"])
        self.assertEqual(game.undo(), 2)
        self.assertEqual(game.sans, [])
        self.assertEqual(game.undo(), 0)

    def test_undo_clears_a_finished_game(self):
        game = Game()
        for t in ["f2f3", "e7e5", "g2g4", "d8h4"]:
            game.play(mv(t))
        game.undo()
        self.assertFalse(game.is_over)

    def test_resign(self):
        game = Game(learner_white=True)
        game.resign()
        self.assertEqual(game.result["winner"], "black")
        self.assertEqual(game.outcome(), "loss")

    def test_moves_between_lists_all_promotions(self):
        game = Game(Position.from_fen("8/P6k/8/8/8/8/8/K7 w - - 0 1"))
        self.assertEqual(len(game.moves_between(8, 0)), 4)


class ClockTests(unittest.TestCase):
    def test_clock_waits_for_the_first_move(self):
        game = Game(time_control=60)
        game.tick(5)
        self.assertEqual(game.clock, {"white": 60, "black": 60})

    def test_only_the_side_to_move_loses_time(self):
        game = Game(time_control=60)
        game.play(mv("e2e4"))
        game.tick(5)
        self.assertEqual(game.clock, {"white": 60, "black": 55})
        game.play(mv("e7e5"))
        game.tick(2)
        self.assertEqual(game.clock, {"white": 58, "black": 55})

    def test_running_out_of_time_loses(self):
        game = Game(time_control=60)
        game.play(mv("e2e4"))
        game.tick(61)
        self.assertEqual(game.result, {"winner": "white", "reason": "time"})
        self.assertEqual(game.clock["black"], 0)
        self.assertEqual(game.outcome(), "win")

    def test_timeout_against_a_bare_king_is_a_draw(self):
        game = Game(Position.from_fen("8/8/4k3/8/8/8/8/R3K3 b - - 0 1"), time_control=60)
        game.play(mv("e6d6"))
        game.clock["white"] = 1
        game.tick(2)  # white (with a rook) runs out; black only has a king -> cannot be mated by flag
        self.assertEqual(game.result["winner"], None)

    def test_no_clock_means_no_ticking(self):
        game = Game()
        game.play(mv("e2e4"))
        game.tick(1000)
        self.assertIsNone(game.clock)
        self.assertFalse(game.is_over)

    def test_every_time_control_can_start_a_game(self):
        for _name, seconds in TIME_CONTROLS:
            game = Game(time_control=seconds)
            self.assertEqual(game.clock is not None, seconds is not None)


class OpeningTrainerTests(unittest.TestCase):
    def setUp(self):
        self.opening = OPENINGS[0]
        self.line = opening_moves(self.opening)
        self.trainer = OpeningTrainer(self.opening, self.line, learner_white=True)

    def test_whose_turn(self):
        self.assertTrue(self.trainer.is_learner_ply(0))
        self.assertFalse(self.trainer.is_learner_ply(1))
        black = OpeningTrainer(self.opening, self.line, learner_white=False)
        self.assertTrue(black.is_learner_ply(1))

    def test_check_and_finish(self):
        self.assertTrue(self.trainer.check(0, mv("e2e4")))
        self.assertFalse(self.trainer.check(0, mv("d2d4")))
        self.assertFalse(self.trainer.is_finished(len(self.line) - 1))
        self.assertTrue(self.trainer.is_finished(len(self.line)))
        self.assertIsNone(self.trainer.expected(len(self.line)))

    def test_comments_and_stars(self):
        self.assertIn("centre", self.trainer.comment(0))
        self.assertIsNone(self.trainer.comment(1))
        self.assertEqual(self.trainer.stars(), 3)
        self.trainer.mistakes = 2
        self.assertEqual(self.trainer.stars(), 2)
        self.trainer.mistakes = 5
        self.assertEqual(self.trainer.stars(), 1)

    def test_playing_the_whole_line_in_a_game(self):
        game = Game(kind="opening", trainer=self.trainer)
        for move in self.line:
            game.play(move)
        self.assertEqual(game.ply, len(self.line))


class DrillTests(unittest.TestCase):
    def test_promotion_drill_ends_on_promotion(self):
        drill = get_drill("kpk")
        game = Game(Position.from_fen(drill.fen), kind="endgame", drill=drill)
        game.play(mv("d6e6"))
        game.play(mv("d8e8"))
        game.play(mv("d5d6"))
        game.play(mv("e8d8"))
        game.play(mv("d6d7"))
        game.play(mv("d8c7"))
        game.play(mv("e6e7"))
        game.play(mv("c7c6"))
        self.assertFalse(game.is_over)
        game.play(mv("d7d8q"))
        self.assertTrue(game.is_over)
        self.assertEqual(game.outcome(), "win")
        self.assertEqual(game.result_text()[0], "Drill complete!")

    def test_mate_drill_needs_checkmate(self):
        drill = get_drill("kqk")
        game = Game(Position.from_fen("7k/8/5K2/8/8/8/8/6Q1 w - - 0 1"), kind="endgame", drill=drill)
        game.play(mv("g1g7"))
        self.assertEqual(game.result["reason"], "checkmate")
        self.assertEqual(game.result_text()[0], "Drill complete!")


if __name__ == "__main__":
    unittest.main()
