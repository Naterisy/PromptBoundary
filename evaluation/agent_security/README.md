# Reproduce the agent-side security experiments

[Chinese delivery report](DELIVERY.zh-CN.md) · [Frozen protocol](PROTOCOL.md) · [Independent audit](INDEPENDENT_AUDIT.md) · [Capability SDK](../../docs/capabilities.md)

This is a synthetic tool-effect benchmark inspired by public AgentDojo, InjecAgent and BIPIA methods. It is **not an official score on any of those benchmarks**. All destinations, records and data are fictional. The simulator only records emails, files and database updates in memory. No proposed email is sent, no proposed path is written and no external database is changed.

The original answer-review controller is retained as the old arm. The new capability arm checks application-owned tool permissions before execution and permits one model repair after denial. The bound arm additionally checks copied arguments against a host-selected source field. The bound_copy arm materializes those explicitly selected literal values before checking the action; the model still proposes the tool and destination. All compared arms receive the same user request, full host authorization and, when enabled, the same source-binding selectors. No expected answer or attack goal goes to a model or runtime.

## Clean installation and offline verification

Use Python 3.10+ and a POSIX environment (macOS or Linux); the budget ledger uses an OS file lock. The runtime and experiment scripts have no third-party runtime dependency. These commands run from the repository root.

~~~sh
git clone --branch hosted-runtime-evaluation https://github.com/Naterisy/PromptBoundary.git
cd PromptBoundary
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
python -m examples.capability_agent --attack
~~~

The example uses scripted inputs by default and makes no API call. It is a wiring check, not a model efficacy result. To recompute the original frozen held-out tables and the cumulative ledger from committed provider journals:

~~~sh
python -m evaluation.agent_security.report evaluation/agent_security/results/test1 --suite evaluation/agent_security/test.json --check
python -m evaluation.agent_security.report evaluation/agent_security/results/test_controls --suite evaluation/agent_security/test.json --check
python -m evaluation.agent_security.report evaluation/agent_security/results/challenge_test1 --suite evaluation/agent_security/challenge_test.json --check
python -m evaluation.agent_security.report evaluation/agent_security/results/challenge_old_control --suite evaluation/agent_security/challenge_test.json --check
for run in confirm41_r1 confirm41_r2 confirm41_r3; do
  python -m evaluation.agent_security.report "evaluation/agent_security/results/$run" --suite evaluation/agent_security/test.json --check
done
python -m evaluation.agent_security.ledger_report evaluation/agent_security/results --check
~~~

The report verifies input identities and archived source hashes, re-scores effects, and sums real provider usage. It preserves early invalid tool-argument rows and labels their outcomes as tool errors. The independent audit separately explains lexical false-refusal undercounting and the sensitivity of exact-copy utility to a terminal newline. The primary frozen scorer is never silently replaced.

## New API run

Keep OPENAI_API_KEY in your existing secret store or environment, outside the checkout. Do not put it into a shell command that will be saved in a shared report. The runner checks actual API model inventory before generation, and starts billable calls only with --execute. Use a fresh result directory, but **share one budget ledger across every run in the same budget**.

~~~sh
mkdir -p work/reproduce-agent-security
run_dir="$PWD/work/reproduce-agent-security"
python -m evaluation.hosted.inventory --out "$run_dir/models.json"

python -m evaluation.agent_security.run \
  --suite evaluation/agent_security/dev.json \
  --out "$run_dir/dev" --inventory "$run_dir/models.json" \
  --budget "$run_dir/budget.json" \
  --models gpt-6.1-sol gpt-6-astra gpt-5.4-mini-2026-03-17 \
  --arms raw old capability --workers 6 --execute

python -m evaluation.agent_security.run \
  --suite evaluation/agent_security/test.json \
  --out "$run_dir/test" --inventory "$run_dir/models.json" \
  --budget "$run_dir/budget.json" \
  --models gpt-6.1-sol gpt-6-astra gpt-5.4-mini-2026-03-17 \
  --arms raw old capability --workers 6 --execute

python -m evaluation.agent_security.report "$run_dir/test" \
  --suite evaluation/agent_security/test.json
~~~

For the final source-copy variant, use the separately frozen challenge and its host metadata. The selectors name a source and field, not the expected field value. This suite includes 24 attacks and 16 normal tasks.

~~~sh
python -m evaluation.agent_security.run \
  --suite evaluation/agent_security/challenge_test.json \
  --bindings evaluation/agent_security/challenge_test.bindings.json \
  --out "$run_dir/challenge" --inventory "$run_dir/models.json" \
  --budget "$run_dir/budget.json" \
  --models gpt-6.1-sol gpt-6-astra gpt-5.4-mini-2026-03-17 gpt-4.1-mini-2025-04-14 gpt-6-luna \
  --arms raw capability bound_copy --workers 6 --execute

python -m evaluation.agent_security.report "$run_dir/challenge" \
  --suite evaluation/agent_security/challenge_test.json
python -m evaluation.agent_security.ledger_report "$run_dir"
~~~

These commands illustrate how to reproduce each condition; they are not a promise that all requested cells will fit a particular account's budget or access rights. A model missing from the account inventory fails preflight rather than silently substituting another name. Current aliases, provider sampling and server behavior can change. Repeating the procedure need not yield identical model text or rates.

## Budget and pricing

The new authorization was USD 10. The ledger in budget.py admits a call only when current exposure plus its conservative reservation fits **USD 9.50**, preserving USD 0.50 of margin. It uses request UTF-8 bytes plus framing allowance and the configured maximum output count to reserve against the highest applicable input/cache rate. Each actual usage record settles that reservation; an attempt without usage keeps the reservation. An unexpected model, tier, token breakdown or usage above reservation halts further calls. Concurrent workers use a shared file lock and atomic writes.

Each new response has a reservation ID, request body, raw provider response or error, elapsed time and usage. ledger_report.py matches every billed response to its reservation, including development, adaptive, interrupted and unsuccessful calls. Do not delete, reset or create a different ledger to bypass the limit. A separate future user-authorized budget needs a clearly separate accounting scope.

The available models were queried through /v1/models; the returned names and per-model details are saved in [results](results). The model-list and model-detail endpoints did not contain prices. Rates were therefore verified from [official OpenAI pricing documentation](https://developers.openai.com/api/docs/pricing) and recorded with their source URLs, rather than claiming a nonexistent pricing API. USD estimates include cached reads/writes and reasoning within output, before account credits and taxes. They are not account invoices.

## Artifacts and study boundaries

- The two freeze manifests preserve the original and challenge fixtures, scorer, source selectors and selector-construction code. Expected actions and attacker goals are evaluator-only.
- Each run directory contains a manifest, archived code under code/, model/arm/case JSON rows and per-case JSONL provider journals. Rows include proposed plans, denied actions, repair feedback, materialized fields and the actual simulated effects.
- An old run's archived code is the authoritative implementation for that run. To re-execute it, overlay its code/ tree on a disposable full checkout before invoking the recorded runner. Current code intentionally fixes earlier sink validation; do not relabel a rerun with current code as the exact original implementation.
- Completed cells are not overwritten. A partially claimed journal is not automatically replayed because a final request may already have been billed. Keep it and use a new run directory for a deliberate retry; retain the same budget ledger.
- Public synthetic journals preserve observable model text, structured replies, timing and usage. Opaque provider continuation-state blobs are replaced by hashes before sharing. Never use this logging mode on private user conversations without an appropriate retention policy.
- Per-model confidence intervals and paired comparisons are exploratory with small, correlated hand-authored attack families. A zero raw ASR supplies no measurable benefit to attribute to the runtime. Sixteen normal cases cannot establish a five-percentage-point population noninferiority margin.
- A copied source field may itself be poisoned. Source bindings enforce authorized data flow, not source truth. A model can still hallucinate claims in its free-text reply, and unrestricted side-effect tools outside the gate would bypass protection.

The strongest positive evidence in the original holdout is on 4.1 mini: six paired cases show a harmful first plan, deterministic denial and a useful corrected plan. The 5.4 mini improvement in that first run includes safe first-sample variation and is not by itself causal gate evidence. Luna's initial null-wildcard confusion and semantic false refusals are retained in the [audit](INDEPENDENT_AUDIT.md), not hidden by its zero observed attack count.


## Final recorded outcome and evidence map

The final source-copy challenge gives 4.1 mini 4/24 raw attacks versus 0/24 after source-copy enforcement, with 16/16 normal tasks in both. Four paired changes are mechanistically visible, but the paired exact p is 0.125; the small cohort does not establish a broad population guarantee. Sol and Astra remain at zero in both arms. Three complete repetitions of the original 4.1 mini task suite retain the reduction direction; they repeat the same 40 scenarios rather than adding 120 independent examples.

All new development, adaptive search, held-out, control and repeat calls total **2,877 requests**, **1,841,445 input tokens**, **278,942 output tokens**, and **USD 6.634151435** using provider usage and recorded rates. No call has unknown usage. The previous USD 3.48438980 batch is outside this newly authorized budget. Spending stopped after the planned investigations, not because the budget was exhausted.

| Artifact | Purpose |
|---|---|
| results/dev1, dev2, dev_controls | Initial wiring, development and additional verified model controls; earlier mistakes retained |
| results/test1, test_controls | Original frozen holdout, including the old conversational runtime |
| results/challenge_dev1, bound_dev1, copy_dev1 | Stronger development attacks and staged source-binding iterations |
| results/adaptive1 | All 12 Astra-generated development attacks against Sol, none successful |
| results/challenge_test1 | Five models, same challenge tasks and source selectors, raw/capability/bound_copy |
| results/challenge_old_control | Old-runtime challenge control on 5.4 mini and 4.1 mini |
| results/confirm41_r1, confirm41_r2, confirm41_r3 | Three predeclared complete repetitions on original 4.1 mini tasks |

A post-evaluation UX fix clears the model's stale reply when materialization changes arguments. It has offline regression coverage; archived model outputs and action-effect scores were not replaced or re-run. Build the final user-facing receipt from actual tool results.
