"""checkme - a chess practice app.

Run it with:  python main.py
"""

import tkinter as tk

from app import CheckMeApp


def main():
    root = tk.Tk()
    CheckMeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
