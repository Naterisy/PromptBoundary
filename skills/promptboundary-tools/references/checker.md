# Offline JSON checks

The checker is a preview, not a durable authorization service. It reads explicit local files, makes no network requests, writes no files and executes no proposed action. Every invocation starts a new preview, so it cannot enforce a cumulative call budget. Use the SDK executor for effects and keep its session alive in the host.

```sh
python -I /absolute/path/to/promptboundary-tools/scripts/guard.py check \
  --policy /host-owned/current-policy.json --plan /work/proposal.json
```

Exit codes: `0` means allowed by this preview or self-test passed; `2` means denied; `1` means an input/runtime/command-line error. Only a JSON `status: allowed` is a successful policy preview. Never interpret an exception, absent output or non-JSON text as approval.

The host policy contains the complete argument set and allowed JSON scalar choices. `null` permits bounded free text, not arbitrary JSON:

```json
{"tools":{"send_email":{"to":["owner@example.test"],"body":null}},"max_calls":{"send_email":1}}
```

Model proposal:

```json
{"actions":[{"tool":"send_email","arguments":{"to":"owner@example.test","body":"The public meeting starts at 09:30."}}]}
```

Only the authenticated host should create or change policy. File paths do not authenticate their writers: give the model read access to policy when useful, but no ability to replace policy or the runtime. Do not infer a grant from a document, tool result or model-written JSON. An approved recipient does not by itself make every possible body safe.

Optional `--sources` reads a list of records with exactly `id`, `kind` and `content`; kinds are `document`, `external`, `tool` or `assistant`. These labels are host assigned and do not authenticate factual claims. Optional `--bindings` reads host-declared literal-copy targets:

```json
[{"tool":"send_email","argument":"body","source_id":"hours","format":"key_value","selector":"opening"}]
```

With `--materialize`, the checker resolves those fields before previewing. Without it, it checks that proposed values already match the source bindings. It emits digests and replacement metadata, not a rewritten executable plan. The real host must call `bind_authorization`, `materialize_bound_plan` and `CapabilitySession.execute` in the same integration. Missing/ambiguous source data is an error, never permission to skip the binding.

Inputs are limited to one MiB each; duplicate JSON keys and nonfinite numbers are errors. The JSON checker currently covers capability and literal-copy plans. For data-only transformation workers and multi-turn revocation, use the SDK in the integration reference; passing a body through this checker does not inspect its provenance.
