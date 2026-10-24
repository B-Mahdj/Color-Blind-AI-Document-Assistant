"""Build the research excerpt PDF from the source files collected in this chat.

Run from the repository's existing virtual environment. Source paths and original
URLs are in research_sampler_sources.json; downloaded originals stay unmodified.
"""

from collections import defaultdict
from copy import copy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.annotations import Link
from pypdf.generic import NameObject, RectangleObject
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads(Path(__file__).with_name("research_sampler_sources.json").read_text(encoding="utf-8"))
SOURCES = {s["id"]: s for s in SPEC["sources"]}
CASES = SPEC["cases"]
OUT = ROOT / "output/pdf"
QA = ROOT / "tmp/pdfs/compilation/final-preview"
TARGET = OUT / "Research_Excerpt_Sampler.pdf"
INK = colors.HexColor("#142537")
MUTED = colors.HexColor("#526475")
BLUE = colors.HexColor("#175E9B")
PALE = colors.HexColor("#F0F4F7")
MARGIN = 32
READERS = {}


def reader(file):
    if file not in READERS:
        READERS[file] = PdfReader(ROOT / file)
    return READERS[file]


def text(c, value, x, y, size=10, bold=False, color=INK):
    c.setFillColor(color)
    c.setFont("ArialBold" if bold else "Arial", size)
    c.drawString(x, y, value)


def lines(value, width, size=10, bold=False):
    font = "ArialBold" if bold else "Arial"
    result, line = [], ""
    for word in value.split():
        candidate = (line + " " + word).strip()
        if line and pdfmetrics.stringWidth(candidate, font, size) > width:
            result.append(line)
            line = word
        else:
            line = candidate
    if line:
        result.append(line)
    return result


def paragraph(c, value, x, y, width, size=10, leading=14, bold=False, color=INK):
    for line in lines(value, width, size, bold):
        text(c, line, x, y, size, bold, color)
        y -= leading
    return y


def fit_text(c, value, x, y, width, size=9, bold=False, color=INK):
    font = "ArialBold" if bold else "Arial"
    measured = pdfmetrics.stringWidth(value, font, size)
    text(c, value, x, y, min(size, size * width / max(measured, 1)), bold, color)


def make_canvas(size):
    stream = BytesIO()
    c = canvas.Canvas(stream, pagesize=size, pageCompression=1)
    c.setTitle(SPEC["title"])
    return c, stream


def finish(c, stream):
    c.save()
    stream.seek(0)
    return PdfReader(stream).pages[0]


def footer(c, width, number):
    c.setStrokeColor(colors.HexColor("#D8E0E7"))
    c.line(MARGIN, 28, width - MARGIN, 28)
    text(c, "COLOR ACCESSIBILITY / RESEARCH SAMPLE", MARGIN, 15, 7.2, color=MUTED)
    c.setFont("Arial", 7.2)
    c.drawRightString(width - MARGIN, 15, f"{number:02d} / 48")


def pdf_crop(panel, source):
    page = copy(reader(panel.get("file", source["file"])).pages[panel["page"] - 1])
    if page.rotation:
        page.transfer_rotation_to_content()
    if panel.get("rotate"):
        page.rotate(panel["rotate"])
        page.transfer_rotation_to_content()
    x0, y0, x1, y1 = panel["crop"]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    # Coordinates refer to the visible source page, after any requested rotation.
    box = page.cropbox
    left = float(box.left) + float(box.width) * x0
    right = float(box.left) + float(box.width) * x1
    bottom = float(box.top) - float(box.height) * y1
    top = float(box.top) - float(box.height) * y0
    page.cropbox = RectangleObject((left, bottom, right, top))
    page.trimbox = RectangleObject((left, bottom, right, top))
    # Source links use page coordinates and must not remain over an unrelated crop.
    page.pop(NameObject("/Annots"), None)
    return page, (left, bottom, right, top)


def image_crop(panel, source):
    with Image.open(ROOT / panel.get("file", source["file"])) as image:
        x0, y0, x1, y1 = panel["crop"]
        crop = image.crop((round(x0 * image.width), round(y0 * image.height),
                           round(x1 * image.width), round(y1 * image.height)))
        if crop.mode == "RGBA":
            background = Image.new("RGB", crop.size, "white")
            background.paste(crop, mask=crop.getchannel("A"))
            return background
        return crop.convert("RGB")


def fit_rect(width, height, region):
    x, y, available_w, available_h = region
    scale = min(available_w / width, available_h / height)
    return x + (available_w - width * scale) / 2, y + (available_h - height * scale) / 2, scale


def build_case(case, number):
    source = SOURCES[case["source"]]
    if case.get("passthrough"):
        return copy(reader(source["file"]).pages[case["panels"][0]["page"] - 1])
    size = landscape(A4) if case.get("orientation") == "landscape" else A4
    width, height = size
    c, stream = make_canvas(size)
    text(c, f"{case['section'].upper()} / CASE {number - 3:02d}", MARGIN, height - 30, 8.5, True, BLUE)
    title_y = paragraph(c, case["title"], MARGIN, height - 58, width - 2 * MARGIN,
                        size=21, leading=24, bold=True)
    text(c, case["locator"], MARGIN, title_y - 1, 9, color=MUTED)
    plot_top = title_y - 23
    plot_bottom = 134 if case.get("note") else 116
    weights = case.get("weights", [1] * len(case["panels"]))
    gap = 20
    room = width - 2 * MARGIN - gap * (len(weights) - 1)
    cursor = MARGIN
    merges = []
    for panel, weight in zip(case["panels"], weights):
        panel_w = room * weight / sum(weights)
        label_space = 18 if panel.get("label") else 0
        if label_space:
            text(c, panel["label"], cursor, plot_top - 9, 9, True, MUTED)
        region = (cursor, plot_bottom, panel_w, plot_top - plot_bottom - label_space)
        assert region[3] > 120
        if panel["page"] is not None:
            page, (left, bottom, right, top) = pdf_crop(panel, source)
            x, y, scale = fit_rect(right - left, top - bottom, region)
            merges.append((page, Transformation().scale(scale).translate(x - left * scale, y - bottom * scale)))
        else:
            image = image_crop(panel, source)
            x, y, scale = fit_rect(image.width, image.height, region)
            c.drawImage(ImageReader(image), x, y, image.width * scale, image.height * scale)
        cursor += panel_w + gap
    if case.get("note"):
        paragraph(c, case["note"], MARGIN, 126, width - 2 * MARGIN, 8, 10, color=MUTED)
    c.setFillColor(PALE)
    c.roundRect(MARGIN, 61, width - 2 * MARGIN, 43, 4, fill=1, stroke=0)
    text(c, "READING TASK", MARGIN + 11, 91, 7.5, True, BLUE)
    task_lines = lines(case["task"], width - 2 * MARGIN - 22, 9.2)
    assert len(task_lines) <= 2, case["title"]
    paragraph(c, case["task"], MARGIN + 11, 77, width - 2 * MARGIN - 22, 9.2, 11)
    source_label = f"{source['id']}  |  {source['credit']}"
    fit_text(c, source_label, MARGIN, 46, width - 2 * MARGIN - 100, 8, color=MUTED)
    if source["url"]:
        text(c, "Open original source", width - MARGIN - 90, 46, 8, color=BLUE)
        c.linkURL(source["url"], (width - MARGIN - 94, 42, width - MARGIN, 55), relative=0)
    footer(c, width, number)
    page = finish(c, stream)
    for cropped, transform in merges:
        page.merge_transformed_page(cropped, transform, expand=False)
    return page


def cover():
    width, height = A4
    c, stream = make_canvas(A4)
    text(c, "COLOR-BLIND AI DOCUMENT ASSISTANT", 40, height - 48, 9, True, BLUE)
    text(c, "Research", 40, height - 105, 42, True)
    text(c, "sample document", 40, height - 154, 38, True)
    paragraph(c, "Original figures gathered throughout this chat, assembled as a practical color-accessibility test document.",
              42, height - 190, width - 84, 12, 17, color=MUTED)
    c.setFillColor(PALE)
    c.roundRect(40, height - 287, width - 80, 46, 5, fill=1, stroke=0)
    text(c, "37 SOURCES", 56, height - 268, 12, True)
    text(c, "43 EXAMPLE PAGES", 220, height - 268, 12, True)
    text(c, "48 PAGES TOTAL", 416, height - 268, 11, True)
    d = pdfium.PdfDocument(str(ROOT / SOURCES["S01"]["file"]))
    im = d[73].render(scale=1.4).to_pil()
    im = im.crop((int(im.width * .12), int(im.height * .06), int(im.width * .875), int(im.height * .405)))
    x, y, scale = fit_rect(im.width, im.height, (40, 245, width - 80, 280))
    c.drawImage(ImageReader(im), x, y, im.width * scale, im.height * scale)
    text(c, "Preview: Caudron (2004), Figure 35 - 21 spectra. Full case on page 4.", 42, 231, 8, color=MUTED)
    paragraph(c, "The published colors, legends and line styles are retained. Excerpts are cropped, resized or rotated for readability. Image-based sources remain images; vector PDF graphics are kept where available.",
              42, 192, width - 84, 10, 14)
    paragraph(c, "Use the reading tasks to compare an original with an adapted version. Source membership is not a claim that every figure fails for every reader. The published palette-comparison figure is labelled as a reference.",
              42, 133, width - 84, 10, 14)
    text(c, "Compiled 24 October 2026 | Includes the original demo and synthetic controls", 42, 58, 8.5, color=MUTED)
    footer(c, width, 1)
    return finish(c, stream)


def contents(part):
    width, height = A4
    c, stream = make_canvas(A4)
    text(c, "COLLECTION GUIDE", MARGIN, height - 35, 8, True, BLUE)
    text(c, f"Contents {part + 1}/2", MARGIN, height - 68, 25, True)
    text(c, "Click a title to jump to the example. Source IDs point to pages 47-48.", MARGIN, height - 91, 9, color=MUTED)
    chunk = list(enumerate(CASES))[part * 22:(part + 1) * 22]
    targets = []
    y = height - 132
    for idx, case in chunk:
        text(c, f"{idx + 1:02d}", MARGIN, y, 9, True, BLUE)
        fit_text(c, case["title"], MARGIN + 28, y, width - 2 * MARGIN - 100, 10)
        text(c, case["source"], width - 91, y, 8, color=MUTED)
        text(c, str(idx + 4), width - 47, y, 10, True)
        targets.append(((MARGIN + 25, y - 5, width - MARGIN, y + 12), idx + 3))
        c.setStrokeColor(colors.HexColor("#E3E8ED"))
        c.line(MARGIN, y - 12, width - MARGIN, y - 12)
        y -= 28
    if part == 1:
        paragraph(c, "The last three examples retain their original page layout and content streams. Real-world excerpts may contain clipping, transparency or images that a PDF parser does not yet support; visual matching alone does not establish recoloring support.",
                  MARGIN, 91, width - 2 * MARGIN, 9, 12, color=MUTED)
    footer(c, width, part + 2)
    return finish(c, stream), targets


def references(part):
    width, height = A4
    c, stream = make_canvas(A4)
    text(c, "ATTRIBUTION AND TRACEABILITY", MARGIN, height - 35, 8, True, BLUE)
    text(c, f"Source index {part + 1}/2", MARGIN, height - 67, 25, True)
    text(c, "Each link opens the original publication or teaching page. Excerpt locations appear on the case pages.",
         MARGIN, height - 88, 8.1, color=MUTED)
    used = defaultdict(list)
    for idx, case in enumerate(CASES):
        used[case["source"]].append(str(idx + 4))
    chunk = SPEC["sources"][part * 19:(part + 1) * 19]
    y = height - 121
    for source in chunk:
        fit_text(c, f"{source['id']}  {source['title']}", MARGIN, y, width - 2 * MARGIN, 9.2, True)
        fit_text(c, source["credit"], MARGIN, y - 11, width - 2 * MARGIN, 8.2, color=MUTED)
        link_label = urlparse(source["url"]).netloc or "Local repository document"
        text(c, f"{link_label}  |  Sample pages: {', '.join(used[source['id']])}", MARGIN, y - 22, 7.8, color=BLUE)
        if source["url"]:
            c.linkURL(source["url"], (MARGIN, y - 26, width - MARGIN, y + 10), relative=0)
        y -= 36
    if part == 1:
        text(c, "Full URLs, file hashes, crop coordinates and source notes are also recorded in the companion manifest.", MARGIN, 49, 7.5, color=MUTED)
    footer(c, width, 47 + part)
    return finish(c, stream)


def main():
    assert len(CASES) == 43 and len(SOURCES) == 37
    assert {c["source"] for c in CASES} == set(SOURCES), "A collected source has no excerpt"
    for font, file in [("Arial", "arial.ttf"), ("ArialBold", "arialbd.ttf")]:
        pdfmetrics.registerFont(TTFont(font, str(Path("C:/Windows/Fonts") / file)))
    OUT.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    for source in SOURCES.values():
        path = ROOT / source["file"]
        assert path.is_file(), f"Missing source: {source['file']} ({source['url']})"
        source["sha256"] = sha256(path.read_bytes()).hexdigest()
    writer = PdfWriter()
    writer.add_page(cover())
    for part in range(2):
        page, targets = contents(part)
        writer.add_page(page)
        for rectangle, target in targets:
            writer.add_annotation(part + 1, Link(rect=rectangle, target_page_index=target))
    for idx, case in enumerate(CASES):
        writer.add_page(build_case(case, idx + 4))
        writer.add_outline_item(f"{idx + 1:02d} - {case['title']}", idx + 3)
        print(f"Assembled {idx + 1:02d}/{len(CASES)}: {case['title']}", flush=True)
    for part in range(2):
        writer.add_page(references(part))
    writer.add_outline_item("Source index", 46)
    writer.add_metadata({"/Title": SPEC["title"], "/Author": "Research collection assembled for the user",
                         "/Subject": "Original-color chart excerpts for protanopia accessibility testing"})
    assert len(writer.pages) == 48 and len(writer.pages) <= 50
    with TARGET.open("wb") as output:
        writer.write(output)
    assert TARGET.stat().st_size <= 50 * 1024 * 1024, "PDF exceeds the CLI's 50 MB limit"
    check = PdfReader(TARGET)
    for idx, case in enumerate(CASES):
        if case.get("passthrough"):
            original = reader(SOURCES[case["source"]]["file"]).pages[case["panels"][0]["page"] - 1]
            assert check.pages[idx + 3].get_contents().get_data() == original.get_contents().get_data()
    manifest = {**SPEC, "output": str(TARGET.relative_to(ROOT)), "page_count": len(check.pages),
                "sources": list(SOURCES.values()), "cases": [{**c, "sample_page": i + 4} for i, c in enumerate(CASES)]}
    (OUT / "Research_Excerpt_Sampler.manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    doc = pdfium.PdfDocument(str(TARGET))
    previews = []
    for idx in range(len(doc)):
        image = doc[idx].render(scale=1.2).to_pil().convert("RGB")
        image.save(QA / f"page-{idx + 1:02d}.png")
        previews.append(image)
        if (idx + 1) % 12 == 0:
            print(f"Rendered {idx + 1}/{len(doc)} pages", flush=True)
    for offset in range(0, len(previews), 12):
        sheet = Image.new("RGB", (1200, 1140), "#d9dfe5")
        draw = ImageDraw.Draw(sheet)
        for i, image in enumerate(previews[offset:offset + 12]):
            thumb = image.copy()
            thumb.thumbnail((290, 350))
            x, y = (i % 4) * 300, (i // 4) * 380
            draw.text((x + 8, y + 5), f"PAGE {offset + i + 1:02d}", fill="black")
            sheet.paste(thumb, (x + (300 - thumb.width) // 2, y + 24))
        sheet.save(QA / f"overview-{offset // 12 + 1}.png")
    print(json.dumps({"pdf": str(TARGET), "pages": len(doc), "sources": len(SOURCES),
                      "bytes": TARGET.stat().st_size, "sha256": sha256(TARGET.read_bytes()).hexdigest()}), flush=True)


if __name__ == "__main__":
    main()
