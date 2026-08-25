# Comment Conventions

> User divergences override this doc via the shared managed
> `## Naming & comment conventions` section in a project or global CLAUDE.md (project
> section > global section > this doc, merged rule-by-rule) — written as plain
> agent-facing rules, so it also applies pre-hoc in every session: prevention and
> teardown read one rule set.
> Sibling: `naming_conventions.md` (the naming verbs' rails).

These are the rails the `comments annotate` verb executes. It makes no judgment this document
does not license. Context: `comments annotate` runs at the END of the cleancode pipeline, on a
stabilized project whose compound verdict (tests + typecheck/lint) is green — the code
has been stripped of all comments, identifiers have been renamed to be
self-documenting, and the removed comments sit verbatim in the escrow. The job now is
to produce the IDEAL comment set for the finished code: judicious, strategic comments
that genuinely aid grokking and reasoning, augmenting names that already carry the
load. Two sources, one bar: escrow entries whose rationale survives, and brand-new
comments for bar-passing constraints the construction era never documented — the
escrow is evidence, not a ceiling.

## The bar

A comment survives, as briefly as it can be written, only if **both** hold:

1. It states a constraint the code cannot show — a deliberate absence, a policy choice
   ("loud abort here is policy, not a gap"), a non-obvious invariant, the reason a
   tempting simpler version is wrong.
2. No gate enforces it — no test, no typechecker, no linter in this repo would go red
   if the constraint were violated.

Everything with a gate behind it gets nothing: the gate is the durable, executable,
zero-token form of the knowledge, and it fires at exactly the moment someone violates
the constraint. One short module-level doc comment per file is allowed. A one-line
summary on a public function or API surface is allowed — other code consumes those
without reading the body.

## Restate timelessly — never restore verbatim

Every survivor is REWRITTEN in present-tense, timeless form. Hard-won rationale often
arrives in the escrow wrapped in change-narration phrasing; the content survives, the
phrasing does not.

```text
Escrow entry:  We now use ROUND_HALF_UP instead of banker's rounding, which was
               causing off-by-one-cent mismatches with the ledger.
Written back:  ROUND_HALF_UP: banker's rounding produces off-by-one-cent ledger
               mismatches.
```

Deleting such an entry loses real knowledge; restoring it verbatim re-plants the
changelog. The rewrite is the only correct move. Test for every survivor: it must read
correctly to someone seeing the file fresh who never saw any diff, any PR, or any
earlier version.

## The razor — a second, independent test

"Carries a real why" and "is worded minimally" are separate judgments. Genuine
rationale can still be three times too long, and passing the bar is not license to
keep the wording. Cut every survivor to the one non-obvious fact a reader needs at
that line; drop the mechanism the code shows, where a value is consumed downstream,
the consequence-of-the-consequence, and justification-of-the-justification. A
multi-line block is suspect on sight — though length that is genuinely earned (a
workaround plus the bug it works around plus the removal condition) is not a defect;
*unearned* length is. Never shorten at the cost of the information itself. The razored
answer is sometimes zero: delete.

## Doubt is asymmetric

Unsure whether a constraint is gate-enforced? **Keep it** (razored). A wrongly dropped
warning costs a future incident; a mediocre survivor costs a line. Record kept-on-doubt
survivors in the run summary so a human can settle them.

## The never-restore list

None of these comes back from the escrow, ever:

- **Change narration in any form** — past-tense change verbs (added, removed, changed,
  fixed, increased, renamed), "this code now handles" phrasings, "as requested" /
  review-feedback echoes, and any reference to old behavior a fresh reader neither
  knows nor needs. Change context lives in commit messages, and the commits already
  happened.
- **What-narration** — anything restating what the adjacent code visibly does, restated
  names/types/signatures, block-end markers.
- **Commented-out code** — strip deleted it and it stays deleted; version control is
  the archive.
- **Gate-enforced facts** — anything a test, typechecker, or linter in this repo
  already pins.
- **Provenance receipts** — capture citations, commit shas, "VERIFIED at" notes,
  review history, run logs. These were construction scaffolding; the escrow and git
  history retain them.

## The keep-list

Categories that look deletable and are not — each states something the code cannot:

- **Cross-file sync obligations** — "keep in sync with X", "mirrors Y". The link
  itself is the why: it is the only thing stopping two copies drifting apart.
- **Data-literal semantics** — the meaning, order, or units of a literal ("pence, not
  pounds"; "(width, height), portrait"). A literal cannot show its own convention.
- **Presentation/format contracts** — output format pinned to an external expectation
  ("£ with full thousands, matching the dashboard").
- **Contract docstrings** — units, valid ranges, side effects, failure modes,
  invariants, what has already been done to the inputs. A docstring that only re-emits
  the signature is what-narration and gets nothing; condensing a docstring to a
  one-liner is valid only when nothing beyond signature restatement is lost.
- **Surprising-but-essential lines** — the reason a simpler-looking version is wrong,
  when no gate would catch the "simplification".

## References are breadcrumbs, never the substance

A survivor must stand on its own with any link removed — encode the substance, then
optionally append the address. Section numbers of any document are never durable, no
matter the document. A ticket ID, RFC, or maintained doc at a stable repo path may
ride as a trailing breadcrumb.

```text
Bad:   per requirements doc section 3.2
Bad:   see WAGE-1234
Good:  Bacs requires 3 clear working days between notice and collection —
       deliberately not "+3 calendar days" (WAGE-1234).
```

A comment that is nothing but a pointer should generally not exist.

## Out of annotate's hands

- **TODO/FIXME** — strip left these in place and flagged them; annotate neither writes
  new ones nor deletes survivors. Each flagged marker is a human call: stale (delete)
  or live unfinished work (belongs in a tracker).
- **The protected class** — pragmas, license headers, shebangs, toolchain-consumed doc
  comments, and navigation markup (region/endregion, `MARK:`, editor-fold, section
  banners) never left the file; they are `comments.py`'s deterministic concern, not a
  judgment.
- **Unclear code** — a comment is never written to compensate for code that should be
  clearer. If a spot still needs explaining after the rename stage, flag it in the run
  summary as a refactor candidate; do not paper over it.

## Fresh comments

A comment with no escrow ancestor is licensed whenever the bar passes — a non-obvious
invariant, deliberate absence, or policy choice the construction era never wrote
down. Same bar, same razor, same timeless phrasing as every survivor. Fresh
authorship is counted separately in the run summary ("authored fresh: N") — invention
is where a judgment verb most needs human oversight, so it never hides inside the
restoration numbers.

## Run summary

Report counts per file (written back / rewritten from escrow / authored fresh /
dropped), the
kept-on-doubt list, and one-line judgment calls a human can overrule. Do not enumerate
the dropped narration — dropping it is the point of the pipeline, not news.
