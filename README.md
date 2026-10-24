# Color-Blind Document Assistant

**Make any PDF easier to read for people with protanopia.**

Upload a PDF containing charts, graphs, or colored diagrams. The tool detects color combinations that collapse under protanopia, remaps them, adds secondary cues when needed, and returns an improved version with a clear explanation of what changed.

Built for the OpenAI DevDay Community Hackathon (Paris) — Impact track (Disability inclusion).

## Problem

Many documents use red and green (or similar pairs) as the only way to distinguish data.  
For people with **protanopia**, these colors often become hard or impossible to tell apart. Existing tools either simulate the problem or require manual recoloring. None offer a simple “upload a PDF → get a readable version with explanations.”

## Solution

A pipeline that:

1. Accepts a PDF
2. Detects problematic color pairs for protanopia
3. Applies a protanopia-specific remapping (daltonize)
4. Uses OpenAI Vision + an agent layer to judge the result and patch remaining issues (labels, milder palette, etc.)
5. Shows a side-by-side view with a short explanation
6. Exports an improved PDF + summary

**Scope of this version:** Protanopia only.

## Demo

<!-- Replace with actual before/after once available -->

| Original | Improved (protanopia-friendly) |
|----------|--------------------------------|
| ![before](demo/before.png) | ![after](demo/after.png) |

**Example explanation:**  
“The red and green bars on page 1 had similar lightness and collapsed under protanopia. They were shifted toward safer hues and direct labels were added to the legend.”

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/colorblind-document-assistant.git
cd colorblind-document-assistant
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set your OpenAI key
cp .env.example .env
# Edit .env and add OPENAI_API_KEY=sk-...

# Run on the included test document
python src/main.py tests/Test_Document_Protanopia.pdf
```

Output:
- `output/improved.pdf`
- `output/explanation.txt`
- Side-by-side preview images

## How it works

```
PDF → pages to images
     → color analysis + protanopia simulation (daltonize, type=p)
     → protanopia-only remapping
     → OpenAI Vision (compare original vs remapped)
     → Agent decision layer (conflicts, labels, explanation)
     → side-by-side + export
```

## Project structure

```
├── README.md
├── pitch.md                  # Full pitch document
├── src/
│   ├── main.py               # Entry point
│   ├── pdf_processor.py
│   ├── color_analysis.py
│   └── agent.py
├── tests/
│   └── Test_Document_Protanopia.pdf
├── demo/
│   ├── before.png
│   └── after.png
├── requirements.txt
└── .env.example
```

## Test document

A 5-page PDF with bar charts, line charts, pie charts, heatmaps, and status indicators using red-green combinations is included:

`tests/Test_Document_Protanopia.pdf`

It was designed so the color distinctions are difficult under protanopia.

## Tech stack

- Python
- `daltonize` (protanopia simulation + remapping)
- OpenAI API (Vision + structured decisions)
- PDF handling (`pypdf` / `pdf2image` or equivalent)
- ReportLab or similar for output assembly

## Roadmap (post-hackathon)

- [ ] Support deuteranopia and tritanopia
- [ ] Severity slider
- [ ] Multi-page batch processing
- [ ] Codex skill packaging
- [ ] Simple web interface

## Team

- [Your name]

## License

MIT

---

*Personal motivation: built by someone with color vision deficiency.*
