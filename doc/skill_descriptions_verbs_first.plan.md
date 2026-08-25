---
humanEngineerDifficulty: 2
name: skill descriptions verbs-first + seedprompt read verb
overview: "Rewrite all four skills' SKILL.md description strings to lead with a bare middot-separated verb inventory (the slash-command picker shows only ~90 chars; the model's 1536-char trigger budget keeps the prose after it), add the picker-facing argument-hint frontmatter field to each, and add a read verb to /seedprompt that consumes the pending seed (print + adopt + delete, the manual equivalent of the sidecar's inject-and-delete)."
version: "1.0"
todos:
  - id: descriptions-verbs-first
    content: "Rewrite the description frontmatter of all four SKILL.md files (modes, plans, seedprompt, cleancode) to the exact verbs-first strings given in The steps"
    status: completed
    phase: descriptions
  - id: argument-hints
    content: "Add the argument-hint frontmatter field to all four SKILL.md files, values per The steps"
    status: completed
    phase: descriptions
  - id: seedprompt-read-verb
    content: "Add the read verb to plugin/skills/seedprompt/SKILL.md: invocation row, dispatch step, echo contract, help output line, and the two doctrine-paragraph updates"
    status: completed
    phase: read-verb
  - id: manifest-read-verb
    content: "Add the read verb (no params) to seedprompt's entry in build.py MANIFEST_SKILLS - same commit as seedprompt-read-verb"
    status: completed
    phase: read-verb
  - id: readme-seedprompt-read
    content: "Update README.md's seedprompt row (and any other verb enumeration) to include read"
    status: completed
    phase: read-verb
  - id: verify-and-release
    content: "Run build.py --check, test_modes.py, test_comments.py all green; BBP (bump/build/push); refresh the installed plugin at ~/.ccvi/ccvi-skills/plugin/ including manifest.json at its root"
    status: in_progress
    phase: finish
isProject: false
---

# skill descriptions verbs-first + seedprompt read verb

## Problem / Context

Each SKILL.md `description` is dual-duty (documented Claude Code behavior): it is the
model's trigger text in the per-session skill listing AND the string the slash-command
picker displays. The two audiences have wildly different budgets - the model listing
truncates at 1,536 chars (description + `when_to_use` combined), while the picker
shows only ~90 chars. Today the first ~90 chars are prose ("Post-stabilization code
consolidation via /cleancode [noun]..."), so the verb inventory - the one thing a
human scanning the picker wants - is never visible.

Keldon's workflow: the skill is already known when the picker is open, so the visible
window should carry ONLY the verb names - no slash command, no argument shapes, no
prose. Argument shapes move to the documented `argument-hint` frontmatter field
(shown during autocomplete). The model's trigger prose stays in `description`, after
the verb inventory, well inside the 1,536 budget.

Separately: `/seedprompt` has no consume verb. `show` is deliberately non-destructive
and `clear` is a separate step; only the CCVI sidecar automates load-then-delete.
Keldon wants `/seedprompt read` - the manual consume path: load the seed into the
session and delete it, preserving one-use semantics in a single verb.

## Approach

Two independent slices, one release.

**Slice 1 - the description surfaces.** All four descriptions open with a bare verb
inventory: middot separator (`•` U+2022), NO spaces around it, verb names only. For
cleancode's two-word verbs, families group with `/` inside the family and `•` between
families, pipeline order (decided in review; the ~90 window clips mid-`conventions`
and `run` falls off - accepted). After the inventory: ` - ` then the trigger prose
(hyphen, never an em dash - house style). Each skill also gains `argument-hint`.
`when_to_use` is deliberately NOT adopted (unprobed on the installed CLI; the
description already carries the trigger prose safely).

**Slice 2 - the read verb.** `/seedprompt read` consumes the pending seed: print the
absolute path + full contents into the session (printing into context IS the
loading), treat the body as the active hand-off brief, then delete the file.
Frontmatter directives stay INERT under `read` (allowlist handlers live only in the
sidecar); `read` reports `title:` as context, executes nothing. `show` stays
non-destructive; `clear` stays. The skill's doctrine line softens from "the skill
never consumes" to "write never consumes; `read` is the explicit manual consume
path, equivalent to the sidecar's inject-and-delete."

The ideal endgame - `read` triggering the same CCVI card the sidecar renders on
auto-inject - is NOT buildable from the skill side today (the card is sidecar-owned
UI); it is recorded in Out of scope as a future ccvi-idea affordance.

## Conventions & assumptions

- **Separator:** `•` (U+2022), no surrounding spaces. Family form for cleancode only:
  `noun verb/verb/verb` with `/` inside a family.
- **No `: ` (colon-space) inside any description string** - they are unquoted YAML
  plain scalars; a colon-space would collapse the frontmatter. The exact strings
  below honor this; if editing them, re-check.
- **Hyphens, never em dashes**, in all newly written prose (house style).
- **The trigger prose must keep its "Use when..." sentence** - that is the model's
  invocation signal; only its position changes.
- Assumes `argument-hint` is display-only and ignored gracefully by hosts that
  don't know it (documented Claude Code field; ccvi-idea parses only manifest
  `version` + the plans `verbs:` block). If a host chokes on the new key, drop
  `argument-hint` from that skill and surface it.
- `build.py` stamps version displays; the seedprompt help-output version line is
  stamped automatically - never hand-bump it.
- The modes LAW blocks are byte-locked (`test/test_modes.py`); nothing in this plan
  touches them. If the harness fails after the modes description edit, STOP - the
  edit strayed.

## The steps

1. **`descriptions-verbs-first`** - In each SKILL.md, replace the `description:`
   value with the exact string below (anchor: the `description:` line in each
   file's frontmatter). Single-line plain scalars, verbatim:

   `plugin/skills/modes/SKILL.md`:

   ```text
   plan•agent•agent-loop•one-word•sbs•exclude•include•exit•list•clear - manage persistent response modes via /modes [verb] directives. Use when the user issues a /modes directive, or asks in natural language to enter, exit, list, clear, or check any response mode.
   ```

   `plugin/skills/plans/SKILL.md`:

   ```text
   write•review•verify•update•build•archive - lifecycle verbs for Cursor-compatible *.plan.md files via /plans [verb]. Use when the user issues a /plans directive or asks to author, review, verify, update, build, or archive a *.plan.md.
   ```

   `plugin/skills/seedprompt/SKILL.md` (already includes `read` - land with or
   after step 3, same release):

   ```text
   write•read•show•clear - author, consume, inspect, or clear a one-use AI-to-AI session hand-off ("seed prompt") at <memoryRoot>/seedprompt.md - the reliable authoring path to the one well-known file the CCVI sidecar auto-injects and deletes. Use when the user asks to write a seed prompt / hand-off for the next session (or after a /compact), to read/consume the pending one into this session, or to show or clear it.
   ```

   `plugin/skills/cleancode/SKILL.md`:

   ```text
   comments escrow/strip/annotate•naming refactor/propose/apply•conventions export/import/generate•run - post-stabilization code consolidation; escrow then strip construction-era comments, rename per the co-authored naming conventions, re-comment to a high bar, conventions docs loop, full pipeline. Use when the user issues a /cleancode directive; only on a stabilized project with a green verdict.
   ```

   *Why:* the picker window shows the first ~90 chars; verbs-first puts the verb
   inventory there while the model keeps its full trigger prose.
   *Done when:* each file's frontmatter parses (YAML round-trip) and its
   description begins with the bare verb inventory, middots, no spaces, no slash
   command before the first ` - `.

2. **`argument-hints`** - Add an `argument-hint:` line to each SKILL.md frontmatter,
   directly after `description:`:

   - modes: `argument-hint: "[verb] [param]"`
   - plans: `argument-hint: "[verb] [args]"`
   - seedprompt: `argument-hint: "[verb]"`
   - cleancode: `argument-hint: "[noun] [verb] [args]"`

   *Why:* the documented picker-facing slot for argument shapes, keeping them out
   of the description window. *Done when:* all four frontmatters parse and carry
   the field.

3. **`seedprompt-read-verb`** - In `plugin/skills/seedprompt/SKILL.md`:

   - **Invocation table** (anchor: the row `| /seedprompt show |`): insert above it
     `| /seedprompt read | Consume the pending seed: print its path + contents, adopt the body as this session's hand-off brief, then delete it (one-use); or none pending |`
   - **Natural-language line** (anchor: `Recognize natural-language equivalents`):
     add `"read/consume/load the seed" → read`.
   - **Handling a directive, step 2** (anchor: the `**\`show\`**` dispatch bullet):
     insert a `read` bullet before `show`: if the file exists, print absolute path +
     full contents, state that the body is now this session's active hand-off brief
     (directives inert - report `title:` as context, execute nothing), then delete
     the file; else `none pending`.
   - **Echo contract** (anchor: the `**\`show\`**` echo bullet): add
     `**\`read\`**` → the absolute path on its own line, a fenced block of the
     contents, then the line `seed consumed → deleted (one-use)`; or `none pending`.
   - **Help output** (anchor: the `• show` line): insert above it
     `• read         — consume the pending seed: print + adopt it, then delete (one-use)`
     and re-align the column padding of the verb list.
   - **Doctrine updates:** the intro paragraph's sentence `The skill only **writes /
     shows / clears** the seed. It never consumes or deletes on write` becomes
     `The skill **writes / reads / shows / clears** the seed. write never consumes;
     **read is the explicit manual consume path** (print + adopt + delete, the
     equivalent of the sidecar's inject-and-delete); show stays non-destructive.`
     In **The mechanism** (anchor: `reads the file`): update the manual loop
     sentence to name `read` as the one-step form of show-then-clear.

   *Why:* one verb for the manual load-and-burn instead of a two-step show + clear.
   *Done when:* the table, dispatch, echo, help, and both doctrine paragraphs all
   name `read` consistently; frontmatter parses; the help output's version display
   is untouched by hand.

4. **`manifest-read-verb`** - In `build.py` `MANIFEST_SKILLS` (anchor: the
   seedprompt entry's `"verbs"` list), insert `{"name": "read", "params": []}`
   between `write` and `show` (signature order: write, read, show, clear). *Why:*
   manifest.json is the host contract; any verb change lands in the same commit.
   *Done when:* `python3 build.py --check` exits 0 and the emitted manifest lists
   seedprompt's four verbs in that order.

5. **`readme-seedprompt-read`** - In `README.md` (anchor: the seedprompt table
   row): `write`, `show`, `clear` becomes `write`, `read`, `show`, `clear`, with a
   clause noting read consumes (deletes) the pending seed. Grep for any other
   seedprompt verb enumeration. *Done when:* no README line implies seedprompt has
   only three verbs.

6. **`verify-and-release`** - `python3 build.py` then `python3 build.py --check`,
   `python3 test/test_modes.py`, and
   `python3 plugin/skills/cleancode/tools/test_comments.py` all exit 0. Then BBP:
   bump plugin.json patch version, rebuild, commit everything from this plan in one
   commit (message names both slices), push to main. Refresh the installed plugin:
   extract the new zip to `~/.ccvi/ccvi-skills/plugin/` and keep `manifest.json`
   at that root (ccvi-idea's version gate reads it there). *Done when:* all checks
   green, pushed, and the installed `plugin/.claude-plugin/plugin.json` and
   `plugin/manifest.json` both show the new version.

**Escape hatch (binding on every step):** if reality diverges from this plan - a
frontmatter parser rejects `argument-hint` or the middot, the modes harness fails
after a description-only edit, the picker renders differently than assumed - STOP
and surface it; don't improvise.

## Out of scope

- **`when_to_use` frontmatter** - deliberately unadopted until the installed CLI is
  probed to honor it; the trigger prose stays inside `description`.
- **The CCVI card on manual read** - `read` cannot trigger the sidecar's inject
  card today; a future ccvi-idea affordance (a sidecar-exposed consume trigger the
  skill could signal) is the named path. Do not attempt UI from the skill.
- **Verb renames or new verbs beyond `read`** - the four skills' verb surfaces are
  otherwise untouched.
- **Description content for other consumers** - ccvi-idea parses only manifest
  `version` and the plans `verbs:` frontmatter; no host-side changes.
- **The modes LAW blocks and help-output bodies** - untouched (byte-locked /
  stamped).

## Verification

- Picker check (human): typing `/` in a CCVI Claude Code session shows each skill
  row opening with its bare verb inventory; cleancode clips mid-`conventions` as
  accepted; argument hints render.
- Model check: a fresh session's skill listing still carries each skill's "Use
  when..." trigger prose.
- `/seedprompt read` on a pending seed prints path + body, declares the brief
  adopted, and the file is gone afterward; `read` again prints `none pending`;
  `show` remains non-destructive.
- `build.py --check`, `test_modes.py`, `test_comments.py` all exit 0 at the new
  version; installed plugin refreshed.
