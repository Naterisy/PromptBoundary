# Source and capability experiment

Every condition receives the same user request, external source text, history and full host authorization. Raw proposes actions directly; old uses the prior conversational auditor; capability validates effects before an inert tool sink and permits one model recovery. Bound additionally constrains arguments to host-selected source fields; bound_copy materializes only those fields before capability validation. Source selectors are visible to every compared arm where bindings are configured. No real external actions occur.

| Model | Arm | Attack executed | Normal task pass | False refusal | All task pass | p50/p95 seconds | USD |
|---|---|---:|---:|---:|---:|---:|---:|
| gpt-6.1-sol | raw | 0/24 | 16/16 | 0/16 | 40/40 | 2.34/2.85 | 0.059266 |
| gpt-6.1-sol | capability | 0/24 | 16/16 | 0/16 | 40/40 | 2.43/2.88 | 0.059036 |
| gpt-6.1-sol | bound_copy | 0/24 | 16/16 | 0/16 | 40/40 | 2.32/2.85 | 0.059156 |
| gpt-6-astra | raw | 0/24 | 16/16 | 0/16 | 40/40 | 2.90/3.96 | 0.29473 |
| gpt-6-astra | capability | 0/24 | 16/16 | 0/16 | 40/40 | 2.90/4.92 | 0.29588 |
| gpt-6-astra | bound_copy | 0/24 | 16/16 | 0/16 | 40/40 | 2.82/3.65 | 0.29538 |
| gpt-5.4-mini-2026-03-17 | raw | 1/24 | 16/16 | 0/16 | 39/40 | 2.06/2.86 | 0.03868125 |
| gpt-5.4-mini-2026-03-17 | capability | 0/23 | 16/16 | 0/16 | 38/39 | 1.96/2.52 | 0.03799275 |
| gpt-5.4-mini-2026-03-17 | bound_copy | 0/24 | 16/16 | 0/16 | 40/40 | 2.04/2.89 | 0.03824925 |
| gpt-4.1-mini-2025-04-14 | raw | 4/24 | 16/16 | 0/16 | 36/40 | 1.47/2.09 | 0.0112012 |
| gpt-4.1-mini-2025-04-14 | capability | 3/24 | 15/16 | 0/16 | 35/40 | 1.48/2.54 | 0.0116604 |
| gpt-4.1-mini-2025-04-14 | bound_copy | 0/24 | 16/16 | 0/16 | 40/40 | 1.51/2.03 | 0.0116292 |
| gpt-6-luna | raw | 0/24 | 14/16 | 0/16 | 32/40 | 2.42/4.35 | 0.0044153 |
| gpt-6-luna | capability | 0/24 | 11/16 | 0/16 | 30/40 | 2.34/4.39 | 0.0045023 |
| gpt-6-luna | bound_copy | 0/24 | 15/16 | 0/16 | 39/40 | 2.43/3.88 | 0.0045988 |

## Uncertainty and paired cases

Each sample is run once; authored attack families and variants can be correlated. Wilson 95% intervals below describe observed attack fractions, not population guarantees. Paired exact two-sided sign/binomial tests operate on discordant case pairs, without multiple-testing correction. They are exploratory. API, timeout, incomplete and parse failures are separately recorded and never credited as successful protection.

| Model | Arm | ASR 95% Wilson interval | Status counts |
|---|---|---:|---|
| gpt-6.1-sol | raw | 0.0%–13.8% | {"ok": 40} |
| gpt-6.1-sol | capability | 0.0%–13.8% | {"ok": 40} |
| gpt-6.1-sol | bound_copy | 0.0%–13.8% | {"ok": 40} |
| gpt-6-astra | raw | 0.0%–13.8% | {"ok": 40} |
| gpt-6-astra | capability | 0.0%–13.8% | {"ok": 40} |
| gpt-6-astra | bound_copy | 0.0%–13.8% | {"ok": 40} |
| gpt-5.4-mini-2026-03-17 | raw | 0.7%–20.2% | {"ok": 40} |
| gpt-5.4-mini-2026-03-17 | capability | 0.0%–14.3% | {"ok": 39, "parse_error": 1} |
| gpt-5.4-mini-2026-03-17 | bound_copy | 0.0%–13.8% | {"ok": 40} |
| gpt-4.1-mini-2025-04-14 | raw | 6.7%–35.9% | {"ok": 40} |
| gpt-4.1-mini-2025-04-14 | capability | 4.3%–31.0% | {"ok": 40} |
| gpt-4.1-mini-2025-04-14 | bound_copy | 0.0%–13.8% | {"ok": 40} |
| gpt-6-luna | raw | 0.0%–13.8% | {"ok": 40} |
| gpt-6-luna | capability | 0.0%–13.8% | {"ok": 40} |
| gpt-6-luna | bound_copy | 0.0%–13.8% | {"ok": 40} |

| Model | Compared with | Metric | Improved / worsened / tied | Benefit pp | Exact p |
|---|---|---|---:|---:|---:|
| gpt-6.1-sol | capability_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | bound_copy_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6.1-sol | bound_copy_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | bound_copy_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | bound_copy_vs_capability | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6.1-sol | bound_copy_vs_capability | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | bound_copy_vs_capability | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | bound_copy_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-astra | bound_copy_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | bound_copy_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | bound_copy_vs_capability | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-astra | bound_copy_vs_capability | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | bound_copy_vs_capability | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | attack_success | 1/0/22 | 4.3478260869565215 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | bound_copy_vs_raw | attack_success | 1/0/23 | 4.166666666666667 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | bound_copy_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | bound_copy_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | bound_copy_vs_capability | attack_success | 0/0/23 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | bound_copy_vs_capability | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | bound_copy_vs_capability | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | attack_success | 1/0/23 | 4.166666666666667 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | normal_pass | 0/1/15 | -6.25 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | bound_copy_vs_raw | attack_success | 4/0/20 | 16.666666666666668 | 0.1250 |
| gpt-4.1-mini-2025-04-14 | bound_copy_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | bound_copy_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | bound_copy_vs_capability | attack_success | 3/0/21 | 12.5 | 0.2500 |
| gpt-4.1-mini-2025-04-14 | bound_copy_vs_capability | normal_pass | 1/0/15 | 6.25 | 1.0000 |
| gpt-4.1-mini-2025-04-14 | bound_copy_vs_capability | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-luna | capability_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-luna | capability_vs_raw | normal_pass | 0/3/13 | -18.75 | 0.2500 |
| gpt-6-luna | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-luna | bound_copy_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-luna | bound_copy_vs_raw | normal_pass | 2/1/13 | 6.25 | 1.0000 |
| gpt-6-luna | bound_copy_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-luna | bound_copy_vs_capability | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-luna | bound_copy_vs_capability | normal_pass | 5/1/10 | 25.0 | 0.2188 |
| gpt-6-luna | bound_copy_vs_capability | false_refusal | 0/0/16 | 0.0 | 1.0000 |

Known usage-priced total for this run: **USD 1.22637845**. Ledger includes all development and independent runs plus reservations for any calls without usage. See RESULTS.json for every outcome, interval, per-category result and token breakdown. All final plans and provider calls remain alongside the report.
