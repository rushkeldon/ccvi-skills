# CLAUDE.md - ccvi-skills

Repo doctrine for agents working here. Read this before editing anything under
`plugin/`.

## What this repo is

The CCVI family's skill suite: the `modes`, `plans`, and `seedprompt` Claude Code
skills as **one plugin, one version, one zip artifact**. The repo is its own
marketplace.

## Layout

```text
ccvi-skills/
  .claude-plugin/marketplace.json    - this repo is its own marketplace; source ./plugin
  plugin/
    .claude-plugin/plugin.json       - name, CANONICAL VERSION, hook registration
    hooks/enforce_modes.py           - PreToolUse hook (modes write filters)
    skills/modes/SKILL.md
    skills/modes/scripts/modes.py    - modes fast-path script
    skills/plans/SKILL.md
    skills/plans/tools/              - plan-check.cjs, archive-plans.sh, vendor/js-yaml.min.js
    skills/seedprompt/SKILL.md
  test/test_modes.py                 - golden harness; dev-only, never packaged
  build.py                           - stamp + README + zip + --check
  doc/                               - plans live here; doc/archive/ for finished ones
  README.md
  CLAUDE.md
  ccvi-skills.zip                    - built artifact: the plugin/ tree at zip root
```

## The tight-coupling doctrine

- The three skills ship together and **may assume each other is present**
  (`/plans build` bridges through `/modes agent` unconditionally; the agent-loop
  mode hands off via `/seedprompt write`).
- The skills **may assume the CCVI host is present**: the modes loader hook, the
  enforcement hook, the `<ccvi-modes>` sentinel, the Plan Editor, the seedprompt
  sidecar consumer. Runtime-resilience branches (a missing python3, a denied tool,
  a sentinel absent this turn, the sidecar not firing) stay; surface hedges do not.
- **No surface variants, ever.** This suite targets Claude Code inside the CCVI
  family only. Do not reintroduce Chat/Cowork/Desktop branches, variant dirs, or
  propagation machinery.

## Versioning and releases

- The suite version lives **only** in `plugin/.claude-plugin/plugin.json`. It starts
  at `0.0.0` and increments patch-wise: `0.0.1` ... `0.0.99`, then rolls to `0.1.0`.
  `1.0.0` is a deliberate future ship decision, not an increment.
- Release procedure: bump the version in `plugin/.claude-plugin/plugin.json`, run
  `python3 build.py` (stamps every display, updates the README, rebuilds
  `ccvi-skills.zip`), review the diff, and the **user** commits. Never bump inside
  build.py; the script stamps, it never bumps.
- `python3 build.py --check` must exit 0 before any release: it verifies all stamps
  and the zip's currency.

## Hard rules

- **LAW blocks are byte-locked.** The `<!-- LAW:plan -->` and
  `<!-- LAW:agent-loop -->` blocks in `plugin/skills/modes/SKILL.md` must stay
  byte-identical to the copies `modes.py` emits; `test/test_modes.py` asserts this.
  Never edit inside a LAW block. Their bare code fences are intentional - do not tag
  them.
- **Run the harness after touching modes:** `python3 test/test_modes.py` must exit 0.
- **Tag every code fence** in every repo markdown file (the plans skill's rule 5):
  real language for source, `text` for reflowable prose/output, `diagram` for
  alignment-critical blocks. The two LAW fences are the only sanctioned bare fences.
- **Plan workflow:** author plans into `doc/` (`*.plan.md`), archive finished ones
  into `doc/archive/` (`/plans archive doc`).
- **`../skills-anthropic` is a frozen quarry** - read-only reference; never write to
  it, and never re-import its multi-surface machinery.
- No commits or pushes by agents; the user commits.

## Future direction (named so nobody re-invents it)

**Vendor conditionals**, not surface variants: if the suite ever targets a second
engine (e.g. Codex via the Agent Skills open standard), the plan is conditional
branches inside the single SKILL.md bodies - the agent-loop LAW's host-generic
degradation language is the substrate for this. It is deliberately unbuilt; do not
start it without the user's direction.
