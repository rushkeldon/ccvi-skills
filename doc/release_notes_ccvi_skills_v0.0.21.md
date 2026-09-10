# ccvi-skills v0.0.21 - release notes

**Range:** v0.0.16 (`7ecfdf6`) → v0.0.21 (`751591b`)
**Date:** 2026-09-10

## Summary

This release is **the agent-loop mode's compression trade, paid in two halves**, plus a
new guard on the harness that enforces the trade's terms.

v0.0.17 cut the `agent-loop` LAW block by roughly 60% on the argument that *repetition
and derivation are substitutes*: the long block bound the mode because it was re-read on
every wake, so a shorter block has to buy that adherence back by being **derived** rather
than merely read. v0.0.17 shipped the cut without the derivation, which left the mode
binding **less** than before - a regression, not a tidy-up. v0.0.18 paid the other half
and added an anti-erosion floor so the same trade cannot be made again silently.

Also new in v0.0.17: **the measurement discipline**, written out of a night of autonomous
work that produced two confident wrong numbers.

v0.0.19-v0.0.21 are packaging and a reverted doctrine edit, with no behavior change.

## v0.0.17 - compress the agent-loop law, add the measurement discipline (`f29d631`)

### The LAW block: 9,926 → 3,777 bytes

Every distinct **failure mode** the block named was retained. What was cut is duplicated
**mechanism** that already appears in the skill body. The block is what gets re-read on
every wake, so it now carries only what must be obeyed **without a lookup**.

Seven assertions were re-pointed from the law to the body - clauses needed once per
engagement, or on a rare event. They still guarantee the lesson **exists**; they no longer
guarantee it is in **working memory on wake**. That trade is deliberate and is documented
in the new body section **"Where the mechanism went"** (`SKILL.md:307`), to be read once
when the flywheel first engages.

### The harness refused two cuts and was right

Two proposed cuts were rejected by `test/test_modes.py` and restored to the law:

- the **landing-bound invariant** phrasing;
- the **rollover threshold** (a threshold checked at every landing has no other trigger).

### The measurement discipline (new)

Provenance: two confident wrong numbers from autonomous work. In both cases the tool was
chosen because it was **already to hand** rather than because it fitted, and its real
behavior was never checked against what its parameters implied - a capture asked for 50ms
between frames and delivered **3.05s**; the same tool's nominal holds carried **0.695s** of
hidden per-step overhead.

Three parts:

1. **One law bullet** - state what must be resolved, and the check that proves it,
   **before** naming any tool. An unusable result restarts *there*, never at a write-up:
   re-tooling produces nothing visible and is still the work.
2. **One clause on truthful reporting** - a number is reported **with the output of its
   check beside it**. This is the load-bearing half: it puts the obligation in the
   **output format**, where a bare number is visibly incomplete to any reader, rather than
   in the agent's diligence, where it fails silently.
3. **A body section, "Choosing an instrument"** (`SKILL.md:198`) - order of operations:
   spec with numbers first, then search the toolkit, then use / extend / build in that
   order; demonstrate before the first number; an unusable result returns to the spec.

## v0.0.18 - pay the other half, and guard the harness itself (`747a72d`)

### agent-loop gets its own encode ask

The skill's encode step (predict-then-derive, answered privately before the echo) gains a
**fourth ask scoped to `agent-loop` only**: predict, in one sentence, what **this turn's
landing** must contain - what will be running, what will be armed - then check it against
what you actually land with.

One question, and **falsifiable**: a prediction about a specific future moment that
reality settles minutes later. The two generic asks beside it have no checkable answer,
and a reflective prompt answered many times becomes recital; recital does not encode.
This is the derivation half of the v0.0.17 trade.

### The anti-erosion floor on the harness

Each pinned phrase in `test_modes.py` is a lesson someone decided was load-bearing, and
this harness refused two cuts during the v0.0.17 compression and was right both times. It
then had seven assertions **re-pointed** by that same pass - the one move that defeats it.

`MIN_CHECKS = 124` (`test/test_modes.py:431`) distinguishes **erosion** from
**relocation**:

- **deleting** a check drops the count and **fails**;
- **re-pointing** one (law → body) keeps the count and **passes**, because the lesson
  still exists.

**Demonstrated, not assumed**: removing one assertion drops 124 → 123 and fails; restored,
green. Lowering the floor is now documented as a **stop-and-ask**, not a judgment call
(`SKILL.md:392-396`).

### Blurb correction

The `agent-loop` blurb promised "at least one sub-agent always running", which the law
then contradicts with a **landing-bound** check. Found only by reading the **emitted
agent-notes** rather than the diff - passing the harness is evidence the phrases survived,
never evidence the law binds.

## v0.0.19-v0.0.21 - packaging, and a doctrine edit made and reverted

- **`a7fd3d0` (v0.0.19)** - version-only rebuild so the zip carries the v0.0.17/v0.0.18
  modes work as an installable artifact.
- **`73fa238` (v0.0.20)** - **made in error.** Edited `CLAUDE.md` to delete the `BBPI`
  name and the step-4 self-install, on the mistaken belief that the session was in the
  **ccvi-idea** repo. `BBPI` and the self-install step are real and correct here.
- **`751591b` (v0.0.21)** - reverted that edit. `CLAUDE.md` restored **byte-identical** to
  its `a7fd3d0` state via `git checkout a7fd3d0 -- CLAUDE.md`; net diff across the whole
  range is zero. The version moved **forward** to 0.0.21 rather than back to 0.0.19,
  because a `git revert` would have republished a lower number than consumers had already
  seen. Both commits remain in the log, so the mistake is recorded rather than rewritten.

## Diff across the range

```text
$ git diff --stat 7ecfdf6 HEAD
 README.md                            |   2 +-
 ccvi-skills.zip                      | Bin 135185 -> 134434 bytes
 manifest.json                        |   2 +-
 plugin/.claude-plugin/plugin.json    |   4 +-
 plugin/skills/cleancode/SKILL.md     |   2 +-
 plugin/skills/modes/SKILL.md         | 133 ++++++++++++++++++++++-----
 plugin/skills/modes/scripts/modes.py | 169 +++++++++--------------------------
 plugin/skills/plans/SKILL.md         |   2 +-
 plugin/skills/repos/SKILL.md         |   2 +-
 plugin/skills/seedprompt/SKILL.md    |   2 +-
 test/test_modes.py                   |  68 ++++++++++++--
 11 files changed, 221 insertions(+), 165 deletions(-)
```

Per-file insertions/deletions for the three files that actually moved:

| File | + | - |
|---|---|---|
| `plugin/skills/modes/SKILL.md` | 113 | 20 |
| `plugin/skills/modes/scripts/modes.py` | 41 | 128 |
| `test/test_modes.py` | 59 | 9 |

`modes.py` is the only net shrink, because the LAW copy it emits shrank with the block it
is byte-locked against. `SKILL.md` grew by roughly the mechanism that moved into it. The
one-line diffs in the other four `SKILL.md` files, the README, and `manifest.json` are
version stamps only.

## Verification

```text
$ python3 build.py --check
build --check OK — version 0.0.21 stamped everywhere; manifest + zip current

$ python3 test/test_modes.py
test_modes OK — 124 checks passed
```

The check count is at the floor (124), which is the intended steady state: the floor is
raised when checks are added, and going below it is the failure this release exists to
prevent.

## Consumer impact (ccvi-idea)

**None.** No consumer contract moved: zip layout, `manifest.json` verb and param
signatures, marketplace shape, and the `<ccvi-autonomy-log>` / `<ccvi-doc-dir>` sentinel
spellings and semantics are all unchanged. Only the version field moved.

The change that *does* reach users is behavioral, not structural: any session entering
`agent-loop` now answers a fourth, falsifiable encode ask, and reads a shorter law block
backed by two new body sections.

## Install

Not performed. Refreshing this machine's live copy at `~/.ccvi/ccvi-skills/plugin/`
remains outstanding.
