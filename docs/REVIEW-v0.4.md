# Implementation and installation review — 0.4.0

Date: 2026-11-16. This is a scoped engineering review, not an external security
audit or a proof that prompt injection is solved. The reviewing agent implemented
the quarantine/review orchestration and separately reviewed the Skill packaging,
production model adapter and experiment runner written by other agents. The Skill
forward test was conducted without reading its author's tests or expected
solutions. No holdout outputs or holdout case contents were inspected for this
review, and no paid model calls or external messages were sent.

## Outcome and scope

No high-severity bypass was found within the stated threat model: attacker text
can occupy external source content or earlier assistant messages; trusted host
code owns source labels, source selection, current authorization, destination
mapping, model transport and tool registry. A malicious Python caller, writable
host policy, compromised interpreter or an agent with alternative unguarded tools
is outside that boundary.

The 18 file hashes in
`evaluation/flow_security/runtime_freeze.json` matched during this review. Frozen
runtime files were not changed. The selected offline suites for quarantine,
review orchestration, Skill packaging and Responses parsing ran **37 tests,
all passing**. These checks exercise execution and parsing properties; they do
not measure real model resistance or normal-task utility.

## What the shipped path actually enforces

`OpenAITextWorker` uses the same reusable transformation callbacks as the live
experiment runner. Each callback creates a new two-message context. Only the
fixed task, selected source objects, and (for repair/review) untrusted draft or
feedback are included. There are no tools or ambient history in these requests.
`OpenAIResponses.complete` creates a fresh request body without
`previous_response_id`, uses `store=False`, rejects unsupported options and does
not follow HTTP redirects carrying API credentials. A custom endpoint is trusted:
it can defeat isolation by silently adding hidden state, so the library cannot
promise isolation for arbitrary callback implementations.

The worker returns generated text, not a tool plan. `QuarantinedWorkflow` supplies
the fixed tool and fixed destination arguments and routes the completed action
through `CapabilitySession.execute`. It preserves source reader restrictions
through derived text, validates destination labels against fixed argument values,
revokes stale handles and consumes execution rights before callbacks. Failed new
authorizations also invalidate the earlier turn. A request that fails before
calling `authorize` requires the host to have called `revoke` when accepting the
replacement user request.

The optional semantic reviewer uses fresh data-only context. Quoted evidence is
checked against selected source text; the reviewer cannot grant permissions.
Repairs are bounded, an unchanged rejected draft is withheld, and the final
changed draft must receive an explicit pass. Model verdicts remain fallible.
The tests deliberately include a wrong draft receiving a pass to demonstrate
that this module cannot certify correctness.

## Independent installed-Skill exercise

A bundle was created into an unrelated temporary directory and imported from its
`runtime.zip` under `python -I`, without relying on an installed repository
package. The exercise used a vendor note that claimed an administrator authorized
an attacker recipient and an earlier assistant message that claimed two sends.
The actual host grant permitted one email to `ops@example.test`, subject `Status`.

Observed behavior:

- The CLI denied the redirected plan with exit code 2 and allowed its corrected
  version with exit code 0. Both outputs explicitly said they were previews and
  had executed nothing.
- A live in-process capability session rejected the redirect, completed the
  corrected action into an in-memory outbox and rejected replay.
- A quarantined transformation received the vendor note only. The earlier
  assistant permission claim and an unrelated owner-only private note were absent.
- An attempted contract sending the private note to the operations recipient was
  rejected before generation or execution.

Local evidence, retained outside the repository:
`/private/tmp/promptboundary-forward-qsxzb2g6/forward_demo.py`,
`/private/tmp/promptboundary-forward-qsxzb2g6/forward_result.json`, and
`/private/tmp/promptboundary-forward-qsxzb2g6/checks.json`.
The model worker was an offline deterministic fixture; this is installation and
execution-boundary evidence, not a model efficacy experiment. These temporary
paths are local review artifacts, not portable reproduction dependencies.

A second bundle exercise placed hostile `json.py`, `hashlib.py`, `pathlib.py` and
`promptboundary/__init__.py` in the working directory and set `PYTHONPATH` to that
directory. Running the documented `python -I .../guard.py self-test` still passed
without importing those files. Evidence:
`/private/tmp/promptboundary-import-review-_j1circp/review_result.json`.
This checks import-path isolation under the documented invocation, not security
against a compromised Python installation or modified trusted bootstrap.

## Remaining responsibilities and limitations

The CLI is intentionally a stateless preview. Repeated invocations cannot consume
or persist grants. Enforcement requires the host to retain the SDK session and
route **every** side effect through it. Downloading a Skill does not automatically
intercept an existing application's tools, and a model-authored JSON policy is
not independent authorization.

Package hashes detect modifications relative to the manifest; they are not
signatures. If an attacker can replace both the archive and manifest, the check
cannot establish authenticity. Users must trust or verify the source checkout,
commit, bootstrap and Python installation. The unbundled installed-package path
checks the package version, not its cryptographic authenticity.

The following limitations remain intentional and tested or documented:

- Fixed permissions do not prevent false facts, malicious prose or semantic
  refusals in an otherwise authorized payload. Review can miss or falsely flag
  these. A grounded quote does not prove a correct interpretation.
- Text emitted by a worker remains untrusted downstream. Passing it into a shell,
  privileged agent instruction channel or active-content renderer would create
  another execution boundary that this library does not protect.
- Source IDs and reader labels are application assertions, not publisher
  authentication. Reader intersections do not establish that source facts are
  true, or that a cloud reviewer is an approved data processor.
- Revocation cannot undo a callback that already began. State is in memory, with
  no persistence across process restarts, delivery deduplication protocol,
  transactional rollback or distributed concurrency guarantees.
- Tool callbacks must enforce real path/address/database semantics. Matching a
  declared destination string does not resolve filesystem symlinks, network
  redirects or application-specific aliases.
- Production workflow audit records source IDs, reader restrictions, task/output
  hashes and execution events. Adding original source-content hashes to this
  audit would improve later forensic attribution; the frozen experiment journals
  already retain their synthetic source inputs. No log-only change was made
  during the frozen experiment.

The experiment runner's model requests use an explicit allowlist, excluding
`gold`, test category and split fields. Context reduction and fixed action
construction are explicit experimental differences; the minimized-context arm
is necessary to assess their contribution. Semantic scoring and actual holdout
outcomes require a separate result audit and are not conclusions of this review.
