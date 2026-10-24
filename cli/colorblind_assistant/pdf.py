"""Inventory visible PDF objects without recreating text or chart geometry."""

from dataclasses import asdict, dataclass, field
from contextlib import closing
from io import BytesIO
import math
import ctypes

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
    matrix: tuple
    stream_path: tuple = ()
    editable: bool = True
    kind: str = "vector"
    image_id: str | None = None
    members: list = field(default_factory=list)
    dash: tuple = ()
    dash_phase: float = 0

    def inventory(self):
        result = {key: value for key, value in vars(self).items()
                  if key in {"id", "bbox", "fill", "stroke", "line_width", "kind", "image_id", "dash", "dash_phase"}}
        if self.kind == "vector" and self.stroke is not None:
            samples = path_segments(self.commands)
            step = max(1, math.ceil(len(samples) / 24))
            result["path_samples"] = [[round(v, 2) for v in (*a, *b)] for a, b in samples[::step]]
        if self.members:
            result["paint_count"] = len(self.members)
            result["grouping"] = "Same-color path fragments; edits affect every fragment in this bounded region."
        result['hatch_size_eligible'] = (self.kind == 'vector' and not self.members and self.fill is not None
                                        and min(self.bbox[2]-self.bbox[0], self.bbox[3]-self.bbox[1]) >= 6)
        return result


def path_segments(commands, close=False):
    """Sample cubic curves for placement, retaining subpath boundaries."""
    segments, current, start = [], (0., 0.), (0., 0.)
    for op, values in commands:
        if op == "m":
            if close and current != start:
                segments.append((current, start))
            current = start = tuple(values)
        elif op in {"l", "h"}:
            end = start if op == "h" else tuple(values)
            segments.append((current, end))
            current = end
        elif op == "c":
            p0, p1, p2, p3 = current, values[:2], values[2:4], values[4:6]
            for i in range(1, 17):
                t = i / 16
                end = tuple((1-t)**3*p0[j] + 3*(1-t)**2*t*p1[j] + 3*(1-t)*t*t*p2[j] + t**3*p3[j] for j in (0, 1))
                segments.append((current, end))
                current = end
    if close and current != start:
        segments.append((current, start))
    return segments


def fill_intersects(element, box, padding=0):
    """Test actual filled paths, including holes and disconnected map fragments."""
    if not intersects(element.bbox, box, padding):
        return False
    if element.members:
        return any(fill_intersects(member, box, padding) for member in element.members)
    if not element.commands:
        return True
    left, bottom, right, top = box
    box = (left-padding, bottom-padding, right+padding, top+padding)
    edges = path_segments(element.commands, close=True)
    if any(segment_crosses(box, a, b, 0) for a, b in edges):
        return True
    x, y = (left+right)/2, (bottom+top)/2
    winding = 0
    for (ax, ay), (bx, by) in edges:
        side = (bx-ax)*(y-ay) - (x-ax)*(by-ay)
        if ay <= y < by and side > 0:
            winding += 1
        elif by <= y < ay and side < 0:
            winding -= 1
    return bool(winding % 2 if element.fill_rule == 0 else winding)


def segment_crosses(box, a, b, padding):
    """Liang-Barsky clipping against a padded rectangle."""
    l, bottom, r, top = box
    l, bottom, r, top = l-padding, bottom-padding, r+padding, top+padding
    lo, hi = 0., 1.
    dx, dy = b[0]-a[0], b[1]-a[1]
    for p, q in ((-dx, a[0]-l), (dx, r-a[0]), (-dy, a[1]-bottom), (dy, top-a[1])):
        if abs(p) < 1e-12:
            if q < 0:
                return False
        elif p < 0:
            lo = max(lo, q/p)
        else:
            hi = min(hi, q/p)
        if lo > hi:
            return False
    return True


def colored(element):
    return element.editable and any(c is not None and max(c) - min(c) > .05
                                    for c in (element.fill, element.stroke))


@dataclass
class TextRun:
    id: str
    text: str
    bbox: tuple
    color: tuple
    visible: bool = True


@dataclass
class PageData:
    number: int
    width: float
    height: float
    elements: list[Element]
    text: list[TextRun]
    warnings: list[str] = field(default_factory=list)
    supported: bool = True
    images: dict = field(default_factory=dict)
    protected: list = field(default_factory=list)

    @property
    def targets(self):
        return [item for item in self.elements if colored(item)]

    def inventory(self):
        return {"page": self.number, "width": self.width, "height": self.height,
                "coordinates": "PDF points; origin at bottom left",
                "elements": [item.inventory() for item in self.targets],
                "text": [asdict(item) for item in self.text],
                "images": [{key: value for key, value in item.items() if key in {"id", "bbox", "width", "height", "palette_ids", "palette_mode"}}
                           for item in self.images.values()],
                "protected_objects": self.protected[:80]}


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
        chars, boxes, colors, visibility = [], [], [], []
        clips = _text_clip_bounds(page)

        def flush():
            if boxes and "".join(chars).strip():
                result.append(TextRun(f"p{number}-t{len(result) + 1:03d}",
                                      "".join(chars).strip(), union(boxes), colors[0], any(visibility)))
            chars.clear()
            boxes.clear()
            colors.clear()
            visibility.clear()

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
            channels = [ctypes.c_uint() for _ in range(4)]
            success = pdfium.raw.FPDFText_GetFillColor(textpage.raw, index, *(ctypes.byref(c) for c in channels))
            rgb = tuple(c.value / 255 for c in channels[:3]) if success else (0., 0., 0.)
            if colors and rgb != colors[-1]:
                flush()
            chars.append(char)
            if box[2] > box[0] and box[3] > box[1]:
                boxes.append(box)
                colors.append(rgb)
                obj = pdfium.raw.FPDFText_GetTextObject(textpage.raw, index)
                address = ctypes.cast(obj, ctypes.c_void_p).value
                clip = clips.get(address, (0,0,*page.get_size()))
                mode = pdfium.raw.FPDFTextObj_GetTextRenderMode(obj) if obj else 0
                visibility.append(mode not in {3,7} and intersects(box, clip))
        flush()
    return result


def _text_clip_bounds(page):
    """Account for inherited Form clipping before treating extracted text as an obstacle.

    PDF text extraction includes words hidden by crop/clip paths. Keep their IDs
    and source content for provenance, but do not let them occupy blank space.
    Bounds are conservative for non-rectangular clips.
    """
    result = {}
    for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_TEXT]):
        ancestry, current = [], obj
        while current is not None:
            ancestry.append(current)
            current = current.container
        matrix, bounds = IDENTITY, (0,0,*page.get_size())
        for current in reversed(ancestry):
            clip = pdfium.raw.FPDFPageObj_GetClipPath(current.raw)
            for i in range(max(0, pdfium.raw.FPDFClipPath_CountPaths(clip))):
                points = []
                for j in range(max(0, pdfium.raw.FPDFClipPath_CountPathSegments(clip,i))):
                    segment = pdfium.raw.FPDFClipPath_GetPathSegment(clip,i,j)
                    x, y = ctypes.c_float(), ctypes.c_float()
                    if pdfium.raw.FPDFPathSegment_GetPoint(segment,ctypes.byref(x),ctypes.byref(y)):
                        points.append(point(matrix,x.value,y.value))
                bounds = (clip_box(bounds,box_for(points)) if points else None) or (0,0,-1,-1)
            if current.type == pdfium.raw.FPDF_PAGEOBJ_FORM:
                matrix = compose(matrix,current.get_matrix().get())
        result[ctypes.cast(obj.raw,ctypes.c_void_p).value] = bounds
    return result


def box_for(points):
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))


def clip_box(box, clip):
    result = (max(box[0], clip[0]), max(box[1], clip[1]), min(box[2], clip[2]), min(box[3], clip[3]))
    return result if result[0] <= result[2] and result[1] <= result[3] else None


def resource(resources, category, name):
    return resources.get(category, {}).get_object().get(name) if category in resources else None


def device_color(space, args, resources):
    """Resolve device colors and ICC alternates; leave spot/pattern colors protected."""
    values = tuple(map(float, args))
    if not all(math.isfinite(c) and 0 <= c <= 1 for c in values):
        return None
    if str(space) not in {"/DeviceRGB", "/DeviceGray", "/DeviceCMYK"}:
        space = resource(resources, '/ColorSpace', space) or space
        space = space.get_object() if hasattr(space, 'get_object') else space
    if isinstance(space, (list, tuple)):
        if str(space[0]) == '/ICCBased':
            profile = space[1].get_object()
            # Convert embedded profiles instead of assuming all 3-channel spaces are sRGB.
            try:
                from PIL import ImageCms
                mode = {1: 'L', 3: 'RGB', 4: 'CMYK'}[int(profile['/N'])]
                sample = Image.new(mode, (1, 1), tuple(round(c * 255) for c in values) if len(values) > 1 else round(values[0] * 255))
                converted = ImageCms.profileToProfile(sample, ImageCms.ImageCmsProfile(BytesIO(profile.get_data())),
                                                      ImageCms.createProfile('sRGB'), outputMode='RGB')
                return tuple(c / 255 for c in converted.getpixel((0, 0)))
            except (ValueError, OSError, KeyError):
                return None
        return None
    if str(space) == '/DeviceRGB' and len(values) == 3:
        return values
    if str(space) == '/DeviceGray' and len(values) == 1:
        return values * 3
    if str(space) == '/DeviceCMYK' and len(values) == 4:
        c, m, y, k = values
        return ((1-c)*(1-k), (1-m)*(1-k), (1-y)*(1-k))
    return None


def inspect_page(page, number: int) -> PageData:
    width, height = float(page.mediabox.width), float(page.mediabox.height)
    data = PageData(number, width, height, [], [])
    if page.rotation or tuple(page.mediabox.lower_left) != (0, 0) or page.cropbox != page.mediabox:
        data.warnings.append("Rotated, offset, or cropped page boxes are unsupported.")
        data.supported = False
    if float(page.get('/UserUnit', 1)) != 1:
        data.warnings.append("Nonstandard PDF user units are unsupported.")
        data.supported = False
    for reference in page.get('/Annots', []):
        annotation = reference.get_object()
        if annotation.get('/Subtype') != '/Link' or annotation.get('/AP'):
            data.warnings.append("Non-link annotations or custom annotation appearances are unsupported.")
            data.supported = False

    def protect(box, reason):
        data.protected.append({"bbox": box, "reason": reason})

    def walk(obj, resources, inherited, path=(), names=(), ancestors=()):
        if len(path) > 16 or id(obj) in ancestors:
            protect(inherited['clip'], 'Recursive or deeply nested Form XObject.')
            return
        state = inherited.copy()
        group = obj.get('/Group')
        if group and getattr(group.get_object().get('/K', False), 'value', group.get_object().get('/K', False)):
            state['unsafe'] = 'Knockout transparency group.'
        stack, commands, points = [], [], []
        current = start = (0., 0.)
        pending_clip = False
        stream = ContentStream(obj.get_contents() if hasattr(obj, 'get_contents') else obj, page.pdf)
        for index, (args, op) in enumerate(stream.operations):
            if op == b'BMC' and args and str(args[0]) == '/CBAAdded':
                data.supported = False
                data.warnings.append('This page already contains assistant cues; reprocess the original source instead.')
            if op == b'q':
                stack.append(state.copy())
            elif op == b'Q':
                if not stack:
                    raise ValueError('Unbalanced graphics state.')
                state = stack.pop()
            elif op == b'cm':
                state['matrix'] = compose(state['matrix'], tuple(map(float, args)))
            elif op == b'gs':
                ref = resource(resources, '/ExtGState', args[0])
                if ref is None:
                    state['unsafe'] = 'Missing graphics state.'
                    continue
                gs = ref.get_object()
                for key in ('/ca', '/CA', '/BM', '/SMask', '/TR', '/TR2', '/OP', '/op', '/BG2', '/UCR2'):
                    if key in gs:
                        state[key] = gs[key]
                if '/LW' in gs:
                    state['width'] = float(gs['/LW'])
                if '/D' in gs:
                    state['dash'] = tuple(map(float,gs['/D'][0]))
                    state['dash_phase'] = float(gs['/D'][1])
                if any(k not in {'/Type', '/ca', '/CA', '/BM', '/SMask', '/TR', '/TR2', '/OP', '/op', '/OPM', '/LW', '/LC', '/LJ', '/ML', '/D', '/RI', '/FL', '/SA', '/SM', '/AIS', '/TK', '/BG2', '/UCR2'} for k in gs):
                    state['unsafe'] = 'Unsupported extended graphics setting.'
            elif op in {b'rg', b'RG', b'g', b'G', b'k', b'K', b'sc', b'SC', b'scn', b'SCN'}:
                channel = 'fill' if op.islower() else 'stroke'
                spaces = {b'rg': '/DeviceRGB', b'RG': '/DeviceRGB', b'g': '/DeviceGray', b'G': '/DeviceGray', b'k': '/DeviceCMYK', b'K': '/DeviceCMYK'}
                space = spaces.get(op, state[channel + '_space'])
                if op in spaces:
                    state[channel + '_space'] = space
                try:
                    state[channel] = device_color(space, args, resources)
                except (ValueError, TypeError):
                    state[channel] = None
            elif op in {b'cs', b'CS'}:
                channel = 'fill' if op == b'cs' else 'stroke'
                state[channel + '_space'] = args[0]
                state[channel] = None
            elif op == b'w':
                state['width'] = float(args[0])
            elif op == b'd':
                state['dash'], state['dash_phase'] = tuple(map(float,args[0])), float(args[1])
            elif op == b'Tr' and args and int(args[0]) >= 4:
                state['unsafe'] = 'Text clipping.'
            elif op in PATH_OPS:
                coords, matrix = list(map(float, args)), state['matrix']
                if op == b're':
                    x, y, w, h = coords
                    rect = [point(matrix, x, y), point(matrix, x+w, y), point(matrix, x+w, y+h), point(matrix, x, y+h)]
                    commands.extend([('m', rect[0]), *[('l', p) for p in rect[1:]], ('h', ())])
                    points.extend(rect)
                    current = start = rect[0]
                elif op in {b'm', b'l'}:
                    current = point(matrix, *coords)
                    if op == b'm':
                        start = current
                    commands.append((op.decode(), current))
                    points.append(current)
                elif op in {b'c', b'v', b'y'}:
                    transformed = [point(matrix, *coords[j:j+2]) for j in range(0, len(coords), 2)]
                    if op == b'v':
                        transformed.insert(0, current)
                    elif op == b'y':
                        transformed.append(transformed[-1])
                    commands.append(('c', tuple(v for p in transformed for v in p)))
                    points.extend(transformed)
                    current = transformed[-1]
                else:
                    commands.append(('h', ()))
                    current = start
            elif op in {b'W', b'W*'}:
                pending_clip = True
            elif op in PAINT_OPS | {b'n'}:
                if points and op != b'n':
                    if op in {b's', b'b', b'b*'}:
                        commands.append(('h', ()))
                    bbox = clip_box(box_for(points), state['clip'])
                    fill = state['fill'] if op not in {b'S', b's'} else None
                    stroke = state['stroke'] if op in {b'S', b's', b'B', b'B*', b'b', b'b*'} else None
                    reason = state.get('unsafe') or unsafe_compositing(state)
                    if (op not in {b'S', b's'} and fill is None) or (op in {b'S', b's', b'B', b'B*', b'b', b'b*'} and stroke is None):
                        reason = 'Unsupported color space.'
                    if pending_clip:
                        reason = 'Combined painting and clipping operation.'
                    if bbox:
                        a, b, c, d, _, _ = state['matrix']
                        data.elements.append(Element(f'p{number}-v{len(data.elements)+1:03d}', index, bbox, commands[:], fill, stroke,
                                                     state['width'] * max(math.hypot(a, b), math.hypot(c, d)),
                                                     0 if op.endswith(b'*') else 1, state['matrix'], path, not reason,
                                                     dash=tuple(round(v*max(math.hypot(a,b),math.hypot(c,d)),3) for v in state.get('dash',())),
                                                     dash_phase=state.get('dash_phase',0)*max(math.hypot(a,b),math.hypot(c,d))))
                        if reason:
                            protect(bbox, reason)
                if pending_clip:
                    state['clip'] = clip_box(box_for(points), state['clip']) if points else None
                    # Empty clipping paths suppress subsequent painting until a restore.
                    state['clip'] = state['clip'] or (0, 0, -1, -1)
                pending_clip, commands, points = False, [], []
            elif op == b'Do':
                reference = resource(resources, '/XObject', args[0])
                if reference is None:
                    raise ValueError('Missing XObject.')
                child = reference.get_object()
                if child.get('/Subtype') == '/Form':
                    child_state = state.copy()
                    child_state['matrix'] = compose(state['matrix'], tuple(map(float, child.get('/Matrix', IDENTITY))))
                    if '/BBox' in child:
                        l, b, r, t = map(float, child['/BBox'])
                        bounds = box_for([point(child_state['matrix'], x, y) for x, y in ((l,b),(r,b),(r,t),(l,t))])
                        child_state['clip'] = clip_box(bounds, state['clip']) or (0, 0, -1, -1)
                    walk(child, child.get('/Resources', resources).get_object(), child_state, (*path, index), (*names, str(args[0])), (*ancestors, id(obj)))
                elif child.get('/Subtype') == '/Image':
                    from .raster import inspect_image
                    bbox = clip_box(box_for([point(state['matrix'], x, y) for x, y in ((0,0),(1,0),(1,1),(0,1))]), state['clip'])
                    if bbox:
                        reason = state.get('unsafe') or unsafe_compositing(state)
                        reason = reason or inspect_image(page, child, (*names, str(args[0])), path, index, state['matrix'], bbox, data)
                        if reason:
                            protect(bbox, reason)
                else:
                    protect(state['clip'], 'Unsupported XObject subtype.')
            elif op in {b'sh', b'INLINE IMAGE'}:
                protect(state['clip'], 'Shading or inline image retained unchanged.')
            elif op not in TEXT_OPS | {b'J', b'j', b'M', b'd', b'ri', b'i', b'BMC', b'BDC', b'EMC', b'MP', b'DP', b'BX', b'EX'}:
                state['unsafe'] = f'Unsupported graphics operator {op!r}.'
        if stack and not path:
            raise ValueError('Unbalanced graphics state.')
        if stack:
            # A Form invocation restores its caller's graphics state on return.
            data.warnings.append('Trailing saved graphics states are isolated inside a Form; original operators retained.')

    state = {'matrix': IDENTITY, 'fill': (0.,0.,0.), 'stroke': (0.,0.,0.), 'width': 1.,
             'fill_space': '/DeviceGray', 'stroke_space': '/DeviceGray', 'clip': (0,0,width,height)}
    walk(page, page.get('/Resources', {}).get_object(), state)
    data.text = [t for t in text_runs(single_page_bytes(page), number) if intersects(t.bbox, (0,0,width,height))]
    if not all(math.isfinite(v) for element in data.elements for v in element.bbox):
        raise ValueError('Non-finite geometry.')
    compact_fragments(data)
    if data.protected:
        counts = {}
        for item in data.protected:
            counts[item['reason']] = counts.get(item['reason'], 0) + 1
        data.warnings.extend(f'{count} object(s) preserved: {reason}' for reason, count in counts.items())
        # Keep the model input bounded; all obstacles remain available locally for placement.
    data.warnings = list(dict.fromkeys(data.warnings))
    return data


def unsafe_compositing(state):
    if any(float(state.get(k, 1)) != 1 for k in ('/ca', '/CA')) or str(state.get('/BM', '/Normal')) not in {'/Normal', '/Compatible'}:
        return 'Non-opaque or blended graphics.'
    if str(state.get('/SMask', '/None')) != '/None' or any(str(state.get(k, '/Identity')) not in {'/Identity', '/Default'} for k in ('/TR', '/TR2', '/BG2', '/UCR2')):
        return 'Soft mask or transfer function.'
    if any(getattr(state.get(k, False), 'value', state.get(k, False)) for k in ('/OP', '/op')):
        return 'Overprint graphics.'
    return None


def compact_fragments(data):
    """Bound large inventories by grouping tiny same-color fragments in page tiles.

    This is a selectable paint bundle, not an assertion about a series' meaning.
    Source objects and individual paint indices remain intact for editing.
    """
    if len(data.targets) <= 400:
        return
    buckets, retained = {}, []
    for item in data.elements:
        if item.kind != 'vector' or not colored(item) or max(item.bbox[2]-item.bbox[0], item.bbox[3]-item.bbox[1]) > 20:
            retained.append(item)
            continue
        key = (item.stream_path, item.fill, item.stroke, item.dash, round(item.line_width, 3),
               int(item.bbox[0] // 100), int(item.bbox[1] // 100))
        buckets.setdefault(key, []).append(item)
    for members in buckets.values():
        first = members[0]
        if len(members) == 1:
            retained.append(first)
        else:
            retained.append(Element(first.id, first.paint_index, union([m.bbox for m in members]),
                                    [c for m in members for c in m.commands], first.fill, first.stroke,
                                    first.line_width, first.fill_rule, first.matrix, first.stream_path, members=members,
                                    dash=first.dash,dash_phase=first.dash_phase))
    data.elements = retained


def preservation_signature(page):
    """Original geometry/text operators must remain an exact prefix before new overlays."""
    def normalize(value):
        if isinstance(value, (list, tuple)):
            return tuple(normalize(item) for item in value)
        if isinstance(value, (int, float)):
            return round(float(value), 5)
        return str(value)
    signature = []

    def walk(obj, resources, ancestors=()):
        if id(obj) in ancestors or len(ancestors) > 16:
            raise ValueError('Recursive Form cannot be preservation-checked.')
        stream = ContentStream(obj.get_contents() if hasattr(obj, 'get_contents') else obj, page.pdf)
        added_depth = 0
        for args, op in stream.operations:
            if op == b"BMC" and args and str(args[0]) == "/CBAAdded":
                added_depth += 1
            elif added_depth:
                if op in {b"BMC", b"BDC"}:
                    added_depth += 1
                elif op == b"EMC":
                    added_depth -= 1
            elif op == b'Do':
                child = resource(resources, '/XObject', args[0]).get_object()
                if child.get('/Subtype') == '/Form':
                    signature.append(('form', normalize(child.get('/Matrix', IDENTITY)), normalize(child.get('/BBox'))))
                    walk(child, child.get('/Resources', resources).get_object(), (*ancestors, id(obj)))
                    signature.append(('end_form',))
                elif child.get('/Subtype') == '/Image':
                    signature.append(('image', int(child['/Width']), int(child['/Height'])))
            elif op in PATH_OPS | TEXT_OPS | {b'cm', b'W', b'W*'}:
                signature.append((op, normalize(args)))

    walk(page, page['/Resources'])
    return signature


def assert_preserved(before, after):
    if before.mediabox != after.mediabox or before.cropbox != after.cropbox or before.rotation != after.rotation:
        raise ValueError("Page dimensions or rotation changed.")
    original = preservation_signature(before)
    if preservation_signature(after)[:len(original)] != original:
        raise ValueError("Original text or chart geometry changed.")
    if not (after.extract_text() or "").startswith(before.extract_text() or ""):
        raise ValueError("Original extractable text changed.")
    def links(page):
        return [(str(a.get_object().get('/Subtype')), tuple(a.get_object().get('/Rect', [])),
                 str(a.get_object().get('/A', {}).get('/URI', ''))) for a in page.get('/Annots', [])]
    if links(before) != links(after):
        raise ValueError('Original annotations changed.')
