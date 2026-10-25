"""Extract every reachable /Image XObject as PNG, including forms and masks.

Usage: python extract_images.py input.pdf [output_directory]
Requires pypdf and Pillow. Defaults to input_images beside the PDF.
Form XObjects contain drawing commands; they are traversed, not rasterized.
Inline images in content streams are not XObjects and are not extracted.
"""

import argparse
from pathlib import Path
import sys

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject


def extract_images(source, output=None):
    source = Path(source).expanduser().resolve(strict=True)
    output = Path(output) if output is not None else source.with_name(source.stem + "_images")
    with source.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported; decrypt a copy first.")
        output.mkdir(parents=True, exist_ok=False)
        pending, seen, paths = [reader.trailer], set(), []
        while pending:
            obj = pending.pop().get_object()
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            if isinstance(obj, DictionaryObject):
                pending.extend(obj.values())
                if obj.get("/Subtype") != "/Image":
                    continue
                reference = getattr(obj, "indirect_reference", None)
                label = (f"{reference.idnum}-{reference.generation}" if reference
                         else f"direct-{len(paths) + 1}")
                path = output / f"image-{label}.png"
                try:
                    image = obj.decode_as_image()
                    if image is None:
                        raise ValueError("Unsupported image encoding")
                    if image.mode == "CMYK":
                        image = image.convert("RGB")
                    with path.open("xb") as destination:
                        image.save(destination, format="PNG")
                except Exception as error:
                    raise RuntimeError(f"Cannot extract {label}: {error}") from error
                paths.append(path)
            elif isinstance(obj, ArrayObject):
                pending.extend(obj)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_directory", nargs="?", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = extract_images(args.input_pdf, args.output_directory)
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"Extracted {len(paths)} image XObjects.")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
