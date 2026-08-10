---
humanEngineerDifficulty: 5
name: ccvi-skills suite - bundle modes, plans, seedprompt as one plugin
version: "1.0"
overview: "Populate this repo with the ccvi-skills Claude Code plugin: the modes, plans, and seedprompt skills ported from ../skills-anthropic as one tightly-coupled suite - surfaces other than Claude Code stripped, cross-skill requirements made explicit, one version (starting 0.0.0) stamped everywhere, one build script, one zip artifact, standard marketplace install."
todos:
  - id: scaffold
    content: "Create the repo skeleton: root .claude-plugin/marketplace.json pointing at ./plugin, plugin/.claude-plugin/plugin.json at 0.0.0 carrying the PreToolUse hook registration, plugin/skills/ dirs, .gitignore"
    status: pending
    phase: "Scaffold"
  - id: port-modes
    content: "Copy the modes skill (SKILL.md, scripts/modes.py) and hooks/enforce_modes.py from ../skills-anthropic into plugin/"
    status: pending
    phase: "Port"
  - id: port-plans
    content: "Copy the plans skill (SKILL.md, tools/ including the vendored js-yaml) into plugin/skills/plans/"
    status: pending
    phase: "Port"
  - id: port-seedprompt
    content: "Copy the seedprompt SKILL.md into plugin/skills/seedprompt/"
    status: pending
    phase: "Port"
  - id: adapt-tests
    content: "Carry test/test_modes.py over, re-point its path constants at plugin/, and run it green before any prose editing"
    status: pending
    phase: "Port"
  - id: strip-surface-branches
    content: "Sweep all three SKILL.md files removing non-Claude-Code surface branches per the strip/keep policy; LAW blocks stay byte-identical"
    status: pending
    phase: "Tighten"
  - id: harden-coupling
    content: "Make co-installation explicit: /plans build always bridges via /modes agent, seedprompt assumes the CCVI consumer, hedges about absent sibling skills removed"
    status: pending
    phase: "Tighten"
  - id: fence-sweep
    content: "Tag every untagged fence opener in modes and seedprompt SKILL.md per the plans fence rule, except the two byte-locked LAW fences"
    status: pending
    phase: "Tighten"
  - id: version-displays
    content: "Give all three skills' help outputs a suite-version display reading the current plugin.json version"
    status: pending
    phase: "Tighten"
  - id: suite-build-script
    content: "Write build.py (stamp version into help outputs and modes.py, update the README version, package ccvi-skills.zip reproducibly, --check mode), derived from ../skills-anthropic/modes/build.py"
    status: pending
    phase: "Release"
  - id: author-docs
    content: "Write README.md (CCVI-family positioning, standard install, skills table) and CLAUDE.md (layout, versioning scheme, release procedure, hard rules)"
    status: pending
    phase: "Release"
  - id: release-verify
    content: "Run build.py and the tests, install the plugin via the standard marketplace flow, and verify end-to-end: skills invoke, the hook blocks, versions display"
    status: pending
    phase: "Release"
isProject: false
---

# ccvi-skills suite - bundle modes, plans, seedprompt as one plugin

## Problem / Context

Three skills in [../skills-anthropic](../../skills-anthropic/) - `modes`, `plans`,
`seedprompt` - have become de-facto components of the CCVI family (Claude Code via
IDE): the modes enforcement hook, the `<ccvi-modes>` sentinel, the loader, the Plan
Editor conventions, and the seedprompt rollover relay are all CCVI machinery. Yet they
ship as three independent plugins written to be surface-agnostic across Chat, Cowork,
and Code - hedging that costs propagation work and prose bloat while serving no real
consumer.

The decision (settled in discussion, this plan encodes it): cut bait. The three skills
become **one plugin named `ccvi-skills`**, tightly coupled - each may assume the
others and the CCVI host are present. This repo is that plugin. `skills-anthropic`
stays frozen as the read-only source; its `theoryplans` and `g-ratings` remain there
permanently and are not part of this work.

Key facts about the source (verified 2026-08-09, versions at port time: modes 4.6.0,
plans 3.2.0, seedprompt 1.1.0):

- `modes` ships a PreToolUse hook (`hooks/enforce_modes.py`) registered in its
  plugin.json via `${CLAUDE_PLUGIN_ROOT}/hooks/enforce_modes.py`, a fast-path script
  (`skills/modes/scripts/modes.py`), and a dev-only golden harness
  (`modes/test/test_modes.py`, not shipped) that byte-locks the two LAW blocks and the
  echo contract between SKILL.md and modes.py.
- `plans` bundles `tools/plan-check.cjs` with a vendored js-yaml, and
  `tools/archive-plans.sh`. Its SKILL.md fences are already tagged per its own rule 5.
- `seedprompt` is a single SKILL.md, already Code-only.
- `modes/build.py` in the source repo is the release-pipeline template: version
  stamping into help outputs with no placeholder tokens, README row update,
  reproducible zips (fixed zip metadata), and a `--check` sync-verify mode.

## Approach

Port the three skills into one standard Claude Code plugin using the proven
repo-as-marketplace shape (root `marketplace.json` pointing at a plugin subdirectory,
exactly like the source repo does), then tighten the prose in place: every branch that
exists only to serve a non-Claude-Code Anthropic surface is removed, and every hedge
about a sibling skill possibly being absent becomes a plain statement, because the
suite guarantees co-presence. One version governs everything, displayed in each
skill's help output and stamped by a single build script that also packages the one
zip artifact.

Target layout:

```text
ccvi-skills/
  .claude-plugin/marketplace.json    - this repo is its own marketplace; source ./plugin
  plugin/
    .claude-plugin/plugin.json       - name ccvi-skills, version 0.0.0, hook registration
    hooks/enforce_modes.py
    skills/modes/SKILL.md
    skills/modes/scripts/modes.py
    skills/plans/SKILL.md
    skills/plans/tools/              - plan-check.cjs, archive-plans.sh, vendor/js-yaml.min.js
    skills/seedprompt/SKILL.md
  test/test_modes.py                 - dev harness, never packaged
  build.py                           - stamp + README + zip + --check
  doc/                               - this plan lives here
  README.md
  CLAUDE.md
  ccvi-skills.zip                    - built artifact: the plugin/ tree at zip root
```

Invocation signatures are untouched (`/modes [verb]`, `/plans [verb]`,
`/seedprompt [verb]`); only the compound prefix changes (`ccvi-skills:modes` etc.),
which is ccvi-idea's problem to sweep, not this repo's.

## Conventions & assumptions

- **Implementer calibration: this plan assumes a Fable 5 (or equivalent
  high-reasoning) implementer.** It states decided policy and invariants and delegates
  editorial judgment - especially in the Tighten phase, where sentence-level
  strip-or-keep calls are yours to make under the stated policy. The hard rails
  (byte-locked LAW blocks, out-of-scope fences, verification checks, stop-and-surface)
  are not judgment calls.
- **Source is read-only.** `../skills-anthropic` is the quarry; never write to it. If
  it is not reachable, ask the user to add it (`/add-dir ../skills-anthropic`).
- **Copy deliberately, file by file.** Port only what the layout above names. The
  source's chat/ and cowork/ variant dirs, all existing .zip/.plugin/.skill artifacts,
  `__pycache__`, and the per-skill plugin.json files are NOT carried.
- **Versioning scheme (decided):** the suite starts at `0.0.0` and increments
  patch-wise: `0.0.1` … `0.0.99`, then rolls to `0.1.0`. `1.0.0` is a deliberate
  future ship decision, not an increment. The version lives ONLY in
  `plugin/.claude-plugin/plugin.json`; build.py stamps it everywhere it is displayed.
  Bumping is manual (edit plugin.json, run build.py) - the script stamps, it never
  bumps.
- **LAW blocks are byte-locked.** The two `<!-- LAW:plan -->` / `<!-- LAW:agent-loop -->`
  blocks in modes SKILL.md must remain byte-identical to the copies modes.py emits;
  test_modes.py asserts this. No edit in any phase touches a LAW block, including the
  fence sweep (their bare fences are intentional - the CCVI Plan Editor wraps
  class-less blocks by design).
- **Fence tagging follows the plans skill's own rule 5** (in the ported
  `plugin/skills/plans/SKILL.md`, section "The plan-write discipline"): real language
  for code, `text` for reflowable non-source, `diagram` for alignment-critical blocks.
- **In-file style:** the ported SKILL.md files keep their existing house style
  (em dashes and all); match it when editing them. New files authored fresh (README,
  CLAUDE.md, build.py docstrings) use plain hyphens, 2-space indentation.
- **Hook registration carries verbatim:** the `hooks` object from the source
  `modes/code/.claude-plugin/plugin.json` (PreToolUse, matcher
  `Write|Edit|MultiEdit|NotebookEdit`, command
  `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/enforce_modes.py"`, timeout 5) moves into the
  suite plugin.json unchanged - `hooks/` sits at plugin root in both layouts, so the
  path resolves identically.
- **No commits, no pushes.** The user reviews and commits per their own cadence.
  Report what is ready to commit; never run git write operations.
- **Assumes `claude` CLI is available** for the install verification. If plugin
  marketplace commands are unavailable or denied, complete everything else and report
  the exact commands the user should run instead - do not skip silently.
- **Coordination notes (recorded here, actioned elsewhere):** ccvi-idea must sweep
  for hard references to old compound names (`modes:modes`, `plans:plans`,
  `seedprompt:seedprompt` become `ccvi-skills:*`) and owns auto-install/pinning at
  extension-install time; the user retires the three old plugins from their own
  installation when adopting the suite. Neither is a todo in this plan.

## The steps

### 1. Scaffold (`scaffold`)

Create the tree exactly as the Approach layout shows, minus the skill payloads:

- `.claude-plugin/marketplace.json` - mirror the shape of
  `../skills-anthropic/.claude-plugin/marketplace.json` (marketplace `name:
  ccvi-skills`, owner block copied from source, one plugin entry: name `ccvi-skills`,
  source `./plugin`, description naming the three skills and the CCVI family).
- `plugin/.claude-plugin/plugin.json` - name `ccvi-skills`, version `"0.0.0"`, author
  block copied from any source plugin.json, description in the same style as the
  source descriptions (one sentence naming all three `/verb` surfaces), and the hook
  registration per Conventions.
- Empty `plugin/hooks/`, `plugin/skills/{modes,plans,seedprompt}/`, `test/` dirs.
- `.gitignore`: `__pycache__/`, `.idea/`, `.vscode/`, `*.iml`, `.DS_Store`.

**Why:** the repo-as-marketplace + plugin-subdir shape is byte-for-byte the pattern
already proven by the source repo, so install behavior is not an experiment.

**Done-when:** `python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); json.load(open('plugin/.claude-plugin/plugin.json'))"`
passes, and the plugin.json contains the `hooks` registration and version `0.0.0`.

### 2-4. Port the three skills (`port-modes`, `port-plans`, `port-seedprompt`)

Straight copies from `../skills-anthropic`, byte-preserving (editing comes later, as
its own phase, so every Tighten diff is reviewable against a clean port):

- `modes/code/skills/modes/SKILL.md` → `plugin/skills/modes/SKILL.md`;
  `modes/code/skills/modes/scripts/modes.py` → `plugin/skills/modes/scripts/modes.py`;
  `modes/code/hooks/enforce_modes.py` → `plugin/hooks/enforce_modes.py`.
- `plans/code/skills/plans/SKILL.md` → `plugin/skills/plans/SKILL.md`; the whole
  `tools/` tree (plan-check.cjs, archive-plans.sh, vendor/js-yaml.min.js) alongside it.
- `seedprompt/code/skills/seedprompt/SKILL.md` → `plugin/skills/seedprompt/SKILL.md`.

**Done-when:** each ported file byte-matches its source (`cmp`), and nothing else came
along (no `__pycache__`, no zips - `find plugin -name '__pycache__' -o -name '*.zip'`
is empty).

### 5. Adapt the test harness (`adapt-tests`)

Copy `../skills-anthropic/modes/test/test_modes.py` → `test/test_modes.py`. Re-point
its path constants (`SCRIPT`, `SKILL_MD`, `HOOK` - currently built from a
`modes/code/...` layout) at `plugin/skills/modes/...` and `plugin/hooks/...`. Change
nothing else unless a path-shaped assumption forces it; if an assertion fails for a
non-path reason, that is a reality mismatch - stop and surface, do not adjust the
assertion.

**Why now:** the harness locks the LAW blocks and echo contract BEFORE the Tighten
phase edits any prose - it is the tripwire that proves the tightening never touched
what it must not.

**Done-when:** `python3 test/test_modes.py` exits 0 against the freshly ported,
unedited files.

### 6. Strip the non-Claude-Code surface branches (`strip-surface-branches`)

An editorial sweep over all three `plugin/skills/*/SKILL.md` files. The deciding test
for every hedge, branch, or aside:

- **REMOVE** if its only trigger is a non-Claude-Code Anthropic surface: mentions of
  Chat, Cowork, Claude Desktop as execution surfaces; "no session id resolvable
  (Chat, Desktop…)" lifecycle branches; "surfaces without hooks / without a shell /
  without such a host"; "in Cowork the allowed-tools declaration is effectively
  documentation"; the Cowork directory-request-tool instruction; "loading is the
  host's job" hedges about hosts with no loader. The suite runs on Claude Code inside
  the CCVI family: session id resolvable, loader present, hook installed - state
  things in that voice.
- **KEEP** if it guards a runtime failure that can occur on Claude Code: the modes
  fallback-logic section for a missing/failed python3, the printenv session-id
  fallback, plan-check's no-Node YAML round-trip fallback, the tools-denied sections
  (rewritten to drop their Cowork sentences), the hook's fail-open note, every
  stop-and-surface escape hatch.
- **KEEP** the engine-generic degradation language inside the agent-loop mode's LAW
  and its harness-menu prose - that text is deliberately host-abstract and is the
  substrate for future vendor conditionals (Codex). Deferred, not deleted.
- **NEVER** edit inside the LAW blocks. If a required removal appears to live inside
  one, it does not - re-read; if it genuinely does, stop and surface.

Sentence-level calls are yours under this policy. When a paragraph survives but its
framing assumes multi-surface shipping ("byte-identical variants", "propagate to
cowork/chat"), reframe it to the single-plugin reality rather than deleting the
useful content it carries.

**Done-when:** `grep -ri 'cowork' plugin/skills/` returns nothing;
`grep -rn 'Chat' plugin/skills/` returns no hit meaning the claude.ai Chat surface;
`python3 test/test_modes.py` still exits 0.

### 7. Harden the coupling (`harden-coupling`)

The inverse sweep - hedges about sibling skills possibly being absent become plain
statements, because this plugin guarantees co-presence:

- In `plugin/skills/plans/SKILL.md`, the `build` verb's mode-bridge prologue
  (anchor: "Mode-bridge prologue") currently reads "If a modes skill exposing the
  `agent` mode is available to you… If no such skill is available, build directly."
  Make the bridge unconditional: always invoke `/modes agent` before the execution
  loop; keep the idempotency and delegated-build notes.
- In `plugin/skills/modes/SKILL.md`, non-LAW prose that hedges about a plans or
  seedprompt skill being available ("where a plans skill is available", "/seedprompt
  write where…") states them plainly as present. (Matching text INSIDE the LAW blocks
  stays byte-identical - the LAW is written host-generically on purpose.)
- In `plugin/skills/seedprompt/SKILL.md`, the host consumer framing ("a host consumer
  (e.g. the CCVI sidecar), if present") becomes the CCVI consumer as the norm; keep
  the truthful-reporting behavior for when the relay does not pick the seed up
  (that is runtime resilience, not surface hedging).
- Sweep all three for remaining "if the host/skill supports X" phrasing and resolve
  each per this policy or the step-6 policy, whichever applies.

**Done-when:** the plans build section contains no conditional path around the mode
bridge; a read-through of each SKILL.md finds no remaining absent-sibling hedge; the
test harness still exits 0.

### 8. Fence sweep (`fence-sweep`)

Apply the plans fence rule to the two SKILL.md files that predate it:
`plugin/skills/modes/SKILL.md` and `plugin/skills/seedprompt/SKILL.md`. Tag every
untagged fence opener (real language / `text` / `diagram` per the rule), **except the
two LAW-block fences in modes SKILL.md, which stay bare** - they are byte-locked and
deliberately rely on the renderer's class-less handling. `plugin/skills/plans/SKILL.md`
is already tagged; verify rather than re-edit.

**Done-when:** in each swept file, `grep -n '^```'` shows every bare ` ``` ` line is
either a closer or one of the two LAW-block openers (modes only); test harness exits 0
(the LAW extraction in test_modes.py proves the LAW fences were not touched).

### 9. Version displays (`version-displays`)

One suite version, visible at each skill's front door:

- modes already displays `Modes · v4.6.0` in its help output (in both SKILL.md and
  modes.py). Re-stamp both to `0.0.0` now (build.py owns this from here on).
- Give the plans and seedprompt help outputs an equivalent display - the suite version
  on the help header line, same `· v0.0.0` idiom, placed so a later regex stamp
  (a real version string replaced in place, no placeholder tokens - the source
  build.py's technique) can find it unambiguously.
- test_modes.py asserts exact stdout: if its golden text embeds the old version
  string, update the golden data to match - that is a version-shaped change, not a
  contract change.

**Done-when:** all three help outputs display `0.0.0`; `grep -rn '4\.6\.0\|3\.2\.0\|1\.1\.0' plugin/` finds no stale per-skill version strings; the test
harness exits 0.

### 10. Suite build script (`suite-build-script`)

Write `build.py` at repo root, derived from `../skills-anthropic/modes/build.py`
(read it first - keep its philosophy: stamp real strings in place, reproducible zip
metadata, `--check` for CI):

1. Read the canonical version from `plugin/.claude-plugin/plugin.json`.
2. Stamp it into every version display: modes SKILL.md + modes.py help lines, plans
   SKILL.md help line, seedprompt SKILL.md help line.
3. Update the version shown in `README.md`.
4. Package `ccvi-skills.zip` at repo root: the `plugin/` tree at the zip root
   (`.claude-plugin/plugin.json`, `hooks/**`, `skills/**` - nothing else), with fixed
   zip metadata so an unchanged build is byte-identical.
5. `--check`: verify all stamps match plugin.json and the zip is current; exit 1 on
   any drift.

Drop everything propagation-related from the source script - there are no variants.

**Done-when:** `python3 build.py` runs clean; `python3 build.py --check` exits 0
immediately after; `unzip -l ccvi-skills.zip` shows exactly the plugin tree (no doc/,
test/, build.py, README); the zipped SKILL.md files byte-match `plugin/`'s
(`unzip -p … | cmp - …`).

### 11. Docs (`author-docs`)

- **README.md**: what ccvi-skills is (the CCVI family's skill suite - one plugin,
  three skills, one version); the positioning sentence agreed in discussion (if you
  are not using the CCVI family of products, these are probably not the skills you
  want); the skills table with their invocation signatures; standard install
  (`claude plugin marketplace add <this repo>` + `claude plugin install ccvi-skills`)
  framed as the development workflow, noting CCVI installs the plugin automatically
  for end users; the current version (stamped by build.py).
- **CLAUDE.md**: the repo layout; the tight-coupling doctrine (skills may assume each
  other and the CCVI host; no surface variants, ever); the versioning scheme and
  release procedure (bump plugin.json → `python3 build.py` → review → user commits);
  the hard rules (LAW blocks byte-locked by test/test_modes.py; fence-tagging rule
  applies to all repo markdown; plan workflow: author into doc/, archive when done);
  vendor conditionals as the named future direction (Codex via the Agent Skills open
  standard) so nobody re-invents the strategy.

Exact wording is yours; those content points are required.

**Done-when:** both files exist and cover every point above; README's displayed
version matches plugin.json after a `build.py` run.

### 12. Release-verify (`release-verify`)

The end-to-end proof, in order:

1. `python3 test/test_modes.py` → exit 0.
2. `python3 build.py && python3 build.py --check` → both exit 0.
3. Install the real thing the standard way:
   `claude plugin marketplace add /Users/keldon/Desktop/working/ccvi-skills` (or its
   equivalent for an already-added marketplace), then
   `claude plugin install ccvi-skills`. Confirm the cache landed keyed on `0.0.0`.
4. Behavioral spot-checks in a session (or as close as tooling allows - report
   honestly what was and was not verifiable): the three skills are invocable by their
   unchanged signatures; `/modes plan ./doc` followed by an attempted non-markdown
   write is denied by the hook; the plans and modes help outputs display `· v0.0.0`.

**Done-when:** all four pass, or every failure is reported with exact reproduction
steps rather than worked around.

## Out of scope

- **`../skills-anthropic`** - read-only quarry. No writes, no commits, ever. Its
  `theoryplans` and `g-ratings` skills stay there and are not ported.
- **Vendor conditionals** (Codex/Agent-Skills-standard branches in SKILL.md bodies) -
  named future direction, deliberately not in this plan.
- **ccvi-idea** - the compound-name sweep (`ccvi-skills:*`), auto-install machinery,
  and version pinning all live there. This repo only promises a standard-installable
  plugin.
- **LAW block content** - byte-locked; no edit under any step.
- **New skill behavior** - no verb changes, no signature changes, no new features;
  this plan repackages and tightens prose only.
- **The `1.0.0` ship decision** and any marketplace publication beyond this local
  repo.
- **Git operations** - the user commits and pushes.

## Verification

1. `python3 test/test_modes.py` exits 0 (LAW blocks and echo contract intact through
   every edit).
2. `python3 build.py --check` exits 0 (version stamps and zip in sync with
   plugin.json at `0.0.0`).
3. `grep -ri 'cowork' plugin/` is empty; no `plugin/skills/` text refers to Chat or
   Desktop as an execution surface.
4. The plans build section bridges through `/modes agent` unconditionally.
5. Fence check: in every `plugin/skills/*/SKILL.md`, each bare ` ``` ` line is a
   closer - except the two LAW openers in modes SKILL.md, which are the only bare
   openers in the repo.
6. `unzip -l ccvi-skills.zip` lists exactly the plugin tree; embedded files byte-match
   `plugin/`.
7. The standard install flow succeeds and the skills respond with their unchanged
   signatures; the modes hook demonstrably denies a plan-mode non-markdown write.

**Escape hatch:** if reality does not match this plan at any step - the source has
drifted from the verified facts, a path constant does not exist, the marketplace
rejects the layout, a test fails for a non-path reason - STOP and surface it with the
evidence; do not improvise.
