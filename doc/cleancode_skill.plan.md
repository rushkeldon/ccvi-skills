---
name: cleancode skill — post-stabilization code consolidation
overview: "Build /cleancode, a skill that tears down construction scaffolding — copious agent-era comments and weak names — AFTER a project stabilizes: survey, harvest-to-escrow, strip, rename (per a co-authored naming convention doc), annotate to a high bar, all gated on a green compound verdict (tests plus typecheck/lint) with one commit per stage."
version: "1.0"
todos:
  - id: naming-conventions-doc
    content: "Review the two ALREADY-DRAFTED convention docs with Keldon (staged beside this plan as cleancode_skill_naming_conventions.md — settle its listed judgment calls — and cleancode_skill_comment_conventions.md), then move them into the skill dir as references/naming_conventions.md and references/comment_conventions.md"
    status: pending
    phase: foundations
  - id: skill-scaffold
    content: "Create the cleancode skill directory with SKILL.md skeleton: invocation table, verb dispatch, casing rule, allowed-tools, help output, and the CLAUDE.md conventions-section template (fixed Comments half, Naming deltas slot)"
    status: pending
    phase: foundations
  - id: comments-tool
    content: "Build tools/comments.py — string-aware comment tokenizer with census/harvest/strip modes over the supported-language table, plus its self-test"
    status: pending
    phase: foundations
  - id: verdict-resolution
    content: "Spec and implement COMPOUND verdict resolution in SKILL.md: tests PLUS typechecker/linter where discoverable (pragma loss is invisible to tests); explicit param wins, else infer from project type, else refuse loudly"
    status: pending
    phase: foundations
  - id: survey-verb
    content: "Write the survey verb: readiness check (clean tree, green verdict, no live plan touching the paths), comment census AND naming census report, closing with the tandem step — user-approved convention overrides written as the delta block to project or global CLAUDE.md"
    status: pending
    phase: verbs
  - id: harvest-verb
    content: "Write the harvest verb: extract every comment verbatim into the escrow dir with a manifest recording HEAD sha and per-file content hashes"
    status: pending
    phase: verbs
  - id: strip-verb
    content: "Write the strip verb: delete all non-protected comments; REFUSES without a fresh escrow (manifest hash must match the file on disk)"
    status: pending
    phase: verbs
  - id: refactor-verb
    content: "Write the refactor verb: the single-symbol rename atom — find and update every reference (defs, call sites, imports; string-keyed uses flagged), verdict-gated"
    status: pending
    phase: verbs
  - id: rename-verb
    content: "Write the rename verb: propose mode (dry-run proposals report, touches nothing) and apply mode (execute through the refactor verb, optionally consuming an edited proposals file)"
    status: pending
    phase: verbs
  - id: annotate-verb
    content: "Write the annotate verb: add back only comments that state a constraint the code cannot show AND no gate enforces — RESTATED timelessly, never restored verbatim — working from code + escrow, with the never-restore list"
    status: pending
    phase: verbs
  - id: run-verb
    content: "Write the run verb: the full pipeline with the green-verdict gate before start and after every stage, one git commit per stage"
    status: pending
    phase: verbs
  - id: docs-and-edges
    content: "Finish SKILL.md: edge cases, tools-denied degradation, what-this-skill-does-NOT-do fence, help cheat-sheet"
    status: pending
    phase: finish
  - id: dogfood-run
    content: "Dogfood /cleancode run on one stabilized module chosen with Keldon; review the diff and escrow together and fold findings back into SKILL.md"
    status: pending
    phase: finish
isProject: false
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
version is implemented, working, and tested — the timing is a *precondition the skill
verifies*, not a vibe.

Names are the second half: agent-era identifiers drift (vague `helper`, `mgr`, stale
metaphors). Clean self-documenting names shrink the need for comments, so renaming runs
*between* stripping and re-commenting.

## Approach

One skill, one entry point — **`/cleancode [verb] [args]`** — following the house style of
the sibling skills ([plans](../../.ccvi/ccvi-skills/plugin/skills/plans/SKILL.md),
`modes`): verbs are independent atoms, a `run` verb composes them, lowercase plain verbs,
a help cheat-sheet on blank/unknown verb.

The pipeline, in order, each stage landing as its own git commit so the reviewer sees
three clean diffs instead of one mash:

```diagram
  survey ──▶ harvest ──▶ strip ──▶ rename ──▶ annotate
 (readiness   (comments    (delete   (per the     (re-comment to
  + census,    → escrow,    inline)   naming       the high bar)
  read-only)   explicit)              convention)
      each destructive stage: verdict must be GREEN before its commit
```

**The verb set:**

- `/cleancode survey [path] [verdict]` — read-only. Readiness check (clean working tree,
  green verdict, no live `*.plan.md` referencing the paths) plus a comment census: total
  comment mass %, counts, per-file candidate ranking, and counts of the two categories
  needing human eyes — commented-out code blocks and live TODO/FIXME markers (a TODO in
  a "done, tested" project is itself a readiness signal). Plus a **naming census**: the
  vocabulary the repo speaks today — which symmetry pairs are in use and how often,
  where repo practice conflicts with the conventions doc ("repo says show/hide 42
  times; doc says display/dismiss"), banned-vagueness hit counts. Survey CLOSES with
  the **tandem step**: it presents each census conflict and offers (via
  AskUserQuestion) to replace the bundled convention with the user's own; approved
  replacements are written as a delimited DELTA block to the CLAUDE.md the user
  chooses — project-level or global. From that moment the user's conventions steer
  BOTH the cleanup and every future agent session writing code (the pre-hoc layer,
  authored by the post-hoc tool, with usage evidence in hand). Survey never touches
  code; the block, only with explicit approval.
- `/cleancode harvest {path} [escrowDir]` — the explicit escrow act (never a silent side
  effect of stripping). Every comment is copied verbatim into the escrow with enough
  anchor context to review later. Writes a manifest (git HEAD sha + per-file content
  hash) that `strip` later checks for freshness.
- `/cleancode strip {path} [escrowDir]` — deletes all inline comments except the
  protected class (see Conventions). TODO/FIXME markers are LEFT IN PLACE and flagged
  in the run summary — each is either stale (delete) or a live claim of unfinished work
  (belongs in a tracker), and neither call is the script's to make. **Refuses to run**
  unless the escrow manifest's per-file hash matches the file on disk — harvest is the
  required, recent, explicit predecessor.
- `/cleancode refactor {symbol} {newName} [path] [tier]` — the single-symbol rename
  atom: find every reference (definition, call sites, imports/re-exports; string-keyed
  or reflective uses are FLAGGED for the human, never silently rewritten), update them
  all, re-run the verdict. Usable standalone for a one-off rename.
- `/cleancode rename {path} [tier] [mode] [proposals]` — the batch driver, in two
  modes. **`propose`** (the dry run): write `<path>_rename_proposals.md` — one line per
  proposed rename (`old → new`, the convention rule licensing it, reference count,
  tier) plus the vocabulary-consolidation summary — and TOUCH NOTHING. The user
  reviews it, deletes or edits lines, or changes the conventions doc and re-proposes.
  **`apply`** (default): execute the renames THROUGH `refactor`, so the reference-sweep
  mechanics live in exactly one place — consuming an edited proposals file when one is
  given, else proposing and applying in one pass. Tiered blast radius; verdict-gated.
- `/cleancode annotate {path} [escrowDir]` — writes the small set of comments that
  survive the bar (see Conventions), reading both the cleaned code and the escrow.
- `/cleancode run {path} [verdict] [escrowDir] [tier]` — the whole pipeline: readiness
  gate, then harvest → strip → rename → annotate, verdict re-run after each stage, one
  commit per stage. Any red verdict stops the pipeline with the failing stage uncommitted.

**The naming convention document is a first-class deliverable of this skill.** It ships
as `references/naming_conventions.md` beside SKILL.md and is what `rename` executes — the
verb makes no naming judgment the doc doesn't license. A full draft is ALREADY STAGED
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
in a CLAUDE.md — project-level or global, the user's choice at the tandem step, with
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
`### Naming` holds the user's deltas (whatever the tandem step collected); `### Comments`
is a FIXED three-part lifecycle text seeded whenever the skill creates the section —
(1) the never-valuable bans (narration of the adjacent line, restated
names/signatures, block-end markers, commented-out code — waste at every phase),
(2) the affirmative construction license (working-memory comments are welcome and
expected mid-build; no razoring, no ad-hoc comment purges), and (3) the consolidation
pointer (the high bar applies at /cleancode time, once the version is done and tests
are green). Style ruling for the whole section: CONCISE over teaching — it loads into
every conversation and its audience is agents, so no explanatory parentheticals
(e.g. "block-end markers" stands unglossed; region markers are covered by the
conventions docs' protected class, not re-explained here). NOTE: the GLOBAL section
already exists — seeded by hand into Keldon's `~/.claude/CLAUDE.md` on 2026-08-26 in
exactly this shape — so the skill's first runs meet pre-existing content and must
merge with it, never re-seed over it.

**Its sibling, `references/comment_conventions.md`, makes the two judgment verbs
symmetrical:** each executes a co-authored convention doc and makes no judgment its doc
doesn't license — `rename` runs on the naming doc, `annotate` runs on the comment doc
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
harvest-stage commit — git history is the deep archive — and it exists as insurance and a
review artifact only. (An earlier design with anchor links from code into a permanent
ledger was deliberately dropped: at post-stabilization time the tests already hold the
pins, so the linked-ledger machinery solved a mid-flight problem the skill never faces.)

**Mechanical work is scripted, judgment is not.** `tools/comments.py` (bundled, stdlib
Python only, the modes-skill precedent) does census/harvest/strip deterministically —
string- and template-literal-aware tokenization per language, so it can never
hallucinate. `rename` and `annotate` are model-driven: they are judgment work.

## Conventions & assumptions

- **Final home:** the ccvi-skills repo (`../skills-anthropic`, installed at
  `~/.ccvi/ccvi-skills`), as `plugin/skills/cleancode/`. This plan's steps use paths
  relative to that skill dir; if the skill stays elsewhere, only the root moves. No
  cross-references to the other skills' behavior are assumed — `/cleancode` stands alone.
- **Supported languages (v1 table):** TypeScript/JavaScript, Rust, Python, Kotlin/Java,
  CSS/Less, Swift. A file outside the table is SKIPPED with a loud line, never
  half-processed. Assumes this covers Keldon's active repos; if not, the table in
  `tools/comments.py` grows — nothing else changes.
- **Protected comment class (never stripped):** license headers, shebangs, tooling
  pragmas (`eslint-disable`, `@ts-ignore`, `noqa`, `# type:`, `#[allow]`-adjacent
  markers inside comments), doc-comments a toolchain consumes for generated API docs
  when the project generates them (a `survey`-reported per-project flag, default off),
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
- **Git discipline:** destructive verbs require a clean working tree at start (the
  readiness gate); each stage commits only the files it touched plus the escrow — never
  `git add -A`. Commit messages: `cleancode <stage>: <path>`.
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
   drop their staging notes. *Why:* `rename` and `annotate` have no authority of their
   own; these docs are their entire license. *Done when:* both docs exist in the skill
   dir, their staging/review sections are gone, and Keldon has explicitly approved
   them.

2. **`skill-scaffold`** — Create `plugin/skills/cleancode/SKILL.md` with frontmatter
   (`allowed-tools: Read, Write, Edit, Glob, Grep, Bash`), the invocation table from the
   Approach, the verbs-are-atoms statement, and the help output listing all seven verbs
   with the signature form `/cleancode verb {required} [optional]`. **The FIRST sentence
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

5. **`survey-verb`** — Write the `survey` verb section: run readiness checks (clean tree
   via `git status --porcelain`, green verdict, no live plan referencing the paths), run
   `comments.py census`, and emit a report: readiness verdict first, then per-file
   ranking by comment mass, counts of commented-out code blocks and live TODO/FIXME
   markers, the NAMING census (symmetry pairs in use with counts, conflicts between
   repo practice and the effective conventions, banned-vagueness hits — grep-driven),
   and a skip list for unsupported files. Then the TANDEM CLOSE: present each census
   conflict via AskUserQuestion (keep the bundled convention / adopt the repo's
   practice / enter another), and write the approved replacements into the managed
   `## Naming & comment conventions` section of the CLAUDE.md the user chooses
   (project or global) — creating it from the SKILL.md template (fixed Comments half +
   collected Naming deltas) or surgically rewriting ONLY that section, merging with
   any pre-existing hand-authored content, authored as plain imperative rules agents
   will follow when naming new files and symbols. Survey never touches code; the section write happens only on explicit
   approval, and declining leaves everything untouched.
   *Done when:* running it against a dirty tree or red suite reports NOT READY and
   names the reason; the census reports the two human-eyes categories; a fixture repo
   speaking show/hide against a display/dismiss doc surfaces the conflict; and an
   accepted override lands in the chosen CLAUDE.md as a well-formed block that a
   second survey run then reads back as the effective convention.

6. **`harvest-verb`** — Write the `harvest` verb section wrapping `comments.py harvest`:
   resolve `[escrowDir]`, write escrow + manifest, echo the escrow path and comment
   count, commit the escrow (`cleancode harvest: <path>`). *Done when:* the escrow files
   contain every comment verbatim and the manifest carries HEAD sha + per-file hashes.

7. **`strip-verb`** — Write the `strip` verb section wrapping `comments.py strip`: the
   freshness gate (refuse, naming the stale/missing file, when manifest hash ≠ disk),
   the protected-class statement, the TODO/FIXME rule (left in place, each flagged in
   the run summary for the human), verdict re-run after the cut, commit
   (`cleancode strip: <path>`). *Done when:* strip on an un-harvested file refuses;
   strip after harvest leaves a comment-free file (protected class and TODO/FIXME
   intact, TODOs flagged) and a green verdict.

8. **`refactor-verb`** — Write the `refactor` verb section: given one `{symbol}` and a
   `{newName}`, enumerate every reference — definition, call sites, imports/re-exports,
   doc-comment mentions — via a repo-wide grep sweep scoped by tier; string-keyed,
   reflective, or serialized uses of the name are FLAGGED in the run summary for the
   human, never silently rewritten; apply all edits, re-run the verdict, commit
   (`cleancode refactor: <symbol> -> <newName>`). *Why:* this is the mechanics atom —
   reference-sweeping lives here and nowhere else. *Done when:* on a fixture with a
   cross-file reference and a same-named string key, the rename lands everywhere except
   the string, the string is flagged, and the verdict stays green.

9. **`rename-verb`** — Write the `rename` verb section: resolve the EFFECTIVE
   conventions — project CLAUDE.md block > global CLAUDE.md block > bundled naming
   doc, merged key-by-key; refuse if not even the bundled doc exists. **`propose`
   mode** walks the target and writes `<path>_rename_proposals.md` — old → new, the
   licensing rule cited, reference count, tier, per line, plus the
   vocabulary-consolidation summary — touching nothing; it is the dry run that
   surfaces the doc's opinions for veto or a conventions change before anything moves.
   **`apply` mode** executes each rename THROUGH the `refactor` verb's mechanics —
   from an edited proposals file when given, else propose-and-apply in one pass — and
   commits the batch (`cleancode rename: <path>`). The verb's brief must state it
   makes no judgment the doc doesn't license. *Done when:* propose writes the report
   and leaves the tree byte-identical; apply on a hand-edited proposals file executes
   exactly the surviving lines; a fixture with a banned-vagueness name gets renamed
   per the doc, `public` symbols are untouched without the opt-in, and the verdict
   stays green.

10. **`annotate-verb`** — Write the `annotate` verb section: read the cleaned code and
    the escrow, execute the effective comment conventions (CLAUDE.md override block
    over `references/comment_conventions.md`, same resolution as rename's) — the bar, the keep-list, the never-restore list with the
    past-tense-change-verbs and "this code now handles" patterns as concrete detection
    examples, the razor as a second independent test, the doubt asymmetry, and the
    breadcrumb rule — writing every survivor **restated timelessly and razored to
    minimum wording** (the ROUND_HALF_UP example goes into SKILL.md as the worked
    case), plus module docs. Commit (`cleancode annotate: <path>`). *Done when:* on the
    fixture set, annotate produces only bar-passing comments, every survivor reads
    timelessly and minimally, keep-list category fixtures (a sync obligation, a
    data-literal unit, a contract docstring) all survive, and the run summary cites
    which escrow entries were dropped, rewritten, and kept-on-doubt.

11. **`run-verb`** — Write the `run` verb section composing survey's readiness gate then
    harvest → strip → rename → annotate with the per-stage verdict + commit contract,
    and the stop rule: any red verdict halts the pipeline, leaves the failing stage
    uncommitted, and reports the last green commit as the rollback point. Every stage's
    run summary follows one shape: **counts** (removed/rewritten/kept per file), **flags**
    (TODO/FIXME, string-keyed rename uses, unclear-code candidates), and **one-line
    judgment calls** the user can overrule. *Done when:* the section spells out the
    exact stop state for a failure at each stage and the summary shape.

12. **`docs-and-edges`** — Finish SKILL.md: edge cases (unsupported file, zero-comment
    file, escrow collision, mid-pipeline interrupt, verdict command not found, a
    static gate present but failing pre-run, an override section whose rules
    contradict each other → surface, never guess), the tools-denied degradation
    section, and
    the NOT-list: not a lint/formatter, not for mid-development use, not a pre-hoc
    authoring style guide (that job belongs to CLAUDE.md rules), no ledger/anchor
    system, no auto-run on a schedule, `public` renames never implicit. *Done when:* every edge case names its behavior and the
    NOT-list matches this plan's Out of scope.

13. **`dogfood-run`** — With Keldon, pick one genuinely stabilized module (small blast
    radius) and take the CAUTIOUS path end to end: `survey` (read the naming census
    together), `harvest`, `strip`, `rename propose` (review the proposals, adjust the
    conventions doc if its opinions misfire), `rename apply`, `annotate` — then confirm
    a plain `/cleancode run` composes the same stages. Review the four stage diffs and
    the escrow together; fold every rough edge back into SKILL.md / `comments.py`. *Done
    when:* the run completes with a green final verdict, Keldon signs off on the diff,
    and any fixes discovered are landed.

**Escape hatch (binding on every step):** if reality diverges from this plan — the
skills-repo layout differs, a language's tokenization turns out infeasible in the script,
the naming doc session changes the rename contract — STOP and surface it; don't
improvise.

## Out of scope

- **Mid-development cleanup.** The skill's identity is post-stabilization; nothing in it
  runs on a project whose tests aren't green, and no "partial/gentle mode" is built.
- **The ledger/anchor system.** Deliberately dropped (see Approach); do not resurrect
  comment-to-ledger links.
- **Formatting, lint, import-sorting, dead-code removal.** Different tools' jobs; the
  skill touches comments and identifiers only.
- **Public-API renames as a default.** `public` tier exists but is opt-in per invocation,
  never part of a plain `run`.
- **CI/scheduled integration.** Human-triggered only.
- **Languages outside the v1 table** — skipped loudly, added later by growing the table.
- **The convention docs' actual content** — both authored collaboratively in todo 1, not
  decided by this plan beyond their required coverage.

## Verification

- `tools/test_comments.py` passes on the per-language fixtures, including string-trap and
  round-trip (harvest + strip + re-paste ⇒ byte-identical) cases.
- Each verb's done-when above holds when exercised against the fixture set.
- The dogfood run (todo 13): a real stabilized module goes through the full pipeline —
  four commits, green verdict after each stage, escrow reviewable, final code readable
  with only bar-passing comments — and Keldon approves the resulting diff.
