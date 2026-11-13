"""Bounded read-only SFTP lint adapter; remote commands are never executed."""
from __future__ import annotations

from pathlib import Path, PurePosixPath
import stat
import tempfile

from hpc_gui.openfoam_core import (
    MAX_REMOTE_CASE_BYTES,
    MAX_REMOTE_CASE_DEPTH,
    MAX_REMOTE_CASE_FILES,
    MAX_REMOTE_DICTIONARY_BYTES,
    REMOTE_CASE_SKIP_DIRS,
    is_dictionary_name,
    scan_remote_dictionaries,
    scan_remote_mesh_boundaries,
)

from .api import lint_files

MAX_FILE_BYTES = MAX_REMOTE_DICTIONARY_BYTES
MAX_CASE_BYTES = MAX_REMOTE_CASE_BYTES
MAX_FILES = MAX_REMOTE_CASE_FILES
MAX_DEPTH = MAX_REMOTE_CASE_DEPTH
SKIP_DIRS = REMOTE_CASE_SKIP_DIRS


def _read_bytes(files, path: PurePosixPath) -> bytes:
    size, _mtime = files.stat(str(path))
    if int(size) > MAX_FILE_BYTES:
        raise ValueError(f"remote dictionary exceeds size limit: {path.name}")
    with tempfile.TemporaryDirectory(prefix="hpc-openfoam-lint-") as directory:
        target = Path(directory) / "dictionary"
        files.download(str(path), str(target))
        data = target.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"downloaded dictionary exceeds size limit: {path.name}")
    return data


def _selected_root(path: PurePosixPath, files) -> tuple[PurePosixPath, PurePosixPath | None]:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("remote OpenFOAM path must be a safe absolute POSIX path")
    try:
        selected = files.stat_entry(str(path))
    except NotImplementedError as exc:
        raise ValueError("remote backend cannot verify symbolic links") from exc
    except OSError:
        selected = None
    if selected is not None and stat.S_ISLNK(int(getattr(selected, "mode", 0) or 0)):
        raise ValueError("symbolic links are not followed by the remote linter")
    try:
        if files.is_dir(str(path)):
            return path, None
    except OSError:
        pass
    if not is_dictionary_name(path.name):
        raise ValueError("selected remote path is not a case folder or dictionary")
    for index, part in enumerate(path.parts):
        if part in {"system", "constant", "0", "0.orig"}:
            root = PurePosixPath(*path.parts[:index])
            if root.is_absolute():
                return root, path
    return path.parent, path


def lint_remote_path(path: str, files):
    """Lint a remote case or one dictionary through the active SFTP adapter."""
    selected = PurePosixPath(path)
    root, selected_file = _selected_root(selected, files)
    contents = scan_remote_dictionaries(
        str(root),
        files,
        maximum_file_bytes=MAX_FILE_BYTES,
        maximum_case_bytes=MAX_CASE_BYTES,
        maximum_files=MAX_FILES,
        maximum_depth=MAX_DEPTH,
        skip_dirs=SKIP_DIRS,
    )
    if selected_file is None or "0" in selected_file.parts or "0.orig" in selected_file.parts:
        contents.update(scan_remote_mesh_boundaries(
            str(root),
            files,
            maximum_case_bytes=max(0, MAX_CASE_BYTES - sum(len(data) for data in contents.values())),
            maximum_files=max(0, MAX_FILES - len(contents)),
        ))
    if selected_file is not None:
        relative = selected_file.relative_to(root).as_posix() if root in selected_file.parents else ""
        if relative and relative not in contents:
            contents[relative] = _read_bytes(files, selected_file)
    if not contents and selected_file is not None:
        return lint_files({selected_file.name: _read_bytes(files, selected_file)}, case_context=False)
    return lint_files(contents, case_context=selected_file is None or bool(contents))
