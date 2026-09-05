# Opus 5 High (claude CLI) × Grok 4.6 Medium (grok CLI)

不走 API。Orchestrator 只干一件事：按顺序拉两个已经登录过的 CLI。

依赖：
- `claude` 在 PATH（Claude Code）
- `grok` 在 PATH（Grok Build）
- 目标目录是 git 仓库
- 两个 CLI 都已经在本机登录过（claude / grok login）

```bash
pip install -r requirements.txt
python -m pa --workspace /path/to/repo plan "把 JWT 过期校验补上，现有测试必须绿"
# 读仓库 .pa/PLAN.md
python -m pa --workspace /path/to/repo go
python -m pa --workspace /path/to/repo resume --reply "过期用 exp，允许 30s 误差"
```

Planner 实际命令骨架：
```
claude -p ... --model claude-opus-5 --effort high --permission-mode plan \
  --disallowedTools Write,Edit,NotebookEdit,Agent,WebSearch,WebFetch \
  --output-format json --json-schema ...
```

Act 实际命令骨架：
```
grok -p ... -m grok-4.6 --effort medium --always-approve \
  --no-plan --no-subagents --disable-web-search \
  --max-turns 12 --output-format json
```
