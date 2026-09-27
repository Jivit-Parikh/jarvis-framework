#!/usr/bin/env python3
"""
docx_insert_answers.py

Library + CLI for worksheet-solver. Takes a source .docx and a JSON list
of {"question_match": "<text substring>" | <candidate index int>,
    "answer": "<answer text, may contain \\n for multiple lines/paragraphs>"}
and writes an output copy with each answer inserted as new paragraph(s)
directly under the matching question paragraph, wherever that paragraph
lives (document body, a table cell, or a cell inside a nested table).

Every inserted run is Times New Roman, 13pt, black (000000), not bold,
not italic, not underlined, no highlight. East-Asian font is also set
to Times New Roman so the font sticks in Word's font picker. No other
paragraph is touched; nothing is restructured.

CLI usage:
    python3 docx_insert_answers.py <source.docx> <answers.json> <output.docx>

answers.json:
[
  {"question_match": "1. What is classical conditioning", "answer": "..."},
  {"question_match": 4, "answer": "..."}
]

Matching (see find_target() below for the full algorithm):
Candidates are every paragraph in the document, walked in document order,
covering body paragraphs AND table-cell paragraphs (including paragraphs
inside a table nested inside another table's cell). Text is normalized
(casefold, whitespace collapsed, curly quotes/dashes unified to straight
ones) before comparing. A string question_match is resolved, in order:
  1. exact normalized match (unique),
  2. unique prefix match (one side is a prefix of the other),
  3. unique substring match (needle appears inside the candidate).
The first level with exactly one match wins. Zero matches at every level,
or more than one match at the level that would otherwise resolve it,
raises ValueError with a clear message listing every matching candidate
(location plus a text snippet) so the caller can make question_match more
specific. An int question_match is a 0-based index into the same ordered
candidate list (not into document.paragraphs, which excludes table cells).
"""
import sys
import json
import copy
import re
import unicodedata
import docx
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.table import Table


TNR = "Times New Roman"

_QUOTE_DASH_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "″": '"',
    "\u2013": "-", "\u2014": "-", "−": "-",
})


def _normalize(text):
    """Casefold, unify curly quotes/dashes to straight ones, collapse all
    whitespace runs to a single space, strip. Used for every comparison
    so 'Q1: What is...' matches 'q1:  what is...' etc."""
    if text is None:
        return ""
    text = unicodedata.normalize("NFKC", str(text))
    text = text.translate(_QUOTE_DASH_MAP)
    text = text.casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _style_run(run):
    run.font.name = TNR
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(0x00, 0x00, 0x00)
    run.font.bold = False
    run.font.italic = False
    run.font.underline = False
    run.font.highlight_color = None
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn('w:rFonts'))
    if rFonts is None:
        rFonts = rPr.makeelement(qn('w:rFonts'), {})
        rPr.append(rFonts)
    rFonts.set(qn('w:eastAsia'), TNR)
    rFonts.set(qn('w:ascii'), TNR)
    rFonts.set(qn('w:hAnsi'), TNR)


def insert_paragraph_after(paragraph, text):
    """Insert a new paragraph with `text` immediately after `paragraph`,
    styled TNR/13/black. Works the same whether `paragraph` lives in the
    document body or inside a table cell: addnext() is an XML-sibling
    insert, and a <w:tc> (table cell) holds its paragraphs the same way
    the document body does. Returns the new paragraph."""
    new_p = copy.deepcopy(paragraph._p)
    # strip existing runs/content from the clone, keep paragraph props minimal
    for child in list(new_p):
        if child.tag != qn('w:pPr'):
            new_p.remove(child)
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    # clear any inherited numbering/heading style effects by resetting to Normal
    doc_styles = paragraph.part.document.styles
    if 'Normal' in [s.name for s in doc_styles]:
        new_para.style = doc_styles['Normal']
    run = new_para.add_run(text)
    _style_run(run)
    return new_para


def _walk(container_elm, parent_obj, location):
    """Yield (Paragraph, location_str) pairs in document order, walking
    `container_elm`'s direct <w:p> and <w:tbl> children. Recurses into
    every table cell (and any table nested inside a cell), so this
    covers body paragraphs and table-cell paragraphs uniformly."""
    for child in container_elm.iterchildren():
        if child.tag.endswith('}p'):
            yield Paragraph(child, parent_obj), location
        elif child.tag.endswith('}tbl'):
            tbl = Table(child, parent_obj)
            for r_idx, row in enumerate(tbl.rows):
                for c_idx, cell in enumerate(row.cells):
                    cell_location = f"{location} > table row {r_idx + 1} col {c_idx + 1}"
                    yield from _walk(cell._tc, cell, cell_location)


def build_candidates(document):
    """Every paragraph in the document, in document order, body and table
    cells (including nested tables) alike. Each candidate is a dict with
    the live Paragraph object, its location description, raw text, and
    normalized text."""
    candidates = []
    for paragraph, location in _walk(document.element.body, document, "body"):
        text = paragraph.text
        candidates.append({
            "paragraph": paragraph,
            "location": location,
            "raw": text,
            "norm": _normalize(text),
        })
    return candidates


def _format_candidates(cands, limit=10):
    lines = []
    for c in cands[:limit]:
        snippet = c["raw"].strip()
        if len(snippet) > 80:
            snippet = snippet[:80] + "..."
        lines.append(f"  [{c['location']}] {snippet!r}")
    if len(cands) > limit:
        lines.append(f"  ... and {len(cands) - limit} more")
    return "\n".join(lines)


def find_target(question_match, candidates):
    """Resolve question_match (str or int) against `candidates` (as built
    by build_candidates()). Returns the matching candidate dict. Raises
    ValueError, listing every candidate at the deciding level, if the
    match is ambiguous (>1) or not found (0 at every level)."""
    if isinstance(question_match, int):
        if question_match < 0 or question_match >= len(candidates):
            raise ValueError(
                f"candidate index {question_match} out of range "
                f"(0..{len(candidates) - 1})"
            )
        return candidates[question_match]

    needle = _normalize(question_match)
    if not needle:
        raise ValueError("question_match is empty after normalization")

    levels = (
        ("exact", lambda c: c["norm"] == needle),
        ("unique prefix", lambda c: c["norm"] != "" and (
            c["norm"].startswith(needle) or needle.startswith(c["norm"])
        )),
        ("unique substring", lambda c: c["norm"] != "" and needle in c["norm"]),
    )
    for level_name, predicate in levels:
        matches = [c for c in candidates if predicate(c)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"question_match {question_match!r} is ambiguous at the "
                f"{level_name} level ({len(matches)} candidates):\n"
                f"{_format_candidates(matches)}\n"
                f"Make question_match more specific (a longer or more "
                f"exact snippet) to pick one."
            )

    raise ValueError(
        f"no paragraph found matching {question_match!r} "
        f"(checked exact, unique-prefix, and unique-substring, 0 candidates "
        f"at every level)"
    )


def insert_answers(source_path, answers, output_path):
    """
    answers: list of {"question_match": str|int, "answer": str}
    Writes output_path with answers inserted. Returns output_path.

    Every question_match is resolved against the same candidate snapshot
    taken before any insertion happens, then each answer is inserted at
    its resolved paragraph's live XML location. Because each resolved
    target is a direct object reference (not a position/index into a
    list that insertions would shift), order of insertion doesn't matter
    and nothing needs to be processed in reverse.
    """
    document = docx.Document(source_path)
    candidates = build_candidates(document)

    resolved = []
    for item in answers:
        target = find_target(item["question_match"], candidates)
        resolved.append((target["paragraph"], item["answer"]))

    for paragraph, answer_text in resolved:
        lines = str(answer_text).split("\n")
        prev = paragraph
        for line in lines:
            prev = insert_paragraph_after(prev, line)

    document.save(output_path)
    return output_path


def main():
    if len(sys.argv) != 4:
        print("usage: docx_insert_answers.py <source.docx> <answers.json> <output.docx>", file=sys.stderr)
        sys.exit(2)
    source_path, answers_json_path, output_path = sys.argv[1:4]
    with open(answers_json_path, "r", encoding="utf-8") as f:
        answers = json.load(f)
    insert_answers(source_path, answers, output_path)
    print(f"OK: wrote {output_path}")


if __name__ == "__main__":
    main()
