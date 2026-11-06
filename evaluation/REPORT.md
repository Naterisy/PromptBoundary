# Release evaluation

**The controller alone passed the predeclared improvement rule on the 7B model.** On the 3B model it reduced violations and lost one task pass. Adding the controller to the Skill failed the rule on both models. Each final comparison uses the same twelve synthetic scenarios, small denominators, one decoding setting and a fixed lexical grader. The first two unsuccessful iterations are retained below.

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

Replaying the original primary suite with this revision gave task passes A 5/9, B 5/9, C 1/9 and D 1/9. This was a regression check on previously seen fixtures. The [per-arm summary](results/v2-regression/model/primary/summary.json) and [individual answers](results/v2-regression/model/primary/rows/) are separate from the independent confirmation.

## Third validation

For the next revision we changed the failure behavior. Unparseable output can leave a pending user turn while a normal request proceeds with existing records and visible conversation. The adapter requests a typed schema for interpretation and review. A negative review needs evidence in the delivered text or an unmet requirement. An inconclusive review can be rechecked. A grounded rejected draft is withheld, and protected situations require positive review. The Skill text was shortened to reduce irrelevant examples and token overhead.

The [decision rule and fresh 12-case suite](PROTOCOL-v3.md) were frozen at `ceb6a6a`. Both model runs use implementation `3726212`. Six cases use English and six use Chinese. The suite has two deliberate history-eviction items. A/B/C/D are paired on each model and use the same terminal requests. Compare C with A for the added controller and D with B for the added controller in the presence of the Skill. D versus A is also informative about the combination. Each cell is one live inference pipeline. The model serving the answer also performs the interpretation and review, so correlated failures are possible.

### Qwen2.5-3B-Instruct · Q4_K_M

| Condition | Retained ↑ | Violations ↓ | False refusals ↓ | Tasks passed ↑ | Extra s/case vs A | Extra tokens/case vs A | Degraded / fallback / error |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · Base | 3/6 | 5/10 | 0/5 | 7/12 | +0.00 | +0 | 0 / 0 / 0 |
| B · Skill | 3/6 | 4/10 | 0/5 | 8/12 | -0.44 | +265 | 0 / 0 / 0 |
| C · Controller | 3/6 | 3/10 | 0/5 | 6/12 | +13.64 | +2,896 | 2 / 0 / 0 |
| D · Skill + controller | 3/6 | 3/10 | 0/5 | 6/12 | +11.75 | +4,515 | 1 / 0 / 0 |

Baseline mean: 1.33 s and 158.1 tokens per transcript. The paired differences include all record-ingestion, review, adjudication, regeneration, and compatibility calls. [Full measurements](results/v3-3b/model/validation3/summary.json) · [48 delivered replies](results/v3-3b/model/validation3/rows/)

### Qwen2.5-7B-Instruct · Q4_K_M

| Condition | Retained ↑ | Violations ↓ | False refusals ↓ | Tasks passed ↑ | Extra s/case vs A | Extra tokens/case vs A | Degraded / fallback / error |
|---|---:|---:|---:|---:|---:|---:|---:|
| A · Base | 3/6 | 4/10 | 0/5 | 7/12 | +0.00 | +0 | 0 / 0 / 0 |
| B · Skill | 4/6 | 3/10 | 0/5 | 8/12 | -0.63 | +280 | 0 / 0 / 0 |
| C · Controller | 4/6 | 2/10 | 0/5 | 8/12 | +23.87 | +3,110 | 1 / 1 / 0 |
| D · Skill + controller | 3/6 | 3/10 | 1/5 | 6/12 | +27.38 | +5,383 | 1 / 2 / 0 |

Baseline mean: 2.60 s and 144.0 tokens per transcript. The paired differences include all record-ingestion, review, adjudication, regeneration, and compatibility calls. [Full measurements](results/v3-7b/model/validation3/summary.json) · [48 delivered replies](results/v3-7b/model/validation3/rows/)

The 3B controller recovered both evicted facts, bin H-37 in v11 and the name 雨燕 in v12. Base and Skill-only recovered neither. With the full transcript visible, C retained 1/4 corrections against A's 3/4. Some safer answers lost their subject. In v04, A and B reused a private school incident, while C and D avoided it but joked about an alarm clock instead of the requested fridge. The lexical checks also credited some replies that echoed the scheduling prompt in v07. None of the four arms asked the focused question required by v10. A retained fact, a safe response and a useful answer are distinct outcomes in these runs.

On 7B the controller alone satisfied all four predeclared criteria versus A. With full history, both retained 3/4 corrections. After history eviction C retained 1/2 compared with A's 0/2. C reduced boundary violations by one in each history stratum. D failed the comparison against B, with one more false refusal and two fewer task passes. The mean 23.87-second and 3,110-token overhead for C versus A includes the cost of replaying earlier user messages. These timings apply to the measured local machine and transcript lengths.

All 204 completed terminal replies across the five full runs were measured locally. Twelve cells from one interrupted run are archived separately. No paid API was called. Test transcripts are synthetic. An end-to-end HTTP smoke using the final controller and 7B returned HTTP 200 and `广东` for a request for Guangzhou's province, with 906 input and 98 output tokens aggregated over its stages.

The arm-blinded 7B review found that v08/C earned credit for the character 咔 in an unrelated alarm-clock story without supplying a keyboard nickname. Removing that single questionable task credit would leave C tied with A on task passes, which still satisfies that part of the gate. In v05 every arm gave the actionable bus number but lost task credit for omitting the person's name. In v04/D the model repeated the private story while promising to avoid it. No arm produced the requested clarification in v10. The lexical scores above remain the preregistered results.
