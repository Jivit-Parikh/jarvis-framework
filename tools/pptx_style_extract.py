#!/usr/bin/env python3
"""
pptx_style_extract.py [vault_root]

Scans every .pptx under <vault_root>/ATLAS WORK/ (default vault_root is
the JARVIS_VAULT_ROOT environment variable, or ~/vault), excluding any
file with "QA Copy" in its
name and exact duplicates (by file hash), and writes a style-token
summary to <vault_root>/JARVIS CONTROL ROOM/Data/presentation-style.json.

Captures: theme fonts (major/minor), most-used fonts/sizes by role
(title vs body, inferred from placeholder type and font size rank),
a color palette (theme colors plus actual run/fill colors ranked by
frequency), slide dimensions, layout names used, median slide count,
typical opening/closing slide patterns (title of first/last slide's
layout name), and a per-deck summary.

Run standalone: python3 pptx_style_extract.py
"""
import sys
import os
import json
import hashlib
import statistics
from collections import Counter

VAULT_DEFAULT = os.path.expanduser(os.environ.get("JARVIS_VAULT_ROOT", "~/vault"))


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def find_decks(vault_root):
    atlas_work = os.path.join(vault_root, "ATLAS WORK")
    decks = []
    seen_hashes = set()
    for root, _dirs, files in os.walk(atlas_work):
        for fn in files:
            if not fn.lower().endswith(".pptx"):
                continue
            if "QA Copy" in fn:
                continue
            if fn.startswith("~$"):
                continue
            full = os.path.join(root, fn)
            try:
                h = file_hash(full)
            except OSError:
                continue
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            decks.append(full)
    return decks


def rgb_str(color_format):
    try:
        if color_format.type is not None and color_format.rgb is not None:
            return str(color_format.rgb)
    except Exception:
        pass
    return None


def extract_deck(path):
    from pptx import Presentation
    from pptx.util import Emu

    prs = Presentation(path)
    info = {
        "path": path,
        "slide_count": len(prs.slides.__iter__.__self__._sldIdLst) if False else len(prs.slides._sldIdLst),
        "width_emu": prs.slide_width,
        "height_emu": prs.slide_height,
        "layouts_used": [],
        "fonts": Counter(),
        "title_fonts": Counter(),
        "body_fonts": Counter(),
        "sizes": Counter(),
        "title_sizes": Counter(),
        "body_sizes": Counter(),
        "colors": Counter(),
        "first_layout": None,
        "last_layout": None,
    }

    slides = list(prs.slides)
    info["slide_count"] = len(slides)
    if slides:
        info["first_layout"] = slides[0].slide_layout.name
        info["last_layout"] = slides[-1].slide_layout.name

    for slide in slides:
        info["layouts_used"].append(slide.slide_layout.name)
        for shape in slide.shapes:
            is_title = False
            try:
                is_title = shape.placeholder_format is not None and shape.placeholder_format.type in (13, 1, 0)
            except Exception:
                is_title = False
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    fname = run.font.name
                    fsize = run.font.size.pt if run.font.size else None
                    if fname:
                        info["fonts"][fname] += 1
                        if is_title:
                            info["title_fonts"][fname] += 1
                        else:
                            info["body_fonts"][fname] += 1
                    if fsize:
                        info["sizes"][fsize] += 1
                        if is_title:
                            info["title_sizes"][fsize] += 1
                        else:
                            info["body_sizes"][fsize] += 1
                    c = rgb_str(run.font.color)
                    if c:
                        info["colors"][c] += 1
            # shape fill color
            try:
                if shape.fill.type is not None:
                    c = rgb_str(shape.fill.fore_color)
                    if c:
                        info["colors"][c] += 1
            except Exception:
                pass

    # theme fonts
    major_font = None
    minor_font = None
    try:
        theme_elm = prs.slide_masters[0].element.getroottree()
    except Exception:
        pass
    try:
        master = prs.slide_masters[0]
        theme = master.element.getroottree().getroot()
        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        major = theme.find(".//a:majorFont/a:latin", ns)
        minor = theme.find(".//a:minorFont/a:latin", ns)
        if major is not None:
            major_font = major.get("typeface")
        if minor is not None:
            minor_font = minor.get("typeface")
    except Exception:
        pass

    info["theme_major_font"] = major_font
    info["theme_minor_font"] = minor_font
    return info


def main():
    vault_root = sys.argv[1] if len(sys.argv) > 1 else VAULT_DEFAULT
    decks = find_decks(vault_root)

    all_fonts = Counter()
    all_title_fonts = Counter()
    all_body_fonts = Counter()
    all_sizes = Counter()
    all_title_sizes = Counter()
    all_body_sizes = Counter()
    all_colors = Counter()
    all_layouts = Counter()
    slide_counts = []
    dims = Counter()
    opening_layouts = Counter()
    closing_layouts = Counter()
    per_deck = []

    for path in decks:
        try:
            info = extract_deck(path)
        except Exception as e:
            per_deck.append({"path": path, "error": str(e)})
            continue

        all_fonts.update(info["fonts"])
        all_title_fonts.update(info["title_fonts"])
        all_body_fonts.update(info["body_fonts"])
        all_sizes.update(info["sizes"])
        all_title_sizes.update(info["title_sizes"])
        all_body_sizes.update(info["body_sizes"])
        all_colors.update(info["colors"])
        all_layouts.update(info["layouts_used"])
        slide_counts.append(info["slide_count"])
        dims[(info["width_emu"], info["height_emu"])] += 1
        if info["first_layout"]:
            opening_layouts[info["first_layout"]] += 1
        if info["last_layout"]:
            closing_layouts[info["last_layout"]] += 1

        per_deck.append({
            "path": info["path"],
            "slide_count": info["slide_count"],
            "theme_major_font": info["theme_major_font"],
            "theme_minor_font": info["theme_minor_font"],
            "top_fonts": info["fonts"].most_common(3),
            "top_colors": info["colors"].most_common(5),
            "layouts_used": sorted(set(info["layouts_used"])),
        })

    top_dim = dims.most_common(1)
    result = {
        "generated_from_deck_count": len([d for d in per_deck if "error" not in d]),
        "decks_scanned": [d["path"] for d in per_deck],
        "slide_dimensions_emu": {
            "most_common": {"width_emu": top_dim[0][0][0], "height_emu": top_dim[0][0][1]} if top_dim else None,
            "all": [{"width_emu": w, "height_emu": h, "count": n} for (w, h), n in dims.most_common()],
        },
        "fonts": {
            "most_used_overall": all_fonts.most_common(10),
            "most_used_title": all_title_fonts.most_common(5),
            "most_used_body": all_body_fonts.most_common(5),
        },
        "sizes_pt": {
            "most_used_overall": all_sizes.most_common(10),
            "most_used_title": all_title_sizes.most_common(5),
            "most_used_body": all_body_sizes.most_common(5),
        },
        "color_palette_ranked": all_colors.most_common(15),
        "layout_names_used": all_layouts.most_common(),
        "median_slide_count": statistics.median(slide_counts) if slide_counts else None,
        "opening_slide_layouts": opening_layouts.most_common(),
        "closing_slide_layouts": closing_layouts.most_common(),
        "per_deck_summary": per_deck,
    }

    out_path = os.path.join(vault_root, "JARVIS CONTROL ROOM", "Data", "presentation-style.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"OK: scanned {len(decks)} deck(s), wrote {out_path}")


if __name__ == "__main__":
    main()
