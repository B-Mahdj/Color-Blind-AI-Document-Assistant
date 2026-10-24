from io import BytesIO
import json
import unittest

import httpx
from openai import OpenAI
from pypdf import PdfReader

from colorblind_assistant.agent import AgentError, OpenAIReviewer
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
        self.assertEqual(agent.calls[0]["usage"]["total_tokens"], 110)

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
