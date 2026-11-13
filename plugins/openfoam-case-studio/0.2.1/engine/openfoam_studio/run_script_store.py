"""Create-only, verified storage for generated case-local OpenFOAM scripts."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import tempfile
import uuid


MAX_SCRIPT_BYTES = 1024 * 1024


def create_local_allrun(root: str, content: str) -> str:
    payload = _payload(content)
    case_root = Path(root).resolve(strict=True)
    if not case_root.is_dir():
        raise ValueError("case root is not a directory")
    target = case_root / "Allrun"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return str(target)


def create_remote_allrun(root: str, files, content: str) -> str:
    payload = _payload(content)
    case_root = _remote_root(root)
    if not files.is_dir(str(case_root)):
        raise ValueError("remote case root is not a directory")
    target = case_root / "Allrun"
    if files.exists(str(target)):
        raise FileExistsError("Allrun already exists in the case; preserve or rename it before generating another")

    token = uuid.uuid4().hex
    stage = target.with_name(f".Allrun.{token}.stage")
    expected = hashlib.sha256(payload).digest()
    with tempfile.TemporaryDirectory(prefix="hpc-openfoam-allrun-") as directory:
        local_source = Path(directory) / "Allrun"
        local_check = Path(directory) / "verify"
        local_source.write_bytes(payload)
        try:
            files.upload(str(local_source), str(stage))
            files.download(str(stage), str(local_check))
            if hashlib.sha256(local_check.read_bytes()).digest() != expected:
                raise IOError("uploaded Allrun failed SHA-256 verification")
            if files.exists(str(target)):
                raise FileExistsError("Allrun appeared in the case while generating the script")
            files.rename(str(stage), str(target))
        finally:
            try:
                if files.exists(str(stage)):
                    files.remove(str(stage))
            except Exception:
                pass
    return str(target)


def _payload(content: str) -> bytes:
    if not isinstance(content, str):
        raise TypeError("Allrun content must be text")
    payload = content.encode("utf-8")
    if not payload or len(payload) > MAX_SCRIPT_BYTES:
        raise ValueError("Allrun content is empty or exceeds the configured size limit")
    return payload


def _remote_root(value: str) -> PurePosixPath:
    root = PurePosixPath(value)
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("remote case root must be an absolute safe POSIX path")
    return root
