from __future__ import annotations

import json
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


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise CliError("CLI 空输出")
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            if "result" in obj and isinstance(obj["result"], str):
                return extract_json(obj["result"])
            if "text" in obj and isinstance(obj["text"], str) and obj["text"].lstrip().startswith("{"):
                return extract_json(obj["text"])
            if "kind" in obj or "status" in obj or "goal" in obj:
                return obj
            if "result" in obj and isinstance(obj["result"], dict):
                return obj["result"]
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise CliError("CLI 输出里没有可用 JSON:\n" + text[:1200])


def run(cmd: list[str], cwd: Path, timeout: int, prompt_file: Path | None = None) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    raw = proc.stdout or ""
    err = proc.stderr or ""
    if proc.returncode != 0 and not raw.strip():
        raise CliError(f"exit={proc.returncode}\n{err[-2000:]}")
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(raw) if raw.strip().startswith("{") else {}
    except json.JSONDecodeError:
        payload = {}
    try:
        data = extract_json(raw)
    except CliError:
        if proc.returncode != 0:
            raise CliError(f"exit={proc.returncode}\nSTDOUT:\n{raw[-1500:]}\nSTDERR:\n{err[-1500:]}")
        raise
    data["_raw_meta"] = {
        "session_id": payload.get("session_id") or payload.get("sessionId"),
        "exit": proc.returncode,
        "stderr_tail": err[-500:],
        "prompt_file": str(prompt_file) if prompt_file else None,
    }
    return data
