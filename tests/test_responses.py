import unittest
from promptboundary.responses import chat_result
from promptboundary.upstream import UpstreamError


class ResponsesTests(unittest.TestCase):
    def example(self, parts, status="completed"):
        return {"status": status, "output": [{"type": "reasoning", "summary": []},
                {"type": "message", "role": "assistant", "content": parts}],
                "usage": {"input_tokens": 3, "output_tokens": 7, "total_tokens": 10}}

    def test_skips_reasoning_and_collects_visible_parts(self):
        response = self.example([{"type": "output_text", "text": "4"}, {"type": "output_text", "text": "2"}])
        chat = chat_result(response)
        self.assertEqual(chat["choices"][0]["message"]["content"], "42")
        self.assertEqual(chat["usage"]["completion_tokens"], 7)

    def test_explicit_refusal_and_length_remain_distinguishable(self):
        refusal = self.example([{"type": "refusal", "refusal": "I decline."}])
        self.assertEqual(chat_result(refusal)["choices"][0]["message"]["refusal"], "I decline.")
        incomplete = self.example([], "incomplete")
        incomplete["incomplete_details"] = {"reason": "max_output_tokens"}
        self.assertEqual(chat_result(incomplete)["choices"][0]["finish_reason"], "length")
        with self.assertRaises(UpstreamError):
            chat_result(self.example([]))
