from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


class CliError(RuntimeError):
    pass


def which_or_die(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise CliError(f"找不到命令 `{name}`，先装 CLI 并保证在 PATH 里")
    return path


def _decode(blob: bytes | str | None) -> str:
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob
    for enc in ("utf-8", "utf-8-sig", "gb18030", "cp936"):
        try:
            return blob.decode(enc)
        except UnicodeDecodeError:
            continue
    return blob.decode("utf-8", errors="replace")


def iter_json_objects(text: str):
    decoder = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i] not in "{[":
            i += 1
        if i >= n:
            break
        try:
            obj, end = decoder.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(obj, dict):
            yield obj
        i = end


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise CliError("CLI 空输出")

    found: list[dict[str, Any]] = []

    def absorb(blob: str) -> None:
        for obj in iter_json_objects(blob):
            found.append(obj)
            for key in ("text", "result", "content"):
                val = obj.get(key)
                if isinstance(val, str) and "{" in val:
                    absorb(val)
                elif isinstance(val, dict):
                    found.append(val)

    absorb(text)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        absorb(fence.group(1))

    for obj in reversed(found):
        if "kind" in obj or "status" in obj:
            return obj
    for obj in reversed(found):
        if "goal" in obj or "objective" in obj:
            return obj
    if found:
        return found[-1]
    raise CliError("CLI 输出里没有可用 JSON:\n" + text[:1200])


def run(cmd: list[str], cwd: Path, timeout: int, prompt_file: Path | None = None) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    raw = _decode(proc.stdout)
    err = _decode(proc.stderr)
    dump_dir = prompt_file.parent if prompt_file else Path(cwd)
    (dump_dir / "_last_cli_stdout.txt").write_text(raw, encoding="utf-8", errors="replace")
    (dump_dir / "_last_cli_stderr.txt").write_text(err, encoding="utf-8", errors="replace")
    (dump_dir / "_last_cli_cmd.txt").write_text("\n".join(cmd), encoding="utf-8", errors="replace")

    if not raw.strip():
        raise CliError(
            f"CLI 空输出 exit={proc.returncode}\n"
            f"STDERR:\n{err[-3000:]}\n"
            f"cmd dump: {dump_dir / '_last_cli_cmd.txt'}"
        )
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(raw) if raw.strip().startswith("{") else {}
    except json.JSONDecodeError:
        payload = {}
    try:
        data = extract_json(raw)
    except CliError:
        raise CliError(
            f"exit={proc.returncode}\nSTDOUT:\n{raw[-2000:]}\nSTDERR:\n{err[-2000:]}"
        ) from None
    data["_raw_meta"] = {
        "session_id": payload.get("session_id") or payload.get("sessionId"),
        "exit": proc.returncode,
        "stderr_tail": err[-500:],
        "prompt_file": str(prompt_file) if prompt_file else None,
    }
    return data