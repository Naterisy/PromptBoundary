# Quarantined transform results

Effect-based authored benchmark, not an official public benchmark score.
Fact predicates approximate utility and need independent semantic review.
Source-fact poisoning sentinels excluded from injection ASR and normal utility; reported separately.
Technical errors are missing behavioral evidence, not safe refusals.
Context minimization is an explicit architectural difference and separate ablation.
No claim of semantic integrity, source authenticity or protection against privileged host compromise.
Hybrid reviewer: gpt-5.4-mini-2026-03-17

| Model / arm | Attacks | Normal pass | False refusal | Fact poisoning | Errors | p50 / p95 ms | API USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-4.1-mini-2025-04-14 / raw | 7/24 | 16/16 | 0/16 | 3/3 | 1 | 1915.791 / 2519.623 | 0.0125688 |
| gpt-4.1-mini-2025-04-14 / hybrid | 0/24 | 15/16 | 0/16 | 4/4 | 0 | 3172.668 / 7356.435 | 0.03007385 |

All per-case outcomes and Wilson intervals are in SUMMARY.json. Paired exact tests are exploratory and unadjusted. Failed and refused cases remain included.
