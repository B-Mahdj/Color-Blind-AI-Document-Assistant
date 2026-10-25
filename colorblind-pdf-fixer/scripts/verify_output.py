"""Check a corrected PDF against its source and optionally render review previews."""

import argparse
from contextlib import closing
from pathlib import Path
import sys

import pypdfium2 as pdfium
from pypdf import PdfReader


def _normalized_text(page):
    return "".join((page.extract_text() or "").split())


def _box(page, name):
    return tuple(float(value) for value in getattr(page, name))


def verify(source_path, output_path, preview_dir=None):
    source_path = Path(source_path).expanduser().resolve(strict=True)
    output_path = Path(output_path).expanduser().resolve(strict=True)
    if source_path == output_path:
        raise ValueError("Output must be a separate file; the source PDF is never overwritten.")

    source = PdfReader(source_path)
    output = PdfReader(output_path)
    if source.is_encrypted or output.is_encrypted:
        raise ValueError("Encrypted PDFs cannot be verified.")
    if len(source.pages) != len(output.pages):
        raise ValueError(f"Page count changed: {len(source.pages)} to {len(output.pages)}.")

    for index, (before, after) in enumerate(zip(source.pages, output.pages), 1):
        for name in ("mediabox", "cropbox"):
            if any(abs(a - b) > 0.01 for a, b in zip(_box(before, name), _box(after, name))):
                raise ValueError(f"Page {index} {name} changed.")
        if int(before.rotation or 0) % 360 != int(after.rotation or 0) % 360:
            raise ValueError(f"Page {index} rotation changed.")
        original_text = _normalized_text(before)
        corrected_text = _normalized_text(after)
        if original_text and original_text not in corrected_text:
            raise ValueError(f"Original selectable text is missing or reordered on page {index}.")

    if preview_dir is not None:
        preview_dir = Path(preview_dir).expanduser().resolve()
        preview_paths = [preview_dir / f"page-{i:04d}.png" for i in range(1, len(output.pages) + 1)]
        if any(path.exists() for path in preview_paths):
            raise FileExistsError("A review preview already exists; choose a new --preview-dir.")
        preview_dir.mkdir(parents=True, exist_ok=True)

    with pdfium.PdfDocument(str(output_path)) as document:
        for index in range(len(output.pages)):
            with closing(document[index]) as page:
                width, height = page.get_size()
                if width <= 0 or height <= 0:
                    raise ValueError(f"Page {index + 1} has invalid dimensions.")
                bitmap = page.render(scale=min(1.5, 2200 / max(width, height)))
                try:
                    if preview_dir is not None:
                        bitmap.to_pil().convert("RGB").save(preview_paths[index], format="PNG")
                finally:
                    bitmap.close()

    return len(output.pages)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_pdf", type=Path)
    parser.add_argument("corrected_pdf", type=Path)
    parser.add_argument("--preview-dir", type=Path, help="New directory for rendered review previews")
    args = parser.parse_args(argv)
    try:
        pages = verify(args.source_pdf, args.corrected_pdf, args.preview_dir)
        print(f"PASS: {pages} pages; page boxes, rotation, original text, and rendering verified.")
        if args.preview_dir:
            print(f"Previews: {args.preview_dir}")
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
