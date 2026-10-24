# MVP validation record

Date: 24 October 2026.

## Scope of the evidence

The five-page sample in `output-controlled-qa/` uses controlled, deterministic responses from `tests/sample_responses.py`. No real OpenAI request generated that sample. A separate production run in `output-live-qa/` now records real OpenAI responses; its results and limitations are below.

## Automated checks

All 29 tests passed using `python -m unittest discover -v`, including the subsequent .env loading change. Coverage includes the supplied five-page PDF, an independent synthetic chart, original text and geometry preservation, color contrast, matching chart and legend cues, transformed hatching and occlusion, copied-label placement, rejected or uncertain edits, unsupported content, API failures, bounded revision, CLI exit codes, environment precedence, and rollback after publication errors or interruption. The installed environment also passed `python -m pip check`.

## Controlled sample visual review

All five corrected pages and all five corrected protanopia simulations were inspected.

- Bar categories retain matching legend colors and patterns; original values and labels remain.
- Both line series retain their data geometry. One is dashed, and copied labels identify both series near their endpoints. A mapping note explains the original red/green wording.
- Pie segments and their legend share matching colors and patterns. Status wording remains visible with preserved or improved contrast.
- The heatmap retains every value, row, and column. Its lightness ordering is monotonic, and a note explains that darker cells mean higher values.
- Regional names and growth values remain present and readable.
- No newly added label or mapping note clips or covers existing content.

The pie's unusual white center and tight legend/status spacing are present in the source PDF. The assistant preserves the source geometry rather than inventing replacement chart data.

## Reader feedback

A reader who self-identified as having protanopia reviewed the five-page controlled sample and reported that it looked good to them. This is positive qualitative feedback from one reader. Task accuracy, reading time, and broader user performance were not measured.

This feedback applies to the controlled sample, not to arbitrary documents or untested live AI proposals. New CLI runs correctly start with reader feedback marked pending.

## Live API validation

The production CLI processed the supplied five-page fixture using the configured `gpt-6.1-sol` model and the key in the ignored local `.env` file. All ten API calls completed (one proposal and one review per page). Recorded API time totaled 131.02 seconds; reported usage was 69,075 input tokens and 7,889 output tokens, or 76,964 tokens total. These are API usage records, not a cost estimate or a performance benchmark.

The run exported all five pages, twenty previews, and both reports to `output-live-qa/`. Original text, dimensions, page count, and geometry checks passed. Its result is **partial**, with four pages changed and every page carrying review warnings. All five exported page previews and their protanopia simulations were visually inspected; the new labels and mapping notes remain within the page and do not cover existing content.

- Page 1 stays unchanged: the East and West bars use shades that do not exactly match the legend, and the model marked their category associations uncertain.
- Page 2 has a dashed blue series, a solid orange series, copied endpoint labels, and a mapping note preserving the original red/green wording. It received one revision and still needs reader review.
- Page 3 has matching colors and patterns on the pie and department legend. The proposed status-box recoloring was rejected by the separation check, so the status boxes retain their original colors. The possible relationship between pie and status colors remains unresolved.
- Page 4 preserves all sixteen values and their positions, with a monotonic blue scale and a note that lighter cells mean higher values.
- Page 5 retains region names and growth values. Several colors remain similar under simulation; existing text labels are still necessary for identification.

Some model warnings describe the initial candidate before its allowed revision. The applied-change entries identify what actually reached the exported PDF. Reader feedback on this live output is still pending; the earlier positive feedback must not be attributed to it.

## Outstanding validation

- Resolve or explicitly retain the live run's ambiguous bar associations and page 3 color correspondence before presenting it as a fully corrected demo.
- Have a reader with protanopia compare identification tasks on the live output and record remaining difficulties.
- Gather task-based feedback on additional documents when expanding support.
