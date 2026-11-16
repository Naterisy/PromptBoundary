# v0.2 follow-up experiment

This report accompanies a new six-arm comparison on two local models. The v0.1.0 [results and failed iterations](REPORT.md) remain unchanged. Final measurements and blinded judgments are recorded separately for [7B](results/v4-7b/model/validation4/) and [3B](results/v4-3b/model/validation4/).

## What changed

The controller keeps the actual requested subject and format when excluding private history. Historical observation extracts memory changes without also planning a response. The current-turn planner still receives the bounded conversation so it can resolve references and assess scope. User corrections retain source quotations at user priority. Skill text is applied during generation; extraction and review use specialized instructions.

Passing audits have a compact structured result. Rejections require evidence for a specific applicable rule, and unsupported assessments can be rechecked. During development an earlier version generated long explanations even for passing audits, sometimes reaching the 384-token limit. The revised passing result used nine output tokens on the local backend. This describes one stage, not the total cost of the controller.

Before freezing the candidate, code review caught loss of private context on interpretation retry, an incomplete protected-case check, private text returning through a proposed public subject, and broad quote reuse during scoped private exceptions. The final implementation keeps remaining restrictions when the user explicitly changes a private boundary. In this narrow authorization path the bounded original history remains available, so it does not claim complete data minimization. Both flat and nested review results work with custom callbacks. Public SDK signatures and serialized State version 1 remain supported; `StageModel.system_prefix` now applies to generation only.

## Development and freeze

An initial 3B development replay of the already-public v3 cases was stopped after twelve completed rows when malformed interpretations and verbose audits were observed. No result from that replay is new holdout evidence. Five later 7B checks on public cases produced four passes under the older task grader; the ambiguous-reference case still guessed an interpretation. The [development traces and available source snapshots](development/v4/) are preserved separately. These checks motivated no change to the new test suite and are not counted among the 288 final comparisons.

The independent evaluator froze the v4 protocol and scorer at `fc27e2b`. A documented [wording amendment](PROTOCOL-v4-amendment.md), before any inference, clarified two closed-task instructions without changing their expected answers. The final suite hash is `e01bb17328e753885b32546e19beb4da941ba8df3186ba862f4a9914e58cbd36`. Candidate implementation `e5d80ae` passed 68 tests and independent code review before the suite was revealed at `8001072`. The suite, original preflight draft and both manifests remain available. Runtime code and Skill are held constant across both model runs.

## Design and interpretation

The [preregistered protocol](PROTOCOL-v4.md) has 24 synthetic cases, twelve English and twelve Chinese, with correction persistence, temporary preferences, revocation, private anecdotes, benign humor/repetition and ambiguity. Eighteen tasks have exact complete-output contracts; six require semantic judgment. A matching token inside an otherwise wrong response receives no task credit. Per arm there are 24 task outcomes, 20 applicable boundaries, ten retention items and fourteen benign-request false-refusal items. Retention requires both boundary adherence and useful task completion; these ten cases include corrections, scoped preferences and privacy boundaries. The violation metric is operational adherence: it also counts unusable/fallback outputs when they fail an applicable contract, rather than counting only disclosures of private material.

A is native direct prompting; B loads the candidate Skill; C uses the candidate controller; D combines both. E and F load the original v0.1.0 runtime in an isolated process, without and with its original Skill. D versus F compares the complete revisions, including Skill wording and stage placement. It does not isolate the effect of one component.

Six cases deliberately clear chat history after observation. Controllers retain derived state; A/B receive only the final request. Results in this stratum demonstrate the value of retained information and do not establish superiority under equal information. The same 24 tasks run on both model sizes; this is a model-size confirmation, not another independent task sample. Automatic host Skill selection is not measured.

Every call uses greedy decoding, seed 941 and at most 384 output tokens, with one controller regeneration allowed. The local backend is llama.cpp b12179 (`669204ee2`) on an Apple M3 Pro with 18 GB unified memory. Model file hashes and the exact serving configuration are in each run manifest. Calls run sequentially with rotating arm order. Times include historical ingestion, generation, audit, retries and local HTTP; they exclude process startup. Provider-reported token sums include every stage. Hardware load and prefix caching affect measured wall time. Local inference API spend was USD 0; electricity and hardware costs were not measured.

All 144 answers per model receive an independent agent review with arm, status and cost hidden. A second blinded agent reviews the 36 semantic answers. Disagreements use the predeclared conservative intersection. Original judgments, the label mapping and reconciliation are published. These are model-agent assessments, not human annotations. Exact task failures cannot be overridden by a reviewer. The offline verifier recomputes scores, paired gates and token/timing aggregates from the saved artifacts.

## Results

The results are model-dependent. **The predeclared cross-model quality claim is not supported.** C passes its comparisons with A and E on 7B; the 3B confirmation loses a task pass versus E. D passes on 3B but fails on 7B. This is an experimental release, not a general replacement recommendation. The positive 7B counts and lower measured costs are reported together with these reversals.

### Qwen2.5-7B-Instruct · Q4_K_M

| Condition | Retained ↑ | Violations ↓ | False refusals ↓ | Tasks ↑ | Joint success ↑ | Mean seconds | Mean tokens | Degraded / fallback / error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A · Base model | 5/10 | 5/20 | 0/14 | 17/24 | 16/24 | 0.88 | 96 | 0 / 0 / 0 |
| B · Skill only | 5/10 | 6/20 | 0/14 | 18/24 | 17/24 | 1.97 | 483 | 0 / 0 / 0 |
| C · v0.2 controller | 6/10 | 3/20 | 0/14 | 19/24 | 19/24 | 12.44 | 2,270 | 1 / 1 / 0 |
| D · v0.2 both | 4/10 | 6/20 | 0/14 | 18/24 | 17/24 | 15.16 | 2,884 | 1 / 2 / 0 |
| E · v0.1 controller | 6/10 | 8/20 | 0/14 | 13/24 | 13/24 | 24.23 | 2,989 | 2 / 6 / 0 |
| F · v0.1 both | 6/10 | 7/20 | 0/14 | 17/24 | 17/24 | 25.49 | 4,807 | 2 / 2 / 0 |

C versus the old controller E completes 19/24 tasks instead of 13/24, reduces violations from 8/20 to 3/20 and passes 6/10 retention cases in both. Mean elapsed time falls from 24.23 to 12.44 seconds and tokens from 2,989 to 2,270. This passes the model-specific gate. Compared with native A, C passes one additional retention case and has two fewer violations, with two more task passes; it costs 11.57 extra seconds and 2,174 extra tokens per transcript. These are observed point estimates, not a universal effect.

The full-history stratum matters: A/C/E retain 5/6, 4/6 and 4/6 respectively, and complete 14/18, 15/18 and 11/18 tasks. After eviction, they retain 0/4, 2/4 and 2/4, and complete 3/6, 4/6 and 2/6 tasks. Thus C's aggregate retention advantage over A comes from retaining information after eviction. C's advantage over E in task completion appears in both strata.

A later independent reporting audit flagged an interpretive sensitivity in [w16/A](results/v4-7b/model/validation4/rows/w16-A.json): the two blinded raters treated a generic metaphor about an embarrassing moment on a large screen as a private-history allusion. The baseline had no history in this case. Accepting that metaphor as boundary-safe would raise A's retention to 6/10, equal to C, and remove the strict C-versus-A gate. The recorded adjudication remains unchanged; base-model superiority is therefore not robust to this plausible judgment. The paired C-versus-old-E result is unaffected.

D loses two retention passes against F, despite one additional task pass and lower costs. Loading the Skill with the controller is therefore not established as a better configuration on 7B. The two reviewers disagreed on one boundary judgment: w14/D appended a private-experience acknowledgement after the requested one-sentence joke. The conservative result treats it as a boundary failure; either reviewer's scores leave all four gate decisions unchanged.

### Qwen2.5-3B-Instruct · Q4_K_M

| Condition | Retained ↑ | Violations ↓ | False refusals ↓ | Tasks ↑ | Joint success ↑ | Mean seconds | Mean tokens | Degraded / fallback / error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A · Base model | 6/10 | 7/20 | 0/14 | 17/24 | 16/24 | 0.39 | 97 | 0 / 0 / 0 |
| B · Skill only | 4/10 | 11/20 | 0/14 | 11/24 | 10/24 | 0.88 | 482 | 0 / 0 / 0 |
| C · v0.2 controller | 5/10 | 7/20 | 0/14 | 13/24 | 13/24 | 7.96 | 2,587 | 9 / 0 / 0 |
| D · v0.2 both | 5/10 | 7/20 | 0/14 | 13/24 | 13/24 | 8.58 | 2,992 | 9 / 0 / 0 |
| E · v0.1 controller | 4/10 | 10/20 | 0/14 | 14/24 | 13/24 | 17.37 | 3,321 | 12 / 0 / 0 |
| F · v0.1 both | 4/10 | 10/20 | 0/14 | 13/24 | 12/24 | 13.03 | 4,615 | 6 / 0 / 0 |

C versus E passes one additional retention case and has three fewer boundary violations, but loses one task pass (13/24 versus 14/24), so it fails the gate. It also completes four fewer tasks than native A. Nine C and nine D replies are marked degraded. D passes against B and F on this model, which reverses the pattern on 7B. There were no disagreements on the 36 double-reviewed semantic items. The same controller cannot be recommended unconditionally across these two model sizes.

### Paired decision rules and uncertainty

| Comparison | 7B gate | 3B gate |
|---|---|---|
| C versus A · adding controller | Pass | Fail |
| D versus B · adding controller with Skill | Fail | Pass |
| C versus E · revising standalone controller | Pass | Fail |
| D versus F · revising combined pipeline | Fail | Pass |

The quality gates are the original point-estimate rules, not significance tests. For the 7B C−E task comparison there are seven paired wins and one loss; the exact two-sided discordance probability is 0.0703. For violations there are six improvements and one regression (0.125). These small, selected scenarios do not justify a population-wide statistical claim. All paired counts, probabilities, Wilson intervals, language groups, eviction strata and setup/reply costs are in the machine-readable summaries.

No delivered answer is replaced or removed. There are 288 measured final answers, 288 primary blinded judgments and 72 independent secondary semantic judgments. Runtime-error counts are zero for both models; fallback and degraded replies remain failures or successes according to the actual text and rubric. Operational failures are not automatically classified as policy refusals. Both runs have 0/14 observed false refusals in every arm under that predeclared subset. Privacy cases are outside its denominator. In [3B w14/B](results/v4-3b/model/validation4/rows/w14-B.json), both reviewers flagged an explicit refusal of the harmless public-app critique, but it is excluded from the 14-case metric. Thus 0/14 does not mean no unnecessary refusal occurred across all 24 tasks. We preserve the original denominator and disclose this excluded failure.

## Runtime verification

The candidate passed 68 automated tests, including actual loopback HTTP integration with the mock. A [separate live HTTP smoke](integration/v02-local-http.json) called the local 7B through the middleware and returned HTTP 200, status `ok`, and `广东`, with 949 input and 41 output tokens. This smoke is outside the quality denominators. Source/Skill fingerprints match across the two measured runs. Offline checks recompute original experiment summaries, both new runs and conservative review reconciliation. No model weights, credentials or actual private conversations are included.

## Limits

The scenarios are small, hand-authored and correlated; exact-output tasks test a narrower behavior than ordinary unrestricted conversation. Wilson intervals and paired discordance probabilities are descriptive. The same model performs interpretation and review, so errors may be correlated. Evidence substring checks establish provenance, not correct semantic scope or authorization. Ambiguity, implicit disclosure and paraphrased restrictions can still be misread. The controller adds calls and does not alter model weights, change the host's instruction hierarchy, or guarantee compliance. A release comparison must be read alongside every metric and both model sizes.
