---
name: autoprompt
description: send•show•clear•config - hand a prompt to the agent in ANOTHER project by writing a CCVI auto-prompt dead drop into that project's per-worktree git dir and, unless told not to, opening it in the right IDE (a named one, else the IDE it last ran in, else Android Studio for Android, else a configured preference) so the CCVI window there runs it as its next turn, via /autoprompt [verb]. Use when the user (or an agent) wants to send work, a brief, or a prompt to another repo's session, or to inspect or clear prompts waiting for one.
argument-hint: "[verb] {projectDir} [prompt] [shouldStartIDE] [ide]"
allowed-tools: Read, Bash(python3:*)
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host that renders a verb menu and
# generates each verb's dialog from `params`. Every fact here MUST also be stated in
# the prose - the skill stays fully usable in vanilla Claude Code.
verbs:
  send:   { order: 1, params: [ { name: projectDir,     type: string,  required: true },
                                { name: prompt,         type: string,  required: false },
                                { name: shouldStartIDE, type: boolean, required: false, default: true },
                                { name: ide,            type: string,  required: false } ] }
  show:   { order: 2, params: [ { name: projectDir, type: string, required: false } ] }
  clear:  { order: 3, params: [ { name: projectDir, type: string, required: true } ] }
  config: { order: 4, params: [ { name: key,   type: string, required: false },
                                { name: value, type: string, required: false } ] }
---

# autoprompt

Send a prompt to the agent working in a **different** project. The skill writes a CCVI
**auto-prompt dead drop** into that project's per-worktree git dir
(`$(git -C <projectDir> rev-parse --absolute-git-dir)/ccvi/`). The CCVI sidecar of the window
open on that worktree picks it up within about 3 seconds and sends it as a CCVI-attributed
turn. A drop never opens a window by itself, so when no live window is on the project, `send`
opens the right IDE there (unless `shouldStartIDE` is false); CCVI starts with the IDE and runs
the drop as its first turn.

Humans and agents both use this skill, and it always runs inside some agent's session. When
`prompt` is omitted, **the agent running the skill authors it**, whoever invoked it.

The consumer contract is ccvi-idea's `doc/contracts/auto_prompt.md`; window liveness comes from
its `doc/contracts/agent_state.md`.

**A prompt may carry a frontmatter envelope.** The drop is the `.prompt.md` file type (ccvi-idea
`doc/contracts/prompt_file.md`): a prompt that STARTS with a `---` fence carries host-only
directives the target window executes before sending the body - `session: new` (start a fresh
session first), `modes:`, `model:`, `effort:`, `thoughts:`, `yolo:`, `label:`, `title:`. Pass
the whole thing, fence included, as the prompt:

```text
/autoprompt send <worktree> '---
session: new
modes: agent-loop 80
yolo: true
label: "#tickets W-1234"
---
<the work order - the only part the target agent sees>'
```

Only the body reaches the target agent, so the body must say why the turn arrived. `yolo: true`
turns YOLO on in the target session, with no allowlist (Keldon's decision, 2026-11-05). An envelope
needs CCVI 0.4.187 or newer in the target IDE: below that, `send` refuses rather than letting
the frontmatter arrive as plain text.

## Invocation

Single entry point - **`/autoprompt [verb] [args]`**, dispatching on the first arg:

| Form | Effect |
|---|---|
| `/autoprompt send {projectDir} [prompt] [shouldStartIDE] [ide]` | Write the next drop for `projectDir`; open its IDE if no live window is there |
| `/autoprompt show [projectDir]` | Report what `send` would do, plus waiting drops; with no arg, the config. Writes nothing |
| `/autoprompt clear {projectDir}` | Move the project's waiting drops to the Trash (`~/.Trash`; the XDG trash off macOS) |
| `/autoprompt config [key] [value]` | Show all config, show one key, or set one |
| `/autoprompt {projectDir} ...` | Shorthand for `send` - any first arg that is not a verb |
| `/autoprompt` (no args) | Print the help cheat-sheet (see **Help output**) |

Verbs are lowercase. A project literally named `send`, `show`, `clear`, or `config` needs the
explicit `send`. Natural language maps the obvious way: "send this to android-dmgz", "hand this
off to the projectx agent" -> `send`; "what's waiting for android-dmgz?" -> `show`.

### `projectDir`

- **No `/` and no leading `~`** -> a project name, joined onto `workingDir` (config; default:
  the parent of the current repo). A name containing `..` is refused.
- **Otherwise** a path: `~` expanded, relative paths against the cwd.
- **An absolute path is the reliable form** - it skips name resolution and the cwd entirely.
  Prefer it when sending from an agent whose cwd you do not control: IntelliJ's cwd is the
  project dir, but VS Code's is the user's home, so a bare name or a relative path resolves
  somewhere different depending on the host.
- It must be a git checkout. A worktree resolves to its own git dir, so a drop for
  `android-dmgz-3` reaches only the window open on that worktree.

### Argument parsing for `send`

After `projectDir`, look at the **trailing** tokens that are **not inside the quoted prompt**,
up to two of them, in either order:

- one of `true false 1 0 yes no` (any case) is `shouldStartIDE`;
- one of `as idea vscode cursor` is `ide`.

Everything between `projectDir` and those (or to the end) is `prompt`, outer quotes stripped. So
`'ship it or no'` and `'open it in idea'` are all prompt, while an unquoted multi-word prompt
still works.

| directive | prompt | shouldStartIDE |
|---|---|---|
| `/autoprompt android-dmgz` | agent-authored | true |
| `/autoprompt android-dmgz 'my amazing prompt'` | that text | true |
| `/autoprompt android-dmgz ~/notes/handoff.md false` | that file | false |
| `/autoprompt android-dmgz false` | agent-authored | false |
| `/autoprompt projectx 'my amazing prompt' vscode` | that text | true, `ide` vscode |
| `/autoprompt projectx idea false` | agent-authored | false, `ide` idea |

`shouldStartIDE` defaults to true. False maps to the script's `--no-ide`. `ide` maps to
`--ide <ide>`; omitted, the script picks (see **What `send` does**, step 4).

### `prompt`: text, a file, or authored

- **Given** -> pass it **raw** with `--prompt-arg-stdin`; the script decides: a single token
  (no whitespace) ending `.md` that contains `/` or starts with `~` is a **path** (its contents are sent; a
  missing file is refused, so a typo never ships as a one-line prompt); anything else is
  **literal text**. Do not read the file yourself.
- **Omitted** -> author it now, from the conversation: a **self-contained brief** for an agent
  that has none of this context - what to do, why, where the relevant files are, what "done"
  means, and whether and how to report back. Do not add instructions to forward work to other
  projects. Pass it with `--prompt-stdin`.

## Run the script

Substitute `{SKILL_DIR}` with the "Base directory for this skill" path. Always send the prompt
on stdin through a **quoted** heredoc, so the shell never expands it:

```bash
python3 "{SKILL_DIR}/scripts/autoprompt.py" send "<projectDir>" [--no-ide] [--ide <ide>] --prompt-arg-stdin <<'AUTOPROMPT_EOF'
<the raw prompt argument>
AUTOPROMPT_EOF
```

```bash
python3 "{SKILL_DIR}/scripts/autoprompt.py" send "<projectDir>" [--no-ide] [--ide <ide>] --prompt-stdin <<'AUTOPROMPT_EOF'
<the brief you authored>
AUTOPROMPT_EOF
```

```bash
python3 "{SKILL_DIR}/scripts/autoprompt.py" show ["<projectDir>"]
python3 "{SKILL_DIR}/scripts/autoprompt.py" clear "<projectDir>"
python3 "{SKILL_DIR}/scripts/autoprompt.py" config ["<key>" ["<value>"]]
```

Exit 0 is success, 1 is a refusal (stdout starts `refused:`), 2 is a usage error.

## Echo

Relay the script's stdout **verbatim as plain text** (not in a code block) as the reply. When
you authored the prompt, follow the echo with one line summarizing what you sent. On exit 1,
relay the `refused:` line and stop - do not retry with different arguments unasked.

## What `send` does

1. Resolves `projectDir` and its git dir.
2. Reads the prompt; an empty prompt is refused.
3. Finds windows by asking CCVI itself: it calls `GET /whoami` on every loopback port in
   17390-17453 in parallel, and a **live window** is one whose sidecar answers there, matched on
   its `gitDir` (so worktrees never collide). No file decides whether a window is open; a gone
   window cannot answer, whatever its leftover records say. `~/.ccvi/agent_state/*.json` only
   supplies the state (idle / mid-turn / human-driven). For a CCVI build older than `/whoami`
   (its port answers 404), a record counts only if it is under 60 s old AND its pid is running.
4. Picks the IDE, taking the first of five rungs that hits (the report names the rung):
   1. **live window** - its own IDE wins and nothing is launched. A given `ide` that differs is
      ignored, with a `note: --ide <x> ignored` line.
   2. **`--ide`** - the `ide` you named.
   3. **last used** - the newest `~/.ccvi/agent_state` record for this project whose editor's
      installed CCVI can take drops. A record for an editor that can't is skipped, not refused.
   4. **android project** (`local.properties` with `sdk.dir=`, `app/src/main/AndroidManifest.xml`,
      or a Gradle file applying `com.android.*`) - **Android Studio**.
   5. **preference** - `idePreferred`.
5. Checks that IDE's installed CCVI can consume drops. Too old, or not installed, is a refusal
   before anything is written.
6. Writes the drop: `auto.prompt.md` when nothing is waiting; `auto_<N>.prompt.md` (next
   number) when something is and the consumer supports numbered drops; otherwise a refusal.
   A target older than the directives floor (0.4.187) gets the legacy names (`auto_prompt.md`,
   `auto_prompt_<N>.md`), which is all it reads, and an envelope prompt to it is refused.
   Drops already waiting under either spelling count toward the next number. Writes are
   no-replace, so two senders never overwrite each other.
7. Launches the IDE with `open -a "<App>" "<projectDir>"` when no live window is open and
   `shouldStartIDE` is true. The drop is written first and waits, so there is no race. The
   launch is idempotent: it is skipped (`not relaunched`) when this project was launched under
   180 s ago (`~/.ccvi/autoprompt_launches.json`), or, for IntelliJ IDEA and Android Studio, when
   the IDE is running and its newest `recentProjects.xml` marks the project open. Either way the
   drop waits for CCVI to come up.

A busy target (`mid-turn`, or `human-driven` because someone typed in it recently) still gets
the drop; it queues behind the current turn like a typed prompt, and the report names the
state. The report also notes when another worktree of the same repo is open instead, or when
two windows share the worktree (either may take the drop).

## Config

Stored in `~/.ccvi/autoprompt.json`:

| key | values | default |
|---|---|---|
| `workingDir` | an existing directory | the parent of the current repo |
| `idePreferred` | `idea`, `vscode`, `cursor` | `idea` |

`idePreferred` applies only to projects that are not Android; Android always opens in Android
Studio, so `as` is not a valid value. A VS Code or Cursor preference works only once that
editor's CCVI extension consumes drops; until then `send` refuses and says so.

## What this skill does not do

- No reply channel: if you want an answer back, ask for one in the prompt.
- No expiry: a waiting drop runs whenever a window next opens. Use `clear` to withdraw it.
- Never edits the target's working tree; the drop lives in the git dir, so it never shows in
  `git status`.
- Never asks the receiver to send work onward.

## Help output

When the user runs `/autoprompt` with no arguments (or asks what it can do), reply with exactly
this - no preamble, no postscript:

```text
/autoprompt · v0.0.42 - send a prompt to another project's CCVI session:
• send {projectDir} [prompt] [shouldStartIDE] [ide]  - write the next drop; open the IDE if no live window
• show [projectDir]                                  - what send would do + waiting drops (no arg: config)
• clear {projectDir}                                 - move waiting drops to the Trash
• config [key] [value]                               - workingDir | idePreferred (idea, vscode, cursor)

Shorthand: /autoprompt {projectDir} ... is send. prompt: text, or a path to a .md file; omitted, the agent writes it.
ide: as | idea | vscode | cursor; omitted, the IDE it last ran in, then Android Studio for Android, then idePreferred.
```
