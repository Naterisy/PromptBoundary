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
    def test_commentary_is_not_part_of_structured_final_answer(self):
        response=self.example([])
        response['output']=[
            {'type':'message','role':'assistant','phase':'commentary','content':[{'type':'output_text','text':'{"to":"intermediate"}'}]},
            {'type':'message','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':'{"actions":[]}'}]},
        ]
        self.assertEqual(chat_result(response)['choices'][0]['message']['content'],'{"actions":[]}')
        response['output']=response['output'][:1]
        with self.assertRaises(UpstreamError):chat_result(response)

    def test_commentary_refusal_cannot_override_final_content(self):
        response=self.example([])
        response['output']=[
            {'type':'message','role':'assistant','phase':'commentary','content':[{'type':'refusal','refusal':'intermediate'}]},
            {'type':'message','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':'final'}]},
        ]
        message=chat_result(response)['choices'][0]['message']
        self.assertEqual(message['content'],'final')
        self.assertNotIn('refusal',message)

    def test_identical_final_messages_coalesce_without_selecting_differing_answers(self):
        import copy, json
        response=self.example([])
        first={'type':'message','role':'assistant','phase':'final_answer','content':[{'type':'output_text','text':'{"actions":[]}'}]}
        response['output']=[first,copy.deepcopy(first)]
        response['output'][0]['id']='one';response['output'][1]['id']='two'
        self.assertEqual(chat_result(response)['choices'][0]['message']['content'],'{"actions":[]}')
        response['output'][1]['content'][0]['text']='{"actions":[1]}'
        with self.assertRaises(json.JSONDecodeError):
            json.loads(chat_result(response)['choices'][0]['message']['content'])
