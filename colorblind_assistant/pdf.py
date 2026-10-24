"""Read simple vector PDFs without recreating their text or chart geometry."""

from dataclasses import asdict, dataclass, field
from contextlib import closing
from io import BytesIO
import math

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream

IDENTITY = (1., 0., 0., 1., 0., 0.)
PATH_OPS = {b"m", b"l", b"c", b"v", b"y", b"h", b"re"}
PAINT_OPS = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
TEXT_OPS = {b"BT", b"ET", b"Tf", b"Tm", b"Td", b"TD", b"T*", b"Tj", b"TJ", b"'", b'"', b"Tc", b"Tw", b"Tz", b"TL", b"Tr", b"Ts"}


def point(matrix, x, y):
    a, b, c, d, e, f = matrix
    return (a * x + c * y + e, b * x + d * y + f)


def compose(outer, inner):
    a, b, c, d, e, f = inner
    x0, y0 = point(outer, e, f)
    x1, y1 = point(outer, a + e, b + f)
    x2, y2 = point(outer, c + e, d + f)
    return (x1 - x0, y1 - y0, x2 - x0, y2 - y0, x0, y0)


def intersects(first, second, padding=0):
    return (first[0] < second[2] + padding and first[2] > second[0] - padding
            and first[1] < second[3] + padding and first[3] > second[1] - padding)


def contains(outer, inner, padding=0):
    return (outer[0] - padding <= inner[0] <= inner[2] <= outer[2] + padding
            and outer[1] - padding <= inner[1] <= inner[3] <= outer[3] + padding)


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


@dataclass
class Element:
    id: str
    paint_index: int
    bbox: tuple
    commands: list
    fill: tuple | None
    stroke: tuple | None
    line_width: float
    fill_rule: int

    def inventory(self):
        return {key: value for key, value in asdict(self).items()
                if key not in {"commands", "paint_index", "fill_rule"}}


@dataclass
class TextRun:
    id: str
    text: str
    bbox: tuple
    color: tuple


@dataclass
class PageData:
    number: int
    width: float
    height: float
    elements: list[Element]
    text: list[TextRun]
    warnings: list[str] = field(default_factory=list)
    supported: bool = True

    def inventory(self):
        return {"page": self.number, "width": self.width, "height": self.height,
                "coordinates": "PDF points; origin at bottom left",
                "elements": [item.inventory() for item in self.elements],
                "text": [asdict(item) for item in self.text]}


def single_page_bytes(page) -> bytes:
    writer = PdfWriter()
    writer.add_page(page)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def render(pdf_bytes: bytes, index=0, scale=1.5) -> Image.Image:
    with pdfium.PdfDocument(pdf_bytes) as doc:
        with closing(doc[index]) as page:
            # Bound raster memory without changing PDF export resolution.
            width, height = page.get_size()
            scale = min(scale, 2200 / max(width, height))
            bitmap = page.render(scale=scale)
            try:
                return bitmap.to_pil().convert("RGB").copy()
            finally:
                bitmap.close()


def text_runs(pdf_bytes: bytes, number: int) -> list[TextRun]:
    result = []
    with pdfium.PdfDocument(pdf_bytes) as doc, closing(doc[0]) as page, closing(page.get_textpage()) as textpage:
        chars, boxes, colors = [], [], []

        def flush():
            if boxes and "".join(chars).strip():
                result.append(TextRun(f"p{number}-t{len(result) + 1:03d}",
                                      "".join(chars).strip(), union(boxes), colors[0]))
            chars.clear()
            boxes.clear()
            colors.clear()

        for index in range(textpage.count_chars()):
            char = textpage.get_text_range(index, 1)
            if char in {"\r", "\n"}:
                flush()
                continue
            box = tuple(textpage.get_charbox(index))
            if not char or not all(math.isfinite(x) for x in box):
                continue
            if boxes:
                last = boxes[-1]
                if abs(box[1] - last[1]) > max(3, (last[3] - last[1]) * .6) or box[0] - last[2] > 8:
                    flush()
            # PDFium reports text fill colors without decoding embedded font glyphs ourselves.
            import ctypes
            channels = [ctypes.c_uint() for _ in range(4)]
            success = pdfium.raw.FPDFText_GetFillColor(textpage.raw, index, *(ctypes.byref(c) for c in channels))
            rgb = tuple(c.value / 255 for c in channels[:3]) if success else (0., 0., 0.)
            chars.append(char)
            if box[2] > box[0] and box[3] > box[1]:
                boxes.append(box)
                colors.append(rgb)
        flush()
    return result


def inspect_page(page, number: int) -> PageData:
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    warnings = []
    if page.rotation or tuple(page.mediabox.lower_left) != (0, 0) or page.cropbox != page.mediabox:
        warnings.append("Rotated, offset, or cropped pages are outside the initial supported subset.")
    if page.get('/Annots'):
        warnings.append("Pages with annotations or form widgets are preserved unchanged.")
    if float(page.get('/UserUnit', 1)) != 1:
        warnings.append("Nonstandard PDF user units are unsupported.")
    if page.get('/Group'):
        warnings.append("Transparency groups are unsupported.")
    stream = ContentStream(page.get_contents(), page.pdf)
    state = {"matrix": IDENTITY, "fill": (0., 0., 0.), "stroke": (0., 0., 0.), "width": 1.}
    stack, commands, points, elements = [], [], [], []
    current, start = (0., 0.), (0., 0.)
    allowed = PATH_OPS | PAINT_OPS | TEXT_OPS | {b"q", b"Q", b"cm", b"rg", b"RG", b"g", b"G", b"w", b"J", b"j", b"M", b"d", b"ri", b"i", b"n", b"BMC", b"BDC", b"EMC", b"MP", b"DP"}
    for index, (args, op) in enumerate(stream.operations):
        if op not in allowed:
            warnings.append(f"Unsupported graphics operator {op.decode('ascii', errors='replace')}; page preserved unchanged.")
            continue
        if op == b"q":
            stack.append(state.copy())
        elif op == b"Q":
            if not stack:
                warnings.append("Unbalanced graphics state.")
            else:
                state = stack.pop()
        elif op == b"cm":
            state["matrix"] = compose(state["matrix"], tuple(map(float, args)))
        elif op in {b"rg", b"RG", b"g", b"G"}:
            rgb = tuple(map(float, args))
            if len(rgb) == 1:
                rgb *= 3
            if len(rgb) != 3 or not all(math.isfinite(c) and 0 <= c <= 1 for c in rgb):
                warnings.append("Invalid device color.")
            else:
                state["fill" if op in {b"rg", b"g"} else "stroke"] = rgb
        elif op == b"w":
            state["width"] = float(args[0])
        elif op in PATH_OPS:
            coords = list(map(float, args))
            matrix = state["matrix"]
            if op == b"re":
                x, y, w, h = coords
                rect = [point(matrix, x, y), point(matrix, x + w, y), point(matrix, x + w, y + h), point(matrix, x, y + h)]
                commands.extend([("m", rect[0]), *[("l", p) for p in rect[1:]], ("h", ())])
                points.extend(rect)
                current = start = rect[0]
            elif op in {b"m", b"l"}:
                current = point(matrix, *coords)
                if op == b"m":
                    start = current
                commands.append((op.decode(), current))
                points.append(current)
            elif op in {b"c", b"v", b"y"}:
                transformed = [point(matrix, *coords[j:j + 2]) for j in range(0, len(coords), 2)]
                if op == b"v":
                    transformed.insert(0, current)
                elif op == b"y":
                    transformed.append(transformed[-1])
                commands.append(("c", tuple(v for p in transformed for v in p)))
                points.extend(transformed)
                current = transformed[-1]
            else:
                commands.append(("h", ()))
                current = start
        elif op in PAINT_OPS:
            if op in {b"s", b"b", b"b*"}:
                commands.append(("h", ()))
            if points:
                bbox = (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))
                a, b, c, d, _, _ = state["matrix"]
                elements.append(Element(f"p{number}-v{len(elements) + 1:03d}", index, bbox, commands[:],
                                        state["fill"] if op not in {b"S", b"s"} else None,
                                        state["stroke"] if op in {b"S", b"s", b"B", b"B*", b"b", b"b*"} else None,
                                        state["width"] * max(math.hypot(a, b), math.hypot(c, d)),
                                        0 if op.endswith(b"*") else 1))
            commands, points = [], []
        elif op == b"n":
            commands, points = [], []
    if stack:
        warnings.append("Unbalanced graphics state.")
    pdf_bytes = single_page_bytes(page)
    text = text_runs(pdf_bytes, number)
    if not text:
        warnings.append("No extractable text; scans and image-only pages are unsupported.")
    if not all(math.isfinite(v) for element in elements for v in element.bbox):
        warnings.append("Non-finite geometry.")
    return PageData(number, width, height, elements, text, list(dict.fromkeys(warnings)), not warnings)


def preservation_signature(page):
    """Original geometry/text operators must remain an exact prefix before new overlays."""
    def normalize(value):
        if isinstance(value, (list, tuple)):
            return tuple(normalize(item) for item in value)
        if isinstance(value, (int, float)):
            return round(float(value), 5)
        return str(value)
    stream = ContentStream(page.get_contents(), page.pdf)
    return [(op, normalize(args)) for args, op in stream.operations if op in PATH_OPS | TEXT_OPS]


def assert_preserved(before, after):
    if before.mediabox != after.mediabox or before.cropbox != after.cropbox or before.rotation != after.rotation:
        raise ValueError("Page dimensions or rotation changed.")
    original = preservation_signature(before)
    if preservation_signature(after)[:len(original)] != original:
        raise ValueError("Original text or chart geometry changed.")
