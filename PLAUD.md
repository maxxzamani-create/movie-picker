# Plaud daily digest

One command to pull a day's [Plaud](https://plaud.ai) recordings, write each
transcript to disk, and flag the action items — so the manual "open Plaud,
read each recording, copy out my to-dos" routine becomes a single step.

## Use it

In Claude Code (the environment where your Plaud account is connected):

```
/plaud-daily              # today's recordings
/plaud-daily yesterday
/plaud-daily 2026-06-04    # a specific day
```

That's it. It will:

1. List every recording **uploaded** that day (a day's audio finishes
   processing overnight and lands the next morning, so "today" = today's
   uploads).
2. Save each transcript to `plaud/transcripts/<date>/NN-<slug>.md` — with the
   AI summary, the topic outline, and the full timestamped, speaker-attributed
   transcript.
3. Collect all action items into `plaud/action-items/<date>.md`, with **your
   (Max's)** items pinned at the top and everyone else's grouped below.
4. Print a short recap: how many recordings, where the files went, and a
   preview of your action items.

Re-running a date overwrites that date's files, so it's safe to run twice.

## Output layout

```
plaud/
  transcripts/
    2026-06-04/
      01-a-day-of-crisis-management.md
      02-...
  action-items/
    2026-06-04.md
```

`plaud/` is git-ignored — these are personal transcripts and never get
committed.

## How it works

Plaud is reachable only through the **Plaud MCP server** connected to Claude
Code (it holds your auth), so the workflow lives as a Claude Code slash command
rather than a standalone script that hits the Plaud API directly. The command
definition is in [`.claude/commands/plaud-daily.md`](.claude/commands/plaud-daily.md);
edit it to change the output format or folders.

It uses three Plaud MCP tools: `list_files` (with a date filter),
`get_transcript` (timestamped segments + topic outline), and `get_note` (AI
summary + the `## Action Items` section grouped by person).

## Running it non-interactively (cron, terminal)

[`scripts/plaud-daily.sh`](scripts/plaud-daily.sh) wraps the command for
headless use:

```bash
scripts/plaud-daily.sh              # today
scripts/plaud-daily.sh 2026-06-04
```

This calls `claude -p "/plaud-daily …"`. It only works where the `claude` CLI
can reach the Plaud MCP server. In the Claude Code web/managed environment the
server is injected automatically; to run from a plain terminal or cron you must
first register it once with `claude mcp add …` (check with `claude mcp list`).
