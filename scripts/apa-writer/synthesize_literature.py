#!/usr/bin/env python3
"""
Synthesize literature on a specified topic using sources from the NEON corpus.

The output is plain markdown prose with inline (Author, Year) citations and a
trailing "Sources used" block. Formatting (headings, APA reference list,
in-text citation conventions) is the responsibility of the apa-style-writer
agent that consumes this output — not this script.

Usage examples
--------------
  python3 synthesize_literature.py \
      --topic "Mirror neuron correlates of Rorschach M responses" \
      --schema rorschach \
      --query "mirror neuron mu suppression M response" \
      --top-k 15

  python3 synthesize_literature.py \
      --topic "R-PAS validity evidence" \
      --schema rorschach \
      --paper-ids 23,45,67 \
      --length long --style critical

  python3 synthesize_literature.py \
      --topic "Citation rules for AI-generated content" \
      --schema psychlibrary \
      --chunk-ids 3720,3718

The script writes logs to stderr and the synthesis to stdout (or --output PATH).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

import anthropic


# ── env loading ────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent

ENV_CANDIDATES = [
    SCRIPT_DIR / ".env",
    SCRIPT_DIR.parent / ".env",
    SCRIPT_DIR.parent.parent / ".env",
    Path.home() / "Desktop" / "Sean Workspace" / "ragarmy_local" / ".env",
]
for candidate in ENV_CANDIDATES:
    if candidate.is_file():
        load_dotenv(candidate)
        break

DATABASE_URL = os.getenv("DATABASE_URL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")


# ── logging (stderr only — stdout reserved for synthesis) ──────────────────
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("synthesize_literature")


# ── synthesis prompt ───────────────────────────────────────────────────────
LENGTH_GUIDANCE = {
    "short":  "150–250 words, one to two paragraphs",
    "medium": "350–500 words, three to four paragraphs",
    "long":   "700–900 words, five to seven paragraphs",
}

STYLE_GUIDANCE = {
    "empirical": (
        "Empirical-summary register: lead with the convergent finding, then enumerate "
        "specific results, methods, samples, and effect sizes. Note tensions or "
        "replication failures where they appear in the excerpts."
    ),
    "narrative": (
        "Narrative-review register: weave the sources into a coherent story arc, "
        "tracing how the field's understanding has developed. Maintain chronological "
        "or thematic flow without sacrificing source-grounding."
    ),
    "critical": (
        "Critical-review register: foreground methodological strengths and weaknesses, "
        "name the assumptions each source rests on, and surface gaps the literature "
        "has not yet addressed."
    ),
}

SYSTEM_PROMPT = """You are a research-writing assistant producing source-grounded prose for inclusion in an APA-style manuscript.

Hard rules:
  1. Cite every empirical claim inline. Use (Author, Year) parenthetical or "Author (Year)" narrative form. Derive Author and Year from the [paper_id N | First-author Year] markers attached to each excerpt.
  2. Do NOT introduce facts, samples, statistics, dates, or quotations that are not present in the excerpts. If a claim is partially supported, qualify it.
  3. If excerpts conflict, name the disagreement and attribute it to the specific sources.
  4. Output prose only. No headings, no bullets, no list formatting, no markdown emphasis. The downstream agent applies APA structural formatting.
  5. No preamble ("This synthesis examines..."), no closing ("In conclusion..."). Begin with substance and end with substance.
  6. Use confident, formal academic prose. Active voice preferred. First person allowed where natural ("I", "we") but unnecessary in synthesis work."""


# ── source resolution ──────────────────────────────────────────────────────
def parse_id_list(s: str | None) -> list[int]:
    if not s:
        return []
    return [int(x.strip()) for x in s.split(",") if x.strip()]


def fetch_chunks_by_paper_ids(cur, schema, paper_ids):
    cur.execute(
        f"""
        SELECT c.chunk_id, c.content, c.paper_id,
               p.title, p.year, p.doi, p.apa_citation
        FROM {schema}.chunks c
        JOIN {schema}.papers p ON p.paper_id = c.paper_id
        WHERE c.paper_id = ANY(%s)
        ORDER BY c.paper_id, c.chunk_index
        """,
        (paper_ids,),
    )
    return cur.fetchall()


def fetch_chunks_by_chunk_ids(cur, schema, chunk_ids):
    cur.execute(
        f"""
        SELECT c.chunk_id, c.content, c.paper_id,
               p.title, p.year, p.doi, p.apa_citation
        FROM {schema}.chunks c
        JOIN {schema}.papers p ON p.paper_id = c.paper_id
        WHERE c.chunk_id = ANY(%s)
        ORDER BY c.chunk_id
        """,
        (chunk_ids,),
    )
    return cur.fetchall()


def fetch_chunks_by_query(cur, schema, query_text, top_k, anthropic_client):
    """Embed the query with Voyage (via the same approach as the MCP server)
    is not available here — instead we use Anthropic for embedding-free retrieval
    by routing through the MCP-equivalent SQL path: pgvector cosine on a
    pre-computed embedding column. Since we cannot embed the query in this
    script without adding a dependency, we delegate to Postgres full-text
    fallback when no embedding service is available.

    Practical strategy: use websearch_to_tsquery against chunks.content. The
    agent typically supplies precise terminology so this works adequately for
    targeted retrieval. For richer semantic search, the caller should pass
    --paper-ids or --chunk-ids derived from the MCP semantic_search tool."""
    cur.execute(
        f"""
        SELECT c.chunk_id, c.content, c.paper_id,
               p.title, p.year, p.doi, p.apa_citation,
               ts_rank_cd(to_tsvector('english', c.content),
                          websearch_to_tsquery('english', %s)) AS rank
        FROM {schema}.chunks c
        JOIN {schema}.papers p ON p.paper_id = c.paper_id
        WHERE to_tsvector('english', c.content)
              @@ websearch_to_tsquery('english', %s)
        ORDER BY rank DESC
        LIMIT %s
        """,
        (query_text, query_text, top_k),
    )
    return cur.fetchall()


def first_author_token(apa_citation: str | None, title: str) -> str:
    """Best-effort extraction of a first-author surname from apa_citation."""
    if apa_citation:
        head = apa_citation.split("(")[0].strip()
        if "," in head:
            return head.split(",", 1)[0].strip()
        return head.split()[0] if head else "Unknown"
    return "Unknown"


def build_excerpt_block(rows):
    """Render the source set as a numbered excerpt block with citation markers."""
    lines = []
    for i, r in enumerate(rows, 1):
        author = first_author_token(r["apa_citation"], r["title"])
        year = r["year"] if r["year"] else "n.d."
        marker = f"[paper_id {r['paper_id']} | {author} {year}]"
        lines.append(f"--- Excerpt {i} {marker} ---")
        lines.append(r["content"].strip())
        lines.append("")
    return "\n".join(lines)


def unique_papers(rows):
    seen = {}
    for r in rows:
        if r["paper_id"] not in seen:
            seen[r["paper_id"]] = r
    return list(seen.values())


def render_sources_block(papers):
    lines = ["", "## Sources used", ""]
    for p in sorted(papers, key=lambda x: (x.get("apa_citation") or x["title"]).lower()):
        bits = [f"- **paper_id {p['paper_id']}**", f"  *{p['title']}*"]
        meta = []
        if p["year"]:
            meta.append(str(p["year"]))
        if p["doi"]:
            meta.append(f"DOI: {p['doi']}")
        if meta:
            bits.append("  " + " · ".join(meta))
        if p["apa_citation"]:
            bits.append(f"  APA: {p['apa_citation']}")
        lines.append("\n".join(bits))
    return "\n".join(lines)


# ── synthesis ──────────────────────────────────────────────────────────────
def synthesize(client, model, topic, length, style, excerpt_block):
    user_msg = (
        f"Topic: {topic}\n\n"
        f"Length target: {LENGTH_GUIDANCE[length]}.\n"
        f"Style: {STYLE_GUIDANCE[style]}\n\n"
        f"Source excerpts:\n\n{excerpt_block}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Synthesize a topic from NEON literature sources. "
                    "Output is raw prose; formatting is the agent's job.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--topic", required=True, help="Synthesis question / prompt")
    p.add_argument("--schema", required=True, help="NEON schema (e.g. rorschach, psychlibrary)")
    p.add_argument("--paper-ids", help="Comma-separated paper_ids to draw from")
    p.add_argument("--chunk-ids", help="Comma-separated chunk_ids to draw from")
    p.add_argument("--query", help="Full-text query against chunks.content (use MCP semantic_search for richer retrieval, then pass results via --chunk-ids)")
    p.add_argument("--top-k", type=int, default=15, help="Max chunks for --query mode")
    p.add_argument("--length", choices=list(LENGTH_GUIDANCE.keys()), default="medium")
    p.add_argument("--style", choices=list(STYLE_GUIDANCE.keys()), default="empirical")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--output", default="-", help="Output path or '-' for stdout (default)")
    args = p.parse_args()

    if not DATABASE_URL:
        sys.exit("DATABASE_URL not set (looked in script dir, parent dirs, and ragarmy_local/.env)")
    if not ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set")

    paper_ids = parse_id_list(args.paper_ids)
    chunk_ids = parse_id_list(args.chunk_ids)

    if not (paper_ids or chunk_ids or args.query):
        sys.exit("Provide at least one of: --paper-ids, --chunk-ids, --query")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    conn = psycopg2.connect(DATABASE_URL)
    rows = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if paper_ids:
                got = fetch_chunks_by_paper_ids(cur, args.schema, paper_ids)
                log.info("paper-id selector: %d chunks across %d papers",
                         len(got), len({r["paper_id"] for r in got}))
                rows.extend(got)
            if chunk_ids:
                got = fetch_chunks_by_chunk_ids(cur, args.schema, chunk_ids)
                log.info("chunk-id selector: %d chunks", len(got))
                rows.extend(got)
            if args.query:
                got = fetch_chunks_by_query(cur, args.schema, args.query, args.top_k, client)
                log.info("query selector: %d chunks (top_k=%d)", len(got), args.top_k)
                rows.extend(got)
    finally:
        conn.close()

    if not rows:
        sys.exit("No chunks resolved from selectors — nothing to synthesize")

    # Dedupe by chunk_id
    seen_chunk_ids = set()
    deduped = []
    for r in rows:
        if r["chunk_id"] not in seen_chunk_ids:
            deduped.append(r)
            seen_chunk_ids.add(r["chunk_id"])
    log.info("synthesis input: %d unique chunks across %d papers (model=%s)",
             len(deduped), len({r["paper_id"] for r in deduped}), args.model)

    excerpt_block = build_excerpt_block(deduped)
    prose = synthesize(client, args.model, args.topic, args.length, args.style, excerpt_block)
    sources_block = render_sources_block(unique_papers(deduped))

    output = prose + "\n" + sources_block + "\n"

    if args.output == "-":
        sys.stdout.write(output)
    else:
        Path(args.output).write_text(output)
        log.info("wrote %d bytes to %s", len(output), args.output)


if __name__ == "__main__":
    main()
