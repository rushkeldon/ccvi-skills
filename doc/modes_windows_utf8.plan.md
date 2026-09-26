---
name: modes on Windows — UTF-8 output, Windows project slug, and a harness that runs there
version: "1.0"
overview: "On Windows, modes.py crashes on any directive that prints the agent notes. Windows Python writes piped stdout as cp1252, which cannot encode the LAW block's ⛔. The crash comes after the state write, so the directive half-applies. Separately, modes.py and enforce_modes.py derive the project slug by replacing only '/', so a Windows cwd like C:\\... yields an absolute component that os.path.join lets swallow the home prefix. Today that is masked only by the cross-project glob. Fix both, and make test_modes.py run on Windows. Every change is byte-identical on macOS and Linux."
todos:
  - id: modes-utf8-stdout
    content: "In plugin/skills/modes/scripts/modes.py main(): assemble the full output string BEFORE write_state, and emit it as UTF-8 bytes via sys.stdout.buffer (fall back to sys.stdout.write when there is no buffer)"
    status: completed
    phase: "1 - fix"
  - id: windows-project-slug
    content: "Derive the auto-memory project slug Windows-correctly in modes.py resolve_memory_root() AND hooks/enforce_modes.py resolve_active_modes_path(): replace '\\\\' and ':' as well as '/', so C:\\Users\\x\\proj becomes C--Users-x-proj (Claude Code's own directory name); POSIX output unchanged"
    status: completed
    phase: "1 - fix"
  - id: skill-fallback-stub
    content: "In plugin/skills/modes/SKILL.md 'Run the script' fallback bullets (outside any LAW block): treat the Windows Store python3 stub ('Python was not found', exit 49 or 9009) like 'python3 not installed', so it gets the install nudge"
    status: completed
    phase: "1 - fix"
  - id: harness-windows
    content: "Make test/test_modes.py run on Windows: subprocess.run(..., encoding='utf-8') in run() and run_hook(), set USERPROFILE as well as HOME to the temp home, open() with encoding='utf-8', and slug_for() using the same rule as the scripts"
    status: completed
    phase: "2 - guard"
  - id: harness-cp1252-guard
    content: "Add test_modes.py checks that run modes.py with PYTHONIOENCODING=cp1252 (a Windows pipe, simulated on any OS) and assert exit 0, and that the stdout bytes decode as UTF-8 and contain the ⛔ LAW line; plus a slug check for a Windows-shaped cwd"
    status: completed
    phase: "2 - guard"
  - id: bbpi
    content: "BBPI per CLAUDE.md: bump plugin/.claude-plugin/plugin.json to the next patch, python3 build.py, then build.py --check and test/test_modes.py both exit 0, push, unzip into ~/.ccvi/ccvi-skills/plugin/, and confirm the installed plugin.json version"
    status: completed
    phase: "3 - ship"
  - id: verify-live-windows
    content: "In the NEXT Claude Code session on the Windows machine (after IDEA restarts so python3 is on PATH): run /modes plan doc, then /modes agent. Both print the echo from the script (exit 0, no fallback) and active_modes.md is correct. In plan mode, a Write to a .ts file is denied by the hook"
    status: in_progress
    phase: "4 - verify"
isProject: false
---

# modes on Windows — UTF-8 output, Windows project slug, and a harness that runs there

## Problem / Context

Found on the Windows machine on 2026-09-26, while the ccvi-idea Windows port ran `/modes plan doc`
against the installed suite:

```text
modes.py error: 'charmap' codec can't encode character '\u26d4' in position 25: character maps to <undefined>
```

1. **Encoding.**
   - Windows Python writes piped stdout in the ANSI code page (cp1252), and the Bash tool's stdout
     is always a pipe. The LAW blocks contain `⛔` (U+26D4), which cp1252 cannot encode.
   - Every directive whose agent notes carry a LAW block therefore crashes. `list` happens to
     survive because its output only uses `•`, which cp1252 has.
   - macOS and Linux default to UTF-8 and are unaffected.
2. **Half-applied directive.**
   - `main()` calls `write_state()` BEFORE it writes stdout, so on Windows the mode changes and
     the script then exits 1.
   - The model then takes the SKILL.md fallback, which reads the ALREADY-UPDATED file and can
     echo the wrong prior state (`already active`, no `is now inactive` line).
3. **Windows project slug (latent).**
   - `resolve_memory_root()` (modes.py) and `resolve_active_modes_path()` (enforce_modes.py)
     build the slug with `cwd.replace("/", "-")`. For `C:\Users\keldon\Desktop\working\ccvi-idea`
     that leaves an absolute `C:\...` component.
   - `os.path.join(home, ".claude", "projects", <that>, "memory")` then DISCARDS the home prefix.
     Measured: `join('C:\\Users\\k', '.claude', 'projects', 'C:\\Users\\k\\proj', 'memory')` →
     `C:\Users\k\proj\memory`.
   - It works today only because the CCVI host seeds `active_modes.md` first, so the
     cross-project glob finds it.
   - Without that seed, modes.py would create `memory\<sid>\` INSIDE the project, and the hook
     would find nothing and fail open, which means no enforcement.
   - Claude Code's own directory for that cwd is `C--Users-keldon-Desktop-working-ccvi-idea`
     (observed in `%USERPROFILE%\.claude\projects`).
4. **The harness is blind on Windows.**
   - `python test\test_modes.py` fails at `aloop/encode-ask-ordering` with `ValueError: substring
     not found`: the script crashed, so there were no notes to search.
   - `subprocess.run(..., text=True)` would also decode with cp1252.
   - The harness sets `HOME`, but on Windows `os.path.expanduser("~")` reads `USERPROFILE`. The
     temp home is ignored, and a run could touch the real `~\.claude`.

`enforce_modes.py` has no encoding problem: it replies with `json.dump`, which is ASCII-escaped by
default. It shares the slug bug (item 3).

**Decided (user, 2026-09-26):** fix it in place (option A). Porting the scripts to CCVI's captive
Node is a separate, later decision and out of scope here.

## Approach

- **Output:** make the output encoding explicit instead of inheriting the platform default.
  `modes.py` assembles its whole output as one string, writes state, then emits
  `text.encode("utf-8")` through `sys.stdout.buffer`. On macOS/Linux that is exactly the bytes they
  emit today.
- **Slug:** replace `\` and `:` as well as `/`. On POSIX, a cwd contains neither, so the slug is
  unchanged.
- **Harness:** decode UTF-8 explicitly, point both home variables at the temp dir, and gain a
  cp1252-forced check, so the guard also fails on a Mac if the fix regresses.

## Conventions & assumptions

- **LAW blocks are byte-locked** (CLAUDE.md). Nothing here edits inside `<!-- LAW:… -->`; the ⛔
  stays. The SKILL.md edit is in the fallback bullets under "Run the script", which are outside
  both LAW blocks.
- **Two copies of the slug rule, on purpose.** The hook and the script are separate programs in
  different directories. Keep them identical, each with a comment naming the other ("mirrors
  enforce_modes.py" / "mirrors scripts/modes.py").
- **`MIN_CHECKS` only goes up.** This plan adds checks and never removes or re-points one.
- **Assumption:** Claude Code's slug for a Windows cwd replaces `\` and `:` with `-` (evidence: the
  `C--Users-…` dirs under `%USERPROFILE%\.claude\projects`). If a user's path contains other
  characters Claude Code rewrites (e.g. `_` or `.`), the primary path still misses and the existing
  glob fallback still rescues reads, exactly as today. Matching Claude Code's full rule is out of
  scope.
- On Windows until IDEA restarts, `python3` may not be on the agent's PATH. Use
  `%LOCALAPPDATA%\Programs\Python\Python313\python3.exe` explicitly for build.py and
  test_modes.py.
- **Escape hatch:** if any anchor below does not match the code, STOP and surface it. Do not
  improvise.

## The steps

### modes-utf8-stdout
Anchor: `def main(argv):` in `plugin/skills/modes/scripts/modes.py`.
- Move the `out = [AGENT_DELIM] … "\n".join(out) + "\n"` assembly ABOVE the `if should_write and
  session_dir is not None: write_state(...)` block, into a local `text`.
- After the write, emit through a small helper:

  ```python
  def emit(text):
      # Explicit UTF-8: Windows Python writes piped stdout as cp1252, which cannot encode the
      # LAW blocks' ⛔. Bytes bypass the platform default; on macOS/Linux they are what
      # sys.stdout already produced.
      data = text.encode("utf-8")
      buf = getattr(sys.stdout, "buffer", None)
      if buf is not None:
          buf.write(data)
          buf.flush()
      else:
          sys.stdout.write(text)
  ```

- **Why:** a directive must either fully apply or not apply at all, and output must not depend on
  the OS code page.
- **Done when:** on Windows, `python3 modes.py "plan doc"` (with `CLAUDE_CODE_SESSION_ID` set)
  exits 0 and prints the ⛔ LAW line. On macOS, the output bytes are identical before and after
  (compare with `cmp`).

### windows-project-slug
- **Anchors:** `slug = cwd.replace("/", "-")` in `resolve_memory_root()`, and
  `slug = (cwd or os.getcwd()).replace("/", "-")` in `resolve_active_modes_path()`.
- **Change both to:** `.replace("\\", "-").replace(":", "-").replace("/", "-")`, with the mirror
  comment.
- **Why:** a Windows cwd must yield a relative slug so `os.path.join` keeps the home prefix.
- **Done when:** for `C:\Users\x\proj` the slug is `C--Users-x-proj`, and for
  `/Users/x/proj` it is `-Users-x-proj`, the same as before.

### skill-fallback-stub
- **Anchor:** the bullet beginning `- **\`python3\` not installed** (shell "command not found" /
  exit 127)` in `plugin/skills/modes/SKILL.md`.
- **Change:** add the Windows Store alias stub: output `Python was not found`, exit 49 (9009 from
  cmd).
- **Why:** on Windows the "not installed" case looks like this, and the nudge should fire.
- **Done when:** the bullet names both forms, and `build.py --check` passes.

### harness-windows
Anchors: `def run(`, `def run_hook(`, `def slug_for(` in `test/test_modes.py`.
- `subprocess.run(..., capture_output=True, encoding="utf-8")` instead of `text=True`, in both
  run functions.
- `env["USERPROFILE"] = home` beside `env["HOME"] = home`, in both.
- Every `open(...)` gets `encoding="utf-8"`.
- `slug_for(path)` applies the same three replacements as the scripts.
- **Done when:** `python3 test/test_modes.py` exits 0 on Windows, and still exits 0 on macOS.
- **STOPPED (2026-09-26, escape hatch):** edits applied; 122/124 pass on Windows. `hook/include-allows-nested` and `hook/include-allows-shallow` fail: a real hook bug, not in this plan. `candidate_paths()` relpath yields `src\deep\a.ts` while `glob_to_regex` matches only `/`. Needs a decision before the harness can exit 0.
- **RESOLVED (orchestrator, user-authorized, 2026-09-26):** approved the fix. It landed, plus two native-separator checks (`MIN_CHECKS` 133). 133/133 on Windows.

### harness-cp1252-guard
New checks in `main()` of `test/test_modes.py`, alongside the existing `check(...)` calls:
1. Run `modes.py "plan doc"` with `env["PYTHONIOENCODING"] = "cp1252"`. Capture BYTES: a variant
   of `run()` that omits `encoding=` and passes neither `text` nor `encoding`, returning
   `proc.stdout` bytes. Assert:
   - `returncode == 0`;
   - `stdout.decode("utf-8")` succeeds;
   - the decoded text contains `⛔ PLAN MODE`.
   Name it e.g. `win/cp1252-stdout`.
2. Call the slug logic (import `modes_mod`, or factor a `project_slug(cwd)` helper out of both
   files, with the mirror comment) on `C:\Users\x\proj` and `/Users/x/proj`. Assert the two
   expected slugs. Name it e.g. `win/slug`.
- **Why:** this regression must fail on ANY OS, not only on the machine that exposed it.
- **Done when:** both checks pass, and temporarily reverting the `emit()` change makes check 1
  fail. Record that you saw it fail.

### bbpi
Per `CLAUDE.md` "BBP / BBPI":
1. Bump `plugin/.claude-plugin/plugin.json` to the next patch version.
2. `python3 build.py`. Then `python3 build.py --check` and `python3 test/test_modes.py` must both
   exit 0.
3. Commit with a message describing the fix, and push.
4. Extract the zip into `~/.ccvi/ccvi-skills/plugin/`. On Windows without `unzip`, use
   `Expand-Archive -Force ccvi-skills.zip $env:USERPROFILE\.ccvi\ccvi-skills\plugin`, or Python's
   `zipfile`.
- **Done when:** the installed `plugin.json` shows the new version.
- **NOT STARTED (2026-09-26, escape hatch):** blocked on two things.
  - The harness does not exit 0; see the `harness-windows` STOPPED note.
  - A Windows `build.py` produces a non-canonical zip. `zipfile.ZipInfo.create_system` defaults to 0
    (MS-DOS) there and 3 on POSIX, so a Unix unzip drops the exec bits. With LF sources plus
    `info.create_system = 3`, the Windows build is byte-identical to HEAD's Mac-built zip.
  - Also build from an LF working tree: this checkout has `core.autocrlf=true` and no
    `.gitattributes`, and `zip_bytes` reads raw bytes.
- **Decisions (orchestrator, user-authorized, 2026-09-26):**
  - **Hook separators:** `candidate_paths()` normalises `os.sep`/`os.altsep` to `/`; a no-op on POSIX.
  - **Zip host:** `build.py` sets `info.create_system = 3`. Built from HEAD's LF sources, it reproduces HEAD's zip byte for byte.
  - **LF:** added `.gitattributes` `* text=auto eol=lf` (as in ccvi-idea 5e02a33) plus `git add --renormalize .`. No git config change.
  - **Stamp writes (builder, under the byte-identity requirement):** `build.py` `_write()` now uses `newline="\n"`. Text mode on Windows had turned stamped files, and so 6 zip members, into CRLF.
- **DONE:** v0.0.23, commit 8178395, pushed. `--check` OK, 133/133. The installed plugin.json reads 0.0.23.

### verify-live-windows
- **Awaits a fresh Claude Code session on Windows** (`bbpi` has shipped 0.0.23). A plan-builder agent cannot run this todo.
In a NEW session on the Windows machine:
- **Directives:** `/modes plan doc` and then `/modes agent` each end with the script's echo. There
  is no `Installing python…` line and no fallback. `active_modes.md` holds `- plan: doc`, then
  `- agent`.
- **Hook:** in plan mode, ask for a trivial `.ts` edit. The PreToolUse hook denies it with the
  plan-mode reason. This proves the hook resolves the state file through the fixed slug.
- **Done when:** both behaviors are observed. Record the log lines or echo in the commit message
  or plan body.

## Out of scope

- **Porting `modes.py`/`enforce_modes.py` to Node** (the captive `~/.ccvi/node`). It is a separate
  decision, because it changes the `plugin.json` hook contract and needs a stable launcher from
  ccvi-idea.
- **Any edit inside a LAW block,** including replacing ⛔ with ASCII.
- **Matching Claude Code's complete slug rule** beyond `\` and `:`.
- **ccvi-idea changes.** The CCVI sidecar's own modes loader is unaffected.

## Verification

- `python3 test/test_modes.py` exits 0 on Windows and on macOS, and the check count rose.
- `python3 build.py --check` exits 0.
- On macOS: `modes.py "plan doc"` stdout is byte-identical before and after the change.
- `verify-live-windows` observed on the Windows machine.
