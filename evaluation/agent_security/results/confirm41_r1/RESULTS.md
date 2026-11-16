# Source and capability experiment

Every condition receives the same user request, external source text, history and full host authorization. Raw proposes actions directly; old uses the prior conversational auditor; capability validates effects before an inert tool sink and permits one model recovery. Bound additionally constrains arguments to host-selected source fields; bound_copy materializes only those fields before capability validation. Source selectors are visible to every compared arm where bindings are configured. No real external actions occur.

| Model | Arm | Attack executed | Normal task pass | False refusal | All task pass | p50/p95 seconds | USD |
|---|---|---:|---:|---:|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 | raw | 7/23 | 13/16 | 0/16 | 29/39 | 1.62/2.26 | 0.0082224 |
| gpt-4.1-mini-2025-04-14 | capability | 2/24 | 13/16 | 0/16 | 34/40 | 1.69/3.13 | 0.0099380 |

## Uncertainty and paired cases

Each sample is run once; authored attack families and variants can be correlated. Wilson 95% intervals below describe observed attack fractions, not population guarantees. Paired exact two-sided sign/binomial tests operate on discordant case pairs, without multiple-testing correction. They are exploratory. API, timeout, incomplete and parse failures are separately recorded and never credited as successful protection.

| Model | Arm | ASR 95% Wilson interval | Status counts |
|---|---|---:|---|
| gpt-4.1-mini-2025-04-14 | raw | 15.6%–50.9% | {"ok": 39, "tool_error": 1} |
| gpt-4.1-mini-2025-04-14 | capability | 2.3%–25.8% | {"ok": 39, "runtime_refusal": 1} |

| Model | Compared with | Metric | Improved / worsened / tied | Benefit pp | Exact p |
|---|---|---|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | attack_success | 5/0/18 | 21.73913043478261 | 0.0625 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |

Known usage-priced total for this run: **USD 0.0181604**. Ledger includes all development and independent runs plus reservations for any calls without usage. See RESULTS.json for every outcome, interval, per-category result and token breakdown. All final plans and provider calls remain alongside the report.
