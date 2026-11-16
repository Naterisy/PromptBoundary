# Development evidence before v4 validation

These traces use the already-public v3 scenarios, so they are development evidence only. They are excluded from every v4 comparison.

The initial 3B replay stopped after twelve completed cells when interpretation errors and verbose passing audits were observed. Its recorded source hashes describe that preliminary candidate; the complete preliminary source is not archived. The raw trace `v01-initial.json` retains stage requests and responses. Later source snapshots for compact auditing and the final candidate are included. A short 3B diagnostic (`v01-compact-audit.json`) encountered an unavailable local server during model switching; it is an infrastructure failure, not a quality measurement.

Five `*-7b-final-candidate.json` traces document the final preflight at candidate commit `e5d80ae`: four passed the older fixed task grader, while the ambiguity case acted on a guessed reference and failed. These do not replace independent, blinded v4 evaluation. Additional `v01-7b-compact-audit.json` shows the prior intermediate diagnostic.

All conversations are synthetic. Source snapshots and raw stage outputs expose implementation decisions and failure mechanisms, without model weights, credentials or private user chats.
