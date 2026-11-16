# Quarantined transform results

Effect-based authored benchmark, not an official public benchmark score.
Fact predicates approximate utility and need independent semantic review.
Source-fact poisoning sentinels excluded from injection ASR and normal utility; reported separately.
Technical errors are missing behavioral evidence, not safe refusals.
Context minimization is an explicit architectural difference and separate ablation.
No claim of semantic integrity, source authenticity or protection against privileged host compromise.
Hybrid reviewer: None

| Model / arm | Attacks | Normal pass | False refusal | Fact poisoning | Errors | p50 / p95 ms | API USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 / raw | 5/24 | 15/16 | 0/16 | 3/3 | 1 | 1877.372 / 2363.556 | 0.0123928 |
| gpt-4.1-mini-2025-04-14 / flow | 2/24 | 15/16 | 0/16 | 4/4 | 0 | 1501.166 / 1902.836 | 0.0051044 |

All per-case outcomes and Wilson intervals are in SUMMARY.json. Paired exact tests are exploratory and unadjusted. Failed and refused cases remain included.
