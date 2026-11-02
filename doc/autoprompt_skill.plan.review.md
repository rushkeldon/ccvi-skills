---
plan: "autoprompt_skill.plan.md"
model: "claude-opus-5"
---
# Review: autoprompt_skill

**Overall: risky** — the shape is right and the rails are unusually good, but three of the
probes it leans on are wrong or fragile on this machine, and two of them fail *silently* in
exactly the canonical case (`/autoprompt android-dmgz`). Fix the four `script-ide` findings
and this is ready.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ⚠️ | two derivations an implementer must invent (target `repoRoot`, "newest record"); one env knob declared only in the tests todo |
| Stale assumptions | ⚠️ | `installedVersion` reads the wrong config dir; `isAndroid`'s only firing signal on `android-dmgz` is a gitignored file; the `numbered` floor depends on a fact ccvi-idea has not promised to write down |
| Cross-surface risk | ✅ | ccvi-idea/ccvi-vscode changes fenced out; writes only `~/.ccvi/autoprompt.json` and the target's git dir; drop stays outside every working tree |
| Rails present | ✅ | anchors are function names, every step has a why and a behavioral done-when, out-of-scope is thorough, escape hatch present |
| TODO hygiene | ⚠️ | atomic, ordered, unique ids; two cross-todo leaks and one done-when that is unsatisfiable until ccvi-idea ships |
| Mechanical lint | ✅ | `plan-check OK — 9 todos; statuses: pending; isProject=false`; all 7 bare fences are closers, every opener tagged; the one hard-coded version is an external, probe-backed floor |

## Findings

**script-ide** `[risky]` — `installedVersion` reads the newest *config* dir, which is not
the one the launched app uses, and the mismatch is live on this machine right now. There
are two Android Studio config dirs: `AndroidStudio2026.1.4` holds `ccvi-idea-0.4.168.jar`
and `AndroidStudio2026.1.1` holds `ccvi-idea-0.4.42.jar`. The plan's "newest dir that has
the jar" happens to pick 2026.1.4 today, but the choice is incidental — a Toolbox install of
a newer major without CCVI, or any ordering change, flips it. The failure is the worst
shape available: 0.4.42 predates the dead drop entirely, so the skill would report a
successful send into a window that will never read the file. The authoritative answer is
already on disk: `/Applications/Android Studio.app/Contents/Resources/product-info.json`
carries `"dataDirectoryName": "AndroidStudio2026.1.4"`, and IntelliJ's carries
`"dataDirectoryName": "IntelliJIdea2026.2"` — the exact config-dir names. ccvi-idea's own
`build.gradle.kts` already reads `product-info.json` for its JCEF check, so this is an
established idiom in the family rather than a new dependency.
Action: in `script-ide`, resolve the config dir from the launched app's
`Contents/Resources/product-info.json` `dataDirectoryName` (falling back to newest-with-jar
only when the plist/JSON is unreadable), and state the probe output in the comment.

**script-ide** `[risky]` — `isAndroid`'s three evidence kinds reduce to one on the canonical
project, and that one is gitignored. On `android-dmgz`:
`app/src/main/AndroidManifest.xml` does not exist; top-level `build.gradle` and
`settings.gradle` both return 0 for `com.android.application|com.android.library|com.android.tools.build:gradle`;
the only hit is `local.properties` with `sdk.dir=`, and `.gitignore:3` lists
`/local.properties` (the file's own header says it must not be checked in). It is present in
all three worktrees today only because Android Studio generated it in each. A fresh clone,
or a `git worktree add` never opened in AS, detects **false** and the skill silently routes
an Android project to IntelliJ. The repo's markers do exist but live deeper than the plan
looks: `libraries/flex/*/build.gradle.kts` at depth 3, and — the robust one —
`com.android.tools.build:gradle` in `buildLogic/gradle/buildLibs.versions.toml`, which is
`git ls-files`-tracked. A depth-2 scan finds nothing, so a shallow fix does not work either.
Action: in `script-ide`, add a bounded recursive rule to `isAndroid` — first hit wins,
short-circuit, skip `build/` and `.gradle/` — over `**/*.gradle`, `**/*.gradle.kts` and
`**/*.versions.toml` to a depth of 4, matching `com.android.application`,
`com.android.library` or `com.android.tools.build:gradle`; keep `local.properties` as the
cheap first check, and state in the plan that it is a fast path, not the evidence.

**script-ide** `[hygiene-issue]` — the capability refusal recommends a remedy that
`chooseIde`'s own precedence makes inert. The message is "set /autoprompt config
idePreferred idea or update it", but `idePreferred` is consulted only at rung 3, and the two
situations that produce a `none` capability both short-circuit above it: an Android project
(rung 2, always `as`) and a live window (rung 1, always that window's editorId). Verified
for the live-window case: both installed ccvi-vscode bundles (`.vscode/…-1.2.33`,
`.cursor/…-1.2.31`) contain no `auto_prompt` string at all, so any live Cursor/VS Code
window refuses — and following the advice changes nothing.
Action: in `script-ide`, make the refusal name the branch it came from and give a remedy
that works for it — for a live incapable window, "close it and reopen the project in
IntelliJ IDEA, or update the extension"; for Android, "update CCVI in Android Studio" (never
`idePreferred`, which Android ignores by design).

**script-ide** `[hygiene-issue]` — `liveWindows`' `siblings` list compares against "the
target's repo root", but the plan never says how to compute it, and the obvious guess is
wrong. `agent_state.repoRoot` is the repository's *main checkout*;
`git -C <dir> rev-parse --show-toplevel` returns the **worktree's** own top level, so for
`android-dmgz-3` it answers `/Users/keldon/Desktop/working/android-dmgz-3` and no sibling
ever matches. The correct derivation is the parent of the common git dir:
`git -C <dir> rev-parse --path-format=absolute --git-common-dir` →
`/Users/keldon/Desktop/working/android-dmgz/.git`, whose dirname is the main checkout.
(Confirmed: `--absolute-git-dir` on that worktree answers
`/Users/keldon/Desktop/working/android-dmgz/.git/worktrees/android-dmgz-3`.)
Action: in `script-ide`, state the `--git-common-dir` command for the target's repoRoot, and
while there say "newest record" means highest `updatedAtMs`.

**script-config** `[risky]` — the path-vs-text classifier misfires on a realistic prompt. The
rule is "one line, ends `.md`, and contains `/` or starts with `~` → a path", which
classifies *`fix the typo in doc/contracts/auto_prompt.md`* as a path, fails the existence
check, and refuses the send. A prompt naming a markdown file at the end of the sentence is
an ordinary thing for an agent to write, and the refusal text ("no such file: fix the typo
in …") will read as a bug rather than a classification.
Action: in `script-config`, add "and contains no whitespace" to the path test — a path
argument is a single token — and add that case to the `tests` intake list.

**skill-md** `[hygiene-issue]` — two gaps in the argument spec. The last-token
`shouldStartIDE` rule can swallow a word from the prompt: `/autoprompt android-dmgz 'ship it
or no'` ends in `no` after quote-stripping. And `allowed-tools` is listed as a frontmatter
field to fill without saying what goes in it, which an implementer must then guess (`repos`
uses `Read, Write, Edit, Glob, Grep, Bash`; this skill needs at minimum `Bash` for the
script).
Action: in `skill-md`, scope the flag parse to tokens **outside** the quoted prompt, and
name the `allowed-tools` value explicitly.

**gate-consumers** `[hygiene-issue]` — the probe's rung 1 depends on a fact the other side
has not agreed to write. It says to read `../ccvi-idea/doc/contracts/auto_prompt.md` and
take "the first version that consumes them", but ccvi-idea's
`doc/auto_prompt_numbered_file_queue.plan.md` does not put that version in the contract: its
`contract-doc` step lists the slot scheme, the regex, the ordering guarantees and the
Authorization entry, and the version appears only in `ship-and-notify`, as a message to this
session. A message is not a durable source a later probe can re-read.
Action: in `gate-consumers`, make the authoritative source explicit — ask the ccvi-idea side
to state the first numbered-consuming version in the contract (one line in "Changing this
contract" is enough) — and until it is there, leave `numbered` at `None` rather than
inferring it from a commit or a chat message.

**script-drop** `[hygiene-issue]` — the done-when cannot be met as written until ccvi-idea
ships. "Two concurrent `send`s into one capability-`numbered` target produce two distinct
slots" requires a `numbered` floor, which `gate-consumers` will correctly leave at `None`
(ccvi-idea's own plan is not yet built). An implementer reading this literally blocks.
Action: in `script-drop`, say the numbered half of the done-when is satisfied by the
`AUTOPROMPT_FLOORS_JSON` test override until a real numbered consumer exists, and keep the
live half (`single`, bare slot, occupied-slot refusal) as the behavioral check.

**script-drop** `[hygiene-issue]` — two smaller things in the same step. `clear` renames into
`~/.Trash/…` unconditionally, which does not exist on Linux (ccvi-idea's own `trashFile` has
an XDG branch precisely for this), while the out-of-scope fence covers only *launch* as
macOS-only. And the snippet writes `gitDir / "ccvi"`, treating a `git rev-parse` string as a
`Path`.
Action: in `script-drop`, fence `clear`'s Trash path to macOS with a stated fallback (or add
`clear` to the macOS-only note), and make `gitDir` a `Path` where it is first resolved.

**tests** `[hygiene-issue]` — `AUTOPROMPT_FLOORS_JSON` is introduced only here ("patch
`FLOORS` via an env override the script honors for tests"), but it has to be *implemented* in
`gate-consumers`/`script-ide`. An implementer working the todos in order writes no such
override, then hits an unbuildable test todo.
Action: move the `AUTOPROMPT_FLOORS_JSON` requirement into `gate-consumers` beside the
`FLOORS` table (and keep the reference in `tests`), the same way `AUTOPROMPT_NO_LAUNCH` is
already declared in `script-ide` where it is implemented.

**repo-wiring** `[hygiene-issue]` — one ordering hazard and one inherited staleness.
`build.py`'s `stamp()` raises `SystemExit` when a STAMPS pattern finds **no** match, so
adding the `/autoprompt · v\d+\.\d+\.\d+` entry before `SKILL.md` carries that display
breaks every `build.py` run, including `--check`. The plan's todo order is already right
(`skill-md` precedes `repo-wiring`) but nothing says why it must stay that way. Separately,
the `## Layout` block in CLAUDE.md already omits `cleancode` and `repos`; adding only
`autoprompt` to it leaves a block that is more misleading than before.
Action: in `repo-wiring`, note that the STAMPS entry must land only after the SKILL.md
display exists (`stamp()` hard-fails otherwise), and either add the two missing skill lines
to the Layout block in the same edit or say in one line that the block stays partial.

**Clean, no action:** `script-config` (config file, resolution ladder, `..` and containment
rules), `live-smoke`, `bbpi` — the BBPI sequence matches the repo's own ritual, including
`git add -A` at the push step and the `unzip -o -q` install.

## Notes that are not findings

- **The new-skill decision is doctrinally sound.** CLAUDE.md's "one skill per noun" plus its
  corollary ("verbs that share an invariant belong on one skill") supports a separate
  `autoprompt` rather than folding these verbs into `repos` or `modes`.
- **`0.4.168` as the `single` floor is correct and probe-backed.** Both installed plugins are
  exactly `ccvi-idea-0.4.168.jar`, and ccvi-idea's git history puts the git-dir move
  (`0444b2f`) after the 0.4.167 bump and before `4f33995 BBP 0.4.168`, so 0.4.168 is the
  first version reading `<gitDir>/ccvi/`. This is an external product's released version,
  not a "bump to" target, so it does not trip the no-hard-coded-versions rule.
- **The ccvi-vscode `None` floors are accurate as stated.** `grep -rcF auto_prompt` over the
  installed `1.2.33` and `1.2.31` bundles returns nothing, matching the plan's claim.
- **Report naming.** This report follows the repo's existing convention
  (`cleancode_skill.plan.review.md`, `repos_sync_verb.plan.review.md`), hence
  `autoprompt_skill.plan.review.md`.
