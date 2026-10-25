# Colorblind PDF Fixer

A Codex skill for making PDF figures more readable for readers with **protanopia** while preserving document content and layout.

[Watch the product walkthrough (MP4)](docs/colorblind-pdf-fixer-demo.mp4)

## Before & after

**Bar chart — normal display colors.** Matching colors and hatching distinguish categories while keeping the original values and labels.

| Before | After |
| --- | --- |
| ![Original bar chart with red, green, and orange category fills](colorblind-pdf-fixer/assets/examples/bar-chart-before.png) | ![Corrected bar chart with blue, orange, and purple fills, with matching hatching in the bars and legend](colorblind-pdf-fixer/assets/examples/bar-chart-after.png) |

**Paris metro map — protanopia simulation.** The original and adapted map are shown under the same DaltonLens simulation, so you can compare the route distinctions being checked. These are simulated views, separate from the adapted PDF's actual colors.

![Original Paris metro map on the left and adapted map on the right, both under the same protanopia simulation](colorblind-pdf-fixer/assets/examples/maps/paris-metro-protanopia-comparison.png)

Map artwork: © RATP, January 2026. This adapted example is not an official RATP map. See the [full example and preservation checks](colorblind-pdf-fixer/README.md#example-paris-metro-map).

## Get started

Requires Codex with PDF-editing and visual-inspection capabilities, plus **Python 3.11+**. The [skill definition](colorblind-pdf-fixer/SKILL.md#dependencies-install-if-missing) lists the Python dependencies and installation commands.

Ask Codex to install the skill from GitHub:

```text
$skill-installer install the skill from
B-Mahdj/Color-Blind-AI-Document-Assistant
using the path colorblind-pdf-fixer
```

Restart Codex if the skill does not appear after installation.

Then attach your PDF and ask:

```text
Use $colorblind-pdf-fixer to improve this PDF for protanopia.
Save the result as improved.pdf, keep the original unchanged,
and explain the changes and anything that could not be safely corrected.
```

You receive the improved PDF, review previews, and an explanation of the changes and remaining limitations.

## How it works & limitations

1. **Inspect:** examine figures and their protanopia simulations, using existing labels, legends, and values to establish meaning.
2. **Correct:** apply supported color changes and non-color cues, such as hatching or line styles, consistently with the legend.
3. **Verify:** check page count, page boxes, rotation, original selectable text, and rendering, then visually review the result.

Uncertain categories are left unchanged and reported. Encrypted PDFs cannot be verified. Automated preservation checks do not establish that every visual distinction is readable; the previews still need review.

Some metro routes still share colors, including 6/7bis and 13/3bis. Adapted colors differ from official signage, so identify services by their route numbers and letters. Reader and physical-print testing were not performed; a simulation is not an accessibility certification.

See the [correction rules](colorblind-pdf-fixer/references/correction-rules.md) for supported changes and further examples. Report problems through [GitHub Issues](https://github.com/B-Mahdj/Color-Blind-AI-Document-Assistant/issues).

Project code is licensed under [MIT](LICENSE). Third-party artwork retains its stated attribution.
