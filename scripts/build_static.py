"""Build the static GitHub Pages site into docs/.

GitHub Pages serves plain files, so the build is just a copy of what the
browser needs: index.html, static/, the engine's .py files and the level JSON.
Run from the repo root:  python scripts/build_static.py
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"


def build(out=OUT):
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)  # start clean so deleted files don't linger in the build
    out.mkdir(parents=True)

    shutil.copy2(ROOT / "index.html", out / "index.html")
    shutil.copytree(ROOT / "static", out / "static")
    # Only the source files: never ship __pycache__ or other local clutter.
    (out / "game").mkdir()
    for f in sorted((ROOT / "game").glob("*.py")):
        shutil.copy2(f, out / "game" / f.name)
    (out / "levels").mkdir()
    for f in sorted((ROOT / "levels").glob("*.json")):
        shutil.copy2(f, out / "levels" / f.name)

    # GitHub Pages runs Jekyll by default, and Jekyll silently drops files whose
    # names start with "_". That would 404 game/__init__.py and break the game.
    # An empty .nojekyll file turns Jekyll off.
    (out / ".nojekyll").touch()
    return out


if __name__ == "__main__":
    print(f"Built {build().relative_to(ROOT)}/")
