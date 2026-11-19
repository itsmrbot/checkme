"""Small helper functions used by the animated chess window (gui.py).

They are plain functions with no tkinter inside, so they are easy to test.
"""

import math


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def lerp(start, end, t):
    """Go from start to end. t=0 gives start, t=1 gives end."""
    return start + (end - start) * t


def progress(start_time, now, duration):
    """How far along an animation is, from 0.0 (just started) to 1.0 (finished)."""
    if duration <= 0:
        return 1.0
    return clamp((now - start_time) / duration)


def ease_in_out_cubic(t):
    """Starts slowly, speeds up, then slows down again. Makes movement feel natural."""
    t = clamp(t)
    if t < 0.5:
        return 4 * t * t * t
    return 1 - ((-2 * t + 2) ** 3) / 2


def ease_out_back(t):
    """Goes a little past the end and settles back. Used for the game-over banner."""
    t = clamp(t)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def pulse(now, period=1.2):
    """A value that smoothly goes 0 -> 1 -> 0 over and over (one cycle per `period` seconds)."""
    return 0.5 + 0.5 * math.sin(2 * math.pi * now / period)


def hex_to_rgb(color):
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def blend(color_a, color_b, t):
    """Mix two '#rrggbb' colours. t=0 gives color_a, t=1 gives color_b."""
    t = clamp(t)
    a = hex_to_rgb(color_a)
    b = hex_to_rgb(color_b)
    mixed = [round(lerp(a[i], b[i], t)) for i in range(3)]
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def square_to_screen(square, size, flipped=False):
    """Top-left pixel position of a square. If flipped, the board is shown from black's side."""
    row, col = divmod(square, 8)
    if flipped:
        row, col = 7 - row, 7 - col
    return col * size, row * size


def screen_to_square(x, y, size, flipped=False):
    """Which square is under this pixel? Returns None if the click is off the board."""
    col = int(x // size)
    row = int(y // size)
    if not (0 <= row < 8 and 0 <= col < 8):
        return None
    if flipped:
        row, col = 7 - row, 7 - col
    return row * 8 + col
