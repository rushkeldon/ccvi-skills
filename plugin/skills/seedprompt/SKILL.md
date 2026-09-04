---
name: seedprompt
description: write•read•show•clear - author, consume, inspect, or clear a one-use AI-to-AI session hand-off ("seed prompt") at <memoryRoot>/seedprompt.md - the reliable authoring path to the one well-known file the CCVI sidecar auto-injects and deletes. Use when the user asks to write a seed prompt / hand-off for the next session (or after a /compact), to read/consume the pending one into this session, or to show or clear it.
argument-hint: "[verb]"
allowed-tools: Read, Write, Bash(printenv:*), Bash(rm:*)
---

# seedprompt

Author a **seedprompt** — a one-use, device-local, AI-to-AI **session hand-off**. The CCVI
sidecar reads the seed after the next session's first turn
(or across a `/compact`), **deletes** it (one-use), and injects its body as a second turn so
continuity crosses the session boundary automatically. **If the sidecar does not pick the seed
up** (it is not running, or the session starts outside CCVI), the skill still works: the seed
sits at the one well-known path, and the next session (or
the user) consumes it from there — `/seedprompt read` retrieves it and deletes it in one step,
preserving the one-use semantics. This skill is the **reliable authoring surface**: it always writes
to that one well-known path, so the hand-off can never be stranded in `doc/` or a session
subdirectory the way a hand-authored file guesses wrong.

The skill **writes / reads / shows / clears** the seed. write never consumes;
**read is the explicit manual consume path** (print + adopt + delete, the equivalent of the
sidecar's inject-and-delete); show stays non-destructive. Consume-and-delete otherwise belongs
to the consumer (the CCVI sidecar; if it does not fire, the next session or the user). See
**The mechanism** at the bottom.

## Invocation

Single entry point — **`/seedprompt [verb] [args]`**, dispatching on the first arg:

| Form | Effect |
|---|---|
| `/seedprompt write [body]` | Author the pending seed at `<memoryRoot>/seedprompt.md` (overwrites any existing one) |
| `/seedprompt read` | Consume the pending seed: print its path + contents, adopt the body as this session's hand-off brief, then delete it (one-use); or `none pending` |
| `/seedprompt show` | Print the pending seed's absolute path + contents, or `none pending` |
| `/seedprompt clear` | Delete the pending seed (best-effort; `none pending` if absent) |
| `/seedprompt` (blank/unknown verb) | Print the help cheat-sheet (see **Help output**) |

Verbs are lowercase. Recognize natural-language equivalents: "write a seed prompt / hand-off for the
next session" → `write`; "read/consume/load the seed" → `read`; "show/what's the pending seed" →
`show`; "clear/delete the seed" → `clear`.

## Path resolution (the reliability crux)

The seed is **always** written to **`<memoryRoot>/seedprompt.md`** — a **project-level** file:

- `<memoryRoot>` is the **auto-memory directory named in the system prompt** (the parent of the
  per-session `<session_id>/` dirs — the *same* anchor the `modes` skill uses for `active_modes.md`).
  Resolve it once from context; do not guess.
- The seed sits **beside `MEMORY.md`**, directly in `<memoryRoot>/`.

Three "not" cases — these are the exact historical failure modes, state them and avoid them:

1. **NOT** in the repo's `doc/` (or anywhere in the working tree). No consumer reads there.
2. **NOT** inside a `<session_id>/` subdirectory. The seed is project-level, one per project, not
   per-session. (This is where it differs from `modes`, whose `active_modes.md` *is* per-session.)
3. **NOT** `MEMORY.md` or any other memory file — the filename is exactly `seedprompt.md`.

**Fallback** (only if the auto-memory dir isn't derivable from the system prompt): compute
`~/.claude/projects/<encode(cwd)>/memory/seedprompt.md`, where `<encode(cwd)>` replaces **every
non-alphanumeric character** of the absolute working-directory path with `-` (the same encoding
Claude Code uses for project dirs; this matches the CCVI host's
`encodeProjectDir`). E.g. cwd `/Users/keldon/Desktop/working/ccvi-idea`
→ `-Users-keldon-Desktop-working-ccvi-idea` → `~/.claude/projects/-Users-keldon-Desktop-working-ccvi-idea/memory/seedprompt.md`.

Echo the **resolved absolute path** on every `write` — that echo is the anti-misfire feedback.

## The seed file format

A seed is **an optional YAML frontmatter directive block, then a markdown body**:

```markdown
---
title: "<3-6 words naming what the next session will do>"
---
<the hand-off body — first-person, to the next you>
```

- **Always emit `title:`.** This is the one directive you write *unasked*, on every `write`: a
  3-to-6-word description of what the NEXT session will be working on, quoted. The incoming
  session may run start-to-finish with nobody typing into it, and this is what names it in the
  History list — you are the best-informed narrator of what it is about to do, and this costs
  nothing (no model call, no turn). Write intent, not a summary of the past: "AVM1 parseInt
  surface", not "continuing the work". A generated title supersedes it later if the session
  drifts, so it is a floor, not a verdict.
- **Otherwise body-only is the norm.** Beyond `title:`, omit the frontmatter unless a caller
  explicitly passes an allowlisted directive — a consumer tolerates a missing directive block.
- **Directives are an allowlist**, enforced by the CCVI consumer: only
  keys with a **registered handler** are honored; any other key is silently ignored (never
  arbitrary execution). If the seed is consumed manually instead, directives are inert metadata
  the next session reads as context. Do **not** invent directives beyond `title:`. Quote every value
  (`key: "value"`).
- **The body** is a concise first-person hand-off *to the next instance of yourself*: **what we're
  doing, the current state, the immediate next step, and any load-bearing decisions.** Write it the
  way you'd want to be briefed cold — enough to resume without re-deriving intent.

## Handling a directive

1. **Resolve `<memoryRoot>`** per **Path resolution** (auto-memory dir from the system prompt; else
   the cwd fallback). The target is `<memoryRoot>/seedprompt.md`.
2. **Dispatch on the verb:**
   - **`write [body]`** — if `[body]` is given inline, use it verbatim as the body; otherwise
     **compose** the first-person hand-off from the current conversation (the four beats above).
     Write the file with a `title:` directive always, plus any explicitly-requested
     allowlisted directive. **Overwrite**
     any existing pending seed — a newer hand-off supersedes an unconsumed older one. **Never delete
     on write** (deletion belongs to whoever consumes, at consume time).
   - **`read`** — if `<memoryRoot>/seedprompt.md` exists: print its absolute path and full
     contents, state that the body is now this session's active hand-off brief (directives are
     inert here — report `title:` as context, execute nothing), then delete the file. Else print
     `none pending`.
   - **`show`** — if `<memoryRoot>/seedprompt.md` exists, print its absolute path and full contents;
     else print `none pending`.
   - **`clear`** — delete `<memoryRoot>/seedprompt.md` if present (best-effort); echo what happened,
     or `none pending` if it wasn't there.
   - **blank / unrecognized verb** — print the **Help output** (no file access).
3. **Echo** (see below). The echo is the whole response — no preamble.

## Echo contract

- **`write`** →
  ```text
  seed written → <absolute path to seedprompt.md>
  the CCVI sidecar will inject it as a turn on the next new session (or after /compact), then delete it (one-use); if it doesn't fire, point the next session at this file.
  ```
- **`read`** → the absolute path on its own line, a fenced block of the contents, then the line
  `seed consumed → deleted (one-use)`; or `none pending`.
- **`show`** → the absolute path on its own line, then a fenced block of the contents; or `none pending`.
- **`clear`** → `seed cleared → <absolute path>` or `none pending`.

## Help output

When the verb is blank or unrecognized, reply with exactly this — no preamble, no postscript:

```text
/seedprompt · v0.0.15 — author a one-use AI-to-AI session hand-off (the CCVI sidecar injects it as a turn on the next session then deletes it; if it doesn't fire, point the next session at the file):
• write [body] — write the pending seed to <memoryRoot>/seedprompt.md (compose from context if no body given)
• read         — consume the pending seed: print + adopt it, then delete (one-use)
• show         — print the pending seed's path + contents (or "none pending")
• clear        — delete the pending seed

The seed is project-level: it lives at <memoryRoot>/seedprompt.md (beside MEMORY.md) — never in doc/, never in a <session_id>/ subdir.
```

## When tools are denied

If `Write` (or the `clear` delete) is denied at runtime, don't fail silently: print the exact intended
file contents + absolute path and ask the user to save it there themselves. Suggest the minimum
settings change (e.g. allow `Write` under the auto-memory directory). The happy path stays quiet.

## The mechanism (context — do not re-implement here)

**The consumer is the CCVI sidecar**
(`sidecar/src/seedprompt.ts`): it reads `<memoryRoot>/seedprompt.md` on session init /
compact-boundary, **deletes** it, runs any registered allowlisted directives, and injects the body
as a host-authored turn. This skill is *only* the writer/reader — it must land the file at exactly
the well-known path so any consumer (automated or manual) finds it. There is no other reliable
writer (the old relay authoring path was removed with the teleprompt engine), so this skill is the
sole hand-off authoring surface.

**If the sidecar does not consume it**, nothing fires automatically — the seed waits at the
well-known path. The manual loop preserves the same semantics: the next session (or the user)
consumes it with `/seedprompt read` — the one-step form of show-then-clear (print the body, act
on it, delete the file) — so the hand-off stays one-use. The skill works identically either way;
the sidecar only automates the consume step.
