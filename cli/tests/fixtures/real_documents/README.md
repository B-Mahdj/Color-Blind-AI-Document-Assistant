# Real documents for reader-task testing

Collected and inspected on 25 October 2026. This set contains **ten education PDFs and one everyday transport PDF**, including two data-visualisation courses and two finance learning resources. Selection is based on tasks a reader needs to complete, rather than the number of colours on a page.

The [manifest](manifest.json) records publisher URLs, original-file SHA-256 hashes, page counts, selected pages, reader tasks and preservation requirements. Paths in the manifest are relative to the repository root. Downloaded originals and previews are under the Git-ignored [`output/pdf/everyday-learning/`](../../../../output/pdf/everyday-learning/) directory. They remain separate, unmodified PDFs; third-party material is not included in this commit or covered by this repository's MIT licence.

## Selected top three

1. **L08 - Visual Encoding, PDF page 57:** the clearest first test of identifying categories through a scatterplot legend when small coloured marks overlap.
2. **L11 - Technical Analysis, PDF page 163:** a practical finance task involving red/green candles and indicator identities. Use PDF page 162 for the indicator legend.
3. **L09 - Color, PDF page 49:** a harder diverging-heatmap task that must preserve the **1:1** ratio reference and both directions. Test visible cells only; the source figure is clipped at the bottom.

This first batch covers categorical, financial direction and diverging-scale reading. The ranking is based on the inspected original/protanopia pairs, not participant results.

## Short excerpts ready to test

The main test chart is **page 3 in each excerpt**. Ranges below use original, 1-based PDF page numbers and include both endpoints. Visual Encoding pages 55-60 make six pages; the other two excerpts contain five pages each.

| Case | Short PDF | Original PDF pages | Excerpt pages |
| --- | --- | --- | --- |
| L08 | [UW Visual Encoding](../../../../output/pdf/everyday-learning/excerpts/UW_Visual_Encoding_PDF_55-60.pdf) | 55-60 | 6 |
| L11 | [Zerodha Technical Analysis](../../../../output/pdf/everyday-learning/excerpts/Zerodha_Technical_Analysis_PDF_161-165.pdf) | 161-165 | 5 |
| L09 | [UW Color](../../../../output/pdf/everyday-learning/excerpts/UW_Color_PDF_47-51.pdf) | 47-51 | 5 |

The excerpts retain native PDF content, selectable text and source colours. All 16 pages were checked against their originals: content streams, text, page boxes, rotation, link annotations and rendered pixels match. The original files' hashes are unchanged. [Verification evidence](../../../../output/pdf/everyday-learning/excerpts/excerpt-verification.json) records each page mapping and output hash. The existing source crop on the heatmap remains.

## Skill-processed versions

The selected short excerpts were processed with `colorblind-pdf-fixer` on 25 October 2026. [Download the three corrected PDFs and read the change/skip report](skill_runs/2026-10-25.md). Nine figures were recolored across the 16 pages; all three outputs passed the skill verifier and additional preservation checks. [Compare original and corrected protanopia previews](../../../../output/pdf/everyday-learning/skill-run-2026-10-25/before-after-protanopia.png). These candidates still need reader testing, including the unchanged teaching examples and ambiguous annotations identified in the report.

## Source catalogue

All page references below are **1-based PDF pages**. Open the original PDFs at a readable zoom; the [comparison overview](../../../../output/pdf/everyday-learning/original-vs-protanopia.png) is for triage. Full-size original and simulated page renders are in [`previews/`](../../../../output/pdf/everyday-learning/previews/).

| Case | Document and local original | Pages | Reader task and useful test boundary |
| --- | --- | --- | --- |
| L01 | [BTS maths resources, Académie de Versailles](https://euler.ac-versailles.fr/IMG/pdf/ressources_partie2.pdf) ([local PDF](../../../../output/pdf/everyday-learning/bts-maths-graphs.pdf)) | **42** | Follow four temperature curves, identify their letters, and estimate when they reach 10 degrees C. Green and yellow become harder to separate in the preview. Check the curve identities and coordinates, including the magenta reference line. |
| L02 | [Géosciences Olympiad, 2011, hosted by Académie de Versailles](https://svt.ac-versailles.fr/IMG/pdf/geosciences_2011_sujet_nw.pdf) ([local PDF](../../../../output/pdf/everyday-learning/geosciences-exam-2011.pdf)) | **4** | Match ocean-floor regions to the age legend. Several pink, orange, brown and green categories converge in the simulation. Keep the entire legend, inset and category-to-region mapping together. |
| L03 | [Tanguy Jean, reproduction and genetics course, prépa TB](https://www.svt-tanguy-jean.com/uploads/1/2/0/4/120408978/tb-16-reproduction-genetique.pdf) ([local PDF](../../../../output/pdf/everyday-learning/svt-meiosis-course.pdf)) | **40**; context 24, 28; control 27 | Compare mitosis and meiosis, then follow chromosome segments through recombination. The summary mixes red/green headings, small diagrams and blue/orange chromosome identities. Some parts already have text or line-weight cues; those should be allowed to remain unchanged. |
| L04 | [NASA, Exploring Color Maps](https://www.nasa.gov/stem-content/exploring-color-maps-visualizing-the-ozone-hole/) ([local PDF](../../../../output/pdf/everyday-learning/nasa-exploring-color-maps.pdf)) | **4**; questions/answers 2; control 3 | Compare maps A-D of the same sea-temperature data. Map C supplies a useful alternative scale. The deliberate differences between scales and the 27.8 degrees C breakpoint in D are part of the lesson: normalising all four palettes would damage the exercise. Preserve this comparison and offer separate explanation or mark it for review. |
| L05 | [Collège Jean Jaurès, Chapitre 4: le pH](https://clg-jaures-poissy.ac-versailles.fr/IMG/pdf/Chap_4_partie_2_le_pH.pdf) ([local PDF](../../../../output/pdf/everyday-learning/chemistry-ph-lesson.pdf)) | **3**; text support 5 | Use the pH wheel and read the numerical meter. Adjacent wheel colours become less distinct. The wheel is a photograph of a physical measurement reference: retain its colours and provide a separate textual explanation or an explicit review result. |
| L06 | [Éduscol, Quelle solution choisir pour détartrer?](https://eduscol.education.fr/document/22993/download) ([local PDF](../../../../output/pdf/everyday-learning/eduscol-household-ph.pdf)) | **8** | Find the BBT transition interval and its named colours, then locate the numerical measurement alternative. The labelled table is an accessible-support control beside a small photograph of pH paper. Preserve the table and measurement photograph; colour changes to decorative headers are not a useful success metric. |
| L07 | [RATP, Paris Métro map](https://www.ratp.fr/informer/picts/plans/pdf/reseaux/metro.pdf) ([local PDF](../../../../output/pdf/everyday-learning/paris-metro-map.pdf)) | **1** | Follow RER A and D between Châtelet-Les Halles and Gare de Lyon using the letter badges and connections. Thin coloured routes and crossings test continuity. Preserve official route identities, station names and interchange topology. The downloaded map is marked 01.2026; this is a test snapshot. |

## Data visualisation and finance learners

The [additional comparison overview](../../../../output/pdf/everyday-learning/dataviz-finance-original-vs-protanopia.png) shows the four new primary pages. Start with L08 for category identification and L11 for financial chart reading.

| Case | Document and local original | Pages | Reader task and useful test boundary |
| --- | --- | --- | --- |
| L08 | [University of Washington CSE512, Visual Encoding](https://courses.cs.washington.edu/courses/cse512/25sp/lectures/CSE512-VisualEncoding.pdf) ([local PDF](../../../../output/pdf/everyday-learning/uw-visual-encoding.pdf)) | **57**; context 30, 58 | Use the scatterplot legend to identify the product category below -$500 profit and the category with the highest-profit point. Small coloured circles overlap; green and orange categories lose separation. Page 58 adds shapes for **market**, not product type: do not mistake this for redundant product-category encoding. Page 30 separately compares a red/green heatmap with positional encoding. |
| L09 | [University of Washington CSE512, Color](https://courses.cs.washington.edu/courses/cse512/25sp/lectures/CSE512-Color.pdf) ([local PDF](../../../../output/pdf/everyday-learning/uw-colour-lecture.pdf)) | **49**; context 44, 50 | Locate the **1:1** reference on the red/green heatmap scale, then distinguish cells on opposite sides of that reference. The simulation collapses opposing hues. Preserve the ratio reference, direction, cell locations, dendrogram and legend together; do not invent negative values or a zero midpoint. The source figure is already clipped at the bottom: test visible cells only. Palette-design demonstrations on other pages need separate review. |
| L10 | [MIT OpenCourseWare, Portfolio Choice recitation](https://ocw.mit.edu/courses/15-401-finance-theory-i-fall-2008/resources/portfolio-theory/index.html) ([local PDF](../../../../output/pdf/everyday-learning/mit-portfolio-choice.pdf)) | **15**; context 16, 18 | Follow the four labelled correlation curves on the expected-return/risk diagram and identify which reaches the lowest risk near 10% expected return. Thin green/orange curves become similar in simulation. Keep correlation labels, dash patterns, endpoints, axis units and curve geometry intact. |
| L11 | [Zerodha Varsity, Technical Analysis](https://zerodha.com/varsity/module/technical-analysis/) ([local PDF](../../../../output/pdf/everyday-learning/zerodha-technical-analysis.pdf)) | **163**; context 14, 162; control 15 | Distinguish red/green candles and match the three lower indicator lines to their right-edge numeric badges. The candle and indicator hues converge in simulation. Page 15 gives labelled candle anatomy and numerical examples as a control. This book changes candle palettes between chapters; apply page-specific meaning, and keep any changed chart colours consistent with surrounding explanations. |

Financial examples are historical teaching snapshots. The task is to read the supplied chart accurately; it does not require judging a trading strategy or choosing an investment. PDF page numbers differ from printed page numbers in the Varsity book: PDF page 163 is printed page 162.

## What was verified

- All eleven downloads have a PDF header, parse successfully, are unencrypted and have recorded page counts and SHA-256 hashes.
- The primary page for each case was rendered and visually inspected alongside a simulation from the existing `colorblind_assistant.colors.simulated_image` helper: DaltonLens Vienot 1999, protanopia, severity 1.0.
- Original and simulated PNG dimensions match. The NASA preview is rotated for reading; its source PDF is unchanged.
- Additional original pages inspected: L03 pages 24, 27 and 28; L04 pages 2 and 3; L05 page 5. These provide context and unchanged controls, not additional simulated cases.
- Additional original pages inspected for the extension: L08 pages 30 and 58; L09 pages 44 and 50; L10 pages 16 and 18; L11 pages 14, 15 and 162. Four new primary pages have full-size original/protanopia pairs; originals remain unchanged.
- `pypdf` reports recoverable cross-reference warnings for L08 and L09, and a cache warning for the earlier L05. The selected pages render successfully. Retain the source bytes and distinguish any future parsing problem from a colour-accessibility result.

These are **candidate accessibility problems inferred from source inspection and simulation**, not results from colour-blind participants. Protanopia simulation is not daltonization, a corrected output, or evidence about every type of colour-vision deficiency.

## How to test a correction

1. For the selected first batch, use L08, L11 and L09 in that order. L01 and L02 remain useful graph/map follow-ups. Record the reader's answer to the manifest task and whether they can follow the intended mark, line or category. Use full-size pages, consistent zoom and the same task before and after.
2. Compare original, original simulation, candidate and candidate simulation. Check task answers and legend/diagram consistency, as well as text, geometry, links and page preservation. A more colourful result alone is not a pass.
3. Use L03 page 27 and L06's labelled table as unchanged controls. Avoid unnecessary changes to already usable content.
4. Use L04 and L05 to test semantic preservation. Where a safe change cannot be established, retain the original and report `skipped` or `needs_review`. A safe skip is not a claim that the reader's accessibility need has been solved.
5. Have readers with the relevant colour-vision deficiency attempt the tasks before claiming usability improvements. Record errors and assistance needed; simulation alone is only triage.
6. For L08-L11, preserve category identity, ratio references and the financial chart's numerical meaning. Assess chart reading, not simulated trading returns. L11's labelled examples provide a check against assigning candle direction from hue alone.

A correction run has been completed for the three selected short excerpts; participant evaluation remains outstanding. The manifest is a manual-test catalogue, not an automated benchmark. To restore downloads on another machine, fetch the recorded publisher URLs and verify their hashes before reusing the page annotations; publisher URLs may later serve different editions. Public availability does not establish permission to redistribute or modify every source.
