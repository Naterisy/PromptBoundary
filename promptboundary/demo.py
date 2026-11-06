"""A tiny deterministic fixture shared by the CLI demo and smoke tests."""
import json


SET_RULE = "For this conversation, use bullet points."
SKIP_ONCE = "For this answer only, use a paragraph. What is a comet?"
CLEAR_RULE = "Stop using the bullet-point rule."
DEMO_TURNS = (SET_RULE, "What is a comet?", SKIP_ONCE, "What is a comet?", CLEAR_RULE)
RULE = "Use bullet points."
SAMPLE = "A comet is an icy body that orbits the Sun."


def mock_response(messages, structured):
    if not structured:
        return SAMPLE
    data = json.loads(messages[-1]["content"])
    user = data["user_text"]
    if "records" in data and "candidate" not in data and "constraints" not in data:
        existing = next((r for r in data["records"] if r["rule"] == RULE), None)
        actions = []
        if user == SET_RULE and not existing:
            actions = [{"op": "set", "kind": "preference", "rule": RULE,
                        "scope": "answer formatting", "lifetime": "conversation", "quote": user}]
        elif existing and user in (SKIP_ONCE, CLEAR_RULE):
            actions = [{"op": "except_once" if user == SKIP_ONCE else "revoke",
                        "id": existing["id"], "quote": user}]
        result = {"intent": "normal", "actions": actions, "alternative": ""}
    else:
        content = "Understood." if user in (SET_RULE, CLEAR_RULE) else SAMPLE
        bullets = any(r["rule"] == RULE for r in data["constraints"])
        if "candidate" in data:
            valid = not bullets or data["candidate"].startswith("- ")
            result = {"verdict": "pass" if valid else "violation",
                      "reason": "" if valid else "Use a bullet point."}
        else:
            result = {"text": "- " + content if bullets else content}
    return json.dumps(result, ensure_ascii=False)
