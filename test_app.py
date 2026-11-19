"""Runs the whole checkme window without a screen, using fake_tkinter (real tkinter is not needed)."""

import json
import os
import tempfile
import time
import unittest

import fake_tkinter

fake_tkinter.install()

import app as app_module  # noqa: E402
from animation import square_to_screen  # noqa: E402
from engine import Position, parse_move_text  # noqa: E402
from game import Game  # noqa: E402
from openings import OPENINGS, opening_moves  # noqa: E402


class AppTest(unittest.TestCase):
    def setUp(self):
        self.clock = [5000.0]
        app_module.now = lambda: self.clock[0]
        self.root = fake_tkinter.FakeRoot()
        self.settings_file = os.path.join(tempfile.mkdtemp(), "settings.json")
        self.app = app_module.CheckMeApp(self.root, settings_path=self.settings_file)

    def step(self, dt=0.016, n=1):
        for _ in range(n):
            self.clock[0] += dt
            callbacks, self.root.queue = self.root.queue, []
            for callback in callbacks:
                callback()

    def wait_for(self, condition, label=""):
        for _ in range(4000):
            self.step()
            if condition():
                return
            time.sleep(0.002)
        self.fail("timed out waiting for " + label)

    def idle(self):
        a = self.app
        return a.anim is None and not a.thinking and not a.quality_pending and a.script_due is None

    def click_square(self, sq):
        a = self.app
        x, y = square_to_screen(sq, a.sq, a.flipped)
        a._on_click(type("E", (), {"x": a.bl + x + a.sq // 2, "y": a.bt + y + a.sq // 2})())

    def click_move(self, text):
        move = parse_move_text(text)
        self.click_square(move[0])
        self.click_square(move[1])

    def test_setup_screens_and_time_formats(self):
        self.step(n=3)
        self.assertTrue(self.app.ui.press("home-play"))
        self.step(n=2)
        for key, seconds in (("time-1", 60), ("time-2", 180), ("time-3", 600)):
            self.assertTrue(self.app.ui.press(key))
            self.assertEqual(self.app.setup["time"], seconds)
        self.assertTrue(self.app.ui.press("level-7"))
        self.assertEqual(self.app.setup["level"], 7)

    def test_play_move_and_clock(self):
        a = self.app
        a.open_setup("play")
        a.setup.update(level=1, side="white", assist=False, time=60)
        a.start_session()
        self.step(n=3)
        self.assertEqual(a.game.clock, {"white": 60, "black": 60})
        self.click_move("e2e4")
        self.wait_for(lambda: len(a.game.moves) >= 2 and self.idle(), "computer reply")
        self.assertEqual(a.game.sans[0], "e4")
        self.assertFalse(a.ui.press("g-Hint"))  # no hints without assist

    def test_opening_line_can_be_learned(self):
        a = self.app
        a.settings["anim"] = "off"
        for index, opening in enumerate(OPENINGS):
            a.go_home()
            a.open_setup("opening")
            a.setup.update(index=index, assist=True, time=None)
            a.start_session()
            g = a.game
            trainer = g.trainer
            guard = 0
            while not a.session_done and guard < 400:
                guard += 1
                self.step(0.1)
                if self.idle() and trainer.is_learner_ply(g.ply) and not a.session_done and not g.is_over:
                    move = trainer.expected(g.ply)
                    self.click_square(move[0])
                    self.click_square(move[1])
            self.assertTrue(a.session_done, opening.name)
            self.assertEqual(g.ply, len(opening_moves(opening)), opening.name)

    def test_promotion_chooser_and_stale_click(self):
        a = self.app
        g = Game(Position.from_fen("8/P6k/8/8/8/8/8/K7 w - - 0 1"), True, 1, True, "play", "Promotion test")
        a._begin_game(g)
        self.step(n=3)
        self.click_move("a7a8")
        self.assertIsNotNone(a.promo)
        self.step(n=3)  # draw the chooser so its buttons exist
        x, y = a._square_xy(parse_move_text("a8a8")[0])
        a._on_click(type("E", (), {"x": x + a.sq // 2, "y": y + a.sq * 1.5})())  # the knight
        self.assertIsNotNone(a.anim)
        self.wait_for(lambda: a.anim is None, "animation")
        self.assertTrue(g.sans[0].startswith("a8=N"))

    def test_settings_are_saved_and_reloaded(self):
        a = self.app
        a.open_settings()
        self.step(n=2)
        self.assertTrue(a.ui.press("theme-1"))
        self.assertTrue(a.ui.press("premove-off"))
        with open(self.settings_file) as handle:
            saved = json.load(handle)
        self.assertEqual(saved["theme"], "brown")
        self.assertFalse(saved["premove"])
        again = app_module.CheckMeApp(fake_tkinter.FakeRoot(), settings_path=self.settings_file)
        self.assertEqual(again.settings["theme"], "brown")

    def test_resign_and_rematch(self):
        a = self.app
        a.open_setup("play")
        a.setup.update(level=1, side="white", assist=False, time=None)
        a.start_session()
        self.step(n=3)
        old = a.game
        self.assertTrue(a.ui.press("g-Resign"))
        self.assertTrue(old.is_over)
        self.step(n=60)
        self.assertTrue(a.ui.press("banner-0"))
        self.assertIsNot(a.game, old)


if __name__ == "__main__":
    unittest.main()
