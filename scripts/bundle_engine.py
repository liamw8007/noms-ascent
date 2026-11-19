"""Zip the game/ package so the browser can load it in one fetch.

main.js fetches engine/game.zip and unpacks it into Pyodide's filesystem with
pyodide.unpackArchive(), then runs `import game`. Flask serves these bytes from
memory and build_static.py writes them into docs/, so neither mode needs a
route that serves source files by path.
"""
import io
import zipfile
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parent.parent / "game"
FIXED_DATE = (2026, 1, 1, 0, 0, 0)  # same timestamp every time, so the zip is reproducible


def make_zip():
    """Return the bytes of a zip holding game/*.py (never __pycache__)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for f in sorted(GAME_DIR.glob("*.py")):
            info = zipfile.ZipInfo(f"game/{f.name}", date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, f.read_bytes())
    return buf.getvalue()
