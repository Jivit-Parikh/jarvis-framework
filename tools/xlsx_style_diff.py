#!/usr/bin/env python3
"""
xlsx_style_diff.py <original.xlsx> <output.xlsx> [--map "OLD=NEW" ...]

Compares every cell across sheets shared between two workbooks: value,
font (name/size/bold/italic/underline/color), fill (pattern/fgColor),
border (each side's style/color), number_format, and alignment
(horizontal/vertical/wrap_text).

Sheet pairing
-------------
A sheet rename used to make the old version of this script report "0
changes" silently, because it only ever compared sheets with identical
names. It now pairs sheets like this, in order:

  1. Exact name matches (both files have a sheet called the same thing).
  2. `--map "OLD=NEW"` (repeatable): explicit pairing for a sheet that
     was renamed, e.g. `--map "DATASET=Employee Sales Data"`.
  3. Auto-pairing: if, after (1) and (2), exactly one sheet remains
     unmatched in each file, and their header rows (row 1) overlap
     heavily (most of the original's column headers are still present
     in the candidate output sheet), they are auto-paired and this is
     called out explicitly in the report as a likely rename.

Any sheet still unmatched after that is reported under "Sheets only in
original" or "Sheets only in output" (added/removed/renamed-without-a-
usable-pairing-signal), instead of being silently skipped.

Column alignment within a paired sheet
---------------------------------------
Within each paired sheet, if both sides have a usable header row (row 1)
with at least two matching header texts (case-insensitive, whitespace-
trimmed), columns are aligned by header text rather than raw column
index. This means a column inserted in the middle of the sheet (e.g. a
new "Employee Code" column before "Emp ID") does not make every column
after it look like it changed. Header texts present only on one side are
reported separately as "Columns inserted" / "Columns removed"; they are
new cells with no prior counterpart, so they are not compared cell-by-
cell against anything and do not themselves count as a "style change to
a pre-existing cell".

Matched columns (present, by header text, on both sides) are then
compared cell-by-cell, row by row, including the header row itself --
so a header that kept its text but changed font/fill (e.g. new bold
headers) is correctly reported as a style change on a pre-existing
cell, along with any number-format changes on the data cells below it.

If a paired sheet has no usable header row (fewer than 2 matching
headers on row 1), column alignment falls back to plain positional
comparison (the original behavior), including column-width and
merged-range comparison, which are skipped in header-aligned mode since
column positions are expected to shift when columns are inserted.

Output
------
Prints "Value-only changes", "Style changes", "Columns inserted" /
"Columns removed" (per sheet), and "Sheets only in original" / "Sheets
only in output", plus a "Sheet pairing" section documenting exactly how
each sheet was matched (exact name, --map, or auto-paired) so a rename
is never invisible in the report.

Exit codes
----------
  0 - sheets were compared and no style changes were found on any
      pre-existing (matched) cell.
  1 - at least one style change was found on a pre-existing (matched)
      cell in some paired sheet. Column/sheet insertions themselves do
      not trigger this; only style drift on cells that exist in both
      files does.
  2 - nothing could be compared at all (no sheet pairing could be
      established between the two files -- e.g. every sheet name
      differs and no --map or auto-pairing signal was available). This
      is the "never a silent 0" case: previously an unrelated rename
      could make the script report a clean 0 with nothing actually
      checked.
"""
import sys
import argparse
import openpyxl


def cell_style_tuple(cell):
    f = cell.font
    fill = cell.fill
    b = cell.border

    def side(s):
        if s is None:
            return (None, None)
        return (s.style, str(s.color.rgb) if s.color and s.color.rgb else None)

    align = cell.alignment
    return (
        (f.name, f.sz, f.b, f.i, f.u, str(f.color.rgb) if f.color and f.color.rgb else None),
        (fill.patternType, str(fill.fgColor.rgb) if fill.fgColor and fill.fgColor.rgb else None),
        (side(b.left), side(b.right), side(b.top), side(b.bottom)),
        cell.number_format,
        (align.horizontal, align.vertical, align.wrap_text),
    )


def _header_key(value):
    if value is None:
        return None
    key = str(value).strip().lower()
    return key or None


def build_header_map(worksheet):
    """header text (normalized) -> column index, for row 1. Ambiguous
    (duplicate) header texts are dropped since they can't be aligned
    unambiguously by text alone."""
    headers = {}
    ambiguous = set()
    for c in range(1, worksheet.max_column + 1):
        key = _header_key(worksheet.cell(row=1, column=c).value)
        if key is None:
            continue
        if key in headers:
            ambiguous.add(key)
        else:
            headers[key] = c
    for key in ambiguous:
        headers.pop(key, None)
    return headers


def sheet_overlap_score(ws_o, ws_n):
    """Rough similarity between two sheets' used ranges, for auto-pairing
    an unmatched original sheet with an unmatched output sheet. Prefers
    header-row overlap; falls back to row/column-count closeness when
    neither side has a usable header row."""
    headers_o = build_header_map(ws_o)
    headers_n = build_header_map(ws_n)
    if headers_o and headers_n:
        common = set(headers_o) & set(headers_n)
        denom = min(len(headers_o), len(headers_n))
        return len(common) / denom if denom else 0.0

    # fallback: closeness of used-range shape
    ro, co = ws_o.max_row, ws_o.max_column
    rn, cn = ws_n.max_row, ws_n.max_column
    if ro == 0 or co == 0 or rn == 0 or cn == 0:
        return 0.0
    row_ratio = min(ro, rn) / max(ro, rn)
    col_ratio = min(co, cn) / max(co, cn)
    return (row_ratio + col_ratio) / 2


def pair_sheets(wb_o, wb_n, explicit_map):
    """Returns (pairs, only_o, only_n, pairing_notes).
    pairs: list of (name_o, name_n).
    only_o / only_n: sheet names left unmatched on each side.
    pairing_notes: human-readable strings describing how each pair (or
    non-pair) was decided.
    """
    names_o = list(wb_o.sheetnames)
    names_n = list(wb_n.sheetnames)

    pairs = []
    notes = []
    used_o = set()
    used_n = set()

    # 1. exact name matches
    for name in names_o:
        if name in names_n:
            pairs.append((name, name))
            used_o.add(name)
            used_n.add(name)
            notes.append(f"{name!r}: matched (same name in both files)")

    # 2. explicit --map
    for old, new in explicit_map:
        if old in used_o:
            notes.append(f"--map {old!r}={new!r}: ignored, {old!r} already matched by exact name")
            continue
        if old not in names_o:
            notes.append(f"--map {old!r}={new!r}: ERROR, {old!r} not found in original (sheets: {names_o!r})")
            continue
        if new not in names_n:
            notes.append(f"--map {old!r}={new!r}: ERROR, {new!r} not found in output (sheets: {names_n!r})")
            continue
        if new in used_n:
            notes.append(f"--map {old!r}={new!r}: ignored, {new!r} already matched")
            continue
        pairs.append((old, new))
        used_o.add(old)
        used_n.add(new)
        notes.append(f"{old!r} -> {new!r}: paired via --map (explicit rename)")

    remaining_o = [n for n in names_o if n not in used_o]
    remaining_n = [n for n in names_n if n not in used_n]

    # 3. auto-pair a single leftover on each side if their content overlaps heavily
    if len(remaining_o) == 1 and len(remaining_n) == 1:
        only_o_name, only_n_name = remaining_o[0], remaining_n[0]
        score = sheet_overlap_score(wb_o[only_o_name], wb_n[only_n_name])
        if score >= 0.5:
            pairs.append((only_o_name, only_n_name))
            used_o.add(only_o_name)
            used_n.add(only_n_name)
            notes.append(
                f"{only_o_name!r} -> {only_n_name!r}: auto-paired, "
                f"sole unmatched sheet on each side with {score:.0%} header/shape "
                "overlap -- likely a rename, verify this is correct"
            )
        else:
            notes.append(
                f"{only_o_name!r} and {only_n_name!r}: both unmatched, only "
                f"{score:.0%} overlap, NOT auto-paired (below 50% threshold)"
            )

    only_o = [n for n in names_o if n not in used_o]
    only_n = [n for n in names_n if n not in used_n]

    for n in only_o:
        notes.append(f"{n!r}: only in original (removed, or renamed with no usable pairing signal)")
    for n in only_n:
        notes.append(f"{n!r}: only in output (added, or renamed with no usable pairing signal)")

    return pairs, only_o, only_n, notes


def diff_paired_sheet(ws_o, ws_n, label_o, label_n):
    """Returns (value_only, style_changes, structural) for one paired
    sheet, using header-based column alignment when possible."""
    value_only = []
    style_changes = []
    structural = []

    sheet_label = f"{label_o!r}->{label_n!r}" if label_o != label_n else repr(label_o)

    headers_o = build_header_map(ws_o)
    headers_n = build_header_map(ws_n)
    common_headers = set(headers_o) & set(headers_n)
    use_header_alignment = len(common_headers) >= 2

    if use_header_alignment:
        only_o_headers = set(headers_o) - set(headers_n)
        only_n_headers = set(headers_n) - set(headers_o)

        for h in sorted(only_o_headers, key=lambda k: headers_o[k]):
            col = headers_o[h]
            col_letter = ws_o.cell(row=1, column=col).coordinate[:-1]
            structural.append(
                f"{sheet_label}: column removed -- {ws_o.cell(row=1, column=col).value!r} "
                f"(was column {col_letter} in original)"
            )
        for h in sorted(only_n_headers, key=lambda k: headers_n[k]):
            col = headers_n[h]
            col_letter = ws_n.cell(row=1, column=col).coordinate[:-1]
            structural.append(
                f"{sheet_label}: column inserted -- {ws_n.cell(row=1, column=col).value!r} "
                f"(now column {col_letter} in output)"
            )

        col_pairs = sorted(
            ((headers_o[h], headers_n[h], h) for h in common_headers),
            key=lambda t: t[0],
        )
        max_row = max(ws_o.max_row, ws_n.max_row)

        for r in range(1, max_row + 1):
            for co, cn, header_text in col_pairs:
                cell_o = ws_o.cell(row=r, column=co)
                cell_n = ws_n.cell(row=r, column=cn)
                val_changed = cell_o.value != cell_n.value
                style_o = cell_style_tuple(cell_o)
                style_n = cell_style_tuple(cell_n)
                style_changed = style_o != style_n

                if not val_changed and not style_changed:
                    continue

                coord = (
                    f"{sheet_label}!{cell_o.coordinate}->{cell_n.coordinate} "
                    f"(col {header_text!r})"
                )
                if style_changed:
                    style_changes.append(
                        f"{coord}: style differs. old={style_o} new={style_n} "
                        f"(value old={cell_o.value!r} new={cell_n.value!r})"
                    )
                elif val_changed:
                    value_only.append(f"{coord}: value {cell_o.value!r} -> {cell_n.value!r}")

        return value_only, style_changes, structural

    # fallback: no usable header-based alignment, compare positionally
    # (original behavior), including widths and merges.
    max_row = max(ws_o.max_row, ws_n.max_row)
    max_col = max(ws_o.max_column, ws_n.max_column)

    for r in range(1, max_row + 1):
        for c in range(1, max_col + 1):
            cell_o = ws_o.cell(row=r, column=c)
            cell_n = ws_n.cell(row=r, column=c)
            val_changed = cell_o.value != cell_n.value
            style_o = cell_style_tuple(cell_o)
            style_n = cell_style_tuple(cell_n)
            style_changed = style_o != style_n

            if not val_changed and not style_changed:
                continue

            coord = f"{sheet_label}!{cell_n.coordinate}"
            if style_changed:
                style_changes.append(
                    f"{coord}: style differs. old={style_o} new={style_n} "
                    f"(value old={cell_o.value!r} new={cell_n.value!r})"
                )
            elif val_changed:
                value_only.append(f"{coord}: value {cell_o.value!r} -> {cell_n.value!r}")

    widths_o = {k: v.width for k, v in ws_o.column_dimensions.items()}
    widths_n = {k: v.width for k, v in ws_n.column_dimensions.items()}
    for col in set(widths_o) | set(widths_n):
        wo = widths_o.get(col)
        wn = widths_n.get(col)
        if wo != wn:
            style_changes.append(f"{sheet_label}!col {col} width: {wo} -> {wn}")

    merges_o = set(str(m) for m in ws_o.merged_cells.ranges)
    merges_n = set(str(m) for m in ws_n.merged_cells.ranges)
    if merges_o != merges_n:
        style_changes.append(
            f"{sheet_label}: merged ranges differ. old={sorted(merges_o)} new={sorted(merges_n)}"
        )

    return value_only, style_changes, structural


def diff_workbooks(orig_path, out_path, explicit_map):
    wb_orig = openpyxl.load_workbook(orig_path, data_only=False)
    wb_out = openpyxl.load_workbook(out_path, data_only=False)

    pairs, only_o, only_n, pairing_notes = pair_sheets(wb_orig, wb_out, explicit_map)

    value_only = []
    style_changes = []
    structural = []

    for name_o, name_n in pairs:
        v, s, st = diff_paired_sheet(wb_orig[name_o], wb_out[name_n], name_o, name_n)
        value_only.extend(v)
        style_changes.extend(s)
        structural.extend(st)

    return {
        "value_only": value_only,
        "style_changes": style_changes,
        "structural": structural,
        "pairing_notes": pairing_notes,
        "only_o": only_o,
        "only_n": only_n,
        "pairs": pairs,
    }


def parse_map_args(map_args):
    result = []
    for raw in map_args or []:
        if "=" not in raw:
            print(f"error: --map value {raw!r} must be \"OLD=NEW\"", file=sys.stderr)
            sys.exit(2)
        old, new = raw.split("=", 1)
        result.append((old.strip(), new.strip()))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Diff cell values and styles between two workbooks, "
                     "tolerant of sheet renames and inserted/deleted columns."
    )
    parser.add_argument("original", help="path to the original .xlsx")
    parser.add_argument("output", help="path to the edited/output .xlsx")
    parser.add_argument(
        "--map",
        action="append",
        dest="map_args",
        metavar="OLD=NEW",
        help='pair a renamed sheet, e.g. --map "DATASET=Employee Sales Data". Repeatable.',
    )
    args = parser.parse_args()

    explicit_map = parse_map_args(args.map_args)
    result = diff_workbooks(args.original, args.output, explicit_map)

    print("Sheet pairing:")
    for note in result["pairing_notes"]:
        print(f"  - {note}")

    if result["only_o"]:
        print(f"\nSheets only in original ({len(result['only_o'])}):")
        for n in result["only_o"]:
            print(f"  - {n!r}")

    if result["only_n"]:
        print(f"\nSheets only in output ({len(result['only_n'])}):")
        for n in result["only_n"]:
            print(f"  - {n!r}")

    if result["structural"]:
        print(f"\nColumn changes ({len(result['structural'])}):")
        for s in result["structural"]:
            print(f"  - {s}")

    print(f"\nValue-only changes ({len(result['value_only'])}):")
    for v in result["value_only"]:
        print(f"  - {v}")

    print(f"\nStyle changes ({len(result['style_changes'])}):")
    for s in result["style_changes"]:
        print(f"  - {s}")

    if not result["pairs"]:
        print(
            "\nNothing could be compared: no sheet pairing could be established "
            "between the two files (no matching names, no --map, no usable "
            "auto-pairing signal). Pass --map \"OLD=NEW\" to pair renamed sheets.",
            file=sys.stderr,
        )
        sys.exit(2)

    if result["style_changes"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
