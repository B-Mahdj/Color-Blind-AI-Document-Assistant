from io import BytesIO
from pathlib import Path
import unittest

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from colorblind_assistant.pdf import inspect_page, single_page_bytes, assert_preserved


FIXTURE = Path(__file__).parent / "fixtures" / "Test_Document_Protanopia.pdf"


def synthetic_pdf():
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=(400, 400))
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(40, 360, "Comparison")
    pdf.setFillColorRGB(.8, .1, .1)
    pdf.rect(50, 100, 50, 100, fill=1, stroke=0)
    pdf.rect(50, 60, 12, 12, fill=1, stroke=0)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(70, 62, "Group X")
    pdf.setFillColorRGB(.1, .6, .15)
    pdf.rect(150, 100, 50, 150, fill=1, stroke=0)
    pdf.rect(150, 60, 12, 12, fill=1, stroke=0)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(170, 62, "Group Y")
    pdf.save()
    return out.getvalue()


class PDFTests(unittest.TestCase):
    def test_fixture_inventory_and_preservation(self):
        reader = PdfReader(FIXTURE)
        self.assertEqual(len(reader.pages), 5)
        for number, page in enumerate(reader.pages, 1):
            data = inspect_page(page, number)
            self.assertTrue(data.supported, data.warnings)
            self.assertGreater(len(data.elements), 3)
            self.assertTrue(data.text)
            assert_preserved(page, PdfReader(BytesIO(single_page_bytes(page))).pages[0])

    def test_independent_synthetic(self):
        page = PdfReader(BytesIO(synthetic_pdf())).pages[0]
        data = inspect_page(page, 1)
        self.assertTrue(data.supported, data.warnings)
        self.assertEqual(len(data.elements), 4)
        self.assertIn("Group X", [text.text for text in data.text])

    def test_transformed_path(self):
        output = BytesIO()
        pdf = canvas.Canvas(output)
        pdf.drawString(20, 20, "Text")
        pdf.saveState()
        pdf.translate(50, 70)
        pdf.scale(2, 3)
        pdf.rect(10, 20, 30, 40, fill=1)
        pdf.restoreState()
        pdf.save()
        data = inspect_page(PdfReader(BytesIO(output.getvalue())).pages[0], 1)
        self.assertEqual(data.elements[0].bbox, (70, 130, 130, 250))

    def test_cmyk_and_rotation_are_unsupported(self):
        output = BytesIO()
        pdf = canvas.Canvas(output)
        pdf.drawString(20, 20, "Text")
        pdf.setFillColorCMYK(0, 1, 1, 0)
        pdf.rect(20, 40, 30, 40, fill=1)
        pdf.save()
        page = PdfReader(BytesIO(output.getvalue())).pages[0]
        self.assertFalse(inspect_page(page, 1).supported)
        page = PdfReader(BytesIO(synthetic_pdf())).pages[0]
        page.rotate(90)
        self.assertFalse(inspect_page(page, 1).supported)


if __name__ == "__main__":
    unittest.main()
