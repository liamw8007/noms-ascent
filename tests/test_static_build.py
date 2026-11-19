"""The committed docs/ folder is what GitHub Pages serves, so it must match a fresh build."""
import filecmp
import io
import zipfile
from pathlib import Path

from scripts.build_static import build

ROOT = Path(__file__).resolve().parent.parent


def files_under(d):
    return sorted(p.relative_to(d) for p in Path(d).rglob("*") if p.is_file())


def test_docs_matches_fresh_build(tmp_path):
    fresh = build(tmp_path / "docs")
    assert files_under(ROOT / "docs") == files_under(fresh), "run: python scripts/build_static.py"
    for rel in files_under(fresh):
        assert filecmp.cmp(ROOT / "docs" / rel, fresh / rel, shallow=False), \
            f"docs/{rel} is stale; run: python scripts/build_static.py"


def test_build_is_static_mode_with_engine_zip(tmp_path):
    out = build(tmp_path / "docs")
    assert (out / ".nojekyll").exists()
    assert 'data-mode="static"' in (out / "index.html").read_text()
    names = zipfile.ZipFile(io.BytesIO((out / "engine" / "game.zip").read_bytes())).namelist()
    assert "game/__init__.py" in names
    assert not any("__pycache__" in n for n in names)
