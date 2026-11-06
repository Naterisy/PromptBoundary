"""State, routing and retry invariants. Scripted responses isolate the controller."""
import unittest

from promptboundary.core import BoundaryController, ProtocolError, State


class Script:
    def __init__(self, **stages):
        self.stages = {name: iter(values) for name, values in stages.items()}
        self.calls = []

    def __call__(self, stage, payload):
        self.calls.append((stage, payload["data"]))
        item = next(self.stages[stage])
        if isinstance(item, Exception):
            raise item
        return item

    def data(self, stage):
        return [payload for name, payload in self.calls if name == stage]


def interpret(*actions, intent="normal"):
    return {"intent": intent, "actions": list(actions), "alternative": ""}


def add(quote, **updates):
    return {"op": "set", "kind": "correction", "rule": "用户的小狗叫团团",
            "scope": "用户的小狗", "lifetime": "conversation", "quote": quote, **updates}


PASS = {"verdict": "pass", "reason": ""}


class ControllerTests(unittest.TestCase):
    def test_round_trip_and_history_window_preserve_past_correction(self):
        text = "我家小狗叫团团，你刚才写错了。"
        model = Script(interpret=[interpret(add(text))] + [interpret()] * 14,
                       generate=[{"text": "团团"}], audit=[PASS])
        controller = BoundaryController(model)
        state = controller.observe(State(), text)
        for _ in range(13):
            state = controller.observe(state, "换个话题")
        state = State.from_dict(state.to_dict())
        result = controller.run(state, "我家小狗叫什么？")
        self.assertEqual(result.text, "团团")
        data = model.data("generate")[0]
        self.assertNotIn(text, [m["content"] for m in data["history"]])
        self.assertEqual(data["constraints"][0]["kind"], "correction")
        self.assertEqual(data["constraints"][0]["quote"], text)
        self.assertEqual(state.turn, 14)

    def test_narrow_temporary_replacement_and_expiry(self):
        first, once = "分享时不要说出任何地址。", "本条可以提城市，但保留街道地址。"
        model = Script(interpret=[interpret(add(first, kind="boundary", scope="分享地址", rule=first)),
                                  interpret(add(once, op="replace", id="r1", kind="boundary",
                                                lifetime="turn", scope="分享地址", rule="允许城市，隐藏街道")),
                                  interpret()],
                       generate=[{"text": "来自上海"}, {"text": "地址已隐去"}], audit=[PASS, PASS])
        c = BoundaryController(model)
        s = c.observe(State(), first)
        one = c.run(s, once)
        later = c.run(State.from_dict(one.state.to_dict()), "再介绍一次")
        constraints = [d["constraints"] for d in model.data("generate")]
        self.assertEqual([[r["id"] for r in rows] for rows in constraints], [["r2"], ["r1"]])
        self.assertEqual(later.state.records[1].status, "expired")

    def test_revoke_keeps_provenance_without_reviving_previous_version(self):
        first, revised, revoked = "简报用三行。", "以后简报只用两行。", "取消简报的行数限制。"
        model = Script(interpret=[
            interpret(add(first, kind="preference")),
            interpret(add(revised, kind="preference", op="replace", id="r1", rule="简报两行")),
            interpret({"op": "revoke", "id": "r2", "quote": revoked}), interpret()],
            generate=[{"text": "收到"}], audit=[PASS])
        c = BoundaryController(model)
        s = State()
        for utterance in [first, revised, revoked]:
            s = c.observe(s, utterance)
        self.assertEqual([(r.status, r.ended_quote) for r in s.records],
                         [("superseded", revised), ("revoked", revoked)])
        c.run(s, "做个简报")
        self.assertEqual(model.data("generate")[0]["constraints"], [])

    def test_ambiguous_instruction_cannot_remove_confirmed_boundary(self):
        first, next_turn = "不要用我的私人经历开玩笑。", "这次真要来点狠的？"
        model = Script(interpret=[
            interpret(add(first, kind="boundary", rule=first)),
            interpret({"op": "except_once", "id": "r1", "quote": next_turn}, intent="ambiguous")],
            generate=[{"text": "可以，就拿虚构的反派开涮？"}], audit=[PASS])
        c = BoundaryController(model)
        result = c.run(c.observe(State(), first), next_turn)
        self.assertEqual(result.status, "clarify")
        self.assertEqual([r["id"] for r in model.data("audit")[0]["constraints"]], ["r1"])

    def test_unanchored_mutation_rolls_back_entire_batch(self):
        model = Script(interpret=[interpret(add("我的狗"), add("用户没说过这段"))])
        before = State()
        result = BoundaryController(model).run(before, "我的狗")
        self.assertEqual(result.status, "fallback")
        self.assertEqual(before.to_dict(), State().to_dict())
        self.assertEqual(result.state.to_dict(), before.to_dict())
        self.assertFalse(model.data("generate"))

    def test_observe_failure_is_explicit(self):
        model = Script(interpret=[interpret({"op": "revoke", "id": "r1", "quote": "撤销"})])
        with self.assertRaises(ProtocolError):
            BoundaryController(model).observe(State(), "撤销")

    def test_both_audit_failure_modes_return_only_accepted_text(self):
        model = Script(interpret=[interpret()], generate=[
            {"text": "没问题，还是用错名字"}, {"text": "我不能回答"}, {"text": "团团今天好吗？"}],
            audit=[{"verdict": "violation", "reason": "用纠正后的名字"},
                   {"verdict": "false_refusal", "reason": "用户只是问候宠物"}, PASS])
        result = BoundaryController(model, max_retries=2).run(State(), "向团团问好")
        self.assertEqual((result.status, result.attempts, result.text), ("ok", 3, "团团今天好吗？"))
        requests = model.data("generate")
        self.assertIn("用纠正后的名字", requests[1]["feedback"])
        self.assertIn("false_refusal", requests[2]["feedback"])
        self.assertEqual(result.state.history[-1]["content"], result.text)
        self.assertNotIn("还是用错名字", str(result.events))

    def test_invalid_audit_or_service_failure_never_leaks_candidate(self):
        model = Script(interpret=[interpret()], generate=[{"text": "sensitive"}] * 2,
                       audit=[{"verdict": "sure"}, RuntimeError("failed")])
        s = State()
        result = BoundaryController(model).run(s, "hello")
        self.assertEqual((result.status, result.attempts), ("fallback", 2))
        self.assertNotIn("sensitive", result.text)
        self.assertEqual(s.turn, 0)
        self.assertEqual(result.state.turn, 1)
        self.assertEqual(result.state.history, [{"role":"user", "content":"hello"}])
        self.assertEqual(result.events.count("audit:error"), 2)

    def test_no_lexical_repeat_filter_and_trusted_context_preserved(self):
        model = Script(interpret=[interpret(), interpret()],
                       generate=[{"text": "一个关于闹钟的笑话。"}] * 2, audit=[PASS, PASS])
        history = [{"role": "system", "content": "回答简短。"}] + [
            {"role": "user", "content": "讲个笑话"} for _ in range(20)]
        c = BoundaryController(model)
        one = c.run(State(), "吐槽这破闹钟", history=history)
        two = c.run(one.state, "吐槽这破闹钟")
        self.assertEqual((one.status, two.status), ("ok", "ok"))
        self.assertEqual(model.data("generate")[1]["history"][0], history[0])
        self.assertFalse(two.state.records)

    def test_repair_mutation_proposal_without_committing_partial_records(self):
        quote = "叫我林老师。"
        model = Script(interpret=[interpret(add(quote), add("来自上轮")), interpret(add(quote))])
        state = BoundaryController(model).observe(State(), quote)
        self.assertEqual([r.id for r in state.records], ["r1"])
        self.assertIn("evidence", model.data("interpret")[1]["feedback"])

    def test_keep_valid_correction_when_no_candidate_can_be_delivered(self):
        quote = "小狗叫团团。"
        model = Script(interpret=[interpret(add(quote)), interpret()],
                       generate=[{"text": "未通过的草稿"}, {"text":"团团"}],
                       audit=[{"verdict":"violation", "reason":"纠正名字"}, PASS])
        c = BoundaryController(model, max_retries=0)
        s = State()
        first = c.run(s, quote)
        self.assertEqual(first.status, "fallback")
        self.assertEqual(first.state.records[0].quote, quote)
        self.assertEqual(first.state.history, [{"role":"user", "content":quote}])
        self.assertEqual(s.turn, 0)
        second = c.run(first.state, "小狗叫什么？")
        self.assertEqual(model.data("generate")[1]["constraints"][0]["id"], "r1")
        self.assertEqual(second.status, "ok")

    def test_only_validated_states_are_loaded(self):
        with self.assertRaises(ProtocolError):
            State.from_dict({"version": 2})
        with self.assertRaises(ProtocolError):
            State.from_dict({"version": 1, "records": [{"kind": "correction"}]})
        with self.assertRaises(ValueError):
            BoundaryController(lambda stage, data: {}, max_retries=-1)


if __name__ == "__main__":
    unittest.main()
