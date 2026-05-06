# claudestuff

Workspace-level Claude Code configuration for `~/Desktop/Sean Workspace/`.
This is the persona, the agents, the operational scripts they call, and
the running journal of how the workspace is used.

## Layout

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Workspace persona and `/status` command definition. Loaded into every Claude Code session opened in this directory tree. |
| `settings.local.json` | Per-machine permission grants and enabled MCP servers. |
| `agents/<name>/` | One folder per subagent: contains `<name>.md` (the agent definition Claude Code discovers) and `settings.local.json` (the permission grants that agent operates with — documentary). |
| `scripts/` | Companion scripts the agents shell out to. Organized by agent. |
| `journal/` | Workspace status snapshots and the scribe journal. |

## Agents

- **`apa-style-writer`** — APA 7th edition writing and citation. Pulls authoritative passages from the APA Publication Manual via the NEON `psychlibrary` schema. Calls `scripts/apa-writer/synthesize_literature.py` for corpus-grounded prose, then formats and cites.
- **`neon-loader`** — Ingests source documents (PDF/EPUB/DOCX/TXT/MHT/HTML) into Neon Postgres schemas via the pipeline at `toolbox/NEON_loader/`. Stages, runs `load.sh`, verifies counts and embeddings.
- **`neon-manager`** — Schema and corpus administration on Neon: stats, health audits, dedup, vector index tuning, embedding backfill. Operates on already-loaded data; does not ingest.

## Conventions

- Each agent gets its own folder: `agents/<name>/` containing `<name>.md` + `settings.local.json`.
- Scripts called by an agent live at `scripts/<agent-name>/`.
- The per-agent `settings.local.json` documents what permissions the agent needs to operate — Claude Code does not load it as authoritative config. Mirror required grants into the workspace-root `settings.local.json`.
- No credentials in tracked files. The root `settings.local.json` is scrubbed before commit.
