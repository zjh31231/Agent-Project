from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import cli_runner
from .models import Plan, Ticket
from .schemas import PLANNER_SCHEMA


class Planner:
    def __init__(self, cfg: dict, workspace: Path, run_dir: Path, timeout: int):
        self.bin = cli_runner.which_or_die(cfg["bin"])
        self.model = cfg["model"]
        self.effort = cfg["effort"]
        self.max_turns = int(cfg["max_turns"])
        self.workspace = workspace
        self.run_dir = run_dir
        self.timeout = timeout
        self.system = Path(__file__).resolve().parent.parent.joinpath("prompts/planner_system.md").read_text(encoding="utf-8")
        self.session_id: str | None = None
        sid_file = run_dir / "planner_session"
        if sid_file.exists():
            self.session_id = sid_file.read_text(encoding="utf-8").strip() or None

    def _save_sid(self, sid: str | None) -> None:
        if not sid:
            return
        self.session_id = sid
        (self.run_dir / "planner_session").write_text(sid, encoding="utf-8")

    def ask(self, user_text: str, phase: str) -> dict[str, Any]:
        prompt_path = self.run_dir / "_planner_prompt.md"
        prompt_path.write_text(user_text, encoding="utf-8")

        cmd = [
            self.bin,
            "-p",
            user_text,
            "--model",
            self.model,
            "--effort",
            self.effort,
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(PLANNER_SCHEMA),
            "--append-system-prompt",
            self.system + "\n\n你的最终可见输出必须是符合 schema 的 JSON，kind 只能是 plan|ticket|human|done。",
            "--max-turns",
            str(self.max_turns),
            "--disallowedTools",
            "Write,Edit,NotebookEdit,Agent,WebSearch,WebFetch",
        ]
        if phase == "planning":
            cmd += ["--permission-mode", "plan"]
        else:
            cmd += ["--permission-mode", "dontAsk"]
        if self.session_id:
            cmd += ["--resume", self.session_id]

        data = cli_runner.run(cmd, cwd=self.workspace, timeout=self.timeout, prompt_file=prompt_path)
        self._save_sid(data.get("_raw_meta", {}).get("session_id"))
        return data

    def interpret(self, data: dict[str, Any], allow_ticket: bool) -> dict[str, Any]:
        kind = data.get("kind")
        if kind == "plan":
            plan = Plan(
                goal=data["goal"],
                done_when=data.get("done_when") or [],
                phases=data.get("phases") or [],
                risks=data.get("risks") or [],
                first_ticket_hint=data.get("first_ticket_hint") or "",
            )
            return {"kind": "plan", "plan": plan}
        if kind == "ticket":
            if not allow_ticket:
                return {"kind": "human", "reason": "planner issued ticket before GO"}
            ticket = Ticket(
                objective=data["objective"],
                files_allowed=data.get("files_allowed") or [],
                forbidden=data.get("forbidden") or [],
                steps=data.get("steps") or [],
                acceptance=data.get("acceptance") or [],
                ask_planner_if=data.get("ask_planner_if") or [],
                notes=data.get("notes") or "",
            )
            return {"kind": "ticket", "ticket": ticket}
        if kind == "done":
            return {"kind": "done", "summary": data.get("summary") or ""}
        if kind == "human":
            return {"kind": "human", "reason": data.get("reason") or "planner requested human"}
        return {"kind": "human", "reason": f"planner JSON 无法识别: {data}"}
