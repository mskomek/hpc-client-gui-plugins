#!/usr/bin/env python3
"""Documentation link/routing checks for the official plugin registry.

Verifies that:

1. the README's "Request a plugin" link exists and targets the dedicated
   ``plugin-request`` issue template in ``mskomek/hpc-client-gui-plugins``;
2. the README links back to the main application repository;
3. every relative Markdown link in documentation resolves to a real file;
4. no documentation sends plugin requests to the wrong repository.

Exit status is non-zero on any problem.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGIN_REQUEST_URL = (
    "https://github.com/mskomek/hpc-client-gui-plugins/issues/new"
    "?template=plugin-request.yml"
)
MAIN_APP_URL = "https://github.com/mskomek/hpc-client-gui"

# Relative links are resolved against these roots per source file location.
DOC_GLOBS = ["README.md", "CONTRIBUTING.md", "SECURITY.md", "docs/*.md"]

_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")

_PLUGIN_REQUEST_TEXT_WORDS = (
    "request a plugin",
    "plugin request",
    "new plugin",
    "cluster profile",
    "job template",
    "lint rule",
    "solver template",
)


def _iter_doc_files() -> list[Path]:
    files: list[Path] = []
    for pattern in DOC_GLOBS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return files


def check(root: Path | None = None) -> list[str]:
    global REPO_ROOT
    original_root = REPO_ROOT
    if root is not None:
        REPO_ROOT = root.resolve()
    try:
        return _check()
    finally:
        REPO_ROOT = original_root


def _check() -> list[str]:
    errors: list[str] = []
    readme_path = REPO_ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""

    # 1. Plugin request routing.
    if PLUGIN_REQUEST_URL not in readme:
        errors.append(
            f"README.md must contain the dedicated plugin request URL: "
            f"{PLUGIN_REQUEST_URL}"
        )
    for path in _iter_doc_files():
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT).as_posix()
        for match in _MD_LINK_RE.finditer(text):
            link_text, target = match.group(1), match.group(2)
            if not target.startswith("http"):
                continue
            lowered = target.lower()
            is_issue_link = "issues/new" in lowered or "issues/choose" in lowered
            if not is_issue_link:
                continue
            if "template=plugin-request" in lowered or "template=plugin-content-bug" in lowered:
                if "hpc-client-gui-plugins" not in lowered:
                    errors.append(
                        f"{rel}: plugin request template link points outside "
                        f"the plugin repository: {target}"
                    )
                continue
            text_lower = link_text.lower()
            mentions_plugin_content = any(
                word in text_lower for word in _PLUGIN_REQUEST_TEXT_WORDS
            )
            if (
                mentions_plugin_content
                and "hpc-client-gui-plugins" not in lowered
                and "/plugins/issues/new?template=" not in lowered
            ):
                errors.append(
                    f"{rel}: plugin requests must not be routed to the main "
                    f"application repository: '{link_text}' -> {target}"
                )

    # 2. Link back to the main application.
    if MAIN_APP_URL not in readme:
        errors.append(f"README.md must link back to {MAIN_APP_URL}")

    # 3. Relative links resolve.
    for path in _iter_doc_files():
        base_dir = path.parent
        text = path.read_text(encoding="utf-8")
        for match in _MD_LINK_RE.finditer(text):
            target = match.group(2)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0].strip()
            if not clean:
                continue
            resolved = (base_dir / clean).resolve()
            try:
                resolved.relative_to(REPO_ROOT.resolve())
            except ValueError:
                continue  # outside the repo (build output); skip
            if not resolved.exists():
                errors.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}: broken relative "
                    f"link '{target}'"
                )
    return errors


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # emoji/arrow-safe consoles
    except Exception:
        pass
    errors = check()
    if errors:
        print(f"FAIL: {len(errors)} documentation problem(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("OK: documentation links and routing are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
