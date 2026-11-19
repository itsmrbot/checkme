"""Practice content: opening lines, middlegame plans, endgame drills, opening names, book.

Everything here is plain data. The tests check that every line is legal and that
every endgame position is a valid, playable position.
"""

import random
import re
from collections import namedtuple

from engine import Position
from notation import parse_line

Opening = namedtuple("Opening", "id name eco side moves idea structure plans comments")


def _comments(*pairs):
    """pairs of (label, text) with labels like '4.c3' (white move) or '4...Nf6' (black move).
    Returns {ply_index: (san, text)} so the tests can check the label matches the move."""
    result = {}
    for label, text in pairs:
        match = re.match(r"^(\d+)(\.\.\.|\.)(.+)$", label)  # try '...' before '.'
        number, dots, san = int(match.group(1)), match.group(2), match.group(3)
        ply = 2 * (number - 1) + (0 if dots == "." else 1)
        result[ply] = (san, text)
    return result


OPENINGS = [
    # ------------------------------------------------------------- White
    Opening(
        "italian", "Italian Game: Giuoco Pianissimo", "C54", "white",
        "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3 Nf6 5.d3 d6 6.O-O O-O 7.Re1 a6 8.Bb3 Ba7 9.h3 h6 10.Nbd2",
        "Develop quickly, aim at f7 and build a solid centre. This is the slow, strategic version of the Italian.",
        "Semi-closed centre: White pawns on d3/e4 against Black pawns on d6/e5. A slow manoeuvring game.",
        ["Reroute the knight: Nbd2-f1-g3", "Prepare the central break d3-d4", "Keep the bishops pointed at f7 and the kingside"],
        _comments(
            ("1.e4", "Take the centre and open lines for your queen and bishop."),
            ("3.Bc4", "The bishop eyes f7, Black's weakest square early on."),
            ("4.c3", "Prepares d4 to build a strong pawn centre."),
            ("5.d3", "A calm setup (Pianissimo means 'very quiet'): keep the tension, develop, castle."),
            ("6.O-O", "Castle early. The king is safe and the rook comes towards the centre."),
            ("7.Re1", "Supports the e4 pawn and eyes the e-file."),
            ("9.h3", "Stops ...Bg4 pinning your knight."),
            ("10.Nbd2", "The last minor piece joins in. Next ideas: Nf1-g3 and d4."),
        ),
    ),
    Opening(
        "ruy-closed", "Ruy Lopez: Closed (Chigorin)", "C96", "white",
        "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 d6 8.c3 O-O 9.h3 Na5 10.Bc2 c5 11.d4 Qc7",
        "Pressure the knight that defends e5 and play for a long, strategic fight in the centre.",
        "Closed centre with White pawns on e4/d4 against Black's c5/d6/e5. Plenty of manoeuvring.",
        ["Play d4 to challenge Black's centre", "Manoeuvre the knight Nbd2-f1-g3", "Keep the bishop on the b3-g8 diagonal"],
        _comments(
            ("3.Bb5", "Attacks the knight that defends e5. The Ruy Lopez has been popular for 400 years."),
            ("4.Ba4", "Keep the pin alive instead of giving up the bishop."),
            ("5.O-O", "Castle first. If Black takes on e4, White hits back with d4."),
            ("6.Re1", "Protects e4 so that the knight can no longer be taken."),
            ("8.c3", "Prepares d4 and gives the bishop a retreat square on c2."),
            ("9.h3", "Stops ...Bg4 so the knight on f3 is not pinned."),
            ("11.d4", "The central strike. White fights for the middle of the board."),
        ),
    ),
    Opening(
        "scotch", "Scotch Game", "C45", "white",
        "1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Nf6 5.Nxc6 bxc6 6.e5 Qe7 7.Qe2 Nd5 8.c4 Ba6",
        "Open the centre at once and get active pieces and a space advantage.",
        "Open game: White has more space and a lead in development; Black has doubled c-pawns.",
        ["Use the extra space in the centre", "Attack Black's doubled c-pawns", "Watch for tactics along the a6-f1 diagonal"],
        _comments(
            ("3.d4", "Opens the centre immediately. White wants activity, not a slow build-up."),
            ("5.Nxc6", "Damages Black's pawn structure: the c-pawns will be doubled."),
            ("6.e5", "Gains space with a tempo on the knight."),
            ("8.c4", "Kicks the knight away from the centre."),
            ("8...Ba6", "Black fights back on the light squares. Be careful with the queen on e2."),
        ),
    ),
    Opening(
        "qgd-white", "Queen's Gambit Declined: Tartakower", "D58", "white",
        "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Bg5 Be7 5.e3 O-O 6.Nf3 h6 7.Bh4 b6 8.cxd5 Nxd5 9.Bxe7 Qxe7 10.Nxd5 exd5 11.Rc1 Be6 12.Qa4 c5 13.Qa3 Rc8 14.Bb5 a6 15.dxc5 bxc5 16.O-O Ra7",
        "Fight for the centre with a flank pawn. Black can't safely win the c-pawn, so White gets a lasting initiative.",
        "Symmetrical-looking structures where the c-file and the squares c5/d4 decide the game.",
        ["Pressure the c-file with Rc1", "Fight for c5 and d4", "Trade pieces when Black is cramped"],
        _comments(
            ("2.c4", "A 'gambit' that Black cannot really accept: if ...dxc4 White regains the pawn easily."),
            ("4.Bg5", "Pins the knight that guards d5."),
            ("8.cxd5", "Exchanges to reduce Black's control of the centre."),
            ("11.Rc1", "Rooks belong on open files. The c-file is about to open."),
            ("14.Bb5", "The bishop attacks the knight's defender and gains time on the queenside."),
        ),
    ),
    Opening(
        "london", "London System", "D02", "white",
        "1.d4 d5 2.Bf4 Nf6 3.e3 e6 4.Nf3 Bd6 5.Bg3 O-O 6.Nbd2 c5 7.c3 Nc6 8.Bd3 b6 9.O-O Bb7 10.Ne5",
        "A solid system you can play against almost anything: bishop out, pawns on c3/d4/e3, castle.",
        "A compact pawn pyramid on c3-d4-e3 with the bishop outside the chain.",
        ["Build the pyramid c3, d4, e3", "Put a knight on e5", "Attack the kingside with Qf3, Bd3 and pushing the h-pawn"],
        _comments(
            ("2.Bf4", "Develop the bishop BEFORE playing e3, otherwise it gets locked in."),
            ("3.e3", "A solid pawn chain that supports d4."),
            ("5.Bg3", "Ready to recapture with the h-pawn if Black trades on g3."),
            ("7.c3", "A firm centre and a retreat square for the queen."),
            ("10.Ne5", "A strong outpost in the middle of the board."),
        ),
    ),
    Opening(
        "english", "English Opening: Reversed Sicilian", "A22", "white",
        "1.c4 e5 2.Nc3 Nf6 3.Nf3 Nc6 4.g3 d5 5.cxd5 Nxd5 6.Bg2 Nb6 7.O-O Be7 8.a3 O-O 9.b4 Be6 10.Bb2",
        "Control the centre from the side. It is like a Sicilian Defense where White has an extra move.",
        "Flexible pawn structure. White often expands on the queenside while Black holds the centre.",
        ["Expand on the queenside with b4", "Use the bishop on g2 along the long diagonal", "Look for d3 or d4 at the right moment"],
        _comments(
            ("1.c4", "Controls d5 from the flank. The English keeps many options open."),
            ("4.g3", "Prepares to fianchetto the bishop on g2."),
            ("6.Bg2", "The bishop on the long diagonal puts pressure on Black's queenside."),
            ("8.a3", "Prepares b4 to gain space."),
            ("9.b4", "Space on the queenside. White is attacking, with the bishop on b2 to follow."),
        ),
    ),
    # ------------------------------------------------------------- Black
    Opening(
        "najdorf", "Sicilian Defense: Najdorf", "B90", "black",
        "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Be3 e5 7.Nb3 Be6 8.f3 Be7 9.Qd2 O-O 10.O-O-O Nbd7",
        "Fight for the centre from the side and aim for an unbalanced, double-edged game.",
        "Black has a healthy centre pawn on e5 and more queenside play; White attacks on the kingside.",
        ["Counterattack with ...b5 and ...Rc8", "Break with ...d5 when it is ready", "Keep your king safe from the g4/h4 pawn storm"],
        _comments(
            ("1...c5", "Fights for d4 without copying White. The positions become unbalanced."),
            ("5...a6", "The Najdorf move: stops a knight or bishop landing on b5 and prepares ...b5."),
            ("6...e5", "Kicks the knight away and grabs central space. d5 becomes a little weak."),
            ("7...Be6", "Develops the bishop and prepares the ...d5 break."),
            ("10...Nbd7", "Development is complete. Next come ...b5, ...Rc8 and ...Qc7."),
        ),
    ),
    Opening(
        "french", "French Defense: Classical", "C11", "black",
        "1.e4 e6 2.d4 d5 3.Nc3 Nf6 4.Bg5 Be7 5.e5 Nfd7 6.Bxe7 Qxe7 7.f4 O-O 8.Nf3 c5 9.Qd2 Nc6 10.O-O-O",
        "Build a solid pawn chain and attack White's centre with ...c5.",
        "Closed centre: White has space with the e5 pawn; Black attacks the d4 pawn.",
        ["Attack the d4 pawn with ...c5, ...Nc6 and ...Qb6", "Undermine e5 with ...f6", "Find an active role for the c8 bishop"],
        _comments(
            ("1...e6", "Solid. Prepares ...d5."),
            ("2...d5", "Challenges the e4 pawn straight away."),
            ("4...Be7", "Breaks the pin and prepares to trade White's active bishop."),
            ("5.e5", "White gains space. The knight must move."),
            ("8...c5", "The typical French break. Attack the base of White's pawn chain at d4."),
            ("9...Nc6", "Add more pressure to d4."),
        ),
    ),
    Opening(
        "caro-kann", "Caro-Kann Defense: Classical", "B19", "black",
        "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Bf5 5.Ng3 Bg6 6.h4 h6 7.Nf3 Nd7 8.h5 Bh7 9.Bd3 Bxd3 10.Qxd3 e6 11.Bf4 Ngf6 12.O-O-O Be7",
        "A rock-solid defense: develop the 'bad' bishop outside the pawn chain, then play ...e6.",
        "Black has a healthy pawn structure and no weaknesses; White has a little more space.",
        ["Trade off the c8 bishop's problems by developing it early", "Play ...c5 to challenge d4", "Develop Ngf6 and Be7, then castle"],
        _comments(
            ("1...c6", "Prepares ...d5 with a pawn chain that supports it."),
            ("4...Bf5", "Develop this bishop BEFORE playing ...e6 so that it is not locked in."),
            ("8...Bh7", "Retreat to safety after h5 gained space."),
            ("9...Bxd3", "Trade your active bishop for White's good one."),
            ("10...e6", "Now close the structure. Black is very solid."),
        ),
    ),
    Opening(
        "scandinavian", "Scandinavian Defense", "B01", "black",
        "1.e4 d5 2.exd5 Qxd5 3.Nc3 Qa5 4.d4 Nf6 5.Nf3 c6 6.Bc4 Bf5 7.Bd2 e6",
        "Challenge e4 immediately and accept an early queen move in exchange for a simple, active game.",
        "Open position where Black has fast development and a solid structure.",
        ["Finish development quickly: Bf5, e6, Nbd7, Be7", "Avoid wasting time with the queen", "Play ...Qc7 when the queen is pushed away"],
        _comments(
            ("2...Qxd5", "The queen comes out early, but White cannot easily harass it."),
            ("3...Qa5", "The queen goes to a safe square and keeps an eye on the knight."),
            ("5...c6", "Gives the queen a retreat on c7."),
            ("6...Bf5", "Develop the bishop before closing the position with ...e6."),
        ),
    ),
    Opening(
        "kid", "King's Indian Defense: Classical", "E92", "black",
        "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 7.O-O Nc6 8.d5 Ne7 9.Ne1 Nd7 10.Be3 f5",
        "Let White build a big centre, then attack it. Black's play is on the kingside.",
        "Locked centre with a pawn chain d5-e4 against d6-e5. White goes queenside, Black goes kingside.",
        ["Attack on the kingside with ...f5 and ...g5", "The bishop on g7 is a monster when the centre opens", "Watch out for White's queenside break c5"],
        _comments(
            ("2...g6", "Prepares to fianchetto the bishop to g7."),
            ("4.e4", "White builds a huge centre. Black plans to attack it later."),
            ("6...e5", "Strike at the centre."),
            ("8.d5", "White closes the centre. Now the game becomes a race: White on the queenside, Black on the kingside."),
            ("10...f5", "The kingside attack begins."),
        ),
    ),
    Opening(
        "nimzo", "Nimzo-Indian Defense: Rubinstein", "E47", "black",
        "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.e3 O-O 5.Bd3 d5 6.Nf3 c5 7.O-O Nc6 8.a3 Bxc3 9.bxc3 dxc4 10.Bxc4 Qc7",
        "Control e4 with pieces, and pin the knight on c3. Give up the bishop for the knight to damage White's pawns.",
        "White has the bishop pair and a big centre; Black has targets on c3 and c4.",
        ["Target the doubled c-pawns", "Keep control of e4 with your knights", "Prepare ...e5 when ready"],
        _comments(
            ("3...Bb4", "Pins the knight so that White cannot easily play e4."),
            ("4.e3", "A solid reply: White wants to develop and castle quietly."),
            ("8...Bxc3", "Gives up the bishop pair to double White's c-pawns."),
            ("9...dxc4", "Wins a tempo by attacking the bishop on d3."),
            ("10...Qc7", "Piles up on c3 and the c-file."),
        ),
    ),
    Opening(
        "slav", "Slav Defense", "D17", "black",
        "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 dxc4 5.a4 Bf5 6.e3 e6 7.Bxc4 Bb4 8.O-O Nbd7 9.Qe2 Bg6 10.e4 O-O 11.Bd3 Bh5",
        "Support d5 with a pawn on c6, keeping the c8 bishop free to develop.",
        "A solid, flexible structure with the bishop outside the pawn chain.",
        ["Hand the pawn back for activity when the time is right", "Break with ...c5 or ...e5", "Use your active bishops"],
        _comments(
            ("2...c6", "Supports d5 but keeps the c8 bishop free, unlike ...e6."),
            ("4...dxc4", "Take the pawn. Hold it with ...Bf5 and ...b5 if you can, otherwise give it back."),
            ("5.a4", "Stops ...b5, so the c4 pawn will not stay long."),
            ("5...Bf5", "Develop outside the pawn chain."),
            ("7...Bb4", "Pins the knight on c3 and eyes the e4 square."),
        ),
    ),
]

_line_cache = {}


def opening_moves(opening):
    """The opening's moves as a list of (start, end, promo) tuples."""
    if opening.id not in _line_cache:
        _line_cache[opening.id] = parse_line(Position(), opening.moves)
    return _line_cache[opening.id]


def opening_end_position(opening):
    pos = Position()
    for move in opening_moves(opening):
        pos = pos.make_move(move)
    return pos


def get_opening(opening_id):
    for opening in OPENINGS:
        if opening.id == opening_id:
            return opening
    raise KeyError(opening_id)


# ---------------------------------------------------------------------------
# Opening names (shown while you play when Assist is on)
# ---------------------------------------------------------------------------
_NAME_TABLE = [
    ("e4", "King's Pawn Game"),
    ("e4 e5", "Open Game"),
    ("e4 e5 Nf3", "King's Knight Opening"),
    ("e4 e5 Nf3 Nc6 Bc4", "Italian Game"),
    ("e4 e5 Nf3 Nc6 Bc4 Bc5", "Italian Game: Giuoco Piano"),
    ("e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3", "Italian Game: Giuoco Pianissimo"),
    ("e4 e5 Nf3 Nc6 Bc4 Nf6", "Italian Game: Two Knights Defense"),
    ("e4 e5 Nf3 Nc6 Bb5", "Ruy Lopez"),
    ("e4 e5 Nf3 Nc6 Bb5 a6", "Ruy Lopez: Morphy Defense"),
    ("e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O", "Ruy Lopez: Closed"),
    ("e4 e5 Nf3 Nc6 Bb5 Nf6", "Ruy Lopez: Berlin Defense"),
    ("e4 e5 Nf3 Nc6 d4", "Scotch Game"),
    ("e4 e5 Nf3 Nf6", "Petrov's Defense"),
    ("e4 e5 f4", "King's Gambit"),
    ("e4 e5 Nc3", "Vienna Game"),
    ("e4 e5 Bc4", "Bishop's Opening"),
    ("e4 c5", "Sicilian Defense"),
    ("e4 c5 c3", "Sicilian Defense: Alapin"),
    ("e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3", "Sicilian Defense: Open"),
    ("e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6", "Sicilian Defense: Najdorf"),
    ("e4 e6", "French Defense"),
    ("e4 e6 d4 d5 e5", "French Defense: Advance"),
    ("e4 e6 d4 d5 Nc3 Nf6", "French Defense: Classical"),
    ("e4 e6 d4 d5 Nc3 Bb4", "French Defense: Winawer"),
    ("e4 e6 d4 d5 Nd2", "French Defense: Tarrasch"),
    ("e4 c6", "Caro-Kann Defense"),
    ("e4 c6 d4 d5 e5", "Caro-Kann Defense: Advance"),
    ("e4 c6 d4 d5 Nc3 dxe4 Nxe4", "Caro-Kann Defense: Classical"),
    ("e4 d5", "Scandinavian Defense"),
    ("e4 d6", "Pirc Defense"),
    ("e4 g6", "Modern Defense"),
    ("e4 Nf6", "Alekhine's Defense"),
    ("d4", "Queen's Pawn Game"),
    ("d4 d5", "Closed Game"),
    ("d4 d5 Bf4", "London System"),
    ("d4 d5 c4", "Queen's Gambit"),
    ("d4 d5 c4 e6", "Queen's Gambit Declined"),
    ("d4 d5 c4 dxc4", "Queen's Gambit Accepted"),
    ("d4 d5 c4 c6", "Slav Defense"),
    ("d4 Nf6", "Indian Defense"),
    ("d4 Nf6 c4 g6", "King's Indian Defense"),
    ("d4 Nf6 c4 e6 Nc3 Bb4", "Nimzo-Indian Defense"),
    ("d4 Nf6 c4 e6 Nf3 b6", "Queen's Indian Defense"),
    ("d4 Nf6 c4 c5 d5", "Benoni Defense"),
    ("c4", "English Opening"),
    ("c4 e5", "English Opening: Reversed Sicilian"),
    ("Nf3", "Reti Opening"),
    ("f4", "Bird's Opening"),
    ("b3", "Larsen's Opening"),
    ("g3", "King's Fianchetto Opening"),
]
_NAMES = [(tuple(line.split()), name) for line, name in _NAME_TABLE]


def opening_name(sans):
    """Name of the opening for a list of SAN moves played so far, or None.
    Uses the longest known line that matches the start of the game."""
    clean = [s.rstrip("+#") for s in sans]
    best = None
    for line, name in _NAMES:
        if len(line) <= len(clean) and tuple(clean[:len(line)]) == line:
            if best is None or len(line) > best[0]:
                best = (len(line), name)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Opening book for the computer (so it does not play the same opening every game)
# ---------------------------------------------------------------------------
_book = None


def _build_book():
    book = {}
    for opening in OPENINGS:
        pos = Position()
        for move in opening_moves(opening):
            choices = book.setdefault(pos.key(), [])
            if move not in choices:
                choices.append(move)
            pos = pos.make_move(move)
    return book


def book_move(pos):
    """A random book move for this position, or None if the position is not in the book."""
    global _book
    if _book is None:
        _book = _build_book()
    choices = _book.get(pos.key())
    return random.choice(choices) if choices else None


# ---------------------------------------------------------------------------
# Endgame drills
# ---------------------------------------------------------------------------
Drill = namedtuple("Drill", "id name fen learner_white goal par description tips")

ENDGAMES = [
    Drill(
        "kqk", "King + Queen vs King", "8/8/4k3/8/8/8/8/Q3K3 w - - 0 1", True, "mate", 10,
        "The easiest checkmate. Use the queen to shrink the box around the king, then bring your own king.",
        ["Keep a knight's move away from the enemy king", "Do not stalemate: always leave a square", "Bring your king close before the final check"],
    ),
    Drill(
        "krk", "King + Rook vs King", "8/8/4k3/8/8/8/8/R3K3 w - - 0 1", True, "mate", 20,
        "Cut the king off with the rook, march your king up, and use the opposition to deliver mate.",
        ["Cut the king off along a rank or file", "Kings face each other (opposition) before the rook check", "Never leave the rook where the king can capture it"],
    ),
    Drill(
        "kbbk", "King + Two Bishops vs King", "8/8/4k3/8/8/8/8/2B1KB2 w - - 0 1", True, "mate", 25,
        "Two bishops on neighbouring diagonals form a wall. Drive the king to a corner with king and bishops together.",
        ["Keep the bishops side by side on adjacent diagonals", "Use the king to take away squares", "The mate happens in a corner"],
    ),
    Drill(
        "kpk", "King + Pawn: Win with the Key Squares", "3k4/8/3K4/3P4/8/8/8/8 w - - 0 1", True, "promote", 8,
        "Your king is in front of your pawn on the sixth rank. That wins by force. Escort the pawn to promotion.",
        ["King in front of the pawn: stay in front of it", "Keep the opposition when you can", "Beware of stalemate when you promote"],
    ),
    Drill(
        "lucena", "Rook Endgame: The Lucena Position", "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1", True, "promote", 12,
        "The most famous winning rook endgame. Build a bridge with your rook to shield your king from checks.",
        ["First give a check to push the enemy king further away", "Place the rook on the fourth rank (build the bridge)", "Use the rook to block the checks as your king steps out"],
    ),
]


def get_drill(drill_id):
    for drill in ENDGAMES:
        if drill.id == drill_id:
            return drill
    raise KeyError(drill_id)
