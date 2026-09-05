from __future__ import annotations

import json
from pathlib import Path

import yaml

from . import fs
from .act import Act
from .models import Report, RunState, Ticket
from .planner import Planner


class Orchestrator:
    def __init__(self, config_path: Path, workspace: Path | None = None):
        self.cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        self.workspace = Path(workspace or self.cfg.get("workspace") or ".").resolve()
        self.run_dir = self.workspace / self.cfg.get("run_dir", ".pa")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "tickets").mkdir(exist_ok=True)
        (self.run_dir / "reports").mkdir(exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.state = self._load_state()
        timeout = int(self.cfg["limits"]["timeout_sec"])
        self.planner = Planner(self.cfg["planner"], self.workspace, self.run_dir, timeout)
        self.act = Act(self.cfg["act"], self.workspace, self.run_dir, timeout)

    def _load_state(self) -> RunState:
        if self.state_path.exists():
            return RunState.model_validate_json(self.state_path.read_text(encoding="utf-8"))
        return RunState()

    def _save(self) -> None:
        self.state_path.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")

    def _log(self, event: str, payload: dict) -> None:
        line = json.dumps({"event": event, **payload}, ensure_ascii=False)
        with (self.run_dir / "log.jsonl").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(f"[{event}] {payload}")

    def plan(self, requirement: str) -> None:
        self.state = RunState(status="planning")
        self._save()
        raw = self.planner.ask(
            "用户需求如下。只做只读探查并输出 kind=plan 的 JSON。禁止 ticket。\n\n" + requirement,
            phase="planning",
        )
        decision = self.planner.interpret(raw, allow_ticket=False)
        if decision.get("kind") != "plan":
            self.state.status = "blocked"
            self.state.human_message = str(decision)
            self._save()
            raise SystemExit(f"计划没成型：{decision}")
        plan = decision["plan"]
        self.state.plan = plan
        self.state.goal = plan.goal
        self.state.status = "await_go"
        (self.run_dir / "GOAL.md").write_text(
            "# GOAL\n\n" + plan.goal + "\n\n## Done when\n" + "\n".join(f"- {x}" for x in plan.done_when) + "\n",
            encoding="utf-8",
        )
        (self.run_dir / "PLAN.md").write_text(
            "# PLAN\n\n"
            + "\n".join(f"{i+1}. {p}" for i, p in enumerate(plan.phases))
            + "\n\n## Risks\n"
            + "\n".join(f"- {r}" for r in plan.risks)
            + "\n",
            encoding="utf-8",
        )
        self._save()
        self._log("await_go", {"goal": plan.goal})
        print("\n计划已冻结：.pa/PLAN.md  .pa/GOAL.md")
        print("确认后: python -m pa go")

    def go(self) -> None:
        if self.state.status != "await_go" or not self.state.plan:
            raise SystemExit(f"现在不能开工，状态={self.state.status}")
        self.state.status = "running"
        self._save()
        self._loop(
            "人已下达 GO。开始 goal 循环。一次只输出一张 kind=ticket 的 JSON。"
            "\nGOAL:\n" + (self.run_dir / "GOAL.md").read_text(encoding="utf-8")
            + "\nPLAN:\n" + (self.run_dir / "PLAN.md").read_text(encoding="utf-8")
        )

    def resume(self, human_reply: str | None = None) -> None:
        msg = "继续 goal 循环。"
        if human_reply:
            msg = "人的回复（仅此一次）：\n" + human_reply + "\n" + msg
            self.state.human_message = None
        self.state.status = "running"
        self._save()
        self._loop(msg)

    def _loop(self, first_user: str) -> None:
        pending = first_user
        limits = self.cfg["limits"]
        while self.state.status == "running":
            if self.state.ticket_seq >= int(limits["max_tickets"]):
                self.state.status = "blocked"
                self.state.human_message = "ticket budget exhausted"
                self._save()
                return
            raw = self.planner.ask(pending, phase="running")
            decision = self.planner.interpret(raw, allow_ticket=True)
            kind = decision.get("kind")
            if kind == "human":
                self.state.status = "blocked"
                self.state.human_message = decision.get("reason")
                self._save()
                print(f"\n需要你出面：{self.state.human_message}")
                return
            if kind == "done":
                self.state.status = "done"
                (self.run_dir / "SUMMARY.md").write_text(decision.get("summary", ""), encoding="utf-8")
                self._save()
                print("\nGOAL 完成。看 .pa/SUMMARY.md")
                return
            if kind != "ticket":
                self.state.status = "blocked"
                self.state.human_message = str(decision)
                self._save()
                print(f"\nPlanner 跑偏：{decision}")
                return

            ticket: Ticket = decision["ticket"]
            self.state.ticket_seq += 1
            ticket.id = f"T{self.state.ticket_seq:03d}"
            self.state.current_ticket_id = ticket.id
            (self.run_dir / "tickets" / f"{ticket.id}.json").write_text(
                ticket.model_dump_json(indent=2), encoding="utf-8"
            )
            self._save()
            self._log("ticket", {"id": ticket.id, "objective": ticket.objective})

            before = set(fs.git_changed_files(self.workspace))
            report = self.act.run_ticket(ticket)
            after = set(fs.git_changed_files(self.workspace))
            changed = sorted(after - before)
            illegal = [p for p in changed if ticket.files_allowed and not fs.path_allowed(p, ticket.files_allowed)]
            if illegal:
                fs.git_restore_files(self.workspace, illegal)
                report.status = "ask_planner"
                report.question = (report.question or "") + f" scope_violation restored: {illegal}"
                self._log("scope_violation", {"files": illegal})
            report.changed_files = [p for p in changed if p not in illegal]
            (self.run_dir / "reports" / f"{ticket.id}.report.json").write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
            self._log("report", report.model_dump())

            if report.status != "ok":
                key = (report.question or report.evidence)[:200]
                if key and key == self.state.last_error:
                    self.state.same_error_streak += 1
                else:
                    self.state.same_error_streak = 1
                    self.state.last_error = key
                if self.state.same_error_streak >= int(limits["human_on_same_error"]):
                    self.state.status = "blocked"
                    self.state.human_message = f"同一错误重复 {self.state.same_error_streak} 次：{key}"
                    self._save()
                    print(f"\n需要你出面：{self.state.human_message}")
                    return

            pending = (
                "ACT REPORT JSON:\n"
                + report.model_dump_json(indent=2)
                + "\n\n根据回执继续输出 kind=ticket 或 kind=done 或 kind=human。"
            )
            self._save()
