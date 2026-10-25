---
name: colorblind-pdf-fixer
description: Make PDF documents more readable for protanopia by daltonizing images and using vision to fix remaining problems.
---

# Colorblind PDF Fixer Skill

## When to use
- Transform a PDF document to make it more readable for people with protanopia (red-green color blindness).

## Workflow
When processing a PDF page:
1. Extract the PDF images (XObjects) & charts with the pdf tools see `references/pdf_chart_image_extraction_reference.md`.
2. Create a protanopia preview of each image with DaltonLens (`python -m daltonlens input_image.png simulated_image.png --model vienot --filter simulate --deficiency protan --severity 1.0`).
3. Send each original image and its simulation to the vision model. Ask it to follow `references/correction-rules.md`, identify evidenced categories and propose only supported corrections, ALWAYS keep the intent of the original image.
4. Apply the accepted fixes to the corresponding images, preserving image dimensions and placements.
5. Recreate the PDF with the corrected images while preserving all other page content.
6. Verify the result and create review previews:
   ```
   python scripts/verify_output.py input.pdf improved.pdf --preview-dir output/previews
   ```
   Fix any reported failure and inspect the previews before delivering `improved.pdf`.
7. Deliver the improved PDF to the user with explanation of each change. In case of failure, provide a clear explanation of what could not be safely changed and why.

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
