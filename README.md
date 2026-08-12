# ccvi-skills

The skill suite for the **CCVI family** of products (Claude Code via IDE): three
tightly-coupled Claude Code skills - `modes`, `plans`, and `seedprompt` - shipped as
**one plugin with one version**.

> If you are not using the CCVI family of products, these are probably not the skills
> you want. The suite assumes the CCVI host machinery is present (the modes loader and
> enforcement hook, the `<ccvi-modes>` sentinel, the Plan Editor, the seedprompt
> rollover relay), and each skill assumes its siblings are installed.

Current version: ccvi-skills · v0.0.3

## The skills

| Skill | Invocation | What it does |
|---|---|---|
| modes | `/modes [verb] [param]` | Persistent response modes - binding, per-session contracts such as `plan` (markdown-only authoring stance), `agent` (full agency), `agent-loop` (autonomous keep-moving loop), `sbs`, `one-word`, and the `include`/`exclude` write filters. Backed by a fast-path script and a PreToolUse enforcement hook. |
| plans | `/plans [verb] [args]` | Lifecycle verbs for Cursor-compatible `*.plan.md` files: `write`, `review`, `verify`, `update`, `build`, `archive` - author, vet, correct, execute, and sweep plans, with a bundled frontmatter validator. |
| seedprompt | `/seedprompt [verb]` | One-use AI-to-AI session hand-offs: `write`, `show`, `clear`. Authors the seed at the one well-known path where the CCVI sidecar picks it up and injects it into the next session. |

Invocation signatures are unchanged from the skills' standalone ancestors; only the
plugin prefix is new (`ccvi-skills:modes`, `ccvi-skills:plans`,
`ccvi-skills:seedprompt`).

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
registers the modes enforcement hook), the three skills, and the hook script.
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
branches removed, sibling-skill and host hedges made plain statements.

## License

MIT - see [LICENSE](LICENSE).
