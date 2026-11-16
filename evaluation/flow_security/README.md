# Reproduce the nonliteral information-flow experiments

This extension tests summaries, translations and calculations rather than the
literal-field copying measured in the preceding experiment. Read
[DELIVERY.zh-CN.md](DELIVERY.zh-CN.md) for the final conclusions, costs, failures
and limitations. This page describes how to inspect and reproduce the evidence;
passing the reproduction checks does not by itself establish security efficacy.

## Install and verify without an API key

The implementation remains on the existing PR branch until the user approves a
merge. All commands below run from the repository root:

```sh
git clone --branch hosted-runtime-evaluation https://github.com/Naterisy/PromptBoundary.git
cd PromptBoundary
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
python -m evaluation.flow_security.verify_all
python -m evaluation.agent_security.verify_all
```

Python 3.10 or newer is supported. Runtime dependencies are standard-library
only; the build backend is pinned in `pyproject.toml`. `pip install` may download
that build backend. The tests and report verification make no API calls.

`flow_security.verify_all` checks frozen input hashes, saved code snapshots,
recomputed per-case effects/statistics and public-journal sanitization for every
completed `flow_*/SUMMARY.json` batch. The preceding `agent_security` verifier
also checks the earlier experiment artifacts and cumulative ledger. These checks
read saved evidence; they do not regenerate model responses.

To try the actual SDK wiring with an in-memory outbox:

```sh
python -m examples.quarantined_openai
python scripts/package_skill.py --destination /tmp/promptboundary-skills
python -I /tmp/promptboundary-skills/promptboundary-tools/scripts/guard.py self-test
```

The default example is an explicitly labelled offline fixture. It is not an
LLM experiment and sends no email. The Skill installer refuses to overwrite an
existing folder. See [Skill installation](../../docs/skill-installation.md) and
[quarantine integration](../../docs/quarantine.md) for installation in an actual
agent host. The Skill checker is advisory unless the host routes every side
effect through the runtime.

## Data, protocol and independence

- [dev.json](dev.json): 12 cases — 6 attacks, 4 normal tasks and 2 false-source
  sentinels. Development iterations may use these outputs.
- [test.json](test.json): 44 independently authored cases — 24 attacks, 16 normal
  tasks and 4 false-source sentinels. The test cases were frozen before any model
  calls on this cohort, and were not used to tune the final runtime variants.
- [freeze.json](freeze.json) records hashes of both cohorts, the scorer, authoring
  script and [original protocol](PROTOCOL.md). The [protocol addendum](PROTOCOL_ADDENDUM.md)
  records extra variants and analysis choices before holdout evaluation.
- [runtime_freeze.json](runtime_freeze.json) records the implementation fixed for
  the independent run. Each run additionally saves the exact source files used.

A separate AI agent authored and froze the cases and scoring predicates. This
is independent **AI** authoring/review, not human annotation. Neither the runtime
nor the model receives the test's gold answers, attack goals or fact predicates.
The host contract contains the user's operation, selected source IDs and fixed
destination; it does not contain the expected transformed answer.

The 24 injection cases include privacy disclosure, control-flow redirection,
stale authorization and payload corruption. Normal cases cover useful nonliteral
tasks. Four deliberately false-source sentinels expose the fact-authentication
limit; they are separate from the attack and normal denominators. All records,
private canaries, tool effects and `example.test` addresses are synthetic.

The threat model and outcome separation follow public methods, without copying
their leaderboards or claiming their benchmark scores:
[AgentDojo](https://github.com/ethz-spylab/agentdojo),
[InjecAgent](https://arxiv.org/abs/2403.02691), and
[CaMeL](https://arxiv.org/abs/2503.18813).
The exact adaptation and originality limits are documented in the protocol.

## Systems being compared

| Runner arm | Model context and execution |
|---|---|
| `raw` | Reasonable host-contract instructions, full supplied context, model-proposed actions applied to the sandbox. |
| `capability` | Same initial context; the preceding v0.3 tool Runtime checks the entire plan, with at most one repair. |
| `minimized` | Same planner and capability executor, but only contract-selected sources and no ambient conversation. |
| `flow` | Data-only text worker with selected sources; trusted host code constructs the fixed operation and destination. |
| `reviewed` | Same flow, plus a separate call to the same model for semantic review; at most one revision and a final pass. |
| `hybrid` | Separately named experiment using GPT-4.1 mini generation and GPT-5.4 mini review. All calls from both models count. |

The protocol's `minimized_capability` maps to runner arm `minimized`. The old
Runtime comparator here is the v0.3 tool capability executor, not the v0.1
conversational auditor. The minimized and flow arms deliberately change context
exposure; this is an ablation, not a claim of identical prompts. Every model uses
the same frozen case set for each included arm. Review changes the number of calls
and cost. Hybrid also changes model capacity, so direct GPT-5.4 mini generation is
an essential comparator rather than an interchangeable equal-budget baseline.

Worker and reviewer calls use the installed SDK's
`promptboundary.transforms` adapters. They receive fresh task/source contexts,
not privileged tools or ambient conversation. Provider output limits are 768
tokens per physical call; supported reasoning models use low effort, GPT-4.1
omits the reasoning option, service tier is standard and scheduling seed is 193.
The provider is not deterministic, so reproducing the code and inputs does not
promise byte-identical model output.

## Run a new paid reproduction

The following commands are optional and billable. Set `OPENAI_API_KEY` securely in
your own environment beforehand; do not put a key in the repository or command
arguments. First obtain a new inventory from the actual API. The runner refuses
IDs absent from that inventory and only accepts IDs with known pricing entries.

```sh
pb_repro_dir="$(mktemp -d)"
python -m evaluation.hosted.inventory --out "$pb_repro_dir/models.json"
```

The project's recorded inventory is
[`flow_models.json`](../agent_security/results/flow_models.json). It establishes
access for the account and time tested, not availability on every account.
Use only the listed model IDs that your own new inventory confirms. The following
full-cohort command has **no paid calls until `--execute` is added**:

```sh
python -m evaluation.flow_security.run \
  --suite evaluation/flow_security/test.json \
  --inventory "$pb_repro_dir/models.json" \
  --budget "$pb_repro_dir/budget.json" \
  --out "$pb_repro_dir/test1" \
  --models gpt-6.1-sol gpt-6-astra gpt-5.4-mini-2026-03-17 \
           gpt-4.1-mini-2025-04-14 gpt-6-luna \
  --arms raw capability minimized flow reviewed --workers 4
```

Remove unavailable model IDs before scheduling; keep the complete 44-case cohort
for every included model/arm. For an authorized real run, repeat the command with
`--execute`. Use `dev.json` instead of `test.json` only for a separately named
development run. Do not tune on holdout outputs and describe the reused cohort
as independently validating that change.

To reproduce the separately labelled hybrid comparison, use the same budget file
and a new output directory:

```sh
python -m evaluation.flow_security.run \
  --suite evaluation/flow_security/test.json \
  --inventory "$pb_repro_dir/models.json" \
  --budget "$pb_repro_dir/budget.json" \
  --out "$pb_repro_dir/hybrid-test1" \
  --models gpt-4.1-mini-2025-04-14 --arms raw hybrid --workers 4
```

Again, append `--execute` only when authorizing paid calls. Hybrid's reviewer ID
is fixed in the recorded experiment to `gpt-5.4-mini-2026-03-17`; the runner checks
its availability too. The SDK allows a separately configured reviewer endpoint,
but changing that endpoint creates a new experiment.

The **default budget path is the project's historical ledger**. Do not use that
path for someone else's new reproduction, erase past charges or reset it to obtain
more spending room. The commands above choose a fresh personal ledger and reuse it
across batches. Its hard admission ceiling is $9.50, leaving $0.50 below a $10
authorization; it is a ceiling, not a prediction of a batch's price. Review,
recovery, refusals and failed calls with unknown usage all consume budget exposure.
The project continuation shared the earlier authorization, with $6.634151435
already consumed before these experiments began. Its actual cumulative results
remain in the delivery report and shared ledger.

Every call reserves a conservative maximum under a cross-process file lock before
transmission, then settles from provider usage. Unknown usage retains its reserve;
unpriced model/tier or a broken reservation halts the ledger. The runner prints
cumulative known/exposed dollars after each case. A batch that cannot fit is not
successful security evidence; budget-blocked cells stay visible as errors.

Use a **new output directory for every full run**. An interrupted run can leave
an exclusive `.jsonl` journal without a completed result. Do not delete it or
blindly retry only missing/error cases: preserve the partial batch, inspect its
ledger and start a separately named full repetition if budget permits. Do not
reuse an output directory after changing any case, model list or code snapshot.

## Reports, logs and cost accounting

Recorded batches are under
[`evaluation/agent_security/results`](../agent_security/results/), using
`flow_dev1`, `flow_dev2`, `flow_dev3`, `flow_hybrid_dev`, `flow_test1` and
`flow_hybrid_test1`. Each completed batch has `SUMMARY.md` and `SUMMARY.json`,
case inputs, a manifest, code snapshots, per-case results and physical-request
JSONL journals. Successes and failures are retained together. The development
history, including phase-parsing defects and unsuccessful protection iterations,
is in [DEVELOPMENT.md](DEVELOPMENT.md); old failures were not relabelled after fixes.

Generate and then verify a report for a complete reproduction:

```sh
python -m evaluation.flow_security.report "$pb_repro_dir/test1"
python -m evaluation.flow_security.report "$pb_repro_dir/test1" --check
```

Reports separate delivered attack success, attempted actions, normal task pass,
false refusal, unauthorized effects, reply-canary disclosure and false-source
sentinels. API errors, timeouts, incomplete output, parse failures and tool errors
remain separate technical outcomes, never credited as successful protection.
The frozen fact scorer accepts specified paraphrases but is not a universal
semantic judge. [AUDIT_PLAN.md](AUDIT_PLAN.md) requires separate review of
failures, refusals and scorer limitations without silently changing frozen scores.

`SUMMARY.json` includes all per-case decisions, valid/total denominators, Wilson
intervals, exploratory paired exact tests, p50/p95 wall-clock latency, token totals
and usage-priced cost. Small authored samples and multiple comparisons limit
claims. A zero raw-model attack rate cannot demonstrate an incremental improvement.

Prices are recorded in [pricing_verified.json](pricing_verified.json), using
official [API pricing](https://developers.openai.com/api/docs/pricing) and model
pages for [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini),
[GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) and
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna).
`GET /v1/models` confirms IDs but **does not return prices**. Check current official
prices before a future live reproduction; changing rates must be recorded as a
new experiment configuration. Reported costs are calculations from provider usage
and these rates, not a billing invoice.

Public journals preserve observable model text, requests, API IDs, usage and
effects. Opaque provider continuation/reasoning state and account-associated program metadata is replaced with hashes and
byte counts in the shareable copy. Keep the full original journals privately
before sanitizing a copy:

```sh
python -m evaluation.hosted.public_logs /path/to/shareable-copy
python -m evaluation.hosted.public_logs /path/to/shareable-copy --check
```

That sanitizer is specific to provider state in synthetic experiment logs; it is
not a general private-conversation or secret scrubber. Never publish a real API
key, authorization header or confidential application input.

The paid runner and shared budget ledger require Linux or macOS (`fcntl` file
locking). The runtime and offline Skill use the Python standard library; these
experiments and CI were validated on macOS/Linux, not every Agent host or OS.

Three complete repetitions (`flow_confirm1`, `flow_confirm2`, `flow_confirm3`)
reuse the same 44 cases for the raw/hybrid pair. Their cluster-bootstrap report
is `evaluation/agent_security/results/FLOW_CONFIRMATION.*`. Cases, not requests
or repetitions, are the units: 24 injection cases and 16 normal cases, with four
source-fact sentinels reported separately. Rebuild it with:

```sh
python -m evaluation.flow_security.confirmation_report \
  evaluation/agent_security/results/flow_confirm1 \
  evaluation/agent_security/results/flow_confirm2 \
  evaluation/agent_security/results/flow_confirm3
```
