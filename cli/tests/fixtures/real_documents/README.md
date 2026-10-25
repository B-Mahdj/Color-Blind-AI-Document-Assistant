# Real documents for reader-task testing

Collected and inspected on 25 October 2026. This set adds **six education PDFs and one everyday transport PDF** to the existing research and geography samples. Selection is based on tasks a reader needs to complete, rather than the number of colours on a page.

The [manifest](manifest.json) records publisher URLs, original-file SHA-256 hashes, page counts, selected pages, reader tasks and preservation requirements. Paths in the manifest are relative to the repository root. Downloaded originals and previews are under the Git-ignored [`output/pdf/everyday-learning/`](../../../../output/pdf/everyday-learning/) directory. They remain separate, unmodified PDFs; third-party material is not included in this commit or covered by this repository's MIT licence.

## Suggested starting order

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

## What was verified

- All seven downloads have a PDF header, parse successfully, are unencrypted and have recorded page counts and SHA-256 hashes.
- The primary page for each case was rendered and visually inspected alongside a simulation from the existing `colorblind_assistant.colors.simulated_image` helper: DaltonLens Vienot 1999, protanopia, severity 1.0.
- Original and simulated PNG dimensions match. The NASA preview is rotated for reading; its source PDF is unchanged.
- Additional original pages inspected: L03 pages 24, 27 and 28; L04 pages 2 and 3; L05 page 5. These provide context and unchanged controls, not additional simulated cases.

These are **candidate accessibility problems inferred from source inspection and simulation**, not results from colour-blind participants. Protanopia simulation is not daltonization, a corrected output, or evidence about every type of colour-vision deficiency.

## How to test a correction

1. Start with L01 and L02, where colour represents graph or map data. Record the reader's answer to the manifest task and whether they can follow the intended curve or category. Use full-size pages, consistent zoom and the same task before and after.
2. Compare original, original simulation, candidate and candidate simulation. Check task answers and legend/diagram consistency, as well as text, geometry, links and page preservation. A more colourful result alone is not a pass.
3. Use L03 page 27 and L06's labelled table as unchanged controls. Avoid unnecessary changes to already usable content.
4. Use L04 and L05 to test semantic preservation. Where a safe change cannot be established, retain the original and report `skipped` or `needs_review`. A safe skip is not a claim that the reader's accessibility need has been solved.
5. Have readers with the relevant colour-vision deficiency attempt the tasks before claiming usability improvements. Record errors and assistance needed; simulation alone is only triage.

No correction run or participant evaluation has been performed for this set. The manifest is a manual-test catalogue, not an automated benchmark. To restore downloads on another machine, fetch the recorded publisher URLs and verify their hashes before reusing the page annotations; publisher URLs may later serve different editions. Public availability does not establish permission to redistribute or modify every source.
