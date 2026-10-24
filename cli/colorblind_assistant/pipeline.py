"""Sequential processing, honest reports, and transactional output publication."""

from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject

from .agent import AgentError
from .colors import simulated_image
from .editor import EditResult, apply_plan
from .pdf import assert_preserved, inspect_page, render, single_page_bytes

PREVIEW_PATTERN = re.compile(r"page-\d{4}\.(?:original|corrected|original-protanopia|corrected-protanopia)\.png")


def _markdown(value):
    # Reports are data, including model warnings and copied source labels.
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("`", "\\`").replace("[", "\\[").replace("]", "\\]").replace("\n", " ")


def write_markdown(report, path):
    lines = ["# Protanopia document report", "", f"Status: **{report['status']}**", "",
             f"AI response source: `{report['ai']['source']}`; model: `{_markdown(report['ai']['model'])}`.", "",
             "Original text, values, page sizes, and vector geometry are preserved. Unsupported or uncertain content remains unchanged.", "",
             "Simulation is an approximation. " + ("Readability feedback from a reader with protanopia is still pending."
                 if report["validation"]["reader_feedback"] == "pending"
                 else report["validation"].get("reader_feedback_note", "Reader feedback has been recorded separately.")), ""]
    for page in report["pages"]:
        lines.extend([f"## Page {page['number']}: {page['status']}", ""])
        if not page["groups"]:
            lines.extend(["No validated correction was applied.", ""])
        for group in page["groups"]:
            lines.append(f"### {_markdown(group['id'])}")
            lines.append("")
            for change in group["changes"]:
                kind = change["kind"]
                target = change.get("target_id", "page")
                if kind == "recolor":
                    detail = f"{change['channel']} {change['before']} -> {change['after']}"
                elif kind in {"hatch", "dash"}:
                    detail = change["style"]
                else:
                    detail = change["text"]
                lines.append(f"- {_markdown(target)}: {_markdown(kind)} — {_markdown(detail)}")
            lines.append("")
        for warning in page["warnings"]:
            lines.append(f"- Needs attention: {_markdown(warning)}")
        lines.append("")
    lines.extend(["## Reader validation checklist", "",
                  "- Identify each bar's category using its legend.",
                  "- Follow both line series through crossings.",
                  "- Match pie segments and status indicators to their meanings.",
                  "- Compare heatmap values and ordering.",
                  "- Record remaining ambiguities and any obscured or misleading cues.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _validate_destination(output, source, overwrite):
    if output.exists() and not output.is_dir():
        raise ValueError("The output directory is an existing file.")
    previews = output / "previews"
    if previews.is_symlink() or (previews.exists() and not previews.is_dir()):
        raise ValueError("The previews path must be a real directory, not a file or symlink.")
    managed = [output / name for name in ("improved.pdf", "report.md", "report.json")]
    if previews.exists():
        managed.extend(path for path in previews.iterdir() if PREVIEW_PATTERN.fullmatch(path.name))
    for path in managed:
        if path.resolve() == source or (path.exists() and source.exists() and path.samefile(source)):
            raise ValueError("An output would overwrite the input PDF.")
        if path.is_symlink() or path.is_dir():
            raise ValueError("Managed output files cannot be symlinks or directories.")
        if path.exists() and not overwrite:
            raise FileExistsError("Outputs already exist. Choose another directory or pass --overwrite.")


def _publish(stage, output, source, overwrite):
    _validate_destination(output, source, overwrite)
    output.mkdir(parents=True, exist_ok=True)
    (output / "previews").mkdir(exist_ok=True)
    files = [path for path in stage.rglob("*") if path.is_file()]
    destinations = {output / path.relative_to(stage): path for path in files}
    stale = [path for path in (output / "previews").iterdir()
             if PREVIEW_PATTERN.fullmatch(path.name) and path not in destinations]
    backups, written = [], []
    backup_dir = stage / "previous"
    backup_dir.mkdir()
    try:
        for index, destination in enumerate([*destinations, *stale]):
            # Verify every resolved mutation target remains in the named output directory.
            destination.resolve().relative_to(output.resolve())
            if destination.resolve() == source:
                raise ValueError("An output would overwrite the input.")
            if destination.exists():
                backup = backup_dir / str(index)
                os.replace(destination, backup)
                backups.append((destination, backup))
        for destination, staged in destinations.items():
            os.replace(staged, destination)
            written.append(destination)
    except BaseException:
        for path in reversed(written):
            path.unlink()
        for destination, backup in reversed(backups):
            os.replace(backup, destination)
        raise


def process_document(input_path, output_dir, agent, overwrite=False, progress=lambda message: None):
    source = Path(input_path).expanduser().resolve(strict=True)
    output = Path(output_dir).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Input must be a PDF file.")
    if source.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("The initial CLI supports PDFs up to 50 MB.")
    _validate_destination(output, source, overwrite)
    raw = source.read_bytes()
    reader = PdfReader(BytesIO(raw))
    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are unsupported; provide an unencrypted copy.")
    if not 1 <= len(reader.pages) <= 50:
        raise ValueError("The initial CLI supports documents with 1 to 50 pages.")
    if reader.trailer['/Root'].get('/AcroForm'):
        raise ValueError("Interactive PDF forms are unsupported; provide a document without form fields.")
    report = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(),
              "input": str(source), "input_sha256": hashlib.sha256(raw).hexdigest(),
              "status": "completed", "deficiency": "protanopia", "simulation": "Vienot1999", "severity": 1.0,
              "ai": {"source": agent.source, "model": agent.model, "calls": []},
              "validation": {"original_content_preserved": False, "reader_feedback": "pending"},
              "pages": [], "outputs": {"pdf": str(output / "improved.pdf"), "markdown": str(output / "report.md"),
                                        "json": str(output / "report.json"), "previews": str(output / "previews")}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".colorblind-", dir=output.parent) as temporary:
        stage = Path(temporary)
        previews = stage / "previews"
        previews.mkdir()
        # Preserve the document's bookmark tree and internal link destinations.
        writer = PdfWriter(clone_from=reader)
        if reader.metadata:
            writer.add_metadata({str(key): str(value) for key, value in reader.metadata.items()})
        disabled = None
        for number, page in enumerate(reader.pages, 1):
            progress(f"[{number}/{len(reader.pages)}] Inspecting page")
            original_pdf = single_page_bytes(page)
            original = render(original_pdf)
            entry = {"number": number, "status": "unchanged", "groups": [], "warnings": [], "previews": {}}
            result = EditResult(original_pdf, [], [])
            try:
                data = inspect_page(page, number)
                entry['coverage'] = {'editable_targets': len(data.targets), 'protected_objects': len(data.protected),
                                     'bitmap_figures': len(data.images),
                                     'vector_paints': sum(len(item.members) or 1 for item in data.elements if item.kind == 'vector')}
                if len(data.targets) > 1200 or sum(len(item.text) for item in data.text) > 30000:
                    data.supported = False
                    data.warnings.append("Page exceeds the analysis budget after filtering and grouping (1,200 editable targets or 30,000 text characters).")
                if not data.supported:
                    entry["status"] = "unsupported"
                    result.warnings.extend(data.warnings)
                elif not data.targets:
                    result.warnings.extend(data.warnings)
                elif disabled:
                    entry["status"] = "failed"
                    result.warnings.append(disabled)
                else:
                    progress(f"[{number}/{len(reader.pages)}] Requesting AI proposal")
                    plan = agent.propose(data, original)
                    result = apply_plan(page, data, plan)
                    if plan.groups:
                        progress(f"[{number}/{len(reader.pages)}] Reviewing validated candidate")
                        review = agent.review(data, original, render(result.pdf), result.groups, result.warnings)
                        if review.approved:
                            result.warnings.extend(review.warnings)
                        elif review.revised_plan is not None:
                            result = apply_plan(page, data, review.revised_plan)
                            result.warnings.extend(f"Review of the initial candidate: {warning}" for warning in review.warnings)
                            result.warnings.append("One revision applied after AI review; its final appearance still needs human review.")
                        else:
                            result = EditResult(original_pdf, [], [*result.warnings, *review.warnings,
                                                                  "AI review did not approve the candidate; page preserved unchanged."])
                    entry["status"] = "corrected" if result.groups else "unchanged"
            except AgentError as error:
                result = EditResult(original_pdf, [], [str(error)])
                entry["status"] = "failed"
                if error.fatal:
                    disabled = "AI processing stopped after an unrecoverable configuration or API error."
            except (ValueError, KeyError, TypeError, RuntimeError) as error:
                result = EditResult(original_pdf, [], [f"Page processing failed ({type(error).__name__}); original page retained."])
                entry["status"] = "failed"
            corrected = render(result.pdf)
            after = PdfReader(BytesIO(result.pdf)).pages[0]
            assert_preserved(page, after)
            destination = writer.pages[number - 1]
            destination.replace_contents(after.get_contents().clone(writer))
            destination[NameObject('/Resources')] = after['/Resources'].clone(writer)
            entry["groups"] = result.groups
            entry["warnings"] = list(dict.fromkeys(result.warnings))
            if entry["warnings"] and entry["status"] in {"corrected", "unchanged"}:
                entry["status"] = "needs_review"
            for kind, image in (("original", original), ("corrected", corrected),
                                ("original-protanopia", simulated_image(original)),
                                ("corrected-protanopia", simulated_image(corrected))):
                filename = f"page-{number:04d}.{kind}.png"
                image.save(previews / filename)
                entry["previews"][kind] = str(output / "previews" / filename)
            report["pages"].append(entry)
            progress(f"[{number}/{len(reader.pages)}] {entry['status']}")
        if all(page["status"] == "failed" for page in report["pages"]):
            report["status"] = "failed"
        elif any(page["status"] in {"failed", "unsupported", "needs_review"} for page in report["pages"]):
            report["status"] = "partial"
        report["ai"]["calls"] = agent.calls
        with (stage / "improved.pdf").open("wb") as handle:
            writer.write(handle)
        exported = PdfReader(stage / "improved.pdf")
        if len(exported.pages) != len(reader.pages):
            raise ValueError("Export changed the page count.")
        for before, after in zip(reader.pages, exported.pages):
            assert_preserved(before, after)
        report["validation"]["original_content_preserved"] = True
        (stage / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        write_markdown(report, stage / "report.md")
        _publish(stage, output, source, overwrite)
    return report
