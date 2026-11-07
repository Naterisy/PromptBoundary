# Application rules and confidentiality

The host owns the conversation envelope. Set application instructions in a system/developer message, or provide the server's own system prefix. Authenticate or reconstruct that envelope in the calling application before sending it to the loopback middleware. A user who can submit arbitrary actual system messages can manufacture policy. This API supplies neither tenant isolation nor caller authorization.

For ordinary natural-language application policy, interpretation and audit receive the real system/developer instructions as authority-bearing context. The schema exposes application rule IDs for review. A citation to an application rule must contain a span of the actual candidate and the applicable policy text. An unresolved review with application policy falls back after the bounded retry window. This closes a confirmed fail-open in v0.1.0: a reviewer could correctly report a visible password leak, the controller had no matching application-rule ID, and the unreviewed draft reached the caller. The defense still depends on the model recognizing semantic violations. An incorrect audit pass can release one.

User-declared restrictions remain scoped, revisable records. The interpreter now has to propose an anchored edit for a prohibition; a bare model classification of “remove” or “once” can only release less restrictive records. Quotation, role labels, and example instructions inside user text are supplied as user data. A motivated user may still persuade a model to propose a bad edit with a superficially valid quote. Applications with multi-user records should enforce ownership and authorization outside this controller.

For values known to the application ahead of time, the SDK and HTTP adapter also accept host-declared opaque literals:

```python
answer, status, usage_source = handle_chat(
    upstream, body, protected_values=(deployment_token,),
)
```

An embedded service can set the same keyword on `make_server` or its `StageModel`. Callers cannot alter the list using an HTTP body field. With an explicit list, stage requests mask occurrences of these values before contacting the provider. A draft containing a registered value fails validation before audit or delivery. Matching uses Unicode NFKC and case-insensitive literal comparison. Use application-owned opaque values rather than ordinary short words, which can also occur in permitted answers. This option does not discover secrets and cannot detect arbitrary transformations, encodings, partial disclosure or semantic allusions. Local application input, session state, and any logging owned by the caller can still contain the original values. Keep secrets out of model inputs when possible. The primary model comparison uses natural-language policy alone, without registering expected benchmark answers.

The HTTP `max_tokens` field limits the user-visible draft. A smaller limit can truncate an interpreter decision or audit verdict even when the intended answer is a single word, so the HTTP adapter allocates at least 512 completion tokens for each structured stage whenever a client requests a smaller cap. Hosting applications should budget for multiple stages and retries. The direct SDK keeps its explicit per-stage cap unless `structured_max_tokens` is set on `StageModel`.

Run `python -m unittest discover -s tests -p test_security.py -v` to exercise the deterministic enforcement cases, including a failing auditor, a guessed registered value, a harmless short-answer request, and an explicit versus inferred authorization to change a user boundary. These scripted cases establish control-flow properties independently of live attack rates.

The offline release comparison uses the same injected generator and reviewer behavior against v0.1.0 and the current runtime. Its developer-password case returns the literal under v0.1.0 and a bounded fallback in the patched version. Its one-digit arithmetic case delivers “4” in both versions: v0.1.0 returned it after unresolved structured reviews, while the patched runtime completed the required checks. This pair measures enforcement and review availability under the injected failures. It gives no model attack success rate or population false-refusal estimate. In a full Git clone, run `python evaluation/hosted/check_runtime.py` and compare stdout with [the saved results](../evaluation/hosted/runtime_faults.json).
