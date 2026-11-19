"""checkme - the window. Everything is drawn on one tkinter Canvas (see ui.py).

Screens:  home  ->  setup (pick what to practise)  ->  game
          settings (premove, board theme ...) can be opened from home or from a game.

The computer thinks in background threads so the window never freezes.
"""

import json
import math
import queue
import random
import sys
import threading
import time
import tkinter as tk
from pathlib import Path

import ui as U
from animation import blend, ease_in_out_cubic, ease_out_back, lerp, progress, pulse, screen_to_square, square_to_screen
from engine import Position, is_in_check, is_white_piece, square_name
from game import (
    QUALITY,
    TIME_CONTROLS,
    Game,
    OpeningTrainer,
    captured_pieces,
    classify_loss,
    format_clock,
    material_balance,
)
from notation import move_to_san
from openings import (
    ENDGAMES,
    OPENINGS,
    book_move,
    opening_end_position,
    opening_moves,
    opening_name,
)
from search import LEVELS, analyse, clamp_score, level_name, pick_engine_move, score_after

# ---------------------------------------------------------------------------
# Settings you can change
# ---------------------------------------------------------------------------
PANEL_W = 300
MARGIN = 16
EVAL_W = 22
STRIP_H = 44
MIN_THINK = 0.45  # the computer waits at least this long so replies don't feel instant
FRAME_FAST = 16  # ms between frames while something moves (about 60 fps)
FRAME_IDLE = 33  # ms between frames otherwise (about 30 fps)

SETTINGS_FILE = Path.home() / ".checkme_settings.json"
DEFAULT_SETTINGS = {"premove": True, "dots": True, "coords": True, "theme": "green", "anim": "normal"}
ANIM_SPEED = {"slow": 1.7, "normal": 1.0, "fast": 0.5, "off": 0.0}

CATEGORIES = [
    ("play", "Play", "A full game against the computer. Pick one of 9 levels and a time control.", "♞"),
    ("opening", "Openings", "Learn opening lines move by move, with explanations. Switch Assist off to test yourself.", "♝"),
    ("middlegame", "Middlegame", "Start from real middlegame positions and play to the plans of the opening.", "♛"),
    ("endgame", "Endgames", "Drill the key endgames: checkmates, key squares and the Lucena position.", "♚"),
]
CATEGORY_TITLES = {c[0]: c[1] for c in CATEGORIES}

GLYPHS = {"k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}
if sys.platform.startswith("win"):
    PIECE_FONT = "Segoe UI Symbol"
elif sys.platform == "darwin":
    PIECE_FONT = "Apple Symbols"
else:
    PIECE_FONT = "DejaVu Sans"

WHITE_FILL, WHITE_EDGE, BLACK_FILL = "#fafafa", "#2a2a2a", "#1f1f1f"
CHECK_RED = "#e8403a"
PREMOVE_RED = "#d6403b"


def now():
    """Current time in seconds (a function so tests can replace it)."""
    return time.monotonic()


# ---------------------------------------------------------------------------
# Jobs that run in background threads (they only compute, they never touch the window)
# ---------------------------------------------------------------------------
def _engine_job(pos, level, keys, seconds_left, use_book):
    if use_book:
        move = book_move(pos)
        if move:
            return move
    return pick_engine_move(pos, level, keys, seconds_left)


def _analysis_job(pos, keys):
    move, score = analyse(pos, 4, 1.5, keys)
    return {"move": move, "score": score}


def _quality_job(prev_pos, move, best_info, keys):
    """How good was the move that was just played? Compare it with the best move."""
    if best_info is None:
        best_move, best_score = analyse(prev_pos, 3, 0.8, keys)
    else:
        best_move, best_score = best_info["move"], best_info["score"]
    if best_move == move:
        played = best_score
    else:
        played = score_after(prev_pos, move, 3, 0.8, keys)
    return {"best_move": best_move, "best_score": best_score, "played": played}


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------
class CheckMeApp:
    def __init__(self, root, settings_path=SETTINGS_FILE):
        self.root = root
        self.settings_path = Path(settings_path)

        # Size of everything, based on the screen height so it fits laptops too
        screen_height = root.winfo_screenheight()
        self.sq = max(48, min(80, ((screen_height - 280) // 8) // 4 * 4))
        self.board_px = self.sq * 8
        self.bl = MARGIN + EVAL_W + 10  # board left
        self.bt = MARGIN + STRIP_H  # board top
        self.px = self.bl + self.board_px + 16  # panel left
        self.win_w = self.px + PANEL_W + MARGIN
        self.win_h = MARGIN + STRIP_H + self.board_px + STRIP_H + 40 + MARGIN

        root.title("checkme - chess practice")
        root.configure(bg=U.BG)
        root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=self.win_w, height=self.win_h, bg=U.BG, highlightthickness=0)
        self.canvas.pack()
        self.ui = U.UI(self.canvas)

        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-2>", self._on_right_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        for key, action in (("<Left>", lambda e: self._review_step(-1)), ("<Right>", lambda e: self._review_step(1)),
                            ("<Home>", lambda e: self._review_to(0)), ("<End>", lambda e: self._review_to(None)),
                            ("<Escape>", lambda e: self._escape())):
            root.bind(key, action)

        self.settings = self._load_settings()
        self.screen = "home"
        self.previous_screen = "home"
        self.setup = {"category": "play", "index": 0, "level": 5, "side": "white", "assist": True, "time": None}
        self.last_cfg = None

        self.results = queue.Queue()
        self.token = 0  # lets us ignore answers from searches that were cancelled
        self.game = None
        self._reset_game_state()

        self._last_time = now()
        self._cache = {}
        self._tick()

    # =======================================================================
    # Settings
    # =======================================================================
    def _load_settings(self):
        settings = dict(DEFAULT_SETTINGS)
        try:
            data = json.loads(self.settings_path.read_text())
            for key in DEFAULT_SETTINGS:
                if key in data and type(data[key]) is type(DEFAULT_SETTINGS[key]):
                    settings[key] = data[key]
        except (OSError, ValueError):
            pass
        if settings["theme"] not in U.THEMES:
            settings["theme"] = "green"
        if settings["anim"] not in ANIM_SPEED:
            settings["anim"] = "normal"
        return settings

    def _save_settings(self):
        try:
            self.settings_path.write_text(json.dumps(self.settings, indent=2))
        except OSError:
            pass  # not being able to save settings is not a problem

    def set_setting(self, key, value):
        self.settings[key] = value
        if key == "premove" and not value:
            self.premove = None
            self.pre_selected = None
        self._save_settings()

    # =======================================================================
    # Navigation
    # =======================================================================
    def go_home(self):
        self._cancel_jobs()
        self.game = None
        self._reset_game_state()
        self.screen = "home"

    def open_setup(self, category):
        self.setup["category"] = category
        self.setup["index"] = 0
        self.screen = "setup"

    def open_settings(self):
        self.previous_screen = self.screen
        self.screen = "settings"

    def close_settings(self):
        self.screen = self.previous_screen

    def set_setup(self, key, value):
        self.setup[key] = value

    # =======================================================================
    # Starting a game
    # =======================================================================
    def start_session(self, cfg=None):
        cfg = dict(cfg or self.setup)
        self.last_cfg = cfg
        category, level, assist, clock = cfg["category"], cfg["level"], cfg["assist"], cfg["time"]
        if category == "play":
            side = cfg["side"] if cfg["side"] != "random" else random.choice(["white", "black"])
            game = Game(Position(), side == "white", level, assist, "play", "Play vs computer", clock)
        elif category == "opening":
            opening = OPENINGS[cfg["index"]]
            white = opening.side == "white"
            trainer = OpeningTrainer(opening, opening_moves(opening), white)
            game = Game(Position(), white, level, assist, "opening", opening.name, clock, trainer=trainer)
        elif category == "middlegame":
            opening = OPENINGS[cfg["index"]]
            game = Game(opening_end_position(opening), opening.side == "white", level, assist, "middlegame",
                        "Middlegame: " + opening.name, clock)
            game.opening = opening
        else:
            drill = ENDGAMES[cfg["index"]]
            game = Game(Position.from_fen(drill.fen), drill.learner_white, level, assist, "endgame",
                        drill.name, clock, drill=drill)
        self._begin_game(game)

    def _begin_game(self, game):
        self._cancel_jobs()
        self.game = game
        self._reset_game_state()
        self.flipped = not game.learner_white
        self.screen = "game"
        self.message = None

    def _reset_game_state(self):
        self.anim = None  # the pieces that are sliding right now
        self.effects = []  # ripples after captures / promotions
        self.selected = None
        self.targets = []
        self.premove = None  # (start, end) queued while waiting for the computer
        self.pre_selected = None
        self.promo = None  # promotion chooser {"start", "end", "moves"}
        self.hint = None
        self.hint_wanted = False
        self.message = None  # {"text", "color"}
        self.banner = None
        self.view = None  # None = live position, number = reviewing that position
        self.flipped = False
        self.error_flash = None
        self.eval_target = 0.0  # centipawns, white's point of view
        self.eval_shown = 0.0
        self.analysis = None
        self.analysis_busy = False
        self.thinking = False
        self.think_start = 0.0
        self.engine_move = None
        self.quality_pending = None  # context of the move being graded
        self.script_due = None  # when the book opponent plays its next move
        self.session_done = False

    # =======================================================================
    # Background jobs
    # =======================================================================
    def _spawn(self, kind, function, *args):
        token = self.token

        def run():
            try:
                result = function(*args)
            except Exception as error:  # never let a thread die silently
                result = error
            self.results.put((kind, token, result))

        threading.Thread(target=run, daemon=True).start()

    def _cancel_jobs(self):
        self.token += 1
        self.thinking = False
        self.engine_move = None
        self.quality_pending = None
        self.analysis_busy = False
        self.script_due = None

    def _poll_jobs(self):
        g = self.game
        try:
            while True:
                kind, token, result = self.results.get_nowait()
                if token != self.token or g is None:
                    continue
                if kind == "engine":
                    if isinstance(result, Exception) or result is None:
                        legal = g.legal()
                        result = random.choice(legal) if legal else None
                    self.engine_move = result
                elif kind == "analysis":
                    self.analysis_busy = False
                    if not isinstance(result, Exception):
                        self._store_analysis(result)
                elif kind == "quality":
                    ctx, self.quality_pending = self.quality_pending, None
                    if not isinstance(result, Exception) and ctx:
                        self._store_quality(ctx, result)
        except queue.Empty:
            pass

    def _eval_for_white(self, score_for_learner):
        score = clamp_score(score_for_learner)
        return score if self.game.learner_white else -score

    def _store_analysis(self, result):
        g = self.game
        key = self._analysis_key
        self.analysis = {"key": key, "move": result["move"], "score": result["score"]}
        if key == g.pos.key():
            self.eval_target = self._eval_for_white(result["score"])
            if self.hint_wanted:
                self.hint_wanted = False
                self._show_hint(result["move"])

    def _store_quality(self, ctx, result):
        g = self.game
        best, played = clamp_score(result["best_score"]), clamp_score(result["played"])
        loss = max(0, best - played)
        label = "best" if ctx["move"] == result["best_move"] else classify_loss(loss)
        g.quality[ctx["ply"]] = {"label": label, "loss": loss}
        text = QUALITY[label][0]
        if label in ("inaccuracy", "mistake", "blunder") and result["best_move"]:
            text += ". Better was " + move_to_san(ctx["prev_pos"], result["best_move"])
        self._set_message(text, QUALITY[label][2])
        self.eval_target = self._eval_for_white(result["played"])

    def _maybe_start_analysis(self):
        g = self.game
        if not g.assist or g.kind == "opening" or self.analysis_busy:
            return
        if self.analysis and self.analysis["key"] == g.pos.key():
            return
        self.analysis_busy = True
        self._analysis_key = g.pos.key()
        self._spawn("analysis", _analysis_job, g.pos, g.history_keys)

    # =======================================================================
    # Making moves
    # =======================================================================
    def _speed(self):
        return ANIM_SPEED[self.settings["anim"]]

    def _apply_move(self, move, by_learner):
        """Play the move in the game and start the sliding animation."""
        g = self.game
        if g.is_over:
            return
        start, end, promo = move
        board = g.pos.board
        piece, captured = board[start], board[end]
        movers = [(piece, start, end)]
        if piece in "Kk" and abs(end - start) == 2:  # castling: the rook slides too
            if end > start:
                movers.append((board[start + 3], start + 3, start + 1))
            else:
                movers.append((board[start - 4], start - 4, start - 1))
        if piece in "Pp" and captured == "." and (start & 7) != (end & 7):
            captured = "p"  # en passant
        prev_pos = g.pos
        best_info = self.analysis if self.analysis and self.analysis["key"] == prev_pos.key() else None
        keys = g.history_keys
        g.play(move)

        distance = math.hypot(start // 8 - end // 8, start % 8 - end % 8)
        self.anim = {
            "board_before": board[:], "movers": movers, "end": end, "captured": captured,
            "promoted": bool(promo), "t0": now(), "duration": max(0.001, (0.2 + 0.04 * distance) * self._speed()),
            "by_learner": by_learner, "prev_pos": prev_pos, "move": move, "best_info": best_info, "keys": keys,
        }
        self.selected, self.targets, self.hint, self.promo, self.view = None, [], None, None, None
        self.hint_wanted = False

    def _finish_anim(self):
        a, self.anim = self.anim, None
        g = self.game
        if a["promoted"]:
            self.effects.append({"square": a["end"], "t0": now(), "duration": 0.6, "color": "#f7c948"})
        elif a["captured"] != ".":
            self.effects.append({"square": a["end"], "t0": now(), "duration": 0.5, "color": CHECK_RED})
        if g.is_over:
            self._on_game_over()
            return

        ply = g.ply - 1
        if g.kind == "opening":
            comment = g.trainer.comment(ply)
            if g.assist and comment:
                self._set_message(comment, U.FG)
            elif a["by_learner"]:
                self._set_message("Correct!", U.ACCENT)
            if g.trainer.is_finished(g.ply):
                self._session_complete()
        elif a["by_learner"] and g.assist:
            self.quality_pending = {"ply": ply, "move": a["move"], "prev_pos": a["prev_pos"]}
            self._spawn("quality", _quality_job, a["prev_pos"], a["move"], a["best_info"], a["keys"])

    def _try_learner_move(self, start, end):
        g = self.game
        moves = g.moves_between(start, end)
        if not moves:
            return
        if len(moves) > 1:  # promotion: let the player choose the piece
            self.promo = {"start": start, "end": end, "moves": moves}
            return
        self._commit_learner_move(moves[0])

    def _commit_learner_move(self, move):
        g = self.game
        if g.kind == "opening" and not g.trainer.check(g.ply, move):
            g.trainer.mistakes += 1
            tip = " Press Hint if you are stuck." if g.assist else " Try again."
            self._set_message("That is not the book move." + tip, U.DANGER)
            self.error_flash = {"squares": (move[0], move[1]), "t0": now()}
            self.selected, self.targets = None, []
            return
        self._apply_move(move, True)

    def _choose_promotion(self, move):
        if not self.promo or self.game.is_over or self.anim:
            return  # a stale click (the chooser has already closed)
        self._commit_learner_move(move)

    def _set_message(self, text, color=U.FG):
        self.message = {"text": text, "color": color}

    # -- computer / book moves -------------------------------------------------
    def _start_engine(self):
        g = self.game
        self.thinking = True
        self.think_start = now()
        self.engine_move = None
        self._spawn("engine", _engine_job, g.pos, g.level, g.history_keys,
                    g.seconds_left(not g.learner_white), g.kind == "play")

    def _advance(self):
        """Decide what happens next when nothing is moving."""
        g = self.game
        if g.is_over or self.session_done or self.anim or self.promo:
            return
        if g.kind == "opening":
            if g.trainer.is_learner_ply(g.ply):
                return
            if self.script_due is None:
                self.script_due = now() + 0.6 * max(0.3, self._speed())
            elif now() >= self.script_due:
                self.script_due = None
                self._apply_move(g.trainer.expected(g.ply), False)
            return

        if g.learner_to_move():
            self._maybe_start_analysis()
            self._try_premove()
        elif not self.thinking and not self.quality_pending:
            self._start_engine()

    def _try_premove(self):
        if not self.premove or self.anim:
            return
        start, end = self.premove
        self.premove = None
        moves = self.game.moves_between(start, end)
        if not moves:
            self._set_message("Premove cancelled: it is not legal now.", U.MUTED)
            return
        move = next((m for m in moves if m[2] in ("", "q")), moves[0])
        self._apply_move(move, True)

    # -- end of game -----------------------------------------------------------------
    def _on_game_over(self):
        g = self.game
        self._cancel_jobs()
        self.premove = self.pre_selected = None
        title, subtitle = g.result_text()
        outcome = g.outcome()
        self.banner = {
            "title": title, "subtitle": subtitle, "t0": now(), "stars": None,
            "good": outcome == "win",
            "buttons": [("Rematch", self.rematch, "primary"), ("Menu", self.go_home, "normal")],
        }

    def _session_complete(self):
        g = self.game
        self.session_done = True
        self._cancel_jobs()
        trainer = g.trainer
        self.banner = {
            "title": "Line complete!",
            "subtitle": "Mistakes: {}   Hints: {}".format(trainer.mistakes, trainer.hints),
            "t0": now(), "stars": trainer.stars(), "good": True,
            "buttons": [("Play on vs computer", self.play_on, "primary"), ("Practise again", self.rematch, "normal"),
                        ("Menu", self.go_home, "normal")],
        }

    def rematch(self):
        if self.last_cfg:
            self.start_session(self.last_cfg)

    def play_on(self):
        """After an opening line: continue the game against the computer from the final position."""
        g = self.game
        cfg = self.last_cfg or self.setup
        game = Game(g.pos.copy(), g.learner_white, cfg["level"], cfg["assist"], "middlegame",
                    "Middlegame: " + g.title, cfg["time"])
        self._begin_game(game)

    # =======================================================================
    # Buttons in the game screen
    # =======================================================================
    def show_hint(self):
        g = self.game
        if not g or not g.assist or g.is_over or self.anim or not g.learner_to_move() or self.view is not None:
            return
        if g.kind == "opening":
            g.trainer.hints += 1
            self._show_hint(g.trainer.expected(g.ply))
        elif self.analysis and self.analysis["key"] == g.pos.key():
            self._show_hint(self.analysis["move"])
        else:
            self.hint_wanted = True
            self._set_message("Analysing the position...", U.MUTED)

    def _show_hint(self, move):
        if move is None:
            return
        g = self.game
        g.hints_used += 1
        self.hint = {"move": move, "t0": now()}
        self._set_message("Hint: " + move_to_san(g.pos, move), U.GOLD)

    def takeback(self):
        g = self.game
        if not g or self.anim or g.clock or not g.moves:
            return
        self._cancel_jobs()
        g.undo()
        self.selected, self.targets, self.hint, self.promo = None, [], None, None
        self.premove = self.pre_selected = None
        self.banner = None
        self.session_done = False
        self.view = None
        self._set_message("Move taken back.", U.MUTED)

    def resign(self):
        g = self.game
        if g and not g.is_over and not self.session_done:
            g.resign()
            self._on_game_over()

    def flip(self):
        self.flipped = not self.flipped

    # =======================================================================
    # Mouse and keyboard
    # =======================================================================
    def _on_motion(self, event):
        self.ui.mouse = (event.x, event.y)
        clickable = self.ui.over_clickable()
        if not clickable and self.screen == "game" and not self.banner:
            sq = screen_to_square(event.x - self.bl, event.y - self.bt, self.sq, self.flipped)
            if sq is not None and self.view is None and self.game and not self.game.is_over:
                piece = self._display_board()[sq]
                clickable = (piece != "." and is_white_piece(piece) == self.game.learner_white) or sq in self.targets
        self.canvas.config(cursor="hand2" if clickable else "")

    def _on_leave(self, event):
        self.ui.mouse = (-1, -1)

    def _on_click(self, event):
        self.ui.mouse = (event.x, event.y)
        if self.ui.click(event.x, event.y):
            return
        if self.screen != "game" or self.banner or not self.game:
            return
        sq = screen_to_square(event.x - self.bl, event.y - self.bt, self.sq, self.flipped)
        self._on_board_click(sq)

    def _on_right_click(self, event):
        self._escape()

    def _escape(self):
        self.premove = self.pre_selected = None
        self.selected, self.targets = None, []
        self.promo = None
        self.hint = None
        self.view = None

    def _actionable(self):
        """True when the player can make a real move right now (otherwise clicks make a premove)."""
        g = self.game
        return g.learner_to_move() and not self.anim and not self.quality_pending and not self.promo

    def _on_board_click(self, sq):
        g = self.game
        if self.promo:
            self.promo = None
            return
        if sq is None or g.is_over or self.view is not None or self.session_done:
            self.selected, self.targets = None, []
            return
        if g.kind == "opening" and not self._actionable():
            return
        if self._actionable():
            self._learner_click(sq)
        elif self.settings["premove"]:
            self._premove_click(sq)

    def _learner_click(self, sq):
        g = self.game
        if self.selected is not None and sq in self.targets:
            self._try_learner_move(self.selected, sq)
            return
        piece = g.pos.board[sq]
        own = piece != "." and is_white_piece(piece) == g.pos.white_to_move
        if own and sq != self.selected:
            self.selected = sq
            self.targets = [m[1] for m in g.legal() if m[0] == sq]
        else:
            self.selected, self.targets = None, []

    def _premove_click(self, sq):
        g = self.game
        piece = self._display_board()[sq]
        own = piece != "." and is_white_piece(piece) == g.learner_white
        if self.pre_selected is None:
            if own:
                self.pre_selected = sq
                self.premove = None
        elif sq == self.pre_selected:
            self.pre_selected = None
        elif own:
            self.pre_selected = sq
        else:
            self.premove = (self.pre_selected, sq)
            self.pre_selected = None

    def _review_step(self, delta):
        g = self.game
        if self.screen != "game" or not g:
            return
        last = len(g.positions) - 1
        current = last if self.view is None else self.view
        self._review_to(max(0, min(last, current + delta)))

    def _review_to(self, index):
        g = self.game
        if self.screen != "game" or not g:
            return
        last = len(g.positions) - 1
        self.view = None if index is None or index >= last else index
        self.selected, self.targets, self.hint = None, [], None

    # =======================================================================
    # Frame loop
    # =======================================================================
    def _tick(self):
        t = now()
        dt = min(0.1, t - self._last_time)
        self._last_time = t
        if self.screen == "game" and self.game:
            self._update_game(t, dt)
        self._draw(t)
        busy = self.anim or self.effects or self.thinking or self.banner
        self.root.after(FRAME_FAST if busy else FRAME_IDLE, self._tick)

    def _update_game(self, t, dt):
        g = self.game
        if g.clock and not g.is_over:
            g.tick(dt)
            if g.is_over and not self.banner:
                self._on_game_over()

        if self.anim and t >= self.anim["t0"] + self.anim["duration"]:
            self._finish_anim()
        self.effects = [e for e in self.effects if t < e["t0"] + e["duration"]]
        self.eval_shown += (self.eval_target - self.eval_shown) * 0.12

        self._poll_jobs()
        if self.thinking and self.engine_move is not None and t - self.think_start >= MIN_THINK and not self.anim:
            move, self.engine_move, self.thinking = self.engine_move, None, False
            self._apply_move(move, False)
        self._advance()

    # =======================================================================
    # Drawing: common
    # =======================================================================
    def _draw(self, t):
        self.canvas.delete("all")
        self.ui.begin_frame()
        if self.screen == "home":
            self._draw_home(t)
        elif self.screen == "setup":
            self._draw_setup(t)
        elif self.screen == "settings":
            self._draw_settings(t)
        elif self.screen == "game" and self.game:
            self._draw_game(t)

    def _glyph(self, x, y, glyph, size, color):
        self.canvas.create_text(x, y, text=glyph, font=(PIECE_FONT, -int(size)), fill=color)

    def _draw_piece(self, piece, cx, cy, size):
        glyph = GLYPHS[piece.lower()]
        c = self.canvas
        font = (PIECE_FONT, -int(size))
        if is_white_piece(piece):  # a dark outline makes white pieces readable on light squares
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1.5, -1.5), (1.5, -1.5), (-1.5, 1.5), (1.5, 1.5)):
                c.create_text(cx + dx, cy + dy, text=glyph, font=font, fill=WHITE_EDGE)
            c.create_text(cx, cy, text=glyph, font=font, fill=WHITE_FILL)
        else:
            c.create_text(cx, cy, text=glyph, font=font, fill=BLACK_FILL)

    # =======================================================================
    # Drawing: home, setup, settings
    # =======================================================================
    def _draw_home(self, t):
        ui, W = self.ui, self.win_w
        ui.text(W / 2 - 2, 96, "check", 66, U.FG, "e", True)
        ui.text(W / 2 - 2, 96, "me", 66, U.ACCENT, "w", True)
        ui.text(W / 2, 150, "Practise openings, middlegames and endgames", 18, U.MUTED)

        card_w, card_h, gap = 390, 128, 22
        x0 = (W - (2 * card_w + gap)) / 2
        y0 = 196
        for i, (key, title, description, glyph) in enumerate(CATEGORIES):
            x1 = x0 + (i % 2) * (card_w + gap)
            y1 = y0 + (i // 2) * (card_h + gap)
            amount = ui.card("home-" + key, x1, y1, x1 + card_w, y1 + card_h, lambda k=key: self.open_setup(k))
            shift = -3 * amount
            self._glyph(x1 + 54, y1 + 64 + shift, glyph, 56, blend(U.ACCENT, "#ffffff", amount * 0.4))
            ui.text(x1 + 108, y1 + 24 + shift, title, 22, U.FG, "nw", True)
            ui.paragraph(x1 + 108, y1 + 56 + shift, description, card_w - 130, 13, U.MUTED)

        y = y0 + 2 * (card_h + gap) + 6
        ui.button("home-settings", W / 2 - 150, y, W / 2 - 10, y + 40, "Settings", self.open_settings, size=14)
        ui.button("home-quit", W / 2 + 10, y, W / 2 + 150, y + 40, "Quit", self.root.destroy, size=14)
        ui.text(W / 2, y + 70, "9 levels  ·  Assist or no assist  ·  Premove  ·  1, 3 and 10 minute clocks", 12, U.MUTED)

    def _draw_setup(self, t):
        ui, s = self.ui, self.setup
        category = s["category"]
        ui.button("setup-back", 28, 22, 118, 54, "< Back", self.go_home, size=13)
        ui.text(138, 38, CATEGORY_TITLES[category], 28, U.FG, "w", True)

        list_x1, list_x2 = 40, 600
        if category == "play":
            ui.card("play-info", list_x1, 100, list_x2, 300, lift=False)
            ui.text(list_x1 + 20, 118, "Play against the computer", 18, U.FG, "nw", True)
            ui.paragraph(list_x1 + 20, 150, "A full game from the starting position. The computer uses a different "
                         "opening each time. Choose your level (1 is a beginner, 9 is the strongest), your colour and "
                         "a time control.\n\nTurn Assist on to get hints, an evaluation bar, move grades "
                         "(best, mistake, blunder) and opening names. Turn it off to play on your own.",
                         list_x2 - list_x1 - 40, 14, U.MUTED)
        elif category in ("opening", "middlegame"):
            ui.text(list_x1, 82, "Choose an opening" if category == "opening" else
                    "Choose a structure to play (you play the side of the opening)", 14, U.MUTED, "w")
            for i, opening in enumerate(OPENINGS):
                x1 = list_x1 + (i % 2) * 288
                y1 = 100 + (i // 2) * 56
                selected = i == s["index"]
                ui.card("op-%d" % i, x1, y1, x1 + 272, y1 + 50, lambda n=i: self.set_setup("index", n),
                        selected=selected, lift=False)
                ui.text(x1 + 14, y1 + 12, opening.name, 13, U.FG, "nw", True)
                ui.text(x1 + 14, y1 + 31, "{}  ·  you play {}".format(opening.eco, opening.side), 11, U.MUTED, "nw")
        else:
            ui.text(list_x1, 82, "Choose a drill (you play the winning side)", 14, U.MUTED, "w")
            for i, drill in enumerate(ENDGAMES):
                y1 = 100 + i * 78
                ui.card("dr-%d" % i, list_x1, y1, list_x2, y1 + 70, lambda n=i: self.set_setup("index", n),
                        selected=(i == s["index"]), lift=False)
                ui.text(list_x1 + 16, y1 + 12, drill.name, 15, U.FG, "nw", True)
                ui.text(list_x1 + 16, y1 + 36, "Goal: {}  ·  par {} moves".format(
                    "checkmate" if drill.goal == "mate" else "promote the pawn", drill.par), 12, U.MUTED, "nw")

        # --- Options panel on the right ---
        px1, px2 = 640, self.win_w - 40
        cw = px2 - px1
        ui.round_rect(px1 - 14, 84, px2 + 14, self.win_h - 24, 14, fill=U.PANEL)
        y = 100
        ui.text(px1, y, "Level" if category != "opening" else "Level (for playing on afterwards)", 14, U.FG, "w", True)
        ui.text(px2, y, level_name(s["level"]).split(" - ")[1], 13, U.ACCENT, "e", True)
        y += 18
        cell_w, cell_h = (cw - 12) // 3, 34
        for level in range(1, 10):
            cx = px1 + ((level - 1) % 3) * (cell_w + 6)
            cy = y + ((level - 1) // 3) * (cell_h + 5)
            ui.button("level-%d" % level, cx, cy, cx + cell_w, cy + cell_h,
                      "{}  {}".format(level, LEVELS[level].name), lambda n=level: self.set_setup("level", n),
                      selected=(level == s["level"]), size=11)
        y += 3 * (cell_h + 5) + 8

        if category == "play":
            ui.text(px1, y + 4, "Play as", 14, U.FG, "w", True)
            y += 16
            ui.segmented("side", px1, y, [("white", "White"), ("black", "Black"), ("random", "Random")],
                         s["side"], lambda v: self.set_setup("side", v), (cw - 8) // 3)
            y += 42

        label = "Learn mode" if category == "opening" else "Assist"
        caption = ("Explanations and hints. Off = test yourself" if category == "opening"
                   else "Hints, eval bar, move grades, opening names")
        ui.toggle_row("assist", px1, y, cw, label, s["assist"], lambda v: self.set_setup("assist", v), caption)
        y += 52

        ui.text(px1, y + 4, "Time", 14, U.FG, "w", True)
        y += 16
        ui.segmented("time", px1, y, TIME_CONTROLS_OPTIONS, s["time"], lambda v: self.set_setup("time", v),
                     (cw - 12) // 4)
        y += 42

        ui.button("setup-start", px1, self.win_h - 24 - 16 - 46, px2, self.win_h - 24 - 16, "Start", self.start_session,
                  style="primary", size=17)

    def _draw_settings(self, t):
        ui, W = self.ui, self.win_w
        ui.button("settings-back", 28, 22, 118, 54, "< Back", self.close_settings, size=13)
        ui.text(138, 38, "Settings", 28, U.FG, "w", True)
        x, width = W / 2 - 280, 560
        ui.round_rect(x - 20, 84, x + width + 20, 84 + 440, 14, fill=U.PANEL)
        s = self.settings
        y = 104
        ui.toggle_row("premove", x, y, width, "Premove", s["premove"], lambda v: self.set_setting("premove", v),
                      "Queue a move while the computer is thinking. Right-click cancels it.")
        y += 66
        ui.toggle_row("dots", x, y, width, "Show legal moves", s["dots"], lambda v: self.set_setting("dots", v),
                      "Dots on the squares a selected piece can reach")
        y += 66
        ui.toggle_row("coords", x, y, width, "Board coordinates", s["coords"], lambda v: self.set_setting("coords", v),
                      "Letters and numbers on the edge of the board")
        y += 66
        ui.text(x, y + 14, "Board theme", 14, U.FG, "w", True)
        ui.segmented("theme", x + width - 3 * 90 - 8, y, [(k, v["name"]) for k, v in U.THEMES.items()], s["theme"],
                     lambda v: self.set_setting("theme", v), 90)
        y += 56
        ui.text(x, y + 14, "Piece animation", 14, U.FG, "w", True)
        ui.segmented("anim", x + width - 4 * 70 - 12, y, [("slow", "Slow"), ("normal", "Normal"), ("fast", "Fast"), ("off", "Off")],
                     s["anim"], lambda v: self.set_setting("anim", v), 70)
        y += 56
        theme = U.THEMES[s["theme"]]
        for i in range(4):  # a little preview of the theme
            for j in range(2):
                col = theme["light"] if (i + j) % 2 == 0 else theme["dark"]
                ui.rect(x + i * 36, y + j * 36, x + i * 36 + 36, y + j * 36 + 36, fill=col)
        self._glyph(x + 54, y + 36, GLYPHS["n"], 40, WHITE_FILL)
        ui.text(x + 170, y + 36, "Settings are saved automatically.", 12, U.MUTED, "w")

    # =======================================================================
    # Drawing: the game screen
    # =======================================================================
    def _display_pos(self):
        g = self.game
        return g.positions[self.view] if self.view is not None else g.pos

    def _display_board(self):
        if self.view is None and self.anim:
            return self.anim["board_before"]
        return self._display_pos().board

    def _display_last_move(self):
        g = self.game
        if self.view is None:
            return g.moves[-1] if g.moves else None
        return g.moves[self.view - 1] if self.view > 0 else None

    def _draw_game(self, t):
        self._draw_eval_bar()
        bottom_white = not self.flipped
        self._draw_strip(self.bt - STRIP_H, not bottom_white)
        self._draw_strip(self.bt + self.board_px, bottom_white)
        self._draw_board(t)
        self._draw_status()
        self._draw_panel(t)
        if self.promo:
            self._draw_promotion()
        if self.banner:
            self._draw_banner(t)

    # -- evaluation bar ------------------------------------------------------------
    def _draw_eval_bar(self):
        g, ui = self.game, self.ui
        x1, y1, x2, y2 = MARGIN, self.bt, MARGIN + EVAL_W, self.bt + self.board_px
        if not g.assist or g.kind == "opening":
            return
        ui.rect(x1, y1, x2, y2, fill="#3a3835")
        cp = self.eval_shown
        white_share = 0.5 + 0.5 * math.tanh(cp / 450.0)
        height = self.board_px * white_share
        if self.flipped:
            ui.rect(x1, y1, x2, y1 + height, fill="#f2f2f2")
            label_y, label_anchor = y1 + 4, "n"
        else:
            ui.rect(x1, y2 - height, x2, y2, fill="#f2f2f2")
            label_y, label_anchor = y2 - 4, "s"
        magnitude = abs(cp)
        label = "M" if magnitude >= 1400 else "{:.1f}".format(magnitude / 100)
        ui.text((x1 + x2) / 2, label_y, label, 10, "#262421" if (cp >= 0) != self.flipped else "#e0e0e0",
                label_anchor, True)

    # -- player strips (name, captured pieces, clock) ---------------------------------
    def _draw_strip(self, y, white):
        g, ui = self.game, self.ui
        x1, x2 = self.bl, self.bl + self.board_px
        ui.round_rect(x1, y + 4, x2, y + STRIP_H - 4, 8, fill=U.PANEL)
        is_learner = white == g.learner_white
        self.canvas.create_oval(x1 + 10, y + 8, x1 + 36, y + 34, fill="#fafafa" if white else "#1f1f1f", outline=U.ACCENT)
        self._glyph(x1 + 23, y + 21, GLYPHS["k"], 18, "#1f1f1f" if white else "#fafafa")
        name = "You" if is_learner else ("Opening book" if g.kind == "opening" else "Computer")
        ui.text(x1 + 46, y + 13, name, 14, U.FG, "w", True)
        if is_learner:
            detail = "Assist on" if g.assist else "Assist off"
        elif g.kind == "opening":
            detail = "plays the book moves"
        else:
            detail = level_name(g.level)
        if not is_learner and self.thinking:
            detail = "thinking" + "." * (int(now() * 3) % 4)
        ui.text(x1 + 46, y + 29, detail, 11, U.MUTED, "w")

        # captured pieces and material
        key = g.pos.key()
        if self._cache.get("cap-key") != key:
            self._cache["cap-key"] = key
            self._cache["cap"] = captured_pieces(g.pos)
        captured = self._cache["cap"]["white" if white else "black"]
        x = x1 + 200
        for kind in captured:
            self._glyph(x, y + 22, GLYPHS[kind], 17, "#c9c8c5" if white else "#8f8e8b")
            x += 10 if kind == "p" else 15
        balance = material_balance(g.pos) * (1 if white else -1)
        if balance > 0:
            ui.text(x + 6, y + 22, "+%d" % balance, 12, U.MUTED, "w", True)

        if g.clock:
            seconds = g.clock["white" if white else "black"]
            active = (g.white_to_move == white) and bool(g.moves) and not g.is_over
            fill = U.ACCENT if active else "#1f1e1c"
            if seconds < 10 and active:
                fill = U.DANGER
            ui.round_rect(x2 - 104, y + 7, x2 - 8, y + STRIP_H - 7, 8, fill=fill)
            ui.text(x2 - 56, y + 22, format_clock(seconds), 19, "#ffffff" if active else "#bdbcba", "center", True)

    # -- the board ---------------------------------------------------------------------
    def _square_color(self, sq, theme, last_move):
        light = ((sq >> 3) + (sq & 7)) % 2 == 0
        if sq == self.selected or sq == self.pre_selected:
            return theme["sel_light"] if light else theme["sel_dark"]
        if last_move and sq in last_move[:2]:
            return theme["last_light"] if light else theme["last_dark"]
        return theme["light"] if light else theme["dark"]

    def _square_xy(self, sq):
        x, y = square_to_screen(sq, self.sq, self.flipped)
        return self.bl + x, self.bt + y

    def _draw_board(self, t):
        g, c, sq_size = self.game, self.canvas, self.sq
        theme = U.THEMES[self.settings["theme"]]
        last_move = self._display_last_move()
        board = self._display_board()
        live = self.view is None

        # squares and coordinates
        for sq in range(64):
            x, y = self._square_xy(sq)
            color = self._square_color(sq, theme, last_move)
            if self.premove and live and sq in self.premove:
                color = blend(color, PREMOVE_RED, 0.55)
            if self.error_flash and sq in self.error_flash["squares"]:
                p = progress(self.error_flash["t0"], t, 0.7)
                if p < 1:
                    color = blend(PREMOVE_RED, color, p)
            c.create_rectangle(x, y, x + sq_size, y + sq_size, fill=color, outline="")
            if self.settings["coords"]:
                light = ((sq >> 3) + (sq & 7)) % 2 == 0
                label_color = theme["dark"] if light else theme["light"]
                if y == self.bt + 7 * sq_size:
                    c.create_text(x + sq_size - 5, y + sq_size - 8, text="abcdefgh"[sq & 7], fill=label_color,
                                  font=U.font(11, True), anchor="e")
                if x == self.bl:
                    c.create_text(x + 5, y + 9, text=str(8 - (sq >> 3)), fill=label_color, font=U.font(11, True), anchor="w")
        if self.error_flash and t - self.error_flash["t0"] > 0.7:
            self.error_flash = None

        self._draw_check_glow(t, theme)
        self._draw_hint_arrow(t)
        if live:
            self._draw_targets(board, theme, last_move)

        # pieces standing still
        moving_from = {m[1] for m in self.anim["movers"]} if self.anim and live else set()
        for sq, piece in enumerate(board):
            if piece == "." or sq in moving_from:
                continue
            x, y = self._square_xy(sq)
            self._draw_piece(piece, x + sq_size / 2, y + sq_size / 2, sq_size * 0.72)

        self._draw_effects(t, theme, last_move)
        self._draw_moving_pieces(t)
        self._draw_quality_badge()

    def _draw_check_glow(self, t, theme):
        pos = self._display_pos()
        if self.anim and self.view is None:
            return
        if self.game.is_over and self.game.result and self.game.result["reason"] != "checkmate":
            return
        if not is_in_check(pos):
            return
        king = pos.board.index("K" if pos.white_to_move else "k")
        x, y = self._square_xy(king)
        color = blend(self._square_color(king, theme, self._display_last_move()), CHECK_RED, 0.35 + 0.4 * pulse(now(), 1.2))
        self.canvas.create_oval(x + 4, y + 4, x + self.sq - 4, y + self.sq - 4, fill=color, outline="")

    def _draw_targets(self, board, theme, last_move):
        """Dots on empty squares the selected piece can reach, rings on captures."""
        if self.anim or not self.settings["dots"]:
            return
        for sq in self.targets:
            x, y = self._square_xy(sq)
            cx, cy = x + self.sq / 2, y + self.sq / 2
            color = blend(self._square_color(sq, theme, last_move), "#000000", 0.2)
            if board[sq] == ".":
                r = self.sq * 0.15
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="")
            else:
                r = self.sq * 0.45
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=6)

    def _draw_hint_arrow(self, t):
        if not self.hint or self.view is not None or self.anim:
            return
        start, end, _promo = self.hint["move"]
        x1, y1 = self._square_xy(start)
        x2, y2 = self._square_xy(end)
        half = self.sq / 2
        sx, sy, ex, ey = x1 + half, y1 + half, x2 + half, y2 + half
        length = math.hypot(ex - sx, ey - sy) or 1
        dx, dy = (ex - sx) / length, (ey - sy) / length
        px, py = -dy, dx  # perpendicular
        sx, sy = sx + dx * self.sq * 0.12, sy + dy * self.sq * 0.12
        ex, ey = ex - dx * self.sq * 0.10, ey - dy * self.sq * 0.10
        shaft, head, head_len = self.sq * 0.09, self.sq * 0.23, self.sq * 0.32
        bx, by = ex - dx * head_len, ey - dy * head_len
        pts = [sx + px * shaft, sy + py * shaft, bx + px * shaft, by + py * shaft, bx + px * head, by + py * head,
               ex, ey, bx - px * head, by - py * head, bx - px * shaft, by - py * shaft, sx - px * shaft, sy - py * shaft]
        color = blend("#2fa84f", "#7be08f", pulse(t, 1.4) * 0.5)
        self.canvas.create_polygon(pts, fill=color, outline="#1c6b32", width=2)

    def _draw_moving_pieces(self, t):
        if not self.anim or self.view is not None:
            return
        a = self.anim
        p = progress(a["t0"], t, a["duration"])
        eased = ease_in_out_cubic(p)
        for i, (piece, start, end) in enumerate(a["movers"]):
            sx, sy = self._square_xy(start)
            ex, ey = self._square_xy(end)
            x = lerp(sx, ex, eased) + self.sq / 2
            y = lerp(sy, ey, eased) + self.sq / 2
            lift = 1 + (0.16 if i == 0 else 0.0) * math.sin(math.pi * p)  # the piece lifts a little mid-move
            self._draw_piece(piece, x, y, self.sq * 0.72 * lift)

    def _draw_effects(self, t, theme, last_move):
        for e in self.effects:
            p = progress(e["t0"], t, e["duration"])
            x, y = self._square_xy(e["square"])
            cx, cy = x + self.sq / 2, y + self.sq / 2
            radius = self.sq * (0.2 + 0.4 * ease_in_out_cubic(p))
            color = blend(e["color"], self._square_color(e["square"], theme, last_move), p)
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=color,
                                    width=max(1, 7 * (1 - p)))

    def _draw_quality_badge(self):
        g = self.game
        if not g.quality or self.view is not None or self.anim:
            return
        ply = max(g.quality)
        if ply < g.ply - 2 or ply >= g.ply:
            return
        label = g.quality[ply]["label"]
        _text, symbol, color = QUALITY[label]
        x, y = self._square_xy(g.moves[ply][1])
        r = self.sq * 0.19
        cx, cy = x + self.sq - r - 2, y + r + 2
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="#ffffff", width=2)
        self.canvas.create_text(cx, cy, text=symbol, font=U.font(r * 1.15, True), fill="#ffffff")

    def _draw_promotion(self):
        """Let the player pick the promotion piece: a column of four pieces next to the board edge."""
        g, ui = self.game, self.ui
        promo = self.promo
        end = promo["end"]
        x, y = self._square_xy(end)
        down = y < self.bt + self.board_px / 2  # column goes towards the middle of the board
        step = self.sq if down else -self.sq
        for i, kind in enumerate("qnrb"):
            cy = y + i * step
            move = next(m for m in promo["moves"] if m[2] == kind)
            piece = kind.upper() if g.learner_white else kind
            hot = ui.inside(x, cy, x + self.sq, cy + self.sq)
            self.canvas.create_rectangle(x, cy, x + self.sq, cy + self.sq,
                                         fill="#ffffff" if hot else "#e6e6e6", outline="#555555")
            self._draw_piece(piece, x + self.sq / 2, cy + self.sq / 2, self.sq * 0.7)
            ui.add_hot(x, cy, x + self.sq, cy + self.sq, lambda m=move: self._choose_promotion(m))

    def _draw_status(self):
        g = self.game
        y = self.bt + self.board_px + STRIP_H + 18
        if self.view is not None:
            text, color = "Reviewing move {}. Press End to return to the game.".format(self.view), U.GOLD
        elif g.is_over or self.session_done:
            text, color = "Game over", U.MUTED
        elif self.thinking:
            text, color = "Computer is thinking" + "." * (int(now() * 3) % 4), U.MUTED
        elif self.premove:
            text, color = "Premove: {} to {}. Right-click to cancel.".format(
                square_name(self.premove[0]), square_name(self.premove[1])), U.GOLD
        elif g.learner_to_move():
            text = ("Check! " if is_in_check(g.pos) else "") + "Your move"
            color = U.DANGER if is_in_check(g.pos) else U.FG
        else:
            text, color = "Opponent to move", U.MUTED
        self.ui.text(self.bl, y, text, 14, color, "w", True)

    # -- side panel --------------------------------------------------------------------
    def _draw_panel(self, t):
        g, ui = self.game, self.ui
        x0, x1 = self.px, self.win_w - MARGIN
        w = x1 - x0
        top, bottom = MARGIN, self.win_h - MARGIN
        avail = bottom - top

        # header
        ui.round_rect(x0, top, x1, top + 80, 12, fill=U.PANEL)
        lines = U.wrap_text(g.title, w - 28, 15)[:2]
        for i, line in enumerate(lines):
            ui.text(x0 + 14, top + 12 + i * 19, line, 15, U.FG, "nw", True)
        sub = [CATEGORY_TITLES.get({"play": "play", "opening": "opening", "middlegame": "middlegame",
                                    "endgame": "endgame"}[g.kind], "")]
        if g.kind != "opening":
            sub.append("Level {}".format(g.level))
        sub.append("Assist on" if g.assist else "Assist off")
        if g.time_control:
            sub.append("{} min".format(g.time_control // 60))
        ui.text(x0 + 14, top + 62, "  ·  ".join(sub), 11, U.MUTED, "nw")

        # buttons (bottom)
        btn_h, gap = 34, 6
        btn_w = (w - 2 * gap) // 3
        by2 = bottom - btn_h - gap - btn_h
        can_take_back = bool(g.moves) and not g.clock and not self.anim
        row1 = [("Hint", self.show_hint, "normal", g.assist and not g.is_over and not self.session_done),
                ("Takeback", self.takeback, "normal", can_take_back),
                ("Resign" if g.kind != "opening" else "Give up", self.resign, "danger",
                 not g.is_over and not self.session_done)]
        row2 = [("Flip", self.flip, "normal", True), ("Settings", self.open_settings, "normal", True),
                ("Menu", self.go_home, "normal", True)]
        for r, row in enumerate((row1, row2)):
            for i, (label, callback, style, enabled) in enumerate(row):
                bx = x0 + i * (btn_w + gap)
                by = by2 + r * (btn_h + gap)
                ui.button("g-" + label, bx, by, bx + btn_w, by + btn_h, label, callback, style, enabled, 13)

        # move list (above the buttons)
        moves_h = max(150, int(avail * 0.36))
        moves_top = by2 - 10 - moves_h
        coach_top, coach_bottom = top + 90, moves_top - 10
        self._draw_coach(x0, coach_top, x1, coach_bottom)
        self._draw_moves(x0, moves_top, x1, moves_top + moves_h)

    def _coach_blocks(self):
        """What the coach card says: a list of (text, size, colour, bold)."""
        g = self.game
        blocks = []
        if g.assist and g.kind in ("play", "middlegame"):
            if self._cache.get("name-n") != (len(g.sans), g.kind):
                start = getattr(g, "opening", None)
                self._cache["name-n"] = (len(g.sans), g.kind)
                self._cache["name"] = opening_name(g.sans) if g.kind == "play" else (start.name if start else None)
            if self._cache["name"]:
                blocks.append((self._cache["name"], 15, U.ACCENT, True))
        if self.message:
            blocks.append((self.message["text"], 14, self.message["color"], True))

        if g.kind == "opening":
            trainer = g.trainer
            done = min(g.ply, len(trainer.line))
            if g.assist:
                blocks.append(("Idea: " + trainer.opening.idea, 13, U.MUTED, False))
            else:
                blocks.append(("Test mode: no hints. Play the book moves from memory.", 13, U.MUTED, False))
            blocks.append(("Progress: {} of {} moves   Mistakes: {}".format(done, len(trainer.line), trainer.mistakes),
                           12, U.FG, False))
        elif g.kind == "middlegame":
            opening = getattr(g, "opening", None)
            if opening and g.assist:
                blocks.append((opening.structure, 13, U.MUTED, False))
                blocks.append(("Plans:", 13, U.FG, True))
                blocks += [("• " + plan, 13, U.MUTED, False) for plan in opening.plans]
            elif g.assist:
                blocks.append(("Play on and look for a plan.", 13, U.MUTED, False))
            else:
                blocks.append(("Assist is off: find your own plan.", 13, U.MUTED, False))
        elif g.kind == "endgame":
            drill = g.drill
            goal = "checkmate" if drill.goal == "mate" else "promote the pawn"
            blocks.append(("Goal: {} (par {} moves)".format(goal, drill.par), 13, U.FG, True))
            if g.assist:
                blocks.append((drill.description, 13, U.MUTED, False))
                blocks += [("• " + tip, 13, U.MUTED, False) for tip in drill.tips]
        elif not self.message and not g.assist:
            blocks.append(("Assist is off. You are on your own!", 13, U.MUTED, False))
        elif not self.message:
            blocks.append(("Make your move. Press Hint if you need help.", 13, U.MUTED, False))
        return blocks

    def _draw_coach(self, x0, y0, x1, y1):
        ui = self.ui
        ui.round_rect(x0, y0, x1, y1, 12, fill=U.PANEL)
        y = y0 + 12
        for text, size, color, bold in self._coach_blocks():
            y = ui.paragraph(x0 + 14, y, text, x1 - x0 - 28, size, color, 3, bold, max_y=y1 - 8) + 5

    def _move_rows(self):
        """Rows for the move list: [(number_text, white_ply or None, black_ply or None)]."""
        g = self.game
        start = g.start_pos
        rows, ply = [], 0
        number = start.fullmove
        if not start.white_to_move and g.sans:
            rows.append(["{}.".format(number), None, 0])
            ply, number = 1, number + 1
        while ply < len(g.sans):
            rows.append(["{}.".format(number), ply, ply + 1 if ply + 1 < len(g.sans) else None])
            ply += 2
            number += 1
        return rows

    def _draw_moves(self, x0, y0, x1, y1):
        g, ui = self.game, self.ui
        ui.round_rect(x0, y0, x1, y1, 12, fill=U.PANEL)
        ui.text(x0 + 14, y0 + 10, "Moves", 13, U.MUTED, "nw", True)
        rows = self._move_rows()
        row_h = 24
        visible = max(1, int((y1 - y0 - 40) // row_h))
        current = (g.ply - 1) if self.view is None else (self.view - 1)
        focus = len(rows) - 1
        if self.view is not None:
            focus = next((i for i, r in enumerate(rows) if current in (r[1], r[2])), focus)
        first = max(0, min(len(rows) - visible, focus - visible // 2 if self.view is not None else len(rows) - visible))
        cell_w = (x1 - x0 - 60) / 2
        y = y0 + 34
        for row in rows[first:first + visible]:
            ui.text(x0 + 14, y + 4, row[0], 13, U.MUTED, "nw")
            for col in (1, 2):
                ply = row[col]
                if ply is None:
                    continue
                cx = x0 + 52 + (col - 1) * cell_w
                if ply == current:
                    ui.round_rect(cx - 4, y, cx + cell_w - 8, y + row_h - 3, 6, fill=U.BUTTON)
                ui.text(cx + 2, y + 4, g.sans[ply], 14, U.FG, "nw", ply == current)
                target = None if ply + 1 >= len(g.positions) - 1 else ply + 1
                ui.add_hot(cx - 4, y, cx + cell_w - 8, y + row_h - 3, lambda n=ply + 1: self._review_to(n))
            y += row_h

    # -- game over card -------------------------------------------------------------------
    def _draw_banner(self, t):
        ui, b = self.ui, self.banner
        p = ease_out_back(progress(b["t0"], t, 0.7))
        width, height = 470, 236 if not b["stars"] else 262
        cx = self.bl + self.board_px / 2
        cy = lerp(-height, self.bt + self.board_px / 2, p)
        x1, y1, x2, y2 = cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2
        ui.round_rect(x1, y1, x2, y2, 16, fill=U.BG, outline=U.ACCENT if b["good"] else U.MUTED, width=3)
        ui.text(cx, y1 + 46, b["title"], 36, "#ffffff", "center", True)
        ui.text(cx, y1 + 90, b["subtitle"], 15, U.MUTED)
        offset = 0
        if b["stars"]:
            stars = "★" * b["stars"] + "☆" * (3 - b["stars"])
            ui.text(cx, y1 + 128, stars, 30, U.GOLD)
            offset = 34
        buttons = b["buttons"]
        gap = 8
        bw = (width - 40 - gap * (len(buttons) - 1)) / len(buttons)
        for i, (label, callback, style) in enumerate(buttons):
            bx = x1 + 20 + i * (bw + gap)
            by = y2 - 62
            ui.button("banner-%d" % i, bx, by, bx + bw, by + 42, label, callback, style, True, 13)


TIME_CONTROLS_OPTIONS = [(seconds, name) for name, seconds in TIME_CONTROLS]
