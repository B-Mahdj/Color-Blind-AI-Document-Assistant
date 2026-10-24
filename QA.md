# MVP validation record

Date: 24 October 2026.

## Scope of the evidence

The five-page sample in `output-controlled-qa/` uses controlled, deterministic responses from `tests/sample_responses.py`. No real OpenAI request generated this sample. Production uses the OpenAI reviewer; its integration was exercised with the real SDK and mocked HTTP responses.

## Automated checks

All 28 tests passed using `python -m unittest discover -v`. Coverage includes the supplied five-page PDF, an independent synthetic chart, original text and geometry preservation, color contrast, matching chart and legend cues, transformed hatching and occlusion, copied-label placement, rejected or uncertain edits, unsupported content, API failures, bounded revision, CLI exit codes, and rollback after publication errors or interruption. The installed environment also passed `python -m pip check`.

## Visual review

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

## Outstanding validation

- Run the production CLI with a real OpenAI API key and confirm model access, proposal quality, latency, and actual token usage.
- Review any live generated PDF and its unresolved warnings before presenting it as the AI-produced demo.
- Gather task-based feedback on additional documents when expanding support.
