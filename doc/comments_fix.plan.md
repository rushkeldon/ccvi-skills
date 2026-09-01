---
humanEngineerDifficulty: 2
name: repos comments fix - true file lines + amend-path docs
version: "1.0"
overview: "Fix forge threads reporting a diff offset as `line` (export would misplace comments on GitHub), and document that inline comments cannot be edited - delete-then-repost is the only amend path."
todos:
  - id: comment-line-helper
    content: "repos_api.py: add pure helper comment_line(position, diff_hunk) preferring hunk arithmetic over position; use it in forge_threads"
    status: completed
  - id: selftest-cases
    content: "repos_api.py selftest: add comment_line cases - hunk wins over position, position-only fallback, neither -> 0"
    status: completed
  - id: skillmd-line-doc
    content: "repos SKILL.md: correct the `line` derivation sentence under the forge threads output shape"
    status: completed
  - id: skillmd-amend-note
    content: "repos SKILL.md review verb: add the no-edit-path note (delete-then-repost; PATCH impossible regardless of token scope)"
    status: completed
  - id: bbpi
    content: "Run BBPI: bump plugin.json patch version, python3 build.py, verify --check and test_modes.py green, commit+push, unzip into ~/.ccvi"
    status: in_progress
isProject: false
---

# repos comments fix - true file lines + amend-path docs

## Problem / Context

A live probe against Forgejo v16.0.3 (2026-09-01, real PR with inline review comments
on a wholly-new file) established two facts about the forge API that the `/repos` skill
currently gets wrong or leaves undocumented:

1. **Read-side `position` is a diff offset, not a file line.** Two probed comments
   reported `position` 157 and 65 while their `diff_hunk` headers (`@@ -0,0 +202,4 @@`,
   `@@ -0,0 +67,4 @@`) show the true anchors at file lines 205 and 70. Yet
   `forge_threads` in
   [repos_api.py](../plugin/skills/repos/tools/repos_api.py) does
   `line = c.get("position") or 0` and only falls back to `line_from_hunk()` when
   `position` is absent - the priority is exactly backwards. The comments are anchored
   correctly on the forge; the damage is downstream: `github export` replays each
   unresolved comment to GitHub as `path` + `line` using that number, so exported
   comments would land on the wrong lines, and `/repos status`'s export preview
   misreports them the same way. SKILL.md line ~146 codifies the wrong preference in
   prose.
2. **Inline review comments cannot be edited, period.** The instance's swagger gives
   review comments only GET/POST/DELETE - no PATCH (issue comments have PATCH, but a
   cross-use attempt 403s on a `write:issue` scope `init` doesn't provision, so scope
   changes buy nothing). DELETE works (probed, HTTP 204). The only amend path is
   delete-then-repost, and the skill documents neither the limitation nor the route.

Decided with the user: fix the bug and add the prose notes; a `forge comment --replace`
subverb was considered and rejected for now (it cannot preserve the comment id anyway,
adds partial-failure surface, and prose makes the manual route discoverable).

## Approach

Invert the line-derivation priority behind a small pure function so it lands in the
existing hermetic `selftest` alongside `line_from_hunk` and `credential_next_action`,
then align the two SKILL.md passages with reality. No skill verb or param changes, so
`manifest.json` and `MANIFEST_SKILLS` in build.py are untouched. Close with the repo's
standard BBPI ritual.

## Conventions & assumptions

- 2-space indentation, zero-dependency python3, matching the file's existing style.
- `selftest` is the verification vehicle - hermetic, no network; follow the existing
  tuple-table case pattern.
- Assumes `line_from_hunk`'s "anchor = the hunk's final line" rule is correct for
  Forgejo's `diff_hunk` payloads; the probe above confirmed it on two real comments
  (205 and 70 both derived correctly). If a future payload breaks it, that is a new
  probe-and-fix, out of this plan's scope.
- Assumes write-side `new_position` (in `forge_comment` and Forgejo PR review POSTs)
  accepts true file lines - probed: reposted comments anchored correctly. The
  read/write unit asymmetry is the trap that caused this bug; record it in the helper's
  docstring so it survives.
- The two SKILL.md edits are documentation prose; keep the file's hyphen-not-em-dash
  style and tag any new code fence.

## The steps

### 1. Add `comment_line` and use it in `forge_threads` (todo: comment-line-helper)

In [repos_api.py](../plugin/skills/repos/tools/repos_api.py), in the
"diff-hunk arithmetic" section beside `line_from_hunk`, add a pure helper:

```python
def comment_line(position, diff_hunk):
  """True new-file line for a read-side comment.

  Forgejo's read-side `position` is a DIFF OFFSET, not a file line (probed
  2026-09-01, v16.0.3: position 157/65 vs true lines 205/70), so hunk
  arithmetic is authoritative and `position` is only a last-resort stand-in
  when the hunk is unparseable. Write-side `new_position` is the opposite -
  it accepts true file lines (probed: reposts anchored correctly).
  """
  line = line_from_hunk(diff_hunk or "")
  return line if line else (position or 0)
```

In `forge_threads`, replace the three lines

```python
      line = c.get("position") or 0
      if not line:
        line = line_from_hunk(c.get("diff_hunk", ""))
```

with

```python
      line = comment_line(c.get("position"), c.get("diff_hunk"))
```

Why: `line` feeds `github export` and the `status` preview verbatim; it must be a file
line. Done-when: `python3 plugin/skills/repos/tools/repos_api.py selftest` still exits 0
and `forge_threads` contains no direct `position` read.

### 2. Selftest cases for the priority (todo: selftest-cases)

In `selftest`, after the `na_cases` block, add a `cl_cases` tuple table exercising
`comment_line` and loop it into `failures` like the others:

```python
  cl_cases = [
    # (name, position, diff_hunk, expected)
    ("hunk wins over position", 157, "@@ -0,0 +202,4 @@\n+a\n+b\n+c\n+d", 205),
    ("position-only fallback",  65,  "not a hunk", 65),
    ("neither",                 None, "", 0),
    ("position None, hunk ok",  None, "@@ -0,0 +1,2 @@\n+a\n+b", 2),
  ]
  for name, position, hunk, expected in cl_cases:
    got = comment_line(position, hunk)
    if got != expected:
      failures.append({"case": name, "expected": expected, "got": got})
```

The first case is the probe's own evidence, immortalized. Update the final `cases`
count expression to include `len(cl_cases)`. Why: the inversion is the whole bug; a
regression flipping it back must fail loudly. Done-when: selftest exits 0 and prints a
case count that includes the new cases; temporarily swapping the helper's preference
order makes it fail (spot-check, then restore).

### 3. Correct the SKILL.md derivation sentence (todo: skillmd-line-doc)

In [SKILL.md](../plugin/skills/repos/SKILL.md), under "**`forge threads` output
shape**", replace the sentence starting `` `line` prefers the API's `position`; ``
(unique anchor) with:

```text
`line` is the TRUE new-file line, derived from the comment's `diff_hunk` by
`@@`-header arithmetic (`comment_line`/`line_from_hunk`, covered by `selftest`);
the API's `position` is a diff offset, not a file line (probed v16.0.3), and is
used only as a stand-in when the hunk is unparseable.
```

Keep the following `resolved` sentence untouched. Done-when: the string "prefers the
API's `position`" no longer appears in the repo.

### 4. Document the amend path (todo: skillmd-amend-note)

In SKILL.md's `## Verb: review` bullet list, insert a bullet immediately after the
"**Each finding = one root inline comment**" bullet (stable anchor: that bolded
phrase):

```text
- **Posted comments cannot be edited - the forge API has no PATCH for review
  comments (regardless of token scope; probed v16.0.3). To amend one:
  DELETE `/repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments/{comment}`
  (works with the provisioned scopes), then repost via `forge comment`. The
  comment id changes; the thread's resolved state starts over.**
```

(Bold the lead phrase only if it matches the list's emphasis style on final read;
content over formatting.) Why: an agent hitting a wrong comment today has no documented
route and may try scope changes that cannot work. Done-when: the review verb section
names delete-then-repost and states PATCH is impossible at the API level.

### 5. BBPI (todo: bbpi)

The repo's standard ritual per CLAUDE.md: bump the patch segment in
`plugin/.claude-plugin/plugin.json` (to the next version - no hard-coded number here),
run `python3 build.py`, then verify `python3 build.py --check` and
`python3 test/test_modes.py` both exit 0; `git add -A`, commit describing the fix (not
just "bump"), push to `main`; `unzip -o -q ccvi-skills.zip -d
~/.ccvi/ccvi-skills/plugin/` and confirm the installed plugin.json shows the new
version. Done-when: all four legs done, both checks green, installed version matches.

## Out of scope

- **No `forge comment --replace` subverb** - explicitly decided against for now; the
  trigger to revisit is replacement becoming a recurring move (e.g. a review
  self-correction pass).
- **No `init` step 6 scope changes** - `write:issue` buys nothing (review comments have
  no PATCH endpoint at all).
- **No manifest/MANIFEST_SKILLS edits** - no verb or param changed.
- **No touching `forge_comment`'s write path** - `new_position` with file lines is
  probed-correct; leave it.
- **No changes to `line_from_hunk` itself** - its arithmetic is probed-correct and
  selftested.

## Verification

`python3 plugin/skills/repos/tools/repos_api.py selftest` exits 0 with the enlarged
case count; `python3 build.py --check` and `python3 test/test_modes.py` exit 0 after
the build; grep confirms the old "prefers the API's `position`" prose is gone and the
review verb documents delete-then-repost. If reality diverges from any anchor or probe
claim above, STOP and surface - don't improvise.
