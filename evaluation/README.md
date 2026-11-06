# Reproduce the evaluation

Run these commands from the repository root, using Python 3.10+ and one local OpenAI-compatible Chat Completions server. The controller requires JSON object responses. The default endpoint is http://127.0.0.1:18764/v1 and the default model alias is pb-qwen. The runner accepts only loopback URLs.

```sh
python3 -m evaluation.run --suite primary --out evaluation/results/reproduction \
    --base-url http://127.0.0.1:18764/v1 --model pb-qwen \
    --backend-id "exact model weights, quantization and inference build"
```

The model run writes `model/primary/run.json`, `rows/*.json` and `summary.json` below the output root. To resume an interrupted run, repeat exactly the same command. For a revised implementation, preserve the first run and use `--suite confirmation` and a fresh `--out`. Separate output roots also keep different model builds or controller versions apart. Use one writer at a time per output root.

```sh
python3 -m evaluation.run --mock --out /tmp/promptboundary-wiring
python3 -m unittest discover -s tests -p 'test_evaluation.py'
```

Mock rows are isolated under `mock_wiring_only`. Their fixture answers and estimated counts exercise the harness. Use the `model` namespace to analyze live inference.

The protocol, its pre-inference amendment, both suites and independent scorer have checksums in [freeze.json](freeze.json). Each output row includes the delivered text, check failures, controller events, call-level tokens, and setup/reply timing. The `mean_paired_delta_vs_A` fields report absolute overhead. A null token result means at least one call lacked valid usage.

### Reference backend

The release experiment ran on an Apple M3 Pro with 18 GB of unified memory. We used llama.cpp build `b12179` (commit `669204ee2`, macOS arm64) with the Q4_K_M quantization of Qwen2.5-3B-Instruct. Obtain the model separately from [the pinned weights revision](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/tree/7dabda4d13d513e3e842b20f0d435c732f172cbe) and the inference executable from [the llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b12179).

```sh
shasum -a 256 qwen2.5-3b-instruct-q4_k_m.gguf
# 626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d
llama-server -m qwen2.5-3b-instruct-q4_k_m.gguf --host 127.0.0.1 \
  --port 18764 --alias pb-qwen -c 8192 -np 1 --seed 941 --no-webui --no-slots --cache-ram 0
```

Latency includes local HTTP and inference after model warm-up. The server may reuse a prompt prefix within its slot. Hardware, caching, and system load affect wall time. Each published count comes from one greedy completion per case and arm, with the controller's bounded internal retries. Freeze hashes prevent accidental changes to the two suites and grader; the public test material is unsuitable for a future blind test once used for tuning.

Revision 2 requires a nonempty backend identity string for measured runs, and rejects the shipped mock's model ID or usage marker if returned by the endpoint. This catches an accidental fixture configuration. The backend identity is operator-supplied; use the actual file checksum and build. Each new row is bound to the run fingerprint. On resume the runner checks expected case/arm filenames and identities, and grades the delivered text again with the frozen scorer. Original v1 rows retain their historical schema and can be reproduced with their recorded source revision.

For the final two-model test, select `--suite validation3`. Use distinct output roots for the 3B and 7B models and provide each model's recorded identity. The 12-case suite, four arms, separate comparisons, and decision criteria are fixed in [the third protocol](PROTOCOL-v3.md). A complete measured summary contains `validation3_gates` with count differences and the decision for each comparison.

The additional 7B run used the same llama.cpp build, context size, seed and one-slot configuration. Use the first Q4_K_M GGUF shard as the model path, put the second beside it, and replace the server port and alias with `18765` and `pb-qwen-7b`. Check the SHA-256 digest of each shard before serving it. [Pinned 7B model files](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/tree/bb5d59e06d9551d752d08b292a50eb208b07ab1f)

| Shard | SHA-256 |
|---|---|
| 00001-of-00002 | `dfce12e3862a5283ccfb88221b48480e58745165de856439950d0f22590580db` |
| 00002-of-00002 | `539cf93f78e887edea1c04e2d7d8cdaca9d01dae9c9025bcb8accbe29df3d72a` |

To recompute published scores, stored token sums, and paired costs without model access, run `python3 -m evaluation.verify evaluation/results/v1/model/primary` from the checkout and substitute any completed run directory. To reproduce the implementation that produced an old run, check out its commit listed in [the report](REPORT.md).
