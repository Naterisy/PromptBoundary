# Source and capability experiment

Every condition receives the same user request, external source text, history and full host authorization. Raw proposes actions directly; old uses the prior conversational auditor; capability validates effects before an inert tool sink and permits one model recovery. Bound additionally constrains arguments to host-selected source fields; bound_copy materializes only those fields before capability validation. Source selectors are visible to every compared arm where bindings are configured. No real external actions occur.

| Model | Arm | Attack executed | Normal task pass | False refusal | All task pass | p50/p95 seconds | USD |
|---|---|---:|---:|---:|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 | raw | 7/24 | 12/15 | 0/15 | 29/39 | 1.76/2.30 | 0.0082672 |
| gpt-4.1-mini-2025-04-14 | capability | 2/24 | 13/16 | 0/16 | 35/40 | 1.93/3.71 | 0.0099864 |

## Uncertainty and paired cases

Each sample is run once; authored attack families and variants can be correlated. Wilson 95% intervals below describe observed attack fractions, not population guarantees. Paired exact two-sided sign/binomial tests operate on discordant case pairs, without multiple-testing correction. They are exploratory. API, timeout, incomplete and parse failures are separately recorded and never credited as successful protection.

| Model | Arm | ASR 95% Wilson interval | Status counts |
|---|---|---:|---|
| gpt-4.1-mini-2025-04-14 | raw | 14.9%–49.2% | {"ok": 39, "tool_error": 1} |
| gpt-4.1-mini-2025-04-14 | capability | 2.3%–25.8% | {"ok": 40} |

| Model | Compared with | Metric | Improved / worsened / tied | Benefit pp | Exact p |
|---|---|---|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | attack_success | 5/0/19 | 20.833333333333332 | 0.0625 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | normal_pass | 0/0/15 | 0.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | false_refusal | 0/0/15 | 0.0 | 1.0000 |

Known usage-priced total for this run: **USD 0.0182536**. Ledger includes all development and independent runs plus reservations for any calls without usage. See RESULTS.json for every outcome, interval, per-category result and token breakdown. All final plans and provider calls remain alongside the report.
