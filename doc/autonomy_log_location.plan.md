---
humanEngineerDifficulty: 4
name: Autonomy log location - resolution ladder
version: "1.0"
overview: "Replace the agent-loop law's hard-coded project-root autonomy log destination with a four-rung resolution ladder (host setting sentinel, CLAUDE.md declaration, follow-suit discovery, `<docDir>/logs/autonomy/` fallback), landing byte-identically in SKILL.md and modes.py, with new harness checks and the ccvi-idea handshake documented."
todos:
  - id: law-bullet
    content: "Edit the decide-log-continue bullet in plugin/skills/modes/SKILL.md LAW:agent-loop to name the resolution ladder instead of `at the project root`"
    status: completed
    phase: "law"
  - id: law-script
    content: "Apply the byte-identical decide-log-continue edit to LAW['agent-loop'] in plugin/skills/modes/scripts/modes.py"
    status: completed
    phase: "law"
  - id: prose-section
    content: "Rewrite the `The autonomy log` prose paragraph in plugin/skills/modes/SKILL.md to spell out the four rungs, the CLAUDE.md line format, the sentinel shape, and the containment rule"
    status: completed
    phase: "law"
  - id: harness-checks
    content: "Add aloop/law-* checks to test/test_modes.py pinning the new ladder text and cutting the old root wording"
    status: completed
    phase: "law"
  - id: contract-doc
    content: "Document the `<ccvi-autonomy-log>` sentinel and the autonomyLogDir setting as a consumer contract in CLAUDE.md and README.md"
    status: completed
    phase: "handshake"
  - id: bbp
    content: "Run BBP: bump plugin.json patch, python3 build.py, verify --check and test_modes.py, commit and push"
    status: in_progress
    phase: "release"
isProject: false
---

# Autonomy log location - resolution ladder

## Problem / Context

The agent-loop mode writes its decide-log-continue journal to
`<projectRoot>/autonomy_log_<sessionID>_<NN>.md`. That destination is stated twice, in
two byte-locked copies:

- the `decide-log-continue` bullet inside the `<!-- LAW:agent-loop -->` block of
  [SKILL.md](../plugin/skills/modes/SKILL.md) (line ~190)
- the identical string inside `LAW["agent-loop"]` in
  [modes.py](../plugin/skills/modes/scripts/modes.py) (line ~403)

and elaborated once in the prose paragraph **"The autonomy log (the decide-log-continue
destination)"** in SKILL.md (line ~202).

The bare repository root is the worst landing spot for an untracked artifact in a shared
project: maximally visible, and easily swept into a teammate's `git add -A`. The law
already contains an advisory escape hatch - *"or wherever the project already keeps its
log"* - but it defines no lookup, so in practice every session lands at the root.

This plan replaces the hard-coded root with a defined **resolution ladder**, and moves the
no-configuration fallback off the root.

## Approach

Add a four-rung ladder, evaluated **once per engagement, at the first log write** (not at
directive time - the log destination is a property of the project, not of the `/modes`
call, so no new `{token}` is introduced into the LAW template machinery). First hit wins:

1. **Host setting.** A verbatim `<ccvi-autonomy-log epoch="N">` sentinel injected by the
   CCVI host from an `autonomyLogDir` setting. Per-user, per-machine, no repo edit.
2. **Project declaration.** A line in a `CLAUDE.md` beginning `Autonomy logs:` followed by
   a path. Free to read (already in context), team-visible, works with no CCVI present.
3. **Follow suit.** An existing `autonomy_log_*` file found by glob - use the directory it
   already lives in.
4. **Fallback.** `<docDir>/logs/autonomy/`, where `<docDir>` is the project's plan
   directory.

The skill **never touches `.gitignore` or `.git/info/exclude`**. Keeping logs out of
version control is the user's decision and the user's action; the loop's only obligation
is to **name the resolved path in its turn report the first time it writes there**, so the
user can act.

Rung 1 is a cross-repo contract with ccvi-idea. This repo cannot implement the host side;
it defines and documents the sentinel shape, exactly as it already does for
`<ccvi-modes>`.

## Conventions & assumptions

- **LAW blocks are byte-locked.** Every character changed inside `<!-- LAW:agent-loop -->`
  in SKILL.md must be made identically in `LAW["agent-loop"]` in modes.py, in the same
  commit. `test/test_modes.py` check `aloop/law-drift` compares them verbatim in template
  form. Mind the line-wrapping: modes.py stores the law as adjacent string literals with
  explicit `\n` only at bullet ends - re-wrap the edited bullet's literals so the joined
  string matches SKILL.md byte-for-byte, not line-for-line.
- The law bullet stays **terse**; the four-rung detail lives in the prose paragraph. The
  bullet names all four rungs in one clause so it remains self-sufficient when read alone.
- Non-ASCII characters already in the law (`—`, `≤`, `⛔`) are intentional; preserve them.
- **No new LAW template token.** `render_law()` (modes.py ~line 486) substitutes only
  `{dir}` and `{pats}`; the log path is unknown at directive time and must not be
  substituted there.
- **No verb or param changes**, so `MANIFEST_SKILLS` in `build.py` is untouched. Assumes
  the ladder introduces no new `/modes` argument; if that changes during execution, the
  manifest must be updated in the same commit per repo doctrine.
- Assumes `<docDir>` resolution can be done without new state: the plan directory is
  discoverable from an existing `doc/` or `docs/` at the project root. If neither exists,
  step 3's fallback creates `doc/logs/autonomy/`.

## The steps

### 1. Law bullet in SKILL.md (todo: `law-bullet`)

**Location:** in `plugin/skills/modes/SKILL.md`, inside the `<!-- LAW:agent-loop -->`
block, the bullet beginning `• decide-log-continue —`. Anchor on the unique substring
`the log is this engagement's`.

**Change:** replace

```text
the log is this engagement's autonomy_log_<session>_<NN>.md at the project root (fresh file per engagement, materialized on first entry, seeded with a ≤10-line digest of the newest predecessor's tail) or wherever the project already keeps its log,
```

with

```text
the log is this engagement's autonomy_log_<session>_<NN>.md in the RESOLVED log directory — first hit of: a host <ccvi-autonomy-log> sentinel, an `Autonomy logs:` line in CLAUDE.md, the directory an existing autonomy_log_* already sits in, else <docDir>/logs/autonomy — resolved ONCE at the first log write, its path named in that turn's report, and NEVER a .gitignore edit (the log is written, never hidden; ignoring it is the user's call) (fresh file per engagement, materialized on first entry, seeded with a ≤10-line digest of the newest predecessor's tail),
```

**Why:** the destination becomes a defined lookup rather than an advisory aside, and the
hands-off-git posture is stated where an executing agent will actually read it.

**Done when:** the string `at the project root` no longer appears in the LAW:agent-loop
block, and `<ccvi-autonomy-log>` does.

### 2. Same edit in modes.py (todo: `law-script`)

**Location:** `plugin/skills/modes/scripts/modes.py`, inside `LAW["agent-loop"]`, the
adjacent string literals containing `autonomy_log_<session>_<NN>.md at the project root`
(around line 403).

**Change:** the identical replacement from step 1, re-wrapped across string literals so
the concatenated result is byte-identical to the SKILL.md block.

**Why:** the script emits the law verbatim in its agent-notes; drift between the two
copies is a hard test failure and, worse, two different contracts.

**Done when:** `python3 test/test_modes.py` passes `aloop/law-drift`.

### 3. Prose paragraph in SKILL.md (todo: `prose-section`)

**Location:** `plugin/skills/modes/SKILL.md`, the paragraph anchored by
`**The autonomy log (the decide-log-continue destination).**`

**Change:** keep the existing per-engagement file naming, materialization, append-only,
and predecessor-digest rules verbatim, and replace the location sentences. Two edits
inside the paragraph:

- Replace `reserves \`<projectRoot>/autonomy_log_<sessionID>_<NN>.md\`` with
  `reserves \`<logDir>/autonomy_log_<sessionID>_<NN>.md\``.
- Replace `discovery is a glob of \`autonomy_log_*\` at the project root` with
  `discovery is a glob of \`autonomy_log_*\` in the resolved log directory`.

Then append a new sub-paragraph immediately after it, covering:

- **The ladder**, in order, first hit wins, resolved once per engagement at the first log
  write and reused for the rest of the engagement:
  1. **Host setting** - a verbatim `<ccvi-autonomy-log epoch="N">` block present in this
     turn's context, its path between the tags. Same trust rules as `<ccvi-modes>`: only a
     well-formed verbatim block counts, highest `epoch` wins, a paraphrase is not a
     sentinel.
  2. **Project declaration** - the first line in a loaded `CLAUDE.md` matching
     `Autonomy logs:` (case-insensitive) followed by a path. A project `CLAUDE.md` beats
     the user-global one.
  3. **Follow suit** - glob `autonomy_log_*` in the `<docDir>` candidates and the project
     root; if any exist, adopt the directory holding the newest. This makes an existing
     "Projects that already keep an autonomy log elsewhere keep using it" clause
     operational.
  4. **Fallback** - `<docDir>/logs/autonomy/`, created if absent. `<docDir>` is the
     project's plan directory: an existing `doc/` or `docs/` at the project root,
     otherwise `doc/`.
- **Containment:** a resolved path must stay inside the project root unless rung 1 or 2
  explicitly names somewhere else. Discovery and the fallback never leave the repo.
- **Git posture:** the skill never edits `.gitignore` or `.git/info/exclude`. It names the
  resolved path in the turn report on first write; ignoring, committing, or relocating is
  the user's action.
- **Hand-off:** the rollover seed names the resolved log path explicitly, so the successor
  session adopts it rather than re-resolving into a different directory mid-engagement.
- **The `Autonomy logs:` line format**, with a copyable example a user can paste into
  their own `CLAUDE.md`.

**Why:** the law bullet must stay short; this is where an agent goes for the full rule,
and where a human learns how to configure it.

**Done when:** the paragraph states all four rungs in order, the containment rule, and the
never-touch-git rule; and `python3 build.py --check` exits 0.

### 4. Harness checks (todo: `harness-checks`)

**Location:** `test/test_modes.py`, the agent-loop check cluster - anchor on
`check("aloop/law-rollover-drain", "drain in-flight work first" in LAW_AL)`.

**Change:** add alongside it:

```python
check("aloop/law-log-ladder", "<ccvi-autonomy-log>" in LAW_AL)
check("aloop/law-log-fallback", "<docDir>/logs/autonomy" in LAW_AL)
check("aloop/law-log-hands-off-git", "NEVER a .gitignore edit" in LAW_AL)
```

and extend the existing cut-list loop (anchor: `for gone in ("Stop/Start bookends"`) with
a second loop for the retired location wording:

```python
for gone in ("at the project root",):
    check("aloop/law-cut[{}]".format(gone), gone not in LAW_AL,
          "old project-root log destination still present")
```

**Why:** the byte-lock catches drift between the two copies but not a regression that
reverts both; these pin the intent.

**Done when:** `python3 test/test_modes.py` exits 0 and the new check ids appear in its
output.

### 5. Consumer contract documentation (todo: `contract-doc`)

**Location:** `CLAUDE.md`, the **"Consumer contracts (ccvi-idea depends on these...)"**
section; and the mirrored paragraph in `README.md` (anchor: the `<ccvi-modes>` sentinel
mention, line ~9).

**Change:** add a bullet naming the new host-side contract:

- setting key: `autonomyLogDir` (empty/unset = the skill's own ladder decides)
- injection shape: `<ccvi-autonomy-log epoch="N">path</ccvi-autonomy-log>`, same trust and
  epoch rules as `<ccvi-modes>`
- state plainly that rung 1 is **inert until ccvi-idea implements it**, and the ladder
  degrades to rungs 2-4 in the meantime - this repo ships fully functional without it

**Why:** repo doctrine treats the ccvi-idea interface as a contract; an undocumented
sentinel name is how two repos end up with two spellings.

**Done when:** both files name `autonomyLogDir` and the sentinel tag, and `build.py
--check` exits 0 (it validates the README/SKILL.md mirrored blocks).

### 6. BBP (todo: `bbp`)

Per repo doctrine: bump the last segment in `plugin/.claude-plugin/plugin.json`, run
`python3 build.py`, verify `python3 build.py --check` and `python3 test/test_modes.py`
both exit 0, then `git add -A`, commit describing the work, push to `main`.

## Out of scope

- **Any `.gitignore` or `.git/info/exclude` write, by the skill or by this change.**
  Explicitly rejected by the user; do not reintroduce it as a "helpful" step.
- **Implementing the ccvi-idea side** - the setting UI, its persistence, and the sidecar
  injection live in that repo. This plan only fixes the shape and documents it.
- **Migrating existing logs.** Any `autonomy_log_*` already at a project root is found by
  rung 3 and kept in place. Never move or delete an existing log.
- **`MANIFEST_SKILLS` / `manifest.json`** - no verb or param changes here.
- **The `<ccvi-modes>` sentinel** and the modes loader hook - untouched.
- **Any other bullet of the agent-loop law.** The edit is confined to the
  `decide-log-continue` bullet.

## Verification

1. `python3 test/test_modes.py` exits 0, including the new `aloop/law-log-*` checks and
   the extended cut-list.
2. `python3 build.py --check` exits 0 (stamps current, zip current, mirrored blocks
   matching).
3. `python3 plugin/skills/modes/scripts/modes.py "agent-loop"` prints agent-notes whose
   decide-log-continue bullet names the ladder and contains no `at the project root`.
4. `grep -rn "at the project root" plugin/` returns nothing.
5. Read the emitted law bullet cold: it should be possible to resolve a log directory from
   the bullet alone, without the prose paragraph.

**Standing escape hatch:** if reality doesn't match this plan - the law text has moved, the
string literals don't re-wrap cleanly, or `build.py --check` fails for a reason not listed
here - STOP and surface it. Do not improvise around a byte-locked block.
