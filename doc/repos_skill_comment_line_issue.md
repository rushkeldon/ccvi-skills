# `/repos`: inline comment line numbers are as-of-comment, not as-of-head

Bug report for the `ccvi-skills` repo. Found while preparing the first live `/repos export` on a
two-PR stack. Everything below was probed against a running instance, not inferred.

## Summary

`forge threads` reports each inline comment's line **as it was in the commit the comment was written
against**, not as it is in the PR head. Any commit that changes the line count *above* a comment
silently desyncs the reported line from reality. `export` replays comments to origin using that
number, so it posts them at the wrong line. It also has no notion of an **outdated** comment - one
whose anchored code was itself rewritten - and will replay those as though they still applied.

Both failure modes are silent. Nothing in the current output distinguishes a good line from a stale
one.

## Environment

- Forgejo **16.0.3**, localhost, `disney/android-dmgz`, PR **#1**.
- `forge threads` and `forge comment` via `tools/repos_api.py`.
- Comments were created through the API (`forge comment --line N`), not the web UI. That matters -
  see the note on `position` below.

## Reproduction

PR #1 head is `b17c08bdcf6`. Three unresolved comments exist. Comparing what the tool reports
against what the Forgejo web UI displays:

| comment | `forge threads` says | web UI shows | truth |
|---|---|---|---|
| 31, `RiveAnimation.kt` | line 121 | line 121 | agrees |
| 31's sibling 37, `RiveStateMachineAnimation.kt` | line 199 | line **200** | UI is right |
| 39, `RiveStateMachineAnimation.kt` | line 70 | **not shown** (folded as outdated) | UI is right |

### Root cause of the off-by-one

Comment 31 was posted against commit `952f84248fd`, where its target line was genuinely 199. Then
commit `b17c08bdcf6` landed with `2 insertions(+), 1 deletion(-)` at lines 70-71 of the same file -
a net **+1** above line 199. So the content moved to line 200. The UI re-anchors to head and shows
200; the tool computes from the frozen `diff_hunk` and still says 199.

### Root cause of the missing comment

Comment 39 was anchored to line 70, and `b17c08bdcf6` rewrote exactly that line. Its anchor no
longer exists in that form, so the UI folds it as outdated. `forge threads` still returns it, with
`resolved: false` and `line: 70`, indistinguishable from a healthy comment.

**This case is the dangerous one.** In our repro that comment is also *factually wrong* - it
describes a deletion the same commit reverted. That is not a coincidence: being outdated and being
wrong are the same event. An outdated comment is the single most likely comment to be stale, and it
is precisely the one the UI hides from the human reviewing before export.

## The fields Forgejo actually provides

Full field dump of one comment (`GET /repos/{owner}/{repo}/pulls/{index}/reviews/{id}/comments`):

```
commit_id              = '952f84248fdf7b819c7a0c5899432cd702f74b38'   <- the anchor
position               = 199                                          <- file line IN commit_id
original_commit_id     = ''                                           <- empty, unused
original_position      = 0                                            <- unused
diff_hunk              = '@@ -0,0 +196,4 @@\n+ * The success value…'
extra_lines_count      = 0
resolver               = None                                         <- null while unresolved
path, id, body, user, created_at, updated_at, html_url, pull_request_review_id
```

So Forgejo does **not** expose a head-relative line (no GitHub-style `line` / `original_line`
pair). It gives one anchor: `commit_id` plus `position`. The head-relative line must be computed.

**Note on `position`.** The current skill text says *"the API's `position` is a diff offset, not a
file line (probed v16.0.3), and is used only as a stand-in when the hunk is unparseable."* In this
instance `position` was **199, a true file line**. The likely reason is provenance: these comments
were created via the API with `new_position`, which the skill text elsewhere says accepts true file
lines, and the read side echoes it back. A comment created in the **web UI** may well carry a diff
offset instead. Do not assume either way - treat `position` as trustworthy only when
`diff_hunk` arithmetic agrees with it, and prefer the hunk.

## The fix

The remap is a local git operation, not an API call. `/repos` always runs inside the clone, so this
needs no new capability.

For each comment, given its `commit_id`, its `path`, and its line in that commit:

```
git diff --unified=0 <commit_id> <pr_head> -- <path>
```

Walk the hunk headers `@@ -a,b +c,d @@` in order (omitted counts default to 1), tracking a delta:

| case | test | action |
|---|---|---|
| hunk entirely above the comment | `a + b <= line` | `delta += d - b` |
| comment sits **inside** the hunk | `a <= line < a + b` | mark **outdated**, stop |
| hunk below the comment | otherwise | stop; hunks are ordered |

Then `head_line = line + delta`.

The outdated case falls out of the same arithmetic rather than needing a separate lookup. Do not
attempt a best-effort guess for it - a comment anchored inside a rewritten hunk is genuinely
unresolvable, and guessing would place a stale comment on unrelated code.

### Verified output

Running exactly that algorithm against all three comments reproduces the web UI on every one:

```
PR head = b17c08bdcf6

  RiveAnimation.kt
    anchored at 952f84248fd line 121  ->  head line 121   [unchanged]
  RiveStateMachineAnimation.kt
    anchored at 952f84248fd line 70   ->  head line None  [OUTDATED (anchor rewritten)]
  RiveStateMachineAnimation.kt
    anchored at 952f84248fd line 199  ->  head line 200   [remapped]
```

## What to change

1. **`tools/repos_api.py`, `forge threads`** - add `head_line` and `outdated` to each entry in
   `threads[]`, computed as above. Keep the existing `line` field as-is so nothing that reads it
   breaks; `line` is the as-of-comment value and is still the right thing for a `DELETE` + repost
   round-trip. `head_line` is what a consumer replaying to another host must use.
   The existing helpers named in the skill text are `comment_line` / `line_from_hunk`.
2. **`export`** - use `head_line`, and **refuse to silently replay an outdated comment**. Either
   skip it with a named warning naming path and body first line, or stop and make the user decide.
   Silently posting it is the current behaviour and is the actual defect.
3. **`status`** - surface `outdated` in the export preview. Right now the preview shows
   `path:line - body` and cannot tell the user that one of the comments they are about to ship is
   anchored to code that no longer exists. This is the cheap half of the fix: the human notices
   before the live run rather than after.

### Edge cases the implementation must handle

- **`commit_id` missing from the local clone** (force-push plus gc). Fall back to marking the
  comment outdated rather than guessing.
- **`commit_id == pr_head`** - no diff to walk, `head_line == line`.
- **File renamed between the anchor commit and head.** `git diff -- <path>` with the old path
  returns nothing useful. Either pass `--find-renames` and follow, or mark outdated.
- **Comment on a file deleted at head.** Mark outdated.

## Done when

- `forge threads` on the repro PR reports `head_line: 200` for comment 31's sibling, `head_line:
  121` for the `RiveAnimation.kt` one, and `outdated: true` for comment 39.
- `export … dryRun` on that PR lists two replayable comments and names the third as outdated
  instead of including it silently.
- The skill text's claim that `line` is "the TRUE new-file line" is corrected: it is true relative
  to the comment's own commit, which is what misled a session into reporting 199 as the current
  line.

## Not covered here, but worth its own file

A separate and **higher-severity** defect in the same tool, found in the same session:
`_gh()` calls `subprocess.run(["gh"] + gh_args)` with no `env=`, using host-relative API paths
(`repos/{owner}/{repo}/pulls`). A shell function is not inherited by a subprocess, so this invokes
the real `gh` binary, and with `GH_HOST` unset it defaults to **github.com**. On a machine
authenticated to both github.com and a GitHub Enterprise host, a live export targets the wrong host
under the wrong account. Worse, `--dry-run` makes no `gh` call at all, so a dry run comes back green
regardless. Fix: build an `env` with `GH_HOST` derived from the origin remote's URL and pass it to
`subprocess.run`.
