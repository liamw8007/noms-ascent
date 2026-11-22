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


def refuse_symlinks(*folders):
    """Raise ValueError if anything in these folders is a symlink (SEC-10).

    Copying or zipping follows a symlink and publishes the file it points to, so a
    stray link such as static/x.txt -> ../.env would put a secret on the website.
    """
    for folder in map(Path, folders):
        for path in [folder, *folder.rglob("*")]:   # rglob doesn't descend into linked folders
            if path.is_symlink():
                raise ValueError(f"refusing to publish a symlink: {path}")


def make_zip():
    """Return the bytes of a zip holding game/*.py (never __pycache__)."""
    refuse_symlinks(GAME_DIR)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for f in sorted(GAME_DIR.glob("*.py")):
            info = zipfile.ZipInfo(f"game/{f.name}", date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, f.read_bytes())
    return buf.getvalue()
