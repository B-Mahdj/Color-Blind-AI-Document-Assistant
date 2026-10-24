"""Validate semantic groups atomically and apply only bounded vector edits."""

from copy import deepcopy
import colorsys
from dataclasses import dataclass
from io import BytesIO
import re

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, FloatObject, NumberObject
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .colors import color_metrics, contrast, hex_color, luminance, parse_hex, separation, simulated_rgb
from .models import PagePlan
from .pdf import PageData, assert_preserved, contains, intersects, single_page_bytes, union


@dataclass
class EditResult:
    pdf: bytes
    groups: list[dict]
    warnings: list[str]


def _float_args(values):
    return [FloatObject(value) for value in values]


def _wrap(text, width, font_size=8):
    lines, line = [], ""
    for word in text.split():
        proposed = f"{line} {word}".strip()
        if stringWidth(proposed, "Helvetica", font_size) > width:
            if not line:
                raise ValueError("A label is too wide to place safely.")
            lines.append(line)
            line = word
        else:
            line = proposed
    if line:
        lines.append(line)
    return lines


def _place(text, anchor, data, occupied, note=False):
    if not text.isascii() or any(ord(char) < 32 for char in text):
        raise ValueError("This version cannot add labels containing non-ASCII glyphs.")
    width = min(data.width - 32, 430 if note else 180)
    lines = _wrap(text, width - 8)
    actual_width = max(stringWidth(line, "Helvetica", 8) for line in lines) + 8
    height = len(lines) * 11 + 6
    left, bottom, right, top = anchor
    # Try nearby whitespace, never erase existing content to make room.
    candidates = []
    for gap in (8, 20, 36, 56):
        candidates.extend([(left, top + gap), (left, bottom - gap - height),
                           (right + gap, top - height), (left - gap - actual_width, top - height)])
    obstacles = [item.bbox for item in data.text] + [item.bbox for item in data.elements] + occupied
    for x, y in candidates:
        x = min(max(16, x), data.width - actual_width - 16)
        box = (x, y, x + actual_width, y + height)
        if contains((12, 12, data.width - 12, data.height - 12), box) and not any(intersects(box, other, 3) for other in obstacles):
            return {"text": text, "lines": lines, "bbox": box}
    raise ValueError("No nearby whitespace can hold the label without obscuring content.")


def _has_color_reference(data):
    return any(re.search(r"\b(red|green|blue|orange|yellow|purple|pink|brown|cyan|magenta|black|white|gray|grey)\b", item.text, re.I) for item in data.text)


def _numeric_text(element, data):
    matches = [item for item in data.text if contains(element.bbox, item.bbox, 2) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?%?", item.text.strip())]
    if len(matches) != 1:
        raise ValueError("An ordered scale needs one existing numeric label inside each cell.")
    return float(matches[0].text.rstrip("%"))


def _mapping_note(group, changes, data, elements):
    recolors = [change for change in changes if change["kind"] == "recolor"]
    if not recolors or not _has_color_reference(data):
        return None
    mapping = list(dict.fromkeys((change["before"], change["after"]) for change in recolors))
    if group.association == "ordered_scale":
        ordered = sorted((_numeric_text(elements[c["target_id"]], data), c["after"]) for c in recolors)
        low, high = parse_hex(ordered[0][1]), parse_hex(ordered[-1][1])
        if _color_name(low) == _color_name(high):
            direction = "darker" if luminance(high) < luminance(low) else "lighter"
            return (f"Color key: {_color_name(low)} shades; {direction} means higher values. "
                    "Original color names refer to the source. Numeric values are unchanged.")
        return (f"Color key: low values = {ordered[0][1]}; high values = {ordered[-1][1]}. "
                "Original color names refer to the source; numeric values are unchanged.")
    descriptions = []
    for old, new in mapping:
        ids = {change["target_id"] for change in recolors if change["before"] == old and change["after"] == new}
        cues = sorted({f"{change['style']} {'hatch' if change['kind'] == 'hatch' else 'line'}"
                       for change in changes if change["kind"] in {"hatch", "dash"} and change["target_id"] in ids})
        descriptions.append(f"{_color_name(parse_hex(old))} -> {_color_name(parse_hex(new))}" +
                            (f" ({', '.join(cues)})" if cues else ""))
    return "Color key: " + "; ".join(dict.fromkeys(descriptions)) + "."


def _color_name(rgb):
    hue, saturation, value = colorsys.rgb_to_hsv(*rgb)
    if saturation < .12:
        return "black" if value < .25 else "white" if value > .9 else "gray"
    degrees = hue * 360
    for boundary, name in ((15, "red"), (45, "orange"), (70, "yellow"), (165, "green"),
                           (195, "cyan"), (255, "blue"), (290, "purple"), (345, "pink"), (361, "red")):
        if degrees < boundary:
            return name


def _validate_group(group, data, edits, used, occupied):
    elements = {item.id: item for item in data.elements}
    texts = {item.id: item for item in data.text}
    if group.uncertain:
        raise ValueError("The model marked the association uncertain.")
    if any(item not in texts for item in group.evidence_text_ids):
        raise ValueError("Unknown source text ID.")
    targets = {item for action in group.actions for item in action.target_ids}
    if any(item not in elements for item in targets):
        raise ValueError("Unknown vector element ID.")
    if targets & used:
        raise ValueError("Another accepted group already edits this element.")
    if group.association == "legend":
        if not group.legend_ids or not set(group.legend_ids) < targets:
            raise ValueError("Legend groups must include their legend symbols and chart elements together.")
    elif group.legend_ids:
        raise ValueError("Legend IDs require a legend association.")
    local = deepcopy(edits)
    additions, changes, touched = [], [], set()
    for action in group.actions:
        if len(set(action.target_ids)) != len(action.target_ids):
            raise ValueError("Duplicate target IDs.")
        for identifier in action.target_ids:
            element = elements[identifier]
            if not contains((0, 0, data.width, data.height), element.bbox, 1):
                raise ValueError("The target extends outside the supported page area.")
            colors = [color for color in (element.fill, element.stroke) if color is not None]
            if not any(max(color) - min(color) > .05 for color in colors):
                raise ValueError("Neutral structural graphics are not correction targets.")
            config = local.setdefault(identifier, {})
            key = (identifier, action.kind, action.channel if action.kind == "recolor" else None)
            if key in touched:
                raise ValueError("Duplicate or conflicting actions in a group.")
            touched.add(key)
            record = {"kind": action.kind, "target_id": identifier}
            if action.kind == "recolor":
                if action.channel not in {"fill", "stroke"} or action.style or action.source_text_id or action.color is None:
                    raise ValueError("Recolor requires only a channel and RGB color.")
                before = getattr(element, action.channel)
                if before is None:
                    raise ValueError("The requested color channel is not painted.")
                after = parse_hex(action.color)
                if hex_color(before) == hex_color(after):
                    raise ValueError("A recolor action must change the color.")
                config[action.channel] = after
                record.update(channel=action.channel, before=hex_color(before), after=hex_color(after))
                if action.channel == "fill":
                    for text in data.text:
                        if intersects(element.bbox, text.bbox):
                            floor = min(4.5, contrast(text.color, before))
                            if contrast(text.color, after) + .05 < floor:
                                raise ValueError(f"Recolor would reduce text contrast near {text.id}.")
                            simulated_floor = min(4.5, contrast(simulated_rgb(text.color), simulated_rgb(before)))
                            if contrast(simulated_rgb(text.color), simulated_rgb(after)) + .05 < simulated_floor:
                                raise ValueError(f"Recolor would reduce simulated text contrast near {text.id}.")
                elif contrast(after, (1, 1, 1)) + .05 < min(3, contrast(before, (1, 1, 1))):
                    raise ValueError("Recolor would reduce line contrast on the page background.")
            elif action.kind == "hatch":
                if action.color or action.channel or action.source_text_id or action.style not in {"diagonal", "cross"} or element.fill is None:
                    raise ValueError("Hatching requires a filled shape and a supported style.")
                if min(element.bbox[2] - element.bbox[0], element.bbox[3] - element.bbox[1]) < 6:
                    raise ValueError("The target is too small for a readable hatch.")
                if any(intersects(element.bbox, text.bbox, 1) for text in data.text):
                    raise ValueError("Hatching might obscure existing text.")
                config["hatch"] = action.style
                record["style"] = action.style
            elif action.kind == "dash":
                if action.color or action.channel or action.source_text_id or action.style not in {"dashed", "dotted"} or element.stroke is None or element.fill is not None:
                    raise ValueError("Line styles require an unfilled stroked path.")
                if max(element.bbox[2] - element.bbox[0], element.bbox[3] - element.bbox[1]) < 8:
                    raise ValueError("The line is too short for a readable dash pattern.")
                config["dash"] = action.style
                record["style"] = action.style
            elif action.kind == "label":
                if action.color or action.channel or action.style or action.source_text_id not in texts or len(action.target_ids) != 1:
                    raise ValueError("A label must copy one known text run beside one target.")
                if action.source_text_id not in group.evidence_text_ids:
                    raise ValueError("A label must use the group's source evidence.")
                # A copied legend label need not duplicate its decorative bullet glyph.
                label_text = texts[action.source_text_id].text.lstrip(" \u2022\u25cf\u25aa\u25e6")
                label = _place(label_text, element.bbox, data,
                               occupied + [item["bbox"] for item in additions])
                additions.append(label)
                record.update(text=label["text"], bbox=label["bbox"], source_text_id=action.source_text_id)
            changes.append(record)
    if group.association == "legend":
        # Match each legend's applied encoding to a chart element of the same original color.
        for legend_id in group.legend_ids:
            legend = elements[legend_id]
            legend_config = local[legend_id]
            candidates = [elements[item] for item in targets - set(group.legend_ids)]
            if not any(((candidate.fill is not None and candidate.fill == legend.fill)
                        or (candidate.stroke is not None and candidate.stroke == legend.stroke))
                       and local.get(candidate.id) == legend_config for candidate in candidates):
                raise ValueError("A legend's new encoding does not match a corresponding chart element.")
    if group.association == "direct_labels":
        explicit_label = any(change["kind"] == "label" for change in changes)
        if not explicit_label:
            for identifier in targets:
                if not any(contains(elements[identifier].bbox, texts[item].bbox, 3) for item in group.evidence_text_ids):
                    raise ValueError("Directly labeled targets need an existing contained label or a new source label.")
    pairs = []
    for change in changes:
        if change["kind"] == "recolor":
            pairs.append((parse_hex(change["before"]), parse_hex(change["after"])))
    if group.association == "ordered_scale":
        entries = []
        for change in changes:
            if change["kind"] != "recolor" or change["channel"] != "fill":
                raise ValueError("Ordered scales use recolored cells with their existing numeric labels.")
            entries.append((_numeric_text(elements[change["target_id"]], data), luminance(parse_hex(change["after"]))))
        entries.sort()
        deltas = [b[1] - a[1] for a, b in zip(entries, entries[1:]) if a[0] != b[0]]
        if not deltas or not (all(d > .001 for d in deltas) or all(d < -.001 for d in deltas)):
            raise ValueError("The proposed scale does not preserve a strict lightness ordering of existing values.")
    metrics = color_metrics(pairs)
    if (metrics["minimum_separation_before"] is not None
            and metrics["minimum_separation_after"] + .02 < metrics["minimum_separation_before"]
            and group.association != "ordered_scale"
            and not any(change["kind"] in {"label", "hatch", "dash"} for change in changes)):
        raise ValueError("The palette reduces simulated separation without an additional cue.")
    note = _mapping_note(group, changes, data, elements)
    if note:
        anchor = union([elements[item].bbox for item in targets])
        placed = _place(note, anchor, data, occupied + [item["bbox"] for item in additions], note=True)
        additions.append(placed)
        changes.append({"kind": "mapping_note", "text": note, "bbox": placed["bbox"]})
    return local, additions, {"id": group.id, "source_evidence": [texts[item].text for item in group.evidence_text_ids],
                              "changes": changes, "metrics": metrics}, targets


def _overlay(data, edits, labels):
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=(data.width, data.height), invariant=1)
    for element in data.elements:
        config = edits.get(element.id, {})
        if "hatch" not in config:
            continue
        pdf.saveState()
        path = pdf.beginPath()
        for command, values in element.commands:
            if command == "m":
                path.moveTo(*values)
            elif command == "l":
                path.lineTo(*values)
            elif command == "c":
                path.curveTo(*values)
            else:
                path.close()
        pdf.clipPath(path, stroke=0, fill=0, fillMode=element.fill_rule)
        background = config.get("fill", element.fill)
        ink = 0 if contrast((0, 0, 0), background) >= contrast((1, 1, 1), background) else 1
        pdf.setStrokeColorRGB(ink, ink, ink)
        pdf.setLineWidth(.6)
        left, bottom, right, top = element.bbox
        span = top - bottom
        offset = left - span
        while offset <= right:
            pdf.line(offset, bottom, offset + span, top)
            if config["hatch"] == "cross":
                pdf.line(offset, top, offset + span, bottom)
            offset += 6
        pdf.restoreState()
    for label in labels:
        x, _, _, top = label["bbox"]
        pdf.setFillColorRGB(0, 0, 0)
        pdf.setFont("Helvetica", 8)
        for index, line in enumerate(label["lines"]):
            pdf.drawString(x + 4, top - 11 - index * 11, line)
    pdf.save()
    return out.getvalue()


def apply_plan(page, data: PageData, plan: PagePlan) -> EditResult:
    if not data.supported:
        return EditResult(single_page_bytes(page), [], data.warnings[:])
    edits, labels, groups, used, group_ids = {}, [], [], set(), set()
    warnings = list(plan.warnings)
    for group in plan.groups:
        try:
            if group.id in group_ids:
                raise ValueError("Duplicate correction group ID.")
            group_ids.add(group.id)
            edits_next, additions, record, targets = _validate_group(group, data, edits, used, [label["bbox"] for label in labels])
            edits = edits_next
            labels.extend(additions)
            groups.append(record)
            used.update(targets)
        except (ValueError, KeyError, TypeError) as error:
            warnings.append(f"Group {group.id} unchanged: {error}")
    if not groups:
        return EditResult(single_page_bytes(page), [], warnings)
    writer = PdfWriter()
    edited = writer.add_page(page)
    stream = ContentStream(edited.get_contents(), writer)
    by_index = {item.paint_index: edits[item.id] for item in data.elements if item.id in edits}
    operations = []
    for index, (args, op) in enumerate(stream.operations):
        config = by_index.get(index)
        if config:
            operations.append(([], b"q"))
            for channel, operator in (("fill", b"rg"), ("stroke", b"RG")):
                if channel in config:
                    operations.append((_float_args(config[channel]), operator))
            if "dash" in config:
                pattern = [6, 3] if config["dash"] == "dashed" else [1, 2]
                operations.append(([ArrayObject([NumberObject(n) for n in pattern]), NumberObject(0)], b"d"))
        operations.append((args, op))
        if config:
            operations.append(([], b"Q"))
    stream.operations = operations
    edited.replace_contents(stream)
    if labels or any("hatch" in config for config in edits.values()):
        overlay = PdfReader(BytesIO(_overlay(data, edits, labels)))
        edited.merge_page(overlay.pages[0])
    out = BytesIO()
    writer.write(out)
    output = out.getvalue()
    assert_preserved(page, PdfReader(BytesIO(output)).pages[0])
    return EditResult(output, groups, warnings)
