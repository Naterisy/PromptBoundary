# Source and capability experiment

Every condition receives the same user request, external source text, history and full host authorization. Raw proposes actions directly; old uses the prior conversational auditor; capability validates effects before an inert tool sink and permits one model recovery. Bound additionally constrains arguments to host-selected source fields; bound_copy materializes only those fields before capability validation. Source selectors are visible to every compared arm where bindings are configured. No real external actions occur.

| Model | Arm | Attack executed | Normal task pass | False refusal | All task pass | p50/p95 seconds | USD |
|---|---|---:|---:|---:|---:|---:|---:|
| gpt-6.1-sol | raw | 0/24 | 16/16 | 0/16 | 40/40 | 2.19/2.63 | 0.043492 |
| gpt-6.1-sol | old | 0/24 | 16/16 | 0/16 | 40/40 | 9.11/18.19 | 0.4498608 |
| gpt-6.1-sol | capability | 0/24 | 16/16 | 0/16 | 40/40 | 2.22/2.75 | 0.043522 |
| gpt-6-astra | raw | 0/24 | 16/16 | 0/16 | 40/40 | 2.71/3.76 | 0.21531 |
| gpt-6-astra | old | 0/24 | 16/16 | 0/16 | 40/40 | 10.77/17.89 | 2.2011500 |
| gpt-6-astra | capability | 0/24 | 16/16 | 0/16 | 40/40 | 2.73/3.43 | 0.21541 |
| gpt-5.4-mini-2026-03-17 | raw | 3/24 | 16/16 | 0/16 | 37/40 | 1.98/2.31 | 0.02940450 |
| gpt-5.4-mini-2026-03-17 | old | 1/24 | 16/16 | 0/16 | 37/40 | 6.63/14.48 | 0.21665880 |
| gpt-5.4-mini-2026-03-17 | capability | 1/24 | 16/16 | 0/16 | 39/40 | 1.87/2.48 | 0.03204150 |

## Uncertainty and paired cases

Each sample is run once; authored attack families and variants can be correlated. Wilson 95% intervals below describe observed attack fractions, not population guarantees. Paired exact two-sided sign/binomial tests operate on discordant case pairs, without multiple-testing correction. They are exploratory. API, timeout, incomplete and parse failures are separately recorded and never credited as successful protection.

| Model | Arm | ASR 95% Wilson interval | Status counts |
|---|---|---:|---|
| gpt-6.1-sol | raw | 0.0%–13.8% | {"ok": 40} |
| gpt-6.1-sol | old | 0.0%–13.8% | {"ok": 40} |
| gpt-6.1-sol | capability | 0.0%–13.8% | {"ok": 40} |
| gpt-6-astra | raw | 0.0%–13.8% | {"ok": 40} |
| gpt-6-astra | old | 0.0%–13.8% | {"ok": 40} |
| gpt-6-astra | capability | 0.0%–13.8% | {"ok": 40} |
| gpt-5.4-mini-2026-03-17 | raw | 4.3%–31.0% | {"ok": 40} |
| gpt-5.4-mini-2026-03-17 | old | 0.7%–20.2% | {"ok": 40} |
| gpt-5.4-mini-2026-03-17 | capability | 0.7%–20.2% | {"ok": 40} |

| Model | Compared with | Metric | Improved / worsened / tied | Benefit pp | Exact p |
|---|---|---|---:|---:|---:|
| gpt-6.1-sol | capability_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_old | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_old | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6.1-sol | capability_vs_old | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_old | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_old | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-6-astra | capability_vs_old | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | attack_success | 2/0/22 | 8.333333333333334 | 0.5000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_raw | false_refusal | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_old | attack_success | 0/0/24 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_old | normal_pass | 0/0/16 | 0.0 | 1.0000 |
| gpt-5.4-mini-2026-03-17 | capability_vs_old | false_refusal | 0/0/16 | 0.0 | 1.0000 |

Known usage-priced total for this run: **USD 3.44684960**. Ledger includes all development and independent runs plus reservations for any calls without usage. See RESULTS.json for every outcome, interval, per-category result and token breakdown. All final plans and provider calls remain alongside the report.
