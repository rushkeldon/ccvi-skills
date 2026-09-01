---
name: "repos: guide the user through forge account setup, including git credentials"
version: "1.0"
overview: "The repos skill's init runbook establishes a Forgejo REST API token but never establishes git credentials for the forge remote, so the first /repos open fails at its push with 'could not read Username'. Add a credential step that lets the user choose HTTPS-plus-helper or SSH, back it with a new check-git-credentials subcommand that reports and remediates in one exit code, rewrite the browser-side steps to say what the forge account actually is, and make open fail fast instead of at the push."
todos:
  - id: tool-check-subcommand
    content: "Add `forge check-git-credentials` to plugin/skills/repos/tools/repos_api.py - reports helper, keychain entry, and ls-remote result, then prints the next action"
    status: completed
    phase: "Tool"
  - id: tool-selftest-case
    content: "Extend repos_api.py selftest to cover the new subcommand's pure decision logic"
    status: completed
    phase: "Tool"
  - id: init-credential-step
    content: "Insert a git-credentials step into the init runbook as step 7, renumbering Config root to 8"
    status: completed
    phase: "Skill prose"
  - id: credential-choice-dialog
    content: "Specify that the credential step presents the HTTPS-vs-SSH choice as prose plus AskUserQuestion rather than prescribing one"
    status: completed
    phase: "Skill prose"
  - id: rewrite-init-account-steps
    content: "Rewrite init steps 4, 5 and 6 to explain what the forge account is and give each a self-check the user can run"
    status: completed
    phase: "Skill prose"
  - id: open-preflight
    content: "Add a fail-fast credential preflight to the open verb, ahead of its base-sync push"
    status: completed
    phase: "Skill prose"
  - id: build-check
    content: "Run python3 build.py --check and confirm no version bump or verbs-block change is needed"
    status: completed
    phase: "Verification"
isProject: false
---

# repos: guide the user through forge account setup, including git credentials

## Problem / Context

`/repos init` walks seven steps and ends with a working Forgejo instance, an admin user, orgs,
an API token at `~/.config/repos/forge_token`, and a manifest. Then the **first `/repos open`
fails**, reproduced 2026-09-01 against a live instance:

```text
fatal: could not read Username for 'http://127.0.0.1:3000': Device not configured
```

The forge repo was created and the `forge` remote was wired; the failure is at step 4's
`git push forge origin/<base>:refs/heads/<base>`. Nothing in the runbook ever established
**git** credentials for the forge remote - only the REST API token, which git does not use.

This is not an edge case. It is the guaranteed outcome of a correct `init` followed by a
correct `open`, on every machine, for every repo. The runbook is missing a step.

Two smaller things surfaced alongside it, in the same area:

1. **The browser-side steps under-explain the account.** Steps 4, 5 and 6 say "the user fills
   the form" and leave the rest implicit - that the forge login is its own identity unrelated
   to any GitHub account, that an access token doubles as the git password, and that step 4's
   own verify is circular ("via the API with the token from step 6", which does not exist yet).
2. **The failure surfaces late.** `open` discovers it at a push, several steps in, after
   creating a repo on the forge and mutating the local remote set.

Machine state that shaped the design, all verified on the reference machine:

| Fact | Evidence |
| --- | --- |
| `osxkeychain` is already active machine-wide | `git config --show-origin --get-all credential.helper` → `file:/Applications/Xcode.app/Contents/Developer/usr/share/git-core/gitconfig  osxkeychain` |
| No helper is set in `~/.gitconfig` | `git config --global --list` shows only `user.*` |
| GitHub-proper creds already live in the keychain | `security find-internet-password -s github.com` → `acct=rushkeldon`, `ptcl=htps` |
| Enterprise GitHub is SSH-only | `~/.ssh/config` has `Host github.twdcgrid.net` + `IdentityFile`; no keychain entry |
| Forge SSH is not listening | nothing on TCP 222 |

The first row is the important one: **the helper is inherited from Xcode's gitconfig**, not
from the user's own config, so "is a helper configured?" looks false to anyone checking
`--global` and is actually true. A human debugging this will reach the wrong conclusion; that
is exactly the kind of thing a tool should answer rather than prose.

## Approach

**Verify with a subcommand, not with prose.** `repos_api.py` grows
`forge check-git-credentials`. It answers three questions in one run and one exit code, then
prints the next action. This is the tool's first `git` shell-out, which contradicts the
current "push is the CALLER's job" division - accepted deliberately: the goal is ease of
setup, and the check's value is the *remediation*, which prose makes the agent re-derive and
therefore get wrong differently each time.

**Let the user choose the mechanism.** The credential step does not prescribe HTTPS or SSH.
It explains the problem space in prose - what each mechanism costs, what already exists on
this machine - and then asks with `AskUserQuestion`. HTTPS-plus-helper is the recommended
option because on a machine like the reference one it needs *no* configuration change at all;
SSH is the real alternative for anyone who would rather keep tokens out of git entirely, at
the cost of a forge server change. Neither is right for everyone, which is why it is a
question rather than a prescription.

**The credential itself never transits the agent.** Same rule that already governs steps 4
and 6. The skill states what is needed and waits; the user either does one interactive push
(git prompts, they paste username and token, the helper stores it) or runs a printed
`git credential approve` one-liner substituting their own token.

**Fail fast in `open`.** The preflight runs the new subcommand *before* `ensure-repo`, so a
credential problem costs nothing and mutates nothing.

## Conventions & assumptions

- **Two files change:** `plugin/skills/repos/SKILL.md` and
  `plugin/skills/repos/tools/repos_api.py`. Nothing else.
- **`repos_api.py` is zero-dependency python3**, prints JSON to stdout, exits 0/1, and dies
  through its existing `_die` helper. Match that shape - no new imports beyond `subprocess`
  and what is already imported.
- **macOS only.** The skill already states this (`brew`, "macOS is the only target"), so the
  keychain probe via `security find-internet-password` is in-contract. Where that binary is
  absent, report the keychain check as `unknown` rather than failing the whole run.
- **Never print a secret.** `security find-internet-password` without `-w` returns metadata
  only; keep it that way. The subcommand's output must be safe to paste into a chat log.
- **`GIT_TERMINAL_PROMPT=0`** on every git invocation the tool makes, so a missing credential
  fails immediately instead of hanging on a prompt that no agent can answer.
- **Assumes the `forge` remote may not exist yet** when the check runs (the `open` preflight
  runs before the remote is wired). Take the forge URL from the manifest's `forge_url` and
  check reachability against the instance, not against a named remote; where a `forge` remote
  *does* exist, prefer `git ls-remote forge`. If this assumption is wrong for some caller,
  the step's fallback path still yields a usable verdict.
- **Assumes the help cheat-sheet text is unchanged**, so no version bump is needed:
  `build.py` stamps the canonical version into each skill's help header, and this plan adds no
  top-level verb. If the cheat-sheet does change, `build.py` must be re-run and the plugin
  version bumped - that is a different task.
- **The frontmatter `verbs:` block mirrors top-level verbs only** (`init`, `config`, `open`,
  `review`, `status`, `export`). `check-git-credentials` is a *sub*verb of the bundled tool,
  not a `/repos` verb, so that block does not change and `build.py --check`'s verb-drift
  tripwire has nothing to catch.

## The steps

### 1. `tool-check-subcommand`

**Anchor:** in `tools/repos_api.py`, the parser assembly - the `forge = sub.add_parser("forge")`
line and the `forge.add_parser(...)` calls beneath it.

Add a fourth `forge` subcommand. It takes no required arguments; `--remote` (default `forge`)
lets a caller name a different remote.

```python
p = forge.add_parser("check-git-credentials")
p.add_argument("--remote", default="forge")
```

Its implementation answers three questions and never raises on a negative answer - a negative
answer *is* the result:

```text
helper   → git config --show-origin --get-all credential.helper
            report the value AND the config file it came from (an inherited helper from
            Xcode's gitconfig is the single most confusing case in the field)
keychain → security find-internet-password -s <forge host>   (NO -w; metadata only)
            "present" / "absent" / "unknown" when the binary is missing
push     → GIT_TERMINAL_PROMPT=0 git ls-remote <remote>       (or the forge_url when the
            remote does not exist yet); exit 0 means credentials genuinely work
```

Output shape, matching the tool's existing JSON-to-stdout convention:

```json
{"helper": "osxkeychain",
 "helper_source": "/Applications/Xcode.app/.../gitconfig",
 "keychain": "absent",
 "ls_remote": false,
 "ok": false,
 "next_action": "Run `git push forge <branch>` in your terminal once; git will prompt for a username and password. Use your forge login and an access token as the password. The helper stores it and later pushes are silent."}
```

`ok` is `ls_remote` alone - the other two fields are diagnosis, not verdict. Exit `0` when
`ok`, `1` otherwise, so a caller can branch on the exit code without parsing.

`next_action` is chosen from the diagnosis: no helper and no SSH → name both options and defer
to the user; helper present but no keychain entry → the interactive-push line above; helper
absent → point at the credential step's own dialog rather than guessing.

**Why:** the remediation is the part a human gets wrong, and the helper-source line is
information no one thinks to look for.

**Done when:** on a machine with no forge credential, the command exits 1 and its
`next_action` names a step the user can perform without reading the skill; after the credential
is seeded, the same command exits 0 with `ls_remote: true`.

### 2. `tool-selftest-case`

**Anchor:** the `selftest` subcommand and the existing case list it reports
(`{"selftest": "OK", "cases": 6}`).

Add cases for the **pure** part of the new subcommand - the diagnosis-to-`next_action`
mapping. Feed it each combination (helper present/absent × keychain present/absent/unknown ×
ls-remote true/false) and assert the chosen action. Do **not** add cases that shell to git or
to `security`; the selftest must stay hermetic, which is why the mapping is factored out as a
pure function in step 1.

**Why:** `line_from_hunk` is already covered this way, so the pattern exists; and the mapping
is the only part with real branching.

**Done when:** `python3 tools/repos_api.py selftest` reports a higher case count and still
exits 0 with no network or keychain access.

### 3. `init-credential-step`

**Anchor:** in `SKILL.md`, between the runbook items beginning
`6. **API token - the USER's step` and `7. **Config root:** scaffold`.

Insert the new step as **7**, and renumber `Config root` to **8**. Grep the file for `step 6`,
`step 7` and `steps 4 and 6` afterwards and fix every cross-reference - the admin-user step
refers forward to the token step by number.

The step's shape follows its six siblings - a do, then a *Verify*:

```text
7. **Git credentials for the forge remote - the USER's step.** The API token from step 6
   authenticates REST calls; git does not use it. Without a git credential the first
   `/repos open` fails at its push with `could not read Username`. Present the choice
   (see below), then have the user seed the credential. Credentials never transit the
   agent.
   *Verify:* `python3 tools/repos_api.py forge check-git-credentials` exits 0.
```

**Why:** this is the missing step - every correct `init` followed by a correct `open`
currently fails without it.

**Done when:** the runbook reads 1-8 with no duplicate or skipped number, and no stale
cross-reference to the old numbering remains.

### 4. `credential-choice-dialog`

**Anchor:** the body of the step added in step 3.

Specify explicitly that the step **asks rather than prescribes**: prose first, laying out the
problem space, then `AskUserQuestion`. Write the prose the skill should use, covering:

- **HTTPS plus a credential helper** - what the credential is (forge username + access token
  as the password), that the helper may already be active and inherited from a config file the
  user did not write, and that the forge is plain `http` on loopback so the exchange is
  unencrypted but never leaves the machine.
- **SSH** - keeps tokens out of git entirely, matches how many people already reach an
  enterprise host, and costs a forge *server* change: enable the SSH listener in the
  work-path `app.ini`, register a public key on the forge account, re-point the remote.

Recommend HTTPS-plus-helper first, and say why in one line: on a machine that already has a
working helper it needs no configuration change at all. Then name the two seeding routes -
one interactive push, or a printed `git credential approve` one-liner the user runs with their
own token substituted.

**Why:** the right mechanism depends on the machine and on how the user already works; the
reference machine uses HTTPS-plus-keychain for one host and SSH-only for another, and both
are correct there.

**Done when:** the step contains no sentence that picks a mechanism on the user's behalf, and
a reader can answer the question from the prose without leaving the skill.

### 5. `rewrite-init-account-steps`

**Anchor:** runbook items 4 (`Admin user`), 5 (`Org namespaces`) and 6 (`API token`).

Keep every existing instruction; add what is currently assumed:

- **What the forge account is** - a local identity on your own instance, unrelated to any
  GitHub or enterprise account, and the username half of the git credential.
- **Fix step 4's circular verify.** It currently says to verify "via the API with the token
  from step 6" - a token that does not exist yet. Replace with something checkable at that
  moment: the installer redirects to a logged-in session, or `forgejo admin user list` run by
  the user.
- **Why orgs exist** - per-origin separation inside one instance, and that the org name is
  asked for at first `open`, so choosing one now avoids a prompt later.
- **What the token is for, and what it is not for** - REST calls made by the bundled tool;
  *not* what git uses, which is why step 7 exists. One sentence, cross-referencing forward.

**Why:** every one of these is currently inferable but unstated, and the token's scope is the
misconception that produced the missing step in the first place.

**Done when:** steps 4-6 each state what the user is creating and end in a check the user can
run at that point in the sequence, with no forward reference to something not yet created.

### 6. `open-preflight`

**Anchor:** the `## Verb: open` steps list, at its item `1. **Ensure the config entry**`.

Add a preflight ahead of it:

```text
0. **Preflight credentials:** `forge check-git-credentials`. On a non-zero exit, STOP and
   surface its `next_action` - do not create the forge repo, do not touch the remote set,
   do not attempt a push. Point the user at `/repos init` step 7.
```

**Why:** the current order creates a forge repo and mutates the local remote set *before* the
step that fails, leaving half-built state behind. Nothing before the preflight is worth
keeping if credentials are absent.

**Done when:** on a machine with no forge credential, `/repos open` reports the credential
problem and the forge has no new repo and the local remote set is unchanged.

### 7. `build-check`

```bash
python3 build.py --check
```

**Why:** it verifies the stamped version displays are in sync and cross-checks verb names
against the SKILL.md prose as a drift tripwire. This plan touches neither, so it should pass
untouched - which is the point of running it.

**Done when:** exit 0. If it reports drift, the cause is a cheat-sheet or `verbs:` edit that
this plan did not intend - fix that rather than re-stamping.

## Out of scope

- **Reworking the `## Tokens` section.** It conflates the REST API token with the git
  credential, and step 5 above corrects that inline where it misleads. A full rewrite of that
  section was considered and declined for this pass.
- **Making the tool seed the credential.** It reports and instructs; the user seeds. Seeding
  would mean the token transiting the agent, which the skill forbids in steps 4 and 6 for the
  same reason.
- **Enabling Forgejo SSH by default.** It stays a documented option the user may pick, not a
  default the runbook configures.
- **Any change to `forge pr` / `threads` / `comment` / `github export`**, and any change to
  the `resolved` semantics.
- **Non-macOS support.** The skill is macOS-only by its own statement; the keychain probe
  degrades to `unknown` elsewhere rather than being made portable.
- **A `/repos` verb for credentials.** The check is a tool subverb, deliberately - adding a
  top-level verb would touch the `verbs:` block, the cheat-sheet, and the version stamp.

## Verification

1. `python3 tools/repos_api.py selftest` exits 0 with a higher case count than 6.
2. `python3 tools/repos_api.py forge check-git-credentials` exits 1 with an actionable
   `next_action` on a machine with no forge credential, and exits 0 with `ls_remote: true`
   after one is seeded.
3. The init runbook reads 1-8, and `grep -n "step [0-9]" SKILL.md` shows no reference to the
   old numbering.
4. The credential step contains the HTTPS-vs-SSH prose and an `AskUserQuestion`, and
   prescribes neither.
5. `/repos open` on a credential-less machine stops at the preflight - verified by the forge
   having no new repo and `git remote -v` being unchanged afterwards.
6. `python3 build.py --check` exits 0.
7. End to end on a clean machine: `/repos init` through `/repos open` completes without the
   `could not read Username` failure.

**Escape hatch:** if the reference facts no longer hold - the helper is not inherited from
Xcode's gitconfig, `security find-internet-password` behaves differently, `git ls-remote`
succeeds anonymously against the forge - **STOP and surface it. Do not improvise**; the
diagnosis-to-remediation mapping in step 1 is built on those facts.
