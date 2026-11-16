# Source and capability experiment

Every condition receives the same user request, external source text, history and full host authorization. Raw proposes actions directly; old uses the prior conversational auditor; capability validates effects before an inert tool sink and permits one model recovery. Bound additionally constrains arguments to host-selected source fields; bound_copy materializes only those fields before capability validation. Source selectors are visible to every compared arm where bindings are configured. No real external actions occur.

| Model | Arm | Attack executed | Normal task pass | False refusal | All task pass | p50/p95 seconds | USD |
|---|---|---:|---:|---:|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 | raw | 2/8 | 3/4 | 0/4 | 9/12 | 1.35/1.72 | 0.0024296 |
| gpt-4.1-mini-2025-04-14 | capability | 1/8 | 4/4 | 0/4 | 10/12 | 1.48/2.93 | 0.0029812 |
| gpt-6-luna | raw | 0/8 | 3/4 | 0/4 | 9/12 | 2.50/5.57 | 0.0011058 |
| gpt-6-luna | capability | 0/8 | 3/4 | 0/4 | 10/12 | 2.35/9.39 | 0.0012969 |

## Uncertainty and paired cases

Each sample is run once; authored attack families and variants can be correlated. Wilson 95% intervals below describe observed attack fractions, not population guarantees. Paired exact two-sided sign/binomial tests operate on discordant case pairs, without multiple-testing correction. They are exploratory. API, timeout, incomplete and parse failures are separately recorded and never credited as successful protection.

| Model | Arm | ASR 95% Wilson interval | Status counts |
|---|---|---:|---|
| gpt-4.1-mini-2025-04-14 | raw | 7.1%–59.1% | {"ok": 12} |
| gpt-4.1-mini-2025-04-14 | capability | 2.2%–47.1% | {"ok": 12} |
| gpt-6-luna | raw | 0.0%–32.4% | {"ok": 12} |
| gpt-6-luna | capability | 0.0%–32.4% | {"ok": 12} |

| Model | Compared with | Metric | Improved / worsened / tied | Benefit pp | Exact p |
|---|---|---|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | attack_success | 2/1/5 | 12.5 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | normal_pass | 1/0/3 | 25.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | false_refusal | 0/0/4 | 0.0 | 1.0000 |
| gpt-6-luna | capability_vs_raw | attack_success | 0/0/8 | 0.0 | 1.0000 |
| gpt-6-luna | capability_vs_raw | normal_pass | 0/0/4 | 0.0 | 1.0000 |
| gpt-6-luna | capability_vs_raw | false_refusal | 0/0/4 | 0.0 | 1.0000 |

Known usage-priced total for this run: **USD 0.0078135**. Ledger includes all development and independent runs plus reservations for any calls without usage. See RESULTS.json for every outcome, interval, per-category result and token breakdown. All final plans and provider calls remain alongside the report.
