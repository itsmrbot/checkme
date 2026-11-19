# checkme ♟

A free chess **practice** app for one player, in pure Python. Think "chess.com free version", but built
for learning: **openings, middlegames and endgames**, against a computer with **9 difficulty levels**.

No pip packages needed: just Python 3 and tkinter.

## Features

- **9 levels**: Rookie, Casual, Novice, Improver, Club player, Advanced, Strong, Expert, Master
- **Practice areas**
  - **Openings**: 13 lines to learn (6 as White, 7 as Black) with comments on every move, ideas and plans. You earn up to 3 stars.
  - **Middlegames**: start from a position after the opening and play it out
  - **Endgames**: 5 drills (K+Q vs K, K+R vs K, two bishops, K+P vs K, Lucena)
  - **Play**: a normal game from the start position
- **Assist / no Assist**: with Assist you get hints, an evaluation bar, move-quality badges (best, good, inaccuracy, mistake, blunder) and takeback. Without it, you are on your own.
- **Time formats**: No clock, **1 min**, **3 min**, **10 min**
- **Settings**: **premove**, board theme (green, brown, blue), animation speed, coordinates, move dots. Saved to `~/.checkme_settings.json`
- Smooth animations: sliding pieces, capture ripples, check glow, hint arrows
- Review the game with the arrow keys, flip the board, resign, rematch

## Run it

```bash
git clone https://github.com/itsmrbot/checkme.git
cd checkme
python main.py
```

tkinter comes with Python on Windows and macOS. On Linux: `sudo apt install python3-tk`.

## Controls

| Action | How |
| --- | --- |
| Move | click a piece, then a square |
| Premove | while the computer thinks, click a piece and a square (premoves promote to a queen) |
| Cancel selection / premove | right click or `Esc` |
| Review moves | `←` `→`, `Home`, `End`, or click a move |

## Tests

```bash
python -m unittest
```

The engine is checked with standard perft counts. `test_app.py` runs the whole window with
`fake_tkinter.py`, so it needs no screen.

## Files

| File | What it does |
| --- | --- |
| `main.py` | starts the app |
| `app.py` | the window: screens, input, animation |
| `ui.py`, `animation.py` | small drawing toolkit and animation helpers |
| `engine.py` | chess rules |
| `notation.py` | SAN notation both ways |
| `search.py` | the computer player and the 9 levels |
| `openings.py` | opening lines, comments, endgame drills |
| `game.py` | game state, clocks, trainer, move grading |

## Limits

No sound, no drag and drop (click to move), games are not saved, each opening has one main line,
and there are 5 endgame drills.

## License

MIT, see `LICENSE`.
