PLANNER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["kind"],
    "properties": {
        "kind": {"type": "string", "enum": ["plan", "ticket", "human", "done"]},
        "goal": {"type": "string"},
        "done_when": {"type": "array", "items": {"type": "string"}},
        "phases": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "first_ticket_hint": {"type": "string"},
        "objective": {"type": "string"},
        "files_allowed": {"type": "array", "items": {"type": "string"}},
        "forbidden": {"type": "array", "items": {"type": "string"}},
        "steps": {"type": "array", "items": {"type": "string"}},
        "acceptance": {"type": "array", "items": {"type": "string"}},
        "ask_planner_if": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
        "reason": {"type": "string"},
        "summary": {"type": "string"},
    },
}

ACT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "evidence"],
    "properties": {
        "status": {"type": "string", "enum": ["ok", "blocked", "ask_planner"]},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "commands": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string"},
                    "exit": {"type": "integer"},
                    "tail": {"type": "string"},
                },
            },
        },
        "evidence": {"type": "string"},
        "question": {"type": "string"},
    },
}
