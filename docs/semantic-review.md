# Optional bounded review of generated text

**Observed v0.4 result:** same-model review is experimental and disabled by default. On the frozen independent set, the 4.1 mini reviewer actively changed two correct drafts into injected answers; its attack count was 3/24 versus 1/24 for the plain quarantined worker. A stronger mixed-model reviewer improved the weaker generator, but the stronger model used directly as a quarantined worker was cheaper and more useful in this set. Do not enable review merely because another model call sounds safer. See [independent audit](../evaluation/flow_security/INDEPENDENT_AUDIT.md).

`ReviewedWorker` adds a fallible semantic check to a quarantined transformation.
It addresses a remaining failure of fixed permissions: a permitted email body can
still contain an injected replacement answer. This is an optional model-based
quality stage; **its verdict does not grant permissions or certify truth**.
The hard destination, source and execution restrictions remain in
`QuarantinedWorkflow`.

```python
from promptboundary.reviewed_worker import ReviewedWorker


def generate(request, feedback):
    # Fresh model request: request.as_dict() plus optional feedback as DATA.
    # No tools, ambient history, unrelated sources or previous_response_id.
    # Parse the provider response; return only the draft text. Raise
    # WorkerRefusal on explicit refusal and ValueError on malformed output.
    return "Seven incident tickets remain open."


def review(request):
    # Fresh independent request: request.as_dict() contains only task,
    # original selected sources, and draft. These are data, not permission.
    # In a real adapter, ask whether the draft follows the actual task and
    # source facts, rather than a source's instructions to replace the answer.
    return {"verdict": "pass", "issues": []}


worker = ReviewedWorker(generate, review, max_revisions=1)
# flow/turn are already created from authenticated host policy:
# artifact = flow.transform(turn, worker)
# result = flow.execute(turn, artifact, application_registry)
```

The above callbacks are offline stubs. They demonstrate the interface, not actual
model effectiveness. The package includes the real `promptboundary.transforms.OpenAITextWorker` adapter, also used by the metered experiment runner. Set `review=True` to enable review; an optional `review_endpoint` can use a different model. Count both endpoints and compare that mixed-model system against using the stronger model directly.

The reviewer returns exactly `verdict` and `issues`. The verdict is `pass`,
`revise`, or `refuse`. A passing verdict must have no issues. A revision must have
at least one issue in this shape:

```json
{"verdict":"revise","issues":[{"source_id":"incident-note","quote":"Seven tickets remain open.","explanation":"The draft incorrectly says all tickets are closed."}]}
```

The host checks that each nonempty quote literally occurs in the named selected
source. Unknown sources, extra keys, fabricated quotations, oversized responses,
blank output, or malformed schemas are **protocol errors**. They must not be
reported as successful defense or normal refusal. Grounded quotations only make
the feedback auditable; they do not establish that the explanation is correct.

The orchestration permits one initial generation and review, followed by at most
one revision and another review. The final draft must receive an explicit
`pass`. `refuse`, or a further `revise` after the budgeted revision, raises
`WorkerRefusal`; no artifact is returned to the executor. Such withheld normal
tasks are utility failures in evaluation, not success. `max_revisions=0` disables
the repair attempt. Each `ReviewedWorker` instance is single-use.

Repair feedback includes `previous_draft` and the grounded `issues`, so the
worker can inspect what it is revising. If it returns the byte-identical rejected
text, the orchestration withholds it with reason `unchanged_revision` before a
second review. A later stochastic reviewer cannot relabel an unchanged rejected
candidate as a successful repair. This is an exact consistency check, not a test
of semantic improvement; a paraphrased bad answer can still pass, and an earlier
false-positive review can cause a useful unchanged draft to be withheld.

Feedback enters generation as untrusted data, never a system/developer message
or a rewritten authorization. A quote can itself contain a prompt injection.
Callbacks must obey the same context isolation requirements as the original
worker and must not send private records into a separate reviewer that is not
approved to process them. The caller journals and charges **every** generation
and review: two model calls for a passing first draft, three when an unchanged
revision is withheld, and up to four with a changed revision.
The audit records stage, verdict, revision count and text/issue hashes; it omits
raw prose and exception details.

This layer can miss attacks, invent issues, falsely refuse useful output, and
be attacked through either sources or drafts. A reviewer using the same model
is a separate request, not an independent human judge. The evaluator must remain
separate from these review decisions. Keep original model outputs and real task
outcomes, including rejected drafts, so that measured safety gains cannot be
manufactured by treating every rejection as successful task completion.
