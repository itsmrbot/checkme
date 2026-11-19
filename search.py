"""The engine's brain: evaluation, search and the 9 difficulty levels.

evaluate()     scores a position (centipawns: 100 = one pawn) for the side to move.
Searcher       looks ahead with negamax + alpha-beta, quiescence search and iterative
               deepening (it searches 1 move deep, then 2, then 3 ... until time is up).
pick_engine_move() chooses a move for a level 1-9. Low levels look less far ahead and
               sometimes play a random or "noisy" move, the way a beginner would.
"""

import random
import time
from collections import Counter, namedtuple

from engine import (
    KING_MOVES,
    count_material,
    is_in_check,
    king_attacked,
    legal_moves,
    pseudo_legal_moves,
)

MATE = 100000
INFINITY = 10 ** 7

# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
PIECE_VALUE = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}

# Piece-square tables (white's point of view, row 0 = rank 8). Black uses them flipped.
_PST = {
    "P": [0, 0, 0, 0, 0, 0, 0, 0,
          50, 50, 50, 50, 50, 50, 50, 50,
          10, 10, 20, 30, 30, 20, 10, 10,
          5, 5, 10, 25, 25, 10, 5, 5,
          0, 0, 0, 20, 20, 0, 0, 0,
          5, -5, -10, 0, 0, -10, -5, 5,
          5, 10, 10, -20, -20, 10, 10, 5,
          0, 0, 0, 0, 0, 0, 0, 0],
    "N": [-50, -40, -30, -30, -30, -30, -40, -50,
          -40, -20, 0, 0, 0, 0, -20, -40,
          -30, 0, 10, 15, 15, 10, 0, -30,
          -30, 5, 15, 20, 20, 15, 5, -30,
          -30, 0, 15, 20, 20, 15, 0, -30,
          -30, 5, 10, 15, 15, 10, 5, -30,
          -40, -20, 0, 5, 5, 0, -20, -40,
          -50, -40, -30, -30, -30, -30, -40, -50],
    "B": [-20, -10, -10, -10, -10, -10, -10, -20,
          -10, 0, 0, 0, 0, 0, 0, -10,
          -10, 0, 5, 10, 10, 5, 0, -10,
          -10, 5, 5, 10, 10, 5, 5, -10,
          -10, 0, 10, 10, 10, 10, 0, -10,
          -10, 10, 10, 10, 10, 10, 10, -10,
          -10, 5, 0, 0, 0, 0, 5, -10,
          -20, -10, -10, -10, -10, -10, -10, -20],
    "R": [0, 0, 0, 0, 0, 0, 0, 0,
          5, 10, 10, 10, 10, 10, 10, 5,
          -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5,
          -5, 0, 0, 0, 0, 0, 0, -5,
          0, 0, 0, 5, 5, 0, 0, 0],
    "Q": [-20, -10, -10, -5, -5, -10, -10, -20,
          -10, 0, 0, 0, 0, 0, 0, -10,
          -10, 0, 5, 5, 5, 5, 0, -10,
          -5, 0, 5, 5, 5, 5, 0, -5,
          0, 0, 5, 5, 5, 5, 0, -5,
          -10, 5, 5, 5, 5, 5, 0, -10,
          -10, 0, 5, 0, 0, 0, 0, -10,
          -20, -10, -10, -5, -5, -10, -10, -20],
}
_KING_MIDDLEGAME = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20]
_KING_ENDGAME = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50]

# TABLE[piece][square]: positive for white pieces, negative for black pieces
TABLE = {}
for _piece, _pst in _PST.items():
    TABLE[_piece] = [PIECE_VALUE[_piece] + _pst[sq] for sq in range(64)]
    TABLE[_piece.lower()] = [-(PIECE_VALUE[_piece] + _pst[sq ^ 56]) for sq in range(64)]

NON_PAWN_VALUE = {"N": 320, "B": 330, "R": 500, "Q": 900, "n": 320, "b": 330, "r": 500, "q": 900}
PASSED_PAWN_BONUS = [0, 10, 20, 40, 70, 120, 200]

# Distance of each square from the centre (used to drive a lone king to the edge)
CENTRE_DISTANCE = [int(abs(sq // 8 - 3.5) + abs(sq % 8 - 3.5)) - 1 for sq in range(64)]


def evaluate(pos):
    """Score for the side to move (positive = good for them)."""
    board = pos.board
    score = 0
    non_pawn = 0
    white_bishops = black_bishops = 0
    white_pieces = black_pieces = 0  # count of non-king pieces including pawns
    white_pawns = [[] for _ in range(8)]  # pawn rows on each file
    black_pawns = [[] for _ in range(8)]
    white_king = black_king = 0

    for sq in range(64):
        piece = board[sq]
        if piece == ".":
            continue
        if piece == "K":
            white_king = sq
            continue
        if piece == "k":
            black_king = sq
            continue
        score += TABLE[piece][sq]
        if piece == "P":
            white_pawns[sq & 7].append(sq >> 3)
            white_pieces += 1
        elif piece == "p":
            black_pawns[sq & 7].append(sq >> 3)
            black_pieces += 1
        else:
            non_pawn += NON_PAWN_VALUE[piece]
            if piece.isupper():
                white_pieces += 1
                if piece == "B":
                    white_bishops += 1
            else:
                black_pieces += 1
                if piece == "b":
                    black_bishops += 1

    has_pawns = any(white_pawns) or any(black_pawns)
    if not has_pawns and non_pawn <= 330:
        return 0  # bare kings or a single minor piece: cannot win

    if white_bishops >= 2:
        score += 30
    if black_bishops >= 2:
        score -= 30

    for f in range(8):
        score -= 12 * max(0, len(white_pawns[f]) - 1)  # doubled pawns
        score += 12 * max(0, len(black_pawns[f]) - 1)
        for row in white_pawns[f]:  # passed pawns
            if not any(r < row for ff in range(max(0, f - 1), min(7, f + 1) + 1) for r in black_pawns[ff]):
                score += PASSED_PAWN_BONUS[6 - row]
        for row in black_pawns[f]:
            if not any(r > row for ff in range(max(0, f - 1), min(7, f + 1) + 1) for r in white_pawns[ff]):
                score -= PASSED_PAWN_BONUS[row - 1]

    # King: safe in the corner early on, active in the centre in endgames
    phase = min(1.0, max(0.0, (non_pawn - 1500) / 3000.0))
    score += int(phase * _KING_MIDDLEGAME[white_king] + (1 - phase) * _KING_ENDGAME[white_king])
    score -= int(phase * _KING_MIDDLEGAME[black_king ^ 56] + (1 - phase) * _KING_ENDGAME[black_king ^ 56])

    # Mop-up: with a big material lead against a lone king, push it to the edge and bring our king close
    if black_pieces == 0 and white_pieces > 0 and non_pawn >= 500:
        score += _mop_up(black_king, white_king)
    elif white_pieces == 0 and black_pieces > 0 and non_pawn >= 500:
        score -= _mop_up(white_king, black_king)

    return score if pos.white_to_move else -score


def _mop_up(losing_king, winning_king):
    row_gap = abs(losing_king // 8 - winning_king // 8)
    col_gap = abs(losing_king % 8 - winning_king % 8)
    return 47 * CENTRE_DISTANCE[losing_king] // 10 + 16 * (14 - row_gap - col_gap) // 10


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchStopped(Exception):
    """Raised inside the search when time runs out."""


def _victim_value(piece):
    return PIECE_VALUE.get(piece.upper(), 0)


class Searcher:
    def __init__(self, history_keys=()):
        self.nodes = 0
        self.deadline = None
        self.killers = [[None, None] for _ in range(80)]
        self.seen = Counter(history_keys)  # positions already played in the real game
        self.path = Counter()  # positions on the current search line

    def _tick(self):
        self.nodes += 1
        if self.deadline is not None and (self.nodes & 511) == 0 and time.perf_counter() > self.deadline:
            raise SearchStopped()

    def order(self, pos, moves, ply, first=None):
        """Sort moves so likely-good ones are searched first (makes alpha-beta much faster)."""
        board = pos.board
        killers = self.killers[ply] if ply < 80 else (None, None)

        def score(move):
            if move == first:
                return 100000
            start, end, promo = move
            victim = board[end]
            if victim != ".":
                return 10000 + 10 * _victim_value(victim) - _victim_value(board[start]) // 10
            if promo:
                return 9000 + _victim_value(promo)
            if move == killers[0] or move == killers[1]:
                return 5000
            return 0

        return sorted(moves, key=score, reverse=True)

    def quiesce(self, pos, alpha, beta, ply):
        """Keep searching captures until things calm down, so we never judge a position mid-exchange."""
        self._tick()
        stand_pat = evaluate(pos)
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        white = pos.white_to_move
        board = pos.board
        for move in self.order(pos, pseudo_legal_moves(pos, captures_only=True), ply):
            victim = board[move[1]]
            if victim != "." and stand_pat + _victim_value(victim) + 200 < alpha and not move[2]:
                continue  # even winning this piece would not help
            child = pos.make_move(move)
            if king_attacked(child.board, white):
                continue
            score = -self.quiesce(child, -beta, -alpha, ply + 1)
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    def negamax(self, pos, depth, alpha, beta, ply):
        self._tick()
        if pos.halfmove >= 100:
            return 0
        white = pos.white_to_move
        in_check = king_attacked(pos.board, white)
        if in_check and ply < 60:
            depth += 1  # look further when in check
        if depth <= 0:
            return self.quiesce(pos, alpha, beta, ply)

        best = -INFINITY
        found_legal = False
        for move in self.order(pos, pseudo_legal_moves(pos), ply):
            child = pos.make_move(move)
            if king_attacked(child.board, white):
                continue
            found_legal = True

            key = child.key()
            if self.seen[key] >= 1 or self.path[key] >= 1:
                score = 0  # repeating a position: treat as a draw
            else:
                self.path[key] += 1
                try:
                    score = -self.negamax(child, depth - 1, -beta, -alpha, ply + 1)
                finally:
                    self.path[key] -= 1

            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                if pos.board[move[1]] == "." and ply < 80 and self.killers[ply][0] != move:
                    self.killers[ply][1] = self.killers[ply][0]
                    self.killers[ply][0] = move
                break

        if not found_legal:
            return -(MATE - ply) if in_check else 0
        return best

    def search_root(self, pos, moves, depth):
        """Search every root move to `depth`. Returns (best_move, score)."""
        alpha, beta = -INFINITY, INFINITY
        best_move, best_score = moves[0], -INFINITY
        for move in moves:
            child = pos.make_move(move)
            key = child.key()
            self.path[key] += 1
            try:
                score = -self.negamax(child, depth - 1, -beta, -alpha, 1)
            finally:
                self.path[key] -= 1
            if score > best_score:
                best_move, best_score = move, score
            if best_score > alpha:
                alpha = best_score
        return best_move, best_score


def find_best_move(pos, max_depth, seconds=None, history_keys=()):
    """Iterative deepening. Returns (move, score, depth_reached); move is None if the game is over."""
    legal = legal_moves(pos)
    if not legal:
        return None, 0, 0
    searcher = Searcher(history_keys)
    moves = searcher.order(pos, legal, 0)
    best_move, best_score, reached = moves[0], 0, 0
    start = time.perf_counter()
    for depth in range(1, max_depth + 1):
        searcher.deadline = None if depth == 1 or seconds is None else start + seconds
        try:
            move, score = searcher.search_root(pos, moves, depth)
        except SearchStopped:
            break
        best_move, best_score, reached = move, score, depth
        moves.remove(move)
        moves.insert(0, move)
        if abs(score) > MATE - 100:
            break  # found a forced mate
        if seconds is not None and time.perf_counter() - start > seconds * 0.5:
            break  # the next depth would take longer than we have
        if len(legal) == 1:
            break
    return best_move, best_score, reached


# ---------------------------------------------------------------------------
# Levels
# ---------------------------------------------------------------------------
Level = namedtuple("Level", "name depth seconds random_chance noise")

LEVELS = {
    1: Level("Rookie", 1, None, 0.45, 200),
    2: Level("Casual", 1, None, 0.25, 120),
    3: Level("Novice", 2, None, 0.12, 90),
    4: Level("Improver", 2, None, 0.04, 50),
    5: Level("Club player", 3, 2.0, 0.0, 25),
    6: Level("Advanced", 4, 2.0, 0.0, 0),
    7: Level("Strong", 5, 3.0, 0.0, 0),
    8: Level("Expert", 6, 5.0, 0.0, 0),
    9: Level("Master", 8, 8.0, 0.0, 0),
}


def level_name(level):
    return "Level {} - {}".format(level, LEVELS[level].name)


def pick_engine_move(pos, level, history_keys=(), seconds_left=None):
    """Choose the computer's move for a level from 1 to 9.
    seconds_left: time on the computer's clock (so it can play faster when short of time)."""
    cfg = LEVELS[level]
    legal = legal_moves(pos)
    if not legal:
        return None

    if random.random() < cfg.random_chance:
        return random.choice(legal)

    seconds = cfg.seconds
    if seconds_left is not None:
        budget = max(0.05, seconds_left / 30.0)
        seconds = budget if seconds is None else min(seconds, budget)

    if cfg.noise > 0:
        return _noisy_best(pos, legal, cfg, history_keys)

    move, _score, _depth = find_best_move(pos, cfg.depth, seconds, history_keys)
    return move


def _noisy_best(pos, legal, cfg, history_keys):
    """Score each move at a shallow depth and add random 'mistakes' to the scores."""
    searcher = Searcher(history_keys)
    best_move, best_score = legal[0], -INFINITY
    for move in legal:
        child = pos.make_move(move)
        score = -searcher.negamax(child, cfg.depth - 1, -INFINITY, INFINITY, 1)
        score += random.gauss(0, cfg.noise)
        if score > best_score:
            best_move, best_score = move, score
    return best_move


def analyse(pos, max_depth=4, seconds=2.0, history_keys=()):
    """Best move and its score for the side to move (used for hints and the evaluation bar)."""
    move, score, _depth = find_best_move(pos, max_depth, seconds, history_keys)
    return move, score


def score_after(pos, move, depth=3, seconds=1.0, history_keys=()):
    """Score (for the player who made `move`) of the position after the move."""
    child = pos.make_move(move)
    _best, score, _d = find_best_move(child, depth, seconds, history_keys)
    if _best is None:  # the move ended the game
        return MATE if is_in_check(child) else 0
    return -score


def clamp_score(score, limit=1500):
    """Turn a mate score into a big but finite number, for the evaluation bar and move grading."""
    return max(-limit, min(limit, score))
