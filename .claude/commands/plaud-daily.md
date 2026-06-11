---
description: Daily Plaud briefing — summarize the newest recordings by project, split by device, with your to-dos
argument-hint: "[date: YYYY-MM-DD | 'yesterday' | blank = today]"
---

# Plaud daily briefing

Produce a short, skimmable **daily briefing** from the newest Plaud recordings
and show it **right here in chat**, then save a copy. The goal is: read the day
in ~30 seconds, see what happened per project, and see your to-dos — no digging
through transcripts.

Drive the connected **Plaud MCP server** (tools end in `_list_files`,
`_get_note`, `_get_transcript`). Never call `get_file` (it's huge).

## Who owns each device

Plaud recordings carry a `serial_number`. Map it to a person:

| serial_number      | person |
| ------------------ | ------ |
| `8810B50283418046` | Max    |
| `8810B50297255281` | Carly  |

Recent recordings are also auto-named with a `Maxx` or `Carly` prefix — use
that as a fallback when a serial isn't in the table. Any unknown serial is a
new/unmapped device: label it with the serial and flag it so it can be added
here.

## Target date

Resolve `$ARGUMENTS` to one `YYYY-MM-DD`: empty → today; `yesterday`/`today`
relative to the current date; or an explicit date. Call it `DATE`. Plaud's date
filter matches the **upload** date, which is what we want (a day's audio lands
the next morning).

## Steps

1. `list_files(date_from=DATE, date_to=DATE)`. If empty: post
   "🎙️ No new Plaud recordings for DATE." in chat and stop.

2. Group the recordings by `serial_number` → person, ordered by `start_at`.

3. For each recording, `get_note(file_id)` and read the `auto_sum_note`
   markdown. It has: a top overview paragraph, then `## <Topic>` section
   headers, then a `## Action Items` section grouped by `**@Person**`.
   - **Short summary** = the overview paragraph, tightened to 2–3 plain
     sentences (no jargon).
   - **By project** = the `## <Topic>` headers (these are the day's
     projects/threads) — one bullet each, with a few words on what moved.
   - **Action items** = the `## Action Items` list; keep the `@Max` items for
     the "your to-dos" line and note who else has items.

4. **Build the briefing** in this shape:

   ```
   # 🎙️ Plaud Daily — <Month D, YYYY>

   ## 👤 Max's Plaud — <N> recording(s)

   ### <Title>
   *Recorded <time> · <duration>*

   <2–3 sentence plain summary>

   **By project:**
   - 🏠 <Topic> — <what moved>
   - 🍷 <Topic> — <what moved>
   ...

   **✅ Your to-dos (<count>):** <item · item · item · …>

   ## 👤 Carly's Plaud
   <her recordings in the same shape, OR:>
   _Not syncing to this account — only Max's device (serial …) shows up._
   ```

   Use a sensible emoji per project (🏠 real estate, 🍷 winery, ☀️ solar,
   🏗️ construction, 💰 financing, 🏥 health, 👨‍👩‍👧 family). Keep it tight.

5. **Save** the briefing to `plaud/briefings/DATE.md` (create the folder).

6. Also save full transcripts for reference (quietly, no chat clutter): for each
   recording write `plaud/transcripts/DATE/<Owner>-NN-<slug>.md` with a header,
   the summary, and — via `python3 scripts/format_transcript.py "<saved_path>"` —
   the topics + timestamped transcript. `<Owner>` is the owner prefix from the
   serial→person map: `Maxx` or `Carly` (use the recording-name prefix as a
   fallback, or the raw serial for an unknown device). So a file looks like
   `Maxx-01-winery-call.md` or `Carly-02-rcfe-walkthrough.md`. (`get_transcript`
   returns a *saved file path* for long recordings; pass that path to the script,
   don't read it into context.)

7. **Post the full briefing in chat.** That's the deliverable the user reads.

8. **File pertinent info into the projects.**

   **Preferred — Cowork project folders (local/desktop runs):** if the user's
   Cowork projects are accessible on this machine, match each topic in the
   briefing to its Cowork project (care facility/RCFE, winery, Cal City duplex,
   ZRE, solar, family — fuzzy match by name). Inside each matching project
   folder, create a `Plaud notes/` folder if it doesn't exist and write
   `DATE.md` containing that project's summary + action-item checkboxes for the
   day. Re-running a date overwrites that date's file. A topic with no matching
   Cowork project: note it in chat instead of guessing a folder.

   **Fallback — Notion (cloud runs, no Cowork access):** file into the Notion
   Projects hub (page titled **Projects**,
   id `37ca86e4-fa11-8130-83bd-e1aa4ffc0dfb`; `search` by name if the id no
   longer resolves; create the hub if missing). Match each topic to a child
   project page (create one if new) and **append a `## <Month D, YYYY>`
   section** with the summary + `- [ ] **@Owner** <task>` checkboxes via
   `update-page` — never overwrite earlier sections; on re-run replace just
   today's dated section. Skip silently if Notion isn't connected either.

   Keep this quiet — a one-line chat note ("Filed to: RCFE, Winery, Family")
   is enough; the briefing in step 7 is the main deliverable.

## Notes

- Output under `plaud/` is git-ignored unless committed deliberately.
- Re-running a date overwrites that date's briefing (safe to re-run).
- Notion filing (step 8) appends a dated section per project and is safe to
  re-run; it updates today's section in place rather than duplicating.
- To change the look, edit this file.
