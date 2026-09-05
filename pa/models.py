from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Status = Literal[
    "idle",
    "planning",
    "await_go",
    "running",
    "blocked",
    "done",
    "failed",
]


class Ticket(BaseModel):
    id: str = ""
    objective: str
    files_allowed: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)
    ask_planner_if: list[str] = Field(default_factory=list)
    notes: str = ""


class CommandResult(BaseModel):
    cmd: str
    exit: int | None = None
    tail: str = ""


class Report(BaseModel):
    ticket: str
    status: Literal["ok", "blocked", "ask_planner"]
    changed_files: list[str] = Field(default_factory=list)
    commands: list[CommandResult] = Field(default_factory=list)
    evidence: str = ""
    question: str | None = None


class Plan(BaseModel):
    goal: str
    done_when: list[str]
    phases: list[str]
    risks: list[str] = Field(default_factory=list)
    first_ticket_hint: str = ""


class RunState(BaseModel):
    status: Status = "idle"
    goal: str = ""
    plan: Plan | None = None
    current_ticket_id: str | None = None
    ticket_seq: int = 0
    ask_count: dict[str, int] = Field(default_factory=dict)
    same_error_streak: int = 0
    last_error: str = ""
    human_message: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
