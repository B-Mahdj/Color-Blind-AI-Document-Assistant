"""Assemble the four locally collected geography sources into seven PDF pages.

Inputs and their original URLs are in output/pdf/geography-research/
selected-geography-sources.json. No recoloring or rasterization is performed.
"""

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter, Transformation, apply_configuration
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import build_research_sampler as layout


SOURCE_DIR = layout.OUT / "geography-research"
TARGET = layout.OUT / "Geography_Hard_Colors_Sampler.pdf"
PREVIEWS = layout.ROOT / "tmp/pdfs/geography-sampler"
SOURCES = json.loads((SOURCE_DIR / "selected-geography-sources.json").read_text(encoding="utf-8"))
# Fractions are measured from the top left; crop only the surrounding whitespace.
CASES = [
    (0, [16], [(.13, .16, .92, .90)], "Campagnes françaises",
     "Petits territoires, nombreuses catégories et légende à deux colonnes."),
    (0, [33], [(.13, .16, .92, .90)], "Littoral français",
     "Rouges, roses et verts dans la carte, la légende et trois diagrammes circulaires."),
    (1, [1, 2], [(.035, .045, .97, .79), (.035, .035, .97, .98)], "Organisation de l'espace du Brésil",
     "Carte et légende réunies : aplats rouges, orange, jaunes et verts, flèches et hachures."),
    (2, [36, 37], [(0, 0, 1, 1)] * 2, "Occupation du sol : Rennes et L'Hermitage",
     "Double page de l'IGN : photographie aérienne, contours denses, roses et verts."),
    (3, [28], [(.065, .09, .935, .965)], "Occupation du sol : Auvergne-Rhône-Alpes",
     "Carte multicolore, longue légende et barres empilées par département."),
    (3, [108], [(.065, .09, .935, .965)], "Occupation du sol : Provence-Alpes-Côte d'Azur",
     "Petites zones colorées, catégories voisines et comparaisons départementales."),
    (3, [112], [(.065, .09, .935, .965)], "Milieux naturels : Provence-Alpes-Côte d'Azur",
     "Nuances de vert dans les forêts, les milieux naturels et les graphiques associés."),
]
COLOR_OPS = {b"RG", b"rg", b"K", b"k", b"G", b"g", b"CS", b"cs", b"SC", b"sc", b"SCN", b"scn"}
PATH_OPS = {b"m", b"l", b"c", b"v", b"y", b"h", b"re", b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}


def graphics_signature(page):
    return Counter((op, repr(args) if op in COLOR_OPS else "") for args, op in page.get_contents().operations
                   if op in COLOR_OPS | PATH_OPS)


def build():
    for name, file in [("Arial", "arial.ttf"), ("ArialBold", "arialbd.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / file)))
    before = {s["file"]: sha256((SOURCE_DIR / s["file"]).read_bytes()).hexdigest() for s in SOURCES}
    assert all(before[s["file"]] == s["sha256"] for s in SOURCES), "A collected source has changed"
    selected = {(index, p) for index, pages, *_ in CASES for p in pages}
    assert selected == {(i, p) for i, s in enumerate(SOURCES) for p in s["pdf_pages"]}
    writer, records, signatures = PdfWriter(), [], []
    for number, (index, pages, crops, title, note) in enumerate(CASES, 1):
        source = SOURCES[index]
        size = landscape(A3) if len(pages) == 2 else A4
        width, height = size
        c, stream = layout.make_canvas(size)
        c.setTitle("Géographie - échantillon de couleurs d'origine")
        layout.text(c, "GÉOGRAPHIE / COULEURS D'ORIGINE", 24, height - 23, 8, True, colors.black)
        layout.fit_text(c, title, 24, height - 45, width - 48, 17, True, colors.black)
        layout.fit_text(c, note, 24, height - 61, width - 48, 8.5, color=colors.black)
        locator = ", ".join(map(str, pages))
        layout.text(c, f"{source['publisher']} | PDF p. {locator}", 24, 45, 7.5, color=colors.black)
        layout.fit_text(c, source["title"], 24, 32, width - 152, 7.5, color=colors.black)
        layout.text(c, "Ouvrir la source", width - 113, 32, 7.5, color=colors.black)
        c.linkURL(source["url"], (width - 117, 27, width - 24, 43), relative=0)
        layout.text(c, "Extraits pour tester la lecture des couleurs. Aucune correction appliquée.", 24, 16, 7, color=colors.black)
        c.drawRightString(width - 24, 16, f"{number} / {len(CASES)}")
        output_page = layout.finish(c, stream)
        panels = [layout.pdf_crop({"page": p, "crop": crop}, {"file": str(SOURCE_DIR / source["file"])})
                  for p, crop in zip(pages, crops)]
        gap = 20 if index == 1 else 0
        body_w = sum(bounds[2] - bounds[0] for _, bounds in panels) + gap * (len(panels) - 1)
        body_h = max(bounds[3] - bounds[1] for _, bounds in panels)
        x, y, scale = layout.fit_rect(body_w, body_h, (24, 62, width - 48, height - 136))
        signature = Counter()
        for panel, (left, bottom, right, top) in panels:
            signature.update(graphics_signature(panel))
            py = y + (body_h - (top - bottom)) * scale / 2
            output_page.merge_transformed_page(panel, Transformation().scale(scale).translate(
                x - left * scale, py - bottom * scale), expand=False)
            x += (right - left + gap) * scale
        writer.add_page(output_page)
        writer.add_outline_item(title, number - 1)
        signatures.append(signature)
        records.append({"page": number, "title": title, "source_file": source["file"],
                        "source_pages": pages, "source_url": source["url"], "crops": crops,
                        "size_points": size, "source_scale": scale})
    writer.add_metadata({"/Title": "Géographie - cartes aux couleurs difficiles",
                         "/Subject": "Sept pages d'extraits, couleurs et légendes d'origine conservées",
                         "/Author": "Compilation pour Color-Blind AI Document Assistant"})
    with TARGET.open("wb") as stream:
        writer.write(stream)
    assert TARGET.stat().st_size <= 50 * 1024 * 1024, "PDF exceeds the CLI's 50 MB input limit"
    result = PdfReader(TARGET)
    assert len(result.pages) == len(CASES) == 7
    assert [result.get_destination_page_number(b) for b in result.outline] == list(range(7))
    for page, record, expected in zip(result.pages, records, signatures):
        assert not expected - graphics_signature(page), f"Source graphics changed on page {record['page']}"
        urls = [a.get_object().get("/A", {}).get("/URI") for a in page.get("/Annots", [])]
        assert record["source_url"] in urls
    assert before == {s["file"]: sha256((SOURCE_DIR / s["file"]).read_bytes()).hexdigest() for s in SOURCES}
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    document = pdfium.PdfDocument(str(TARGET))
    sheet = Image.new("RGB", (1600, 1600), "#e6e9ed")
    draw = ImageDraw.Draw(sheet)
    for i in range(len(document)):
        page = document[i]
        bitmap = page.render(scale=1.5)
        rendered = bitmap.to_pil().copy()
        bitmap.close()
        page.close()
        rendered.save(PREVIEWS / f"page-{i + 1:02d}.png")
        rendered.thumbnail((770, 350))
        x, y = (i % 2) * 800, (i // 2) * 400
        draw.text((x + 12, y + 10), f"{i + 1:02d} / 07", fill="black")
        sheet.paste(rendered, (x + (800 - rendered.width) // 2, y + 34))
    document.close()
    sheet.save(PREVIEWS / "contact-sheet.png")
    manifest = {"pages": records, "sources": SOURCES,
                "checks": {"page_count": 7, "all_selected_source_pages_included": True,
                           "source_files_unchanged": True, "source_color_and_path_operators_retained": True,
                           "source_links_verified": 7, "bookmarks_verified": 7, "pages_rendered": 7},
                "correction_pipeline_run": False, "sha256": sha256(TARGET.read_bytes()).hexdigest()}
    TARGET.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"pdf": str(TARGET), "bytes": TARGET.stat().st_size, **manifest["checks"]}, indent=2))


if __name__ == "__main__":
    # The hash-checked DATAR map contains about 4.3 million content tokens.
    with apply_configuration(stream_parsing_work_maximum_count=6_000_000):
        build()
