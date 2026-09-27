#!/usr/bin/env python3
"""
docx_format_check.py <file.docx> [--baseline original.docx]

Checks that every run NOT present in the baseline document (or, if no
baseline is given, every run in the whole document) is formatted:
Times New Roman, 13pt, black (RGB 000000 or no explicit color / theme
"auto"), not bold, not italic, not underlined, no highlight.

Checks BOTH document-body paragraphs AND table-cell paragraphs
(including paragraphs inside a table nested in a cell), walked together
in document order, the same traversal docx_insert_answers.py uses to
find insertion targets. A worksheet whose questions live in a table is
checked exactly the same as one that doesn't.

"Present in baseline" is decided by matching paragraph text, in the
same body+table-cell document-order sequence, against the baseline
docx. Any paragraph beyond the baseline's sequence, or any paragraph
whose text differs from the baseline paragraph at that position, is
treated as new/inserted content and is checked. This is a heuristic
good enough for worksheet-solver's "insert answers, don't touch
anything else" workflow.

Exit 0 and prints "OK" if all applicable runs pass.
Exit 1 and lists every violation (location, run index, text snippet,
what's wrong) if any run fails.
"""
import sys
import argparse
import difflib
import docx
from docx.shared import Pt
from docx.text.paragraph import Paragraph
from docx.table import Table


def run_violations(run):
    problems = []
    font = run.font
    name = font.name
    east_asian = None
    try:
        rPr = run._element.rPr
        if rPr is not None:
            rFonts = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts')
            if rFonts is not None:
                east_asian = rFonts.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia')
    except Exception:
        pass

    if name != "Times New Roman":
        problems.append(f"font name is {name!r}, expected 'Times New Roman'")
    if east_asian and east_asian != "Times New Roman":
        problems.append(f"eastAsia font is {east_asian!r}, expected 'Times New Roman'")

    size = font.size
    if size is None or size != Pt(13):
        problems.append(f"font size is {size!r}, expected 13pt")

    color = font.color
    if color is not None and color.rgb is not None and str(color.rgb) != "000000":
        problems.append(f"font color is {color.rgb}, expected black (000000)")

    if font.bold:
        problems.append("run is bold")
    if font.italic:
        problems.append("run is italic")
    if font.underline:
        problems.append("run is underlined")
    if font.highlight_color is not None:
        problems.append(f"run has highlight {font.highlight_color}")

    return problems


def _walk(container_elm, parent_obj, location):
    """Yield (Paragraph, location_str) pairs in document order, walking
    body/cell paragraphs and recursing into every table cell (including
    nested tables). Mirrors docx_insert_answers.py's traversal so both
    tools see the same set of paragraphs in the same order."""
    for child in container_elm.iterchildren():
        if child.tag.endswith('}p'):
            yield Paragraph(child, parent_obj), location
        elif child.tag.endswith('}tbl'):
            tbl = Table(child, parent_obj)
            for r_idx, row in enumerate(tbl.rows):
                for c_idx, cell in enumerate(row.cells):
                    cell_location = f"{location} > table row {r_idx + 1} col {c_idx + 1}"
                    yield from _walk(cell._tc, cell, cell_location)


def get_all_paragraphs(document):
    """List of (Paragraph, location) covering body + every table cell
    (including nested tables), in document order."""
    return list(_walk(document.element.body, document, "body"))


def paragraphs_needing_check(target_texts, baseline_texts):
    """Align target paragraph texts against baseline paragraph texts with
    difflib and return the set of target-sequence indices that are NEW
    (inserted or replaced relative to baseline) -- these are the only
    paragraphs whose runs get format-checked. Paragraphs that match the
    baseline 1:1 ('equal' opcodes) are trusted as untouched."""
    sm = difflib.SequenceMatcher(a=baseline_texts, b=target_texts, autojunk=False)
    new_indices = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            new_indices.update(range(j1, j2))
    return new_indices


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--baseline")
    args = ap.parse_args()

    doc = docx.Document(args.file)
    target_pairs = get_all_paragraphs(doc)
    target_texts = [p.text for p, _loc in target_pairs]

    if args.baseline:
        base_doc = docx.Document(args.baseline)
        baseline_pairs = get_all_paragraphs(base_doc)
        baseline_texts = [p.text for p, _loc in baseline_pairs]
        check_indices = paragraphs_needing_check(target_texts, baseline_texts)
    else:
        check_indices = set(range(len(target_texts)))

    violations = []

    for p_idx in sorted(check_indices):
        paragraph, location = target_pairs[p_idx]
        for r_idx, run in enumerate(paragraph.runs):
            if not run.text.strip():
                continue
            problems = run_violations(run)
            if problems:
                snippet = run.text.strip()[:50]
                for prob in problems:
                    violations.append(
                        f"[{location}] paragraph {p_idx}, run {r_idx} ({snippet!r}): {prob}"
                    )

    if violations:
        print(f"FAIL: {len(violations)} violation(s) in {args.file}")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)
    else:
        print(f"OK: no formatting violations in {args.file}")
        sys.exit(0)


if __name__ == "__main__":
    main()
