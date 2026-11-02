---
name: autoprompt
description: send•show•clear•config - hand a prompt to the agent in ANOTHER project by writing a CCVI auto-prompt dead drop into that project's per-worktree git dir and, unless told not to, opening it in the right IDE (Android Studio for Android, else a configured preference) so the CCVI window there runs it as its next turn, via /autoprompt [verb]. Use when the user (or an agent) wants to send work, a brief, or a prompt to another repo's session, or to inspect or clear prompts waiting for one.
argument-hint: "[verb] {projectDir} [prompt] [shouldStartIDE]"
allowed-tools: Read, Bash(python3:*)
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host that renders a verb menu and
# generates each verb's dialog from `params`. Every fact here MUST also be stated in
# the prose - the skill stays fully usable in vanilla Claude Code.
verbs:
  send:   { order: 1, params: [ { name: projectDir,     type: string,  required: true },
                                { name: prompt,         type: string,  required: false },
                                { name: shouldStartIDE, type: boolean, required: false, default: true } ] }
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

## Invocation

Single entry point - **`/autoprompt [verb] [args]`**, dispatching on the first arg:

| Form | Effect |
|---|---|
| `/autoprompt send {projectDir} [prompt] [shouldStartIDE]` | Write the next drop for `projectDir`; open its IDE if no live window is there |
| `/autoprompt show [projectDir]` | Report what `send` would do, plus waiting drops; with no arg, the config. Writes nothing |
| `/autoprompt clear {projectDir}` | Move the project's waiting drops to the Trash (`~/.Trash`; the XDG trash off macOS) |
| `/autoprompt config [key] [value]` | Show all config, show one key, or set one |
| `/autoprompt {projectDir} ...` | Shorthand for `send` - any first arg that is not a verb |
| `/autoprompt` (no args) | Print the help cheat-sheet (see **Help output**) |

Verbs are lowercase. A project literally named `send`, `show`, `clear`, or `config` needs the
explicit `send`. Natural language maps the obvious way: "send this to android-dmgz", "hand this
off to the dpp agent" -> `send`; "what's waiting for android-dmgz?" -> `show`.

### `projectDir`

- **No `/` and no leading `~`** -> a project name, joined onto `workingDir` (config; default:
  the parent of the current repo). A name containing `..` is refused.
- **Otherwise** a path: `~` expanded, relative paths against the cwd.
- It must be a git checkout. A worktree resolves to its own git dir, so a drop for
  `android-dmgz-3` reaches only the window open on that worktree.

### Argument parsing for `send`

After `projectDir`, if the **last** token is one of `true false 1 0 yes no` (any case) **and is
not inside the quoted prompt**, it is `shouldStartIDE`; everything between `projectDir` and it
(or to the end) is `prompt`, outer quotes stripped. So `'ship it or no'` is all prompt, while an
unquoted multi-word prompt still works.

| directive | prompt | shouldStartIDE |
|---|---|---|
| `/autoprompt android-dmgz` | agent-authored | true |
| `/autoprompt android-dmgz 'my amazing prompt'` | that text | true |
| `/autoprompt android-dmgz ~/notes/handoff.md false` | that file | false |
| `/autoprompt android-dmgz false` | agent-authored | false |

`shouldStartIDE` defaults to true. False maps to the script's `--no-ide`.

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
python3 "{SKILL_DIR}/scripts/autoprompt.py" send "<projectDir>" [--no-ide] --prompt-arg-stdin <<'AUTOPROMPT_EOF'
<the raw prompt argument>
AUTOPROMPT_EOF
```

```bash
python3 "{SKILL_DIR}/scripts/autoprompt.py" send "<projectDir>" [--no-ide] --prompt-stdin <<'AUTOPROMPT_EOF'
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
3. Finds windows from `~/.ccvi/agent_state/*.json`: a record is a **live window** only when
   `version` is 1 and it was updated less than 60 s ago, and it matches when its `cwd` is the
   project. Stale records are history, never windows.
4. Picks the IDE: a live window's own IDE wins (nothing is launched); else an **Android
   project** (`local.properties` with `sdk.dir=`, `app/src/main/AndroidManifest.xml`, or a
   Gradle file applying `com.android.*`) gets **Android Studio**; else `idePreferred`.
5. Checks that IDE's installed CCVI can consume drops. Too old, or not installed, is a refusal
   before anything is written.
6. Writes the drop: `auto_prompt.md` when nothing is waiting; `auto_prompt_<N>.md` (next
   number) when something is and the consumer supports numbered drops; otherwise a refusal.
   Writes are no-replace, so two senders never overwrite each other.
7. Launches the IDE with `open -a "<App>" "<projectDir>"` when no live window is open and
   `shouldStartIDE` is true. The drop is written first and waits, so there is no race.

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
/autoprompt · v0.0.27 - send a prompt to another project's CCVI session:
• send {projectDir} [prompt] [shouldStartIDE]  - write the next drop; open the IDE if no live window
• show [projectDir]                            - what send would do + waiting drops (no arg: config)
• clear {projectDir}                           - move waiting drops to the Trash
• config [key] [value]                         - workingDir | idePreferred (idea, vscode, cursor)

Shorthand: /autoprompt {projectDir} ... is send. prompt: text, or a path to a .md file; omitted, the agent writes it.
```
