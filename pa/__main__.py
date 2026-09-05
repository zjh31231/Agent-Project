from __future__ import annotations

import argparse
from pathlib import Path

from .orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Opus5-high planner / Grok4.6-medium act")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--workspace", default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("requirement")
    sub.add_parser("go")
    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--reply", default="")
    sub.add_parser("status")
    args = parser.parse_args()

    orch = Orchestrator(Path(args.config), Path(args.workspace) if args.workspace else None)
    if args.cmd == "plan":
        orch.plan(args.requirement)
    elif args.cmd == "go":
        orch.go()
    elif args.cmd == "resume":
        orch.resume(args.reply or None)
    elif args.cmd == "status":
        print(orch.state.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
