"""The committed docs/ folder is what GitHub Pages serves, so it must match a fresh build."""
import filecmp
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_static", ROOT / "scripts" / "build_static.py")
build_static = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_static)


def files_under(d):
    return sorted(p.relative_to(d) for p in Path(d).rglob("*") if p.is_file())


def test_docs_matches_fresh_build(tmp_path):
    fresh = build_static.build(tmp_path / "docs")
    assert files_under(ROOT / "docs") == files_under(fresh), "run: python scripts/build_static.py"
    for rel in files_under(fresh):
        assert filecmp.cmp(ROOT / "docs" / rel, fresh / rel, shallow=False), \
            f"docs/{rel} is stale; run: python scripts/build_static.py"


def test_build_disables_jekyll(tmp_path):
    # Without .nojekyll, Pages drops game/__init__.py (leading underscore).
    out = build_static.build(tmp_path / "docs")
    assert (out / ".nojekyll").exists()
    assert (out / "game" / "__init__.py").exists()
