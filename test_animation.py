import unittest

from animation import (
    blend,
    clamp,
    ease_in_out_cubic,
    ease_out_back,
    lerp,
    progress,
    pulse,
    screen_to_square,
    square_to_screen,
)


class MathHelperTests(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(clamp(-1), 0)
        self.assertEqual(clamp(2), 1)
        self.assertEqual(clamp(0.4), 0.4)

    def test_lerp(self):
        self.assertEqual(lerp(10, 20, 0), 10)
        self.assertEqual(lerp(10, 20, 1), 20)
        self.assertEqual(lerp(10, 20, 0.5), 15)

    def test_progress(self):
        self.assertEqual(progress(5, 5, 2), 0)
        self.assertEqual(progress(5, 6, 2), 0.5)
        self.assertEqual(progress(5, 99, 2), 1)
        self.assertEqual(progress(5, 6, 0), 1)

    def test_easing_starts_and_ends_correctly(self):
        for ease in (ease_in_out_cubic, ease_out_back):
            self.assertAlmostEqual(ease(0), 0)
            self.assertAlmostEqual(ease(1), 1)

    def test_ease_in_out_is_slow_at_the_start(self):
        self.assertLess(ease_in_out_cubic(0.1), 0.1)
        self.assertAlmostEqual(ease_in_out_cubic(0.5), 0.5)

    def test_ease_out_back_overshoots(self):
        self.assertGreater(max(ease_out_back(i / 100) for i in range(101)), 1.0)

    def test_pulse_stays_between_0_and_1(self):
        for i in range(50):
            self.assertTrue(0 <= pulse(i * 0.1) <= 1)


class ColourTests(unittest.TestCase):
    def test_blend(self):
        self.assertEqual(blend("#000000", "#ffffff", 0), "#000000")
        self.assertEqual(blend("#000000", "#ffffff", 1), "#ffffff")
        self.assertEqual(blend("#000000", "#ffffff", 0.5), "#808080")
        self.assertEqual(blend("#ff0000", "#0000ff", 0.5), "#800080")


class BoardPositionTests(unittest.TestCase):
    def test_square_to_screen(self):
        self.assertEqual(square_to_screen(0, 80), (0, 0))  # a8 is top-left
        self.assertEqual(square_to_screen(63, 80), (560, 560))  # h1 is bottom-right

    def test_square_to_screen_flipped(self):
        self.assertEqual(square_to_screen(0, 80, flipped=True), (560, 560))
        self.assertEqual(square_to_screen(63, 80, flipped=True), (0, 0))

    def test_screen_to_square(self):
        self.assertEqual(screen_to_square(5, 5, 80), 0)
        self.assertEqual(screen_to_square(635, 635, 80), 63)
        self.assertEqual(screen_to_square(4 * 80 + 10, 6 * 80 + 10, 80), 52)  # e2

    def test_screen_to_square_off_board(self):
        self.assertIsNone(screen_to_square(-1, 10, 80))
        self.assertIsNone(screen_to_square(10, 640, 80))

    def test_round_trip(self):
        for flipped in (False, True):
            for square in range(64):
                x, y = square_to_screen(square, 80, flipped)
                self.assertEqual(screen_to_square(x + 40, y + 40, 80, flipped), square)


if __name__ == "__main__":
    unittest.main()
