---
humanEngineerDifficulty: 1
name: Rename the retired project name to projectx everywhere
version: "1.0"
overview: "Replace every instance of the retired project name (matched by the pattern d[p]p) with projectx across the whole working tree: shipped skill examples, a script's comments, CLAUDE.md, live plans, and the archive. Rebuild the zip so the artifact is clean too, then BBPI."
todos:
  - id: sweep-replace
    content: "Replace every d[p]p with projectx in the 10 files listed in the plan body"
    status: completed
  - id: verify-zero
    content: "Prove zero survivors in the working tree (case-insensitive grep, filenames included)"
    status: completed
  - id: rebuild-test
    content: "Run build.py, then build.py --check, test_modes.py, and test_autoprompt.py; all exit 0"
    status: completed
  - id: zip-zero
    content: "Prove the rebuilt ccvi-skills.zip contains zero survivors"
    status: completed
  - id: bbpi
    content: "BBPI: bump plugin.json, build, commit and push to main, install into ~/.ccvi/ccvi-skills/plugin/"
    status: completed
isProject: false
---

# Rename the retired project name to projectx everywhere

## Problem / Context

The suite uses the name of one of Keldon's other projects as its stand-in example project.
It appears most heavily in the `/aio` skill (the `<ccvi-aio>` sentinel example, the prefix
doctrine, and the `#...-ack` hash-command examples), and also in `/autoprompt` examples,
two `autoprompt.py` comments, the `CLAUDE.md` contract example, two live plans, and the
archive. Keldon wants **no surviving instance anywhere** in the repo, history docs included.

This plan never spells the retired name. It is written as the grep pattern `d[p]p`, which
matches the name but not itself, so this file can't become a survivor.

## Approach

Do one mechanical, case-sensitive, global substitution of `d[p]p` with `projectx` in the
10 affected files. The inventory taken 2026-11-10 found **every hit lowercase**, with **no
filename** containing the name. Compound forms map consistently and need no special
handling: `<name>-skills` becomes `projectx-skills`, `<name>_api.py` becomes
`projectx_api.py`, `~/.<name>` becomes `~/.projectx`, `<name>-ack` becomes `projectx-ack`,
`-Users-k-Desktop-working-<name>` becomes `-Users-k-Desktop-working-projectx`, and so on.

`projectx` was chosen because it is an obvious placeholder that means nothing else in the
suite. In particular it is not `aio`, which already names the skill, the workspace
directory, and the html route.

## Conventions & assumptions

- **The substitution is the whole change.** Do not reword the surrounding prose, even where
  history docs now read oddly (e.g. a `projectx-skills` plugin that never existed under that
  name). Keldon accepted this tradeoff explicitly.
- **Assumes all hits are lowercase.** If the grep in step 1 shows any uppercase or mixed-case
  form, STOP and surface it. Do not improvise a mapping.
- **Assumes the 10-file list is complete.** If step 1 finds a file not on the list, STOP and
  surface it.
- `/Users/k/` in the examples is already anonymized. Leave it.
- macOS BSD `sed` needs `-i ''`.

## The steps

### 1. Sweep (`sweep-replace`)

Re-inventory first, then replace. Run from the repo root:

```bash
grep -rlI -i 'd[p]p' --exclude-dir=.git --exclude=ccvi-skills.zip . | sort
```

Expected output, exactly these 10 files (STOP if it differs):

```text
./CLAUDE.md
./doc/archive/skills/hashcmd/SKILL.md
./doc/archive/skills/pages/SKILL.md
./doc/archive/work_skill_and_plugin_merge.plan.md
./doc/archive/work_skill_and_plugin_merge.plan.review.md
./doc/autoprompt_skill.plan.md
./doc/repos_evolve.plan.md
./plugin/skills/aio/SKILL.md
./plugin/skills/autoprompt/SKILL.md
./plugin/skills/autoprompt/scripts/autoprompt.py
```

Then:

```bash
grep -rlI 'd[p]p' --exclude-dir=.git --exclude=ccvi-skills.zip . | xargs sed -i '' 's/d[p]p/projectx/g'
```

**Why** one sed over the grep's own file list: the target set and the edited set are
provably the same.

**Done when:** `git diff --stat` shows exactly those 10 files.

### 2. Prove zero in the tree (`verify-zero`)

```bash
grep -rnI -i 'd[p]p' --exclude-dir=.git --exclude=ccvi-skills.zip . ; echo "exit $?"
find . -path ./.git -prune -o -iname '*d[p]p*' -print
```

**Done when:** grep prints only `exit 1` (no matches) and find prints nothing.

### 3. Rebuild and test (`rebuild-test`)

Run this before the BBPI bump, so a failure is caught while the change is small:

```bash
python3 build.py && python3 build.py --check && python3 test/test_modes.py && python3 test/test_autoprompt.py
```

**Done when:** all four exit 0. The `autoprompt.py` change is comments only, so a test
failure means something unexpected happened. STOP and surface it.

### 4. Prove zero in the artifact (`zip-zero`)

```bash
unzip -p ccvi-skills.zip | grep -c -i 'd[p]p'; unzip -l ccvi-skills.zip | grep -ci 'd[p]p'
```

**Done when:** both print `0`. Before this change the zip held 15 matching lines.

### 5. BBPI (`bbpi`)

Run the repo ritual from `CLAUDE.md`. Bump the last segment of
`plugin/.claude-plugin/plugin.json` (currently `0.0.39`, so `0.0.40`), then
`python3 build.py`, `--check`, and `test_modes.py`. Commit with a message like
`rename the example project to projectx everywhere; v0.0.40`, and keep the commit message
free of the old name. Push to `main`, then
`unzip -o -q ccvi-skills.zip -d ~/.ccvi/ccvi-skills/plugin/`.

**Done when:** the installed `plugin.json` shows `0.0.40`, and
`grep -rIci 'd[p]p' ~/.ccvi/ccvi-skills/plugin/ | grep -v ':0$'` prints nothing.

## Out of scope

- **Git history.** Two existing commit messages and every past blob still contain the name.
  Removing them means rewriting and force-pushing `main`, which is destructive and a separate
  decision for Keldon. Do not touch history.
- **Anything outside this repo:** the other project itself, `~/.<name>/`, memory files, and
  other repos.
- **Prose rewording** of any kind (see Conventions).

## Verification

- Step 2's grep and find are empty in the working tree.
- Step 4 prints `0` for the zip.
- Step 5's grep over the live install prints nothing.
- `build.py --check`, `test_modes.py`, and `test_autoprompt.py` all exit 0.
