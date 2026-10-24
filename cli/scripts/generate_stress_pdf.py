"""Build a deliberately color-confusing, deterministic PDF for manual evaluation.

Run from the cli directory: python scripts/generate_stress_pdf.py
All data is synthetic. This generates an input, not an accessible output.
"""

import math
from pathlib import Path
import sys

from pypdf import PdfReader
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from colorblind_assistant.pdf import inspect_page
from colorblind_assistant.colors import separation

OUTPUT = ROOT / "output/pdf/Protanopia_Chart_Stress_Test.pdf"
WIDTH, HEIGHT = landscape(A4)
INK, MUTED, RULE = "#172126", "#526168", "#DDE2E4"

# Adjacent red/green pairs nearly coincide in the repo's protanopia simulation.
# They are intentional test hazards, not a recommended visualization palette.
PAIRS = [
    ("#D21E28", "#40522C"), ("#B41822", "#384624"),
    ("#EE352A", "#48662C"), ("#9D1226", "#303A28"),
    ("#E84C20", "#087224"), ("#C64120", "#006224"),
    ("#862329", "#303A2C"), ("#EC6043", "#507E44"),
]
COLORS = [color for pair in PAIRS for color in pair] + [
    "#BE2932", "#296B38", "#DA392A", "#4B7330",
    "#A62C24", "#3D6130", "#F05437", "#548B3E",
    "#AC3B31", "#42723B", "#CA4935", "#5A8140",
    "#8F332B", "#3B5632", "#DC5A41", "#658D45",
]
SCHOOLS = ["Aster", "Birch", "Cedar", "Dune", "Elm", "Fern",
           "Grove", "Harbor", "Iris", "Juniper", "Kite", "Linden"]
COUNTRIES = ["France", "Germany", "Spain", "Italy", "Portugal", "Belgium",
             "Netherlands", "Denmark", "Sweden", "Norway", "Finland", "Ireland",
             "Austria", "Switzerland", "Poland", "Czechia", "Greece", "Croatia",
             "Romania", "Hungary"]


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = Canvas(str(OUTPUT), pagesize=(WIDTH, HEIGHT), pageCompression=1,
                 invariant=1, pdfVersion=(1, 4))
    pdf.setTitle("Protanopia Chart Stress Test - Synthetic Evaluation Pack")
    pdf.setAuthor("Color-Blind Document Assistant")
    pdf.setSubject("Synthetic charts with intentionally confusing colors")
    answers = []

    def text(x, y, value, size=10, color=INK, bold=False, align="left"):
        value = str(value)
        font = "Helvetica-Bold" if bold else "Helvetica"
        width = stringWidth(value, font, size)
        start = x - width if align == "right" else x - width / 2 if align == "center" else x
        assert 18 <= start and start + width <= WIDTH - 18, value
        assert 18 <= y and y + size <= HEIGHT - 12, value
        pdf.setFont(font, size)
        pdf.setFillColor(HexColor(color))
        pdf.drawString(start, y, value)

    def rect(x, y, w, h, color, border=None):
        pdf.setFillColor(HexColor(color))
        if border:
            pdf.setStrokeColor(HexColor(border))
            pdf.setLineWidth(.5)
        pdf.rect(x, y, w, h, fill=1, stroke=int(border is not None))

    def line(x1, y1, x2, y2, color=RULE, width=.6):
        pdf.setStrokeColor(HexColor(color))
        pdf.setLineWidth(width)
        pdf.line(x1, y1, x2, y2)

    def header(number, title, subtitle, badge):
        text(42, 570, "COLOR LAB  /  SYNTHETIC EVALUATION PACK", 8, MUTED, True)
        text(42, 539, title, 25, bold=True)
        text(42, 518, subtitle, 10.5, MUTED)
        text(800, 547, badge, 10, MUTED, True, "right")
        line(42, 501, 800, 501)
        line(42, 38, 800, 38)
        text(42, 23, "FICTIONAL DATA  |  Colors are intentionally difficult for protanopia.  |  Original test input", 8, MUTED)
        text(800, 23, f"{number:02d} / 08", 8, MUTED, align="right")

    def tasks(page, items):
        assert len(items) == 2
        text(42, 91, "READING CHECK", 8, MUTED, True)
        for i, (question, answer) in enumerate(items):
            text(42, 75 - 15 * i, f"{page}.{i + 1}  {question}", 9)
        answers.append((page, items))

    def axes(ymin, ymax, yticks, xticks, unit, bounds=(75, 210, 715, 265)):
        x, y, w, h = bounds
        text(x, y + h + 9, unit, 9, MUTED)
        for val in yticks:
            py = y + (val - ymin) / (ymax - ymin) * h
            line(x, py, x + w, py)
            text(x - 10, py - 3, f"{val:g}", 8, MUTED, align="right")
        for fraction, label in xticks:
            px = x + fraction * w
            line(px, y, px, y + h, "#EDF0F1", .4)
            text(px, y - 16, label, 8, MUTED, align="center")
        line(x, y, x + w, y, MUTED)
        line(x, y, x, y + h, MUTED)
        def convert(i, count, value):
            assert ymin <= value <= ymax, (unit, value, ymin, ymax)
            return (x + i / (count - 1) * w,
                    y + (value - ymin) / (ymax - ymin) * h)
        return convert

    def curves(series, convert, markers=False):
        for index, values in enumerate(series):
            points = [convert(i, len(values), v) for i, v in enumerate(values)]
            path = pdf.beginPath()
            path.moveTo(*points[0])
            for point in points[1:]:
                path.lineTo(*point)
            pdf.setStrokeColor(HexColor(COLORS[index]))
            pdf.setLineWidth(1.6 if markers else 1.25)
            pdf.drawPath(path)
            if markers:
                pdf.setFillColor(HexColor(COLORS[index]))
                for px, py in points:
                    pdf.circle(px, py, 2.1, fill=1, stroke=0)

    def legend(labels, colors, columns, top=170, kind="line", step=18):
        cell_width = 758 / columns
        for i, (label, color) in enumerate(zip(labels, colors, strict=True)):
            x, y = 42 + i % columns * cell_width, top - i // columns * step
            if kind == "line":
                line(x, y + 3, x + 19, y + 3, color, 2)
            else:
                rect(x, y - 1, 12, 10, color)
            text(x + 25, y, label, 8.6)

    header(1, "10 schools, 12 months", "Monthly science assessment scores across ten school cohorts.", "10 CURVES")
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    school_data = [[round(62 + .8 * t + 12 * math.sin(t * .72 + i * .8)
                         + 6 * math.cos(t * .39 + i * 1.2), 1)
                    for t in range(12)] for i in range(10)]
    point = axes(40, 100, range(40, 101, 10),
                 [(i / 11, m) for i, m in enumerate(months)], "Score / 100")
    curves(school_data, point, markers=True)
    legend(SCHOOLS[:10], COLORS[:10], 5, step=22)
    winner = max(range(10), key=lambda i: school_data[i][-1])
    tasks(1, [("Which school has the highest December score?",
               f"{SCHOOLS[winner]} - {school_data[winner][-1]:.1f} / 100."),
              ("In June, is Aster or Birch higher?",
               f"{'Aster' if school_data[0][5] > school_data[1][5] else 'Birch'} - Aster {school_data[0][5]:.1f}; Birch {school_data[1][5]:.1f}.")])
    pdf.showPage()

    header(2, "20 countries, overlapping trends", "Simulated renewable-output index. Country names are illustrative; these are not national statistics.", "20 CURVES")
    country_data = [[round(95 + .8 * t + 15 * math.sin(.32 * t + i * .73)
                          + 10 * math.cos(.49 * t + i * 1.21) + (i % 5 - 2) * .4 * t, 1)
                     for t in range(24)] for i in range(20)]
    point = axes(60, 160, range(60, 161, 20),
                 [(i / 23, label) for i, label in [(0, "Jan 23"), (3, "Apr 23"),
                  (6, "Jul 23"), (9, "Oct 23"), (12, "Jan 24"), (15, "Apr 24"),
                  (18, "Jul 24"), (23, "Dec 24")]], "Output index")
    curves(country_data, point)
    legend(COUNTRIES, COLORS[:20], 5)
    winner = max(range(20), key=lambda i: country_data[i][-1])
    gain = max(range(20), key=lambda i: country_data[i][-1] - country_data[i][0])
    tasks(2, [("Which country ends highest in December 2024?",
               f"{COUNTRIES[winner]} - index {country_data[winner][-1]:.1f}."),
              ("Which country gains the most between the first and last points?",
               f"{COUNTRIES[gain]} - gain of {country_data[gain][-1] - country_data[gain][0]:.1f} index points.")])
    pdf.showPage()

    header(3, "32 samples, crossing spectra", "Simulated absorbance spectra from a materials-science practical.", "32 CURVES")
    wavelengths = list(range(380, 781, 5))
    spectra = [[round(.08 + (.7 + (i % 7) * .055) * math.exp(-((w - 425 - i * 7) / (37 + i % 5 * 6)) ** 2)
                      + (.28 + i % 4 * .06) * math.exp(-((w - 640 + i % 9 * 9) / 64) ** 2)
                      + .025 * math.sin(w / 25 + i), 4) for w in wavelengths] for i in range(32)]
    point = axes(0, 1.8, [0, .3, .6, .9, 1.2, 1.5, 1.8],
                 [(i / 8, str(380 + 50 * i)) for i in range(9)], "Absorbance / a.u.")
    curves(spectra, point)
    text(790, 181, "Wavelength / nm", 8, MUTED, align="right")
    legend([f"Sample {i + 1:02d}" for i in range(32)], COLORS, 8, top=163, step=17)
    at_500, at_650 = wavelengths.index(500), wavelengths.index(650)
    winner = max(range(32), key=lambda i: spectra[i][at_500])
    tasks(3, [("Which sample has the highest absorbance at 500 nm?",
               f"Sample {winner + 1:02d} - {spectra[winner][at_500]:.3f} a.u."),
              ("At 650 nm, is Sample 01 or Sample 02 higher?",
               f"Sample {1 if spectra[0][at_650] > spectra[1][at_650] else 2:02d} - 01: {spectra[0][at_650]:.3f}; 02: {spectra[1][at_650]:.3f}.")])
    pdf.showPage()

    header(4, "12 schools, four subjects", "Synthetic end-of-term results. Every subject is identified by its fill color and legend.", "48 BARS")
    subjects = ["Mathematics", "Science", "Reading", "Writing"]
    bar_data = [[45 + (i * 17 + j * 13 + i * j * 5) % 51 for j in range(4)] for i in range(12)]
    point = axes(0, 100, range(0, 101, 20), [], "Score / 100", (75, 210, 715, 265))
    for i, school in enumerate(SCHOOLS):
        center = 75 + (i + .5) * 715 / 12
        for j, value in enumerate(bar_data[i]):
            x = center - 23 + j * 12
            rect(x, 210, 10, value / 100 * 265, COLORS[j])
            text(x + 5, 215 + value / 100 * 265, value, 6.8, align="center")
        text(center, 193, school, 7.6, MUTED, align="center")
    legend(subjects, COLORS[:4], 4, top=157, kind="box")
    top_science = max(range(12), key=lambda i: bar_data[i][1])
    tasks(4, [("Which school has the highest science score?",
               f"{SCHOOLS[top_science]} - {bar_data[top_science][1]} / 100."),
              ("At Cedar, does mathematics or reading score higher?",
               f"{'Mathematics' if bar_data[2][0] > bar_data[2][2] else 'Reading'} - mathematics {bar_data[2][0]}; reading {bar_data[2][2]}.")])
    pdf.showPage()

    header(5, "Research budgets and project status", "Two independent color legends: program allocation on the left, project status on the right.", "PIE + STATUS")
    programs = ["Imaging", "Genomics", "Materials", "Climate", "Robotics", "Chemistry", "Ecology", "Computing"]
    shares = [22, 18, 15, 13, 11, 9, 7, 5]
    assert sum(shares) == 100
    text(42, 476, "PROGRAM ALLOCATION", 9, MUTED, True)
    text(453, 476, "PROJECT STATUS", 9, MUTED, True)
    cx, cy, radius, angle = 223, 341, 111, 90
    for i, share in enumerate(shares):
        end = angle - share * 3.6
        path = pdf.beginPath()
        path.moveTo(cx, cy)
        for k in range(25):
            a = math.radians(angle + (end - angle) * k / 24)
            path.lineTo(cx + radius * math.cos(a), cy + radius * math.sin(a))
        path.close()
        pdf.setFillColor(HexColor(COLORS[i]))
        pdf.setStrokeColor(HexColor("#FFFFFF"))
        pdf.setLineWidth(1)
        pdf.drawPath(path, fill=1, stroke=1)
        angle = end
    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.circle(cx, cy, 54, fill=1, stroke=0)
    text(cx, cy + 2, "$2.4m", 23, bold=True, align="center")
    text(cx, cy - 16, "research budget", 9, MUTED, align="center")
    for i, (name, share) in enumerate(zip(programs, shares, strict=True)):
        x, y = 42 + i % 2 * 190, 205 - i // 2 * 22
        rect(x, y - 1, 12, 10, COLORS[i])
        text(x + 20, y, name, 9)
        text(x + 165, y, f"{share}%", 9, align="right")
    statuses = [("Atlas", "On track", COLORS[1]), ("Beacon", "At risk", COLORS[0]),
                ("Cobalt", "Delayed", COLORS[2]), ("Delta", "Completed", COLORS[3]),
                ("Echo", "Blocked", COLORS[6]), ("Flux", "Review", COLORS[4])]
    for i, (name, status, color) in enumerate(statuses):
        x, y = 453 + i % 2 * 181, 381 - i // 2 * 97
        rect(x, y, 166, 80, color)
        text(x + 15, y + 49, name, 14, "#FFFFFF", True)
        text(x + 15, y + 21, status, 11, "#FFFFFF")
    tasks(5, [("Which program corresponds to the second-largest pie segment?", "Genomics - 18%."),
              ("Which project is at risk, and which is delayed?", "Beacon is At risk; Cobalt is Delayed.")])
    pdf.showPage()

    header(6, "Team performance matrix", "Quarterly scores. The five colors encode ordered performance bands; each value is also printed.", "96 CELLS")
    bands = [(40, "#D21E28", "0-39"), (55, "#B54C20", "40-54"),
             (70, "#8B5B24", "55-69"), (85, "#66632A", "70-84"),
             (101, "#40522C", "85-100")]
    matrix = [[30 + (r * 17 + q * 11 + r * q * 3) % 69 for q in range(8)] for r in range(12)]
    for q in range(8):
        text(125 + q * 83 + 41.5, 472, f"Q{q % 4 + 1} {2024 + q // 4}", 8.5, MUTED, True, "center")
    for r, row in enumerate(matrix):
        y = 441 - r * 23
        text(110, y + 7, f"Team {r + 1:02d}", 9, align="right")
        for q, value in enumerate(row):
            color = next(color for upper, color, _ in bands if value < upper)
            rect(125 + q * 83, y, 81, 21, color)
            text(125 + q * 83 + 40.5, y + 6, value, 10, "#FFFFFF", align="center")
    legend([label for _, _, label in bands], [color for _, color, _ in bands], 5, top=153, kind="box")
    best = max(range(12), key=lambda r: matrix[r][7])
    low = sum(value < 40 for row in matrix for value in row)
    tasks(6, [("Which team has the highest score in Q4 2025?", f"Team {best + 1:02d} - {matrix[best][7]} / 100."),
              ("How many cells belong to the lowest band, 0-39?", f"{low} cells.")])
    pdf.showPage()

    header(7, "Regional scorecards", "Synthetic monthly changes. Similar reds and greens carry the status; signs and words provide backup cues.", "12 CARDS")
    regions = ["North", "South", "East", "West", "Central", "Coastal",
               "Highlands", "Valley", "Lakes", "Metro", "Islands", "Border"]
    changes = [-5.2, 5.4, -2.8, 2.9, -8.1, 8.4, -3.7, 3.8, -1.6, 1.7, -6.2, 6.5]
    for i, (region, change) in enumerate(zip(regions, changes, strict=True)):
        x, y = 42 + i % 4 * 194, 368 - i // 4 * 105
        rect(x, y, 176, 91, COLORS[i])
        text(x + 15, y + 65, region, 12, "#FFFFFF", True)
        text(x + 15, y + 34, f"{change:+.1f}%", 21, "#FFFFFF", True)
        text(x + 15, y + 15, "Below last month" if change < 0 else "Above last month", 8, "#FFFFFF")
    text(42, 128, "TEXT-ONLY INDICATORS", 8, MUTED, True)
    for x, label, value, color in [(215, "Attendance", "+4.2%", COLORS[1]),
                                  (416, "Completion", "-4.1%", COLORS[0]),
                                  (624, "Engagement", "+2.8%", COLORS[3])]:
        text(x, 127, label, 9)
        text(x + 88, 127, value, 10, color, True)
    tasks(7, [("Which region has the largest decline?", "Central - -8.1%."),
              ("What are the North and South monthly changes?", "North -5.2%; South +5.4%.")])
    pdf.showPage()

    header(8, "Reference answers", "Use these answers to check identification and value preservation after correction.", "ANSWER KEY")
    for index, (page, items) in enumerate(answers):
        x, y = 42 + index % 2 * 393, 470 - index // 2 * 88
        text(x, y, f"PAGE {page:02d}", 9, MUTED, True)
        for j, (_, answer) in enumerate(items):
            text(x, y - 21 - j * 20, f"{page}.{j + 1}  {answer}", 9)
    line(42, 107, 800, 107)
    text(42, 88, "This is a deliberately difficult input, not a model of accessible chart design.", 10, bold=True)
    text(42, 70, "All values are fictional. Colors repeat by role; line styles and marker shapes deliberately do not distinguish series.", 9, MUTED)
    text(42, 54, "Reading checks can reveal mistakes; they do not constitute a validated accessibility study.", 9, MUTED)
    pdf.showPage()
    pdf.save()


def verify():
    """Fail immediately if the fixture falls outside the application's input subset."""
    reader = PdfReader(OUTPUT)
    assert len(reader.pages) == 8
    assert len(set(COLORS)) == 32
    for red, green in PAIRS:
        rgb = lambda s: tuple(int(s[i:i + 2], 16) / 255 for i in (1, 3, 5))
        assert separation(rgb(red), rgb(green)) < .012
    for number, page in enumerate(reader.pages, 1):
        data = inspect_page(page, number)
        assert data.supported, (number, data.warnings)
        assert len(data.elements) <= 500
        assert sum(len(run.text) for run in data.text) <= 20000
        assert "FICTIONAL DATA" in page.extract_text()
        if number <= 3:
            traces = [element for element in data.elements
                      if element.stroke is not None and len(element.commands) > 8
                      and element.fill is None]
            assert len(traces) == (10, 20, 32)[number - 1], (number, len(traces))
        print(f"Page {number}: supported; {len(data.elements)} vector elements; {len(data.text)} text runs")
    print(f"Created {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
    verify()
