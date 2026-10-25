---
name: colorblind-pdf-fixer
description: Make PDF documents more readable for protanopia by daltonizing images and using vision to fix remaining problems.
---

# Colorblind PDF Fixer Skill

## When to use
- Transform a PDF document to make it more readable for people with protanopia (red-green color blindness).

## Workflow
When processing a PDF page:
1. Read `references/correction-rules.md`, then extract the PDF images (XObjects) with `pypdf`.
2. Create a protanopia preview of each image with DaltonLens (`python -m daltonlens input_image.png simulated_image.png --model vienot --filter simulate --deficiency protan --severity 1.0`).
3. Send each original image and its simulation to the vision model. Ask it to follow `references/correction-rules.md`, identify evidenced categories and propose only supported corrections.
4. Apply the accepted fixes to the corresponding images, preserving image dimensions and placements.
5. Recreate the PDF with the corrected images while preserving all other page content.
6. Verify the result and create review previews:
   ```
   python scripts/verify_output.py input.pdf improved.pdf --preview-dir output/previews
   ```
   Fix any reported failure and inspect the previews before delivering `improved.pdf`.


## Dependencies (install if missing)
Prefer `uv` for dependency management. Requires Python 3.11 or later.

Python packages:
```
uv pip install pypdf pypdfium2 reportlab Pillow numpy daltonlens
```
If `uv` is unavailable:
```
python3 -m pip install pypdf pypdfium2 reportlab Pillow numpy daltonlens
```
PDF rendering uses the bundled PDFium library from `pypdfium2`; `pdfplumber` and Poppler are not required.

If installation isn't possible in this environment, tell the user which dependency is missing and how to install it locally.

## Environment
No required environment variables.
## Worked example: categorical bar chart

The paired example in `assets/examples/` shows one source chart and a supported correction. Categories are established by the legend; the correction applies each color consistently to its bars and legend swatch, then adds hatching as a non-color cue. Keep the values and category meanings unchanged. Treat this as an example, not a fixed palette for other charts.

| Original | Corrected example |
| --- | --- |
| ![Original bar chart with red, green, and orange category fills](assets/examples/bar-chart-before.png) | ![Corrected bar chart with consistent blue, orange, and purple fills, with hatching on two categories](assets/examples/bar-chart-after.png) |
