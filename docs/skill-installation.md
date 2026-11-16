# Install PromptBoundary tools

The `promptboundary-tools` Skill combines short source/authorization guidance,
offline checks and a portable copy of the actual runtime. It makes no API calls
while installing or testing. Python 3.10 or newer is required for the scripts;
there are no runtime package dependencies.

## Install from a reviewed checkout

The work remains on the existing PR branch until it is merged. Review or pin the
Git commit you want before installing:

```sh
git clone --branch hosted-runtime-evaluation https://github.com/Naterisy/PromptBoundary.git
cd PromptBoundary
python3 scripts/package_skill.py --destination "${CODEX_HOME:-$HOME/.codex}/skills"
python3 -I "${CODEX_HOME:-$HOME/.codex}/skills/promptboundary-tools/scripts/guard.py" self-test
```

The destination is the parent of `promptboundary-tools`, not the skill folder
itself. Pass a different parent for hosts configured to discover `~/.agents/skills`,
`.claude/skills` or project-local skills. The installer refuses to overwrite an
existing folder. To upgrade, review and move/remove the existing package before
installing its replacement.

Start a new chat and invoke:

> Use $promptboundary-tools while summarizing these retrieved documents and
> preparing an email to the recipient I authorized. Preserve the source boundaries
> and use the host's capability executor for any actual send.

Whether the Skill loads automatically depends on the host. Installation does not
add a runtime hook to an existing application, alter tool permissions or prevent
the agent from bypassing unmediated tools. When the host does not provide an
executor, the guidance and local preview remain advisory.

## Portable ZIP

The repository's `releases/promptboundary-tools.zip` contains the generated
package; the adjacent `.sha256` file records its checksum. Verify the checkout or
download source independently: a checksum distributed beside a malicious file is
not proof of authenticity. To create the same type of archive locally:

```sh
python3 scripts/package_skill.py --archive /tmp/promptboundary-tools.zip
cd /tmp
shasum -a 256 -c promptboundary-tools.zip.sha256
unzip promptboundary-tools.zip -d "${CODEX_HOME:-$HOME/.codex}/skills"
```

Extract only an archive from the reviewed source. The generated archive has one
`promptboundary-tools/` root. It contains `SKILL.md`, references, `scripts/guard.py`,
`LICENSE`, `runtime.zip` and `manifest.json`. The runtime archive is built from the
same package source; it is not an independently maintained fork. The manifest
records the source commit, whether the relevant source tree was dirty, an aggregate
content hash and hashes for individual files. The wrapper checks these hashes
before importing the bundled runtime. Archive generation is deterministic for the
same source contents and Git provenance metadata.

## Python package and copied Skills

`pip install .` installs the SDK and an unbundled Skill beneath Python's
`share/promptboundary/skills` directory. Copy that entire `promptboundary-tools`
folder to your host's Skill location. Its helper requires the matching installed
PromptBoundary 0.4.0 package and reports that it is using it; run the helper with
that environment's Python. A plain copy without either the runtime bundle or the
installed package offers advisory instructions only; the helper returns an error.
The builder/portable ZIP avoids this environment dependency.

## What is actually enforced

`guard.py self-test` exercises real offline invariants: unauthorized redirect,
replayed grant, source-copy resolution, unselected private-source isolation,
fixed destination, restricted egress and revoked handle. All callbacks stay in
memory. Passing these checks is wiring evidence, not an LLM safety score.

`guard.py check --policy policy.json --plan proposal.json` emits a JSON preview
and never executes the proposal. Exit `0` is allowed, `2` denied, and `1` an error.
The host must supply and protect policy; a model-generated policy file does not
authenticate its own authorization. Each preview is stateless, so the application
must use the actual SDK session for consumption, revocation and effects.

See the bundled [checker contract](../skills/promptboundary-tools/references/checker.md)
and [integration examples](../skills/promptboundary-tools/references/integration.md).
The runtime can isolate data from authority; it cannot certify external facts,
authenticate source labels, make generated prose true or secure a host that gives
the model an alternative unrestricted tool path.
