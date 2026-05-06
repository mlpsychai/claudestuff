#!/usr/bin/env python3
"""
Generate one-paragraph hover summaries for every leaf topic in rorschach.quote_topics.

For each leaf, pulls all assigned quote_text values and asks Claude to produce a
short empirical summary (3-5 sentences, ~80-120 words) that captures what the
clustered quotes collectively say. Writes back to rorschach.quote_topics.summary.

Usage:
  python3 summarize_topics.py [--model claude-sonnet-4-6] [--force]
                              [--max-quotes-per-topic 30]
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

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("summarize_topics")

SYSTEM_PROMPT = """You are a research librarian summarizing thematic clusters in a Rorschach Inkblot Test literature corpus.

Given the topic name and a set of quotes that were grouped together, write ONE paragraph (3-5 sentences, 80-120 words) that:
  - Identifies the empirical or conceptual core that unites these quotes
  - Names specific findings, methods, scores, or theoretical positions when they appear
  - Notes any contrasts, tensions, or critiques among the quotes if present
  - Avoids generalities; does not introduce facts that are not supported by the quotes

Write in confident, formal prose. No preamble, no list format, no "this cluster discusses"-style throat-clearing — just the paragraph."""


def fetch_targets(cur, force):
    where = "" if force else "AND (t.summary IS NULL OR t.summary = '')"
    cur.execute(f"""
        SELECT t.topic_id, t.topic_name, t.member_count,
               p.topic_name AS parent_name
        FROM rorschach.quote_topics t
        LEFT JOIN rorschach.quote_topics p ON p.topic_id = t.parent_id
        WHERE t.parent_id IS NOT NULL
          {where}
        ORDER BY COALESCE(p.topic_id, 0), t.topic_id
    """)
    return cur.fetchall()


def fetch_quotes_for_topic(cur, topic_id, max_quotes):
    cur.execute("""
        SELECT q.quote_text
        FROM rorschach.canonical_picks_quotes_topics qt
        JOIN rorschach.canonical_picks_quotes q ON q.quote_id = qt.quote_id
        WHERE qt.topic_id = %s
        ORDER BY qt.confidence DESC NULLS LAST
        LIMIT %s
    """, (topic_id, max_quotes))
    return [r["quote_text"] for r in cur.fetchall()]


def summarize(client, model, topic_name, parent_name, quotes):
    quotes_block = "\n\n".join(f"[{i + 1}] {q}" for i, q in enumerate(quotes))
    user_msg = (
        f"Parent topic: {parent_name}\n"
        f"Leaf topic: {topic_name}\n"
        f"Member quote count: {len(quotes)}\n\n"
        f"Quotes:\n{quotes_block}"
    )
    resp = client.messages.create(
        model=model,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--force", action="store_true",
                   help="Regenerate summaries even if already present")
    p.add_argument("--max-quotes-per-topic", type=int, default=30)
    args = p.parse_args()

    if not DATABASE_URL:
        sys.exit("DATABASE_URL not set in environment")
    if not ANTHROPIC_API_KEY:
        sys.exit("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            targets = fetch_targets(cur, args.force)
            log.info("summarizing %d leaf topics", len(targets))
            for t in targets:
                quotes = fetch_quotes_for_topic(cur, t["topic_id"], args.max_quotes_per_topic)
                if not quotes:
                    log.warning("topic_id=%s (%s): no quotes assigned, skipping",
                                t["topic_id"], t["topic_name"])
                    continue
                log.info("[%s] %s  (%d quotes)",
                         t["parent_name"], t["topic_name"], len(quotes))
                summary = summarize(client, args.model, t["topic_name"],
                                    t["parent_name"], quotes)
                cur.execute("""
                    UPDATE rorschach.quote_topics
                    SET summary = %s, summary_generated_at = NOW()
                    WHERE topic_id = %s
                """, (summary, t["topic_id"]))
        conn.commit()
        log.info("done")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
