---
name: colorblind-pdf-fixer
description: Make PDF documents more readable for protanopia by daltonizing images and using vision to fix remaining problems.
---

# Colorblind PDF Fixer Skill

## When to use

- Transform a PDF document to make it more readable for people with protanopia (red-green color blindness).

## Workflow

1. Inspect PDF images and charts with `pypdf` and `pypdfium2`. Extract embedded raster images; render vector charts for review, remembering that rendering does not recover editable chart geometry.
2. Create a protanopia preview of each image with DaltonLens:
   ```
   python -m daltonlens input_image.png simulated_image.png --model vienot --filter simulate --deficiency protan --severity 1.0
   ```
   A simulation is a review preview, not a corrected image.
3. Compare each original image with its simulation using vision. Follow the correction rules below, identify evidenced categories, and propose only supported corrections. Always preserve the original intent.
4. Apply supported fixes while preserving image dimensions, placements, and all other page content. Save the corrected PDF as a separate file; never overwrite the source.
5. Verify the result against the source: page count, media and crop boxes, rotation, and original selectable text must be preserved. Render every output page and inspect before-and-after previews in both ordinary and simulated views. Check that labels, values, legends, and chart geometry remain intact. If verification fails, retain the original and report what needs review.
6. Deliver the improved PDF with an explanation of each change. Identify any figures left unchanged and explain what could not be safely corrected and why.

## Correction rules

- Establish category meaning from legends, direct labels, values, or explicit source text. Never infer meaning from color similarity alone.
- Apply each replacement consistently to matching chart marks and legend symbols. Choose colors distinguishable in the simulation with readable contrast against nearby text and backgrounds.
- Preserve numeric values, category meaning, and the image's original intent. Do not recolor photographs or colors that are themselves data, such as spectral bands or microscopy channels.
- Recolor sequential numeric scales only when the complete key and low-to-high direction are clear. Keep lightness monotonic and numeric labels intact; preserve any meaningful midpoint in diverging scales and neutral no-data categories.
- For categorical charts, use recoloring and hatching when supported by known shape boundaries or reliable pixel masks. Keep hatching inside the shape, away from text, and consistent with the legend symbol.
- For line charts, use dashed, dotted, or dash-dot styles only when each curve and legend sample are confidently matched. Apply the same style to both.
- Add labels only by copying existing source text or values, without covering chart content. If surrounding text names original colors, preserve it and add a concise mapping note.
- Leave uncertain or unsupported figures unchanged and report them as `skipped` or `needs_review`. Do not apply speculative edits to ambiguous categories, boundaries, or chart geometry.

## Dependencies (install if missing)

Prefer `uv` for dependency management. Requires Python 3.11 or later.

```
uv pip install pypdf pypdfium2 reportlab Pillow numpy daltonlens
```

If `uv` is unavailable:

```
python3 -m pip install pypdf pypdfium2 reportlab Pillow numpy daltonlens
```

PDF rendering uses the bundled PDFium library from `pypdfium2`; `pdfplumber` and Poppler are not required. No helper scripts are bundled with this definition; use the installed libraries to perform the workflow and verification.

If installation isn't possible in this environment, tell the user which dependency is missing and how to install it locally.

## Environment

No required environment variables.
