---
humanEngineerDifficulty: 6
name: autoprompt_skill
version: "1.0"
overview: "Add /autoprompt, a standalone ccvi-skills skill that writes a numbered CCVI auto-prompt dead drop into another project's per-worktree git dir and, unless told not to, opens that project in the right IDE (Android Studio for Android, else a configured preference) so the CCVI sidecar there consumes the drop as its next turn. Verbs send (default), show, clear, config; a Python fast-path script does the work."
todos:
  - id: gate-consumers
    content: "Probe ccvi-idea and ccvi-vscode for the numbered-drop consumer and pin the per-editor version floors in autoprompt.py's FLOORS table"
    status: completed
    phase: "Gate"
  - id: script-config
    content: "Create plugin/skills/autoprompt/scripts/autoprompt.py with argument parsing, ~/.ccvi/autoprompt.json config, and projectDir resolution"
    status: completed
    phase: "Script"
  - id: script-ide
    content: "Add agent_state matching, Android detection, IDE choice, consumer-version lookup, and open -a launch to autoprompt.py"
    status: completed
    phase: "Script"
  - id: script-drop
    content: "Add the no-replace numbered drop writer plus the show and clear verbs to autoprompt.py"
    status: completed
    phase: "Script"
  - id: skill-md
    content: "Author plugin/skills/autoprompt/SKILL.md - frontmatter verbs schema, dispatch, prompt sourcing, echo, help output"
    status: completed
    phase: "Skill"
  - id: repo-wiring
    content: "Wire the skill into build.py (MANIFEST_SKILLS, STAMPS), README.md's skills table, and CLAUDE.md's layout block"
    status: completed
    phase: "Skill"
  - id: tests
    content: "Write test/test_autoprompt.py covering resolution, config, IDE choice, the slot writer race, show, and clear against a fake HOME"
    status: completed
    phase: "Verify"
  - id: live-smoke
    content: "Run a real send into this repo's own live CCVI window with shouldStartIDE false and confirm the turn arrives and the drop is consumed"
    status: completed
    phase: "Verify"
  - id: bbpi
    content: "BBPI per CLAUDE.md - bump, build, check, test, commit and push, install - and confirm /autoprompt registers"
    status: completed
    phase: "Verify"
isProject: false
---

# autoprompt_skill

## Problem / Context

An agent working in one repo has no way to hand work to an agent in a different repo. CCVI
already has the receiving half: the **auto-prompt dead drop**. A file dropped at
`$(git -C <repo> rev-parse --absolute-git-dir)/ccvi/auto_prompt.md` is picked up within about
3 seconds by the CCVI sidecar of the window open on that worktree and sent as a CCVI-attributed
turn. The contract is `../ccvi-idea/doc/contracts/auto_prompt.md`; the window liveness signal
is `../ccvi-idea/doc/contracts/agent_state.md`.

Two things are missing, and this skill supplies the ccvi-skills half of both:

1. **A reliable writer** - path resolution, an atomic no-clobber write, and (new) more than one
   waiting prompt per worktree.
2. **Getting a window open.** The drop never opens a window; an unopened repo's drop waits
   forever. The skill opens the right IDE on the project when no live window is there.

The usual call is `/autoprompt android-dmgz`.

## Approach

One standalone skill, `autoprompt`, under the repo's one-skill-per-noun rule:

```text
/autoprompt send {projectDir} [prompt] [shouldStartIDE]
/autoprompt show [projectDir]
/autoprompt clear {projectDir}
/autoprompt config [key] [value]
```

`send` is the default verb: when the first argument is not one of `send`, `show`, `clear`,
`config`, the directive is read as `send` with that argument as `projectDir`. A project whose
name is literally a verb needs the explicit `send`.

All bookkeeping lives in one fast-path script,
[autoprompt.py](../plugin/skills/autoprompt/scripts/autoprompt.py), mirroring how
[modes.py](../plugin/skills/modes/scripts/modes.py) carries `/modes`. The SKILL.md body owns
only what needs the model: authoring the prompt from the conversation when none is given, and
relaying the script's report.

### The cross-repo contract this skill writes against (ccvi-idea builds the consumer)

ccvi-idea agreed to this design on 2026-11-01 and builds its side from
`../ccvi-idea/doc/auto_prompt_numbered_file_queue.plan.md`, whose regex, slot rules, and writer
recipe this section matches.
**The numbered consumer does not exist yet** in the installed ccvi-idea 0.4.168; the skill
degrades to the single fixed slot until it does (see `gate-consumers`).

- **Directory:** `$(git -C <target> rev-parse --absolute-git-dir)/ccvi/` - the PER-WORKTREE git
  dir, never `--git-common-dir`. That is what addresses exactly one window.
- **Slots:** `auto_prompt.md` is slot 0 (unchanged, so dpp and other existing writers keep
  working), then `auto_prompt_<N>.md` for N >= 1, unpadded. Match regex
  `^auto_prompt(_[1-9][0-9]*)?\.md$`; sort by parsed integer, bare = 0. The `\.md$` anchor
  excludes the consumer's in-flight `*.md.claimed-<pid>` names.
- **Consumer (ccvi-idea's side):** each tick, drain lowest-first up to 20 files, claiming each by
  rename as today, one `send()` and one CCVI-attributed turn per file. Draining in one tick keeps
  a batch in one window when two windows share a worktree.
- **Writer (this skill):** per-writer temp name in the same dir; create the slot with a
  no-replace primitive; rescan on collision; bare name only when the dir holds no slot at all.
  Detail in `script-drop`.
- **Old consumers** (<= 0.4.168) read only the bare name and never list the dir, so a numbered
  file sits unread forever. The skill therefore never writes a numbered slot unless the target
  editor's installed CCVI is at or above the numbered floor.

## Conventions & assumptions

- **Language and style:** Python 3.9+ stdlib only, matching [modes.py](../plugin/skills/modes/scripts/modes.py)
  - its indentation, its module-docstring contract header, plain `print` output. The skills may
  assume `python3` (repo CLAUDE.md).
- **Naming** follows the global conventions: booleans `is`/`has`/`should`; the common part of a
  name goes left (`idePreferred`, `ideChosen`). Params are literally `projectDir`,
  `prompt`, `shouldStartIDE`, `key`, `value`.
- **Humans and agents both call this skill** - it always runs inside some agent's session. An
  omitted `prompt` means the agent running the skill authors it, whoever invoked it.
- **editorId vocabulary is agent_state's own:** `as`, `idea`, `vscode`, `cursor`. Never invent
  another spelling.
- **App names for `open -a`:** `as` -> `Android Studio`, `idea` -> `IntelliJ IDEA`, `vscode` ->
  `Visual Studio Code`, `cursor` -> `Cursor`. Always `open -a "<App>" "<dir>"`, **never `-n`**
  (JetBrains IDEs are single-instance; plain `open -a` opens a new window in the running
  instance, or launches it). Not the Toolbox `idea`/`studio` scripts: agent shells often lack
  them on PATH.
- **Write the drop BEFORE launching.** A drop waits indefinitely, so there is no race to lose;
  CCVI's project-open activity spawns the sidecar within indexing-or-15 s and the next tick
  consumes it.
- **Busy targets are sent to anyway** (Keldon, 2026-11-01): a live window reading `mid-turn` or
  `human-driven` still gets the drop; it queues like a typed prompt. The report names the state.
- **Launch default is true** (Keldon's request, 2026-11-01). Assumes launching from a skill the
  user or an agent invoked is acceptable on this machine; recording that in ccvi-idea's
  contract is ccvi-idea's business, not a step here. If Keldon reverses it, only the
  `shouldStartIDE` default in `script-config` changes.
- **No fan-out by construction:** the skill never adds text to the prompt asking the receiver
  to forward work onward. The payload is exactly what the caller supplied or authored.
- **Payload is plain text, whole file.** No frontmatter, header, or metadata is added - the
  consumer reads everything as prompt.
- **Timestamps** in reports are local time with zone; file mtimes come from `os.stat`.
- **Escape hatch:** if anything below does not match reality (a contract changed, a path moved,
  a probe answers differently than stated), STOP and surface it. Do not improvise.

## The steps

### 1. gate-consumers - pin the version floors

**Anchor:** a module-level `FLOORS` dict near the top of `autoprompt.py` (create the file here
if `script-config` has not yet; this todo runs first).

```python
# editorId -> minimum installed CCVI version for each capability, or None = unsupported.
# "single": consumes <gitDir>/ccvi/auto_prompt.md. "numbered": also drains auto_prompt_<N>.md.
FLOORS = {
  "as":     {"single": "0.4.168", "numbered": None},
  "idea":   {"single": "0.4.168", "numbered": None},
  "vscode": {"single": None,      "numbered": None},
  "cursor": {"single": None,      "numbered": None},
}
```

`0.4.168` is the first ccvi-idea consuming `<gitDir>/ccvi/` (0.4.167 read the old repo-root
path). Then probe and fill the `None`s:

1. **ccvi-idea numbered:** read `../ccvi-idea/doc/contracts/auto_prompt.md`.
   - It documents numbered slots and names the first version that consumes them -> set
     `numbered` for `as` and `idea` to that version.
   - It still says "One fixed name" -> leave `None`. The skill ships single-slot; that is a
     supported state, not a blocker.
2. **ccvi-vscode:** it has no auto-prompt code of its own; `src/sidecar_link.ts` imports
   ccvi-idea's sidecar source, so it gains the consumer on its first build after ccvi-idea
   ships (ccvi-idea's plan confirms: no host glue). Probe the installed bundles per version
   dir, `~/.vscode/extensions/appcloud9.ccvi-vscode-<ver>/{out,dist}`:
   - `grep -rlF 'auto_prompt(?:_'` matches (the numbered regex literal survives bundling)
     -> the lowest such version is the `numbered` floor, and also the `single` floor.
   - only `grep -rlF 'auto_prompt.md'` matches -> that version is the `single` floor.
   - neither (1.2.33 on 2026-11-01) -> leave `None`.
   - Apply the same to `cursor` using `~/.cursor/extensions/appcloud9.ccvi-vscode-*`.

Record the probe results (command plus outcome) in a comment above `FLOORS`.

**Why:** a drop the target's consumer cannot read fails silently forever; the floors are what
turns that into a loud refusal.

**Done when:** `FLOORS` exists with every value either a version string backed by a recorded
probe or `None`.

### 2. script-config - parsing, config, and project resolution

**Anchor:** new file `plugin/skills/autoprompt/scripts/autoprompt.py`, module docstring
modeled on modes.py's "Contract:" header.

**CLI** (what SKILL.md calls; flags, not a raw directive string, because the prompt arrives on
stdin):

```text
autoprompt.py send   <projectDir> [--no-ide] (--prompt-arg-stdin | --prompt-stdin)
autoprompt.py show   [<projectDir>]
autoprompt.py clear  <projectDir>
autoprompt.py config [<key> [<value>]]
```

Exit 0 on success, 1 on a refusal (message on stdout, prefixed `refused:`), 2 on usage error.
Stdout is the user-facing report, relayed verbatim.

**Config** at `Path.home() / ".ccvi" / "autoprompt.json"` (use `Path.home()` so tests can set
`HOME`), a flat object:

| key | valid values | default when unset |
|---|---|---|
| `workingDir` | an existing directory; `~` expanded; stored absolute | parent of the cwd repo's `git rev-parse --show-toplevel` |
| `idePreferred` | `idea`, `vscode`, `cursor` | `idea` |

- `config` prints every key as `key = value` with `(default)` after an unset one.
- `config <key>` prints that one. `config <key> <value>` validates, writes (temp + rename in
  `~/.ccvi/`), and prints the new value.
- An unknown key, or an invalid value, is a refusal naming the valid ones.
- `as` is deliberately not a valid `idePreferred`: Android projects always get Android Studio.

**projectDir resolution** (function `resolveProject(raw)`):

1. No `/` in `raw` and not starting with `~`: reject if it contains `..`; join onto `workingDir`
   (config, else the default above; if the cwd is not a git repo and no config, refuse with
   "set it: /autoprompt config workingDir <dir>").
2. Otherwise expand `~`; a relative path resolves against the cwd.
3. `os.path.realpath` the result. It must be a directory.
4. `git -C <dir> rev-parse --absolute-git-dir` must succeed, else refuse ("not a git checkout -
   auto-prompt drops live in the git dir").
5. For a bare name, the realpath must still be inside `realpath(workingDir)`; refuse otherwise.

Return `(projectDir, gitDir)`.

**Prompt intake** (function `readPrompt(mode)`), both modes reading stdin:
- `--prompt-arg-stdin`: stdin is the user's raw `prompt` argument, classified here:
  - one line, ends `.md`, and contains `/` or starts with `~` -> a path. `~` expanded, relative
    to the cwd. It exists as a file -> its contents are the prompt; it does not exist ->
    refuse `no such file: <path>` (a mistyped path must never ship as a one-line prompt).
  - anything else -> the literal text.
- `--prompt-stdin`: stdin is agent-authored text, always literal.
- Text empty after strip -> refuse, before any file is written.

**`shouldStartIDE`** is the `--no-ide` flag at the script level. SKILL.md maps the user's
`false`/`0`/`no` to `--no-ide`; `true`/`1`/`yes` or absent means launch.

**Done when:** `config` round-trips both keys and refuses a bad one; `resolveProject` returns the
worktree git dir for `android-dmgz-3` (a worktree of `android-dmgz` on this machine) and refuses
`../x`, a non-git dir, and a missing dir.

### 3. script-ide - live windows, Android detection, IDE choice, version, launch

**Anchor:** functions `liveWindows(projectDir)`, `isAndroid(projectDir)`, `chooseIde(...)`,
`installedVersion(editorId)`, `launchIde(editorId, projectDir)` in `autoprompt.py`.

**`liveWindows`:** read every `~/.ccvi/agent_state/*.json` (dir may be absent - that is "none").
Skip a record whose `version` is not `1`. A record is **fresh** when
`now_ms - updatedAtMs < 60000`. Return two lists:
- `exact`: fresh records whose `realpath(cwd) == projectDir`;
- `siblings`: fresh records with the same `realpath(repoRoot)` as the target's repo root but a
  different `cwd` (another worktree of the same repo is open).

Stale records are never treated as a window. `show` lists the stale records for the project
under "history" (their `editorId` and age) as information only.

**`isAndroid`:** true if any of these exist in `projectDir`:
- `local.properties` containing a line starting `sdk.dir=`;
- `app/src/main/AndroidManifest.xml`;
- any of `build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`,
  `app/build.gradle`, `app/build.gradle.kts` containing `com.android.application`,
  `com.android.library`, or `com.android.tools.build:gradle`.

`.idea/` alone is not evidence; both JetBrains products write it.

**`chooseIde`**, in order, returning `(editorId, reason)`:
1. `exact` non-empty -> the newest record's `editorId`, reason `live window`. No launch.
2. `isAndroid` -> `as`, reason `android project`.
3. else -> `idePreferred`, reason `preference`.

History (stale records, JetBrains `recentProjects.xml`) does NOT steer the choice: for a
non-Android project the IDE is a preference, and history would override it with whatever
happened last.

**`installedVersion(editorId)`:**
- `as`: newest `~/Library/Application Support/Google/AndroidStudio*` dir (sort by the numeric
  version in the dir name) that has `plugins/ccvi-idea/lib/ccvi-idea-<ver>.jar`; ignore
  `-searchableOptions` jars and `ccvi-idea.bak*` dirs. On this machine that is
  `AndroidStudio2026.1.4` -> `0.4.168`.
- `idea`: the same under `~/Library/Application Support/JetBrains/IntelliJIdea*`.
- `vscode` / `cursor`: highest `appcloud9.ccvi-vscode-<ver>` under `~/.vscode/extensions` /
  `~/.cursor/extensions`.
- Not found -> `None`. Compare versions as integer tuples.

**Capability:** `capability(editorId)` returns `numbered` if the installed version meets
`FLOORS[e]["numbered"]`, else `single` if it meets `FLOORS[e]["single"]`, else `none`.
`none` is a refusal for `send`: "the CCVI extension for <app> at <ver|not installed> can't
consume auto-prompt drops; set /autoprompt config idePreferred idea or update it". This check
runs before any file is written.

**`launchIde`:** `subprocess.run(["open", "-a", APP[editorId], projectDir])`. Non-zero exit
-> report the stderr; the drop stays written (it will be consumed whenever a window opens).
When env `AUTOPROMPT_NO_LAUNCH=1` is set, print `would run: open -a "<App>" "<dir>"` instead
(tests and the smoke use this).

**Done when:** for `android-dmgz` the choice is `as` (android project, or live window if one is
fresh); for `ccvi-skills` with this session open it is `idea` via `live window`; for a
non-Android repo with no window it is `idePreferred`; `installedVersion("idea")` returns
`0.4.168` on this machine.

### 4. script-drop - the writer, show, and clear

**Anchor:** functions `slots(ccviDir)`, `writeDrop(gitDir, text, capability)`, `cmdShow`,
`cmdClear` in `autoprompt.py`.

**`slots`:** list `ccviDir`, keep names matching `^auto_prompt(_[1-9][0-9]*)?\.md$`, return
`[(index, name)]` sorted by index (bare = 0).

**`writeDrop`:**

```python
ccviDir = gitDir / "ccvi"
ccviDir.mkdir(parents=True, exist_ok=True)   # mandatory: an unopened repo has no ccvi/ dir
tmp = ccviDir / f".auto_prompt.{os.getpid()}.{secrets.token_hex(4)}.tmp"
tmp.write_text(text.rstrip() + "\n", encoding="utf-8")
try:
  for _ in range(10):
    present = slots(ccviDir)
    if not present:
      dest = ccviDir / "auto_prompt.md"
    elif capability == "numbered":
      dest = ccviDir / f"auto_prompt_{present[-1][0] + 1}.md"
    else:
      return refuse("a drop is already waiting at <path>; this CCVI version holds one at a time")
    try:
      os.link(tmp, dest)       # no-replace: fails with FileExistsError, never overwrites
      return dest
    except FileExistsError:
      continue                 # a racing writer took it - RESCAN, don't just increment
  return refuse("could not claim a slot after 10 attempts")
finally:
  tmp.unlink(missing_ok=True)
```

- **Never `os.rename`/`mv` onto a slot** - rename silently replaces.
- The bare name is used only when NO slot exists. Once any numbered slot is present, never the
  bare name (slot 0 would jump the queue).
- `numbered` is used only when `capability == "numbered"` (old consumers ignore `_N`).
- Empty text after strip is a refusal before any file is created.

**`send` report** (stdout), one fact per line:

```text
autoprompt -> /Users/keldon/Desktop/working/android-dmgz
drop: <absolute slot path> (slot N, M waiting)
window: live in Android Studio (state idle) | none open
ide: Android Studio (android project) - launched | not launched (--no-ide) | already open
note: other worktrees of this repo are open: <cwd> (<editorId>) ...
```

The `note:` line appears in two cases, and neither one stops the send:
- `siblings` is non-empty and `exact` is empty: the user asked for one checkout while a window
  is open on another. Still write and launch as asked.
- `exact` holds more than one fresh record: two windows share this worktree, and either may
  claim the drop (ccvi-idea's contract: "two windows on one repo root can split a batch").

**`show [projectDir]`:** with no arg, the `config` listing. With one: resolved dir and git dir;
live windows (editorId, state, age); sibling worktree windows; stale history; the IDE `send`
would use and why; installed CCVI version and capability for that editor; waiting slots (name,
bytes, mtime) and their first line. Writes nothing.

**`clear {projectDir}`:** for each waiting slot, `os.rename` it to
`~/.Trash/auto_prompt-cleared-<YYYYmmddTHHMMSS>-<name>` (the rename is the claim; on
`FileNotFoundError` report "already consumed"). Report each move. The skill only ever moves to
the Trash, never deletes.

**Done when:** two concurrent `send`s into one capability-`numbered` target produce two
distinct slots with no overwrite; a capability-`single` target with a waiting drop refuses;
`clear` empties the slots into `~/.Trash` and a second `clear` reports nothing waiting.

### 5. skill-md - plugin/skills/autoprompt/SKILL.md

**Anchor:** new file. Model the frontmatter on
[repos SKILL.md](../plugin/skills/repos/SKILL.md) (description with the `•`-joined verb list,
`argument-hint`, `allowed-tools`, the commented `verbs:` schema block).

```yaml
verbs:
  send:   { order: 1, params: [ { name: projectDir,     type: string,  required: true },
                                { name: prompt,         type: string,  required: false },
                                { name: shouldStartIDE, type: boolean, required: false, default: true } ] }
  show:   { order: 2, params: [ { name: projectDir, type: string, required: false } ] }
  clear:  { order: 3, params: [ { name: projectDir, type: string, required: true } ] }
  config: { order: 4, params: [ { name: key,   type: string, required: false },
                                { name: value, type: string, required: false } ] }
```

Body sections, kept thin:

- **Invocation** table for the four verbs plus the bare-`projectDir` default-to-`send` rule.
- **Argument parsing for send:** after `projectDir`, if the LAST token is one of
  `true false 1 0 yes no` (any case) it is `shouldStartIDE`; everything between `projectDir`
  and it (or to the end) is `prompt`, quotes stripped. So `/autoprompt android-dmgz false` is no
  prompt plus no launch, and an unquoted multi-word prompt still works. Worked examples, stated
  in the SKILL.md as a table:

  | directive | prompt | shouldStartIDE |
  |---|---|---|
  | `/autoprompt android-dmgz` | agent-authored | true |
  | `/autoprompt android-dmgz 'my amazing prompt'` | that text | true |
  | `/autoprompt android-dmgz ~/notes/handoff.md false` | that file | false |
  | `/autoprompt android-dmgz false` | agent-authored | false |

- **Prompt sourcing,** two cases, both piped on stdin with a quoted heredoc so the shell never
  expands the text:
  1. `prompt` given -> pass it raw with `--prompt-arg-stdin`; the script decides text vs path
     (see `script-config`). Do not read the file yourself.
  2. no `prompt` -> author it from the conversation, whoever invoked the skill: a
     self-contained brief for an agent with none of this context (what to do, why, where the
     relevant files are, what "done" means, whether to report back and how). Do not add
     instructions to forward work to other projects. Pass it with `--prompt-stdin`.
  ```bash
  python3 "{SKILL_DIR}/scripts/autoprompt.py" send "<projectDir>" [--no-ide] --prompt-arg-stdin <<'AUTOPROMPT_EOF'
  <raw prompt argument, or the authored brief with --prompt-stdin>
  AUTOPROMPT_EOF
  ```
- **Echo:** relay the script's stdout verbatim as plain text (not fenced). On exit 1, relay the
  `refused:` line and stop - do not retry with different arguments unasked.
- **What it does not do:** no queueing beyond the consumer's slots, no reply channel (ask for a
  reply in the prompt if one is wanted), no expiry, never edits the target repo's working tree.
- **Help output** for a blank `/autoprompt` (no arg at all): a fenced `text` block headed
  `/autoprompt · v0.0.0 - ...` (build.py stamps the real version) listing the four signatures
  above and the two config keys.

**Done when:** the frontmatter parses as YAML; the help header matches the STAMPS pattern added
in `repo-wiring`; every fact in the `verbs:` block is also stated in the prose.

### 6. repo-wiring - build.py, README, CLAUDE.md

- **`build.py` `MANIFEST_SKILLS`:** append

  ```python
  {
    "name": "autoprompt",
    "invocation": "/autoprompt [verb] [args]",
    "verbs": [
      {"name": "send", "params": [_param("projectDir", True, "dir"),
                                  _param("prompt", False, "freeform"),
                                  _param("shouldStartIDE", False, "flag", "1")]},
      {"name": "show", "params": [_param("projectDir", False, "dir")]},
      {"name": "clear", "params": [_param("projectDir", True, "dir")]},
      {"name": "config", "params": [_param("key", False, "freeform"),
                                    _param("value", False, "freeform")]},
    ],
  },
  ```
- **`build.py` `STAMPS`:** add
  `(p("plugin", "skills", "autoprompt", "SKILL.md"), re.compile(r"/autoprompt · v\d+\.\d+\.\d+"), "/autoprompt · v{v}")`.
- **README.md:** add an `autoprompt` row to the table under `## The skills`, in the existing
  row style (verbs as a nested `<ul>` with params), and add `autoprompt` to the intro sentence
  listing the skills and to the `ccvi-skills:<name>` list.
- **CLAUDE.md:** in the `## Layout` block add
  `skills/autoprompt/SKILL.md` and `skills/autoprompt/scripts/autoprompt.py - autoprompt fast-path script`
  lines beside the existing skill lines.

**Done when:** `python3 build.py` then `python3 build.py --check` exit 0, and `manifest.json`
lists the `autoprompt` skill with four verbs.

### 7. tests - test/test_autoprompt.py

**Anchor:** new file beside [test_modes.py](../test/test_modes.py); dev-only, never packaged.
Plain asserts with a final count, in test_modes.py's style; exit non-zero on any failure.

Each test runs the script as a subprocess with `HOME` set to a temp dir (so config,
`agent_state`, the Trash, and the IDE install dirs are all fakes) and `AUTOPROMPT_NO_LAUNCH=1`.
Build fixtures with real `git init` and `git worktree add` in the temp dir.

Cover:
- config set/get/unknown key/bad `idePreferred`/`as` rejected;
- resolution: bare name via `workingDir`, `..` rejected, absolute path, worktree -> worktree git
  dir, non-git dir refused;
- `isAndroid` true for each of the three evidence kinds, false for a `.idea/`-only dir;
- `chooseIde`: fresh exact record wins; stale record ignored; android -> `as`; else preference;
  a `version: 2` record skipped;
- capability: fake `IntelliJIdea2026.2/plugins/ccvi-idea/lib/ccvi-idea-0.4.168.jar` -> `single`;
  absent install -> `none` and `send` refuses without creating `ccvi/`;
- writer: `single` empty -> bare slot; `single` occupied -> refusal; `numbered` (patch `FLOORS`
  via an env override `AUTOPROMPT_FLOORS_JSON` the script honors for tests) -> `_1`, `_2`;
  20 parallel `send`s produce 20 distinct slots and no temp files left behind;
- prompt intake: `--prompt-arg-stdin` with literal text sends it; with an existing `.md` path
  sends the file's contents; with `~/nope/missing.md` refuses and creates no slot; a multi-line
  text ending in `.md` is literal; `--prompt-stdin` never reads a path;
- `show` writes nothing (dir listing identical before and after);
- `clear` moves slots into the fake `~/.Trash`.

**Done when:** `python3 test/test_autoprompt.py` exits 0 and `python3 test/test_modes.py` still
exits 0.

### 8. live-smoke - one real drop

With this repo's own CCVI window open (it is the one running the build):

```bash
SKILL=plugin/skills/autoprompt
python3 "$SKILL/scripts/autoprompt.py" show "$PWD"
python3 "$SKILL/scripts/autoprompt.py" send "$PWD" --no-ide --prompt-arg-stdin <<'AUTOPROMPT_EOF'
Say the word banana and nothing else.
AUTOPROMPT_EOF
```

**Done when:** within ~5 s a CCVI-attributed turn reading "Say the word banana and nothing
else." arrives in this session; `ls "$(git rev-parse --absolute-git-dir)/ccvi/"` shows no slot
left; `grep AutoPrompt ~/.ccvi/Logs/idea/ccvi-$(date -u +%F).log` shows the pickup (the log
date is UTC). Answer the banana turn with "banana" and continue.

The IDE launch is not smoke-tested here because it opens a window; it is the manual check in
**Verification**.

### 9. bbpi

Run BBPI exactly as CLAUDE.md's "BBP / BBPI" section states: bump the last segment in
`plugin/.claude-plugin/plugin.json`, `python3 build.py`, `python3 build.py --check`,
`python3 test/test_modes.py`, `python3 test/test_autoprompt.py`, commit with a message
describing the new skill, push to `main`, unzip into `~/.ccvi/ccvi-skills/plugin/`.

**Done when:** the installed plugin.json shows the new version and
`~/.ccvi/ccvi-skills/plugin/skills/autoprompt/SKILL.md` exists. The skill registers in the next
Claude Code session.

## Out of scope

- **Anything in ccvi-idea or ccvi-vscode** - the numbered consumer, the drain-per-tick change,
  the contract edit, the authorization entry, stale `*.claimed-<pid>` sweeping. ccvi-idea
  reviews this plan and builds its side; this plan only reads their files.
- **The `/work` skill and its plan** (`doc/work_skill_and_plugin_merge.plan.md`) - on hold;
  do not touch, and do not make `/work` depend on this.
- **Windows and Linux launch** - macOS `open -a` only; on another platform `send` with launch
  reports "launch unsupported on <platform>" after writing the drop.
- **A reply channel, receipts, or expiry** - not part of the contract.
- **Editing `~/.ccvi/global_settings.json`** - the skill owns `~/.ccvi/autoprompt.json` only.
- **Fixing other stale lines in CLAUDE.md** (e.g. "What this repo is" naming three skills).

## Verification

1. `python3 build.py --check`, `python3 test/test_modes.py`, `python3 test/test_autoprompt.py`
   all exit 0.
2. The live-smoke banana turn arrived and the drop was consumed.
3. Manual, by Keldon, when convenient: with Android Studio closed on `android-dmgz`, run
   `/autoprompt android-dmgz "Say the word banana and nothing else."` from another repo. Android
   Studio opens on `android-dmgz` and the banana turn arrives as its first turn.
4. Once ccvi-idea ships the numbered consumer: re-run `gate-consumers`'s probe, set the
   `numbered` floor, and confirm two quick `send`s to one open window arrive as two turns, in
   order.

## Build notes (2026-11-01)

- **Review findings applied during the build.** `autoprompt_skill.plan.review.md` landed
  mid-build and was not run through `/plans update`; its probes checked out on this machine, so
  the build applied them directly:
  - `installed_version` reads the launched app's `Contents/Resources/product-info.json`
    `dataDirectoryName` (Android Studio -> `AndroidStudio2026.1.4`, whose jar is 0.4.168; the
    older `AndroidStudio2026.1.1` holds 0.4.42), falling back to newest-with-jar;
  - `is_android` adds a depth-4 scan of `*.gradle`, `*.gradle.kts`, and `*.versions.toml`
    (android-dmgz's only tracked marker is `buildLogic/gradle/buildLibs.versions.toml`);
  - the capability refusal names a remedy that fits its branch;
  - the path test requires a single token, so a sentence ending in `.md` is literal;
  - `clear` uses the XDG trash off macOS; the CLAUDE.md layout gained the missing `cleancode`
    and `repos` lines.
  - Already handled in the build as written: repoRoot via `--git-common-dir`, `Path` git dir,
    `AUTOPROMPT_FLOORS_JSON`, STAMPS after the SKILL.md display.
- **Naming:** Python functions use snake_case (`resolve_project`, `live_windows`, ...) to match
  modes.py; the plan's camelCase names map one-to-one.
- **gate-consumers result:** `numbered` stays `None` for `as`/`idea` (ccvi-idea's contract still
  says "One fixed name" at 0.4.168); `vscode`/`cursor` are unsupported (no consumer string in
  1.2.31 or 1.2.33).
