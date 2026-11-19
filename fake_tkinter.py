"""A stand-in for tkinter that only records what is drawn.

It lets the tests run the whole checkme window without a screen, and (optionally) turn the
drawing into an SVG picture. Real tkinter is NOT needed to run test_app.py.
"""

import html
import sys
import types


class FakeCanvas:
    def __init__(self, master=None, width=0, height=0, bg="#000000", **kwargs):
        self.width, self.height, self.bg = width, height, bg
        self.items = []
        self.cursor = ""

    def pack(self, **kwargs):
        pass

    def bind(self, sequence, function):
        pass

    def delete(self, *args):
        self.items = []

    def config(self, **kwargs):
        self.cursor = kwargs.get("cursor", self.cursor)

    def create_rectangle(self, *coords, **kwargs):
        self.items.append(("rect", coords, kwargs))

    def create_oval(self, *coords, **kwargs):
        self.items.append(("oval", coords, kwargs))

    def create_text(self, *coords, **kwargs):
        self.items.append(("text", coords, kwargs))

    def create_polygon(self, *coords, **kwargs):
        points = coords[0] if len(coords) == 1 and isinstance(coords[0], (list, tuple)) else coords
        self.items.append(("poly", points, kwargs))


class FakeRoot:
    def __init__(self):
        self.queue = []
        self.destroyed = False

    def after(self, milliseconds, function):
        self.queue.append(function)

    def title(self, *args):
        pass

    def configure(self, **kwargs):
        pass

    def resizable(self, *args):
        pass

    def bind(self, *args):
        pass

    def winfo_screenheight(self):
        return 1080

    def destroy(self):
        self.destroyed = True

    def mainloop(self):
        pass


def install():
    """Make `import tkinter` give the fake one."""
    module = types.ModuleType("tkinter")
    module.Tk = FakeRoot
    module.Canvas = FakeCanvas
    module.TclError = Exception
    sys.modules["tkinter"] = module
    return module


def to_svg(canvas):
    """Turn what was drawn into an SVG picture (handy for looking at the screens in a browser)."""
    parts = ['<rect width="{}" height="{}" fill="{}"/>'.format(canvas.width, canvas.height, canvas.bg)]
    for kind, c, kw in canvas.items:
        fill = kw.get("fill") or "none"
        outline = kw.get("outline") or "none"
        width = kw.get("width", 1)
        if kind == "rect":
            x1, y1, x2, y2 = c
            parts.append('<rect x="{}" y="{}" width="{}" height="{}" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
                x1, y1, x2 - x1, y2 - y1, fill, outline, width))
        elif kind == "oval":
            x1, y1, x2, y2 = c
            parts.append('<ellipse cx="{}" cy="{}" rx="{}" ry="{}" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
                (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) / 2, (y2 - y1) / 2, fill, outline, width))
        elif kind == "poly":
            xs, ys = c[0::2], c[1::2]
            if kw.get("smooth"):
                parts.append('<rect x="{}" y="{}" width="{}" height="{}" rx="10" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
                    min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), fill, outline, width))
            else:
                parts.append('<polygon points="{}" fill="{}" stroke="{}" stroke-width="{}"/>'.format(
                    " ".join("{},{}".format(x, y) for x, y in zip(xs, ys)), fill, outline, width))
        else:
            x, y = c
            font = kw["font"]
            weight = "bold" if len(font) > 2 and "bold" in font[2] else "normal"
            anchor = kw.get("anchor", "center")
            text_anchor = "end" if anchor in ("e", "ne", "se") else ("start" if "w" in anchor else "middle")
            baseline = "hanging" if anchor.startswith("n") else ("auto" if anchor.startswith("s") else "central")
            parts.append('<text x="{}" y="{}" font-family="{}, DejaVu Sans, sans-serif" font-size="{}" font-weight="{}" '
                         'text-anchor="{}" dominant-baseline="{}" fill="{}">{}</text>'.format(
                             x, y, font[0], abs(font[1]), weight, text_anchor, baseline, fill, html.escape(kw["text"])))
    return '<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}">{}</svg>'.format(
        canvas.width, canvas.height, "".join(parts))
