from __future__ import annotations

import json
from pathlib import Path

from . import cli_runner
from .models import Report, Ticket
from .schemas import ACT_SCHEMA


class Act:
    def __init__(self, cfg: dict, workspace: Path, run_dir: Path, timeout: int):
        self.bin = cli_runner.which_or_die(cfg["bin"])
        self.model = cfg["model"]
        self.effort = cfg["effort"]
        self.max_turns = int(cfg["max_turns"])
        self.workspace = workspace
        self.run_dir = run_dir
        self.timeout = timeout
        self.system = Path(__file__).resolve().parent.parent.joinpath("prompts/act_system.md").read_text(encoding="utf-8")

    def run_ticket(self, ticket: Ticket) -> Report:
        prompt = (
            self.system
            + "\n\nCURRENT TICKET (law):\n"
            + ticket.model_dump_json(indent=2)
            + "\n\n做完后只输出符合 schema 的 JSON 回执。不要散文。"
        )
        prompt_path = self.run_dir / f"_{ticket.id}_act_prompt.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        cmd = [
            self.bin,
            "-p",
            prompt,
            "-m",
            self.model,
            "--effort",
            self.effort,
            "--cwd",
            str(self.workspace),
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(ACT_SCHEMA),
            "--max-turns",
            str(self.max_turns),
            "--always-approve",
            "--no-plan",
            "--no-subagents",
            "--disable-web-search",
            "--rules",
            "零创造性。只改 files_allowed。不确定就 status=ask_planner 然后停。最终输出必须是 JSON 回执。",
        ]
        data = cli_runner.run(cmd, cwd=self.workspace, timeout=self.timeout, prompt_file=prompt_path)
        payload = {k: v for k, v in data.items() if not k.startswith("_")}
        payload["ticket"] = ticket.id
        if "status" not in payload:
            return Report(
                ticket=ticket.id,
                status="blocked",
                evidence="act JSON missing status",
                question=json.dumps(payload, ensure_ascii=False)[:800],
            )
        return Report.model_validate(payload)
