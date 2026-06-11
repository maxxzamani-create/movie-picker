#!/usr/bin/env python3
"""Format a Plaud `get_transcript` result into readable markdown.

The Plaud `get_transcript` tool returns a JSON list with (among others):
  - a `transaction` entry whose `data_content` is a JSON *string* of segments,
    each `{start_time, end_time, content, speaker}` with times in milliseconds;
  - an `outline` entry whose `data_content` is a JSON string of
    `{start_time, end_time, topic}` section markers.

A full day's transcript is hundreds of KB, so the daily-digest workflow hands
the raw JSON to this script instead of loading it into the model. It prints a
`## Topics` section and a `## Transcript` section to stdout (append it after the
file header + summary).

Usage:
    python3 scripts/format_transcript.py <transcript.json>
    python3 scripts/format_transcript.py -            # read JSON from stdin
"""

import json
import sys


def hms(ms):
    """Milliseconds -> 'H:MM:SS' (hour dropped when zero -> 'M:SS')."""
    total = int(ms) // 1000
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def load(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    return json.loads(raw)


def section(entries, data_type):
    for e in entries:
        if e.get("data_type") == data_type:
            content = e.get("data_content") or ""
            return json.loads(content) if content else []
    return []


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)

    entries = load(sys.argv[1])
    out = []

    topics = section(entries, "outline")
    out.append("## Topics\n")
    if topics:
        for t in topics:
            out.append(f"- [{hms(t['start_time'])}] {t['topic']}")
    else:
        out.append("_No topic outline._")
    out.append("")

    segments = section(entries, "transaction")
    out.append("## Transcript\n")
    if segments:
        for seg in segments:
            speaker = seg.get("speaker") or "Speaker"
            text = (seg.get("content") or "").strip()
            out.append(f"[{hms(seg['start_time'])}] {speaker}: {text}")
    else:
        out.append("_No transcript content._")
    out.append("")

    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main()
