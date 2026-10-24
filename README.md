# Color-Blind Document Assistant

A Python CLI for readers with **protanopia**. It improves supported digital PDFs using color changes, hatching, line styles, and direct labels while retaining original selectable text, values, page layout, and chart geometry.

Built for the OpenAI DevDay Community Hackathon in Paris, Impact track.

## Run on Windows

Requires Python 3.11 or later, internet access for OpenAI, and an API key with access to the configured model. From the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

# Create the local settings file if it does not already exist, then add your key.
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env

.\.venv\Scripts\python.exe -m colorblind_assistant tests\fixtures\Test_Document_Protanopia.pdf --output-dir output
$LASTEXITCODE
```

The environment in this checkout is already installed. Open `.env`, paste your key after `OPENAI_API_KEY=`, and save it before running the CLI. Virtual environments are machine-specific and are not committed.

The default model is `gpt-6.1-sol`. Change `OPENAI_MODEL` in `.env` to use another compatible model available to your account. The CLI automatically reads `.env` from the **current working directory**, so run it from the project directory. Existing environment variables take precedence over `.env`. Only `OPENAI_API_KEY` and `OPENAI_MODEL` are used from the file; variable expansion is disabled. [.env.example](.env.example) documents the settings. The private `.env` file and generated outputs are ignored by Git.

The installed `colorblind-assistant` command is equivalent to `python -m colorblind_assistant`. On macOS/Linux, use `.venv/bin/python` and edit `.env` in your preferred editor.

## Outputs and exit codes

Each completed processing run writes:

| Output | Purpose |
| --- | --- |
| `improved.pdf` | Complete PDF, including pages retained unchanged |
| `report.md` | English explanations of actual edits, unresolved issues, reader checklist |
| `report.json` | Versioned machine-readable results, stable element IDs, changes, metrics, warnings, model usage, output paths |
| `previews/` | Original, corrected, original-protanopia, and corrected-protanopia PNGs for every page |

Preview filenames follow `page-0001.corrected.png`. Simulations are for comparison, not the exported reading version.

Progress goes to stderr. Stdout contains one JSON result for automation; `--help` uses normal help text.

| Exit | Meaning |
| --- | --- |
| `0` | Processing completed, with no reported unresolved issue |
| `1` | Failure, including missing credentials or all pages failing AI processing |
| `2` | Invalid command-line arguments |
| `3` | Partial result: unsupported content, rejected corrections, or further review needed |

`completed` describes processing, **not certified accessibility**. An unchanged page means no validated correction was applied; it does not prove that the page is already accessible. Readability feedback starts as pending in each new report.

The input is never overwritten. Use a different output directory or `--overwrite` to replace existing generated files. Overwrite replaces only the named reports/PDF and this tool's numbered previews; unrelated files remain. New outputs are staged first, and recoverable publication failures restore existing outputs. If AI fails after processing starts, the report can accompany an unchanged PDF; check the status before using it.

## Supported documents

- One digital PDF per run, 1-50 pages and at most 50 MB.
- Native filled text and simple device RGB/grayscale vector shapes, including ordinary affine transformations.
- At most 500 shapes and 20,000 extracted text characters per supported page.
- Source text remains in its original language. CLI messages and generated explanations are English.
- Added labels copy source words; decorative bullet prefixes are omitted. Added labels currently use ASCII glyphs. Unsupported labels are rejected.

Scans, image-containing pages, Form XObjects, CMYK/ICC/spot colors, shading, clipping paths, transparency, rotated/cropped/offset pages, nonstandard user units, advanced text rendering, and pages with annotations are retained unchanged and reported. A mixed supported/unsupported document still exports every page. Encrypted PDFs and interactive forms are rejected as complete inputs. This conservative subset includes the supplied five-page fixture; it does not cover every digitally created PDF.

Run again from the **original PDF** when changing settings. PDFs already containing assistant cues are not correction inputs for this initial version.

## How corrections work

1. `pypdf` inventories original paths; `pypdfium2` extracts text positions and renders page images.
2. DaltonLens simulates protanopia using Viénot 1999 at severity `1.0`.
3. OpenAI receives original page images, a simulated view, extracted text, stable element IDs, and a consistent categorical palette informed by reader feedback. Suggested colors are checked against existing text and line contrast; they do not establish category associations. Structured responses propose atomic groups of chart/legend corrections.
4. Local code validates IDs, colors, legend consistency, text contrast in normal and simulated views, scale ordering, and available space. Unknown or uncertain groups remain unchanged. Neutral structural graphics cannot be edited.
5. Color and dash changes are scoped to original paint operations. Clipped hatching is inserted at the original drawing position so later shapes retain their occlusion. ReportLab adds copied labels and color mapping notes only in nearby whitespace.
6. The AI reviews the rendered candidate. It may approve, reject, or provide one replacement plan. A revision is applied from the original page and marked for human review; there is no unbounded loop or second AI review of that revision.
7. Before publication, the pipeline reopens the PDF and verifies page dimensions, original text/geometry operations, and extractable text. Reports describe accepted edits only.

Simulation distances are ranking heuristics. Numeric geometry checks cannot prove an AI's interpretation of a legend; real-reader review remains important.

## Data and API behavior

OpenAI analysis is enabled by default. Supported pages' rendered content and extracted text leave the machine. Calls use `store=False`, a 60-second request timeout, and at most one SDK retry per call. Each supported page uses one proposal call and, if a correction was proposed, one review call. No tools, code execution, or filesystem access are exposed to the model. Instructions inside a document are treated as untrusted content.

Local reports contain document text and usage metadata; keep them as private as the source document. API error bodies and credentials are not copied into reports. Access to the default model must be verified with your own API account.

## Tests and demo evidence

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

Tests run without an API key or network. They cover the five-page fixture, independent synthetic charts, original-content preservation, group rejection, contrast, label placement, hatch occlusion, API parsing through the real SDK with mocked HTTP, bounded revision, exit handling, and transactional overwrite.

`tests/sample_responses.py` supplies **controlled test responses only**. It is never selected by the production CLI. The local `output-controlled-qa/` sample is identified as such in its reports. It demonstrates the PDF engine; it is not evidence of live model performance.

See [QA.md](QA.md) for visual review and positive qualitative reader feedback on the controlled sample. A separate live run with `gpt-6.1-sol` completed all ten API calls and produced `output-live-qa/`: four pages changed, one remained unchanged, and unresolved issues correctly yielded a partial result. The reader found that live output harder to read, especially "At risk" versus "Delayed"; it has not passed reader validation.

## Project layout

- `colorblind_assistant/pdf.py`: inventory, rendering, preservation checks.
- `colorblind_assistant/editor.py` and `colors.py`: bounded edits and color checks.
- `colorblind_assistant/agent.py` and `models.py`: OpenAI interface and structured decisions.
- `colorblind_assistant/pipeline.py` and `cli.py`: processing, reports, publication, CLI.
- `tests/`: fixtures and automated regression checks.

Deferred: scans/OCR, other color-vision deficiencies, web interface, and reusable skill packaging.

MIT license.
