# ♟️ CheckMe — Python Chess Engine & GUI

A complete, modular chess application built in Python featuring a custom game engine, AI search algorithms, opening book support, move notation parsing, and an interactive user interface with smooth piece animations.

## ✨ Features

* **Core Chess Engine (`engine.py`, `game.py`):** Full implementation of standard chess rules, move validation, check/checkmate detection, and game state management.

* **AI Opponent (`search.py`, `openings.py`):** Intelligent move calculation powered by search algorithms (e.g., Minimax / Alpha-Beta pruning) paired with an opening book for strong early-game play.

* **Algebraic Notation (`notation.py`):** Support for parsing and generating standard chess notation (SAN / FEN / UCI) for logging games and loading board states.

* **Interactive UI & Animations (`ui.py`, `animation.py`, `app.py`):** Clean graphical interface with smooth piece movement transitions and visual board feedback.

* **Comprehensive Test Suite (`test_*.py`):** Unit tests covering the engine, search logic, notation parser, openings, and animations to ensure reliability.

## 📁 Project Structure

```text
├── LICENSE               # Project license
├── checkme.py            # Primary entry point to launch the application
├── app.py                # Application controller and main loop
├── engine.py             # Core chess rules, board representation, and move generation
├── game.py               # Game state, turn management, and win/draw conditions
├── search.py             # AI evaluation and search tree algorithms
├── openings.py           # Opening book database and lookup logic
├── notation.py           # Chess notation parsing and formatting (SAN/FEN)
├── ui.py                 # Graphical user interface rendering and event handling
├── animation.py          # Smooth visual transitions for piece movements
└── test_*.py             # Unit tests for engine, game, search, openings, notation, and animations
```

## 🚀 Getting Started

### Prerequisites

* Python 3.8 or higher
* Required dependencies (e.g., `pygame` or other GUI libraries—)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/itmrbot/checkme.git
   cd checkme
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```


### Running the Application

Launch the game by running `checkme.py`:

```bash
python checkme.py
```

## 🧪 Running Tests

This project includes a full suite of unit tests for its core modules. You can run all tests at once using `pytest` or Python's built-in `unittest` module:

```bash
# Using unittest
python -m unittest discover

# Or using pytest
pytest
```

## 🛠️ Roadmap / Future Improvements

* 🤖 Add configurable AI difficulty levels / search depth
* 📂 Support PGN game export and import
* 🎵 Add sound effects for moves, captures, and checks
* 👥 Implement multiplayer over network

## 📄 License

This project is licensed under the terms of the MIT LICENSE file included in this repository.
