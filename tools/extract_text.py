#!/usr/bin/env python3
"""
extract_text.py <file>

Uniform text extraction for pptx, pdf, docx, md/txt. Prints JSON to stdout:
{
  "source": "<path>",
  "type": "pptx"|"pdf"|"docx"|"text",
  "sections": [ {"index": int, "label": str, "text": str} , ... ],
  "word_count": int
}

pptx: one section per slide (slide text + notes, notes appended after "[Notes]").
pdf: one section per page (pdfplumber).
docx: one section for body paragraphs, one per table (tables rendered as
      pipe-separated rows) -- indices follow document order.
md/txt: single section with the raw text.
"""
import sys
import json
import os


def extract_pptx(path):
    from pptx import Presentation
    prs = Presentation(path)
    sections = []
    for i, slide in enumerate(prs.slides):
        parts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    parts.append(t)
            if shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        text = "\n".join(parts)
        if notes:
            text += "\n[Notes]\n" + notes
        sections.append({"index": i, "label": f"Slide {i + 1}", "text": text})
    return sections


def extract_pdf(path):
    import pdfplumber
    sections = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            sections.append({"index": i, "label": f"Page {i + 1}", "text": text})
    return sections


def extract_docx(path):
    import docx
    d = docx.Document(path)
    sections = []
    body_parts = []
    idx = 0
    # Walk document body in order (paragraphs and tables interleaved)
    body = d.element.body
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    for child in body.iterchildren():
        if child.tag.endswith('}p'):
            p = Paragraph(child, d)
            if p.text.strip():
                body_parts.append(p.text)
        elif child.tag.endswith('}tbl'):
            if body_parts:
                sections.append({"index": idx, "label": "Paragraphs", "text": "\n".join(body_parts)})
                idx += 1
                body_parts = []
            tbl = Table(child, d)
            rows = [" | ".join(c.text for c in row.cells) for row in tbl.rows]
            sections.append({"index": idx, "label": "Table", "text": "\n".join(rows)})
            idx += 1
    if body_parts:
        sections.append({"index": idx, "label": "Paragraphs", "text": "\n".join(body_parts)})
    return sections


def extract_text_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    return [{"index": 0, "label": os.path.basename(path), "text": text}]


def main():
    if len(sys.argv) != 2:
        print("usage: extract_text.py <file>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pptx":
        ftype = "pptx"
        sections = extract_pptx(path)
    elif ext == ".pdf":
        ftype = "pdf"
        sections = extract_pdf(path)
    elif ext == ".docx":
        ftype = "docx"
        sections = extract_docx(path)
    elif ext in (".md", ".txt"):
        ftype = "text"
        sections = extract_text_file(path)
    else:
        print(f"unsupported file type: {ext}", file=sys.stderr)
        sys.exit(2)

    word_count = sum(len(s["text"].split()) for s in sections)
    out = {
        "source": path,
        "type": ftype,
        "sections": sections,
        "word_count": word_count,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
