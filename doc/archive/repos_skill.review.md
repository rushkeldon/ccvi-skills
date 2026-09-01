---
plan: "repos_skill.plan.md"
model: "claude-fable-5"
---
# Review: /repos skill - local-forge PR pipeline

**Overall: near-ready** - a well-railed plan (verified anchors, real done-whens, strong
fences, no open-questions limbo) with one internal contradiction (the spike vs. the
out-of-scope fence) and one missed build-pipeline obligation (the STAMPS table) that
would derail a literal implementer at step 4 and step 10 respectively. The agreed
resolution (per the design conversation after this review's first pass): **install
first** - move `init-verb` up, add a `run-init` todo that actually executes `/repos
init` on this machine, and let the spike and `api-tool` run against the live forge.
The findings below encode that reorder.

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ⚠️ | config's two optional positionals lack a disambiguation rule; spike/fence conflict resolved by the install-first reorder encoded below |
| Stale assumptions | ✅ | All refs verified live: `MANIFEST_SKILLS` at build.py:94 (exact), plans SKILL.md `verbs:` block exists, cleancode present, test/test_modes.py present, kind vocab {plan-file, dir, file, model, flag, freeform} matches |
| Cross-surface risk | ✅ | Shared files (build.py, plugin.json, manifest) named in step 10 with the doctrine cited; other skills fenced off |
| Rails present | ✅ | Every step has anchor + why + done-when; out-of-scope fence and escape hatch present; assumptions carry consequences |
| TODO hygiene | ⚠️ | ids unique, atomic, phased; but P2/P3 need the install-first reorder (init-verb -> run-init -> spike -> api-tool) encoded below |
| Mechanical lint | ✅ | `plan-check OK - 10 todos`; scalars quoted; `isProject: false`; no hard-coded release versions ("next version" language used); extra `humanEngineerDifficulty` key is additive and safe |

## Findings

**init-verb** `[hygiene-issue]` - Sequencing: the design decision is install-first, so
the init runbook is needed before any P2 plumbing, not in P3. Writing the section and
then immediately exercising it is also the strongest test the runbook can get - a fresh
read either works end-to-end or the section gets fixed on the spot.
Action: move `init-verb` from P3 into P2, first in the phase; then ADD a new todo
directly after it - id `run-init`, phase "P2 plumbing", content "Run /repos init on
this machine following the just-written section: brew install forgejo, localhost-only +
SQLite first-run, brew services start, admin user, org namespaces, token into
~/.config/repos/forge_token (0600), manifest.json scaffolded; fix the section wherever
the runbook and reality diverge" - with a step body noting: this todo touches the
machine (brew install, service start; nothing destructive), it is the ONE step that
cannot run unattended (admin user, org names, and token provisioning are interactive -
the user must be at the keyboard), and its DONE-WHEN is "Forgejo answers on
127.0.0.1, the token authenticates against the API, and the init section required no
further edits on a clean read-through".

**spike-resolved-flag** `[risky]` - The spike's runbook contradicted the plan's own
fence: its DONE-WHEN requires cited probe evidence from a live Forgejo, while Out of
scope said "No Forgejo installation as part of this plan's execution" - and it
suggested a throwaway `brew install forgejo`, directly violating that fence. Resolved
by the install-first reorder: `run-init` (above) puts a live forge on the machine
before the spike runs.
Action: rewrite the spike's "what to try" opening to "against the live localhost forge
that `run-init` just stood up" (drop the "after init exists / throwaway instance"
framing); note the probe uses raw `curl` with the provisioned token, since
`repos_api.py` does not exist yet at spike time; keep both branches (a)/(b) and the
DONE-WHEN as-is.

**api-tool** `[hygiene-issue]` - Ordering: todo 3 ships `forge threads` "with resolved
flag" before todo 4 (the spike) determines how that flag is derived - the field's
semantics are undefined at build time for todo 3.
Action: reorder P2 to init-verb -> run-init -> spike-resolved-flag -> api-tool, so
`forge threads` implements the resolved-flag derivation with the spike's answer already
known; add one line to the api-tool step saying the resolved field's derivation comes
from the spike's recorded branch.

**scaffold-skill** `[hygiene-issue]` - Body-consistency edits the reorder demands
(anchored here as the plan-wide todo; these are prose edits, not scaffold changes):
Action: in Out of scope, DELETE the bullet "No Forgejo installation as part of this
plan's execution" and in Conventions & assumptions ADD a bullet "init runs once during
this plan's execution (`run-init`), on this machine - macOS/brew, localhost-only,
nothing destructive; the user is present for its interactive steps"; in Verification,
change the end-to-end behavioral proof from deferred ("post-/repos init, i.e. after the
user runs init") to a live verification step of THIS plan (the forge is up after
`run-init`): open a PR on a scratch repo, post a comment, resolve it, post another,
export with `dryRun` - the dry run must list exactly the one unresolved comment.

**manifest-and-bbp** `[hygiene-issue]` - Step 10 wires only `MANIFEST_SKILLS`, but
build.py has a second per-skill registry the plan misses: the `STAMPS` table
(build.py:56), one entry per skill help display (`/plans · v{v}`, `/cleancode · v{v}`,
...). Without a repos entry, the new skill's help output never gets version-stamped
(silently breaking the sibling convention); with an entry but no matching `/repos ·
vN.N.N` display in the SKILL.md, `stamp()` raises SystemExit and every build fails.
Action: add to manifest-and-bbp: "append a STAMPS entry for
plugin/skills/repos/SKILL.md matching `/repos · v\d+\.\d+\.\d+`"; and add to
scaffold-skill's Help output content: "the cheat-sheet header opens `/repos · v0.0.0`
(any version - build.py stamps it)". ALSO add to manifest-and-bbp a ride-along fix
already made in prose but blocked from code by plan mode: the plans SKILL.md `[out]`
default for review/verify changed from `./` to "the plan file's own directory" (edited
2026-08-31, uncommitted in plugin/skills/plans/SKILL.md); flip the two matching
manifest defaults in build.py - `_param("out", False, "dir", "./")` at the review and
verify entries under the plans skill in MANIFEST_SKILLS - to the same semantics
(default "plan-dir"), in the same commit as this plan's build, per the manifest-drift
doctrine in CLAUDE.md.

**config-verb** `[hygiene-issue]` - `/repos config {kind} [origin] [value]` puts two
optional positionals in sequence with no disambiguation rule: is `/repos config
template ./my-template.md` an origin or a value? A low-reasoning implementer must
guess. Same section: the manifest schema allows ONE kind per param, but `value` is a
file for template/directions and a branch name for base - step 10 says
"template/directions paths are file" without resolving what kind `value` actually gets.
Action: state the disambiguation rule in the config section (e.g. "origin is recognized
by URL shape - contains `://` or `git@`; anything else in that slot is the value") and
pin `value` to kind `freeform` in the manifest entry with a one-line note that its
file-ness depends on `kind`.

**open-verb**, **review-verb**, **status-verb**, **export-verb** `[ready]` - terse
roll-up: verified anchors, decided semantics, behavioral done-whens, no open choices
beyond the items above.
