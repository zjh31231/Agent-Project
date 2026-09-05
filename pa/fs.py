from __future__ import annotations

import fnmatch
import os
import subprocess
from pathlib import Path


def resolve_under(root: Path, rel: str) -> Path:
    target = (root / rel).resolve()
    root_r = root.resolve()
    if root_r not in target.parents and target != root_r:
        raise ValueError(f"path escapes workspace: {rel}")
    return target


def path_allowed(rel: str, patterns: list[str]) -> bool:
    rel = rel.replace("\\", "/").lstrip("./")
    for pat in patterns:
        pat = pat.replace("\\", "/").lstrip("./")
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(rel, pat.rstrip("/*")):
            return True
        if pat.endswith("/*") and (rel.startswith(pat[:-1]) or rel.startswith(pat[:-2] + "/")):
            return True
        if rel == pat.rstrip("/*"):
            return True
    return False


def read_file(root: Path, rel: str, max_chars: int = 80_000) -> str:
    p = resolve_under(root, rel)
    if not p.is_file():
        return f"ERROR: not a file: {rel}"
    text = p.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n\n...[truncated {len(text) - max_chars} chars]"
    return text


def write_file(root: Path, rel: str, content: str) -> str:
    p = resolve_under(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"WROTE {rel} ({len(content)} chars)"


def list_dir(root: Path, rel: str = ".", depth: int = 2) -> str:
    base = resolve_under(root, rel)
    if not base.exists():
        return f"ERROR: missing {rel}"
    lines: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        rel_dir = os.path.relpath(dirpath, root)
        level = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if level > depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv", "__pycache__", ".pa"}]
        prefix = rel_dir if rel_dir != "." else "."
        lines.append(prefix + "/")
        for f in filenames[:80]:
            lines.append(f"{prefix}/{f}" if prefix != "." else f)
        if len(filenames) > 80:
            lines.append(f"... +{len(filenames) - 80} files")
    return "\n".join(lines[:400])


def grep(root: Path, pattern: str, glob: str = "*", max_hits: int = 40) -> str:
    hits: list[str] = []
    for p in root.rglob(glob):
        if not p.is_file():
            continue
        parts = set(p.parts)
        if parts & {".git", "node_modules", ".venv", "__pycache__", ".pa"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pattern in line:
                rel = p.relative_to(root).as_posix()
                hits.append(f"{rel}:{i}:{line[:240]}")
                if len(hits) >= max_hits:
                    return "\n".join(hits)
    return "\n".join(hits) if hits else "(no hits)"


def run_bash(root: Path, cmd: str, blocked: list[str], timeout: int = 120) -> tuple[int, str]:
    low = cmd.lower()
    for bad in blocked:
        if bad.lower() in low:
            return 126, f"BLOCKED command contains `{bad}`"
    proc = subprocess.run(
        cmd,
        cwd=root,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    return proc.returncode, out[-8000:]


def git_changed_files(root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    files: list[str] = []
    for line in proc.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            files.append(path.replace("\\", "/"))
    return files


def git_restore_files(root: Path, files: list[str]) -> None:
    if not files:
        return
    subprocess.run(["git", "checkout", "--", *files], cwd=root, capture_output=True)
    subprocess.run(["git", "clean", "-fd", "--", *files], cwd=root, capture_output=True)
