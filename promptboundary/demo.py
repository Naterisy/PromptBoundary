"""A tiny deterministic fixture shared by the CLI demo and smoke tests."""
import json
from .upstream import GENERATION_CONTEXT


SET_RULE = "For this conversation, use bullet points."
SKIP_ONCE = "For this answer only, use a paragraph. What is a comet?"
CLEAR_RULE = "Stop using the bullet-point rule."
DEMO_TURNS = (SET_RULE, "What is a comet?", SKIP_ONCE, "What is a comet?", CLEAR_RULE)
RULE = "Use bullet points."
SAMPLE = "A comet is an icy body that orbits the Sun."


def mock_response(messages, structured):
    if not structured:
        user = messages[-1]["content"]
        context = {}
        if len(messages) > 1 and messages[-2]["content"].startswith(GENERATION_CONTEXT):
            context = json.loads(messages[-2]["content"][len(GENERATION_CONTEXT):])
        content = "Understood." if user in (SET_RULE, CLEAR_RULE) else SAMPLE
        bullets = any(r["rule"] == RULE for r in context.get("constraints", []))
        return "- " + content if bullets else content
    data = json.loads(messages[-1]["content"])
    user = data["user_text"]
    if "records" in data and "candidate" not in data and "constraints" not in data:
        existing = next((r for r in data["records"] if r["rule"] == RULE), None)
        actions = []
        if user == SET_RULE and not existing:
            actions = [{"op": "set", "kind": "preference", "rule": RULE, "private": False,
                        "scope": "answer formatting", "lifetime": "conversation", "quote": user}]
        elif existing and user in (SKIP_ONCE, CLEAR_RULE):
            actions = [{"op": "except_once" if user == SKIP_ONCE else "revoke",
                        "id": existing["id"], "quote": user}]
        result = {"intent": "normal", "actions": actions, "alternative": "", "protected_ids": [],
                  "personal_humor": False, "public_topic": ""}
        if data["records"]:
            result["decisions"] = {r["id"]: "keep" for r in data["records"]}
    else:
        bullets = any(r["rule"] == RULE for r in data["constraints"])
        valid = not bullets or data["candidate"].startswith("- ")
        result = {"verdict": "pass" if valid else "violation", "evidence": "",
                  "rule_id": "" if valid else next(r["id"] for r in data["constraints"] if r["rule"] == RULE),
                  "reason": "" if valid else "Use a bullet point.", "missing": "" if valid else RULE}
    return json.dumps(result, ensure_ascii=False)
