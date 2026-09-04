---
name: /repos head-line remap for inline comments
overview: "forge threads reports each inline comment's line as-of its anchor commit, not as-of the PR head, and export replays outdated comments silently. Add a git-diff remap (head_line + outdated) to threads, make export and status honor it, and correct the skill text's line-semantics claims."
version: "1.0"
todos:
  - id: remap-helper
    content: "Add pure remap_line(line, diff_text) -> (head_line, outdated) to tools/repos_api.py, walking @@ hunk headers with the a + max(b,1) <= line above-test"
    status: completed
  - id: threads-fields
    content: "forge_threads: fetch the PR head sha and emit head_line + outdated on every threads[] entry, keeping line as-is"
    status: completed
  - id: export-refusal
    content: "Export path: SKILL.md workflow builds the comments JSON from head_line and excludes outdated entries with a named warning; github_export refuses any entry carrying outdated: true"
    status: completed
  - id: status-preview
    content: "SKILL.md status verb: surface outdated in the export preview lines"
    status: completed
  - id: skill-text-corrections
    content: "Correct the line-semantics claims: SKILL.md threads JSON example + 'TRUE new-file line' paragraph, and the comment_line docstring in repos_api.py"
    status: completed
  - id: selftests
    content: "Extend selftest() with remap_line cases: unchanged, remapped, outdated, pure-insertion boundary, deletion shift, unparseable diff"
    status: completed
isProject: false
---

# /repos head-line remap for inline comments

## Problem / Context

`forge threads` in [tools/repos_api.py](../plugin/skills/repos/tools/repos_api.py) reports each
inline comment's line **as it was in the commit the comment was written against** (derived from
the frozen `diff_hunk` by `comment_line`/`line_from_hunk`), not as it is in the PR head. Any
commit that changes the line count above a comment silently desyncs the reported line, and
`export` replays comments to origin at that stale number. There is also no notion of an
**outdated** comment - one whose anchored code was itself rewritten - and export replays those
as though they still applied. Both failures are silent.

Probed on Forgejo 16.0.3 (`disney/android-dmgz` PR #1, head `b17c08bdcf6`): one comment agreed
with the web UI (line 121), one was off by one (tool said 199, UI says 200 after a +1 commit
above it), one was folded by the UI as outdated (anchor line 70 rewritten) yet returned by the
tool as a healthy unresolved comment. Full evidence:
[repos_skill_comment_line_issue.md](repos_skill_comment_line_issue.md) (may since be archived to
[archive/](archive/)).

Forgejo exposes no head-relative line (no GitHub-style `line`/`original_line` pair) - only
`commit_id` plus `position`/`diff_hunk`. The head-relative line must be computed locally, and
`/repos` always runs inside the clone, so a plain `git diff` suffices; no new capability.

## Approach

Add a **pure** remap function over unified-diff text, call it from `forge_threads` with the
output of `git diff --unified=0 <commit_id> <head_sha> -- <path>`, and emit two additive fields
per thread entry: `head_line` (int or null) and `outdated` (bool). The existing `line` field is
untouched - it is the as-of-comment value and remains correct for the DELETE + repost amend
path. Consumers that replay to another host use `head_line`.

The export workflow (SKILL.md prose) then builds its comments JSON from `head_line` and drops
outdated entries with a named warning; `github_export` gains a belt-and-braces refusal.
`status` shows the outdated flag in its preview so the human sees it before a live run.

## Conventions & assumptions

- 2-space indentation, matching the existing file style in `repos_api.py`.
- All edits live in the **repo working tree** (`plugin/skills/repos/...`), never in the
  installed copy under `~/.ccvi/` - BBP's install step propagates.
- `forge threads` is invoked from inside the PR's clone (the skill's standing assumption); the
  new git calls use the process cwd. Assumes the clone has the PR branch fetched - if
  `commit_id` is unreachable the remap degrades to `outdated` rather than failing.
- Probed field semantics (do not re-derive): read-side `position` may be a diff offset OR a
  true file line depending on provenance (web UI vs API-written via `new_position`); the hunk
  arithmetic in `comment_line` stays authoritative and `position` stays a last-resort stand-in.
- `manifest.json` / `MANIFEST_SKILLS` need **no** change: no verb or param is added or renamed,
  only output fields.
- Pure-insertion hunks: git's `@@ -a,0 +c,d @@` means "inserted after old line a"; old line `a`
  itself does NOT move. This is why the above-test is `a + max(b, 1) <= line`, not
  `a + b <= line` - the naive form shifts a comment sitting exactly on the insertion anchor.

## The steps

### 1. `remap-helper` - the pure remap function

In [tools/repos_api.py](../plugin/skills/repos/tools/repos_api.py), directly after
`comment_line` (anchor: the `# --------- github side` separator comment follows it), add:

```python
def remap_line(line, diff_text):
  """Map a file line in the diff's OLD side to the NEW side.

  Walks the @@ -a,b +c,d @@ hunk headers of a --unified=0 diff, accumulating
  the net delta of hunks strictly above `line`. A hunk that CONTAINS the line
  (a <= line < a + b) means the anchored code was rewritten: outdated.
  Pure-insertion hunks (b == 0) insert AFTER old line a, so line == a does not
  move - hence max(b, 1) in the above-test. Returns (head_line, outdated);
  outdated=True carries head_line=None.
  """
  delta = 0
  for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
                       diff_text, re.MULTILINE):
    a = int(m.group(1))
    b = 1 if m.group(2) is None else int(m.group(2))
    d = 1 if m.group(4) is None else int(m.group(4))
    if a + max(b, 1) <= line:
      delta += d - b
    elif a <= line < a + b:
      return (None, True)
    else:
      break
  return (line + delta, False)
```

Add `import re` to the file's imports if not already present. **Why:** keeping the arithmetic
pure (text in, tuple out) lets `selftest` pin it without git or a live forge.

**Done-when:** `remap_line(199, "@@ -70,1 +70,2 @@\n...")` returns `(200, False)`;
`remap_line(70, same)` returns `(None, True)`; `remap_line(70, "@@ -70,0 +71,2 @@")` returns
`(70, False)` (the pure-insertion boundary).

### 2. `threads-fields` - wire it into `forge_threads`

In `forge_threads` (anchor: the loop appending to `out` with `"line": line`):

- Before the review loop, fetch the head sha once:
  `head_sha = (_forge("GET", "/repos/{}/{}/pulls/{}".format(owner, name, args.pr)) or {}).get("head", {}).get("sha", "")`.
- Per comment, compute `head_line`/`outdated` via a small helper that shells out
  (`subprocess.run`, already imported) and applies the edge-case ladder, in this order:
  1. `commit_id` empty or `head_sha` empty → `outdated = True` (no basis to remap).
  2. `commit_id == head_sha` → `head_line = line`, `outdated = False` (no diff to walk).
  3. `git cat-file -e <commit_id>` fails (anchor commit missing locally - force-push + gc) →
     `outdated = True`. Never guess.
  4. `git cat-file -e <head_sha>:<path>` fails (file renamed or deleted at head) →
     `outdated = True`. One rule covers both; do not chase renames.
  5. Else run `git diff --unified=0 <commit_id> <head_sha> -- <path>` and feed its stdout to
     `remap_line(line, diff_text)`.
  A failing git invocation at step 5 (non-zero exit) → `outdated = True`, never a crash.
- Append `"head_line": head_line, "outdated": outdated` to each entry dict, leaving every
  existing key untouched.

**Why:** `head_line` is the only value a consumer replaying to another host may use; `line`
stays for the delete-then-repost amend path. **Done-when:** on the repro PR, `forge threads`
reports `head_line: 121` (RiveAnimation.kt), `head_line: 200` (the line-199 comment), and
`outdated: true, head_line: null` (the line-70 comment) - matching the Forgejo web UI on all
three.

### 3. `export-refusal` - export uses head_line and refuses outdated

Two layers, both in the same commit:

- **SKILL.md export workflow** ([SKILL.md](../plugin/skills/repos/SKILL.md), Verb: export
  section - anchor: the prose describing how the comments JSON is assembled from unresolved
  `threads[]` entries): state that each replayed entry's `line` value in the comments JSON is
  the thread's **`head_line`**, and that any entry with `outdated: true` is **excluded** from
  the JSON, with a warning printed per exclusion naming its `path` and the first line of its
  `body`. The user sees the exclusions before the live call and can resolve or reword those
  comments on the forge first.
- **`github_export`** (anchor: the `review_comments = [...]` list comprehension): before
  building `review_comments`, fail via `_die` if any entry in the loaded JSON carries
  `outdated` truthy - message: `"comments file contains outdated entries"`, detail naming the
  paths. This is belt-and-braces: the workflow should never hand them over, but a hand-built
  comments file must not slip through either.

**Why:** silently posting a comment anchored to rewritten code is the actual defect - an
outdated comment is the one most likely to be factually wrong. **Done-when:**
`export ... --dry-run` on the repro PR lists exactly two `pending_review_comments` (at lines
121 and 200) and the workflow output names the third as excluded-outdated; feeding a JSON
containing `"outdated": true` to `github_export` dies before any `gh` call.

### 4. `status-preview` - surface outdated in the preview

In SKILL.md's Verb: status section (anchor: the export-preview description showing
`path:line - body`): the preview line for an outdated thread renders with an explicit marker,
e.g. `path:OUTDATED - body` or a trailing `[OUTDATED - will be excluded from export]`, and the
preview's summary counts replayable vs outdated. Pick the phrasing that matches the section's
existing preview format - the requirement is only that an outdated comment is visibly flagged
and stated to be excluded from export.

**Why:** the cheap half of the fix - the human notices before the live run. **Done-when:**
`/repos status` on the repro PR shows two replayable comments and one flagged outdated.

### 5. `skill-text-corrections` - fix the line-semantics claims

Three places, same commit:

- **SKILL.md threads JSON example** (anchor: the fenced block whose entry reads
  `"line": 2`): add `"head_line": 2, "outdated": false` to the example entry.
- **SKILL.md prose below the example** (anchor: the paragraph beginning
  `` `line` is the TRUE new-file line ``): rewrite to state that `line` is the new-file line
  **as of the comment's own anchor commit** (`commit_id`) - still the right value for the
  DELETE + repost amend path - while `head_line` is the line re-anchored to the current PR
  head (`null` when `outdated: true`, meaning the anchored code was itself rewritten), and
  that export consumers keep unresolved entries and replay by `head_line`, never `line`.
  Keep the existing probed note that `position` is only a stand-in, and extend it with the
  provenance caveat: API-written comments echo `new_position` back as a true file line, so
  `position`'s meaning varies by provenance; the hunk arithmetic stays authoritative.
- **`comment_line` docstring** in repos_api.py: change the first line from
  `"True new-file line for a read-side comment."` to
  `"New-file line for a read-side comment, as of the comment's OWN anchor commit (commit_id) - NOT the PR head; remap_line maps it to head."`
  and append the provenance caveat sentence. Keep the probed measurements already there.

**Why:** the "TRUE new-file line" wording is what misled a session into reporting 199 as the
current line; prose and behavior may not drift. **Done-when:** grep for `TRUE new-file line`
returns nothing in the repo; the example block and prose mention `head_line` and `outdated`.

### 6. `selftests` - pin the remap

In `selftest()` (anchor: the `cl_cases` tuple list), add a `remap_cases` table exercising
`remap_line` and assert each, following the existing name/expected tuple style:

```python
remap_cases = [
  # (name, line, diff_text, expected)
  ("no hunks - unchanged",        121, "",                              (121, False)),
  ("insertion above shifts",      199, "@@ -70,1 +70,2 @@\n-x\n+y\n+z", (200, False)),
  ("anchor inside hunk",          70,  "@@ -70,1 +70,2 @@\n-x\n+y\n+z", (None, True)),
  ("pure-insert at anchor line",  70,  "@@ -70,0 +71,2 @@\n+y\n+z",     (70, False)),
  ("pure-insert line below it",   71,  "@@ -70,0 +71,2 @@\n+y\n+z",     (73, False)),
  ("deletion above shifts down",  199, "@@ -100,3 +99,0 @@\n-a\n-b\n-c",(196, False)),
  ("inside deleted range",        101, "@@ -100,3 +99,0 @@\n-a\n-b\n-c",(None, True)),
  ("hunk below - stops",          50,  "@@ -70,1 +70,2 @@\n-x\n+y\n+z", (50, False)),
]
```

**Why:** the repro PR's live state will not survive merges or a forge reset; the selftest is
the durable guard, and it specifically pins the pure-insertion boundary the naive arithmetic
gets wrong. **Done-when:** `python3 plugin/skills/repos/tools/repos_api.py selftest` exits 0
with the new cases counted in its output.

## Out of scope

- **The `_gh()` / `GH_HOST` defect** (subprocess inherits no shell function; unset `GH_HOST`
  targets github.com; `--dry-run` masks it). Real and higher-severity, but it gets its own
  plan - do not touch `_gh` here beyond what step 3 requires.
- **Resolved comments** - the remap runs for every thread entry uniformly, but no behavior
  change for resolved ones; export already excludes them.
- **Rename-following** (`--find-renames`) - deliberately not implemented; a rename marks the
  comment outdated (step 2's ladder). Revisit only if it bites in practice.
- **Amending comments on the forge** - the DELETE + repost path is unchanged; that is why
  `line` keeps its as-of-comment semantics.
- **`manifest.json`** - no verb/param change, so no manifest edit.

## Verification

1. `python3 plugin/skills/repos/tools/repos_api.py selftest` exits 0, new remap cases included.
2. Against the live repro (`disney/android-dmgz` PR #1, if still standing): `forge threads`
   matches the web UI on all three comments (121 / 200 / outdated); `export ... --dry-run`
   lists two comments and the workflow names the excluded one.
3. `grep -rn "TRUE new-file line" plugin/` returns nothing.
4. `python3 build.py --check` and `python3 test/test_modes.py` exit 0 (nothing here touches
   modes or the manifest, so both must stay green).
5. If reality diverges from any anchor named above - a symbol moved, a section reworded -
   STOP and surface it; do not improvise.
