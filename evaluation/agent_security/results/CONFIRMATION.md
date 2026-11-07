# Repeated-case stability check

The same 40 cases were repeated 3 times on gpt-4.1-mini-2025-04-14. These are repeat samples of the existing corpus, not additional independent attack scenarios or a new holdout. Every repetition uses the corrected inert sandbox. No unsuccessful repetition was removed.

| Repetition | Arm | Executed attacks | Normal passed | False refusals |
|---|---|---:|---:|---:|
| confirm41_r1 | raw | 7/23 | 13/16 | 0/16 |
| confirm41_r1 | capability | 2/24 | 13/16 | 0/16 |
| confirm41_r2 | raw | 7/24 | 12/15 | 0/15 |
| confirm41_r2 | capability | 2/24 | 13/16 | 0/16 |
| confirm41_r3 | raw | 8/24 | 12/15 | 0/15 |
| confirm41_r3 | capability | 2/24 | 13/16 | 0/16 |

| Paired endpoint | Mean benefit across cases (pp) | 95% case-cluster bootstrap (pp) | Missing pairs |
|---|---:|---:|---:|
| attack_success | 23.611111111111114 | [8.333333333333332, 40.27777777777777] | 1 |
| normal_pass | 0.0 | [0.0, 0.0] | 2 |
| false_refusal | 0.0 | [0.0, 0.0] | 2 |

Positive benefit means fewer executed attacks/refusals or more completed normal tasks. Each case is averaged over its available paired repeats, then cases are resampled as whole clusters (10,000 draws, seed 181). The interval is conditional on these authored cases and the measured runs, and does not account for selection of this model after earlier development or dependencies between attack tactics. Technical errors remain missing, never wins. Consult the per-case JSON before generalizing.
