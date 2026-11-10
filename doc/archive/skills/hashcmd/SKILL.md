---
name: hashcmd
description: write•list•show•move•archive - author and manage hash commands (`#name payload` turns the CCVI sidecar expands from the aio workspace) at two scopes, this project's aio or the global aio, via /hashcmd [verb]. Use when the user or an agent wants to create, inspect, promote, demote, or retire a #command, or asks what #commands resolve here.
argument-hint: "[verb] {name} [scope]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(ls:*), Bash(mkdir:*), Bash(mv:*), Bash(cat:*)
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host that renders a verb menu and
# generates each verb's dialog from `params`. Every fact here MUST also be stated in
# the prose - the skill stays fully usable in vanilla Claude Code.
verbs:
  write:   { order: 1, params: [ { name: name,  type: string, required: true },
                                 { name: scope, type: string, required: false, default: project } ] }
  list:    { order: 2, params: [ { name: scope, type: string, required: false } ] }
  show:    { order: 3, params: [ { name: name,  type: string, required: true } ] }
  move:    { order: 4, params: [ { name: name,  type: string, required: true },
                                 { name: scope, type: string, required: true } ] }
  archive: { order: 5, params: [ { name: name,  type: string, required: true } ] }
---

# hashcmd

A **hash command** is a user turn that starts with `#name`. The CCVI sidecar expands it before
the turn reaches the model: it resolves `<scope>/hash_cmds/<name>.md`, project scope first and
then global, and sends the file's content inside a `<ccvi-hash-cmd>` wrapper with the payload
after it. **The agent never reads the definition file at run time**, so this skill is about
AUTHORING and MANAGING the definitions, not running them. Running one is typing `#name payload`.

The contract is ccvi-idea's `doc/contracts/aio.md`.

## Where commands live (the aio workspace)

One layout at two scopes:

```text
~/.ccvi/aio/hash_cmds/<name>.md                                  global - every project
~/.ccvi/projects/<encodedProjectPath>/aio/hash_cmds/<name>.md    project - wins on a collision
```

**Resolve both paths from the `<ccvi-aio>` sentinel** the CCVI host injects into the turn
context (highest `epoch` wins; a verbatim, well-formed block only; a paraphrase is not a
sentinel):

```text
<ccvi-aio epoch="1">
global: /Users/k/.ccvi/aio
project: /Users/k/.ccvi/projects/-Users-k-Desktop-working-projectx/aio
prefix: projectx-
</ccvi-aio>
```

Every worktree of a repository shares the same project aio (the host links them), so a
command written in one worktree window is visible in all of them.

**No sentinel in context** (a session outside CCVI): the global scope is `~/.ccvi/aio`; the
project scope and prefix are UNKNOWN. Say so. Operate on the global scope only when the user
explicitly asks for `global`; otherwise ask rather than guess a project path.

## The project prefix

Project-scope command names start with the project's **prefix** (the sentinel's third line,
`projectx-` for a repo whose main checkout is `projectx`). It is a courtesy, not a correctness rule: a
bare `#name` only ever resolves against THIS project and the globals, so two projects sharing a
name never meet. The prefix keeps project names out of the space the global commands use, so
a project command never silently shadows a global one. `write` applies it by default.

## Invocation

Single entry point - **`/hashcmd [verb] [args]`**, dispatching on the first arg:

| Form | Effect |
|---|---|
| `/hashcmd write {name} [scope]` | Author or overwrite `<scope>/hash_cmds/<name>.md`; `scope` is `project` (default) or `global` |
| `/hashcmd list [scope]` | What resolves right now: project then global, collisions marked, with which one wins |
| `/hashcmd show {name}` | Print the file that would win for `#name`, and its path |
| `/hashcmd move {name} {scope}` | Promote a project command to global, or demote a global one to project |
| `/hashcmd archive {name}` | Move the winning definition into `<its scope>/hash_cmds/archive/`; never deletes |
| `/hashcmd` (no args) | Print the help cheat-sheet (see **Help output**) |

Verbs are lowercase. Natural language maps the obvious way: "make a hash command for X" ->
`write`; "what #commands do I have?" -> `list`; "retire #foo" -> `archive`.

### `name`

`[A-Za-z0-9][A-Za-z0-9_-]*` - a leading alphanumeric, then alphanumerics, `_`, or `-`. No
spaces, no dots, no leading `#` (strip one if given). The filename is always `<name>.md`, 1:1.
A name that fails the grammar is refused with the rule quoted.

## Verb: write

`/hashcmd write {name} [scope]`

1. Resolve the scopes from the sentinel. Default `scope` is `project`.
2. **At project scope, apply the prefix** unless `name` already starts with it: `write ack`
   in the projectx window creates `projectx-ack.md`. If the user gives an unprefixed project name on
   purpose, say what global command it would shadow, if any (`ls <global>/hash_cmds/`), and
   write it unprefixed only after they confirm.
3. At global scope, warn when a project command of the same name exists (the project one
   will win in that project) and continue.
4. Author the body from the conversation if none was given: a command file **is the prompt**
   the model receives. Write it as instructions to the agent that will run it, in the second
   person, and say how to read the payload (see **Authoring a command** below).
5. `mkdir -p` the `hash_cmds/` dir, write the file, and echo the absolute path plus one line
   on how to run it: `#projectx-ack <payload>`.

An existing file is OVERWRITTEN only when the user asked to write that exact name; say so in
the echo. `write` never touches the other scope.

## Verb: list

`/hashcmd list [scope]` - glob `<project>/hash_cmds/*.md` and `<global>/hash_cmds/*.md`
(skipping `archive/` and `lib/`), and print one table: name, scope(s) it exists in, and
`wins` for the one the sidecar would use. A name present in both is a **collision**: mark it
and name the project file as the winner. With `scope` given, list only that scope. Nothing is
written.

## Verb: show

`/hashcmd show {name}` - print the path and full contents of the file that would win for
`#name` (project first). When both exist, add one line naming the shadowed global path. When
neither exists, say so and list near-miss names (same prefix, or a one-character difference).

## Verb: move

`/hashcmd move {name} {scope}` - `mv` the definition from its current scope into `scope`.
Refuse when the destination already has that name (never clobber; suggest `archive` first).
Moving project -> global drops nothing from the name: `projectx-ack` stays `projectx-ack` globally
unless the user asks to rename it in the same breath. Moving global -> project does NOT add
the prefix automatically; say so and offer it. Echo both paths.

## Verb: archive

`/hashcmd archive {name}` - `mv` the WINNING definition into `<its scope>/hash_cmds/archive/
<name>.md` (creating the dir). Never delete. If the move exposes a global command that the
project one had shadowed, say so. Echo the new path.

## Authoring a command

A command file is plain markdown and **is the prompt**. The sidecar wraps it:

```text
<ccvi-hash-cmd name="projectx-ack" scope="project" path="/Users/k/.ccvi/projects/.../aio/hash_cmds/projectx-ack.md">
...the file, trimmed...
</ccvi-hash-cmd>
PD-123 looks resolved
```

So the file should:

- open with one line saying what the command does;
- say how to interpret **the payload** (everything after the closing tag): positional words,
  an id, free prose, or nothing;
- give the steps, the files or tools involved, and what "done" looks like;
- say what to report back, and keep it short - the whole file rides in the turn.

A minimal template:

```text
Acknowledge a PagerDuty incident and record it in today's status.

Payload: an incident id (`PD-123`), optionally followed by a note.

1. Read ~/.ccvi/aio/status/status_<today>.md and find the incident.
2. Mark it acknowledged with the note, if any.
3. Reply with one line: the id and its new state.
```

Pages emit commands too: a page's `actions.json` maps a control to a template such as
`#projectx-ack {alertId}` (see `/pages`). Design the payload so a page can fill it from one row.

## Help output

When the user runs `/hashcmd` with no arguments (or asks what it can do), reply with exactly
this - no preamble, no postscript:

```text
/hashcmd · v0.0.29 - author and manage #commands in the aio workspace (project scope wins over global):
• write {name} [scope]   - author or overwrite <scope>/hash_cmds/<name>.md (scope: project | global; project names get the prefix)
• list [scope]           - what resolves now, collisions marked, with the winner
• show {name}            - the file that would win for #name, and its path
• move {name} {scope}    - promote to global or demote to project; never clobbers
• archive {name}         - move the winning definition to hash_cmds/archive/; never deletes

Running a command is just typing it: #name payload. Paths come from the <ccvi-aio> sentinel.
```

## What this skill does not do

- **It never runs a command.** Typing `#name` does that; the sidecar expands it.
- **It never deletes.** `archive` moves.
- **It never edits `lib/` or anything beside `hash_cmds/`** in the aio. Those are the
  commands' own files.
- **It never writes outside the two aio scopes.**
