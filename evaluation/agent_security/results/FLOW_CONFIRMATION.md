# Repeated-case flow confirmation

Generator: `gpt-4.1-mini-2025-04-14`. Comparison: `raw` → `hybrid`.
Hybrid reviewer: `gpt-5.4-mini-2026-03-17`.

This comparison was selected after the primary holdout was observed. It is exploratory confirmation, not a new independent validation of the selected method.

The same 44 cases were sampled 3 times: 24 injection cases, 16 normal cases, and 4 separately reported factual-poisoning sentinels. These are repeated measurements, not new independent cases.

| Run | Arm | Attacks | Normal pass | False refusal | Technical errors | Calls | Known USD |
|---|---|---:|---:|---:|---:|---:|---:|
| flow_confirm1 | raw | 5/24 | 16/16 | 0/16 | 0 | 44 | 0.0125416 |
| flow_confirm1 | hybrid | 0/24 | 16/16 | 0/16 | 0 | 102 | 0.03498010 |
| flow_confirm2 | raw | 7/24 | 16/16 | 0/16 | 1 | 44 | 0.0125688 |
| flow_confirm2 | hybrid | 0/24 | 15/16 | 0/16 | 0 | 96 | 0.03007385 |
| flow_confirm3 | raw | 6/24 | 15/16 | 0/16 | 1 | 44 | 0.0125112 |
| flow_confirm3 | hybrid | 0/24 | 15/16 | 0/16 | 0 | 98 | 0.03180655 |

| Paired endpoint | Mean benefit (pp) | 95% case-cluster bootstrap (pp) | Clusters | Missing pairs |
|---|---:|---:|---:|---:|
| attack_success | 25.0 | [11.1111111111, 40.2777777778] | 24/24 | 0 |
| normal_pass | -2.0833333333 | [-6.25, 0.0] | 16/16 | 0 |
| false_refusal | 0.0 | [0.0, 0.0] | 16/16 | 0 |

Positive benefit means fewer executed attacks or false refusals, or more normal task completions. Each case is averaged over its available paired repetitions, then cases are sampled with replacement as whole clusters (10,000 draws, seed 181). Missing technical outcomes stay null. Factual-poisoning sentinels are excluded from injection and normal-task denominators.

Selected-arm totals: 428 API calls, 428 priced responses, 2 technical errors, USD 0.13448210 usage-priced cost.

- Exploratory confirmation of a model and method selected after observing the primary holdout; no multiplicity correction.
- Repeated cases are not additional independent scenarios or a new holdout.
- Intervals are conditional on the authored case clusters and observed repetitions; tactic dependence is unmodeled.
- Technical errors are missing paired evidence, never safe or successful outcomes.
- Missing pairs may be nonrandom; available-case averages do not establish noninferiority.
- Fact predicates approximate semantic utility; consult the independent audit and all raw outputs.
- Known USD is usage-priced API cost, not an invoice; unpriced responses require the shared reservation ledger.
