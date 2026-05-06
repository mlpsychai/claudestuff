# WORKSTATION STATUS

> Last updated: 2026-04-05
> Operator: Sean — Northern Arizona University
> Runtime: Python 3.12.3 | Node 18.19.1 | VS Code 1.110.1

---

## System

| Resource     | Value         | Alert |
|-------------|---------------|-------|
| Disk (/)    | 36 GB free    | **CRITICAL — 96% full** |
| External    | Seagate 5.5TB | Available (exFAT, `/media/dft/Expansion`) |

---

## Core RAG Ecosystem

| Project | Purpose | Status | Git | Action |
|---------|---------|--------|-----|--------|
| **RAGARMY_local** | Multi-schema RAG + MCP server | Active | *not tracked* | Center of gravity — needs git init |
| **researchrag-v2** | Academic search (HF Spaces) | Deployed | `main` — 4 dirty | Commit pending changes |
| **researchrag v1** | Original paper search | Archived | `main` — clean | Superseded by v2 |
| **ccworkspace** | Multi-course educational RAG | Legacy | *no commits* | 71K LOC unversioned — exposure |
| **soupdashboard** | Paper discovery | Stalled | `main` — dirty | Archive candidate |

## Data Pipeline

| Project | Purpose | Status | Git | Action |
|---------|---------|--------|-----|--------|
| **appicRAG** | APPIC internship scraper | In progress | *not tracked* | **Shortest path to next win** — wire into RAGARMY |

## Research

| Project | Purpose | Status | Git | Action |
|---------|---------|--------|-----|--------|
| **ableisttaxonomy** | Ableist language in dating subs | Analysis complete | *not tracked* | Deployment pending (Gradio → Neon → HF) |
| **HiTop** | Reddit disorder dataset scaling | **BLOCKED** | *not tracked* | Needs 4TB+ storage — 36GB available |
| **skeleton_assess** | Psychometric scoring (PAI/MMPI-3) | Production | `master` — **47 dirty** | Commit immediately — significant drift |

## Web / Output

| Project | Purpose | Status | Git |
|---------|---------|--------|-----|
| **SIMPLEHTML** | APA template system | Maintained | *not tracked* |
| **grinch-space** | Interpretive psych report | Complete | `main` — clean |
| **clinicaldashboard** | HiTOP string theory viz | Archived | *not tracked* |

## Archive

| Project | Notes |
|---------|-------|
| **schoolworktemp** | Coursework notes, CSV taxonomies |
| **archive/** | 24 subdirs: BFI-2-S, EPPP, PDM-2, TRANSCRIBER, etc. |

---

## The Throughline

1. **Disk is the hard constraint.** 36 GB with a 4TB project queued. HiTop cannot move. Nothing large can be added. This shapes every decision until resolved.

2. **Version control gaps are risk.** RAGARMY_local (your center of gravity) and appicRAG (your active frontier) have zero git history. skeleton_assess has 47 uncommitted changes. One bad edit away from unrecoverable loss.

3. **appicRAG → RAGARMY wiring is the shortest win.** Data scraped, loader built. Embed 500 chunks, patch MCP schema_stats, wire into RAGARMY UI. This is the move.

---

*To refresh: ask Claude to run `/status`*
