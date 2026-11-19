"""checkme rules engine: board, move generation, FEN and game-end detection.

The board is a list of 64 characters. Uppercase = white, lowercase = black, "." = empty.
Square 0 is a8 and square 63 is h1 (so row 0 is rank 8).

A move is a tuple (start, end, promo) where promo is "" or one of "q", "r", "b", "n".
Castling is a king move of two squares (e1g1) and en passant is a normal pawn capture
onto the en-passant square; make_move() takes care of moving the rook / removing the pawn.
"""

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
FILES = "abcdefgh"

WHITE_PIECES = frozenset("PNBRQK")
BLACK_PIECES = frozenset("pnbrqk")


def square_name(square):
    """52 -> 'e2'"""
    return FILES[square & 7] + str(8 - (square >> 3))


def name_to_square(name):
    """'e2' -> 52"""
    return (8 - int(name[1])) * 8 + FILES.index(name[0])


def is_white_piece(piece):
    return piece in WHITE_PIECES


# ---------------------------------------------------------------------------
# Pre-computed tables (makes move generation much faster)
# ---------------------------------------------------------------------------
_KNIGHT_JUMPS = [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]
_KING_STEPS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_ROOK_DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_BISHOP_DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]


def _inside(row, col):
    return 0 <= row < 8 and 0 <= col < 8


def _build_tables():
    knight, king, white_pawn, black_pawn, rook_rays, bishop_rays = [], [], [], [], [], []
    for sq in range(64):
        row, col = divmod(sq, 8)
        knight.append(tuple(
            (row + dr) * 8 + col + dc for dr, dc in _KNIGHT_JUMPS if _inside(row + dr, col + dc)))
        king.append(tuple(
            (row + dr) * 8 + col + dc for dr, dc in _KING_STEPS if _inside(row + dr, col + dc)))
        # squares a white pawn on sq attacks (up the board = smaller row)
        white_pawn.append(tuple(
            (row - 1) * 8 + col + dc for dc in (-1, 1) if _inside(row - 1, col + dc)))
        black_pawn.append(tuple(
            (row + 1) * 8 + col + dc for dc in (-1, 1) if _inside(row + 1, col + dc)))
        for directions, table in ((_ROOK_DIRS, rook_rays), (_BISHOP_DIRS, bishop_rays)):
            rays = []
            for dr, dc in directions:
                ray = []
                r, c = row + dr, col + dc
                while _inside(r, c):
                    ray.append(r * 8 + c)
                    r += dr
                    c += dc
                if ray:
                    rays.append(tuple(ray))
            table.append(tuple(rays))
    return knight, king, white_pawn, black_pawn, rook_rays, bishop_rays


KNIGHT_MOVES, KING_MOVES, WP_ATTACKS, BP_ATTACKS, ROOK_RAYS, BISHOP_RAYS = _build_tables()

# Which castling rights are lost when a piece moves from / to these squares
CASTLE_LOSS = {60: "KQ", 4: "kq", 63: "K", 56: "Q", 7: "k", 0: "q"}


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------
class Position:
    """A chess position: pieces, side to move, castling rights, en passant, move counters."""

    __slots__ = ("board", "white_to_move", "castling", "ep", "halfmove", "fullmove")

    def __init__(self, board=None, white_to_move=True, castling="KQkq", ep=-1, halfmove=0, fullmove=1):
        if board is None:
            board = _board_from_fen_rows(START_FEN.split()[0])
        self.board = list(board)
        self.white_to_move = white_to_move
        self.castling = castling
        self.ep = ep  # en passant target square, or -1
        self.halfmove = halfmove  # moves since the last capture or pawn move (50-move rule)
        self.fullmove = fullmove

    # -- FEN ---------------------------------------------------------------
    @classmethod
    def from_fen(cls, fen):
        parts = fen.split()
        if len(parts) < 2:
            raise ValueError("Bad FEN: " + fen)
        board = _board_from_fen_rows(parts[0])
        white = parts[1] == "w"
        castling = parts[2] if len(parts) > 2 and parts[2] != "-" else ""
        ep = name_to_square(parts[3]) if len(parts) > 3 and parts[3] != "-" else -1
        halfmove = int(parts[4]) if len(parts) > 4 else 0
        fullmove = int(parts[5]) if len(parts) > 5 else 1
        return cls(board, white, castling, ep, halfmove, fullmove)

    def to_fen(self):
        rows = []
        for row in range(8):
            text, empty = "", 0
            for piece in self.board[row * 8:row * 8 + 8]:
                if piece == ".":
                    empty += 1
                else:
                    if empty:
                        text += str(empty)
                        empty = 0
                    text += piece
            if empty:
                text += str(empty)
            rows.append(text)
        ep = square_name(self.ep) if self.ep >= 0 else "-"
        return "{} {} {} {} {} {}".format(
            "/".join(rows), "w" if self.white_to_move else "b",
            self.castling or "-", ep, self.halfmove, self.fullmove)

    def copy(self):
        return Position(self.board, self.white_to_move, self.castling, self.ep, self.halfmove, self.fullmove)

    def key(self):
        """A string that is the same for repeated positions (used for repetition draws)."""
        ep = -1
        if self.ep >= 0:  # only count en passant if a pawn can really capture
            if self.white_to_move:
                if any(self.board[s] == "P" for s in BP_ATTACKS[self.ep]):
                    ep = self.ep
            elif any(self.board[s] == "p" for s in WP_ATTACKS[self.ep]):
                ep = self.ep
        return "".join(self.board) + ("w" if self.white_to_move else "b") + self.castling + str(ep)

    # -- Making a move -----------------------------------------------------
    def make_move(self, move):
        """Return a NEW position after the move (this one is not changed)."""
        start, end, promo = move
        board = self.board[:]
        piece = board[start]
        white = self.white_to_move
        castling = self.castling
        ep = -1
        halfmove = self.halfmove + 1
        if board[end] != "." or piece == "P" or piece == "p":
            halfmove = 0

        board[start] = "."
        if piece == "P" or piece == "p":
            if end == self.ep and (start & 7) != (end & 7):
                board[end + 8 if white else end - 8] = "."  # en passant capture
            elif end - start == 16 or start - end == 16:
                ep = (start + end) // 2
            if promo:
                piece = promo.upper() if white else promo
        elif piece == "K" or piece == "k":
            if end - start == 2:  # castle kingside: move the rook too
                board[start + 1] = board[start + 3]
                board[start + 3] = "."
            elif start - end == 2:  # castle queenside
                board[start - 1] = board[start - 4]
                board[start - 4] = "."

        board[end] = piece

        if castling:
            for square in (start, end):
                lost = CASTLE_LOSS.get(square)
                if lost:
                    for letter in lost:
                        castling = castling.replace(letter, "")

        return Position(board, not white, castling, ep, halfmove, self.fullmove + (0 if white else 1))


def _board_from_fen_rows(rows_text):
    board = []
    for row_text in rows_text.split("/"):
        for ch in row_text:
            if ch.isdigit():
                board.extend("." * int(ch))
            else:
                board.append(ch)
    if len(board) != 64:
        raise ValueError("Bad FEN board: " + rows_text)
    return board


# ---------------------------------------------------------------------------
# Attacks and check
# ---------------------------------------------------------------------------
def is_square_attacked(board, square, by_white):
    """Is this square attacked by any piece of the given colour?"""
    if by_white:
        pawn, knight, bishop, rook, queen, king = "P", "N", "B", "R", "Q", "K"
        pawn_sources = BP_ATTACKS[square]
    else:
        pawn, knight, bishop, rook, queen, king = "p", "n", "b", "r", "q", "k"
        pawn_sources = WP_ATTACKS[square]

    for s in pawn_sources:
        if board[s] == pawn:
            return True
    for s in KNIGHT_MOVES[square]:
        if board[s] == knight:
            return True
    for s in KING_MOVES[square]:
        if board[s] == king:
            return True
    for ray in ROOK_RAYS[square]:
        for s in ray:
            p = board[s]
            if p != ".":
                if p == rook or p == queen:
                    return True
                break
    for ray in BISHOP_RAYS[square]:
        for s in ray:
            p = board[s]
            if p != ".":
                if p == bishop or p == queen:
                    return True
                break
    return False


def king_attacked(board, white):
    """Is the king of this colour in check on this board?"""
    return is_square_attacked(board, board.index("K" if white else "k"), not white)


def is_in_check(pos, white=None):
    if white is None:
        white = pos.white_to_move
    return king_attacked(pos.board, white)


# ---------------------------------------------------------------------------
# Move generation
# ---------------------------------------------------------------------------
_PROMOS = ("q", "r", "b", "n")


def pseudo_legal_moves(pos, captures_only=False):
    """Moves that follow the piece rules but may leave the own king in check.
    With captures_only=True only captures and queen promotions are returned."""
    board = pos.board
    white = pos.white_to_move
    own = WHITE_PIECES if white else BLACK_PIECES
    enemy = BLACK_PIECES if white else WHITE_PIECES
    moves = []
    add = moves.append

    for sq in range(64):
        piece = board[sq]
        if piece not in own:
            continue
        kind = piece if white else piece.upper()

        if kind == "P":
            if white:
                step, start_row, attacks, last_row = -8, 6, WP_ATTACKS[sq], 0
            else:
                step, start_row, attacks, last_row = 8, 1, BP_ATTACKS[sq], 7
            one = sq + step
            if board[one] == ".":
                if (one >> 3) == last_row:
                    for promo in (("q",) if captures_only else _PROMOS):
                        add((sq, one, promo))
                elif not captures_only:
                    add((sq, one, ""))
                    if (sq >> 3) == start_row and board[sq + 2 * step] == ".":
                        add((sq, sq + 2 * step, ""))
            for target in attacks:
                victim = board[target]
                if victim in enemy:
                    if (target >> 3) == last_row:
                        for promo in (("q",) if captures_only else _PROMOS):
                            add((sq, target, promo))
                    else:
                        add((sq, target, ""))
                elif target == pos.ep and victim == ".":
                    add((sq, target, ""))  # en passant

        elif kind == "N" or kind == "K":
            for target in (KNIGHT_MOVES[sq] if kind == "N" else KING_MOVES[sq]):
                victim = board[target]
                if victim in enemy or (victim == "." and not captures_only):
                    add((sq, target, ""))

        else:  # rook, bishop, queen
            if kind == "R":
                rays = ROOK_RAYS[sq]
            elif kind == "B":
                rays = BISHOP_RAYS[sq]
            else:
                rays = ROOK_RAYS[sq] + BISHOP_RAYS[sq]
            for ray in rays:
                for target in ray:
                    victim = board[target]
                    if victim == ".":
                        if not captures_only:
                            add((sq, target, ""))
                    else:
                        if victim in enemy:
                            add((sq, target, ""))
                        break

    if not captures_only and pos.castling:
        _add_castling_moves(pos, moves)
    return moves


def _add_castling_moves(pos, moves):
    board = pos.board
    if pos.white_to_move:
        if board[60] != "K" or is_square_attacked(board, 60, False):
            return
        if "K" in pos.castling and board[63] == "R" and board[61] == "." and board[62] == "." \
                and not is_square_attacked(board, 61, False) and not is_square_attacked(board, 62, False):
            moves.append((60, 62, ""))
        if "Q" in pos.castling and board[56] == "R" and board[57] == "." and board[58] == "." \
                and board[59] == "." and not is_square_attacked(board, 59, False) \
                and not is_square_attacked(board, 58, False):
            moves.append((60, 58, ""))
    else:
        if board[4] != "k" or is_square_attacked(board, 4, True):
            return
        if "k" in pos.castling and board[7] == "r" and board[5] == "." and board[6] == "." \
                and not is_square_attacked(board, 5, True) and not is_square_attacked(board, 6, True):
            moves.append((4, 6, ""))
        if "q" in pos.castling and board[0] == "r" and board[1] == "." and board[2] == "." \
                and board[3] == "." and not is_square_attacked(board, 3, True) \
                and not is_square_attacked(board, 2, True):
            moves.append((4, 2, ""))


def legal_moves(pos):
    """Moves that do not leave your own king in check."""
    white = pos.white_to_move
    legal = []
    for move in pseudo_legal_moves(pos):
        if not king_attacked(pos.make_move(move).board, white):
            legal.append(move)
    return legal


def has_legal_move(pos):
    white = pos.white_to_move
    for move in pseudo_legal_moves(pos):
        if not king_attacked(pos.make_move(move).board, white):
            return True
    return False


# ---------------------------------------------------------------------------
# Move text ("e2e4", "e7e8q")
# ---------------------------------------------------------------------------
def move_to_text(move):
    start, end, promo = move
    return square_name(start) + square_name(end) + promo


def parse_move_text(text):
    """'e2e4' -> (52, 36, ''), 'e7e8q' -> (12, 4, 'q'). Returns None if the text is not a move."""
    text = text.strip().lower()
    if len(text) not in (4, 5):
        return None
    if text[0] not in FILES or text[2] not in FILES or text[1] not in "12345678" or text[3] not in "12345678":
        return None
    promo = text[4] if len(text) == 5 else ""
    if promo and promo not in "qrbn":
        return None
    return (name_to_square(text[0:2]), name_to_square(text[2:4]), promo)


# ---------------------------------------------------------------------------
# Game end
# ---------------------------------------------------------------------------
def game_status(pos):
    """'checkmate', 'stalemate' or 'playing' for the side to move."""
    if has_legal_move(pos):
        return "playing"
    return "checkmate" if is_in_check(pos) else "stalemate"


def insufficient_material(pos):
    """True when neither side can possibly checkmate (K v K, K+minor v K, K+B v K+B same colour)."""
    minors = []
    for sq, piece in enumerate(pos.board):
        kind = piece.lower()
        if kind in ".k":
            continue
        if kind in "pqr":
            return False
        minors.append((kind, piece.isupper(), (sq >> 3) + (sq & 7) & 1))
    if len(minors) <= 1:
        return True
    if all(m[0] == "b" for m in minors):
        return len({m[2] for m in minors}) == 1  # all bishops on the same colour
    return False


def game_end_reason(pos, key_counts=None):
    """Why the game is over, or None if it is still going.
    key_counts maps Position.key() -> how many times that position has happened."""
    status = game_status(pos)
    if status != "playing":
        return status
    if insufficient_material(pos):
        return "insufficient material"
    if pos.halfmove >= 100:
        return "fifty-move rule"
    if key_counts and key_counts.get(pos.key(), 0) >= 3:
        return "threefold repetition"
    return None


def count_material(pos, white):
    """Total value of one side's non-king pieces (pawn 1, minor 3, rook 5, queen 9)."""
    values = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9}
    total = 0
    for piece in pos.board:
        if piece != "." and (piece in WHITE_PIECES) == white:
            total += values.get(piece.lower(), 0)
    return total
