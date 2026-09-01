---
humanEngineerDifficulty: 3
name: "<ccvi-doc-dir> hint feeding <docDir>"
version: "1.1"
overview: "Accept the ccvi-idea proposal: lift the `<docDir>` definition out of rung 4 into a single term definition consumed by rungs 3 and 4, fed by an optional `<ccvi-doc-dir>` host hint that is explicitly not a rung; add mechanical containment and blank-body-is-a-miss rules; pin the semantics with the harness's first SKILL.md prose checks; and reword the contract docs so the tag is the contract and the setting key is host-local."
todos:
  - id: docdir-definition
    content: "Lift `<docDir>` into its own definition ahead of the rung list in plugin/skills/modes/SKILL.md, fed by the `<ccvi-doc-dir>` hint, with the not-a-rung, containment, and blank-body rules"
    status: completed
    phase: "prose"
  - id: harness-checks
    content: "Add the harness's first SKILL.md prose checks to test/test_modes.py, pinning `<ccvi-doc-dir>` and the phrase that keeps it out of rung 1"
    status: completed
    phase: "prose"
  - id: contract-docs
    content: "Add the `<ccvi-doc-dir>` consumer-contract bullet to CLAUDE.md and README.md and reword the `autonomyLogDir` key pin to name the tag instead"
    status: completed
    phase: "handshake"
  - id: bbp
    content: "Run BBP: bump plugin.json patch, python3 build.py, verify --check and test_modes.py, commit and push"
    status: completed
    phase: "release"
isProject: false
---

# `<ccvi-doc-dir>` hint feeding `<docDir>`

## Problem / Context

v0.0.7 shipped the autonomy-log resolution ladder. Its rung 4 lands at
`<docDir>/logs/autonomy/`, and `<docDir>` is currently defined **inside rung 4** as a blind
probe: an existing `doc/` or `docs/` in the project root, otherwise `doc/`.

Two problems, both raised by the ccvi-idea agent in
`../ccvi-idea/doc/proposal_ccvi_doc_dir_hint.md` (round 2, both amendments accepted):

1. **The probe guesses wrong exactly when the user has expressed a preference.** CCVI holds
   the project's plan directory as a setting (`ccvi.plans.dir`, default `doc`). A user who
   sets it to `notes` gets plans in `notes/` and autonomy logs in `doc/logs/autonomy/` -
   two trees, neither chosen. No skill-side logic can recover that setting, and the host
   cannot push it through `<ccvi-autonomy-log>` without that value outranking rung 2 and
   permanently overriding any repo's `Autonomy logs:` line. Hence a **second channel with
   different semantics: a fact about layout, not a preference about where logs go.**
2. **`<docDir>` has two consumers but one of them owns the definition.** Rung 3's
   follow-suit glob searches "the `<docDir>` candidates and the project root"
   ([SKILL.md](../plugin/skills/modes/SKILL.md) line ~222); rung 4 defines the term
   (line ~226). Defining a term inside one of its two consumers is how the two drift apart.

Three smaller gaps close alongside: a **blank sentinel body** is currently well-formed and
would resolve rung 1 to the empty string with no defined behavior; **containment** is
stated as a resolve-and-compare rule when a mechanical one is cheaper; and nothing states
that the hint must **not** be waited for or re-checked.

**The headline: no LAW edit.** The byte-locked bullet already says `else
<docDir>/logs/autonomy` and never defines `<docDir>`. Only the definition moves, and it
lives entirely in prose. No `SKILL.md`/`modes.py` twin edit, no drift risk.

## Approach

Restructure the ladder paragraph so `<docDir>` is defined **once, before first use**, and
both rungs consume that one definition:

> `<docDir>` is the project's plan directory: a verbatim `<ccvi-doc-dir epoch="N">` hint
> present in this turn's context, otherwise an existing `doc/` or `docs/` in the project
> root, otherwise `doc/`.

The hint is **an input to `<docDir>`, never a rung**. Rungs 1-3 are evaluated first and in
order, unchanged; the hint only ever answers "what is `<docDir>`?" for whichever rung asks.
Its presence alone never resolves the ladder.

Three rules land beside it:

- **Containment, mechanical:** a hint value that is absolute or contains `..` is ignored
  and the probe runs. Checkable without filesystem access. An out-of-repo log directory is
  a *preference*, which is what rungs 1 and 2 are for; the hint only describes layout.
- **Blank body is a miss**, for `<ccvi-doc-dir>`, for `<ccvi-autonomy-log>`, and (a
  consistency call, see assumptions) for a blank rung-2 `Autonomy logs:` value.
- **Resolve once, never re-check.** Keeping the hint in context at the first-log-write
  moment is a host obligation (it attaches unconditionally on a session's first turn, plus
  the existing re-attach-after-compaction trigger). The skill adds **no** waiting or
  re-checking logic - only the side that can observe turn boundaries can fix that, and
  re-check logic here would contradict the resolve-once rule the paragraph already states.

## Conventions & assumptions

- **No LAW-block edit.** `<!-- LAW:agent-loop -->` in SKILL.md and `LAW["agent-loop"]` in
  `modes.py` are untouched. If any step seems to require one, STOP - the seam is wrong.
- **The harness has no SKILL.md prose checks today.** It asserts LAW-block byte-equality
  and script behavior only. Todo `harness-checks` adds the first of their kind; the local
  `md` variable (read at `test/test_modes.py` line ~245) is already in scope in the
  agent-loop cluster where the new checks go.
- **Pinnable phrases.** The harness pins literal strings, so the prose must contain
  `<ccvi-doc-dir>` and the exact phrase **`never a rung-1 hit`**. Choose no synonym: the
  check and the prose are one unit, and a later reword that drops the phrase must fail the
  harness rather than silently promote the hint to a rung.
- **Blank rung-2 values are a consistency call, not the proposal's ask.** The proposal
  covers the two sentinels; extending "blank is a miss" to a blank `Autonomy logs:` value
  is this plan's decision, on the grounds that one rule across all three declaration
  sources is easier to hold than two rules with an exception. Consequence: a repo with a
  literally empty `Autonomy logs:` line falls through to rung 3 instead of resolving to
  the empty string.
- **No verb or param changes**, so `MANIFEST_SKILLS` in `build.py` and `manifest.json` are
  untouched.
- Assumes the ladder prose still sits where v0.0.7 put it - the paragraph anchored by
  `**Resolving \`<logDir>\` (the four-rung ladder).**`. If it has moved, re-anchor rather
  than guessing at line numbers.

## The steps

### 1. The `<docDir>` definition (todo: `docdir-definition`)

**Location:** `plugin/skills/modes/SKILL.md`, the paragraph anchored by
`**Resolving \`<logDir>\` (the four-rung ladder).**`.

**Change A - define the term before first use.** In that intro paragraph, immediately
before the sentence `Take the **first rung that hits**:`, insert the `<docDir>` definition
plus its three rules. Cover, in prose:

- the definition itself (hint → `doc/`/`docs/` probe → `doc/`);
- **not a rung** - rungs 1-3 are evaluated first and in order; the hint is an input to
  `<docDir>` and is **never a rung-1 hit**; its presence alone never resolves the ladder;
- **trust rules** identical to `<ccvi-modes>`: verbatim well-formed block only, highest
  `epoch` wins (its own independent counter, evaluated per tag), a paraphrase is not a
  sentinel;
- **containment, mechanical** - an absolute value or one containing `..` is ignored and
  the probe runs;
- **blank body is a miss** - for `<ccvi-doc-dir>`, `<ccvi-autonomy-log>`, and a blank
  rung-2 `Autonomy logs:` value alike;
- **no trailing-slash significance** - `notes` and `notes/` are the same value;
- **resolve once, never re-check** - the skill adds no logic to wait for or re-poll the
  hint; keeping it in context at the first-log-write moment is the host's obligation.

Include the tag's shape as a tagged fence so a reader sees the literal form:

```text
<ccvi-doc-dir epoch="3">notes</ccvi-doc-dir>
```

**Change B - strip the now-duplicated definition from rung 4.** Rung 4 becomes just its
destination:

```text
4. **Fallback.** `<docDir>/logs/autonomy/`, created if absent.
```

**Change C - fix rung 3's now-stale plural.** Rung 3 reads "across the `<docDir>`
candidates and the project root". "Candidates" fit a two-way probe; against a single
resolved definition it no longer parses. Reword to the singular - glob `autonomy_log_*` in
`<docDir>` and in the project root - keeping the two search locations intact.

**Why:** one term, one definition, both consumers pointing at it - and the hint reaches
rung 3's candidate set for free, which the proposal's original rung-4-scoped wording would
have missed.

**Done when:** `<docDir>` is defined exactly once in the file, ahead of its first use;
rung 4 contains no definition; the prose contains `<ccvi-doc-dir>` and the literal phrase
`never a rung-1 hit`; and `python3 test/test_modes.py` still exits 0 (the LAW blocks are
untouched, so `aloop/law-drift` must still pass).

### 2. Harness checks (todo: `harness-checks`)

**Location:** `test/test_modes.py`, the agent-loop cluster - anchor on the existing
`check("aloop/law-log-hands-off-git", ...)` line, adding after it. Use the local `md`
(SKILL.md contents), **not** `LAW_AL`: this content is prose, and asserting it against the
law text would fail.

**Change:**

```python
check("aloop/docdir-hint", "<ccvi-doc-dir>" in md,
      "the <ccvi-doc-dir> hint is missing from the ladder prose")
check("aloop/docdir-not-a-rung", "never a rung-1 hit" in md,
      "the phrase keeping the doc-dir hint out of rung 1 is missing")
```

**Why:** the hint's whole safety property is that it cannot outrank rung 2. A later edit
that reworded it into a rung would be silent otherwise - nothing else in the repo would
notice.

**Done when:** `python3 test/test_modes.py` exits 0 and its total check count has risen by
exactly 2 (114, from 112).

### 3. Contract docs (todo: `contract-docs`)

**Location:** three files - rung 1's prose in `plugin/skills/modes/SKILL.md` (anchor:
`the CCVI host's \`autonomyLogDir\` setting`), the `<ccvi-autonomy-log>` bullet in the
**Consumer contracts** section of `CLAUDE.md`, and its mirrored paragraph in `README.md`.
**SKILL.md is the one that matters most** - it ships inside the plugin, so a wrong key
there travels to every install.

**Change A - the tag is the contract; the setting key is host-local.** All three files
currently name `autonomyLogDir`. CCVI will ship `ccvi.agentLoop.logDir`, so that key is a
documented-but-wrong fact sitting in two repos. Reword to name the **tag** as the contract
and describe the setting generically ("the host's autonomy-log-directory setting"), with
no key spelled out.

**Change B - add the `<ccvi-doc-dir>` bullet** alongside it: the tag and its epoch rule
(independent counter, per-tag highest-epoch-wins), that it feeds `<docDir>` and is **never
a rung**, the containment and blank-body rules, and that it is **inert until ccvi-idea
emits it** - the probe is the standing fallback, so the suite ships fully functional
without the host side.

**Why:** repo doctrine treats the ccvi-idea interface as a contract, and the failure mode
here is silent: two different spellings produce no error, just logs in the wrong tree
forever.

**Done when:** `grep -rn autonomyLogDir plugin/ CLAUDE.md README.md` returns nothing;
`CLAUDE.md` and `README.md` both name `<ccvi-doc-dir>` and `<ccvi-autonomy-log>`;
`python3 build.py --check` exits 0.

### 4. BBP (todo: `bbp`)

Bump the last segment in `plugin/.claude-plugin/plugin.json` (`0.0.7` → `0.0.8`), run
`python3 build.py`, verify `python3 build.py --check` and `python3 test/test_modes.py`
both exit 0, then `git add -A`, commit describing the work, push to `main`.

## Out of scope

- **The `LAW:agent-loop` block and its `modes.py` twin.** Explicitly not asked for, and
  the whole point of this seam. Do not touch either.
- **Rungs 1-3 and their order.** Unchanged. Only the `<docDir>` term moves.
- **Any skill-side logic that waits for, re-checks, or re-polls the hint.** Explicitly
  declined by the host, and it would contradict resolve-once.
- **`<ccvi-modes>` and the modes loader hook.**
- **Migration of existing `autonomy_log_*` files.** Rung 3 keeps finding them in place.
- **`MANIFEST_SKILLS` / `manifest.json`** - no verb or param changes.
- **Implementing the host side** - the setting, its per-project override, and the sentinel
  emission live in ccvi-idea.

## Verification

1. `python3 test/test_modes.py` exits 0 at **114** checks, including `aloop/docdir-hint`
   and `aloop/docdir-not-a-rung`.
2. `python3 build.py --check` exits 0.
3. The term is defined exactly once. Flatten before matching, because the phrase wraps
   across lines and `grep -c` counts lines rather than occurrences:
   `tr '\n' ' ' < plugin/skills/modes/SKILL.md | grep -o "is the project's plan directory" | wc -l`
   returns 1.
4. `grep -rn "autonomyLogDir" plugin/ CLAUDE.md README.md` returns nothing - the plugin
   tree included, since `SKILL.md` ships to every install.
5. **Run this BEFORE todo 4** - `git diff --exit-code -- plugin/skills/modes/scripts/modes.py`
   exits 0, proving the byte-locked twin was never touched. It is vacuous after the BBP
   commit (HEAD would be the post-change file) and misleading after `python3 build.py`,
   which stamps the version into `modes.py`'s `HELP_TEXT` (line ~97). Post-BBP, the only
   permissible diff in that file is that one version line.
6. Read the ladder paragraph cold: a reader meeting `<docDir>` in rung 3 must already have
   seen its definition.

**The live proof neither harness can reach** (recorded from the proposal; **not run by
this plan** - it needs both halves shipped and is the user's to run): in a scratch project
set `ccvi.plans.dir` to `notes`, leave the host log-dir setting unset, ensure no `Autonomy
logs:` line and no existing `autonomy_log_*` file so rungs 1-3 all miss, then enter
`/modes agent-loop`, assign trivial work, and force a first log entry. **Pass:** the log
lands in `notes/logs/autonomy/` and the turn report names that path. **Fail:**
`doc/logs/autonomy/` means the hint was absent or rejected at resolution time; anywhere
else means a rung above 4 hit unexpectedly. This is observable without touching the
filesystem only because the law requires naming the resolved path on first write - that
requirement is load-bearing for verification and must stay where it is.

**Standing escape hatch:** if reality doesn't match this plan - the ladder prose has moved,
a step seems to require a LAW edit, or the harness check count doesn't land at 114 - STOP
and surface it. Do not improvise.
