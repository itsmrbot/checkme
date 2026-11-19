"""Standard algebraic notation (SAN): 'e4', 'Nf3', 'exd5', 'O-O', 'e8=Q+' ...

move_to_san() writes a move as text, san_to_move() reads it back.
"""

import re

from engine import FILES, has_legal_move, is_in_check, legal_moves, square_name

_SAN_PATTERN = re.compile(r"^([NBRQK])?([a-h])?([1-8])?(x)?([a-h][1-8])(?:=?([NBRQnbrq]))?$")


def move_to_san(pos, move, legal=None):
    """Write a legal move in standard notation, including + for check and # for mate."""
    if legal is None:
        legal = legal_moves(pos)
    start, end, promo = move
    board = pos.board
    piece = board[start]
    kind = piece.upper()

    if kind == "K" and abs(end - start) == 2:
        san = "O-O" if end > start else "O-O-O"
    else:
        is_capture = board[end] != "." or (kind == "P" and (start & 7) != (end & 7))
        if kind == "P":
            san = (FILES[start & 7] + "x" if is_capture else "") + square_name(end)
            if promo:
                san += "=" + promo.upper()
        else:
            rivals = [m for m in legal if m != move and m[1] == end and board[m[0]] == piece]
            hint = ""
            if rivals:
                if not any((m[0] & 7) == (start & 7) for m in rivals):
                    hint = FILES[start & 7]
                elif not any((m[0] >> 3) == (start >> 3) for m in rivals):
                    hint = str(8 - (start >> 3))
                else:
                    hint = square_name(start)
            san = kind + hint + ("x" if is_capture else "") + square_name(end)

    after = pos.make_move(move)
    if is_in_check(after):
        san += "#" if not has_legal_move(after) else "+"
    return san


def san_to_move(pos, san):
    """Find the legal move that a SAN string describes. Raises ValueError if there is none."""
    text = san.strip().replace("0", "O").rstrip("+#!?")
    legal = legal_moves(pos)

    if text in ("O-O", "O-O-O"):
        row_start = 60 if pos.white_to_move else 4
        target = row_start + (2 if text == "O-O" else -2)
        for move in legal:
            if move[0] == row_start and move[1] == target and pos.board[row_start].upper() == "K":
                return move
        raise ValueError("Cannot castle: " + san)

    match = _SAN_PATTERN.match(text)
    if not match:
        raise ValueError("Not a move: " + san)
    piece, from_file, from_rank, _capture, target, promo = match.groups()
    kind = piece or "P"
    end = (8 - int(target[1])) * 8 + FILES.index(target[0])
    promo = promo.lower() if promo else ""

    found = []
    for move in legal:
        start = move[0]
        if move[1] != end or pos.board[start].upper() != kind or move[2] != promo:
            continue
        if from_file and FILES[start & 7] != from_file:
            continue
        if from_rank and str(8 - (start >> 3)) != from_rank:
            continue
        found.append(move)

    if len(found) == 1:
        return found[0]
    if not found:
        raise ValueError("Illegal move: " + san)
    raise ValueError("Ambiguous move: " + san)


def parse_line(pos, text):
    """Turn '1. e4 e5 2. Nf3 Nc6' into a list of moves, starting from pos."""
    moves = []
    for token in text.replace("\n", " ").split():
        if re.match(r"^\d+\.(\.\.)?$", token):
            continue
        token = re.sub(r"^\d+\.+", "", token)  # '1.e4' -> 'e4'
        if not token or token in ("1-0", "0-1", "1/2-1/2", "*"):
            continue
        move = san_to_move(pos, token)
        moves.append(move)
        pos = pos.make_move(move)
    return moves
