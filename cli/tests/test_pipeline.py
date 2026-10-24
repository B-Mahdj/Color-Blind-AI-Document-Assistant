from contextlib import chdir, redirect_stdout, redirect_stderr
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter, get_configuration

from colorblind_assistant.cli import main
from colorblind_assistant.models import PagePlan
from colorblind_assistant.pdf import assert_preserved, inspect_page
from colorblind_assistant.pipeline import process_document
from tests.sample_responses import SampleReviewer
from tests.test_editor import legend_plan
from tests.test_pdf import FIXTURE, synthetic_pdf


class PipelineTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[1] / "tmp"
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.pdf"
        self.source.write_bytes(synthetic_pdf())
        self.output = self.root / "output"

    def test_full_five_page_fixture(self):
        original = FIXTURE.read_bytes()
        report = process_document(FIXTURE, self.output, SampleReviewer())
        self.assertEqual(report["status"], "completed", json.dumps(report["pages"], indent=2))
        self.assertEqual([page["status"] for page in report["pages"]], ["corrected"] * 5)
        self.assertEqual(len(list((self.output / "previews").glob("*.png"))), 20)
        self.assertEqual(FIXTURE.read_bytes(), original)
        before, after = PdfReader(FIXTURE), PdfReader(self.output / "improved.pdf")
        for a, b in zip(before.pages, after.pages):
            assert_preserved(a, b)
        self.assertEqual(report["ai"]["source"], "controlled_test_responses")
        self.assertEqual(report["validation"]["reader_feedback"], "pending")
        self.assertEqual(len(report["ai"]["calls"]), 10)
        self.assertIn("red -&gt; blue", (self.output / "report.md").read_text(encoding="utf-8"))

    def test_independent_synthetic_and_overwrite(self):
        report = process_document(self.source, self.output, SampleReviewer(legend_plan))
        self.assertEqual(report["status"], "completed")
        with self.assertRaises(FileExistsError):
            process_document(self.source, self.output, SampleReviewer(legend_plan))
        sentinel = self.output / "my-notes.txt"
        sentinel.write_text("Keep me")
        process_document(self.source, self.output, SampleReviewer(legend_plan), overwrite=True)
        self.assertEqual(sentinel.read_text(), "Keep me")

    def test_bookmarks_and_internal_link_destinations_survive(self):
        from reportlab.pdfgen import canvas
        from tests.test_extended_pdf import chart
        pdf = canvas.Canvas(str(self.source), pagesize=(400,400))
        pdf.bookmarkPage('first')
        pdf.addOutlineEntry('Chart', 'first')
        chart(pdf)
        pdf.showPage()
        chart(pdf)
        pdf.linkAbsolute('Back to chart', 'first', Rect=(20,300,140,320))
        pdf.save()
        report = process_document(self.source, self.output, SampleReviewer(legend_plan))
        self.assertEqual(report['status'], 'completed', report['pages'])
        result = PdfReader(self.output / 'improved.pdf')
        self.assertEqual(result.outline[0]['/Title'], 'Chart')
        link = result.pages[1]['/Annots'][0].get_object()
        self.assertEqual(link['/Dest'][0].idnum, result.pages[0].indirect_reference.idnum)
        for index in range(2):
            from colorblind_assistant.pdf import render
            from PIL import Image
            import numpy as np
            preview = Image.open(self.output / 'previews' / f'page-{index+1:04d}.corrected.png')
            self.assertTrue(np.array_equal(np.array(preview), np.array(render((self.output/'improved.pdf').read_bytes(),index))))

    def test_cannot_overwrite_input(self):
        self.output.mkdir()
        source = self.output / "improved.pdf"
        source.write_bytes(synthetic_pdf())
        original = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "overwrite the input"):
            process_document(source, self.output, SampleReviewer(legend_plan), overwrite=True)
        self.assertEqual(source.read_bytes(), original)

    def test_unsupported_page_and_no_change(self):
        writer = PdfWriter()
        writer.add_page(PdfReader(self.source).pages[0]).rotate(90)
        with self.source.open("wb") as handle:
            writer.write(handle)
        agent = SampleReviewer(legend_plan)
        report = process_document(self.source, self.output, agent)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["pages"][0]["status"], "unsupported")
        self.assertFalse(agent.calls)

    def test_api_failure_exports_original_and_reports_failure(self):
        report = process_document(self.source, self.output, SampleReviewer(failure=True))
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["pages"][0]["groups"])
        self.assertIn("Simulated API failure", report["pages"][0]["warnings"][0])

    def test_revision_is_bounded_and_honest(self):
        agent = SampleReviewer(legend_plan, revision=True)
        report = process_document(self.source, self.output, agent)
        self.assertEqual(len(agent.calls), 2)
        self.assertEqual(report["status"], "partial")
        self.assertIn("human review", report["pages"][0]["warnings"][-1])

    def test_rejected_revision_does_not_claim_it_was_applied(self):
        agent = SampleReviewer(legend_plan, revision=True)
        from colorblind_assistant.models import PageReview
        agent.review = lambda *args: PageReview(approved=False, revised_plan=PagePlan(groups=[],warnings=[]),warnings=[])
        report = process_document(self.source,self.output,agent)
        self.assertFalse(report['pages'][0]['groups'])
        self.assertIn('no correction passed',report['pages'][0]['warnings'][-1])

    def test_parser_budget_is_bounded_and_restored(self):
        previous = get_configuration().stream_parsing_work_maximum_count
        def inspect(*args):
            self.assertEqual(get_configuration().stream_parsing_work_maximum_count,6_000_000)
            return inspect_page(*args)
        with patch('colorblind_assistant.pipeline.inspect_page',side_effect=inspect):
            process_document(self.source,self.output,SampleReviewer(legend_plan))
        self.assertEqual(get_configuration().stream_parsing_work_maximum_count,previous)

    def test_missing_key_and_cli_json(self):
        stdout, stderr = StringIO(), StringIO()
        with chdir(self.root), patch.dict(os.environ, {}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            result = main([str(self.source), "--output-dir", str(self.output)])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")
        self.assertIn("OPENAI_API_KEY", stderr.getvalue())
        self.assertFalse(self.output.exists())

    def test_cli_reads_env_file_and_respects_environment_precedence(self):
        (self.root / ".env").write_text(
            '# Local settings\nOPENAI_API_KEY="test-file-key"\nOPENAI_MODEL=file-model\nUNRELATED=value\n',
            encoding="utf-8-sig")
        for environment, expected in (({}, ("test-file-key", "file-model")),
                                      ({"OPENAI_API_KEY": "test-shell-key", "OPENAI_MODEL": "shell-model"},
                                       ("test-shell-key", "shell-model"))):
            with self.subTest(environment=bool(environment)), chdir(self.root), patch.dict(os.environ, environment, clear=True):
                stdout, stderr = StringIO(), StringIO()
                with patch("colorblind_assistant.cli.OpenAIReviewer") as reviewer, \
                     patch("colorblind_assistant.cli.process_document", return_value={"status": "completed", "pages": [], "outputs": {}}), \
                     redirect_stdout(stdout), redirect_stderr(stderr):
                    self.assertEqual(main([str(self.source)]), 0)
                reviewer.assert_called_once_with(*expected)
                self.assertEqual(dict(os.environ), environment)
                self.assertNotIn("test-file-key", stdout.getvalue() + stderr.getvalue())

    def test_cli_completed_partial_and_invalid_exit_codes(self):
        for revision, expected in ((False, 0), (True, 3)):
            stdout, stderr = StringIO(), StringIO()
            with patch("colorblind_assistant.cli.OpenAIReviewer", return_value=SampleReviewer(legend_plan, revision=revision)), redirect_stdout(stdout), redirect_stderr(stderr):
                result = main([str(self.source), "--output-dir", str(self.output), "--overwrite"])
            self.assertEqual(result, expected)
            self.assertIn(json.loads(stdout.getvalue())["status"], {"completed", "partial"})
            self.assertIn("Inspecting page", stderr.getvalue())
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as caught:
            main([str(self.source), "--unknown-option"])
        self.assertEqual(caught.exception.code, 2)

    def test_encrypted_and_malformed_input(self):
        self.source.write_bytes(b"not a PDF")
        with self.assertRaises(Exception):
            process_document(self.source, self.output, SampleReviewer())
        self.assertFalse(self.output.exists())
        writer = PdfWriter()
        writer.add_page(PdfReader(BytesIO(synthetic_pdf())).pages[0])
        writer.encrypt("test-password")
        with self.source.open("wb") as handle:
            writer.write(handle)
        with self.assertRaisesRegex(ValueError, "Encrypted"):
            process_document(self.source, self.output, SampleReviewer())
        self.assertFalse(self.output.exists())

    def test_publish_failure_rolls_back_existing_outputs(self):
        process_document(self.source, self.output, SampleReviewer(legend_plan))
        before = {path.relative_to(self.output): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        real_replace = os.replace
        count = 0

        def fail_once(source, destination):
            nonlocal count
            count += 1
            if count == 9:
                raise PermissionError("Simulated locked output")
            return real_replace(source, destination)

        with patch("colorblind_assistant.pipeline.os.replace", side_effect=fail_once):
            with self.assertRaises(PermissionError):
                process_document(self.source, self.output, SampleReviewer(legend_plan), overwrite=True)
        after = {path.relative_to(self.output): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_interrupt_during_publish_rolls_back_existing_outputs(self):
        process_document(self.source, self.output, SampleReviewer(legend_plan))
        before = {path.relative_to(self.output): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        real_replace = os.replace
        count = 0

        def interrupt_once(source, destination):
            nonlocal count
            count += 1
            if count == 9:
                raise KeyboardInterrupt()
            return real_replace(source, destination)

        with patch("colorblind_assistant.pipeline.os.replace", side_effect=interrupt_once):
            with self.assertRaises(KeyboardInterrupt):
                process_document(self.source, self.output, SampleReviewer(legend_plan), overwrite=True)
        after = {path.relative_to(self.output): path.read_bytes() for path in self.output.rglob("*") if path.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
