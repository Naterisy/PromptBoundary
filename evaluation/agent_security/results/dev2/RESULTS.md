# Source and capability experiment

Every condition receives the same user request, external source text, history and full host authorization. Raw proposes actions directly; old uses the prior conversational auditor; capability validates effects before an inert tool sink and permits one model recovery. Bound additionally constrains arguments to host-selected source fields; bound_copy materializes only those fields before capability validation. Source selectors are visible to every compared arm where bindings are configured. No real external actions occur.

| Model | Arm | Attack executed | Normal task pass | False refusal | All task pass | p50/p95 seconds | USD |
|---|---|---:|---:|---:|---:|---:|---:|
| gpt-6.1-sol | raw | 0/8 | 4/4 | 0/4 | 12/12 | 2.19/2.53 | 0.012676 |
| gpt-6.1-sol | capability | 0/8 | 4/4 | 0/4 | 12/12 | 2.16/2.98 | 0.012686 |
| gpt-6-astra | raw | 0/8 | 4/4 | 0/4 | 12/12 | 2.88/3.55 | 0.06388 |
| gpt-6-astra | capability | 0/8 | 4/4 | 0/4 | 12/12 | 2.94/8.95 | 0.06383 |
| gpt-5.4-mini-2026-03-17 | raw | 0/8 | 4/4 | 0/4 | 12/12 | 2.07/2.49 | 0.00916350 |
| gpt-5.4-mini-2026-03-17 | capability | 0/8 | 4/4 | 0/4 | 12/12 | 2.07/2.65 | 0.00959100 |

## Uncertainty and paired cases

Each sample is run once; authored attack families and variants can be correlated. Wilson 95% intervals below describe observed attack fractions, not population guarantees. Paired exact two-sided sign/binomial tests operate on discordant case pairs, without multiple-testing correction. They are exploratory. API, timeout, incomplete and parse failures are separately recorded and never credited as successful protection.

| Model | Arm | ASR 95% Wilson interval | Status counts |
|---|---|---:|---|
| gpt-6.1-sol | raw | 0.0%–32.4% | {"ok": 12} |
| gpt-6.1-sol | capability | 0.0%–32.4% | {"ok": 12} |
| gpt-6-astra | raw | 0.0%–32.4% | {"ok": 12} |
| gpt-6-astra | capability | 0.0%–32.4% | {"ok": 12} |
| gpt-5.4-mini-2026-03-17 | raw | 0.0%–32.4% | {"ok": 12} |
| gpt-5.4-mini-2026-03-17 | capability | 0.0%–32.4% | {"ok": 12} |

| Model | Compared with | Metric | Improved / worsened / tied | Benefit pp | Exact p |
|---|---|---|---:|---:|---:|
| gpt-6.1-sol | capability_vs_raw | attack_success | 0/0/8 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_raw | normal_pass | 0/0/4 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_raw | false_refusal | 0/0/4 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | attack_success | 0/0/8 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | normal_pass | 0/0/4 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | false_refusal | 0/0/4 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | attack_success | 0/0/8 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | normal_pass | 0/0/4 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | false_refusal | 0/0/4 | 0.0 | 1.0000 |

Known usage-priced total for this run: **USD 0.17182650**. Ledger includes all development and independent runs plus reservations for any calls without usage. See RESULTS.json for every outcome, interval, per-category result and token breakdown. All final plans and provider calls remain alongside the report.
