# CLI workflow and code map

The pipeline processes one page at a time. OpenAI proposes and reviews changes; local Python code validates and applies every PDF edit. Rendering provides analysis images and previews. The exported PDF retains its original text and vector geometry.

```mermaid
flowchart TD
    A["1. Start CLI<br/>__main__.py → cli.main()"] --> B["2. Load arguments, .env and model<br/>cli.py + agent.py"]
    B --> C["3. Validate input and output paths<br/>pipeline.process_document()"]
    C --> D["4. Render and inspect next page<br/>pdf.py"]
    D --> E{"Supported page?"}
    E -->|No| U["Keep original page and record warnings<br/>pipeline.py"]
    E -->|Yes| F["5. Simulate protanopia and suggest palette<br/>colors.py + agent.py"]
    F --> G["6. OpenAI proposes structured actions<br/>agent.propose() + models.py"]
    G --> H["7. Validate groups and apply accepted edits<br/>editor.apply_plan()"]
    G -. API failure .-> U
    H --> I{"Any groups proposed?"}
    I -->|No| J["8. Check preserved content and save previews<br/>pdf.py + colors.py + pipeline.py"]
    I -->|Yes| K["OpenAI reviews rendered candidate<br/>agent.review()"]
    K --> L{"Review result"}
    L -->|Approved| J
    L -->|Replacement plan| R["Validate and apply ONE revision from original<br/>editor.py; flag for human review"]
    R --> J
    L -->|Rejected| U
    K -. API failure .-> U
    U --> J
    J --> M{"More pages?"}
    M -->|Yes| D
    M -->|No| N["9. Assemble PDF and recheck preservation<br/>pipeline.py + pdf.py"]
    N --> O["10. Write reports and publish staged outputs<br/>pipeline.write_markdown() + _publish()"]
    O --> P["improved.pdf<br/>report.md + report.json<br/>previews: four images per page"]
    P --> Q["11. JSON result and exit code<br/>cli.py"]
    P -. Manual review .-> V["12. Reader feedback<br/>QA.md + sample reports"]
    B -. Configuration error .-> X["Failure result<br/>cli.py"]
    C -. Invalid input or destination .-> X
    J -. Preservation check fails .-> X
    N -. Preservation check fails .-> X
    O -. Publication fails .-> X
```

## Files and functions for each step

This document and all CLI files live under the repository's `cli/` directory. All Python modules below are inside `cli/colorblind_assistant/`; supporting file paths are relative to `cli/` unless stated otherwise.

| Step | File and main code | Responsibility |
| --- | --- | --- |
| 1 | `__main__.py`; `cli.py:main()` | Starts `python -m colorblind_assistant` and parses CLI arguments. |
| 2 | `cli.py:main()`; `agent.py:OpenAIReviewer.__init__()` | Reads `.env` from the current directory, gives environment variables precedence, checks credentials, and initializes the API client. |
| 3 | `pipeline.py:process_document()`, `_validate_destination()` | Checks file size, page count, encryption/forms, output collisions, and input protection. |
| 4 | `pdf.py:inspect_page()`, `compact_fragments()`, `text_runs()`; `raster.py:inspect_image()` | Recurses through Form invocations, tracks transforms/clipping/graphics states, protects unsupported objects, and inventories vector paths and flat-color image palettes. |
| 5 | `colors.py:simulated_image()`, `simulated_rgb()`, `contrast()`, `color_metrics()`; `agent.py:categorical_color_guidance()` | Runs Viénot protanopia simulation at severity 1.0, calculates contrast/separation heuristics, and offers consistent colors and eligible hatch targets. |
| 6 | `agent.py:OpenAIReviewer.propose()`, `_request()`; `models.py:Action`, `CorrectionGroup`, `PagePlan`, `PageReview` | Sends page images, text, inventory, and palette guidance to OpenAI. Parses a strict structured response. Document contents are treated as untrusted data. |
| 7 | `editor.py:_validate_group()`, `apply_plan()` | Rejects uncertain or invalid groups; checks known IDs, legend consistency, contrast, scale ordering, and placement; applies accepted changes atomically per group. |
| Review/revision | `agent.py:OpenAIReviewer.review()`; `pipeline.py:process_document()` | Reviews the candidate once. Approves it, restores the original, or applies one replacement plan from the original. That revision is flagged for human review. |
| 8 | `pdf.py:assert_preserved()`, `preservation_signature()`; `pipeline.py:process_document()` | Checks original text/geometry operations and page dimensions. Saves original, corrected, and simulated versions of both. |
| 9-10 | `pipeline.py:process_document()`, `write_markdown()`, `_publish()` | Assembles every page, rechecks the export, writes reports from applied changes, and publishes staged outputs with rollback on recoverable publication errors. |
| 11 | `cli.py:main()` | Sends progress to stderr, a JSON result to stdout, and exit codes 0, 1, 2, or 3. |
| 12 | `QA.md`; output `report.json` and `report.md` | Manually records visual checks and reader feedback. Each new CLI run starts with feedback pending. |

## Where the visible corrections are implemented

| Correction | Implementation |
| --- | --- |
| Change fill/stroke colors | `editor.py:_edit_objects()` inserts scoped PDF color operations around existing paints, cloning edited Form invocation branches. |
| Recolor a bitmap category | `raster.py:recolor_image()` classifies original pixels against the complete source palette and changes selected masks; `image_stream()` writes lossless RGB. |
| Add diagonal/grid patterns | `editor.py:_hatch_operations()` clips hatch strokes to the original shape and preserves drawing order. |
| Change line style | `editor.py:apply_plan()` inserts dashed or dotted stroke settings. |
| Add an existing source label | `editor.py:_place()` checks text, fills, protected objects, and sampled stroke intersections; `_overlay()` draws copied Latin text using ReportLab. |
| Explain changed color references | `editor.py:_mapping_note()` generates a note from accepted changes; `_place()` and `_overlay()` position and draw it. |

## Supporting files

- `pyproject.toml`: dependencies, package metadata, and the installed `colorblind-assistant` entry point.
- `.env.example`: configuration template. The local `.env` is ignored through the repository-root `.gitignore`.
- `README.md`: installation, Windows commands, outputs, exit codes, and support limits.
- `QA.md`: automated, visual, live API, and reader-validation evidence.
- `tests/test_pdf.py`: PDF inventory, transformations, preservation, and an independent synthetic fixture.
- `tests/test_editor.py`: bounded edits, contrast, legend checks, placement, and hatch occlusion.
- `tests/test_extended_pdf.py`: clipped/nested/shared figures, scoped transparency, bitmap masks, dense fragments, French labels, 32-curve encodings, and nested preservation failures.
- `tests/test_agent.py`: structured API requests through mocked HTTP, error handling, and palette guidance.
- `tests/test_pipeline.py`: complete processing, reports, CLI codes, configuration, overwrite, and rollback.
- `tests/sample_responses.py`: deterministic test responses for controlled QA only; production uses `OpenAIReviewer`.
- `tests/fixtures/Test_Document_Protanopia.pdf`: the supplied five-page test document.

## Boundaries

An unsupported page remains unchanged and is included in the complete export. An invalid correction group remains unchanged while other validated groups may proceed. API failures retain the affected original page and appear in the report; fatal configuration/API errors stop subsequent API calls. Document-level or preservation failures stop publication.

Within an inspectable page, unsupported effects are recorded as protected objects. They remain placement obstacles and are never offered as editable targets. The report's coverage counts separate editable targets, original vector paints, eligible bitmap figures, and protected objects. Fragment bundles reduce model input; they do not assert that all same-color marks have the same meaning, and support recoloring only. Clipping bounds used for inventory filtering are conservative rectangles; original clipping paths remain in the PDF.

The bitmap path handles categorical flat colors only. A vision proposal must identify a readable embedded legend/direct labels. This does not provide OCR, segmentation of individual crossing bitmap curves, or scientific validation of a palette's meaning. Photos, continuous scales, masked images, and measurement colors need separate strategies.

The loop allows one proposal, one review, and at most one revision per page. Reader feedback is a manual validation step that informs later code changes. A successful processing run does not by itself establish readability for a reader with protanopia.
