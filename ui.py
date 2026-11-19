"""A tiny "immediate mode" UI toolkit for the checkme window.

The whole app is drawn on ONE tkinter Canvas. Every frame we clear the canvas and draw
everything again; buttons are drawn with ui.button(), which also remembers where the
button is so a mouse click can find it. This keeps the code simple and makes it easy
to animate things (like a button that glows when the mouse is over it).
"""

from animation import blend

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
BG = "#262421"
PANEL = "#302e2b"
PANEL_LIGHT = "#3b3936"
BUTTON = "#45433f"
BUTTON_HOVER = "#57544f"
FG = "#ececec"
MUTED = "#9b9a98"
ACCENT = "#81b64c"
ACCENT_HOVER = "#96cb5e"
DANGER = "#ca3431"
GOLD = "#f7c631"

# Board colour themes: light, dark, last-move light/dark, selected light/dark
THEMES = {
    "green": {"name": "Green", "light": "#eeeed2", "dark": "#769656",
              "last_light": "#f6f669", "last_dark": "#baca2b", "sel_light": "#ffe45c", "sel_dark": "#dcc22a"},
    "brown": {"name": "Brown", "light": "#f0d9b5", "dark": "#b58863",
              "last_light": "#cdd26a", "last_dark": "#aaa23a", "sel_light": "#f7ec74", "sel_dark": "#dac34a"},
    "blue": {"name": "Blue", "light": "#dee3e6", "dark": "#8ca2ad",
             "last_light": "#a8d4f0", "last_dark": "#6aa5cf", "sel_light": "#7fc4f5", "sel_dark": "#4a9fd6"},
}


def font(size, bold=False, family="Helvetica"):
    """A tkinter font tuple. The negative size means 'size in pixels', so it looks the same on every screen."""
    size = -int(size)
    return (family, size, "bold") if bold else (family, size)


def wrap_text(text, max_width, size):
    """Split text into lines that fit in max_width pixels (an estimate, based on the font size)."""
    max_chars = max(8, int(max_width / (size * 0.54)))
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split(" "):
            if not line:
                line = word
            elif len(line) + 1 + len(word) <= max_chars:
                line += " " + word
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


class UI:
    def __init__(self, canvas):
        self.c = canvas
        self.hot = []  # clickable regions from the last frame: (x1, y1, x2, y2, callback)
        self.mouse = (-1, -1)
        self.hover_amount = {}  # key -> 0..1, how "hovered" a button is (for smooth colour fades)

    # -- frame / mouse ------------------------------------------------------
    def begin_frame(self):
        self.hot = []

    def inside(self, x1, y1, x2, y2):
        mx, my = self.mouse
        return x1 <= mx <= x2 and y1 <= my <= y2

    def over_clickable(self):
        mx, my = self.mouse
        return any(x1 <= mx <= x2 and y1 <= my <= y2 for x1, y1, x2, y2, _cb, _key in self.hot)

    def add_hot(self, x1, y1, x2, y2, callback, key=None):
        self.hot.append((x1, y1, x2, y2, callback, key))

    def click(self, x, y):
        """Run the callback of the top-most clickable region under (x, y). Returns True if there was one."""
        for x1, y1, x2, y2, callback, _key in reversed(self.hot):
            if x1 <= x <= x2 and y1 <= y <= y2:
                callback()
                return True
        return False

    def press(self, key):
        """Click a button by its name (used by the tests). Returns True if the button exists and is enabled."""
        for _x1, _y1, _x2, _y2, callback, hot_key in self.hot:
            if hot_key == key:
                callback()
                return True
        return False

    def hover(self, key, x1, y1, x2, y2, enabled=True):
        target = 1.0 if enabled and self.inside(x1, y1, x2, y2) else 0.0
        amount = self.hover_amount.get(key, 0.0)
        amount += (target - amount) * 0.35
        self.hover_amount[key] = amount
        return amount

    # -- drawing -------------------------------------------------------------
    def rect(self, x1, y1, x2, y2, fill="", outline="", width=1):
        return self.c.create_rectangle(x1, y1, x2, y2, fill=fill, outline=outline, width=width)

    def round_rect(self, x1, y1, x2, y2, radius=10, fill="", outline="", width=1):
        r = radius
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
                  x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.c.create_polygon(points, smooth=True, fill=fill, outline=outline, width=width)

    def text(self, x, y, text, size=14, color=FG, anchor="center", bold=False):
        return self.c.create_text(x, y, text=text, font=font(size, bold), fill=color, anchor=anchor)

    def paragraph(self, x, y, text, width, size=13, color=FG, gap=4, bold=False, max_y=None):
        """Draw wrapped text starting at (x, y). Returns the y where the text ended."""
        for line in wrap_text(text, width, size):
            if max_y is not None and y + size > max_y:
                break
            self.text(x, y, line, size, color, "nw", bold)
            y += size + gap
        return y

    def button(self, key, x1, y1, x2, y2, label, callback, style="normal", enabled=True, size=13, selected=False):
        """A rounded button. style: 'normal', 'primary' (green), 'danger' (red)."""
        amount = self.hover(key, x1, y1, x2, y2, enabled)
        if style == "primary":
            base, hover, text_color = ACCENT, ACCENT_HOVER, "#ffffff"
        elif style == "danger":
            base, hover, text_color = "#7a2b29", DANGER, "#ffffff"
        else:
            base, hover, text_color = BUTTON, BUTTON_HOVER, FG
        if selected:
            base, hover, text_color = ACCENT, ACCENT_HOVER, "#ffffff"
        fill = blend(base, hover, amount)
        if not enabled:
            fill, text_color = blend(PANEL, BUTTON, 0.4), "#6d6c6a"
        self.round_rect(x1, y1, x2, y2, 8, fill=fill)
        self.text((x1 + x2) / 2, (y1 + y2) / 2, label, size, text_color, "center", True)
        if enabled:
            self.add_hot(x1, y1, x2, y2, callback, key)

    def card(self, key, x1, y1, x2, y2, callback=None, selected=False, lift=True):
        """A big clickable card (used for the home screen and lists). Returns the hover amount."""
        amount = self.hover(key, x1, y1, x2, y2, callback is not None)
        shift = -3 * amount if lift else 0
        fill = blend(PANEL, PANEL_LIGHT, amount)
        outline = ACCENT if selected else blend(PANEL, BUTTON, 0.6 + 0.4 * amount)
        self.round_rect(x1, y1 + shift, x2, y2 + shift, 12, fill=fill, outline=outline, width=3 if selected else 1)
        if callback:
            self.add_hot(x1, y1, x2, y2, callback, key)
        return amount

    def toggle_row(self, key, x, y, width, label, value, callback, caption=None):
        """A label with an On/Off switch on the right."""
        self.text(x, y + 14, label, 14, FG, "w", True)
        if caption:
            self.text(x, y + 34, caption, 11, MUTED, "w")
        self.button(key + "-on", x + width - 130, y, x + width - 66, y + 30, "On", lambda: callback(True),
                    selected=value is True, size=12)
        self.button(key + "-off", x + width - 62, y, x + width, y + 30, "Off", lambda: callback(False),
                    selected=value is False, size=12)

    def segmented(self, key, x, y, options, current, callback, cell_w, cell_h=30, gap=4, size=12):
        """A row of buttons where one is selected. options = list of (value, label)."""
        for index, (value, label) in enumerate(options):
            x1 = x + index * (cell_w + gap)
            self.button("{}-{}".format(key, index), x1, y, x1 + cell_w, y + cell_h, label,
                        lambda v=value: callback(v), selected=(value == current), size=size)
