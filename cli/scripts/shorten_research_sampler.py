"""Make matching 23-page excerpts of the original sampler and its verified v5 run.

Run from the repository virtual environment. Existing figures are copied as native
PDF content; this editorial operation makes no new AI calls or chart corrections.
"""

from copy import copy
from hashlib import sha256
import json
from math import ceil
from pathlib import Path

from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import build_research_sampler as layout


# Keep distinct subjects and both successful and unresolved processing examples.
CASE_IDS = (1, 3, 6, 7, 9, 11, 14, 16, 20, 21, 25, 28, 32, 33, 34, 36, 38, 41, 42, 43)
CASES = [layout.CASES[number - 1] for number in CASE_IDS]
SOURCES = [s for s in layout.SPEC["sources"] if s["id"] in {c["source"] for c in CASES}]
TOTAL = len(CASES) + 3
OUT = layout.ROOT / "output/pdf"
PREVIEWS = layout.ROOT / "tmp/pdfs/research-sampler-short"
INPUTS = {
    "Original": OUT / "Research_Excerpt_Sampler.pdf",
    "Processed": layout.ROOT / "cli/output-research-sampler-v5/improved.pdf",
}


def number(c, width, page, clear_height=20):
    c.setFillColorRGB(1, 1, 1)
    c.rect(width - 110, 6, 86, clear_height, fill=1, stroke=0)
    c.setFillColor(layout.MUTED)
    c.setFont("Arial", 7.2)
    c.drawRightString(width - 32, 15, f"{page:02d} / {TOTAL}")


def cover(kind, preview):
    width, height = A4
    c, stream = layout.make_canvas(A4)
    layout.text(c, "COLOR-BLIND AI DOCUMENT ASSISTANT", 40, height - 48, 9, True, layout.BLUE)
    layout.text(c, "Research sampler", 40, height - 108, 35, True)
    layout.text(c, "Short edition", 40, height - 151, 31, True)
    label = "Original colors" if kind == "Original" else "Existing corrections - reader review pending"
    layout.text(c, label, 42, height - 181, 11, color=layout.MUTED)
    c.setFillColor(layout.PALE)
    c.roundRect(40, height - 254, width - 80, 45, 5, fill=1, stroke=0)
    for x, value in [(56, f"{len(SOURCES)} SOURCES"), (220, f"{len(CASES)} EXAMPLES"), (416, f"{TOTAL} PAGES")]:
        layout.text(c, value, x, height - 237, 11, True)
    x, y, scale = layout.fit_rect(preview.width, preview.height, (40, 265, width - 80, 270))
    c.drawImage(ImageReader(preview), x, y, preview.width * scale, preview.height * scale)
    layout.text(c, "Preview: Caudron (2004), 21 spectra. Full example on page 3.", 42, 246, 8, color=layout.MUTED)
    layout.paragraph(c, "Wavelength spectra, titration and dilution, drosophila and SVT, dense official charts, and synthetic test controls.", 42, 211, width - 84, 11, 16)
    explanation = (
        "Uses the accepted edits from the existing v5 run. No new AI processing was performed. Some figures and labels still need review."
        if kind == "Processed" else
        "Published colors and native PDF graphics are preserved. Each example keeps its reading task and source reference."
    )
    layout.paragraph(c, explanation, 42, 151, width - 84, 10, 15)
    layout.text(c, f"Clickable contents on page 2. Source index on page {TOTAL}.", 42, 87, 9, color=layout.MUTED)
    layout.text(c, "Shortened from the 48-page collection | 24 October 2026", 42, 57, 8, color=layout.MUTED)
    number(c, width, 1)
    return layout.finish(c, stream)


def contents():
    width, height = A4
    c, stream = layout.make_canvas(A4)
    layout.text(c, "COLLECTION GUIDE", 32, height - 35, 8, True, layout.BLUE)
    layout.text(c, "Contents", 32, height - 68, 25, True)
    layout.text(c, f"Click a title to open an example. Source IDs point to page {TOTAL}.", 32, height - 91, 9, color=layout.MUTED)
    targets = []
    for idx, case in enumerate(CASES):
        y = height - 132 - idx * 28
        layout.text(c, f"{idx + 1:02d}", 32, y, 9, True, layout.BLUE)
        layout.fit_text(c, case["title"], 60, y, width - 164, 10)
        layout.text(c, case["source"], width - 91, y, 8, color=layout.MUTED)
        layout.text(c, str(idx + 3), width - 47, y, 10, True)
        targets.append(((57, y - 5, width - 32, y + 12), idx + 2))
        c.setStrokeColorRGB(.89, .91, .93)
        c.line(32, y - 12, width - 32, y - 12)
    layout.paragraph(c, "The collection includes unresolved examples as well as successful corrections. Case numbers and PDF page numbers match in both editions.", 32, 103, width - 64, 9, 12, color=layout.MUTED)
    number(c, width, 2)
    return layout.finish(c, stream), targets


def references():
    width, height = A4
    c, stream = layout.make_canvas(A4)
    layout.text(c, "ATTRIBUTION AND TRACEABILITY", 32, height - 35, 8, True, layout.BLUE)
    layout.text(c, "Source index", 32, height - 67, 25, True)
    layout.text(c, "Links open the original publications. Excerpt locations remain on the example pages.", 32, height - 88, 8.1, color=layout.MUTED)
    for idx, source in enumerate(SOURCES):
        y = height - 121 - idx * 36
        pages = [str(i + 3) for i, case in enumerate(CASES) if case["source"] == source["id"]]
        layout.fit_text(c, f"{source['id']}  {source['title']}", 32, y, width - 64, 9.2, True)
        layout.fit_text(c, source["credit"], 32, y - 11, width - 64, 8.2, color=layout.MUTED)
        domain = layout.urlparse(source["url"]).netloc or "Local repository document"
        layout.text(c, f"{domain}  |  Sample pages: {', '.join(pages)}", 32, y - 22, 7.8, color=layout.BLUE)
        if source["url"]:
            c.linkURL(source["url"], (32, y - 26, width - 32, y + 10), relative=0)
    number(c, width, TOTAL)
    return layout.finish(c, stream)


def main():
    assert len(set(CASE_IDS)) == len(CASE_IDS) == 20 and TOTAL == 23
    assert len(SOURCES) <= 19, "Source index would overflow"
    for font, file in [("Arial", "arial.ttf"), ("ArialBold", "arialbd.ttf")]:
        pdfmetrics.registerFont(TTFont(font, str(Path("C:/Windows/Fonts") / file)))
    input_hashes = {kind: sha256(path.read_bytes()).hexdigest() for kind, path in INPUTS.items()}
    evidence = {"page_count": TOTAL, "sources": SOURCES, "input_sha256": input_hashes,
                "cases": [{**case, "sample_page": i + 3, "full_sample_page": old + 3}
                          for i, (old, case) in enumerate(zip(CASE_IDS, CASES))], "outputs": {}}
    for kind, source in INPUTS.items():
        reader = PdfReader(source)
        original = pdfium.PdfDocument(str(source))
        assert len(reader.pages) == len(original) == 48
        preview = original[3].render(scale=1.2).to_pil().convert("RGB")
        preview = preview.crop((38, 126, preview.width - 38, preview.height - 139))
        writer = PdfWriter()
        writer.add_page(cover(kind, preview))
        page, targets = contents()
        writer.add_page(page)
        for idx, (case_id, case) in enumerate(zip(CASE_IDS, CASES)):
            page = copy(reader.pages[case_id + 2])
            width, height = float(page.mediabox.width), float(page.mediabox.height)
            c, stream = layout.make_canvas((width, height))
            if not case.get("passthrough"):
                c.setFillColorRGB(1, 1, 1)
                c.rect(30, height - 41, width - 60, 25, fill=1, stroke=0)
                layout.text(c, f"{case['section'].upper()} / CASE {idx + 1:02d}", 32, height - 30, 8.5, True, layout.BLUE)
            number(c, width, idx + 3, clear_height=28 if case.get("passthrough") else 20)
            page.merge_page(layout.finish(c, stream))
            writer.add_page(page)
            writer.add_outline_item(f"{idx + 1:02d} - {case['title']}", idx + 2)
        writer.add_page(references())
        writer.add_outline_item("Source index", TOTAL - 1)
        for rectangle, target in targets:
            writer.add_annotation(1, Link(rect=rectangle, target_page_index=target))
        writer.add_metadata({"/Title": f"Research sampler - Short edition - {kind}",
                             "/Subject": "20 selected examples; source links and matching page numbers"})
        target = OUT / f"Research_Sampler_Short_{kind}.pdf"
        writer.write(target)
        result = PdfReader(target)
        assert len(result.pages) == TOTAL and len(result.outline) == 21
        page_refs = [p.indirect_reference for p in result.pages]
        assert [page_refs.index(a.get_object()["/Dest"][0]) for a in result.pages[1]["/Annots"]] == list(range(2, 22))
        assert all(result.get_destination_page_number(d) == i + 2 for i, d in enumerate(result.outline[:-1]))
        assert result.get_destination_page_number(result.outline[-1]) == TOTAL - 1
        rendered = pdfium.PdfDocument(str(target))
        directory = PREVIEWS / kind.lower()
        directory.mkdir(parents=True, exist_ok=True)
        images = []
        for idx in range(TOTAL):
            image = rendered[idx].render(scale=1.2).to_pil().convert("RGB")
            image.save(directory / f"page-{idx + 1:02d}.png")
            images.append(image)
            if 2 <= idx < TOTAL - 1:
                old = original[CASE_IDS[idx - 2] + 2].render(scale=1.2).to_pil().convert("RGB")
                assert image.size == old.size
                body = (0, ceil(44 * 1.2), image.width, image.height - ceil(30 * 1.2))
                assert image.crop(body).tobytes() == old.crop(body).tobytes(), (kind, idx + 1)
                old_links = [a.get_object().get("/A", {}).get("/URI") for a in reader.pages[CASE_IDS[idx - 2] + 2].get("/Annots", [])]
                new_links = [a.get_object().get("/A", {}).get("/URI") for a in result.pages[idx].get("/Annots", [])]
                assert old_links == new_links, (kind, idx + 1, "source links")
        for offset in range(0, TOTAL, 12):
            sheet = Image.new("RGB", (1200, 1140), "#d9dfe5")
            draw = ImageDraw.Draw(sheet)
            for idx, image in enumerate(images[offset:offset + 12]):
                thumb = image.copy()
                thumb.thumbnail((290, 350))
                x, y = (idx % 4) * 300, (idx // 4) * 380
                draw.text((x + 8, y + 5), f"PAGE {offset + idx + 1:02d}", fill="black")
                sheet.paste(thumb, (x + (300 - thumb.width) // 2, y + 24))
            sheet.save(directory / f"overview-{offset // 12 + 1}.png")
        rendered.close()
        original.close()
        evidence["outputs"][kind] = {"path": str(target), "bytes": target.stat().st_size,
                                    "sha256": sha256(target.read_bytes()).hexdigest(),
                                    "figure_renders_preserved": True, "navigation_verified": True}
        print(json.dumps(evidence["outputs"][kind]), flush=True)
    assert input_hashes == {kind: sha256(path.read_bytes()).hexdigest() for kind, path in INPUTS.items()}
    (OUT / "Research_Sampler_Short.manifest.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
