# Map support fixes

Baseline: geography 0/7 changed, Real Maps 0/6 changed (QA at `db7263d`).

1. **Bounded parsing and Form isolation.** Scope a six-million-token pypdf parsing budget to the production pipeline. Accept trailing saved states inside a Form's isolated graphics scope; keep restore underflows and page-level imbalance rejected. Test scope restoration and unchanged geometry.
2. **Actual painted areas.** Use filled paths and individual fragments for text-overlap checks rather than their enclosing rectangles. Keep contrast checks on actual overlaps. Give the model explicit action eligibility and consistent palette guidance for larger categorical maps.
3. **Map images and their keys.** Decode supported ICC/CMYK images, extract stable colors from compressed maps, preserve neutral pixels and unmatched image content, and edit related bitmap/vector legends atomically. Add an ordered-raster association with a validated monotonic palette; sample the complete numeric key when dominant colors omit its rare endpoints. Retain incomplete or ambiguous source information rather than inventing it.
4. **Accurate revision reports.** Distinguish evaluated revisions from accepted changes and retain actionable rejection reasons.
5. **Verification and delivery.** Add targeted regression cases, run the full suite, rerun both PDFs with the normal CLI, check exported geometry/text/links and normal/protanopia renders, record remaining issues, and commit locally.

Scope: `pdf.py`, `raster.py`, `editor.py`, `models.py`, `agent.py`, `pipeline.py`, dependency minimum if needed, their callers/tests, README and QA. No new UI, whole-page rasterization, fabricated legends, or weakened preservation checks.

Resource configuration follows [pypdf's scoped configuration API](https://pypdf.readthedocs.io/en/latest/user/security.html#configuration). Results must distinguish successful edits from complete accessibility; reader validation remains separate.

Implementation checkpoints: `eaabf73` added the first four fixes and passed 60 tests. Real reruns then exposed partial numeric-key conversion and inconsistent suggestions for close vector paint variants. Complete-key sampling, shared contrast constraints for confirmed variants, and filled-path label placement bring the regression suite to 64 passing tests. Final live-run and export findings are recorded in `QA.md`; unresolved source content must remain explicit.

Final verification: all 66 tests pass at `557afa9`. Geography has accepted changes on 6/7 pages and Real Maps on 4/6, compared with 0/13 initially. Export/preview pixels, original characters and positions, page boxes, links/bookmarks and unchanged source hashes pass. The geography blank-map regression passes in PDF.js without JPEG 2000 assets. Final live-run provenance, exact affected figures and unresolved cases are recorded in `QA.md` and `../output/pdf/Map_Fixes_QA.md`; reader validation remains pending.
