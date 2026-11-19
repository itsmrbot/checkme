"""Game logic for checkme (no windows in here, so it is easy to test).

Game          one game: moves, history, clocks, result and the practice goal.
OpeningTrainer checks your moves against an opening line.
Also: time controls, move grading ("Best move", "Blunder"...) and captured-piece counts.
"""

from collections import Counter

from engine import (
    Position,
    count_material,
    game_end_reason,
    legal_moves,
)
from notation import move_to_san

# ---------------------------------------------------------------------------
# Time controls and clocks
# ---------------------------------------------------------------------------
TIME_CONTROLS = [("No clock", None), ("1 min", 60), ("3 min", 180), ("10 min", 600)]


def format_clock(seconds):
    """83.4 -> '1:23', 7.31 -> '0:07.3' (tenths of a second when under 10 seconds)."""
    seconds = max(0.0, seconds)
    if seconds < 10:
        return "0:{:04.1f}".format(seconds)
    whole = int(seconds)
    return "{}:{:02d}".format(whole // 60, whole % 60)


# ---------------------------------------------------------------------------
# Move grading (Assist)
# ---------------------------------------------------------------------------
QUALITY = {
    "best": ("Best move", "!", "#81b64c"),
    "good": ("Good move", "✓", "#95bb4a"),
    "inaccuracy": ("Inaccuracy", "?!", "#f7c631"),
    "mistake": ("Mistake", "?", "#e58f2a"),
    "blunder": ("Blunder", "??", "#ca3431"),
}


def classify_loss(loss_centipawns):
    """How bad was a move? loss = (score of the best move) - (score of the move played)."""
    if loss_centipawns <= 15:
        return "best"
    if loss_centipawns <= 50:
        return "good"
    if loss_centipawns <= 120:
        return "inaccuracy"
    if loss_centipawns <= 280:
        return "mistake"
    return "blunder"


# ---------------------------------------------------------------------------
# Captured pieces
# ---------------------------------------------------------------------------
_STANDARD = {"p": 8, "n": 2, "b": 2, "r": 2, "q": 1}
_VALUES = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9}


def captured_pieces(pos):
    """Pieces each side has captured, e.g. {'white': ['p', 'p', 'n'], 'black': [...]}
    (letters are the type of the captured piece, lowercase)."""
    present = {True: Counter(), False: Counter()}
    for piece in pos.board:
        if piece not in ".Kk":
            present[piece.isupper()][piece.lower()] += 1

    result = {}
    for white in (True, False):  # missing pieces of this colour were captured by the other side
        missing = []
        extra_queens_etc = sum(max(0, present[white][k] - _STANDARD[k]) for k in "nbrq")
        for kind in "qrbnp":
            count = max(0, _STANDARD[kind] - present[white][kind])
            if kind == "p":
                count = max(0, count - extra_queens_etc)  # promoted pawns were not captured
            missing += [kind] * count
        result["black" if white else "white"] = missing
    return result


def material_balance(pos):
    """Positive = white is ahead, in pawns."""
    return count_material(pos, True) - count_material(pos, False)


# ---------------------------------------------------------------------------
# Opening trainer
# ---------------------------------------------------------------------------
class OpeningTrainer:
    """Follows an opening line: the computer plays the other side's moves, you play yours."""

    def __init__(self, opening, line, learner_white):
        self.opening = opening
        self.line = line
        self.learner_white = learner_white
        self.mistakes = 0
        self.hints = 0

    def is_learner_ply(self, ply):
        return (ply % 2 == 0) == self.learner_white

    def expected(self, ply):
        return self.line[ply] if ply < len(self.line) else None

    def is_finished(self, ply):
        return ply >= len(self.line)

    def check(self, ply, move):
        expected = self.expected(ply)
        return expected is not None and move[:2] == expected[:2] and (move[2] or "") == (expected[2] or "")

    def comment(self, ply):
        entry = self.opening.comments.get(ply)
        return entry[1] if entry else None

    def stars(self):
        if self.mistakes == 0 and self.hints == 0:
            return 3
        return 2 if self.mistakes <= 2 else 1


# ---------------------------------------------------------------------------
# The game
# ---------------------------------------------------------------------------
class Game:
    """kind is 'play', 'opening', 'middlegame' or 'endgame'."""

    def __init__(self, start_pos=None, learner_white=True, level=5, assist=True, kind="play",
                 title="Play", time_control=None, trainer=None, drill=None):
        self.start_pos = start_pos or Position()
        self.positions = [self.start_pos]
        self.moves = []
        self.sans = []
        self.counts = Counter({self.start_pos.key(): 1})
        self.learner_white = learner_white
        self.level = level
        self.assist = assist
        self.kind = kind
        self.title = title
        self.trainer = trainer
        self.drill = drill
        self.result = None  # {"winner": "white"/"black"/None, "reason": str}
        self.quality = {}  # ply -> {"key": ..., "loss": ...}
        self.hints_used = 0
        self.time_control = time_control
        self.clock = {"white": time_control, "black": time_control} if time_control else None
        self._legal_cache = {}

    # -- basic info ----------------------------------------------------------
    @property
    def pos(self):
        return self.positions[-1]

    @property
    def ply(self):
        return len(self.moves)

    @property
    def white_to_move(self):
        return self.pos.white_to_move

    def learner_to_move(self):
        return self.white_to_move == self.learner_white

    @property
    def is_over(self):
        return self.result is not None

    def legal(self):
        key = self.pos.key()
        if key not in self._legal_cache:
            self._legal_cache[key] = legal_moves(self.pos)
        return self._legal_cache[key]

    def moves_between(self, start, end):
        """Legal moves from start to end (several if it is a promotion)."""
        return [m for m in self.legal() if m[0] == start and m[1] == end]

    @property
    def history_keys(self):
        return [p.key() for p in self.positions]

    # -- playing ---------------------------------------------------------------
    def play(self, move):
        """Play a legal move. Returns its SAN text. Raises ValueError if it is not legal."""
        if self.is_over:
            raise ValueError("The game is over")
        legal = self.legal()
        if move not in legal:
            raise ValueError("Illegal move")
        san = move_to_san(self.pos, move, legal)
        mover_white = self.white_to_move
        new_pos = self.pos.make_move(move)
        self.positions.append(new_pos)
        self.moves.append(move)
        self.sans.append(san)
        self.counts[new_pos.key()] += 1
        self._check_end(move, mover_white)
        return san

    def _check_end(self, move, mover_white):
        learner_moved = mover_white == self.learner_white
        if self.drill and self.drill.goal == "promote" and learner_moved and move[2]:
            self.result = {"winner": "white" if mover_white else "black", "reason": "promotion"}
            return
        reason = game_end_reason(self.pos, self.counts)
        if reason is None:
            return
        if reason == "checkmate":
            self.result = {"winner": "white" if mover_white else "black", "reason": "checkmate"}
        else:
            self.result = {"winner": None, "reason": reason}

    def undo(self):
        """Take back moves until it is the learner's turn again. Returns how many moves were taken back."""
        taken = 0
        while self.moves:
            self.counts[self.pos.key()] -= 1
            self.positions.pop()
            self.moves.pop()
            self.sans.pop()
            self.quality.pop(len(self.moves), None)
            taken += 1
            if self.learner_to_move():
                break
        self.result = None
        return taken

    def resign(self):
        if not self.is_over:
            self.result = {"winner": "black" if self.learner_white else "white", "reason": "resignation"}

    # -- clocks ----------------------------------------------------------------
    def tick(self, seconds):
        """Run the clock of the side to move. The clock starts after White's first move."""
        if not self.clock or self.is_over or not self.moves:
            return
        side = "white" if self.white_to_move else "black"
        self.clock[side] -= seconds
        if self.clock[side] <= 0:
            self.clock[side] = 0.0
            self._flag(side == "white")

    def _flag(self, white_flagged):
        other_has_material = count_material(self.pos, not white_flagged) > 0 \
            or any(p in ("P", "p") for p in self.pos.board)
        if other_has_material:
            self.result = {"winner": "black" if white_flagged else "white", "reason": "time"}
        else:
            self.result = {"winner": None, "reason": "timeout vs insufficient material"}

    def seconds_left(self, white):
        return None if not self.clock else self.clock["white" if white else "black"]

    # -- result as seen by the learner --------------------------------------------
    def outcome(self):
        """'win', 'loss', 'draw' for the learner, or None while the game is on."""
        if not self.result:
            return None
        winner = self.result["winner"]
        if winner is None:
            return "draw"
        return "win" if (winner == "white") == self.learner_white else "loss"

    def result_text(self):
        """(title, subtitle) for the end-of-game card."""
        outcome = self.outcome()
        reason = self.result["reason"]
        nice = {"checkmate": "Checkmate", "stalemate": "Stalemate", "time": "Time ran out",
                "resignation": "Resignation", "promotion": "Pawn promoted"}.get(reason, reason.capitalize())
        moves_made = (len(self.moves) + 1) // 2
        if self.drill:
            if outcome == "win":
                par = self.drill.par
                note = "You beat par ({} moves)!".format(par) if moves_made <= par else "Par was {} moves.".format(par)
                return "Drill complete!", "{} in {} moves. {}".format(nice, moves_made, note)
            if outcome == "loss":
                return "Drill failed", nice
            return "Not quite", nice + ". The goal was to win."
        if outcome == "win":
            return "You win!", nice
        if outcome == "loss":
            return "You lost", nice
        return "Draw", nice
