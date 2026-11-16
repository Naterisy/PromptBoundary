# Historical Responses transport

`responses.py` is copied byte-for-byte from commit
`aa0862b78e4fc8b9385d6cd2dcc13c446248c64a`, matching the hash already recorded in
the original hosted and hosted/stress experiment manifests:

`41628af4165ac7ef5bf14ec137ebcedf59d8f4e37217fe0745c990026877d19a`

This parser historically concatenated assistant commentary and final messages.
The current production parser fixes that behavior. Archived report verification
must use the parser that produced the archived outputs, including its known
limitations; it must not silently reinterpret old results with the corrected
parser. No archived output, scoring rule, manifest or result was changed.

`evaluation.hosted.archive` checks the requested path/hash against this single
explicit allowlist and verifies the snapshot bytes before importing its decoder
as `promptboundary._responses_v02`. All other manifest sources still must match
the current checkout. This snapshot is for offline historical verification, not
for new API experiments or production calls.
