---
name: cleancode
description: comments escrow/strip/annotate•naming refactor/propose/apply•conventions export/import/generate•run - post-stabilization code consolidation; escrow then strip construction-era comments, rename per the co-authored naming conventions, re-comment to a high bar, conventions docs loop, full pipeline. Use when the user issues a /cleancode directive; only on a stabilized project with a green verdict.
argument-hint: "[noun] [verb] [args]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# cleancode

**`/cleancode` runs once, after the human declares a version stabilized — implemented,
working, tested, its compound verdict green — and never mid-development.** On an active
project the copious agent-era comments are scaffolding and must stand; after
stabilization the tests hold the knowledge executably and the same comments are
formwork on cured concrete. This skill tears the scaffolding down: escrow the comments,
strip them, rename weak identifiers per a co-authored naming convention, then
re-comment to a high bar — each stage gated on a green compound verdict and landing as
its own git commit. **The timing is the human's call, alone**: invoking a destructive
verb IS the declaration that the project has stabilized. The skill never tries to
detect the phase; it verifies only the mechanical safety of the moment (clean tree,
green verdict, no colliding plan) at the moment of cutting.

## Invocation

One skill, one entry point — **`/cleancode [noun] [verb] [args]`** — dispatching on the
leading args. Verbs are **noun-first two-word forms** in three families — `comments`,
`naming`, `conventions` — plus the bare `run`: the Yoda rule applied to the command
surface itself, general to the left, specific to the right, so the help output
alphabetizes into families and every invocation answers its own "escrow what?"
question.

| Form | Effect |
|---|---|
| `/cleancode comments escrow {path} [escrowDir]` | Copy every comment verbatim into the escrow + manifest; report the comment census |
| `/cleancode comments strip {path} [escrowDir]` | Delete all non-protected comments; refuses without a fresh escrow |
| `/cleancode comments annotate {path} [escrowDir]` | Write the ideal comment set for the finished code, from code + escrow |
| `/cleancode naming refactor {symbol} {newName} [path] [tier]` | The single-symbol rename atom: sweep every reference, verdict-gated |
| `/cleancode naming propose {path} [tier]` | Dry run: write a `*.naming.proposal.md`, touch nothing |
| `/cleancode naming apply {path} [tier] [proposals]` | Execute renames through `naming refactor`, optionally from an edited proposals file |
| `/cleancode conventions export [topic] [pathAndFileName]` | Render the effective conventions as one editable `*.conventions.md` |
| `/cleancode conventions import [pathAndFileName]` | Diff an edited conventions file against the bundled baseline; codify in-scope deltas into CLAUDE.md |
| `/cleancode conventions generate {strategy} [pathAndFileName]` | Census the repo's actual naming practice into an import-ready `*.naming.conventions.md` |
| `/cleancode run {path} [verdict] [escrowDir] [tier]` | The full pipeline: escrow → strip → rename → annotate, one commit per stage |
| `/cleancode` (blank/unknown verb) | Print the help cheat-sheet (see **Help output**) |

**Verbs are independent atoms** — the caller composes them; no verb auto-runs another.
The one composition lives in `run`, which sequences the four pipeline verbs; the
`conventions` family is standalone and `run` never invokes it. `[topic]` on
`conventions export` defaults to `all`.

**Casing:** all verbs are plain lowercase (the cross-skill rule: only a
proper-noun/initialism target would be camelCase, and this set has none). Nouns and
verbs are single lowercase words; the noun comes first.

**Argument resolution:** expand `~`, normalize relative paths against the cwd.
`{path}` is a file or directory scope. `[escrowDir]` defaults to `./comment_escrow/`.
`[tier]` ∈ `local | internal | public`, default `internal`. Omitted optional args take
their documented defaults; a required arg missing → ask, don't guess.

## The pipeline

The four pipeline verbs run in this order, each stage landing as its own git commit so
the reviewer sees clean separable diffs instead of one mash:

```diagram
  escrow ──▶ strip ──▶ rename ──▶ annotate
 (comments  (delete   (per the   (re-comment to
  → escrow    inline)   naming     the high bar)
  + census)             convention)
   each stage: safety gate + GREEN verdict before its commit
```

Renaming runs *between* stripping and re-commenting because clean self-documenting
names shrink the need for comments — annotate augments names that already carry the
load.

**Mechanical work is scripted, judgment is not.** `tools/comments.py` (bundled, stdlib
Python only) does census/harvest/strip deterministically — string- and
template-literal-aware tokenization per language, so it can never hallucinate. The
`naming` verbs and `comments annotate` are model-driven judgment work, and each
executes a co-authored convention doc — `references/naming_conventions.md` for the
`naming` verbs, `references/comment_conventions.md` for `comments annotate` — making
no judgment its doc doesn't license.

**Supported languages (v1 table):** TypeScript/JavaScript, Rust, Python, Kotlin/Java,
CSS/Less, Swift. A file outside the table is SKIPPED with a loud line, never
half-processed.

## Verdict resolution — COMPOUND, always

The verdict is the green light every destructive verb and every pipeline stage requires,
and it is **compound: tests PLUS every discoverable static gate**. The skill's
characteristic failure mode is invisible to tests — a stripped tool pragma (`# noqa`,
`# type: ignore`, `eslint-disable-line`) breaks the linter or the typechecker, never
the test suite — so a tests-only verdict would cheerfully bless exactly the damage this
skill is most likely to do. The static half is non-optional wherever it can be found.

**Resolution order:**

1. **Explicit `[verdict]` param wins.** When the caller passes a shell command, THAT is
   the whole verdict: run it, exit 0 = green, anything else = red. No inference is
   added on top — an explicit verdict is the caller taking responsibility for
   completeness.
2. **Else compose from the project.** Both halves, independently discovered, ALL run;
   green means every discovered command exited 0:
   - **Tests:** root `package.json` with `scripts.test` → `npm test` ·
     `Cargo.toml` → `cargo test` · `build.gradle`/`build.gradle.kts` →
     `./gradlew test` · `pytest.ini` or `pyproject.toml` with pytest config →
     `pytest`.
   - **Typecheck/lint, where present:** `tsconfig.json` → `npx tsc --noEmit` ·
     mypy config (`mypy.ini`, or `[tool.mypy]`/`[mypy]` in
     `pyproject.toml`/`setup.cfg`) → `mypy` · `Cargo.toml` → `cargo clippy` ·
     eslint config (`.eslintrc*`, `eslint.config.*`) → `npx eslint .`.
   Discovery runs at the repo root of the target path. A discovered command that
   cannot run (tool not installed) is a red verdict with the reason named, not a
   silent skip — a gate you can see but not run is not a gate you may ignore.
3. **Else REFUSE — loudly.** If not even a test command can be inferred, no
   destructive verb runs. The refusal wording: *"cannot resolve a verdict: no test
   command found (looked for package.json scripts.test, Cargo.toml, build.gradle,
   pytest config). A skill whose safety story is 'the gates hold the knowledge'
   cannot run where it can't find the gates. Pass an explicit `[verdict]` command,
   or add a test entry point."* The `conventions` family and `naming propose` are
   exempt — they are read-only on code and need no verdict.

The verdict re-runs after every mutating stage, before that stage's commit. A red
verdict leaves the stage uncommitted and stops; recovery is `git checkout -- <path>`
to retreat or fix-and-rerun to advance.

## The moment-safety gate

Every destructive verb (`comments escrow`, `comments strip`, `naming refactor`,
`naming apply`, `comments annotate`, `run`) checks three things **at the moment of
cutting** — mechanical safety only, never phase detection:

1. **Clean working tree** — `git status --porcelain` is empty, so stage commits and
   rollback points are clean. A dirty tree refuses with the dirty paths named.
2. **Green compound verdict** — per **Verdict resolution** above, before the first cut.
3. **No colliding plan** — no live `*.plan.md` (in the cwd or an obvious plan dir)
   with non-terminal todos referencing the target paths. This is a COLLISION check —
   don't cut files an active plan is mid-editing — never an inference about project
   phase.

**Git discipline:** each stage commits only the files it touched plus the escrow —
never `git add -A`. Commit messages carry the full verb phrase:
`cleancode <noun> <verb>: <path>` (e.g. `cleancode comments escrow: src/`).

## Verb: comments escrow

**`/cleancode comments escrow {path} [escrowDir]`** — the explicit escrow act (never a
silent side effect of stripping), and the pipeline's opening report.

**Steps:**

1. **Run the moment-safety gate** (above). Refuse with the reason named on any miss.
2. **Resolve `[escrowDir]`** (default `./comment_escrow/`, created if needed) and the
   target file set: `{path}` expanded to every supported-language file under it.
3. **Harvest** — run the bundled tool, resolved against the skill's base dir:
   `python3 tools/comments.py harvest <escrowDir> <files...>`. It writes one escrow
   markdown file per source file — every comment VERBATIM under a heading naming its
   nearest enclosing symbol, with its span and removal-span — plus `MANIFEST.md`
   carrying the run stamp, git HEAD sha, and per-file content sha256 hashes.
   `comments strip` later checks those hashes for freshness, which is what makes
   escrow the required, explicit predecessor of any cut.
4. **Report the census** — since escrow reads every comment anyway, its report carries
   the comment census for free (`python3 tools/comments.py census <files...>` emits
   the JSON):
   - total comment mass % and the per-file ranking by mass;
   - the two **human-eyes categories**, seen before anything is deleted:
     commented-out code blocks and live TODO/FIXME markers (a TODO in a "done,
     tested" project is itself a signal for the human's phase call);
   - a **loud skip list** for files outside the supported-language table.
   (The NAMING side of observation belongs to `conventions generate`, not here.)
5. **Commit** the escrow: `cleancode comments escrow: <path>` — the escrow dir plus
   nothing else.

*Done when:* the escrow files contain every comment verbatim; the manifest carries the
HEAD sha and per-file hashes; the report carries the mass ranking, both human-eyes
counts, and the skip list; a dirty tree or red verdict refuses with the reason named.

## Verb: comments strip

**`/cleancode comments strip {path} [escrowDir]`** — deletes all non-protected inline
comments. The cut itself is the deterministic script's; the freshness gate is what
makes it safe.

**The freshness gate.** Strip **refuses to run** unless the escrow manifest's per-file
sha256 matches the file on disk — `comments escrow` is the required, recent, explicit
predecessor. The refusal names each stale or missing file. Hashes are per-file, so a
`{path}` NARROWER than the escrowed scope is legitimate (strip one file out of an
escrowed directory). The gate is implemented in the tool: `python3 tools/comments.py
strip <escrowDir> <files...>` exits 3 and cuts nothing when any target fails the
hash check.

**Steps:**

1. **Run the moment-safety gate**, then the tool — which enforces the freshness gate
   and deletes every comment classified `normal`, leaving:
   - **the protected class** (never stripped, detected deterministically): license
     headers, shebangs, tooling pragmas (`eslint-disable`, `@ts-ignore`, `noqa`,
     `# type:`, clippy/`allow(`-adjacent markers inside comments), toolchain
     doc-comments when the project generates API docs from them (the
     `--keep-doc-comments` flag — an escrow-reported per-project setting, default
     off), and structural navigation markup (`#region`/`#endregion`,
     `// region`/`// endregion`, `// MARK: -`, `<editor-fold>`, `--- Name ---`
     banners — navigation is not narration: it restates no line of code and editors
     fold on it);
   - **TODO/FIXME markers**, LEFT IN PLACE and flagged in the run summary — each is
     either stale (delete) or a live claim of unfinished work (belongs in a
     tracker), and neither call is the script's to make.
2. **Re-run the verdict** (compound, per Verdict resolution).
3. **On green, commit**: `cleancode comments strip: <path>` — the stripped files only.

**The closing counts report** (always, green or red):

- files in scope vs files escrowed;
- comments removed;
- comments kept BY CATEGORY — pragmas, license/shebang, navigation markup, toolchain
  doc-comments — with per-file and total counts;
- TODO/FIXME left in place, **each one listed** with file and line;
- the verdict result LAST — green committed; red left **uncommitted** with the
  recovery moves stated plainly: `git checkout -- <path>` to retreat, fix-and-rerun
  to advance.

*Done when:* strip on an un-escrowed file refuses; strip after escrow leaves a
comment-free file (protected class and TODO/FIXME intact, TODOs flagged) and a green
verdict; the report's removed + kept counts reconcile with the escrow's comment count
for the same scope.

## Verb: naming refactor

**`/cleancode naming refactor {symbol} {newName} [path] [tier]`** — the single-symbol
rename atom, usable standalone for a one-off rename. This is the mechanics atom:
**reference-sweeping lives here and nowhere else** — `naming apply` executes THROUGH
this verb.

**Steps:**

1. **Run the moment-safety gate.**
2. **Enumerate every reference** via a repo-wide grep sweep scoped by `[tier]`
   (default `internal`): the definition, call sites, imports/re-exports, and
   doc-comment mentions. No LSP is assumed — the sweep is grep-based
   (word-boundary match on `{symbol}`), which is exactly why `internal` is
   verdict-gated and `public` is opt-in.
3. **Flag, never silently rewrite, the un-sweepables:** string-keyed, reflective, or
   serialized uses of the name (the symbol inside a string literal, a config key, a
   wire format). Each is FLAGGED in the run summary for the human; string content is
   never rewritten.
4. **Apply all edits**, re-run the compound verdict.
5. **On green, commit**: `cleancode naming refactor: <symbol> -> <newName>`.

**Tiers** (blast radius): `local` — function-locals and private members, always safe ·
`internal` — module/file-internal symbols, applied with the repo-wide reference
sweep, the default · `public` — exported API, **opt-in only, never part of a default
`run`**.

*Done when:* on a fixture with a cross-file reference and a same-named string key, the
rename lands everywhere except the string, the string is flagged, and the verdict
stays green.

## Verbs: naming propose / naming apply

The old rename verb's modes, promoted to verbs. Both resolve the **EFFECTIVE
conventions** — project CLAUDE.md section > global CLAUDE.md section > bundled
`references/naming_conventions.md`, merged rule-by-rule — and **refuse if not even
the bundled doc exists**. Neither makes a naming judgment the resolved doc doesn't
license; that statement binds every proposal line.

**`/cleancode naming propose {path} [tier]`** — the dry run:

1. Walk the target, judging each identifier against the effective conventions.
2. Write a **`*.naming.proposal.md`** — default `<pathSlug>.naming.proposal.md`
   beside the target, path separators folded to `__` per the escrow's convention;
   the suffix joins the suite's typed-markdown family (`.plan.md`, `.review.md`,
   `.verify.md`, `.conventions.md`), so proposal files are recognizable and
   glob-resolvable without being opened. One line per proposed rename:
   `old → new`, the convention rule licensing it, the reference count, the tier —
   plus the vocabulary-consolidation summary (synonym pairs and one-term-per-concept
   drift, with the repo's dominant term named).
3. **TOUCH NOTHING** — the tree stays byte-identical. The user reviews the file,
   deletes or edits lines, or changes the conventions doc and re-proposes. Propose is
   read-only, so it needs no verdict and no gate.

**`/cleancode naming apply {path} [tier] [proposals]`** — the execution:

1. **Run the moment-safety gate.**
2. **Resolve the proposals**: the explicit `[proposals]` path, else exactly one
   `*.naming.proposal.md` in scope (several → ask), else propose-and-apply in one
   pass.
3. **Execute each surviving line THROUGH `naming refactor`'s mechanics** — the
   reference sweep, the string-key flagging, the tier scoping live in exactly one
   place. An edited proposals file is a contract: exactly the surviving lines
   execute, nothing else.
4. Re-run the verdict; **on green, commit the batch**:
   `cleancode naming apply: <path>`.

*Done when:* propose writes the report and leaves the tree byte-identical; apply on a
hand-edited proposals file executes exactly the surviving lines; a fixture with a
banned-vagueness name gets renamed per the doc; `public` symbols are untouched without
the opt-in; the verdict stays green.

## Verb: comments annotate

**`/cleancode comments annotate {path} [escrowDir]`** — writes the IDEAL comment set
for the finished code: judicious, strategic comments that genuinely aid grokking and
reasoning, augmenting code whose names now carry the load. It executes the **effective
comment conventions** — CLAUDE.md override section over
`references/comment_conventions.md`, same resolution as the naming verbs' — and makes
no judgment its doc doesn't license.

**Two sources, one bar:**

- **escrow entries** whose hard-won rationale survives — restated timelessly, razored;
- **brand-new comments with no escrow ancestor** — a bar-passing invariant the
  construction era never documented gets authored fresh. The escrow is evidence, not
  a ceiling. Fresh authorship is counted separately in the summary
  (**"authored fresh: N"**) — invention is where a judgment verb most needs
  oversight, so it is never folded into the restoration numbers.

**The bar (both must hold, and the comment is written as briefly as it can be):** it
states a constraint the code cannot show — a deliberate absence, a policy choice
("loud abort here is policy"), a non-obvious invariant — AND no gate (test, typecheck,
lint) enforces it. Everything with a gate behind it gets nothing. One short
module-level doc comment per file is allowed.

**Restate timelessly, never restore verbatim.** The worked case:

```text
Escrow entry:  We now use ROUND_HALF_UP instead of banker's rounding, which was
               causing off-by-one-cent mismatches with the ledger.
Written back:  ROUND_HALF_UP: banker's rounding produces off-by-one-cent ledger
               mismatches.
```

Deleting such an entry loses real knowledge; restoring it verbatim re-plants the
changelog. The rewrite is the only correct move.

**The never-restore list:** change narration in any form — past-tense change verbs
(added, removed, changed, fixed, increased) and "this code now handles" phrasings are
the concrete detection patterns — references to old behavior a fresh reader neither
knows nor needs; narration of what the next line visibly does; commented-out code
(strip deleted it and it stays deleted — version control is the archive); anything a
gate in the repo already enforces; provenance receipts (capture citations, commit
shas, review history).

**The keep-list (categories that look deletable and are not):** cross-file sync
obligations ("keep in sync with X" — the link IS the why); data-literal semantics
("pence, not pounds" — a literal cannot show its own convention);
presentation/format contracts pinning output to an external expectation; contract
docstrings (units, valid ranges, side effects, failure modes — one that only
re-emits the signature is narration and gets nothing).

**The razor is a second, independent test.** "Carries a real why" and "is worded
minimally" are separate judgments — passing the bar is not license to keep the
wording. Every survivor is cut to the one non-obvious fact a reader needs at that
line; the razored answer is sometimes zero. **Doubt is asymmetric:** unsure whether a
constraint is gate-enforced → keep it (razored), and record it as kept-on-doubt — a
wrongly dropped warning costs more than a mediocre survivor.

**References are breadcrumbs, never the substance.** A survivor must stand on its own
with any link removed; a ticket ID or stable maintained-doc path may ride as a
trailing breadcrumb after the encoded substance. Section numbers of any document are
never durable.

**Steps:** run the moment-safety gate; read the cleaned code and the escrow; write
every survivor and every fresh comment per the rules above; re-run the verdict; on
green, commit `cleancode comments annotate: <path>`. The run summary cites which
escrow entries were **dropped**, **rewritten**, and **kept-on-doubt**, plus the
authored-fresh count — one-line judgment calls a human can overrule. TODO/FIXME are
out of annotate's hands (strip flagged them; annotate neither writes new ones nor
deletes survivors), as are the protected class (never left the file) and unclear code
(never paper over it with a comment — flag it as a refactor candidate instead).

*Done when:* on the fixture set, annotate produces only bar-passing comments; every
survivor reads timelessly and minimally; keep-list category fixtures (a sync
obligation, a data-literal unit, a contract docstring) all survive; an undocumented
bar-passing invariant fixture gains a fresh comment counted under authored-fresh; the
run summary cites dropped, rewritten, and kept-on-doubt entries.

## Verbs: conventions export / conventions import

Together, export and import replace conflict-by-conflict interrogation with document
editing: **recognition over recall** — the same emit-edit-feed-back grammar as
`naming propose`. All three `conventions` verbs are standalone; `run` never invokes
them, and they need no verdict (they never touch code).

**`/cleancode conventions export [topic] [pathAndFileName]`** — render the EFFECTIVE
conventions (project CLAUDE.md section > global section > bundled docs, merged
rule-by-rule) as **ONE editable markdown file**:

- **Minimal YAML frontmatter** for bookkeeping: `topic`, `exported-at`, and a
  baseline marker (the bundled docs' content hash) so import can detect staleness.
- **Body as list-per-line entries** (`- app = application`) and short prose
  sections, **NO tables** — tables are miserable to edit raw, and this file exists
  only to be edited; the bundled reference docs keep theirs, the flattening is
  purely the export rendering.
- `[topic]` ∈ `naming | comments | all` (default `all`). The output carries a
  **topic-scoped suffix** — `*.naming.conventions.md`, `*.comments.conventions.md`;
  topic `all` (both in one file) takes the plain `.conventions.md`. The suffix is
  the type contract, joining the suite's typed-markdown family: convention files are
  recognizable and glob-resolvable without being opened, the family glob
  `*.conventions.md` matches every topic variant, and the topic slot leaves room for
  future types outside this skill (`*.coding.conventions.md` is RESERVED,
  deliberately unbuilt — coding conventions are out of scope here).
- Default filename per the file conventions:
  `exported_<YYYY.MM.DD>.naming.conventions.md` / `.comments.conventions.md` /
  `.conventions.md` by topic; `[pathAndFileName]` overrides.

**`/cleancode conventions import [pathAndFileName]`** — the write-back, and the
**SINGLE write path** to the managed CLAUDE.md section; no other verb touches it:

1. **Resolve the target** like the plans skill resolves a plan: the explicit path,
   else exactly one `*.conventions.md` in scope → use it; several → ask; none → say
   so and stop. The file declares its own topic via frontmatter.
2. **Model-diff** the edited file against the BUNDLED baseline. A stale baseline
   marker triggers a warning and a re-diff against the current bundled docs; a
   hand-mangled/unparseable file is surfaced, never guessed at.
3. **Classify each divergence before codifying:** naming/comment rules pass;
   out-of-scope rules — coding conventions like parameter counts or structural
   patterns, anything the `naming`/`comments` verbs could not execute — are flagged
   **"not codified: coding convention, not naming/comment"** and never written.
4. **Present the delta set for approval**, then write only the in-scope divergences
   into the managed `## Naming & comment conventions` section of the chosen
   CLAUDE.md (project or global — the user's choice at import time): creating the
   section from the template below (fixed Comments half + collected Naming deltas)
   when absent; else **surgically rewriting ONLY that section**, merging with
   pre-existing hand-authored content — never re-seeding.

*Done when:* export of pristine defaults round-trips (an immediate import reports
zero deltas); an edited blessed-list line plus a swapped symmetry pair land as
exactly two rules in the chosen CLAUDE.md section; a hand-added parameter-count rule
is flagged out-of-scope and NOT codified; a second export renders the merged
effective state including those overrides.

## Verb: conventions generate

**`/cleancode conventions generate {strategy} [pathAndFileName]`** — observation:
census the codebase and generate an **import-ready** `*.naming.conventions.md`
carrying the conventions the repo ACTUALLY practices. Bundled docs are opinion;
generate is observation; the user arbitrates between them in an editor.

**The census is a stratified matrix — era × language family.** Partition history into
eras (equal commit-count buckets, 4–5 by default) and census the identifiers ADDED in
each era (`git log -p` over the era's window; per-added-line attribution, so an old
file edited recently contributes to both eras), bucketed by the supported-language
table's families — so conventions that differ by family or drift over time are seen,
not averaged away. On huge repos, commits per era are capped and the cap is reported
in the output's `sampled:` coverage line — **no silent caps**.

**`{strategy}`** resolves the matrix into proposals:

- `majority` — sum across the matrix; most instances win.
- `recent` — cells weighted by era recency; captures the direction a migrating repo
  is heading.

**The migration signal is the trend.** Wherever the signals diverge, the file carries
the era trend line ("display/dismiss: 10% → 45% → 90% across eras; majority overall
is show/hide") — a monotone trend is a migration, noise is a wobble — so importing a
generated file codifies a decision, not a blind tally. Per-family proposals
(`- visibility (Python): …`) appear only where families genuinely disagree, else one
repo-wide line, keeping the file pleasantly editable.

**Two-layer mechanics — scripted harvest, model judgment:**

- **Scripted:** extract identifiers, split into word-tokens (camel humps,
  underscores, digit boundaries), classify each against an English wordlist
  (`/usr/share/dict/words` where present; absent → over-collect and let the model
  filter harder), the acronym lexicon, and the current blessed list. What remains
  are abbreviation candidates, carried with counts and sample identifiers
  (`cfg` ×31: `cfgPath`, `loadCfg`). The pair/prefix/vagueness censuses ride the
  same identifier-splitter.
- **Model:** infer expansions (co-occurrence of `err` and `error` is evidence;
  unclear → marked as a guess), reject domain terms of art (`twips` — words, not
  abbreviations, listed under a "terms of art detected" note), shape proposals with
  a frequency floor (≥3 uses; the tail is reported as a count, never as proposals).

**Output:** the export format — an import-ready `*.naming.conventions.md` (default
`generated_<strategy>_<YYYY.MM.DD>.naming.conventions.md` — the topic-scoped suffix;
generate is naming-only in v1) whose frontmatter carries `topic: naming`, `strategy`,
`generated-from` (repo @ HEAD sha), `exported-at`, and the `sampled:` coverage line.

**Scope fence:** naming topics only in v1 (comment practice is future work); only
rules the `naming` verbs could execute — vocabularies, prefixes, casing practice,
file naming — **never code shape**. Generate writes no CLAUDE.md — `conventions
import` is the single write path — and writes nothing outside its output file.

*Done when:* on a fixture repo whose legacy mass speaks show/hide but whose recent
commits speak display/dismiss, `generate majority` proposes show/hide and `generate
recent` proposes display/dismiss, each carrying the era trend; an abbreviation
fixture (`cfg` ×N beside `config`) yields a candidate line with inferred expansion
and counts while a terms-of-art fixture stays out of proposals; the output imports
cleanly; generate itself writes nothing outside the output file.

## Verb: run

**`/cleancode run {path} [verdict] [escrowDir] [tier]`** — the whole pipeline, in
order, composing the four pipeline verbs (and only them — the `conventions` family is
never invoked by `run`):

1. **The moment-safety gate**, once, before anything: clean tree, green compound
   verdict (an explicit `[verdict]` param governs every stage's verdict), no
   colliding plan.
2. **`comments escrow`** → census report, escrow commit.
3. **`comments strip`** → counts report, strip commit.
4. **`naming apply`** → rename batch through `naming refactor`, rename commit
   (`[tier]` defaults to `internal`; `public` never runs without the explicit
   opt-in).
5. **`comments annotate`** → survivor/fresh comment set, annotate commit.

The verdict re-runs after EVERY stage, before that stage's commit.

**The stop rule:** any red verdict halts the pipeline, leaves the failing stage
**uncommitted**, and reports the last green commit as the rollback point. The exact
stop state per stage:

- red after **escrow** — escrow files exist but are uncommitted; no source touched;
  recovery: fix and re-run, or delete the escrow dir.
- red after **strip** — stripped sources uncommitted; recovery:
  `git checkout -- <path>` to retreat (escrow commit remains the rollback point),
  fix-and-rerun to advance.
- red after **rename** — renamed sources uncommitted; same recovery, with the strip
  commit as the rollback point.
- red after **annotate** — annotated sources uncommitted; same recovery, with the
  rename commit as the rollback point.

**Every stage's run summary follows one shape:** **counts** (removed / rewritten /
kept per file), **flags** (TODO/FIXME, string-keyed rename uses, unclear-code
candidates), and **one-line judgment calls** the user can overrule.

*Done when:* the section spells out the exact stop state for a failure at each stage
and the summary shape — and a plain `/cleancode run` composes the same stages the
cautious verb-by-verb path takes.

## The managed CLAUDE.md conventions section

User divergences from the bundled convention docs live in ONE markdown section under
the stable heading `## Naming & comment conventions`, in a CLAUDE.md — project-level or
global, the user's choice at import time. Precedence: project section > global
section > bundled docs, merged rule-by-rule (a section entry beats the doc rule it
names; nothing else is inferred). The heading IS the delimiter — the section runs to
the next same-level heading. Its PRIMARY audience is every agent session naming new
files and symbols outside this skill; the skill's parser is the secondary consumer, so
the contents are ordinary imperative agent-facing rules, deltas only, never a copy of
the docs. `conventions import` is the SINGLE write path to this section — no other
verb touches it — and it locates and rewrites the section surgically by its heading; a
hand-edited section is legitimate input, not corruption.

**Style ruling for the whole section: CONCISE over teaching** — it loads into every
conversation and its audience is agents, so no explanatory parentheticals ("block-end
markers" stands unglossed; region markers are covered by the conventions docs'
protected class, not re-explained here).

**The section template** (seeded whenever the skill creates the section; the
`### Comments` half is FIXED lifecycle text, the `### Naming` half holds whatever
deltas `conventions import` codifies):

```markdown
## Naming & comment conventions

Managed by /cleancode - overrides its bundled defaults; edit freely.

### Naming
<the user's deltas: one imperative rule per line, whatever `conventions import` codifies>

### Comments
- Never: narration of what the adjacent line does, restated names/signatures,
  block-end markers, commented-out code. These are waste at every phase.
- During active construction, working-memory comments are welcome and expected -
  rationale, measurements, provenance, hand-off notes for the next agent. Don't
  razor them, and don't run ad-hoc comment purges.
- The high bar (a comment must state a constraint the code can't show and no test
  enforces) applies at consolidation, not now - that's /cleancode's job, once the
  version is done and its tests are green.
```

## Edge cases

- **Unsupported file in scope** → SKIPPED with a loud per-file line; never
  half-processed. The skip list rides every census and run summary.
- **Zero-comment file** → escrowed with a zero-count entry (so the manifest still
  covers it and a narrower strip stays legitimate); strip and annotate report it as
  a no-op line, not an error.
- **Escrow collision** (`[escrowDir]` already holds a manifest for a different
  scope/run) → refuse and name the existing manifest; the user re-runs escrow to
  refresh it or points at a different `[escrowDir]`. Never silently overwrite an
  escrow that a pending strip might depend on.
- **Mid-pipeline interrupt** (`run` killed between stages) → the per-stage commits
  are the recovery ledger: committed stages are done; the interrupted stage is
  uncommitted working-tree changes — `git status` shows exactly where it stopped,
  `git checkout -- <path>` retreats to the last green commit, re-running the failed
  verb advances.
- **Verdict command not found** (inferred or explicit command missing from PATH) →
  red verdict with the command named; never a silent skip of that half.
- **A static gate present but failing PRE-run** → the moment-safety gate is not met:
  refuse before cutting anything, reporting the failing gate — a project that was
  never green is not stabilized, and stripping would bury the signal.
- **Override section rules that contradict each other** (or contradict themselves
  across project/global) → surface the contradiction and stop; never guess which
  rule wins beyond the documented project > global > bundled precedence.
- **Blank/unknown verb or noun** → print the **Help output**. Don't guess at a verb.

## When tools are denied

This skill declares `allowed-tools: Read, Write, Edit, Glob, Grep, Bash`,
pre-approved while the skill is active. If a tool is denied at runtime, don't fail
silently — surface the exact manual command:

- **`Bash` denied** (the tool runs, verdicts, git) → print the intended invocation —
  `python3 <skill-base-dir>/tools/comments.py <mode> ...`, the verdict command(s),
  the `git` commands — and ask the user to run them; report what could not be
  verified (e.g. "verdict not run — do not treat this stage as green").
- **`Write`/`Edit` denied** (escrow files, renames, annotations, CLAUDE.md section)
  → print the change that was intended and stop the pipeline at that stage; a
  half-applied rename is worse than none.
- **`Glob`/`Grep` denied** (reference sweep, target resolution) → refuse `naming`
  verbs plainly (a rename without a complete sweep is unsafe); other verbs degrade
  to explicit file lists from the user.
- **`Read` denied** on the target or escrow → stop and tell the user.

Suggest the minimum settings change that would let the verb complete next time (e.g.
`"Bash(python3:*)": "allow"` so the bundled tool can run).

## What this skill does NOT do

- **Not for mid-development use.** Identity is post-stabilization; nothing here runs
  on a project whose tests aren't green, and no "partial/gentle mode" exists.
- **Not a stabilization detector.** The phase call belongs to the human — invoking a
  destructive verb IS the declaration; the skill checks moment-safety (clean tree,
  green verdict, collision) and reports activity facts; it never infers the phase,
  and no readiness heuristics exist.
- **Not a lint/formatter.** Formatting, import-sorting, dead-code removal are other
  tools' jobs; the skill touches comments and identifiers only.
- **Not a pre-hoc authoring style guide.** Steering comments as they are written is
  the managed CLAUDE.md section's job, loaded into every session — not a verb.
- **Not a coding-standards authority.** A rule the `naming` or `comments` verbs
  could not execute — parameter counts, structural patterns, function shape — does
  not belong in its docs; `conventions import` flags such rules instead of
  codifying them, and `conventions generate` never collects them. The
  `*.coding.conventions.md` suffix slot is reserved for whatever future tool owns
  that domain — never this skill.
- **No ledger/anchor system.** Deliberately dropped; comments never link into a
  living ledger — the escrow is a plain archive and git history is the deep archive.
- **No auto-run, no CI/scheduled integration.** Human-triggered only.
- **`public` renames are never implicit.** The tier exists but is opt-in per
  invocation, never part of a plain `run`.

## Help output

When the user runs `/cleancode` with a blank or unrecognized verb (or asks "what can
/cleancode do?"), reply with exactly this — no preamble, no postscript:

```text
/cleancode · v0.0.13 — post-stabilization code consolidation. Run ONLY when a version is done, tested, and green — invoking a destructive verb IS the stabilization declaration:
comments — the escrow pipeline
• comments escrow   {path} [escrowDir]              — copy every comment into the escrow + manifest; report the census
• comments strip    {path} [escrowDir]              — delete non-protected comments; refuses without a fresh escrow
• comments annotate {path} [escrowDir]              — write the ideal comment set for the finished code
naming — the rename machinery
• naming refactor {symbol} {newName} [path] [tier]  — single-symbol rename atom: full reference sweep, verdict-gated
• naming propose  {path} [tier]                     — dry run: write *.naming.proposal.md, touch nothing
• naming apply    {path} [tier] [proposals]         — execute renames through naming refactor
conventions — the docs loop
• conventions export   [topic] [pathAndFileName]    — render effective conventions as one editable file (topic: naming|comments|all)
• conventions import   [pathAndFileName]            — codify in-scope divergences into the managed CLAUDE.md section
• conventions generate {strategy} [pathAndFileName] — census actual practice into an import-ready file (majority|recent)
bare
• run {path} [verdict] [escrowDir] [tier]           — escrow → strip → rename → annotate; green verdict + one commit per stage

Verbs are independent atoms; run composes the pipeline ones; conventions verbs are standalone.
Tiers: local | internal (default) | public (opt-in only, never part of a default run).
```
