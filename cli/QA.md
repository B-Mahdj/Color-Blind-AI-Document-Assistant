# MVP validation record

Date: 24 October 2026.

The CLI, fixtures, and local output folders now live under `cli/`. Historical run reports retain the absolute paths recorded when those runs were produced; the PDFs and preview images were moved without changing their contents. New runs record the new locations.

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

## CLI and skill folder separation

The application, tests, generator, configuration, and local outputs were moved into `cli/`; the migration plan is in `skill/`. The repository's existing `.venv/` was retained and its editable installation refreshed for `cli/`.

All 30 tests and the dependency consistency check passed from the new CLI directory. Both module and console entry points were checked, and the eight-page stress generator reproduced its existing PDF byte-for-byte. Local documentation links and nested ignore rules were verified. Runtime modules and test contents are unchanged, the private `.env` was preserved, and 89 generated files were verified unchanged during relocation. No new live API run was needed. The skill folder is preparation only; it contains no runnable skill yet.

## Research sampler expansion

On 24 October 2026, the expanded implementation passed all **48 tests** with `python -m unittest discover -s tests -q`. The new cases cover nested and reused Forms, clipping and hidden text, link annotations, instance-local edits, source dash patterns at different scales, bounded flat-color bitmaps, dense curve/legend encodings, caption legends, note placement, and exported document preservation. The original tests still pass.

The final evaluation uses the original 48-page `Research_Excerpt_Sampler.pdf`. Its SHA-256 remains `9177c902503ffe5dbda2bc13526c3ed64ffe926a7ae75f716587a0b71b32a8ff`. The output is `output-research-sampler-v5/improved.pdf`, with SHA-256 `2ffbb6276b59711269b5a93b3791e35d72a1a8ba27f4107cf80cc5e3f58a5a36` and size 40,969,228 bytes.

The baseline changed pages 44 and 46. The final output visibly changes **12 pages: 6, 10, 24, 25, 26, 35, 36, 37, 39, 44, 45, and 46**. Accepted changes comprise 410 recolors, 75 dash changes, 38 hatches, nine mapping notes, and four copied labels. These are applied actions, not counts of fully accessible charts. Pages 24-26 change the threshold tables only; their dense NIST curves remain unchanged. Page 10 changes the 19-trajectory panel only, not the six-gene panels. Page 45 now has 32 matched curve/legend encodings using eight colors and four line styles.

An independent export check rendered every output page and compared it pixel-for-pixel with its corrected preview. All 48 matched. Original previews also match the baseline on all 48 pages, actual changed-page numbers match the applied-group records, and recursive original text/geometry checks pass. All 44 bookmarks and 118 links, including their destinations, are preserved. The machine-readable evidence is `output-research-sampler-v5/verification.json`.

This evaluation used real `gpt-6.1-sol` responses. To avoid repeating identical paid analysis while iterating on the editor, it reused 48 recorded proposal/revision responses for this exact input, revalidated by the current implementation. Ten previously approved reviews were reused only when both the rendered candidate pixels and applied-group records were identical. Seven reviews were fresh live requests. The report identifies this as `openai_with_verified_decision_reuse`; none of the final decisions came from controlled test responses. There were no final API failures. Some raw proposal warnings retain earlier wording about color names or unavailable dash information; the current applied changes and previews show the final state.

Visual checks covered the 12 changed-page contact sheets, full-size note/label examples, and the normal/protanopia comparison for the 32-curve page. The new notes fit in available whitespace. Dense crossings remain hard to trace. Page 36's copied labels contain only the source text fragments `SSP1-` and `SSP3-`; the complete original scenario labels remain visible. On page 44, the added Product B label is near both series at their right ends, so its association still needs reader review; the dashed orange style and color key provide the other cues. These limitations are not an accessibility pass.

The overall result remains **partial**: 44 pages are marked `needs_review`, three `unchanged`, and one `corrected`. These statuses include protected content and unresolved associations rather than whole-page parser failures. Photos, gradients, masked/profiled bitmaps, ambiguous repeated curve encodings, and edits without safe label space remain protected. Flat-color bitmap recoloring is verified by regression fixtures; no bitmap recoloring was accepted in this real sampler. Reader validation of this 48-page output is **pending**.

## Short research sampler

The user requested at least a 50% reduction. `scripts/shorten_research_sampler.py` creates matching **23-page** original and processed editions, retaining 20 examples from 17 sources. The selection keeps wavelength spectra, titration/dilution, drosophila and SVT material, dense official charts, and the local controls, including both changed and unresolved figures. The 48-page input files remain unchanged.

Outputs are `../output/pdf/Research_Sampler_Short_Original.pdf` and `../output/pdf/Research_Sampler_Short_Processed.pdf`. A companion manifest records source URLs, the old-to-new page mapping, and input/output hashes. The figures remain native PDF content where available. This is an editorial shortening of the existing documents, with no new AI requests or accessibility corrections.

The generation self-checks passed for both PDFs: 23 pages, 20 working contents destinations, 21 correctly targeted bookmarks, and preserved example-page source links. All 40 retained example bodies render pixel-identically to the corresponding full-edition pages at 1.2 scale; only the case badge and page-number regions are excluded from this comparison. Both 48-page input hashes remain unchanged. All 46 output pages were rendered and inspected through contact sheets; the source index and control-page footer were also inspected at full size. Contents, case numbers, source-index page references, and visible page counters use the new pagination.

The processed short edition inherits the v5 corrections and its unresolved limitations. The previous run report uses full-edition page numbers; use the new manifest to translate them. Reader validation remains pending.
