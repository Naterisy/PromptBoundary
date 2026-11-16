# Enforce the boundary in the application

The self-contained Skill includes the same Python source as the repository in `runtime.zip`, not a separately maintained implementation. A Python host can add the reviewed archive to its import path, or install the repository package with `pip install .`. The Skill bootstrap verifies file hashes before running its offline CLI. Hashes detect changes; they are not signatures or proof that a checkout is trustworthy. Verify the Git commit from the repository and review `manifest.json` (`source_commit`, `source_dirty`, `source_tree_sha256`).

For an application using the reviewed standalone bundle:

```python
import sys
sys.path.insert(0, "/absolute/path/to/promptboundary-tools/runtime.zip")
# Import the SDK only after verifying the bundle and its manifest.
```

Host-owned operation and fresh worker:

```python
from promptboundary.quarantine import FlowSource, QuarantinedWorkflow, TransformSpec

flow = QuarantinedWorkflow(session_id="authenticated-user-job")
flow.add_source(FlowSource("public-agenda", "The meeting begins at 09:30."))
# Host code derives this contract from the authenticated user's request.
turn = flow.authorize(TransformSpec(
    task="Summarize the meeting time in one sentence.",
    source_ids=("public-agenda",), tool="send_email",
    arguments={"to": "owner@example.test"}, output_argument="body",
    destination="owner@example.test",
))

def worker(request):
    # Replace this offline stub with a fresh model call receiving ONLY
    # request.as_dict(); never ambient history, previous_response_id or tools.
    # Detect provider refusal/incomplete/error and raise WorkerRefusal/FlowError.
    return "The meeting begins at 09:30."

artifact = flow.transform(turn, worker)
outbox = []
result = flow.execute(turn, artifact, {
    "send_email": lambda **args: outbox.append(args)
})
assert result.completed
# In a real application, render a receipt from result/outbox, not worker claims.
```

All callbacks above stay in memory. For a real tool, the host supplies the callback and routes every operation through the executor. A Python callback has ambient process authority: this library does not sandbox malicious Python or validate file symlinks, HTTP redirects or database permissions. An agent with unrestricted alternative shell/browser/network tools can bypass it.

`FlowSource(..., readers=frozenset({"owner@example.test"}))` allows derived content only to that reader label. `readers=None` is public. Restrictions from all selected sources are intersected. A source's text cannot change these labels. Source selectors, task contract and the mapping between reader labels and actual tool destinations must come from trusted host logic.

The worker cannot choose tool, recipient or path. It can still produce wrong or malicious prose. Give it the minimum relevant sources and no unrelated private context; do not treat its text as a new instruction stream. For exact-copy work, use `bind_authorization` and `materialize_bound_plan` instead of asking the worker to transcribe data.

Each `authorize` supersedes the earlier turn; `revoke()` invalidates pending work. Old handles and generated artifacts cannot be reused after a new authorization. The current in-process state is not durable across restarts. Callback failures can happen after an effect starts; do not automatically retry real effects or claim rollback.

The original capability executor remains useful for agent-proposed plans:

```python
from promptboundary.capabilities import CapabilitySession
gate = CapabilitySession.from_dict(
    {"tools": {"send_email": {"to": ["owner@example.test"], "body": None}}},
    session_id="authenticated-job",
)
result = gate.execute(proposal, application_tool_registry)
```

It validates a complete batch before any callback, then consumes the grants. `inspect` alone does not consume grants or guarantee future execution. A passed body is not a factual or confidentiality certification.

Call `revoke()` when accepting a new user request, before constructing its new `TransformSpec`. A rejected `authorize()` also invalidates the preceding turn, but a constructor error occurs before that call. Keep this explicit revocation in the host adapter.

## Optional model transformation and bounded review

The packaged `OpenAITextWorker` is the reusable adapter measured by the current
experiment runner. It creates a fresh request from the selected task and sources,
not an ambient conversation. Its optional reviewer examines the draft and original
sources, requires literal source quotations for repairs, allows at most one
revision and requires an explicit final pass. A reviewer verdict does not grant
permissions or prove that the draft is true.

```python
import os
from promptboundary.responses import OpenAIResponses
from promptboundary.transforms import OpenAITextWorker

endpoint = OpenAIResponses(
    "https://api.openai.com/v1", "gpt-6.1-sol",
    api_key=os.environ["OPENAI_API_KEY"], reasoning_effort="low",
)
worker = OpenAITextWorker(endpoint, review=True)
# This starts billable requests when used; do not execute as an install check.
artifact = flow.transform(turn, worker)
result = flow.execute(turn, artifact, application_tool_registry)
```

Use a model ID verified on your account; the example model was verified for this
project's experiments, not guaranteed available to every user. The endpoint may be
a compatible implementation that meters and journals every physical request.
Use `reasoning_effort=None` to omit unsupported reasoning options. The normal
reviewed path makes two calls; one repair can increase this to four. Each call has
a 768-token output limit. Create a new reviewed worker for each transformation.
Malformed/incomplete provider outputs are errors, explicit refusals are refusals,
and neither yields a tool effect. A model can still approve a wrong draft.

For a separately selected reviewer, construct a second endpoint and pass
`OpenAITextWorker(generator_endpoint, review=True, review_endpoint=reviewer_endpoint)`.
The generator still produces all drafts; the other endpoint sees only review
requests. Meter both endpoints. This changes model capacity and cost, so compare
against using the stronger model directly as well; it is not a free improvement
at the same model budget. The default remains a shared endpoint.

From the repository after installing the SDK,
`python -m examples.quarantined_openai` runs only an offline fixture with an
in-memory outbox. The optional `--live --model <verified-id> --review` form uses an
existing API key and reports token usage. It sends no actual email. An isolated
Skill bundle does not contain the repository's `examples` directory.
Add `--reviewer-model <verified-id>` to try a separate reviewer and report its
usage separately; `--reviewer-reasoning none` omits its reasoning option.

### Evidence-based default

Use `OpenAITextWorker(endpoint)` without review by default. In the v0.4 independent experiments, same-model review sometimes corrupted a correct answer; it is not a generally safer setting. A stronger separate reviewer can help a legacy weak generator, but compare against using that stronger model directly in the quarantined worker. Keep the host capability boundary in either case.
