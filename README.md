# PromptBoundary

[中文使用说明](README.zh-CN.md) · [Agent Skill](skills/promptboundary/SKILL.md) · [Evaluation](evaluation/)

When someone says “Stop bringing that up when you tease me” and later says “Roast me again,” the assistant can still tell a joke. PromptBoundary helps it remember which subject the user excluded, recognize a genuine change of mind, and check what the final joke actually says.

Use the **Skill** to guide an agent with access to its conversation. Use the **Python controller** when you own the model call and want an explicit correction record, a pre-answer decision, and a review before returning text. Both operate in the application context. The package runs on Python 3.10+ with the standard library.

## Tool authorization and source-copy experiments

The new optional [capability SDK](docs/capabilities.md) tracks external-source origins, checks application-owned tool grants before execution, and recovers rejected plans. Explicit literal-copy tasks can additionally bind an argument to a host-selected source field. It does not infer authority from retrieved text or claim that source data is truthful.

On the original frozen tool-effect holdout, GPT-4.1 mini's raw model executed 8/23 evaluable attacks, the old conversational runtime 11/23, and the capability runtime 2/24; normal task pass remained 13/16. All six improvements on comparable raw/protected pairs include an unsafe initial plan, a gate denial and a useful repair. Stronger Sol/Astra baselines stayed at zero, so that set establishes no security gain for them. [Reproduce every run](evaluation/agent_security/README.md), [read the current delivery report](evaluation/agent_security/DELIVERY.zh-CN.md), and [review limitations and metric sensitivity](evaluation/agent_security/INDEPENDENT_AUDIT.md). These are authored adaptations of public methods, not official AgentDojo scores.

The final source-copy challenge reduced 4.1 mini's observed attacks from 4/24 to 0/24 with 16/16 normal tasks in both arms; the small paired comparison has p=0.125. Sol/Astra still showed no measurable security gain. All new iterations and confirmations cost USD 6.634151435 across 2,877 calls. These checks protect tool effects in explicitly authorized workflows; source truth and open-ended reasoning remain outside their guarantee.

## Hosted security evaluation (v0.2)

The [three-model report](evaluation/hosted/results/main/RESULTS.md) compares the raw model, v0.1 controller and patched controller on the same 32 cases. It separates disclosing a synthetic secret or emitting an unauthorized mock command from completing a useful task or refusing it. [Read the cases and reproduce the run](evaluation/hosted/README.md), [inspect the earlier benign failures](evaluation/hosted/DIAGNOSIS.md), or [review the runtime changes](docs/runtime-security.md).

On natural replies every raw model already resisted all 20 attacks. When given the same leaking drafts, live reviews plus the patch stopped all 12; the released controller delivered 4/12. The patch also withheld one legitimate task on Sol and Astra. [Stress test and clean controls](evaluation/hosted/stress/results/RESULTS.md)

## Earlier local-model results (v0.1)

On a frozen 12-case bilingual suite, adding the controller to Qwen2.5-7B raised correction retention from 3/6 to 4/6, reduced violations from 4/10 to 2/10 and kept false refusals at 0/5. It cost an extra 23.87 seconds and 3,110 tokens per transcript on average. One retained correction came from the history-eviction cases. On 3B the controller reduced violations but lost one task pass. Combining the Skill and controller missed the predeclared improvement rule on both models. Read the complete [four-arm results, early failures and limitations](evaluation/REPORT.md).

## Install and try it

From a terminal with Python and Git:

```sh
git clone --branch hosted-runtime-evaluation https://github.com/Naterisy/PromptBoundary.git
cd PromptBoundary
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
promptboundary demo
```

The demo runs a scripted mock locally with synthetic dialogue. To install the Skill for your Codex projects, copy its self-contained directory:

```sh
mkdir -p ~/.agents/skills
cp -R skills/promptboundary ~/.agents/skills/
```

Start a new chat and invoke `$promptboundary`, or let the agent select it from its description. For a project-scoped installation use `.agents/skills/` in that project. The Skill works independently of the Python installation. [Codex Skill discovery](https://developers.openai.com/codex/skills/)

The earlier [v0.1.0 release](https://github.com/Naterisy/PromptBoundary/releases/tag/v0.1.0) also includes a standalone Skill ZIP, a Python wheel for offline installation, and SHA-256 checksums.

To install the **historical v0.1.0** Python CLI without cloning the repository, run this inside a virtual environment.

```sh
python -m pip install https://github.com/Naterisy/PromptBoundary/releases/download/v0.1.0/promptboundary-0.1.0-py3-none-any.whl
promptboundary demo
```

## Use a local model

Start a Chat Completions server supporting structured responses. The adapter requests a JSON Schema for interpretation and review. An explicit rejection of schema support triggers a JSON-object compatibility path. Drafts use ordinary text completions. For example, with llama.cpp and a GGUF model you have downloaded:

```sh
llama-server -m /path/to/instruct.gguf --host 127.0.0.1 --port 18764 --alias pb-qwen -c 8192 -np 1
```

The adapter sends the conversation and intermediate drafts to the endpoint you configure. Use a local endpoint when these should stay on the device. Keep one SDK state per conversation. Review its contents and apply your own retention and access policy before persisting it.

## Python SDK

```python
from promptboundary import BoundaryController, OpenAICompatible, StageModel, State

backend = OpenAICompatible("http://127.0.0.1:18764/v1", "pb-qwen")
model = StageModel(backend, generation={"temperature": 0, "max_tokens": 512})
controller = BoundaryController(model, max_retries=1)
state = State()
for request in [
    "Please stop calling me chief. Suggest a lunch.",
    "Give me another idea in the same casual tone.",
]:
    turn = controller.run(state, request)
    state = turn.state
    print(turn.text)
```

To include the Skill in the application, pass its UTF-8 contents to `StageModel(..., system_prefix=...)`. For an already loaded agent Skill, the host handles the instructions. To save and restore a session, use `turn.state.to_dict()` and `State.from_dict(saved)`. Store the returned state even on a delivery fallback so an accepted correction can carry forward. To retry the same input, start with the original state.

## Run the HTTP middleware

Start the proxy, then send the full transcript from a second terminal.

```sh
promptboundary serve --base-url http://127.0.0.1:18764/v1 --model pb-qwen --skill SKILL.md --port 8080
```

```sh
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"pb-qwen","messages":[{"role":"user","content":"Please drop the titles. Just call me Lee."},{"role":"assistant","content":"Sure, Lee."},{"role":"user","content":"Greet me and suggest a podcast topic."}],"temperature":0,"max_tokens":384}'
```

The loopback proxy replays prior user turns on every request. It implements text-only, non-streaming Chat Completions with one choice. Use `GET /v1/models` to discover the model ID. Each model stage has its own `max_tokens` limit. The response aggregates token usage across replay, drafts, audits and retries when the provider reports it. Inspect the `X-PromptBoundary-Status` header or SDK `turn.status` for a fallback. For a network-free upstream, start `promptboundary serve --mock` and select `promptboundary-mock` in your request.

## How the controller makes a decision

1. An interpreter reads the new utterance, recent dialogue and effective records. It proposes scoped changes with an exact quote from the current user turn. The controller validates the action, record ID, lifetime and source quote before applying it.
2. The generator sees the current request and the effective constraints. A single-turn exception suspends the corresponding record for that turn. A permanent revocation ends it.
3. An auditor reads the proposed answer and checks both boundary violations and unnecessary refusals. A rejected answer gets specific revision feedback. The default permits one new draft. The reviewer must support a rejection with text from the candidate or a concrete missing requirement. An inconclusive assessment can trigger a second review. Grounded violations and unavailable upstreams can yield a fallback. A delivered reply marked `degraded` carries unresolved interpretation or review uncertainty. Inspect its events for details.

The SDK keeps a bounded window of 12 dialogue messages plus application instructions, its record ledger and a bounded list of unparsed user turns. The ledger can retain exact user quotations, including superseded entries. Give each conversation a separate state and discard it when appropriate. The HTTP example reconstructs state on each request, which adds model calls and can produce different interpretations. Use a single-user trusted machine for the unauthenticated loopback example. A model can misread scope, accept a bad joke, or invent a reason to reject a good answer. Keep access control, authorization and private-data handling in the host application.

The schema adapter makes at most two interpretation calls per turn, up to `max_retries + 1` drafts and at most two reviews per draft. Endpoints that explicitly reject the schema format may incur an additional compatibility request. Unparsed input is retained for up to six turns. Positive review is required for protected cases. In ordinary cases two inconclusive reviews can yield a delivered draft with `degraded` status. The HTTP header `X-PromptBoundary-Status` exposes this distinction.

## Development

```sh
python -m unittest discover -s tests -v
```

Run the tests from the checkout. Local HTTP integration tests open an ephemeral loopback port. For the experimental protocol, fixed test inputs, scoring rules and individual model replies, see [evaluation](evaluation/). Code, Skill and synthetic fixtures are available under the [MIT license](LICENSE). Model weights are obtained separately under their publisher's terms.
