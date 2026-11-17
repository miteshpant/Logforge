"""
The docs site (MkDocs, published to GitHub Pages) builds from docs/.

`mkdocs build --strict` fails on links that don't resolve inside the site, so
these checks keep that true without needing MkDocs installed: every nav entry
exists, and every relative link in docs/ points at a file inside docs/.
Links to the rest of the repository must be absolute GitHub URLs, which also
work when the Markdown is read on GitHub.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


class _Loader(yaml.SafeLoader):
    """mkdocs.yml may use !!python/name tags (e.g. for emoji extensions)."""


_Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda loader, suffix, node: None)


def _config():
    return yaml.load((ROOT / "mkdocs.yml").read_text(), Loader=_Loader)


def _nav_files(nav):
    for entry in nav:
        if isinstance(entry, str):
            yield entry
        elif isinstance(entry, dict):
            for value in entry.values():
                if isinstance(value, list):
                    yield from _nav_files(value)
                elif isinstance(value, str) and not value.startswith("http"):
                    yield value


def test_mkdocs_config_points_at_docs():
    config = _config()
    assert config["site_name"] == "Logforge"
    assert config.get("docs_dir", "docs") == "docs"


def test_every_nav_entry_exists():
    missing = [f for f in _nav_files(_config()["nav"]) if not (DOCS / f).exists()]
    assert missing == []


def test_relative_links_in_docs_resolve_inside_docs():
    broken = []
    for md in DOCS.rglob("*.md"):
        for target in LINK.findall(md.read_text(encoding="utf-8")):
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            path = target.split("#")[0]
            if not path:
                continue
            resolved = (md.parent / path).resolve()
            if not resolved.exists() or DOCS.resolve() not in resolved.parents and resolved != DOCS.resolve():
                broken.append(f"{md.relative_to(ROOT)} -> {target}")
    assert broken == []


def test_pages_workflow_builds_the_site_and_keeps_the_api_reference():
    workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "mkdocs build --strict" in workflow
    assert "path: site" in workflow
    # Redoc (docs/api/index.html) is served at /api/ inside the built site.
    assert (DOCS / "api" / "index.html").exists()
