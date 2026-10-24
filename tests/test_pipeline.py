from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from colorblind_assistant.cli import main
from colorblind_assistant.models import PagePlan
from colorblind_assistant.pdf import assert_preserved
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

    def test_missing_key_and_cli_json(self):
        stdout, stderr = StringIO(), StringIO()
        with patch.dict(os.environ, {}, clear=True), redirect_stdout(stdout), redirect_stderr(stderr):
            result = main([str(self.source), "--output-dir", str(self.output)])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "failed")
        self.assertIn("OPENAI_API_KEY", stderr.getvalue())
        self.assertFalse(self.output.exists())

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
