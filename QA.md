# MVP validation record

Date: 24 October 2026.

## Scope of the evidence

The five-page sample in `output-controlled-qa/` uses controlled, deterministic responses from `tests/sample_responses.py`. No real OpenAI request generated that sample. A separate production run in `output-live-qa/` now records real OpenAI responses; its results and limitations are below.

## Automated checks

All 30 tests passed using `python -m unittest discover -v`, including .env loading and the reader-feedback palette revision. Coverage includes the supplied five-page PDF, an independent synthetic chart and status boxes, original text and geometry preservation, color contrast, matching chart and legend cues, transformed hatching and occlusion, copied-label placement, rejected or uncertain edits, unsupported content, API failures, bounded revision, CLI exit codes, environment precedence, and rollback after publication errors or interruption. The installed environment also passed `python -m pip check`.

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

## First live API validation

The production CLI processed the supplied five-page fixture using the configured `gpt-6.1-sol` model and the key in the ignored local `.env` file. All ten API calls completed (one proposal and one review per page). Recorded API time totaled 131.02 seconds; reported usage was 69,075 input tokens and 7,889 output tokens, or 76,964 tokens total. These are API usage records, not a cost estimate or a performance benchmark.

The run exported all five pages, twenty previews, and both reports to `output-live-qa/`. Original text, dimensions, page count, and geometry checks passed. Its result is **partial**, with four pages changed and every page carrying review warnings. All five exported page previews and their protanopia simulations were visually inspected; the new labels and mapping notes remain within the page and do not cover existing content.

- Page 1 stays unchanged: the East and West bars use shades that do not exactly match the legend, and the model marked their category associations uncertain.
- Page 2 has a dashed blue series, a solid orange series, copied endpoint labels, and a mapping note preserving the original red/green wording. It received one revision and still needs reader review.
- Page 3 has matching colors and patterns on the pie and department legend. The proposed status-box recoloring was rejected by the separation check, so the status boxes retain their original colors. The possible relationship between pie and status colors remains unresolved.
- Page 4 preserves all sixteen values and their positions, with a monotonic blue scale and a note that lighter cells mean higher values.
- Page 5 retains region names and growth values. Several colors remain similar under simulation; existing text labels are still necessary for identification.

Some model warnings describe the initial candidate before its allowed revision. The applied-change entries identify what actually reached the exported PDF.

The reader with protanopia subsequently reported that this live output was hard to read globally, especially the difference between "At risk" and "Delayed." They preferred the earlier controlled sample. This live output **did not pass reader validation**: its unchanged red status colors are a concrete remaining failure. The local report records this feedback; the earlier positive feedback must not be attributed to the live result.

## Revised live API validation

After that feedback, the production reviewer now receives generic source-to-new-color suggestions using the palette from the preferred sample. Suggestions check the page's existing text and line contrast, apply consistently to identical source colors, and identify text-free shapes eligible for matching hatches. They use vector data rather than fixture page numbers or label names. Semantic associations still require model evidence and local validation.

The new run is saved separately in `output-live-qa-v2/`. All ten calls completed with `gpt-6.1-sol`, recording 114.60 seconds of API time and 81,107 total tokens. All five pages received changes, and original text, page dimensions, page count, and geometry checks passed. All five page previews and all five corrected simulations were visually inspected.

Page 3 now uses orange for "On track," blue for "At risk," purple for "Delayed," and dark gray for "Completed," with matching pie and legend colors. Both the normal page preview and the protanopia simulation are pixel-identical to page 3 of the reader-preferred controlled sample. The page passed AI review without warnings.

The processing result remains **partial**. East and West on page 1 remain unchanged because their category mappings are uncertain; the other bars and their matching legend symbols are corrected. Pages 1 and 2 received one revision and retain their recorded review warnings. Pages 3-5 passed AI review. Existing region labels remain important where colors look similar under simulation.

The reader with protanopia reviewed this revised live output and described it as "way better," specifically highlighting the color changes and the grid/hatching patterns. This is positive qualitative feedback on the actual live result from one reader. Identification accuracy and reading time were not measured, and the feedback does not resolve the East and West category mappings. The revised output's JSON and Markdown reports now record this feedback.

## Outstanding validation

- Resolve or explicitly retain the East and West bar associations before presenting a fully corrected demo.
- Measure identification accuracy and reading time in a structured comparison if broader usability claims are needed.
- Gather task-based feedback on additional documents when expanding support.

## Repository publication review

On 24 October 2026, the automated suite was rerun: all 30 tests passed and `python -m pip check` found no broken requirements. No new live API call was needed for this documentation and publication change.

The review checked the tracked working files and all reachable Git history, including commit messages, for the configured local OpenAI key (without printing it), its base64 representation, common provider-token formats, private keys, credential-bearing URLs, and suspicious credential assignments. At the starting commit `7c4a946`, this covered 13 commits and 52 distinct file blobs. No secret matches or historical private environment files were found. The final documentation and ignore changes were scanned again before publication.

The sole tracked PDF is the supplied test fixture. Its extracted text and decoded page streams were checked; its metadata is generic, and it contains no attachments or document-level automatic action. The Git remote contains no embedded credentials. `.env`, generated outputs, environments, logs, and temporary processing folders are excluded from the intended publication; `.env.example` contains an empty key field.

These are scoped publication checks, not a penetration test or a dependency-vulnerability audit. Pattern matching cannot prove that every possible secret format is absent. The documented unsupported PDF types and unresolved reader-validation issues remain unchanged.
