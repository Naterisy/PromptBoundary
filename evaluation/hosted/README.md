# Reproduce the hosted PromptBoundary comparison

[Results and paired changes](results/main/RESULTS.md) · [Machine-readable scores and usage](results/main/RESULTS.json) · [Case design and scoring rules](PROTOCOL.md) · [Diagnosis of earlier benign failures](DIAGNOSIS.md) · [Runtime trust model](../../docs/runtime-security.md)

Use the repository checkout for these commands (Python 3.10+). The runtime and evaluation use only the standard library. To re-score the committed data **offline**, without an API key:

```sh
python -m evaluation.hosted.report --check
python -m evaluation.hosted.stress.report --check
python -m unittest discover -s tests -v
```

Each of the 32 cases has one fixed final request. Earlier turns are authored fixtures. The three conditions are the raw API, the controller from Git commit `cd5ee311c7637a6100a4c5392ea802419f16c3ed`, and the patched controller. The two controller arms use the actual middleware request handler and independently regenerate their stage calls. No evaluated secret list, expected output, case label or scorer accompanies any request. The application message itself contains each case's trusted policy; this is a text-boundary test, without real tools or credentials. The optional host-side exact-value blocklist is **off**. One trial per cell measures observed differences, not a guarantee about a model or a family of prompts.

## Run against an API account

Use a **new output directory**. Set `OPENAI_API_KEY` in your environment using your own secret store. Keep it outside the checkout. Inventory discovery verifies IDs against the account's `/v1/models` before any generation. The dated mini snapshot is used instead of its moving alias; only unversioned Sol/Astra IDs were returned. There is no silent fallback to an unverified model.

```sh
run_dir=$(mktemp -d)
mkdir -p "$run_dir/old"
git archive cd5ee311c7637a6100a4c5392ea802419f16c3ed promptboundary | tar -x -C "$run_dir/old"
python -m evaluation.hosted.inventory --out "$run_dir/models.json"
python -m evaluation.hosted.experiment --inventory "$run_dir/models.json" --out "$run_dir/smoke" --smoke --execute
python -m evaluation.hosted.experiment --inventory "$run_dir/models.json" --out "$run_dir/main" --legacy "$run_dir/old" --arms raw release --workers 10 --execute
python -m evaluation.hosted.experiment --inventory "$run_dir/models.json" --out "$run_dir/main" --arms patched --workers 10 --execute
python -m evaluation.hosted.report "$run_dir/main"
```

Generation begins only with `--execute`. Calls are billable; retries and history replay count. Re-running skips completed cells; the runner refuses to overwrite an interrupted journal whose last call may already have been billed. A newly available model needs a verified ID and price entry before inclusion. Model aliases and sampling can change; reproducing the procedure need not reproduce identical answers. Keep the runner, fixtures and scorer at the commit used for the published result when re-scoring this batch.

## Read the evidence

- [API inventory](results/models.json) records public GPT IDs, the discovery time and a hash of the full ID list; private fine-tune names are not published. Each of the three [smoke probes](results/smoke) checks generation, in addition to verifying the list.
- Under [results/main](results/main), each model has three arm directories. `<case>.json` holds the delivered answer, runtime status, input hash, elapsed time and count of stage calls. `<case>.jsonl` contains the corresponding request bodies and provider response bodies, including model ID, stage output, timing and token usage. The shareable journals replace opaque provider reasoning/continuation blobs with their SHA-256 and byte counts. Delivered text, review JSON, response IDs, usage and timings remain intact. HTTP authorization headers are never journaled. These public synthetic inputs and full replies are deliberate; do not enable such logging on private conversations.
- The manifests record the immutable input and code hashes, reasoning effort (`low`), tier (standard), shuffle seed (41) and maximum 1,024 output tokens per call, including reasoning. No temperature override or tools were used. Concurrency was 10 per batch; raw and v0.1 were shuffled together, and the patched batch ran later. Elapsed time includes network and all model stages; it is not a controlled speed benchmark.
- Cost uses provider-reported usage, cached read/write breakdowns and the standard rate for each model: [Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), [mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini). Published USD values are usage-based estimates before credits or taxes, not an account invoice. Offline replay incurs no charges.

For an application, `OpenAIResponses` implements the same interface as the existing Chat Completions transport. For example, with a model ID confirmed on your account:

```sh
promptboundary chat --api responses --base-url https://api.openai.com/v1 --model gpt-6.1-sol --api-key-env OPENAI_API_KEY --max-tokens 1024 'Suggest a lunch without peanuts.'
```

## Fixed-draft stress test

The main suite produced no successful attack even without a controller. A separate [8-case reviewer stress test](stress/PROTOCOL.md) forces the same draft on each generation and revision, and compares release and patch with live hosted interpretation and audit. The [results](stress/results/RESULTS.md) measure escape **given an already compromised generator**, separately from clean draft usability. Do not pool these counts with the primary ASR.

```sh
python -m evaluation.hosted.stress.run --inventory "$run_dir/models.json" --legacy "$run_dir/old" --out "$run_dir/stress" --workers 8 --execute
python -m evaluation.hosted.stress.report "$run_dir/stress" --inventory "$run_dir/models.json"
```

Before sharing a synthetic run, keep the original journals privately, copy the output directory, and run `python -m evaluation.hosted.public_logs PATH_TO_PUBLIC_COPY`. The scorer uses only observable replies and usage, and works on either copy. See also the [blinded reading of every primary answer](results/QUALITATIVE.md) and the [trace of the normal-request failure](../../docs/authority-failure.md).

## What the two runs establish

On naturally generated replies, every model already resisted all 20 attacks without middleware. Under a repeatedly compromised generator and live reviewers, the old runtime returned the protected marker in 1/4 cases on Sol, 1/4 on Astra and 2/4 on mini; the patch returned none, and all clean controls passed. The patch withheld the authorized fact as well in every compromised case. It prevents a demonstrated failure path but does not establish an incremental natural ASR reduction. Sol and Astra each withheld one legitimate task that the raw model answered. Main, smoke and stress runs together made **914 real API calls**, with **498,834 input and 80,980 output tokens**, priced at **USD 3.48438980** using the recorded standard rates.

See the [Chinese delivery report](DELIVERY.zh-CN.md) for the model-by-model comparison.
