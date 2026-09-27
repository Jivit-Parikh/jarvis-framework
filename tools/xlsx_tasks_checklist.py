#!/usr/bin/env python3
"""
xlsx_tasks_checklist.py <workbook.xlsx> [--sheet <name>]

Extracts every task item from a workbook's task sheet into a JSON
checklist, so excel-solver has a structural list of what has to be
addressed rather than relying purely on its own self-reported summary
(SA-5's acceptance-check gap).

Prints JSON to stdout:
{
  "source": "<path>",
  "sheet": "<actual sheet name>" | null,
  "note": "<explanation>" | null,
  "items": [
    {
      "number": <int> | null,
      "row": <1-based row number>,
      "sheet": "<sheet name>",
      "part": "<enclosing 'Part X' / section header text>" | null,
      "text": "<row's cell values, in column order, joined with ' | '>",
      "done": false,
      "addressed_at": null
    },
    ...
  ]
}

Sheet detection
---------------
The sheet holding the task list is not always literally named "Tasks".
Detection is case-insensitive and tries, in order:
  1. `--sheet <name>` on the command line, if given (exact, case-insensitive
     match against the workbook's sheet names; hard error if that sheet
     doesn't exist).
  2. An exact (case-insensitive, whitespace-trimmed) match on "tasks" or
     "task".
  3. Any sheet name containing "task" as a whole word-ish fragment (e.g.
     "Task Sheet", "TASK", "Tasks (final)").
  4. Any sheet name containing "instructions".
  5. Any sheet name containing "questions".
If nothing matches, "sheet" is null, "items" is [], and "note" lists the
workbook's actual sheet names so the calling agent can read the workbook's
structure directly (some workbooks embed the task list in the
data sheet itself instead of a dedicated sheet). This is not an error;
the script exits 0.

Task-row detection
-------------------
Handles the layouts actually seen in real assignment workbooks:

  - Table layout: first cell is a plain integer (or integer-valued float),
    e.g. a "Task #" column. Rows fully covered by a single merged range
    spanning more than one column in that row (typically a section title
    like "TEXT FUNCTIONS") are treated as structural headers, not items.

  - Numbered/lettered free text: a line like "1. Rename the worksheet..."
    or "1) ..." or "Q1 ..." / "Task 3 ...". The leading number is
    extracted as `"number"`.

  - Bulleted free text: a line starting with -, *, or •.

  - Plain instruction sentences with no numbering (seen in MODULE 1.xlsx's
    TASK sheet): counted as an item when the line ends with '.' (a
    completed sentence) and is not itself a "Part X:" header or a
    list-introducing sub-header line ending with ':' (e.g. "Apply the
    following formatting:", which introduces the items that follow it,
    rather than being one itself). This also naturally excludes bare
    example tokens dropped into the sheet as illustrations (e.g. "EMP001",
    "January") since they carry no trailing period.

  - "Part A" / "Part B" ... header rows (a line matching `^Part\\s+\\w+`,
    optionally followed by ':') are not items; they set the current
    "part" context attached to every item that follows until the next
    part header. A full-row merged section header (e.g. "TEXT FUNCTIONS")
    also sets this context.

A merged cell's value (openpyxl only stores it on the top-left cell of
the range) is resolved to every cell in that range before building each
row's joined text, so a task description that spans merged cells still
reads correctly.

`"done"` and `"addressed_at"` are always false/null here, this script
only extracts the checklist; the calling agent fills those in as it
works and reports the annotated checklist back, it does not re-run this
script with completion status.

CLI usage:
    python3 xlsx_tasks_checklist.py <workbook.xlsx> [--sheet <name>]
"""
import sys
import json
import re
import argparse
import openpyxl


_BULLET_RE = re.compile(r'^\s*[-*•]\s*(.+)')
_TASK_PREFIX_RE = re.compile(r'^\s*(?:task|q)\s*#?\s*(\d+)\b', re.IGNORECASE)
_NUM_PREFIX_RE = re.compile(r'^\s*(\d+)[.)]\s+\S')
_PART_HEADER_RE = re.compile(r'^\s*part\s+([a-z0-9]+)\b\.?\s*:?\s*$', re.IGNORECASE)
_PART_HEADER_WITH_BODY_RE = re.compile(r'^\s*(part\s+[a-z0-9]+)\s*:\s*(.*\S)', re.IGNORECASE)


def _norm(name):
    return name.strip().lower()


def find_tasks_sheet(workbook, requested=None):
    """Returns (sheet_name, error_message_or_None)."""
    names = workbook.sheetnames

    if requested is not None:
        for name in names:
            if _norm(name) == _norm(requested):
                return name, None
        return None, (
            f"--sheet {requested!r} not found (sheet names: {names!r})"
        )

    # 1. exact "tasks" / "task"
    for name in names:
        if _norm(name) in ("tasks", "task"):
            return name, None

    # 2. contains "task"
    for name in names:
        if "task" in _norm(name):
            return name, None

    # 3. contains "instructions"
    for name in names:
        if "instructions" in _norm(name):
            return name, None

    # 4. contains "questions"
    for name in names:
        if "questions" in _norm(name):
            return name, None

    return None, None


def _build_merge_value_map(worksheet):
    """Map every (row, col) covered by a merged range to that range's
    stored value (only the top-left cell actually holds it in openpyxl)."""
    value_map = {}
    for merged_range in worksheet.merged_cells.ranges:
        anchor = worksheet.cell(row=merged_range.min_row, column=merged_range.min_col)
        for r in range(merged_range.min_row, merged_range.max_row + 1):
            for c in range(merged_range.min_col, merged_range.max_col + 1):
                value_map[(r, c)] = anchor.value
    return value_map


def _full_row_header_ranges(worksheet):
    """Row numbers that are entirely covered by one merged range spanning
    more than one column in that row -- treated as a section header/title,
    not a task item."""
    header_rows = set()
    for merged_range in worksheet.merged_cells.ranges:
        if merged_range.min_row == merged_range.max_row and merged_range.max_col > merged_range.min_col:
            header_rows.add(merged_range.min_row)
    return header_rows


def _cell_display(value):
    if value is None:
        return None
    return str(value).strip()


def _row_number_and_text(worksheet, row_idx, merge_value_map):
    max_col = worksheet.max_column
    values = []
    for c in range(1, max_col + 1):
        raw = worksheet.cell(row=row_idx, column=c).value
        if raw is None:
            raw = merge_value_map.get((row_idx, c))
        display = _cell_display(raw)
        if display:
            values.append(display)
    return values


def _first_cell_text(worksheet, row_idx, merge_value_map):
    raw = worksheet.cell(row=row_idx, column=1).value
    if raw is None:
        raw = merge_value_map.get((row_idx, 1))
    return raw


def extract_checklist(path, requested_sheet=None):
    workbook = openpyxl.load_workbook(path, data_only=False)
    sheet_name, err = find_tasks_sheet(workbook, requested_sheet)

    if err:
        return {
            "source": path,
            "sheet": None,
            "note": err,
            "items": [],
        }

    if sheet_name is None:
        return {
            "source": path,
            "sheet": None,
            "note": (
                "no task-like sheet found (tried exact 'tasks'/'task', then "
                "names containing 'task', 'instructions', or 'questions'; "
                f"sheet names: {workbook.sheetnames!r}); this workbook may "
                "embed its task list in a data sheet instead, read it "
                "directly, or pass --sheet <name> if one of these is it"
            ),
            "items": [],
        }

    worksheet = workbook[sheet_name]
    merge_value_map = _build_merge_value_map(worksheet)
    header_rows = _full_row_header_ranges(worksheet)

    items = []
    current_part = None

    for row_idx in range(1, worksheet.max_row + 1):
        first_col_raw = _first_cell_text(worksheet, row_idx, merge_value_map)
        first_col_text = first_col_raw.strip() if isinstance(first_col_raw, str) else None

        if row_idx in header_rows:
            # Structural section header (e.g. "TEXT FUNCTIONS"). Use it as
            # the current part/section context for subsequent items.
            row_values = _row_number_and_text(worksheet, row_idx, merge_value_map)
            if row_values:
                current_part = row_values[0]
            continue

        # "Part A" / "Part B:" style header line -- not an item itself,
        # sets context for what follows. Handle both "Part A" alone and
        # "Part A: <body text>" (rare, but keep it as an item if it carries
        # real instruction text after the colon).
        if first_col_text:
            part_match = _PART_HEADER_RE.match(first_col_text)
            if part_match:
                current_part = first_col_text.rstrip(':').strip()
                continue
            part_with_body = _PART_HEADER_WITH_BODY_RE.match(first_col_text)
            if part_with_body:
                current_part = part_with_body.group(1).strip()
                # fall through, body text after the colon is still checked
                # below via the normal rules on first_col_text as a whole;
                # simplest is to just treat this row as a header only,
                # since the part label is the meaningful bit here.
                continue

        number = None
        is_task_row = False

        if isinstance(first_col_raw, (int, float)) and not isinstance(first_col_raw, bool):
            if float(first_col_raw).is_integer():
                number = int(first_col_raw)
                is_task_row = True
        elif first_col_text:
            bullet_match = _BULLET_RE.match(first_col_text)
            prefix_match = _TASK_PREFIX_RE.match(first_col_text)
            num_match = _NUM_PREFIX_RE.match(first_col_text)

            if prefix_match:
                number = int(prefix_match.group(1))
                is_task_row = True
            elif num_match:
                number = int(num_match.group(1))
                is_task_row = True
            elif bullet_match:
                is_task_row = True
            elif (
                not first_col_text.endswith(':')
                and first_col_text.endswith('.')
                and len(first_col_text) > 3
            ):
                # Plain, unnumbered instruction sentence (MODULE 1.xlsx's
                # TASK sheet layout). A line ending in ':' introduces a
                # list rather than being an item, so it's excluded; a bare
                # example token (e.g. "EMP001", "January") has no trailing
                # period, so it's excluded too.
                is_task_row = True

        if not is_task_row:
            continue

        row_values = _row_number_and_text(worksheet, row_idx, merge_value_map)
        if not row_values:
            continue

        items.append({
            "number": number,
            "row": row_idx,
            "sheet": sheet_name,
            "part": current_part,
            "text": " | ".join(row_values),
            "done": False,
            "addressed_at": None,
        })

    return {
        "source": path,
        "sheet": sheet_name,
        "note": None,
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract a task checklist from a workbook's task sheet."
    )
    parser.add_argument("workbook", help="path to the .xlsx workbook")
    parser.add_argument(
        "--sheet",
        default=None,
        help="override sheet-name detection with this exact sheet name "
             "(case-insensitive)",
    )
    args = parser.parse_args()

    result = extract_checklist(args.workbook, requested_sheet=args.sheet)
    print(json.dumps(result, indent=2, default=str))

    if result["note"] is not None and result["sheet"] is None and args.sheet is not None:
        # An explicit --sheet that didn't resolve is a real error.
        sys.exit(2)


if __name__ == "__main__":
    main()
