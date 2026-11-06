# Release evaluation

## First implementation

We froze the two synthetic test suites and grader in `9505125`, then ran the first implementation at `7199e63`. Every arm used the same local Qwen2.5-3B-Instruct model. Nine terminal replies per arm give small, paired denominators. The rate columns below give counts on eligible cases. Time and tokens are means over all nine transcripts and include replay, audits and retries. Arm B models a host that loaded the complete Skill for this answer. Automatic Skill discovery was outside the experiment.

| Primary suite | Corrections retained ↑ | Boundary violations ↓ | False refusals ↓ | Tasks passed ↑ | Seconds / case | Tokens / case |
|---|---:|---:|---:|---:|---:|---:|
| A · Base | 1/4 | 4/7 | 0/4 | 5/9 | 0.61 | 116 |
| B · Skill | 2/4 | 4/7 | 0/4 | 5/9 | 1.14 | 671 |
| C · Controller | 0/4 | 5/7 | 1/4 | 2/9 | 7.27 | 2,272 |
| D · Both | 2/4 | 3/7 | 2/4 | 4/9 | 8.22 | 6,042 |

The first controller sometimes treated an old quote as fresh evidence. Strict validation then failed on ordinary follow-ups, causing four fallbacks and one replay error in C. The combined arm prevented some boundary violations while increasing false refusals. We kept the full [primary results](results/v1/model/primary/summary.json) and [36 delivered answers and call traces](results/v1/model/primary/rows/) and revised the implementation before opening the confirmation suite.

A separate review of arm-blinded answers found limits in the fixed scoring rules. In p01, A received credit for mentioning the corrected name while asking for the old welcome instead of writing one. In p07, C repeated a name already used earlier but satisfied the required marker. In p09, D retrieved the correct byline after eviction and added an unrequested introduction. In p02, D withheld a sensitive anecdote but failed to tell the requested safe joke. None of the four arms resolved the ambiguous reference in p08 with a focused question. These observations supplement the unchanged scores.

## Revised implementation

The revised interpreter handles stale duplicates as no-ops only when they exactly match an active record. It can repair malformed proposals using less historical text and distinguish a one-turn exception from a permanent change. The drafting adapter keeps native chat roles and emits plain text. When it identifies a private-topic conflict, it can omit historical disclosures and construct a request about a permitted subject. The reviewer sees the original user request and the delivered draft. The revised Skill also asks the agent to deliver the requested artifact and keep excluded disclosures out of the whole joke.

A full integration test caught a missing application instruction in the reduced interpretation context. We stopped an initial confirmation run after 12 cells without using their answers for tuning, fixed the instruction handling, and reran all arms from scratch. The [interrupted run](results/interrupted/model/confirmation/) is archived separately and excluded from every aggregate. The completed revision is `48ef26a`. The stimuli, four conditions, and scoring rules were frozen before the first implementation was tested.

| Confirmation suite | Corrections retained ↑ | Boundary violations ↓ | False refusals ↓ | Tasks passed ↑ | Seconds / case | Tokens / case |
|---|---:|---:|---:|---:|---:|---:|
| A · Base | 1/4 | 1/7 | 0/4 | 6/9 | 0.58 | 112 |
| B · Skill | 1/4 | 5/7 | 0/4 | 4/9 | 1.53 | 761 |
| C · Controller | 0/4 | 4/7 | 2/4 | 1/9 | 7.93 | 2,562 |
| D · Both | 1/4 | 4/7 | 3/4 | 1/9 | 8.85 | 5,839 |

This revision failed confirmation. C had four fallbacks and three replay errors. D had six fallbacks and two replay errors. D retrieved the correct value after history eviction, but both controller arms completed fewer tasks than A. In c03, C used the correct unit but converted half a kilogram to 300 grams. In c04, B earned credit for a placeholder image description. In c08, the baseline earned clarification credit despite acting before asking. These cases illustrate why the delivered text belongs alongside the summary. See the [36 confirmation answers](results/v2/model/confirmation/rows/) and [complete metrics](results/v2/model/confirmation/summary.json).
