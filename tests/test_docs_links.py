"""Documentation link and issue-routing checks (see scripts/check_docs_links.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from check_docs_links import PLUGIN_REQUEST_URL, check  # noqa: E402


def test_real_docs_pass():
    errors = check()
    assert errors == []


def _build_repo(tmp_path, readme: str, extra: dict[str, str] | None = None):
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")
    for name, content in (extra or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_missing_request_url_fails(tmp_path):
    _build_repo(tmp_path, "See [app](https://github.com/mskomek/hpc-client-gui).")
    errors = check(tmp_path)
    assert any(PLUGIN_REQUEST_URL in e for e in errors)


def test_wrong_repository_routing_fails(tmp_path):
    readme = (
        "# plugins\n\n"
        f"Request a plugin: {PLUGIN_REQUEST_URL}\n"
        "Or open issues at https://github.com/mskomek/hpc-client-gui/issues/new/choose\n"
    )
    # README mentions the app chooser as a plain link without the word
    # "plugin" attached to that specific link text; base case must pass.
    _build_repo(tmp_path, readme)
    errors = check(tmp_path)
    assert not any("wrong repository" in e for e in errors)

    bad = (
        "# plugins\n\n"
        f"Request a plugin: {PLUGIN_REQUEST_URL}\n"
        "[Request a plugin](https://github.com/mskomek/hpc-client-gui/issues/new?template=x.md)\n"
    )
    _build_repo(tmp_path, bad)
    errors = check(tmp_path)
    assert any("must not be routed to the main" in e for e in errors)


def test_broken_relative_link_fails(tmp_path):
    readme = (
        "# Registry\n\n"
        f"Request a plugin: {PLUGIN_REQUEST_URL}\n"
        "Back to [HPC Client GUI](https://github.com/mskomek/hpc-client-gui).\n"
        "See [missing](docs/nope.md).\n"
    )
    _build_repo(tmp_path, readme)
    errors = check(tmp_path)
    assert any("broken relative link 'docs/nope.md'" in e for e in errors)
