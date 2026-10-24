import argparse
import json
import os
from pathlib import Path
import sys

from pypdf.errors import PdfReadError

from .agent import AgentError, OpenAIReviewer
from .pipeline import process_document


def main(argv=None):
    parser = argparse.ArgumentParser(description="Improve supported digital PDFs for readers with protanopia while preserving text and layout.")
    parser.add_argument("input", type=Path, help="Input digital PDF")
    parser.add_argument("--output-dir", type=Path, default=Path("output"), help="Output directory (default: output)")
    parser.add_argument("--overwrite", action="store_true", help="Replace this tool's existing output files, never the input")
    args = parser.parse_args(argv)
    try:
        reviewer = OpenAIReviewer(os.environ.get("OPENAI_API_KEY"), os.environ.get("OPENAI_MODEL", "gpt-6.1-sol"))
        report = process_document(args.input, args.output_dir, reviewer, args.overwrite,
                                  progress=lambda message: print(message, file=sys.stderr, flush=True))
        result = {"status": report["status"], "pages": len(report["pages"]),
                  "corrected_pages": sum(bool(page["groups"]) for page in report["pages"]),
                  "reader_validation": "pending", "outputs": report["outputs"]}
        print(json.dumps(result, ensure_ascii=True))
        return {"completed": 0, "failed": 1, "partial": 3}[report["status"]]
    except (AgentError, OSError, ValueError, PdfReadError) as error:
        print(str(error), file=sys.stderr)
        print(json.dumps({"status": "failed", "error": str(error)}))
        return 1
    except KeyboardInterrupt:
        print("Processing interrupted; no new output set was published.", file=sys.stderr)
        print(json.dumps({"status": "failed", "error": "Interrupted"}))
        return 1
    except Exception as error:
        message = f"Processing failed ({type(error).__name__}); no new output set was published."
        print(message, file=sys.stderr)
        print(json.dumps({"status": "failed", "error": message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
