---
name: plans
description: Plan lifecycle verbs via /plans [verb] — write (author a plan), review (vet quality), verify (audit todo-status vs reality), update (apply a review/verify report), build (execute in place, flip todos live), archive (sweep finished plans into an archive dir). Use when the user issues a /plans directive or asks to author, review, verify, update, build, or archive a *.plan.md.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host (e.g. CCVI's plan-phase picker) that
# reads `verbs` to render the menu in lifecycle `order` and to generate each verb's
# dialog from `params`. Every fact here MUST also be stated in the prose — the skill
# stays fully usable in vanilla Claude Code (which gap-fills conversationally), and this
# block only encodes how a host COLLECTS the same facts as UI.
# param.type ∈ string | boolean | modelName (modelName → a model picker; its value is
# 'session' for inline or a model id to delegate to — see the review/build prose).
# param.suggestions is a literal list OR a host-known source token (plans|models).
# `collaborate` is the implicit baseline (order 1, no verb/dialog).
verbs:
  write:   { order: 2, params: [ { name: name, type: string, required: false } ] }
  review:  { order: 3, params: [ { name: plan,  type: string, required: true, suggestions: plans },
                                 { name: out,   type: string, required: false },
                                 { name: model, type: modelName, required: false } ] }
  verify:  { order: 4, params: [ { name: plan,  type: string, required: true, suggestions: plans },
                                 { name: out,   type: string, required: false },
                                 { name: model, type: modelName, required: false } ] }
  update:  { order: 5, params: [ { name: plan,   type: string, required: true, suggestions: plans },
                                 { name: report, type: string, required: true } ] }
  build:   { order: 6, params: [ { name: plan,  type: string, required: true, suggestions: plans },
                                 { name: model, type: modelName, required: false } ] }
  archive: { order: 7, params: [ { name: dir,        type: string, required: false },
                                 { name: archiveDir, type: string, required: false },
                                 { name: lenient,    type: boolean, required: false } ] }
---

# plans

Lifecycle verbs for Cursor-compatible `*.plan.md` files. One skill, one entry point —
**`/plans [verb] [args]`** — dispatching on the first arg. The six verbs form a
producer/consumer loop over a plan:

```diagram
   write ─▶ *.plan.md ─▶ review ─┐
                        verify ─┴─▶ report.md ─▶ update ─▶ corrected plan ─▶ build ─▶ archive
   (author)            (produce report)         (consume report)           (execute)  (sweep done)
```

Verbs are **independent atoms** — the caller composes them; **no verb auto-runs
another**. `write` authors a plan; `review`/`verify` produce a report; `update` consumes
one; `build` executes a plan and `archive` sweeps the finished ones away.

## Invocation

| Form | Effect |
|---|---|
| `/plans write [name]` | **Author** the plan being discussed into a `*.plan.md` |
| `/plans review [plan.md] [out] [model]` | Vet the plan's **quality** → write a report card |
| `/plans verify [plan.md] [out] [model]` | Audit each todo's **status vs. reality** → write a report card |
| `/plans update [plan.md] [report.md]` | Apply a review/verify report back into the plan |
| `/plans build [plan.md] [model]` | Execute the plan **in place**, flipping todo statuses live |
| `/plans archive [dir] [archiveDir] [lenient]` | Sweep finished plans (todos all terminal) from the top level of `[dir]` into `[archiveDir]` |
| `/plans` (blank/unknown verb) | Print the help cheat-sheet (see **Help output**) |

**Casing:** plain verbs are lowercase; a verb naming a proper-noun/initialism target
would be camelCase, but the current set has none — all six verbs are plain lowercase.
(Same cross-skill rule as the `modes` skill.)

**Argument resolution (all verbs):** if `[plan.md]` is omitted, resolve it — if exactly
one `*.plan.md` is in scope (cwd or an obvious plan dir) use it; if several, ask which;
if none, say so and stop. Expand `~`, normalize relative paths against the cwd.

**Portability:** every verb is **editor-agnostic** — filesystem + reasoning only. They
work on plan files anywhere: a repo copy, a Cursor copy, or a future IntelliJ-native
panel file; nothing launches, assumes, or configures an editor.

## What a good plan is (shared context for every verb)

Every verb here operates on a plan, so it helps to know what the plan is *for*. **A plan
is a set of rails** — typically written by a high-reasoning model and implemented by a
*possibly cheaper, lower-reasoning model*. The author spends reasoning up front so the
implementer only executes and verifies, never re-derives intent or guesses between
options. It must also read top-to-bottom for a *human*. `review` grades against the
standard below. The high-value
elements a strong plan has and weak plans omit: **done-when checks** (behavioral, not
"it compiles"), **out-of-scope fences**, **conventions made explicit**, **stable anchors**
(symbols/unique strings, never line numbers), and **no unresolved decisions**.

## The plan-write discipline (binding on build, update, archive — any verb that writes or moves a plan)

Plans must render cleanly in **plan renderers** — Cursor's plans panel and the CCVI
Plan Editor. Five non-negotiable rules whenever you write or edit a plan file:

1. **Surgical edits only.** To change a todo, locate it by its stable `id` and mutate
   only the relevant line (almost always `status:`). **Never** re-emit or reorder the
   frontmatter block, regenerate `id`s, or rewrite the file wholesale — Cursor's renderer
   is picky and a reformatted block drops the plan view back to plain markdown. The status
   keyword is **`in_progress` with an underscore** — `in-progress` (hyphen) parses but
   the spinner silently never renders. Valid statuses: `pending`, `in_progress`,
   `completed`, `cancelled`.
2. **Always-quote free-text scalars.** An unquoted `overview:` or `content:` value
   containing embedded `"quotes"` or a `colon-space` sequence collapses the **entire**
   frontmatter block and blanks every todo at once — a symptom that looks far worse than
   "one bad field." Wrap such values in double quotes and escape inner quotes, **or**
   validate with the bundled checker — `node tools/plan-check.cjs <file>` (resolved
   against the skill's base dir; see **Validating a plan** below) — which round-trips the
   frontmatter through a vendored js-yaml (the parser class Cursor itself uses). If Node
   is unavailable, fall back to a YAML round-trip via
   `python3 -c "import yaml,sys; yaml.safe_load(sys.stdin.read())"` or
   `ruby -ryaml -e 'YAML.safe_load(STDIN.read)'`. Eyeballing is not reliable. This bites
   hardest in `update`, which writes prose into frontmatter.
3. **Preserve additive keys.** Cursor ignores unknown frontmatter keys, so a plan may
   carry extras — a **`phase`** key grouping todos, a **`version`** key (a quoted
   `"MAJOR.MINOR"` revision counter the plan-editor badge and `/plans update` maintain), and
   an **`updates:`** key — a YAML **sequence** of revision entries `/plans update` appends
   (each `{ type: verify|review, model, at: "<UTC yyyy-mm-ddThh:mmZ>", version }`), placed as
   the **final** frontmatter key (after `isProject:`) so it never disturbs the `todos:` block.
   Never strip or reorder these; always quote `version` (a bare `1.10` YAML-coerces to the
   float `1.1`) and the `updates` entries' `at`/`model`/`version`; never let one become
   load-bearing for the renderer.
4. **One writer per plan file.** At any moment exactly one agent — whoever holds the
   plan and runs its verb — writes it. Worker agents that writer spawns are fenced off
   the plan entirely, and their briefs must say so: concurrent frontmatter edits race,
   and that collision class blanks todo blocks and sweeps foreign edits into commits.
   (`build`'s execution loop spells out who flips what when work is delegated.)
5. **Tag every code fence.** No bare ` ``` ` — every fence opener carries a language
   identifier. Source code gets its real language (`ts`, `bash`, `json`, `yaml`, …).
   Everything else splits on one question — would soft-wrapping a long line hurt it?
   Prose, logs, terminal/echo output, file trees, format skeletons → `text`
   (renderers soft-wrap the text family, so long lines reflow instead of scrolling).
   ASCII diagrams, wide tables, anything whose column alignment is load-bearing →
   `diagram` (kept out of the wrap set — wrapping destroys alignment; it renders
   plain and scrolls). Genuinely unsure → `text`; an untagged block is always worse
   than a tagged one. **Why:** plan renderers syntax-paint fences, auto-detecting
   untagged ones as *some* language — untagged prose comes out as keyword confetti.

> **After any frontmatter write, validate it parses** — run `node tools/plan-check.cjs
> <file>` (or the python/ruby fallback if Node is absent; see **Validating a plan**).
> If it doesn't pass, you've corrupted the plan — fix before proceeding, don't leave it broken.

## Validating a plan

The skill bundles a validator so the parse-check is fast, uniform, and first-try (no
runtime hunt). Run it after any frontmatter write, and as the mechanical-lint pass for
`review`:

```sh
node tools/plan-check.cjs <file.plan.md>
```

- **Resolve `tools/plan-check.cjs` against the skill's base dir** (the absolute base dir
  is given to you at skill-invocation time) — not the cwd of the plan being checked.
- **Bundled + vendored — no install, no network, offline.** It `require`s a vendored
  js-yaml (`tools/vendor/js-yaml.min.js`, pinned MIT) — the same parser class Cursor's
  plans panel uses, so "passes this" closely tracks "Cursor will render it."
- **What it checks:** the frontmatter parses as YAML; `isProject` is a boolean; `todos`
  is an array; each todo has a non-empty string `id` and `content` and a `status` in
  `{pending, in_progress, completed, cancelled}`; `in-progress` (hyphen) is rejected with
  a pointed message; todo `id`s are unique; `overview` is a string when present. All
  failures are collected in one run.
- **Exit contract:** exit `0` and print `plan-check OK — N todos; statuses: …;
  isProject=…` on success; exit `1` and print `plan-check FAIL <file>:` followed by one
  `- <problem>` line per issue on failure.
- **No-Node fallback** (if Node is unavailable): round-trip the frontmatter through any
  YAML parser instead — `python3 -c "import yaml,sys; yaml.safe_load(sys.stdin.read())"`
  or `ruby -ryaml -e 'YAML.safe_load(STDIN.read)'`. This only confirms it parses; it
  doesn't check the invariants above.

## The report contract (what review/verify WRITE and update READS)

`review` and `verify` are *producers*: they write a **report card** (a `.md`). `update`
is the lone *consumer*: it reads a report and applies it.

**Where the report lands.** Both producers take an `[out]` **directory** (default `./`, the
cwd) and write `<planbasename>.review.md` or `<planbasename>.verify.md` into it (creating
the dir if needed). `[out]` always names a *directory*, never a file path; the report is
named after the plan and lands directly in that directory.

**Reports carry a MINIMAL YAML frontmatter — a `plan:` ref + the producing `model:` — then a
pure-markdown body.** All of a report's **evidence** stays in the **body** as prose: evidence
cites grep results and code full of colons and quotes that would collapse a YAML scalar, so
evidence NEVER goes in frontmatter (that fragility tax is real; markdown body text has no such
hazard). The two machine-readable things up top are a pointer to the plan the report is about
(the report→plan association a consumer needs) and the id of the **model** that produced the
report (which `/plans update` records into the plan's revision-history log):

```yaml
---
plan: "<relative path from this report to its plan>"
model: "<id of the model that produced this report>"
---
```

`plan:` is `relative(<out>, <plan.md>)` — the path from the report's own directory (`[out]`) to
the plan file, computed from the two paths the verb already holds, so it assumes **no** directory
layout. **Always quote it** (a path can contain spaces or a `:`); validate the tiny frontmatter
parses after writing. A consumer resolves the ref relative to the report's own directory.
`model:` is the id of the model that produced this report (inline = the session model;
delegated = the subagent's model) — always quote it; `update` copies it verbatim into the
plan's `updates:` revision log. The body still has two audiences (`update`, an LLM, and a
human) and stays pure prose otherwise.

**The extraction spine `update` reads.** `update` doesn't need YAML to act
deterministically — it needs three things per finding, and they're all bareword-safe, so
they live inline in markdown:

- a **bolded todo-id** at the start of the finding — `**<todo-id>**` — the JOIN KEY that
  matches a todo's `id` in the plan;
- an inline **`[verdict]`** tag from the closed set below — first token after the id, so
  it's unambiguous to locate;
- a labeled **`Action:`** line — the imperative `update` applies (e.g.
  `Action: set status → pending`).

Everything else — evidence, rationale, recommendations, the one-line gestalt — is free
prose in the body, where colons and quotes are inert. `review` and `verify` each shape
these into their own layout (scorecard vs. punch list — see their verb sections); the
spine above is the contract both honor and `update` relies on.

**Verdict vocabularies (closed sets — `update` switches on them):**

- **`verify`** → `status-accurate` · `overclaimed` (status says more done than reality) ·
  `unverifiable` (couldn't substantiate either way — say why).
- **`review`** → `ready` · `stale` (refs drifted code/APIs) · `risky` (e.g. edits
  shared/global code with no degrade path) · `hygiene-issue` (non-atomic / unverifiable /
  mis-ordered / bad deps) · `lint` (mechanical frontmatter problem).

The `id` is the contract. A finding whose `id` matches no todo is a report error — surface
it, don't invent a todo to fit.

---

## Verb: write

**`/plans write [name]`** — author the plan currently being discussed into a
Cursor-compatible `*.plan.md` file. **Inline only** — `write` is a pure authoring step in
the current session; it never delegates. It doesn't duplicate the plan format here: follow
**`## The plan-write discipline`** (surgical/quoted/additive-safe frontmatter) and
**`## What a good plan is`** (done-when checks, out-of-scope fences, stable anchors, no
unresolved decisions) above.

**Steps:**

1. **Resolve the base name.** Use `[name]` if given; else infer it from the conversation's
   topic. If neither yields a clear name, **ask via the AskUserQuestion tool** — never
   invent one silently. Strip a trailing `.plan.md` from whatever you resolve (it's
   re-added in step 2).
2. **Resolve the destination.** If a plan directory is known in context (e.g. the active
   plan-authoring directory), write to `{planDir}/{baseName}.plan.md`; otherwise write
   `{baseName}.plan.md` into `./` (the cwd). **Never overwrite** — if the target exists,
   bump `-2`, `-3`, … until the name is free.
3. **Write the plan** following the disciplines referenced above, then **validate the
   frontmatter parses** (round-trip through a YAML parser).
4. **Echo the full written path** so the user knows exactly where it landed.

---

## Verb: review

**`/plans review [plan.md] [out] [model]`** — judge the plan's **quality as written** (not
whether its todos are done — that's `verify`). Read-only on the plan; writes only the
report.

`[out]` is a **directory** the report is written into (default `./`); the report lands at
`<planbasename>.review.md` inside it (create the dir if needed). If the user gives an
`[out]`, treat it as the destination directory.

**Who runs it — inline or delegated (model choice).** `review` can run two ways, and the
user may pick either (e.g. "review this plan" → inline; "have an agent review it" or
"review it with <model>" → delegate):

- **Inline (default):** you review the plan yourself, in the current session, and write
  the report.
- **Delegated to a fresh-context subagent at a chosen model:** spawn a subagent (via the
  normal Task/subagent mechanism — you are not launching a separate process) running
  `/plans review <plan> [out]`, ideally at the model that will *implement* the plan, in a
  fresh context — so it reviews as the prospective implementer ("can I build this with no
  open questions?"), which catches what the author's own eyes miss. When it finishes, it
  reports back the written report path and a one-line verdict gestalt. If the user names a
  model, use it; if they just say "an agent," pick a sensible implementer-tier model or
  ask. **Fresh eyes are the point of delegating** — note inline review is the author
  grading its own work.

**Rubric** — grade each todo and the plan overall against these dimensions:

- **Execution-readiness** — any unresolved decisions / open questions a low-reasoning
  implementer would have to guess on? (An "Open questions" section is itself a flag.)
- **Stale assumptions** — does any todo reference files/APIs/symbols that have since
  changed or no longer exist? (Grep the codebase to check.)
- **Cross-surface / regression risk** — does a todo edit shared or global code without a
  stated degrade path / fence?
- **Rails present** — does each step have a **stable anchor**, a **why**, and a
  **done-when** check? Are conventions/assumptions made explicit? Is there an
  out-of-scope fence and an escape hatch?
- **TODO hygiene** — atomic, verifiable, ordered, dependency-correct, unique `id`s.
- **Mechanical lint** — frontmatter parses (round-trip it); `overview`/`content` quoted
  where needed; `isProject: false`; no hard-coded release/app version numbers **in the
  plan's steps or content** (plans say "bump to the next version") — the plan's own
  `version:` frontmatter field is exempt, it's the plan's revision counter, not an app
  version; statuses from the valid set with the `in_progress` underscore.

**Output — a minimal `plan:` frontmatter + a pure-markdown scorecard** (per the report contract):

```markdown
---
plan: "<relative path to the plan>"
model: "<id of the model that produced this report>"
---
# Review: <plan name>

**Overall: <verdict gestalt>** — <one-line summary>

| Dimension | Grade | Notes |
|---|---|---|
| Execution-readiness | ✅ / ⚠️ / ❌ | <terse> |
| Stale assumptions | … | … |
| Cross-surface risk | … | … |
| Rails present | … | … |
| TODO hygiene | … | … |
| Mechanical lint | … | … |

## Findings

**<todo-id>** `[<verdict>]` — <evidence: cite file:symbol / grep result — prose, colons
and quotes are fine here>
Action: <imperative, e.g. set status → pending>

(…one block per todo with a non-`ready` verdict; clean todos can be a terse roll-up…)
```

Each finding leads with the **bolded todo-id**, then the inline **`[verdict]`** tag from
the review vocab, then prose evidence; an **`Action:`** line where `update` should do
something. Be specific and cite evidence (file:symbol, grep result). Do **not** modify the
plan — `review` only reports; the user runs `update` to apply.

## Verb: verify

**`/plans verify [plan.md] [out] [model]`** — the taskmaster. For each todo, check whether its
recorded `status` matches **reality in the codebase**. A `completed` todo must be
*actually* done — "compiles" ≠ "works"; don't take a status on faith. Read-only on the
plan; writes only the report.

`[out]` is a **directory** the report is written into (default `./`); the report lands at
`<planbasename>.verify.md` inside it (create the dir if needed). If the user gives an
`[out]`, treat it as the destination directory.

**Who runs it — inline or delegated (model choice).** Mirrors `review`: an omitted `[model]`
(or the literal `session`) runs **inline** (you verify in the current session and write the
report); a **model id** delegates to a fresh-context subagent running `/plans verify <plan>
[out]` at that model — ideally the model that will *implement* the plan, so it audits as the
prospective implementer — which then reports back the written report path and a one-line
gestalt. "Have an agent verify it" → pick a sensible implementer-tier model or ask; plain
"verify it" → inline.

**Depth — tiered, evidence-graded, read-only by default:**

1. **Existence / static checks (always):** does the file/symbol/section the todo claims
   actually exist? Use `Read`, `Grep`, `Glob`. A `completed` todo whose artifact is absent
   is `overclaimed`.
2. **Test coverage (note, don't run):** if the repo has a test command and the todo maps
   to it, note whether tests appear to cover the claim — but **do not run builds/tests on
   your own**; that keeps `verify` fast, safe, side-effect-free, and portable. Recommend
   the behavioral check in the report instead.
3. **Grade each todo** `status-accurate | overclaimed | unverifiable` with the strongest
   evidence cheaply available. A claim you cannot substantiate either way is
   `unverifiable` (with the reason) — **never** an optimistic `status-accurate`.

Behavioral confirmation beyond static evidence is the caller's opt-in — surface it as a
recommendation, don't perform it unasked.

**Output — a pure-markdown punch list, grouped by verdict, actionable-first** (per the
report contract; a minimal `plan:` frontmatter + markdown body). `verify` is a dev-QA pass, so the findings that need
work float to the top and the passing ones collapse to a roll-up:

```markdown
---
plan: "<relative path to the plan>"
model: "<id of the model that produced this report>"
---
# Verify: <plan name>

**Gestalt:** <e.g. "3 of 8 todos overclaimed; 1 unverifiable; rest accurate">

## ⚠️ Needs attention
**<todo-id>** `[overclaimed]` — status says `completed` but <evidence: artifact absent /
grep shows X — prose>
Action: set status → pending

## ❓ Unverifiable
**<todo-id>** `[unverifiable]` — <why it couldn't be substantiated either way>
Action: <recommended behavioral check the caller can run to settle it>

## ✓ Accurate
<todo-id>, <todo-id>, <todo-id> — status matches reality (no action)
```

Each actionable finding leads with the **bolded todo-id**, the inline **`[verdict]`** tag
from the verify vocab, prose evidence, and an **`Action:`** line. The `✓ Accurate` group
is a terse one-line id roll-up — passing todos need no evidence, so don't force empty
fields for them. Do **not** modify the plan.

## Verb: build

**`/plans build [plan.md] [model]`** — execute the plan **at the given path, in place**, as the
live file. **No copy, no launch, no archive** — pure execution. That purity is what makes
`build` portable: the path may be a Cursor copy, a plain repo file, or a future
IntelliJ-native plan; `build` treats whatever it's handed as canonical and never
duplicates it. (If a plan should live somewhere else before execution, the caller copies
it there first — `build` never does a handoff itself.)

**Who runs it — inline or delegated (model choice).** Like `review`, `build` can run two
ways: **inline** (you execute the plan in the current session — the default) or
**delegated to a fresh-context subagent at a chosen model** (spawn a subagent running
`/plans build <plan>` — execute the plan, flipping its todos live — then report back a
one-line summary of what landed). Delegating lets a heavier/cheaper model do the
execution while the main session stays free. **Either way the plan has exactly one
writer** — the context running the execution loop owns every status flip: a delegated
build subagent owns them for its run, and if the loop-runner farms a todo's *work* out
to a worker agent, the flips stay with the loop-runner, never the worker (see the
execution loop below). **Model resolution:** an omitted `[model]`
(or the literal `session`) means **inline**; a model id means **delegate** to that model.
If the user names a model ("build it with <model>") use it; "have an agent build it" →
pick a sensible model or ask; plain "build it" → inline.

**Mode-bridge prologue (run before the execution loop).** Invoke `/modes agent` before
executing — idempotent (a no-op if already in agent mode; bridges out of plan mode
otherwise) — and **stay in agent** afterward. The bridge runs in whatever context
actually executes, so a **delegated** build runs it inside the subagent. **Why:** a
direct `build` while plan mode is still held would otherwise balk on the first
non-markdown write.

**Execution loop — for each todo, in order.** Status ownership never leaves this loop:
whoever runs it (the inline session, or the delegated build subagent) is the plan's
single writer. A worker agent spawned for a todo's work never touches the plan file —
its brief must say so explicitly.

1. **Flip `pending` → `in_progress`** *before* the first tool call against the todo —
   a surgical `status:`-line edit located by `id`. **Deploying a worker agent on the
   todo IS that first tool call**: flip as part of the launch, before or immediately as
   the worker starts — never after it finishes. (Flipping early is what makes a live
   panel show in-flight state; never batch flips to the end. A plan sitting at
   `pending` while a worker is mid-flight tells the human watching it that nothing is
   happening.)
2. **Do the work** the todo's body detail describes — follow its stable anchor, make the
   concrete change, respect conventions and the out-of-scope fence.
3. **Check done-when.** Confirm the todo's behavioral done-when condition actually holds
   ("compiles" ≠ "works"). For delegated work you verify the worker's landing yourself —
   a worker's self-report is evidence, not the verdict. Only then **flip `in_progress` →
   `completed`**, immediately.
4. **If you bail** (blocker, decision needed, out of scope), flip → `cancelled` and add a
   one-line note in the markdown body explaining why. A worker that is killed, bails, or
   blocks gets the same honest treatment from you, promptly, never batched — back to
   `pending`, or `cancelled` with the note.

**The escape hatch (critical for a lower-reasoning implementer):** if the code or reality
**does not match what the plan describes**, **STOP and surface it — do not improvise.** A
diverged reality is the derail case; report it as a cheap question instead of guessing.

`build` does **not** auto-run `verify`/`review` and does **not** refuse an unverified plan
(atoms are independent) — though running `verify` first is good practice. All edits obey
the plan-write discipline (surgical, quoted, additive-keys-preserved). Validate the
frontmatter parses after each flip.

## Verb: update

**`/plans update [plan.md] [report.md]`** — the lone writer-back. Consume a review/verify
report (per the report contract) and apply its findings to the plan. `[report.md]` is
**required** — `update` never auto-runs `review`/`verify`; the user hands it a report. It
**applies directly** (no propose-then-confirm gate): the safety model is that the user has
already reviewed the report before triggering `update`, and the plan is under version
control, so a bad apply is a `git` rollback away.

**Steps:**

0a. **Snapshot the plan if it's under version control and dirty.** Resolve the plan's
   directory. If `git -C <plandir> rev-parse --is-inside-work-tree` succeeds **and**
   `git -C <plandir> status --porcelain -- <planfile>` is non-empty (the plan file has
   uncommitted changes), commit **just the plan file** as a restore point:
   `git -C <repo> add -- <planfile> && git -C <repo> commit -m "snapshot before /plans update: <planbasename>"`.
   If the plan isn't inside a git repo, **skip this step silently** (e.g. an untracked
   `~/.cursor/plans/` copy). Commit **only the plan file** — never `git add -A` — so
   unrelated working changes are not swept in.

0b. **Bump the version.** Read the frontmatter `version:` (a quoted `"MAJOR.MINOR"`). Treat
   an absent/blank version as `1.0`. Bump: if `MINOR < 9`, new = `MAJOR.(MINOR+1)`; if
   `MINOR >= 9`, roll to `(MAJOR+1).0` (e.g. `1.9` → `2.0`). Write it back **surgically** as
   a quoted string `version: "X.Y"` — replace the existing `version:` line, or insert one
   immediately after `name:` if absent. This bump happens on **every** `update` (review or
   verify). Validate the frontmatter parses after the write (`node tools/plan-check.cjs
   <file>`).

1. **Read & validate the report.** The report is **markdown** with an optional leading `plan:` frontmatter (per the report contract). **Skip that frontmatter when extracting findings** — findings live in the body; and if `[plan.md]` was omitted, **resolve it from the report's `plan:` ref** (relative to the report's directory) before applying, else fall back to the normal argument-resolution. Then
   extract each finding's **bolded todo-id**, its inline **`[verdict]`** tag, and its
   **`Action:`** line. If no findings are extractable (no `**id**` / `[verdict]` /
   `Action:` structure at all), or a finding's id matches **no** todo in the plan —
   **refuse to apply blindly.** Surface exactly what couldn't be mapped; never churn the
   plan on a malformed/stale report.
2. **Branch on report type — this sets the editing latitude.** Detect the type from the
   report's filename suffix (`.review.md` vs `.verify.md`), backed by its `# Review:` /
   `# Verify:` heading:
   - **`.review.md` → broad latitude.** Edit the plan as heavily as needed to address
     **every** finding — rewrite `content`, reword `overview`, add/remove/reorder todos,
     fix anchors, tighten done-when checks. A review judges the plan's *quality*, so its
     fixes are inherently structural.
   - **`.verify.md` → narrow latitude.** Change **nothing beyond todo `status`**, plus
     **add** clarifying prose **comments into the body** (never the frontmatter)
     referencing the updated todos, to orient the next builder on what reality showed. A
     verify audits *status accuracy*, so it never licenses content rewrites.
3. **Surgical throughout** — locate by `id`, change only what the finding (and the
   type-branch latitude) dictates, leave every other byte untouched. Preserve `phase` and
   other additive keys. When writing **free-text into frontmatter** (`overview`/`content`,
   review-branch only), always-quote the scalar or round-trip it through a YAML parser —
   the quoting hazard is real.
4. **Validate the frontmatter parses** after writing. Report what was applied and what (if
   anything) couldn't be mapped.
5. **Append a revision-history entry.** After the bump + applying findings, read the report's
   `model:` (fall back to `"unknown"` if the report lacks it) and its type (`verify` from a
   `.verify.md` / `# Verify:` report, `review` from a `.review.md` / `# Review:` one). Get the
   UTC minute-stamp — `date -u +%Y-%m-%dT%H:%MZ` → e.g. `2026-07-05T21:45Z`. Append one entry
   to the plan's `updates:` sequence (creating the key as the **final** frontmatter key, after
   `isProject:`, if absent), using the **post-bump** `version`:
   ```yaml
   updates:
     - type: <verify|review>
       model: "<from the report, or unknown>"
       at: "<UTC to the minute>"
       version: "<post-bump X.Y>"
   ```
   Append (oldest-first) — never reorder existing entries. Write **nothing** to the body: the
   plan-editor renders the "Plan Revision History" section from this YAML. Validate the
   frontmatter parses (`node tools/plan-check.cjs <file>`).

**Do not auto-commit the post-bump/post-apply result** — step 0a's snapshot is the restore
point; the user reviews the applied update and commits it per their normal cadence.

## Verb: archive

**`/plans archive [dir] [archiveDir] [lenient]`** — the bulk sweep: move every FINISHED
`*.plan.md` (todos all terminal) from the **top level** of `[dir]` into `[archiveDir]`,
each plan's sibling `<stem>.review.md` / `<stem>.verify.md` reports riding along so a
plan and its reports never split across the two directories. **No git is used or
required** — the verb works identically inside and outside a repository.

**Semantics:**

- **Scan is top-level only** — `<dir>/*.plan.md`, never recursive, so `[archiveDir]`
  (typically `<dir>/archive`) is naturally never scanned even though it sits inside
  `[dir]`.
- **Terminal gate:** a plan needs ≥1 todo and no todo `pending`/`in_progress`.
  **Strict** (default): every todo `completed` — a `cancelled` todo keeps the plan put
  (it may have been abandoned partway and deserves a human glance). **Lenient:** every
  todo `completed` OR `cancelled`. A zero-todo plan is always kept.
- **Copy-verify-delete, never a bare move:** copy the file, compare source and copy
  byte-for-byte, and only on equality delete the source. On mismatch: discard the bad
  copy, keep the source, report an ERROR line, continue.
- **Never clobber:** an existing same-named file in `[archiveDir]` → SKIP line, source
  stays put.
- **It moves immediately** (no confirm gate) — safety is copy-verify-delete plus the
  punch-list echo, mirroring `update`'s act-then-report model.

**Argument resolution:** `[dir]` and `[archiveDir]` resolve by the standard rule —
leading `~` → expand to `$HOME`; leading `/` → absolute, as-is; anything else →
relative to the project cwd. `[dir]` omitted → use the active plan-authoring directory
if one is known in session context; else the cwd if it holds top-level `*.plan.md`;
else say so and stop. `[archiveDir]` omitted → `<dir>/archive` (created if needed).
`[lenient]` omitted or `0` → strict; `1` or the literal `lenient` → lenient.

**Fast path:** run the bundled script — `bash tools/archive-plans.sh <dir> <archiveDir>
<0|1>` — resolving `tools/archive-plans.sh` against the skill's base dir (the absolute
base dir is given to you at skill-invocation time), not the cwd. Relay its punch list
(`ARCHIVE` / `keep` / `SKIP` / `ERROR` lines + the summary count) as the response. Exit
contract: `0` = success (even when nothing qualified); `1` = at least one copy-verify
failure; `2` = usage error.

**No-bash fallback** (when `Bash` is denied): `Glob` `<dir>/*.plan.md`, `Read` each
plan's todo statuses and apply the terminal gate; then per qualifying file: copy with
file tools, `Read` both copies to confirm identical content, delete the source only
after the match; sweep the sibling reports the same way; report the same punch list.

## Help output

When the user runs `/plans` with a blank or unrecognized verb (or asks "what can /plans
do?"), reply with exactly this — no preamble, no postscript:

```text
/plans · v0.0.1 — lifecycle verbs for *.plan.md files:
• write  [name]                                    — author the discussed plan into a *.plan.md
• review [plan.md] [out] [model]                   — vet the plan's quality → report card
• verify [plan.md] [out] [model]                   — audit each todo's status vs. reality → report card
• update [plan.md] [report.md]                     — apply a review/verify report back into the plan
• build  [plan.md] [model]                         — execute in place, flipping todos live
• archive [dir] [archiveDir] [lenient]             — sweep finished plans (todos all terminal) into archiveDir

Verbs are independent — you compose them. write authors; review/verify produce a report; update consumes one.
```

## When tools are denied

This skill declares `allowed-tools: Read, Write, Edit, Glob, Grep, Bash`, pre-approved
while the skill is active.
If a tool is denied at runtime, don't fail silently — surface the exact manual command:

- **`Write`/`Edit` denied** (writing a report or editing a plan) → print the change you
  intended (the report contents, or the surgical `status:` edit) and ask the user to
  apply it.
- **`Bash`/`Glob`/`Grep` denied** (collision check, evidence gathering) → degrade
  gracefully and say what you couldn't check (e.g. "couldn't check the destination dir for
  name collisions, so no bump suffix was applied").
- **`Bash` denied on `archive`** → print the manual invocation — `bash
  <skill-base-dir>/tools/archive-plans.sh <dir> <archiveDir> <0|1>` — and, for a single
  file, the copy-verify-delete triple (`cp src dst && cmp -s src dst && rm src`) for the
  user to run themselves.
- **`Read` denied** on the plan/report → stop and tell the user.

Suggest the minimum settings change that would let the verb complete next time (e.g.
`"Bash(bash:*)": "allow"` in `~/.claude/settings.json` so `archive`'s bundled script can
run).

## Edge cases

- **Unknown/blank verb** → print the **Help output**. Don't guess at a verb.
- **`build` escape hatch** → reality ≠ plan ⇒ STOP and surface; never improvise.
- **`update` on a malformed/stale report** → refuse; surface what couldn't be mapped.
- **Report/plan `id` mismatch** → a finding referencing a non-existent todo is a report
  error; surface, don't fabricate a matching todo.
- **A frontmatter write that won't parse** → you corrupted the plan; fix immediately,
  don't leave it broken.
- **`archive` finds no top-level `*.plan.md`** → say so and exit clean (not an error).
- **`archive` name collision in `[archiveDir]`** → SKIP that file and report it; the
  source stays put.
- **`archive` copy-verify mismatch** → ERROR line, bad copy discarded, source kept.
- **`[archiveDir]` inside `[dir]`** (the default `<dir>/archive`) → the normal case;
  the top-level-only scan never descends into it.
- **`archive` on a plan with zero todos** → kept, with a punch-list line saying why.

## What this skill does NOT do

- **No auto-chaining.** No composite verb; the caller composes.
- **`build` is not coupled to `verify`/`review`.** It won't read a report or refuse an
  unverified plan — atoms stay independent (a gate is deliberately out of scope).
- **`archive` never runs itself.** No verb triggers a sweep as a side effect; archiving
  happens only when the user asks for it.
- **No surprise verbs.** author → vet → place → execute → sweep, with a correction path,
  is the current set. Resist `/plans new` and friends — the verbs documented here are the
  whole surface.
- **Does not validate/normalize plan *content*** beyond the mechanical lint `review`
  reports and the parse-check after writes. Authoring quality is `/modes plan`'s job.
