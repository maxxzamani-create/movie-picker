#!/usr/bin/env bash
#
# plaud-daily.sh — run the Plaud daily digest non-interactively.
#
# This is a thin wrapper around the `/plaud-daily` Claude Code slash command.
# It pulls a day's Plaud recordings, writes transcripts under plaud/transcripts/,
# and flags action items in plaud/action-items/<date>.md.
#
# Usage:
#   scripts/plaud-daily.sh                # today
#   scripts/plaud-daily.sh 2026-06-04     # a specific day
#   scripts/plaud-daily.sh yesterday
#
# Requirements:
#   - The `claude` CLI on PATH.
#   - The Plaud MCP server must be reachable from this invocation. In the
#     Claude Code web/managed environment it is injected automatically. To run
#     this from a plain terminal or cron, first register the server with the
#     CLI (one time):
#         claude mcp add ...   # your Plaud MCP server endpoint + auth
#     Verify with `claude mcp list`. Without it, the run has no Plaud access.

set -euo pipefail

DATE_ARG="${1:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: 'claude' CLI not found on PATH" >&2
  exit 1
fi

# Run the slash command headlessly. --permission-mode acceptEdits lets it
# write the transcript/action-item files without prompting.
exec claude -p "/plaud-daily ${DATE_ARG}" --permission-mode acceptEdits
