# Quarantined transformations and revocable egress

`promptboundary.quarantine` extends the capability boundary to summaries,
translations and other generated text. A trusted application selects the source
IDs, transformation, tool, fixed arguments and destination **before** exposing
external text to a model. A fresh worker receives only the selected sources and
transformation. Its generated text occupies one payload argument; it cannot choose
which tool runs, where the result goes, or what other information it reads.

This applies established control/data separation and information-flow ideas from
[CaMeL](https://arxiv.org/html/2503.18813v2). It is a smaller, host-authored workflow
API, not the CaMeL interpreter or a reproduction of its benchmark. Keeping derived
text in the data channel also addresses the provenance-loss pattern studied in
[multi-CaMeL](https://arxiv.org/abs/2610.05640). Those papers' reported results are
not PromptBoundary results.

## Integration

```python
from promptboundary.quarantine import (
    FlowSource, QuarantinedWorkflow, TransformSpec, WorkerRefusal,
)

flow = QuarantinedWorkflow(session_id="conversation-17")
flow.add_source(FlowSource(
    "report", "Revenue increased 12%. Operating margin was unchanged.",
    readers=frozenset({"owner@example.test"}), kind="document",
))
# An unrelated private source can exist in application state without entering
# the worker request. No history or other source is included implicitly.
flow.add_source(FlowSource("private", "Simulated private note", frozenset({"private-vault"})))

handle = flow.authorize(TransformSpec(
    task="Summarize the report in one sentence.",
    source_ids=("report",),
    tool="send_email",
    arguments={"to": "owner@example.test", "subject": "Report summary"},
    output_argument="body",
    destination="owner@example.test",
))


def worker(request):
    # Replace with a fresh model request using request.as_dict() as data and
    # a fixed application instruction. NO tools, ambient conversation history,
    # previous_response_id, credentials or arbitrary source-fetch callbacks.
    # Parse the response and raise WorkerRefusal() on an explicit refusal;
    # raise a parse error on invalid output. Return only generated text.
    return "Revenue rose 12%, while operating margin stayed unchanged."


artifact = flow.transform(handle, worker)
outbox = []  # Replace only this host registry callback with a real integration.
result = flow.execute(handle, artifact, {"send_email": lambda **args: outbox.append(args)})
assert result.completed
assert outbox[0]["to"] == "owner@example.test"
```

The runnable offline version is `python examples/quarantined_agent.py`. It also
demonstrates a source injection trying to redirect a tool and a blocked attempt
to reuse a private derived summary for another recipient.

`WorkerRequest.as_dict()` contains `task` and a `sources` array. Each source has
`id`, `kind`, `content`, `authority: "none"`, and `allowed_destinations` (null means
public). The runtime does not send a request itself. The **trusted adapter** must
actually enforce a fresh context; a Python callback retaining arbitrary history
or access to global secrets is outside this library's protection.

## Host policy and derived values

- `FlowSource.readers=None` means the host permits this source at any destination.
  A set restricts it to those exact strings; an empty set permits none. Every
  selected source must allow the declared destination before the worker runs.
- A generated artifact inherits the **intersection** of all input readers,
  regardless of whether the worker claims to have used only public information.
  There is no automatic declassification based on a model assertion.
- `flow.retain(handle, artifact, source_id="derived")` registers a derived source
  with its original ancestry and restrictions. A subsequent transform must opt
  into that source explicitly. Its text is never a new user/system instruction.
- `TransformSpec.arguments` contains fixed scalar arguments. The payload argument
  must be absent from this mapping. Nested argument objects are not supported.
- `destination` must equal the actual fixed argument selected by
  `destination_argument`. Built-in mappings are `send_email: to`, `write_file:
  path`, `update_record: record_id`, and `set_record: key`; custom tools require
  an explicit mapping. The application is responsible for canonical addresses,
  resolved paths, redirects and the callback's actual destination semantics.
- Host-authored specs and labels are trusted input. Do not deserialize them from
  model output, page content, an assistant's alleged permission, or unverified
  history. If a model helps draft a contract, validate it against independently
  authenticated user/application policy before calling `authorize`.

## Turn changes and execution semantics

`authorize(spec)` invalidates the prior handle and artifact, including when the
new contract is denied. `revoke()` explicitly ends the current authority. Call it
as soon as the application accepts a replacement/cancel request, **before parsing
or constructing** a replacement contract: a failed constructor cannot revoke a
session it has not been given.

Each handle and artifact is an opaque in-process capability checked by object
identity. A copied, serialized, cross-session or stale object cannot be executed.
A result returning after revocation or reauthorization is discarded. The worker
may be retried after a refusal or parser exception by the host; retries must be
bounded by the application's budget, and they do not create additional egress
rights.

Execution builds one action and passes it through the existing
`CapabilitySession`. The complete action is validated, then its one-shot grant is
consumed before the callback. A missing callback consumes nothing; a callback
exception consumes the grant to prevent accidental duplicate effects. Revocation
waits for an executing callback and cannot undo a send already begun. There is
no transactional rollback, persistent process-restart protection, multi-host
consensus, or delivery retry protocol.

The audit log records epochs, destinations, source IDs, inherited reader labels,
output hashes and execution status. It avoids raw source/output text and exception
messages. Destination/source identifiers themselves may be sensitive; the host
must control log access. Full experiment logs separately retain synthetic inputs
and model outputs for reproducibility.

## What this does not solve

A worker can still produce a wrong, misleading, injected or refusing summary.
That text can be delivered through the authorized payload field. Structured data
and correct provenance do not prove factual correctness. The unit test
`test_data_changed_into_bad_fact_is_explicitly_not_solved` deliberately preserves
this failure mode. This API cannot safely execute arbitrary generated code or
injected follow-up tasks, and does not verify that externally supplied facts are
true.

The intended sink treats payload text as data. If a recipient agent interprets
it as privileged instructions, a shell executes it, or a browser renders active
content without appropriate escaping, the downstream boundary has been lost.
Source reader labels describe destination policy, not API-provider residency or
legal consent to disclose data to a cloud model. The host must separately approve
its worker provider and transport.

This is application-level isolation, not an OS/process sandbox. Host Python,
callbacks, model adapters and source-label assignment are trusted. Internal
objects are not cryptographic capabilities against a malicious Python caller.
Source IDs prevent replacement in one live process; they do not authenticate a
remote publisher or establish source truth. A standalone Skill can guide this
integration but cannot force a host to route all side effects through it.
