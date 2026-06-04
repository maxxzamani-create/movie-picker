---
description: Pull a day's Plaud recordings, write transcripts to disk, and flag action items
argument-hint: "[date: YYYY-MM-DD | 'yesterday' | blank = today]"
---

# Plaud daily digest

Pull every Plaud recording uploaded on a given day, save each transcript to
disk, and surface the action items — especially the ones assigned to **Max**.

This command drives the connected **Plaud MCP server**. The tools it uses are
named `*_list_files`, `*_get_note`, and `*_get_transcript` (the MCP server has
an opaque ID prefix in this environment — match on the suffix). Do **not** call
`get_file`; it returns hundreds of KB of inlined audio metadata and is not
needed.

## Target date

`$ARGUMENTS` is the requested day. Resolve it to a single `YYYY-MM-DD`:

- empty → **today** (use the current date from the environment).
- `yesterday` / `today` → resolve relative to the current date.
- an explicit `YYYY-MM-DD` → use as-is.

Call the date `DATE` below. Plaud's `list_files` date filter matches on the
**upload** date (`created_at`), which is what we want: a day's audio finishes
processing and lands the following morning, so "today's recordings" are the
ones uploaded today.

## Steps

1. **List the day's recordings.** Call `list_files` with
   `date_from = DATE` and `date_to = DATE`. If `data` is empty, tell the user
   "No Plaud recordings uploaded on DATE." and stop — do not create any files.

2. **Order them.** Sort the recordings by `start_at` ascending so the numbering
   reflects the order they were recorded.

3. **Prepare output folders** under the repo root (create if missing):
   - `plaud/transcripts/DATE/`
   - `plaud/action-items/`

4. **For each recording** (index `NN` starting at `01`, two digits):

   a. Build a slug from `name`: lowercase, strip a leading `MM-DD ` date prefix
      if present, replace any run of non-alphanumeric characters with a single
      `-`, trim leading/trailing `-`, and cap at ~60 characters. Filename =
      `NN-<slug>.md`. If the name is just a timestamp, use `NN-recording.md`.

   b. Call `get_note(file_id)`. From the returned list, take the entry whose
      `data_type` is `auto_sum_note` and read its `data_content` (markdown).
      The summary text is everything before the `## Action Items` heading; the
      action items are the `## Action Items` section to the end. If there is no
      summary note, note that and continue.

   c. **Write the file header + summary first.** Create
      `plaud/transcripts/DATE/NN-<slug>.md` containing only:

      ```
      # <name>

      - Recording ID: <id>
      - Recorded: <start_at>  (duration <H:MM:SS>, from duration_ms / 1000)
      - Uploaded: <created_at>

      ## Summary

      <summary portion of the auto_sum_note, or "_No summary available._">

      ```

   d. Call `get_transcript(file_id)`. **A full day's transcript is hundreds of
      KB**, so the tool will usually not return it inline — it returns a message
      saying the result was *saved to a file* at some path. **Do not read that
      file into context.** Instead append the formatted transcript directly:

      ```
      python3 scripts/format_transcript.py "<saved_file_path>" \
        >> plaud/transcripts/DATE/NN-<slug>.md
      ```

      If the transcript was small enough to come back inline, write that JSON to
      a temp file and run the same script on it (or pipe via `-`). The script
      emits the `## Topics` and `## Transcript` sections, with timestamps as
      `H:MM:SS`. The raw transcript JSON has a `transaction` entry
      (`data_content` = JSON string of `{start_time, end_time, content,
      speaker}`, milliseconds) and an `outline` entry (`{start_time, topic}`);
      entries that carry only an S3 `data_link` (highlights / polished audio)
      are ignored by the script.

5. **Aggregate action items** into `plaud/action-items/DATE.md`. Collect the
   `## Action Items` section from every recording's summary note. The notes
   group items as `**@Person**` followed by `- [ ]` checkbox lines, sometimes
   with a `- [<when>]` due hint. Produce a single file:

   ```
   # Action items — DATE

   _N recordings · M action items_

   ## ⭐ Yours (Max)

   <every @Max item, as "- [ ] <text>  — <when> _(from: NN-<slug>)_">

   ## Delegated / others

   ### @<Person>
   <their items, same format, grouped by person>
   ```

   Put **@Max** first and prominent. Preserve any due/`when` hints. If a person
   has no items, omit them. If there are zero action items across all
   recordings, still write the file with "_No action items._".

6. **Report** a concise summary in chat (do not paste full transcripts):
   - the date and number of recordings,
   - the list of transcript files written (relative paths),
   - the count of **your** (@Max) action items and a short bullet preview of
     them,
   - the path to `plaud/action-items/DATE.md`.

## Notes

- Generated output lives under `plaud/`, which is git-ignored — these are
  personal transcripts and never get committed.
- Re-running for the same date overwrites that date's files (idempotent).
