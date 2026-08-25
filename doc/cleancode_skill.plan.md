---
humanEngineerDifficulty: 7
name: cleancode skill — post-stabilization code consolidation
overview: "Build /cleancode, a skill that tears down construction scaffolding — copious agent-era comments and weak names — AFTER the human declares a project stabilized: escrow the comments, strip, rename (per a co-authored naming convention doc), annotate to a high bar, all gated on a green compound verdict (tests plus typecheck/lint) with one commit per stage. Noun-first two-word verbs in three families: comments, naming, conventions."
version: "1.1"
todos:
  - id: naming-conventions-doc
    content: "Review the two ALREADY-DRAFTED convention docs with Keldon (staged beside this plan as cleancode_skill_naming_conventions.md — settle its listed judgment calls — and cleancode_skill_comment_conventions.md), then move them into the skill dir as references/naming_conventions.md and references/comment_conventions.md"
    status: completed
    phase: foundations
  - id: skill-scaffold
    content: "Create the cleancode skill directory with SKILL.md skeleton: invocation table, verb dispatch, casing rule, allowed-tools, help output, and the CLAUDE.md conventions-section template (fixed Comments half, Naming deltas slot)"
    status: completed
    phase: foundations
  - id: comments-tool
    content: "Build tools/comments.py — string-aware comment tokenizer with census/harvest/strip modes over the supported-language table, plus its self-test"
    status: completed
    phase: foundations
  - id: verdict-resolution
    content: "Spec and implement COMPOUND verdict resolution in SKILL.md: tests PLUS typechecker/linter where discoverable (pragma loss is invisible to tests); explicit param wins, else infer from project type, else refuse loudly"
    status: completed
    phase: foundations
  - id: comments-escrow-verb
    content: "Write the comments escrow verb: extract every comment verbatim into the escrow dir with a manifest recording HEAD sha and per-file content hashes, reporting the comment census as it goes (per-file mass ranking, commented-out-code and TODO/FIXME counts, skip list)"
    status: completed
    phase: verbs
  - id: comments-strip-verb
    content: "Write the comments strip verb: delete all non-protected comments; REFUSES without a fresh escrow (manifest hash must match the file on disk)"
    status: completed
    phase: verbs
  - id: naming-refactor-verb
    content: "Write the naming refactor verb: the single-symbol rename atom — find and update every reference (defs, call sites, imports; string-keyed uses flagged), verdict-gated"
    status: completed
    phase: verbs
  - id: naming-propose-apply-verbs
    content: "Write the naming propose verb (dry-run proposals report, touches nothing) and the naming apply verb (execute through naming refactor, optionally consuming an edited proposals file) — the old rename verb's modes promoted to verbs"
    status: completed
    phase: verbs
  - id: comments-annotate-verb
    content: "Write the comments annotate verb: add back only comments that state a constraint the code cannot show AND no gate enforces — RESTATED timelessly, never restored verbatim — working from code + escrow, with the never-restore list"
    status: completed
    phase: verbs
  - id: conventions-export-import-verbs
    content: "Write the conventions export and conventions import verbs: export renders the EFFECTIVE conventions as one editable no-tables *.conventions.md (frontmatter bookkeeping, list-per-line body); import model-diffs the edited file against the bundled baseline, flags out-of-scope (coding-convention) rules, and codifies only in-scope divergences into the managed CLAUDE.md section"
    status: completed
    phase: verbs
  - id: conventions-generate-verb
    content: "Write the conventions generate verb: census the identifiers added per era × language family (stratified sample), classify tokens via scripted harvest + model judgment, and generate an import-ready *.conventions.md — strategy majority (sum across the matrix) or recent (era-recency weighted), with era trend annotations wherever the signals diverge"
    status: completed
    phase: verbs
  - id: run-verb
    content: "Write the run verb: the full pipeline with the green-verdict gate before start and after every stage, one git commit per stage"
    status: completed
    phase: verbs
  - id: docs-and-edges
    content: "Finish SKILL.md: edge cases, tools-denied degradation, what-this-skill-does-NOT-do fence, help cheat-sheet"
    status: completed
    phase: finish
  - id: repo-integration
    content: "Register cleancode in build.py's MANIFEST_SKILLS (all nine verbs with ordered param lists) so manifest.json carries the new skill, and get python3 build.py --check to exit 0 — landed in the same commit as the SKILL.md verb surface"
    status: completed
    phase: finish
  - id: readme-update
    content: "Update README.md for the four-skill suite: the three-skills intro sentence, a cleancode row in The skills table, the plugin-prefix list, and every other spot that enumerates the skills"
    status: completed
    phase: finish
  - id: dogfood-run
    content: "Dogfood /cleancode run on one stabilized module chosen with Keldon; review the diff and escrow together and fold findings back into SKILL.md"
    status: in_progress
    phase: finish
isProject: false
updates:
  - type: review
    model: "claude-fable-5"
    at: "2026-08-25T15:08Z"
    version: "1.1"
---

# cleancode skill — post-stabilization code consolidation

## Problem / Context

When AI agents build a project over weeks, the source accumulates snowdrifts of
comments: oracle citations, measured values, "VERIFIED RED at <sha>" notes, registry
cross-references, change narration. During construction this is load-bearing — it is the
working memory of the agent swarm. After the version lands and the test suite holds the
knowledge executably, the same comments become formwork left on cured concrete: a human
opening the file finds the code lost among receipts, and every agent session pays a token
tax re-reading an audit trail addressed to nobody.

The reference example of the "after" state this skill targets is
`web_flash_player`'s `crates/core/src/avm2/interp.rs` — a file whose comment mass is
60-70% of its bytes, nearly all of it provenance already enforced by byte-match tests in
the same file. **The skill is explicitly NOT for mid-development use**: on an active
project those comments are scaffolding and must stand. `/cleancode` runs once, when a
version is implemented, working, and tested — and **the timing is the human's call,
alone**: invoking a destructive verb IS the declaration that the project has
stabilized. The skill never tries to detect the phase (in an agent-loop project any
heuristic would cry wolf for months); it verifies only the mechanical safety of the
moment — clean tree, green verdict, no colliding plan — enforced by each destructive
verb at the moment of cutting.

Names are the second half: agent-era identifiers drift (vague `helper`, `mgr`, stale
metaphors). Clean self-documenting names shrink the need for comments, so renaming runs
*between* stripping and re-commenting.

## Approach

One skill, one entry point — **`/cleancode [noun] [verb] [args]`** — following the
sibling skills' dispatch-on-args idiom
([plans](../../.ccvi/ccvi-skills/plugin/skills/plans/SKILL.md), `modes`) with one
deliberate evolution: **verbs are noun-first two-word forms**, grouped into three
families — `comments`, `naming`, `conventions` — plus the bare `run`. This is the
Yoda rule applied to the skill's own command surface: general to the left, specific
to the right, so the help output alphabetizes into families and every invocation
answers its own "harvest what?" question (`comments escrow`, not `harvest`). Verbs
are independent atoms; `run` composes the pipeline ones; a help cheat-sheet prints
on blank/unknown input.

The pipeline, in order, each stage landing as its own git commit so the reviewer sees
three clean diffs instead of one mash:

```diagram
  escrow ──▶ strip ──▶ rename ──▶ annotate
 (comments  (delete   (per the   (re-comment to
  → escrow    inline)   naming     the high bar)
  + census)             convention)
   each stage: safety gate + GREEN verdict before its commit
```

**The verb set — `comments` family (the escrow pipeline):**

- `/cleancode comments escrow {path} [escrowDir]` — the explicit escrow act (never a
  silent side
  effect of stripping), and the pipeline's opening report. Every comment is copied
  verbatim into the escrow with enough
  anchor context to review later, with a manifest (git HEAD sha + per-file content
  hash) that `comments strip` later checks for freshness. Since escrow reads every
  comment
  anyway, its report carries the **comment census** for free: total comment mass %,
  per-file ranking by mass, counts of the two categories needing human eyes —
  commented-out code blocks and live TODO/FIXME markers (a TODO in a "done, tested"
  project is itself a signal for the human's phase call) — and a loud skip list for
  files outside the supported-language table. The human sees all of it before
  anything is deleted, because `comments strip` cannot run without a fresh escrow.
- `/cleancode comments strip {path} [escrowDir]` — deletes all inline comments except
  the
  protected class (see Conventions). TODO/FIXME markers are LEFT IN PLACE and flagged
  in the run summary — each is either stale (delete) or a live claim of unfinished work
  (belongs in a tracker), and neither call is the script's to make. **Refuses to run**
  unless the escrow manifest's per-file hash matches the file on disk —
  `comments escrow` is the
  required, recent, explicit predecessor (per-file hashes, so a `{path}` NARROWER
  than the escrowed scope is fine). **Closes with a counts report:** files in scope
  vs files escrowed; comments removed; comments kept BY CATEGORY (pragmas,
  license/shebang, navigation markup, toolchain doc-comments) with per-file and
  total counts; TODO/FIXME left in place, each one listed; then the verdict result —
  green committed, red left uncommitted with the recovery moves stated plainly
  (`git checkout -- <path>` to retreat, fix-and-rerun to advance).
- `/cleancode comments annotate {path} [escrowDir]` — writes the IDEAL comment set
  for the finished code: judicious, strategic comments that genuinely aid grokking
  and reasoning, augmenting code whose names now carry the load. Two sources, one
  bar: escrow entries whose hard-won rationale survives (restated timelessly,
  razored), and **brand-new comments with no escrow ancestor** — a bar-passing
  invariant the construction era never documented gets authored fresh. The escrow
  is evidence, not a ceiling. Fresh authorship is reported under its own count
  ("authored fresh: N") — invention is where a judgment verb most needs oversight,
  so it is never folded into the restoration numbers.

**The verb set — `naming` family (the rename machinery):**

- `/cleancode naming refactor {symbol} {newName} [path] [tier]` — the single-symbol
  rename
  atom: find every reference (definition, call sites, imports/re-exports; string-keyed
  or reflective uses are FLAGGED for the human, never silently rewritten), update them
  all, re-run the verdict. Usable standalone for a one-off rename.
- `/cleancode naming propose {path} [tier]` — the dry run, promoted from a mode param
  to its own verb: write a `*.naming.proposal.md` (default `<pathSlug>.naming.proposal.md`
  beside the target, separators folded to `__` per the escrow's convention — the
  suffix joins the suite's typed-markdown family, so proposal files are recognizable
  and glob-resolvable without being opened) — one line per
  proposed rename (`old → new`, the convention rule licensing it, reference count,
  tier) plus the vocabulary-consolidation summary — and TOUCH NOTHING. The user
  reviews it, deletes or edits lines, or changes the conventions doc and re-proposes.
- `/cleancode naming apply {path} [tier] [proposals]` — execute the renames THROUGH
  `naming refactor`, so the reference-sweep
  mechanics live in exactly one place — consuming an edited proposal file: the
  explicit `[proposals]` path, else exactly one `*.naming.proposal.md` in scope
  (several → ask), else proposing and applying in one pass. Tiered blast radius;
  verdict-gated.

**The verb set — `conventions` family (the docs loop):**

- `/cleancode conventions export {topic} [pathAndFileName]` — render the EFFECTIVE conventions
  (bundled docs + CLAUDE.md overrides, merged) as ONE editable markdown file: minimal
  YAML frontmatter for bookkeeping (`topic`, `exported-at`, a baseline marker), body
  as list-per-line entries and short prose sections, **NO tables** — tables are
  miserable to edit raw, and this file exists only to be edited; the bundled
  reference docs keep theirs, the flattening is purely the export rendering.
  `topic` ∈ `naming | comments | all` (default `all`). Output carries a
  **topic-scoped `.{topic}.conventions.md`** suffix — `*.naming.conventions.md`,
  `*.comments.conventions.md`; topic `all` (both in one file) takes the plain
  `.conventions.md` — joining the suite's typed-markdown family
  (`.plan.md`, `.review.md`, `.verify.md`, `.naming.proposal.md`): the suffix is the
  type contract, so
  convention files are recognizable and glob-resolvable without being opened, the
  family glob `*.conventions.md` matches every topic variant, and the topic slot
  leaves room for future types outside this skill (`*.coding.conventions.md` is
  RESERVED, deliberately unbuilt — coding conventions are out of scope here).
  Default filenames per the file conventions:
  `exported_<YYYY.MM.DD>.naming.conventions.md` /
  `.comments.conventions.md` / `.conventions.md` by topic.
- `/cleancode conventions import [pathAndFileName]` — the write-back: model-diff the
  edited file
  against the BUNDLED baseline and codify only the divergences into the managed
  `## Naming & comment conventions` CLAUDE.md section (project or global — the user's
  choice at import time; import is the SINGLE write path to that section, no other
  verb touches it), presenting the delta set for approval before
  writing. A bare `import` resolves its target like the plans skill resolves a plan:
  exactly one `*.conventions.md` in scope → use it; several → ask; none → say so.
  Each divergence is **classified before codifying**: naming/comment rules pass;
  out-of-scope rules — coding conventions like parameter counts or structural
  patterns, anything the `naming`/`comments` verbs could not execute — are flagged
  "not codified: coding convention, not naming/comment" and never written. The file
  declares its own topic via frontmatter; a stale baseline marker
  triggers a warning and re-diff; a hand-mangled file is surfaced, never guessed at.
  Together export and import replace conflict-by-conflict interrogation with document
  editing: recognition over recall — the
  same emit-edit-feed-back grammar as `naming propose`. All three conventions verbs
  are standalone;
  `run` never invokes them.
- `/cleancode conventions generate {strategy} [pathAndFileName]` — observation: census
  the codebase
  and generate an **import-ready** `*.conventions.md` carrying the conventions the
  repo ACTUALLY practices. **The census is a stratified matrix — era × language
  family:** history is partitioned into eras and the identifiers ADDED in each era
  are censused per language family, so conventions that differ by family or drift
  over time are seen, not averaged away. `strategy` ∈ `majority` (sum across the
  matrix — most instances win) | `recent` (cells weighted by era recency — captures
  the direction a migrating repo is heading). **The migration signal is the trend:**
  wherever the signals diverge, the file carries the era trend line ("display/dismiss:
  10% → 45% → 90% across eras; majority overall is show/hide") — a monotone trend is
  a migration, noise is a wobble — so importing a generated file codifies a decision,
  not a blind tally. Mechanics are two-layer — scripted candidate harvest (identifier
  splitting, wordlist/lexicon classification, counts with sample evidence) + model
  judgment (expansion inference, terms-of-art rejection, proposal shaping).
  Generate detects only what the scope fence allows
  (vocabularies, prefixes, casing practice, file naming — never code shape), covers
  naming topics only in v1 (comment practice is future work), and never writes
  CLAUDE.md — `conventions import` remains the single write path. Default output:
  `generated_<strategy>_<YYYY.MM.DD>.naming.conventions.md` (topic-scoped suffix —
  generate is naming-only in v1).

**Bare:**

- `/cleancode run {path} [verdict] [escrowDir] [tier]` — the whole pipeline:
  moment-safety gate, then comments escrow → comments strip → naming apply →
  comments annotate, verdict re-run after each stage, one
  commit per stage. Any red verdict stops the pipeline with the failing stage uncommitted.

**The naming convention document is a first-class deliverable of this skill.** It ships
as `references/naming_conventions.md` beside SKILL.md and is what the `naming` verbs
execute — they make no naming judgment the doc doesn't license. A full draft is ALREADY STAGED
beside this plan as
[cleancode_skill_naming_conventions.md](cleancode_skill_naming_conventions.md), covering
casing per language family, verb-noun functions and question-prefix booleans, banned
vagueness, the abbreviation allowlist, file naming (snake_case, general-first), symmetry
pairs, and one-term-per-concept. Its trailing **Calls to settle in
review** section is the agenda for todo `naming-conventions-doc`'s session with Keldon.

**Overrides live in CLAUDE.md, written by the skill itself — as a section agents READ,
not a data fence.** The bundled docs are the base; user divergences live in ONE
markdown section under the stable heading `## Naming & comment conventions` (with a
one-line note: "managed by /cleancode — overrides its bundled defaults; edit freely"),
in a CLAUDE.md — project-level or global, the user's choice at import time, with
precedence project section > global section > bundled docs, merged rule-by-rule (a
section entry beats the doc rule it names; nothing else is inferred). The heading IS
the delimiter (the section runs to the next same-level heading), and it is chosen to
invite reading, not to say "machine territory": the contents are ordinary imperative
CLAUDE.md rules ("booleans start with is/has/should", "visibility pair: show/hide"),
because the section's PRIMARY audience is every agent session naming new files and
symbols outside the skill — the skill's parser is the secondary consumer. Deltas only,
never a copy of the docs (CLAUDE.md is context ballast in every session; being in
every session is also exactly what makes it the pre-hoc layer). The skill locates and
rewrites the section surgically by its heading; a hand-edited section is legitimate
input, not corruption. This is the ONLY override mechanism (no per-project doc
override).

**The section has a fixed shape SKILL.md carries as a template.** Two subsections:
`### Naming` holds the user's deltas (whatever `import` codifies); `### Comments`
is a FIXED three-part lifecycle text seeded whenever the skill creates the section —
(1) the never-valuable bans (narration of the adjacent line, restated
names/signatures, block-end markers, commented-out code — waste at every phase),
(2) the affirmative construction license (working-memory comments are welcome and
expected mid-build; no razoring, no ad-hoc comment purges), and (3) the consolidation
pointer (the high bar applies at /cleancode time, once the version is done and tests
are green). Style ruling for the whole section: CONCISE over teaching — it loads into
every conversation and its audience is agents, so no explanatory parentheticals
(e.g. "block-end markers" stands unglossed; region markers are covered by the
conventions docs' protected class, not re-explained here).

**Its sibling, `references/comment_conventions.md`, makes the two judgment verbs
symmetrical:** each executes a co-authored convention doc and makes no judgment its doc
doesn't license — the `naming` verbs run on the naming doc, `comments annotate` runs on the comment doc
(the annotate bar, the keep-list, the never-restore list, the razor and breadcrumb
rules from Conventions below). The comment doc is ALREADY DRAFTED and staged beside
this plan as [cleancode_skill_comment_conventions.md](cleancode_skill_comment_conventions.md)
— it moves with the plan and lands as `references/comment_conventions.md` at
implementation. It shares the CLAUDE.md override block with the naming doc — one
mechanism, both docs, prevention and teardown reading one rule set.

**The escrow is a plain archive, not a living ledger.** Format: one markdown file per
source file under `[escrowDir]` (default `./comment_escrow/`, path separators folded to
`__`), each comment verbatim under a heading naming its nearest enclosing symbol, plus
`MANIFEST.md` with the run stamp, HEAD sha, and per-file hashes. It is committed in the
escrow-stage commit — git history is the deep archive — and it exists as insurance and a
review artifact only. (An earlier design with anchor links from code into a permanent
ledger was deliberately dropped: at post-stabilization time the tests already hold the
pins, so the linked-ledger machinery solved a mid-flight problem the skill never faces.)

**Mechanical work is scripted, judgment is not.** `tools/comments.py` (bundled, stdlib
Python only, the modes-skill precedent) does census/harvest/strip deterministically —
string- and template-literal-aware tokenization per language, so it can never
hallucinate. The `naming` verbs and `comments annotate` are model-driven: they are
judgment work.

## Conventions & assumptions

- **Final home:** the ccvi-skills repo (installed at `~/.ccvi/ccvi-skills`), as
  `plugin/skills/cleancode/` beside the existing modes/plans/seedprompt skill dirs.
  This plan's steps use paths
  relative to that skill dir; if the skill stays elsewhere, only the root moves. No
  cross-references to the other skills' behavior are assumed — `/cleancode` stands alone.
- **Supported languages (v1 table):** TypeScript/JavaScript, Rust, Python, Kotlin/Java,
  CSS/Less, Swift. A file outside the table is SKIPPED with a loud line, never
  half-processed. Assumes this covers Keldon's active repos; if not, the table in
  `tools/comments.py` grows — nothing else changes.
- **Protected comment class (never stripped):** license headers, shebangs, tooling
  pragmas (`eslint-disable`, `@ts-ignore`, `noqa`, `# type:`, `#[allow]`-adjacent
  markers inside comments), doc-comments a toolchain consumes for generated API docs
  when the project generates them (an escrow-reported per-project flag, default off),
  and **structural navigation markup** — IDE folding regions (`#region`/`#endregion`,
  `// region`/`// endregion`, `// MARK: -`, `<editor-fold>`) and `--- Name ---` section
  banners. Navigation is not narration: it restates no line of code and editors fold on
  it; all of it is regex-recognizable, so the protection lives deterministically in
  `comments.py`.
- **The annotate bar (the whole rule):** a comment survives, as briefly as it can be
  written, only if it states a constraint the code cannot show **and** no gate (test,
  typecheck, lint) enforces — deliberate absences, policy choices ("loud abort here is
  policy"), non-obvious invariants without executable pins. One short module-level doc
  comment per file is allowed. Everything with a gate behind it gets nothing.
- **Restate timelessly, never restore verbatim.** A surviving comment is REWRITTEN in
  present-tense, timeless form. Hard-won rationale often arrives in change-narration
  phrasing ("we now use ROUND_HALF_UP instead of banker's rounding — it caused
  off-by-one-cent ledger mismatches"); the content survives, the phrasing does not
  ("ROUND_HALF_UP: banker's rounding produces off-by-one-cent ledger mismatches").
  Deleting such a comment loses real knowledge; restoring it verbatim re-plants the
  changelog. Rewrite is the only correct move.
- **The never-restore list (annotate's negative instructions):** change narration in any
  form — past-tense change verbs (added/removed/changed/increased), "this code now
  handles" phrasings, references to old behavior a reader neither knows nor needs;
  narration of what the next line visibly does; commented-out code (it was deleted by
  strip and stays deleted — version control is the archive); anything a gate in the
  repo already enforces; provenance receipts (capture citations, commit shas, review
  history).
- **The keep-list (annotate's positive enumeration — categories that look deletable and
  are not):** cross-file sync obligations ("keep in sync with X" — the link itself is
  the why; it is the only thing stopping two copies drifting); data-literal semantics
  (the meaning/order/units of a literal — "pence, not pounds" — a literal cannot show
  its own convention); presentation/format contracts pinning output to an external
  expectation; and contract docstrings — units, valid ranges, side effects, failure
  modes, what has already been done to the inputs. A docstring that only re-emits the
  signature is narration; condensing one to a one-liner is valid only when nothing
  beyond signature restatement is lost.
- **The razor is a second, independent test.** "Carries a real why" and "is worded
  minimally" are separate judgments — genuine rationale can still be three times too
  long, and passing the bar is not license to keep the wording. Every survivor is cut
  to the one non-obvious fact a reader needs at that line; the razored answer is
  sometimes zero. **Doubt is asymmetric:** unsure whether a constraint is
  gate-enforced → keep it; a wrongly dropped warning costs more than a mediocre
  survivor.
- **References are breadcrumbs, never the substance.** A surviving comment must stand
  on its own with any link removed. Section numbers of any document are never durable;
  a ticket ID or stable maintained-doc path may ride as a trailing breadcrumb after
  the encoded substance.
- **Rename tiers:** `local` (function-locals and private members — always safe),
  `internal` (module/file-internal symbols, applied with a repo-wide reference sweep —
  the default), `public` (exported API — opt-in only, never part of a default `run`).
  No LSP is assumed; the sweep is grep-based, which is why `internal` is verdict-gated
  and `public` is opt-in.
- **Verdict resolution — COMPOUND, because the skill's characteristic failure mode is
  invisible to tests.** A stripped tool pragma (`# noqa`, `# type: ignore`,
  `eslint-disable-line`) breaks the linter or typechecker, never the test suite. So the
  verdict is tests PLUS every discoverable static gate: an explicit `[verdict]` shell
  command wins; else compose from the project — tests (root `package.json`
  `scripts.test`, `Cargo.toml` → `cargo test`, `build.gradle*` → `./gradlew test`,
  `pytest.ini`/`pyproject` → `pytest`) AND typecheck/lint where present (`tsconfig` →
  `tsc --noEmit`, mypy config → `mypy`, `Cargo.toml` → `cargo clippy`, eslint config →
  `eslint .`). If not even a test command infers, REFUSE to run any destructive verb —
  a skill whose safety story is "the gates hold the knowledge" cannot run where it
  can't find the gates.
- **Git discipline — the moment-safety gate:** every destructive verb checks, at the
  moment of cutting: a clean working tree (so stage commits and rollback points are
  clean), a green verdict, and no live `*.plan.md` with non-terminal todos
  referencing the target paths (a COLLISION check — don't cut files an active plan
  is mid-editing — never phase detection); each stage commits only the files it touched plus the escrow — never
  `git add -A`. Commit messages carry the full verb phrase:
  `cleancode <noun> <verb>: <path>` (e.g. `cleancode comments escrow: src/`).
- **House style for the skill files:** 2-space indentation, snake_case file names,
  AI-facing imperative phrasing in SKILL.md (render intent robustly, don't copy
  conversational wording verbatim).

## The steps

1. **`naming-conventions-doc`** — Both convention docs are ALREADY DRAFTED, staged
   beside this plan as `cleancode_skill_naming_conventions.md` and
   `cleancode_skill_comment_conventions.md`. The work is a review session with Keldon:
   settle the naming doc's trailing "Calls to settle in review" list (the agenda),
   apply any changes to either doc, move them into the skill dir as
   `references/naming_conventions.md` and `references/comment_conventions.md`, and
   drop their staging notes. *Why:* the `naming` verbs and `comments annotate` have no
   authority of their
   own; these docs are their entire license. *Done when:* both docs exist in the skill
   dir, their staging/review sections are gone, and Keldon has explicitly approved
   them.

2. **`skill-scaffold`** — Create `plugin/skills/cleancode/SKILL.md` with frontmatter
   (`allowed-tools: Read, Write, Edit, Glob, Grep, Bash`), the invocation table from the
   Approach, the verbs-are-atoms statement, and the help output listing all ten verb
   entries, grouped by family (comments escrow / strip / annotate; naming refactor /
   propose / apply; conventions export / import / generate; bare run)
   with the signature form `/cleancode noun verb {required} [optional]`. **The FIRST sentence
   of the skill body states the moment-of-use**: post-stabilization only, on a green
   verdict — a skill that doesn't declare when it applies gets judged (and misused) on
   the use it never intended. Include the CLAUDE.md conventions-section template from
   the Approach (fixed `### Comments` lifecycle half verbatim; `### Naming` deltas
   slot; the concise/agent-audience style ruling). *Anchor:* the plans
   skill's SKILL.md layout is the structural template. *Done when:* the skill loads and
   `/cleancode` (blank verb) prints the cheat-sheet.

3. **`comments-tool`** — Write `tools/comments.py` (stdlib only). Modes:
   `census <files…>` (JSON: per-file comment count, byte mass, mass %),
   `harvest <escrowDir> <files…>` (writes the escrow files + manifest),
   `strip <escrowDir> <files…>` (deletes non-protected comments; exits non-zero
   without a matching fresh manifest). Tokenizer handles line/block/doc comments per the
   language table and is string-aware (quotes, template literals, raw strings) so a `//`
   inside a string is never a comment. The protected class — pragmas, license headers,
   shebangs, and the navigation markup (region/endregion in every dialect, `MARK:`,
   editor-fold, `--- Name ---` banners) — is detected here, deterministically. Include
   `tools/test_comments.py` self-tests with fixture snippets per language, including
   the string-trap and protected-class cases. *Why:* deterministic,
   zero-token, cannot hallucinate — the model orchestrates, the script cuts. *Done when:*
   self-tests pass and a round-trip (harvest + strip + manual re-paste from escrow)
   reconstructs the original file byte-for-byte on the fixtures.

4. **`verdict-resolution`** — Write the SKILL.md section implementing the COMPOUND
   verdict rule from Conventions (tests + typecheck/lint), including why the static
   gates are non-optional (pragma loss is invisible to tests) and the refusal wording
   when not even a test command is resolvable. *Done when:* the section reads
   unambiguously for each of: explicit param, each inferable project type (test and
   static-gate halves), and the refuse case.

5. **`comments-escrow-verb`** — Write the `comments escrow` verb section wrapping
   `comments.py harvest`:
   run the moment-safety gate (clean tree via `git status --porcelain`; green
   verdict; collision check — per the git-discipline convention), resolve
   `[escrowDir]`, write escrow + manifest, and report: the escrow path and comment
   count, then the census that falls out of reading every comment — total mass %
   and per-file ranking, counts of commented-out code blocks and live TODO/FIXME
   markers (the two human-eyes categories, seen before anything is deleted, because
   `comments strip` cannot run without a fresh escrow), and a loud skip list for
   unsupported files. (The NAMING side of observation belongs to
   `conventions generate`.) Commit
   the escrow (`cleancode comments escrow: <path>`). *Done when:* the escrow files
   contain every comment verbatim; the manifest carries HEAD sha + per-file hashes;
   the report carries the ranking, both human-eyes counts, and the skip list; and a
   dirty tree or red verdict refuses with the reason named.

6. **`comments-strip-verb`** — Write the `comments strip` verb section wrapping
   `comments.py strip`: the
   freshness gate (refuse, naming the stale/missing file, when manifest hash ≠ disk;
   per-file hashes, so a `{path}` narrower than the escrowed scope is legitimate),
   the protected-class statement, the TODO/FIXME rule (left in place, each flagged in
   the run summary for the human), verdict re-run after the cut, commit
   (`cleancode comments strip: <path>`). **The closing counts report:** files in
   scope vs escrowed; comments removed; comments kept by category — pragmas,
   license/shebang, navigation markup, toolchain doc-comments — per file and total;
   every TODO/FIXME listed; verdict result last, and on red the stage stays
   uncommitted with the recovery moves stated (`git checkout -- <path>` to retreat,
   fix-and-rerun to advance). *Done when:* strip on an un-escrowed file
   refuses;
   strip after escrow leaves a comment-free file (protected class and TODO/FIXME
   intact, TODOs flagged) and a green verdict; and the report's removed + kept counts
   reconcile with the escrow's comment count for the same scope.

7. **`naming-refactor-verb`** — Write the `naming refactor` verb section: given one
   `{symbol}` and a
   `{newName}`, enumerate every reference — definition, call sites, imports/re-exports,
   doc-comment mentions — via a repo-wide grep sweep scoped by tier; string-keyed,
   reflective, or serialized uses of the name are FLAGGED in the run summary for the
   human, never silently rewritten; apply all edits, re-run the verdict, commit
   (`cleancode naming refactor: <symbol> -> <newName>`). *Why:* this is the mechanics atom —
   reference-sweeping lives here and nowhere else. *Done when:* on a fixture with a
   cross-file reference and a same-named string key, the rename lands everywhere except
   the string, the string is flagged, and the verdict stays green.

8. **`naming-propose-apply-verbs`** — Write the `naming propose` and `naming apply`
   verb sections (the old rename verb's modes, promoted to verbs — the `[mode]` param
   is gone): both resolve the EFFECTIVE
   conventions — project CLAUDE.md block > global CLAUDE.md block > bundled naming
   doc, merged key-by-key; refuse if not even the bundled doc exists.
   **`naming propose {path} [tier]`** walks the target and writes a
   `*.naming.proposal.md` (default `<pathSlug>.naming.proposal.md` beside the
   target, separators folded to `__`; the suffix is the type contract) — old → new,
   the
   licensing rule cited, reference count, tier, per line, plus the
   vocabulary-consolidation summary — touching nothing; it is the dry run that
   surfaces the doc's opinions for veto or a conventions change before anything moves.
   **`naming apply {path} [tier] [proposals]`** executes each rename THROUGH
   `naming refactor`'s mechanics —
   from an edited proposal file (the explicit `[proposals]` path, else exactly one
   `*.naming.proposal.md` in scope; several → ask), else propose-and-apply in one
   pass — and
   commits the batch (`cleancode naming apply: <path>`). Both verbs' briefs must
   state they
   make no judgment the doc doesn't license. *Done when:* propose writes the report
   and leaves the tree byte-identical; apply on a hand-edited proposals file executes
   exactly the surviving lines; a fixture with a banned-vagueness name gets renamed
   per the doc, `public` symbols are untouched without the opt-in, and the verdict
   stays green.

9. **`comments-annotate-verb`** — Write the `comments annotate` verb section: read the
    cleaned code and
    the escrow, execute the effective comment conventions (CLAUDE.md override block
    over `references/comment_conventions.md`, same resolution as the naming verbs') —
    the bar, the keep-list, the never-restore list with the
    past-tense-change-verbs and "this code now handles" patterns as concrete detection
    examples, the razor as a second independent test, the doubt asymmetry, and the
    breadcrumb rule — writing every survivor **restated timelessly and razored to
    minimum wording** (the ROUND_HALF_UP example goes into SKILL.md as the worked
    case), plus module docs, plus **fresh comments with no escrow ancestor** where a
    bar-passing constraint was never documented (same bar, same razor; counted
    separately as "authored fresh: N" in the summary — the goal is the IDEAL comment
    set for the finished code, escrow as evidence, not a ceiling). Commit
    (`cleancode comments annotate: <path>`). *Done when:* on the
    fixture set, annotate produces only bar-passing comments, every survivor reads
    timelessly and minimally, keep-list category fixtures (a sync obligation, a
    data-literal unit, a contract docstring) all survive, an undocumented
    bar-passing invariant fixture gains a fresh comment counted under
    authored-fresh, and the run summary cites
    which escrow entries were dropped, rewritten, and kept-on-doubt.

10. **`conventions-export-import-verbs`** — Write the `conventions export` and
    `conventions import` verb sections.
    **`conventions export {topic} [pathAndFileName]`**: resolve the EFFECTIVE
    conventions (project
    CLAUDE.md block > global block > bundled docs — the same resolution as the naming
    verbs'),
    render them as ONE editable markdown file — minimal YAML frontmatter (`topic`,
    `exported-at`, a baseline marker such as the bundled docs' content hash), body as
    list-per-line entries (`- app = application`) and short prose sections, NO tables —
    written to `[pathAndFileName]` (default
    `exported_<YYYY.MM.DD>.{topic}.conventions.md` per the file conventions — topic
    `all` takes plain `.conventions.md`; the topic-scoped suffix is the type
    contract, and the `*.coding.conventions.md` slot stays reserved/unbuilt).
    **`conventions import [pathAndFileName]`**: resolve the target (explicit path,
    else exactly
    one `*.conventions.md` in scope; several → ask; none → say so), read the edited
    file, model-diff it against the BUNDLED baseline, **classify each divergence**
    (naming/comment rules pass; coding-convention rules — parameter counts,
    structural patterns, anything the `naming`/`comments` verbs could not execute — are flagged
    "not codified" and never written), present the resulting delta set for
    approval, then write only the in-scope divergences into the managed
    `## Naming & comment conventions` section of the chosen CLAUDE.md (project or
    global) — creating the section from the SKILL.md template (fixed Comments half +
    collected Naming deltas) when absent, else surgically rewriting ONLY that
    section, merging with pre-existing hand-authored content — never re-seeding.
    Import is the SINGLE write path to the managed section; no other verb touches it. A stale baseline
    marker warns and re-diffs; an unparseable file is surfaced, never guessed at.
    *Why:* natural-language override authoring is daunting; editing a concrete
    rendering replaces recall with recognition — the same emit-edit-feed-back grammar
    as `naming propose`. *Done when:* export of pristine defaults round-trips (an
    immediate import reports zero deltas); an edited blessed-list line plus a swapped
    symmetry pair land as exactly two rules in the chosen CLAUDE.md section; a
    hand-added parameter-count rule is flagged out-of-scope and NOT codified; a second
    export renders the merged effective state including those overrides.

11. **`conventions-generate-verb`** — Write the `conventions generate` verb section:
    `conventions generate {strategy}
    [pathAndFileName]`, strategy `majority` | `recent`. **The census is a stratified
    matrix — era × language family:** partition history into eras (equal
    commit-count buckets, 4–5 by default) and census the identifiers ADDED in each
    era (`git log -p` over the era's window; per-added-line attribution, so an old
    file edited recently contributes to both eras), bucketed by the
    supported-language table's families. `majority` = sum across the matrix;
    `recent` = cells weighted by era recency. **Two-layer mechanics — scripted
    harvest, model judgment.** The scripted layer extracts identifiers, splits them
    into word-tokens (camel humps, underscores, digit boundaries), and classifies
    each against an English wordlist (`/usr/share/dict/words` where present; absent →
    over-collect and let the model filter harder), the acronym lexicon, and the
    current blessed list — what remains are abbreviation candidates, carried with
    counts and sample identifiers (`cfg` ×31: `cfgPath`, `loadCfg`). The model layer
    infers expansions (co-occurrence of `err` and `error` is evidence; unclear →
    marked as a guess), rejects domain terms of art (`twips` — words, not
    abbreviations, listed under a "terms of art detected" note), and shapes
    proposals with a frequency floor (≥3 uses; the tail is reported as a count,
    never as proposals). The pair/prefix/vagueness censuses ride the same
    identifier-splitter — THIS step is where that machinery is specced. Output: the
    export format — an
    import-ready `*.naming.conventions.md`
    (default `generated_<strategy>_<YYYY.MM.DD>.naming.conventions.md`) whose frontmatter
    carries `topic: naming`, `strategy`, `generated-from` (repo @ HEAD sha),
    `exported-at`, and a `sampled:` coverage line (commits per era are capped on
    huge repos — no silent caps). **Wherever the signals diverge, emit the era
    trend** ("display/dismiss: 10% → 45% → 90% across eras; majority overall is
    show/hide") — a monotone trend is a migration, noise is a wobble; per-family
    proposals (`- visibility (Python): …`) appear only where families genuinely
    disagree, else one repo-wide line, keeping the file pleasantly editable. Scope
    fence: naming topics only in v1; only rules the `naming` verbs could execute
    (vocabularies,
    prefixes, casing practice, file naming — never code shape). Generate writes no
    CLAUDE.md — `conventions import` is the single write path. *Why:* bundled docs
    are opinion;
    generate is observation; the user arbitrates between them in an editor. *Done when:*
    on a fixture repo whose legacy mass speaks show/hide but whose recent commits
    speak display/dismiss, `generate majority` proposes show/hide and `generate recent`
    proposes display/dismiss, each carrying the era trend; an abbreviation fixture
    (`cfg` ×N beside `config`) yields a candidate line with inferred expansion and
    counts while a terms-of-art fixture stays out of proposals; the output imports
    cleanly (parse-clean, delta preview renders); generate itself writes nothing outside
    the output file.

12. **`run-verb`** — Write the `run` verb section: open with the moment-safety gate, then
    comments escrow → comments strip → naming apply → comments annotate with the
    per-stage verdict + commit contract,
    and the stop rule: any red verdict halts the pipeline, leaves the failing stage
    uncommitted, and reports the last green commit as the rollback point. Every stage's
    run summary follows one shape: **counts** (removed/rewritten/kept per file), **flags**
    (TODO/FIXME, string-keyed rename uses, unclear-code candidates), and **one-line
    judgment calls** the user can overrule. *Done when:* the section spells out the
    exact stop state for a failure at each stage and the summary shape.

13. **`docs-and-edges`** — Finish SKILL.md: edge cases (unsupported file, zero-comment
    file, escrow collision, mid-pipeline interrupt, verdict command not found, a
    static gate present but failing pre-run, an override section whose rules
    contradict each other → surface, never guess), the tools-denied degradation
    section, and
    the NOT-list: not a lint/formatter, not for mid-development use, **not a
    stabilization detector** (the phase call belongs to the human — invoking a
    destructive verb IS the declaration; the skill checks moment-safety, never
    infers the phase), not a pre-hoc
    authoring style guide (that job belongs to CLAUDE.md rules), **not a
    coding-standards authority** (a rule the naming or comments verbs could not
    execute — parameter counts, structural patterns — does not belong in its docs;
    conventions import flags such rules instead of codifying them), no ledger/anchor
    system, no auto-run on a schedule, `public` renames never implicit. *Done when:* every edge case names its behavior and the
    NOT-list matches this plan's Out of scope.

14. **`repo-integration`** — Register the new skill in the repo's consumer contract:
    add a `cleancode` entry to `MANIFEST_SKILLS` in `build.py` carrying all ten verb
    entries
    with their ORDERED param lists (literal `name`, `required`, `kind` hints per the
    existing entries' shape). Encode each two-word verb as its literal verb string
    including the space (`"comments escrow"`) — a NEW manifest shape: confirm
    ccvi-idea's manifest consumer tolerates it before landing, and flag the shape
    change in the commit message. Then run `python3 build.py` and
    `python3 build.py --check`.
    *Why:* the repo's CLAUDE.md makes manifest.json the machine-readable contract hosts
    consume — any SKILL.md verb/param change must update `MANIFEST_SKILLS` in the same
    commit, and a new skill is the largest such change. *Done when:* `python3 build.py
    --check` exits 0 and the emitted `manifest.json` lists cleancode's ten verb
    entries with
    params in signature order, in the same commit that lands the SKILL.md verb surface.

15. **`readme-update`** — Update `README.md` to describe the four-skill suite. Anchors:
    the intro sentence "three tightly-coupled Claude Code skills - `modes`, `plans`,
    and `seedprompt`" becomes four and names `cleancode`; the "## The skills" table
    gains a cleancode row (signature `/cleancode [verb] [args]`, a one-line description
    matching the table's voice); the plugin-prefix list gains `ccvi-skills:cleancode`;
    and any other line enumerating the skills (e.g. "the three skills" in the install
    section) is updated. *Why:* the README is the suite's shop window and build.py
    stamps only the version into it — skill enumeration is manual content. *Done when:*
    no line in README.md implies a three-skill suite and the cleancode row renders in
    the table.

16. **`dogfood-run`** — First make the skill invocable: skills run from the installed
    copy at `~/.ccvi/ccvi-skills`, so a release/install cycle (the repo's BBP ritual,
    then refreshing the installed plugin) precedes the dogfood — otherwise `/cleancode`
    resolves to a stale or absent skill. Then, with Keldon, pick one genuinely
    stabilized module (small blast
    radius) and take the CAUTIOUS path end to end: `conventions generate majority`
    (read the generated
    census together), `comments escrow` (review its census report and the two
    human-eyes
    counts), `comments strip`, `naming propose` (review the proposals, adjust the
    conventions doc if its opinions misfire), `naming apply`, `comments annotate` — then confirm
    a plain `/cleancode run` composes the same stages. Review the four stage diffs and
    the escrow together; fold every rough edge back into SKILL.md / `comments.py`. *Done
    when:* the run completes with a green final verdict, Keldon signs off on the diff,
    and any fixes discovered are landed.

**Escape hatch (binding on every step):** if reality diverges from this plan — the
skills-repo layout differs, a language's tokenization turns out infeasible in the script,
the naming doc session changes the naming-verbs contract — STOP and surface it; don't
improvise.

## Out of scope

- **Mid-development cleanup.** The skill's identity is post-stabilization; nothing in it
  runs on a project whose tests aren't green, and no "partial/gentle mode" is built.
- **Stabilization detection.** "This version is done" is the human's call — invoking a
  destructive verb is the declaration. The skill verifies moment-safety (clean tree,
  green verdict, collision check) and reports activity facts; it never infers the
  phase, and no readiness heuristics are built.
- **The ledger/anchor system.** Deliberately dropped (see Approach); do not resurrect
  comment-to-ledger links.
- **Formatting, lint, import-sorting, dead-code removal.** Different tools' jobs; the
  skill touches comments and identifiers only.
- **Public-API renames as a default.** `public` tier exists but is opt-in per invocation,
  never part of a plain `run`.
- **CI/scheduled integration.** Human-triggered only.
- **Coding/structural conventions.** Parameter counts, keyed-object thresholds,
  function shape, arity: a rule the `naming` or `comments` verbs could not execute does not
  belong in this suite's docs — `conventions import` flags such rules as out of scope rather than
  codifying them, and `conventions generate` never collects them. The
  `*.coding.conventions.md` suffix slot is reserved for whatever future tool owns that
  domain — never this skill.
- **Languages outside the v1 table** — skipped loudly, added later by growing the table.
- **The convention docs' actual content** — both authored collaboratively in todo 1, not
  decided by this plan beyond their required coverage.

## Verification

- `tools/test_comments.py` passes on the per-language fixtures, including string-trap and
  round-trip (harvest + strip + re-paste ⇒ byte-identical) cases.
- Each verb's done-when above holds when exercised against the fixture set.
- The dogfood run (todo 16): a real stabilized module goes through the full pipeline —
  four commits, green verdict after each stage, escrow reviewable, final code readable
  with only bar-passing comments — and Keldon approves the resulting diff.
