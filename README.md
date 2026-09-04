# ccvi-skills

The skill suite for the **CCVI family** of products (Claude Code via IDE): five
tightly-coupled Claude Code skills - `modes`, `plans`, `seedprompt`, `cleancode`,
and `repos` - shipped as **one plugin with one version**.

> If you are not using the CCVI family of products, these are probably not the skills
> you want. The suite assumes the CCVI host machinery is present (the modes loader and
> enforcement hook, the `<ccvi-modes>` sentinel, the Plan Editor, the seedprompt
> rollover relay), and each skill assumes its siblings are installed.

The host also supplies two optional sentinels for the agent-loop autonomy log. A
`<ccvi-autonomy-log epoch="N">path</ccvi-autonomy-log>` block is rung 1 of the resolution
ladder; without it the ladder falls through to a `CLAUDE.md` `Autonomy logs:` line, then
to wherever existing `autonomy_log_*` files already live, then to
`<docDir>/logs/autonomy/`. A `<ccvi-doc-dir epoch="N">notes</ccvi-doc-dir>` block names
the project's plan directory, which is what `<docDir>` resolves to - it is an input to
that term, never a rung of its own. In both cases the **tag is the contract**; the
settings keys behind them are host-local.

Current version: ccvi-skills · v0.0.16

## The skills

| Skill | Invocation | What it does |
|---|---|---|
| modes | `/modes [verb] [param]` | Persistent response modes - binding per-session contracts, enforced by a fast-path script and a PreToolUse hook.<br>verbs<ul><li><code>plan</code> - markdown-only authoring stance; mutex with agent/agent-loop<ul><li><code>dir</code> - default dir for new <code>*.plan.md</code> (default <code>./</code>)</li></ul></li><li><code>agent</code> - full agency; the default stance</li><li><code>agent-loop</code> - autonomous keep-moving loop; clears all modes on entry<ul><li><code>pct</code> - context-usage % for session hand-off (20-99)</li></ul></li><li><code>one-word</code> - single-word responses</li><li><code>sbs</code> - step-by-step; one step then wait</li><li><code>exclude</code> - block writes matching globs<ul><li><code>patterns</code> - comma-separated globs</li></ul></li><li><code>include</code> - only allow writes matching globs<ul><li><code>patterns</code> - comma-separated globs</li></ul></li><li><code>exit</code> - exit one mode<ul><li><code>mode</code> - the mode to exit</li></ul></li><li><code>list</code> - echo the active modes</li><li><code>clear</code> - exit every mode</li></ul> |
| plans | `/plans [verb] [args]` | Lifecycle verbs for Cursor-compatible `*.plan.md` files, with a bundled frontmatter validator.<br>verbs<ul><li><code>write</code> - author the discussed plan<ul><li><code>name</code> - plan file stem</li></ul></li><li><code>review</code> - vet the plan's quality → report card<ul><li><code>plan</code> - the plan file</li><li><code>out</code> - report dir (default: beside the plan)</li><li><code>model</code> - delegate to a model, or inline</li></ul></li><li><code>verify</code> - audit todo status vs reality → report card<ul><li><code>plan</code> - the plan file</li><li><code>out</code> - report dir (default: beside the plan)</li><li><code>model</code> - delegate to a model, or inline</li></ul></li><li><code>update</code> - apply a report back into the plan<ul><li><code>plan</code> - the plan file</li><li><code>report</code> - the review/verify report</li></ul></li><li><code>build</code> - execute in place, flipping todos live<ul><li><code>plan</code> - the plan file</li><li><code>model</code> - delegate to a model, or inline</li></ul></li><li><code>archive</code> - sweep finished plans + their reports<ul><li><code>dir</code> - scan dir (top level)</li><li><code>archiveDir</code> - default <code>&lt;dir&gt;/archive</code></li><li><code>lenient</code> - count cancelled as terminal</li></ul></li></ul> |
| seedprompt | `/seedprompt [verb]` | One-use AI-to-AI session hand-offs at the well-known path the CCVI sidecar consumes and injects into the next session.<br>verbs<ul><li><code>write</code> - author the pending seed (overwrites)<ul><li><code>body</code> - seed body; composed from context if omitted</li></ul></li><li><code>read</code> - consume the pending seed: print + adopt it, then delete (one-use)</li><li><code>show</code> - print the pending seed's path + contents</li><li><code>clear</code> - delete the pending seed</li></ul> |
| cleancode | `/cleancode [noun] [verb] [args]` | Post-stabilization code consolidation - run once a version is done, tested, and green; every destructive stage verdict-gated, one git commit per stage.<br>verbs<ul><li><code>comments escrow</code> - copy every comment verbatim into the escrow + census report<ul><li><code>path</code> - target scope</li><li><code>escrowDir</code> - default <code>./comment_escrow/</code></li></ul></li><li><code>comments strip</code> - delete non-protected comments; refuses without a fresh escrow<ul><li><code>path</code> - target scope</li><li><code>escrowDir</code> - default <code>./comment_escrow/</code></li></ul></li><li><code>comments annotate</code> - write the ideal comment set for the finished code<ul><li><code>path</code> - target scope</li><li><code>escrowDir</code> - default <code>./comment_escrow/</code></li></ul></li><li><code>naming refactor</code> - single-symbol rename atom, full reference sweep<ul><li><code>symbol</code> - current name</li><li><code>newName</code> - replacement</li><li><code>path</code> - sweep scope</li><li><code>tier</code> - <code>local</code> \| <code>internal</code> \| <code>public</code> (default <code>internal</code>)</li></ul></li><li><code>naming propose</code> - dry run → <code>*.naming.proposal.md</code>, touches nothing<ul><li><code>path</code> - target scope</li><li><code>tier</code> - blast radius</li></ul></li><li><code>naming apply</code> - execute renames through naming refactor<ul><li><code>path</code> - target scope</li><li><code>tier</code> - blast radius</li><li><code>proposals</code> - edited proposal file</li></ul></li><li><code>conventions export</code> - render effective conventions as one editable file<ul><li><code>topic</code> - <code>naming</code> \| <code>comments</code> \| <code>all</code> (default <code>all</code>)</li><li><code>pathAndFileName</code> - output override</li></ul></li><li><code>conventions import</code> - codify in-scope divergences into the managed CLAUDE.md section<ul><li><code>pathAndFileName</code> - the edited conventions file</li></ul></li><li><code>conventions generate</code> - census actual practice into an import-ready conventions file<ul><li><code>strategy</code> - <code>majority</code> \| <code>recent</code></li><li><code>pathAndFileName</code> - output override</li></ul></li><li><code>run</code> - escrow → strip → rename → annotate, one commit per stage<ul><li><code>path</code> - target scope</li><li><code>verdict</code> - explicit verdict command</li><li><code>escrowDir</code> - default <code>./comment_escrow/</code></li><li><code>tier</code> - rename blast radius</li></ul></li></ul> |
| repos | `/repos [verb] [args]` | Local-forge PR pipeline - iterate a PR to polish privately on a local Forgejo, then export the refined result (branch, description verbatim, and only the root comments of UNRESOLVED threads) to the origin as a PENDING GitHub review a human submits.<br>verbs<ul><li><code>init</code> - one-time forge install + configure (idempotent re-run = verify & repair)</li><li><code>config</code> - per-repo config entry<ul><li><code>kind</code> - <code>template</code> \| <code>directions</code> \| <code>base</code></li><li><code>origin</code> - origin URL (default: the current repo's)</li><li><code>value</code> - set when present, show when absent</li></ul></li><li><code>sync</code> - push the base and current branch to the forge; no drafting, no PR<ul><li><code>force</code> - allow a non-fast-forward branch push via <code>--force-with-lease</code></li></ul></li><li><code>open</code> - push branch to the forge, open/refresh the local PR<ul><li><code>branch</code> - default: current branch</li><li><code>base</code> - default: entry's base, else origin default</li></ul></li><li><code>review</code> - Claude review → durable inline forge comments<ul><li><code>pr</code> - default: current branch's open forge PR</li></ul></li><li><code>status</code> - thread counts, export preview, base drift, preflight warnings<ul><li><code>pr</code> - default: current branch's open forge PR</li></ul></li><li><code>export</code> - stage the pending review on origin<ul><li><code>pr</code> - required (the outward-facing guard)</li><li><code>dryRun</code> - print the full payload, touch nothing</li></ul></li></ul> |

Invocation signatures are unchanged from the skills' standalone ancestors; only the
plugin prefix is new (`ccvi-skills:modes`, `ccvi-skills:plans`,
`ccvi-skills:seedprompt`, `ccvi-skills:cleancode`, `ccvi-skills:repos`).

## The /plans lifecycle

Phase 0 is **collaborate** - the unofficial one: no verb, no dialog. You and the agent
talk the work through (typically in `/modes plan`, which fences writes to markdown)
until the shape is agreed. Every phase after it is an explicit verb, and the verbs are
**independent atoms**: nothing auto-runs the next one, so you compose the loop and can
re-enter any phase at any time.

Note where the two graders sit: **`review` is the pre-build gate** (is this plan
buildable as written?) while **`verify` is the post-build audit** (did it actually
land?). `verify` only has something to say once `build` has flipped statuses - before
that every todo is `pending` and there is nothing to audit. Steps 6 and 7 are the
remediation loop: when a verify finds gaps, `update` records the truth and `build`
finishes the work, then verify again. `archive` waits until every todo is terminal.

```diagram
  0. COLLABORATE - the unofficial phase: no verb, no dialog
     talk the work through (typically inside /modes plan, which
     fences writes to markdown): research, resolve every decision,
     agree the shape. Nothing is authored yet.
        │
        ▼
  1. /plans write [name]
     author the agreed plan  ->  *.plan.md
        │
        ▼
  2. /plans review {plan} [out] [model]
     the plan's QUALITY as written: rails, stale refs, risk,
     hygiene, lint  ->  <plan>.review.md
        │
        ▼
  3. /plans update {plan} {report}
     broad latitude - restructure the plan freely
        │
        ▼
  4. /plans build [plan] [model]  ◀────────────────┐
     execute IN PLACE, flipping todos live:        │
     pending -> in_progress -> completed           │
     reality != plan?  STOP and surface            │
        │                                          │
        ▼                                          │
  5. /plans verify {plan} [out] [model]            │
     status vs. REALITY: is each "completed"       │
     todo ACTUALLY done? -> <plan>.verify.md       │
        │                                          │
        ├───────────────┐                          │
        │               ▼                          │
        │             6. [/plans update] if needed │
        │                narrow - status flips only│
        │               │                          │
        │               ▼                          │
        │             7. [/plans build]  if needed │
        │                finish the gaps ──────────┘
        │
        │  every todo terminal and true
        ▼
  8. /plans archive [dir] [archiveDir] [lenient]
     sweep the finished plan + its sibling reports into archiveDir
     (copy-verify-delete, never a bare move)
```

Reading the loop in one line: **collaborate → write → review → update → build →
verify → [update → build if needed] → archive when terminal**. `review` and `verify`
are the only producers of a report card and `update` is its only consumer, so each
grading pass costs one `update` to apply.

## Install

End users do not install this by hand - **CCVI installs the plugin automatically**.
The standard flow below is the development workflow:

```sh
claude plugin marketplace add /path/to/ccvi-skills   # this repo is its own marketplace
claude plugin install ccvi-skills
```

The plugin payload is everything under [plugin/](plugin/): the manifest (which also
registers the modes enforcement hook), the four skills, and the hook script.
`ccvi-skills.zip` at the repo root is the same tree, packaged reproducibly by
[build.py](build.py). [manifest.json](manifest.json) - emitted beside the zip and
into its root - is the machine-readable signatures contract for hosts: the suite
version plus each skill's verbs with ordered, typed param lists.

## Development

- One version governs the whole suite. It lives only in
  `plugin/.claude-plugin/plugin.json`; `python3 build.py` stamps it into every help
  display and this README, and packages `ccvi-skills.zip`. `python3 build.py --check`
  verifies nothing has drifted.
- `python3 test/test_modes.py` is the golden harness for the modes contract - it
  byte-locks the two LAW blocks and the echo contract between `SKILL.md` and
  `modes.py`.
- See [CLAUDE.md](CLAUDE.md) for the repo doctrine, versioning scheme, and release
  procedure.

## Provenance

Ported from the multi-surface
[skills-anthropic](../skills-anthropic) repo (modes 4.6.0, plans 3.2.0,
seedprompt 1.1.0) and tightened for the single-surface reality: non-Claude-Code
branches removed, sibling-skill and host hedges made plain statements. `cleancode`
is native to this repo, not a port.

## License

MIT - see [LICENSE](LICENSE).
