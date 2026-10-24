from io import BytesIO
import unittest

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from colorblind_assistant.colors import hex_color, simulated_image
from colorblind_assistant.editor import apply_plan
from colorblind_assistant.models import Action, CorrectionGroup, PagePlan
from colorblind_assistant.pdf import assert_preserved, inspect_page, render, text_runs
from tests.test_pdf import synthetic_pdf


def legend_plan(data, color="#005A9C", hatch=True):
    targets = [item.id for item in data.elements if item.fill == (.8, .1, .1)]
    label = next(item for item in data.text if item.text == "Group X")
    actions = [Action(kind="recolor", target_ids=targets, channel="fill", color=color)]
    if hatch:
        actions.append(Action(kind="hatch", target_ids=targets, style="diagonal"))
    return PagePlan(groups=[CorrectionGroup(id="group-x", reason="Use the source legend.",
                    evidence_text_ids=[label.id], association="legend", legend_ids=[targets[-1]],
                    uncertain=False, actions=actions)], warnings=[])


class EditorTests(unittest.TestCase):
    def setUp(self):
        self.page = PdfReader(BytesIO(synthetic_pdf())).pages[0]
        self.data = inspect_page(self.page, 1)

    def test_color_and_hatch_preserve_original(self):
        result = apply_plan(self.page, self.data, legend_plan(self.data))
        self.assertFalse(result.warnings, result.warnings)
        self.assertEqual(len(result.groups), 1)
        after = PdfReader(BytesIO(result.pdf)).pages[0]
        assert_preserved(self.page, after)
        self.assertIn("Group X", after.extract_text())
        image = render(result.pdf)
        self.assertEqual(simulated_image(image).size, image.size)

    def test_unknown_and_uncertain_are_atomic(self):
        for change in ("unknown", "uncertain"):
            plan = legend_plan(self.data)
            if change == "unknown":
                plan.groups[0].actions[0].target_ids.append("does-not-exist")
            else:
                plan.groups[0].uncertain = True
            result = apply_plan(self.page, self.data, plan)
            self.assertFalse(result.groups)
            self.assertTrue(result.warnings)
            assert_preserved(self.page, PdfReader(BytesIO(result.pdf)).pages[0])

    def test_legend_not_updated_is_rejected(self):
        plan = legend_plan(self.data)
        for action in plan.groups[0].actions:
            action.target_ids = action.target_ids[:1]
        result = apply_plan(self.page, self.data, plan)
        self.assertFalse(result.groups)
        self.assertIn("legend", result.warnings[0].lower())

    def test_hatch_cannot_obscure_existing_text(self):
        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=(300, 300))
        pdf.setFillColorRGB(.8, .1, .1)
        pdf.rect(40, 100, 160, 60, fill=1, stroke=0)
        pdf.setFillColorRGB(1, 1, 1)
        pdf.drawString(60, 120, "Existing label")
        pdf.save()
        page = PdfReader(BytesIO(output.getvalue())).pages[0]
        data = inspect_page(page, 1)
        group = CorrectionGroup(id="box", reason="Keep the label", evidence_text_ids=[data.text[0].id],
                                association="direct_labels", legend_ids=[], uncertain=False,
                                actions=[Action(kind="hatch", target_ids=[data.elements[0].id], style="diagonal")])
        result = apply_plan(page, data, PagePlan(groups=[group], warnings=[]))
        self.assertFalse(result.groups)
        self.assertIn("obscure", result.warnings[0])
        group.actions = [Action(kind="recolor", target_ids=[data.elements[0].id], channel="fill", color="#FFFFFF")]
        result = apply_plan(page, data, PagePlan(groups=[group], warnings=[]))
        self.assertFalse(result.groups)
        self.assertIn("contrast", result.warnings[0])

    def test_label_copies_existing_words_and_is_in_whitespace(self):
        plan = legend_plan(self.data, hatch=False)
        group = plan.groups[0]
        group.actions.append(Action(kind="label", target_ids=[group.actions[0].target_ids[0]], source_text_id=group.evidence_text_ids[0]))
        result = apply_plan(self.page, self.data, plan)
        self.assertFalse(result.warnings, result.warnings)
        after = PdfReader(BytesIO(result.pdf)).pages[0]
        assert_preserved(self.page, after)
        self.assertEqual(after.extract_text().count("Group X"), 2)

    def test_invalid_color_is_rejected(self):
        result = apply_plan(self.page, self.data, legend_plan(self.data, color="blue"))
        self.assertFalse(result.groups)
        self.assertIn("hexadecimal", result.warnings[0])


if __name__ == "__main__":
    unittest.main()
