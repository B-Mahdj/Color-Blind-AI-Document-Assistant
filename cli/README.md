# Color-Blind Document Assistant

A Python CLI for readers with **protanopia**. It improves supported digital PDFs using color changes, hatching, line styles, and direct labels while retaining original selectable text, values, page layout, and chart geometry.

Built for the OpenAI DevDay Community Hackathon in Paris, Impact track.

## Run on Windows

Requires Python 3.11 or later, internet access for OpenAI, and an API key with access to the configured model. Start in the repository root; the virtual environment stays there, and the application runs from `cli/`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .\cli
Set-Location cli

# Create the local settings file if it does not already exist, then add your key.
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
notepad .env

..\.venv\Scripts\python.exe -m colorblind_assistant tests\fixtures\Test_Document_Protanopia.pdf --output-dir output
$LASTEXITCODE
```

After installing the dependencies, open `.env`, paste your key after `OPENAI_API_KEY=`, and save it before running the CLI. Virtual environments are machine-specific and are not committed.

The default model is `gpt-6.1-sol`. Change `OPENAI_MODEL` in `cli/.env` to use another compatible model available to your account. The CLI automatically reads `.env` from the **current working directory**, so run it from `cli/`. Existing environment variables take precedence over `.env`. Only `OPENAI_API_KEY` and `OPENAI_MODEL` are used from the file; variable expansion is disabled. [.env.example](.env.example) documents the settings. The private `.env` file and generated outputs are ignored by Git.

The installed `colorblind-assistant` command is equivalent to `python -m colorblind_assistant`. On macOS/Linux, install from the repository root with `.venv/bin/python -m pip install -e ./cli`, then use `cd cli` and `../.venv/bin/python` for the commands below. Edit `.env` in your preferred editor.

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
- Native text and RGB, grayscale, CMYK, and supported ICC vector colors, including affine transformations, clipping, ordinary link annotations, and nested Form XObjects.
- Opaque normal graphics states are supported. Unsupported effects protect the affected objects rather than automatically blocking the entire page.
- Up to 1,200 editable targets and 30,000 extracted text characters after filtering invisible/neutral objects and bundling small same-color fragments. Individual source paints remain intact.
- Flat-color RGB/grayscale bitmap figures have a separate categorical palette path. Replacements are lossless, preserve dimensions and neutral pixels, and affect only the selected image invocation, including its embedded legend. Profiled/CMYK bitmaps remain protected until a dedicated color-managed conversion is implemented.
- Source text remains in its original language. CLI messages and generated explanations are English.
- Added labels copy source words; decorative bullet prefixes are omitted. Helvetica Latin characters, including French accents, are supported. Other glyphs are rejected.

Photos, gradients, continuous/diverging bitmap scales, masked images, shading, spot/pattern colors, real transparency/overprint, and text clipping remain protected. Bitmap colors that are themselves measurements (such as spectral colors or microscopy channels) must not be remapped as categories. Bitmap OCR, hatching, and line-style editing are not implemented. Rotated/cropped/offset page boxes, nonstandard user units, and non-link/custom-appearance annotations still block a page. Encrypted PDFs and interactive forms are rejected as complete inputs. Every page remains in the export; inspect the per-page coverage and warnings to distinguish editable figures from protected content.

Run again from the **original PDF** when changing settings. PDFs already containing assistant cues are not correction inputs for this initial version.

## How corrections work

1. `pypdf` recursively inventories original paths, clipping, nested figures, and bitmap palettes; `pypdfium2` extracts text positions and renders page images. The model receives sampled curve trajectories and original dash patterns as well as bounding boxes. Extracted text hidden by clipping is marked as source context and is excluded from placement obstacles.
2. DaltonLens simulates protanopia using Viénot 1999 at severity `1.0`.
3. OpenAI receives original page images, a simulated view, extracted text, stable element IDs, and a consistent categorical palette informed by reader feedback. Suggested colors are checked against existing text and line contrast; they do not establish category associations. Structured responses propose atomic groups of chart/legend corrections.
4. Local code validates IDs, colors, legend consistency, text contrast in normal and simulated views, scale ordering, and available space. Unknown or uncertain groups remain unchanged. Neutral structural graphics cannot be edited.
   Scientific captions can serve as textual legends when they explicitly name every recolored source color. Their original wording stays intact and a mapping note is mandatory; overlapping curve boxes are never used to infer which color word belongs to which curve.
5. Color and dash changes are scoped to original paint operations. Edited Form/image invocation branches are cloned so shared copies elsewhere do not change. Clipped hatching retains drawing order. Label placement checks actual stroked paths rather than treating a curve's entire bounding rectangle as occupied. Bitmap palette masks use original pixels, preventing cascading replacements.
6. The AI reviews the rendered candidate. It may approve, reject, or provide one replacement plan. A revision is applied from the original page and marked for human review; there is no unbounded loop or second AI review of that revision.
7. Before publication, the pipeline reopens the PDF and verifies page dimensions, nested text/geometry operations, image dimensions, annotations, and extractable text. The export retains bookmarks and internal link destinations. Reports describe accepted edits only.

Simulation distances are ranking heuristics. Numeric geometry checks cannot prove an AI's interpretation of a legend; real-reader review remains important.

## Data and API behavior

OpenAI analysis is enabled by default. Supported pages' rendered content and extracted text leave the machine. Calls use `store=False`, a 60-second request timeout, and at most one SDK retry per call. Each supported page uses one proposal call and, if a correction was proposed, one review call. No tools, code execution, or filesystem access are exposed to the model. Instructions inside a document are treated as untrusted content.

Local reports contain document text, absolute file paths, and usage metadata; keep them as private as the source document. API error bodies and credentials are not copied into reports. Access to the default model must be verified with your own API account.

Git excludes `.env`, `.env.*` (except the empty `.env.example` template), logs, virtual environments, standard `output/` and `output-*/` folders, and temporary `.colorblind-*/` staging folders. Outputs written to a differently named directory need their own ignore rule before committing. The supplied five-page test fixture is deliberately versioned; generated previews and live-run reports are local only.

## Tests and demo evidence

Run these commands from `cli/`:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -v
```

Tests run without an API key or network. They cover the five-page fixture, independent synthetic charts, original-content preservation, group rejection, contrast, label placement, hatch occlusion, API parsing through the real SDK with mocked HTTP, bounded revision, exit handling, and transactional overwrite.

For a larger manual evaluation input, generate the eight-page synthetic stress document:

```powershell
..\.venv\Scripts\python.exe scripts\generate_stress_pdf.py
..\.venv\Scripts\python.exe -m colorblind_assistant output\pdf\Protanopia_Chart_Stress_Test.pdf --output-dir output-stress-test
```

The generator runs locally without API calls. It includes 10-, 20-, and 32-curve charts, 48 grouped bars, a pie and status cards, a 96-cell heatmap, regional scorecards, and an answer key. Its colors are deliberately confusing under protanopia simulation. The generator checks parser support for all eight pages, the curve counts, and the application's per-page limits; successful generation does not establish correction quality. The second command runs the actual OpenAI-backed correction pipeline.

`tests/sample_responses.py` supplies **controlled test responses only**. It is never selected by the production CLI. The local `output-controlled-qa/` sample is identified as such in its reports. It demonstrates the PDF engine; it is not evidence of live model performance.

See [QA.md](QA.md) for visual review and positive qualitative reader feedback on the controlled sample. A separate live run with `gpt-6.1-sol` completed all ten API calls and produced `output-live-qa/`: four pages changed, one remained unchanged, and unresolved issues correctly yielded a partial result. The reader found that live output harder to read, especially "At risk" versus "Delayed"; it has not passed reader validation.

The revised live result in `output-live-qa-v2/` restores the preferred status colors. Its entire page 3 preview, including its simulation, matches the first controlled sample exactly. It applies changes on all five pages while retaining the two ambiguous bars and review warnings. All 30 automated tests pass. The reader with protanopia found the revised live output much better, especially the color changes and grid/hatching patterns. This is qualitative feedback from one reader; identification accuracy and reading time were not measured.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the Mermaid workflow and the files/functions responsible for each step.

See [the skill migration plan](../skill/PROJECT_PLAN.md) for completed milestones, the overall architecture, and the proposed migration to an installable skill containing instructions and references. The migration is a plan; no skill package has been implemented yet.

- `colorblind_assistant/pdf.py`: inventory, rendering, preservation checks.
- `colorblind_assistant/editor.py` and `colors.py`: bounded edits and color checks.
- `colorblind_assistant/raster.py`: flat-color image inventory and lossless palette replacement.
- `colorblind_assistant/agent.py` and `models.py`: OpenAI interface and structured decisions.
- `colorblind_assistant/pipeline.py` and `cli.py`: processing, reports, publication, CLI.
- `tests/`: fixtures and automated regression checks.

Deferred: scans/OCR, other color-vision deficiencies, web interface, and reusable skill packaging.

MIT license.
