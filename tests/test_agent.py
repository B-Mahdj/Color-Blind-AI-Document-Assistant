from io import BytesIO
import json
import unittest

import httpx
from openai import OpenAI
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from colorblind_assistant.agent import AgentError, OpenAIReviewer, categorical_color_guidance
from colorblind_assistant.editor import apply_plan
from colorblind_assistant.models import Action, CorrectionGroup, PagePlan
from colorblind_assistant.pdf import inspect_page, render
from tests.test_pdf import synthetic_pdf


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.pdf = synthetic_pdf()
        self.data = inspect_page(PdfReader(BytesIO(self.pdf)).pages[0], 1)
        self.image = render(self.pdf)
        self.requests = []

    def agent(self, status=200, payload=None):
        def respond(request):
            self.requests.append(json.loads(request.content))
            self.assertEqual(request.url.path, "/v1/responses")
            return httpx.Response(status, json=payload)
        http_client = httpx.Client(transport=httpx.MockTransport(respond))
        client = OpenAI(api_key="test-only-key", base_url="https://api.openai.com/v1", http_client=http_client, max_retries=0)
        self.addCleanup(client.close)
        return OpenAIReviewer("test-only-key", client=client)

    def response(self, text, status="completed"):
        return {"id": "resp_test", "object": "response", "created_at": 0,
                "model": "gpt-6.1-sol", "status": status,
                "output": [{"id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": text, "annotations": []}]}],
                "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}}

    def test_real_sdk_request_uses_images_and_strict_schema(self):
        agent = self.agent(payload=self.response('{"groups":[],"warnings":[]}'))
        plan = agent.propose(self.data, self.image)
        self.assertFalse(plan.groups)
        request = self.requests[0]
        self.assertEqual(request["model"], "gpt-6.1-sol")
        self.assertFalse(request["store"])
        self.assertTrue(request["text"]["format"]["strict"])
        self.assertEqual(request["text"]["format"]["type"], "json_schema")
        self.assertIn("untrusted DATA", request["input"][0]["content"])
        self.assertNotIn("tools", request)
        content = request["input"][1]["content"]
        self.assertEqual(sum(item["type"] == "input_image" for item in content), 2)
        guidance = json.loads(content[0]["text"])["categorical_color_guidance"]
        self.assertEqual([item["suggested_color"] for item in guidance], ["#005A9C", "#A84400"])
        self.assertEqual(len(guidance[0]["targets"]), 2)
        self.assertEqual(agent.calls[0]["usage"]["total_tokens"], 110)

    def test_guidance_produces_valid_distinct_status_colors(self):
        output = BytesIO()
        pdf = canvas.Canvas(output, pagesize=(400, 400))
        for index, color in enumerate(((.75, .15, .1), (.2, .65, .2), (.78, .17, .12), (.22, .67, .23))):
            pdf.setFillColorRGB(*color)
            pdf.rect(40, 40 + index * 70, 200, 50, fill=1, stroke=0)
            pdf.setFillColorRGB(1, 1, 1)
            pdf.drawString(60, 60 + index * 70, f"Status {index + 1}")
        pdf.save()
        page = PdfReader(BytesIO(output.getvalue())).pages[0]
        data = inspect_page(page, 1)
        guidance = categorical_color_guidance(data)
        self.assertEqual([item["suggested_color"] for item in guidance], ["#005A9C", "#A84400", "#6B3C91", "#303030"])
        self.assertTrue(all(not item["hatch_eligible_ids"] for item in guidance))
        actions = [Action(kind="recolor", target_ids=[target["target_id"]], channel=target["channel"], color=item["suggested_color"])
                   for item in guidance for target in item["targets"]]
        group = CorrectionGroup(id="statuses", reason="Use existing labels", association="direct_labels",
                                legend_ids=[], uncertain=False, evidence_text_ids=[text.id for text in data.text], actions=actions)
        result = apply_plan(page, data, PagePlan(groups=[group], warnings=[]))
        self.assertFalse(result.warnings, result.warnings)
        self.assertEqual(len(result.groups[0]["changes"]), 4)

    def test_http_error_does_not_disclose_response_body(self):
        agent = self.agent(401, {"error": {"message": "sensitive-marker", "type": "authentication_error"}})
        with self.assertRaises(AgentError) as caught:
            agent.propose(self.data, self.image)
        self.assertTrue(caught.exception.fatal)
        self.assertNotIn("sensitive-marker", str(caught.exception))

    def test_malformed_schema_and_incomplete_response(self):
        for text, status in (("{}", "completed"), ('{"groups":[],"warnings":[]}', "incomplete")):
            agent = self.agent(payload=self.response(text, status))
            with self.assertRaises(AgentError):
                agent.propose(self.data, self.image)

    def test_contradictory_review_is_rejected(self):
        body = {"approved": True, "revised_plan": {"groups": [], "warnings": []}, "warnings": []}
        agent = self.agent(payload=self.response(json.dumps(body)))
        with self.assertRaisesRegex(AgentError, "both approved"):
            agent.review(self.data, self.image, self.image, [], [])


if __name__ == "__main__":
    unittest.main()
