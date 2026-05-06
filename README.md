# claudestuff

Workspace-level Claude Code configuration for `~/Desktop/Sean Workspace/`.
This is the persona, the agents, the operational scripts they call, and
the running journal of how the workspace is used.

## Layout

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Workspace persona and `/status` command definition. Loaded into every Claude Code session opened in this directory tree. |
| `settings.local.json` | Per-machine permission grants and enabled MCP servers. |
| `agents/` | Subagent definitions discovered by Claude Code (`agents/<name>.md`). |
| `scripts/` | Companion scripts the agents shell out to. Organized by agent. |
| `journal/` | Workspace status snapshots and the scribe journal. |

## Agents

- **`apa-style-writer`** — APA 7th edition writing and citation. Pulls authoritative passages from the APA Publication Manual via the NEON `psychlibrary` schema. Calls `scripts/apa-writer/synthesize_literature.py` for corpus-grounded prose, then formats and cites.

## Conventions

- Agent definitions live flat at `agents/<name>.md` — kebab-case, one `.md` per agent.
- Scripts called by an agent live at `scripts/<agent-name>/`.
- No credentials in tracked files. `settings.local.json` is scrubbed before commit.
