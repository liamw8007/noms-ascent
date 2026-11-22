"""Build the static GitHub Pages site into docs/.

GitHub Pages serves plain files and can't run Flask, so this writes everything
the browser needs: the page (rendered in "static" mode), static/, the engine
zip and the level JSON. Run from the repo root:  python scripts/build_static.py
"""
import shutil
import sys
from pathlib import Path

from jinja2 import Template  # installed with Flask

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # so this works as a script as well as an import
from scripts.bundle_engine import make_zip, refuse_symlinks  # noqa: E402

OUT = ROOT / "docs"


def build(out=OUT):
    out = Path(out)
    refuse_symlinks(ROOT / "templates", ROOT / "static", ROOT / "levels")  # before deleting anything
    if out.exists():
        shutil.rmtree(out)  # start clean so deleted files don't linger in the build
    out.mkdir(parents=True)

    page = Template((ROOT / "templates" / "index.html").read_text(encoding="utf-8"))
    (out / "index.html").write_text(page.render(mode="static"), encoding="utf-8")
    shutil.copytree(ROOT / "static", out / "static")
    (out / "engine").mkdir()
    (out / "engine" / "game.zip").write_bytes(make_zip())
    (out / "levels").mkdir()
    for f in sorted((ROOT / "levels").glob("*.json")):
        shutil.copy2(f, out / "levels" / f.name)

    # GitHub Pages runs Jekyll by default, and Jekyll silently drops files whose
    # names start with "_". Nothing in the build needs that today (the engine is
    # zipped), but an empty .nojekyll turns Jekyll off so it never surprises us.
    (out / ".nojekyll").touch()
    return out


if __name__ == "__main__":
    print(f"Built {build().relative_to(ROOT)}/")
