# Naming Conventions

> User divergences override this doc via the managed
> `## Naming & comment conventions` section `/cleancode conventions import` writes
> into a project or global CLAUDE.md (project section > global section > this doc,
> merged rule-by-rule) — a section written as plain agent-facing rules, so it also
> governs naming in every session, not just this skill's runs.
> Sibling: `comment_conventions.md` (annotate's rails).

These are the rails the `naming` verbs (`refactor`, `propose`, `apply`) execute. They
make no judgment this document
does not license. Context: `naming apply` runs mid-pipeline on a stabilized project —
comments are already stripped, so names are about to become the primary documentation
of the code. That is the standard: **a name is good when it makes the comment
unnecessary.**

**Scope fence:** this document governs what things are *called* — never how code is
*shaped*. Parameter counts, keyed-object thresholds, function length, structural
patterns, formatting: those are coding conventions, out of scope however adjacent
they feel. The membership test: a rule belongs here only if the `naming` verbs could execute it
by changing a name.

## Goals

- **Self-documenting code** — clear, consistent naming and commenting; everything aids
  the developer in grokking and reasoning about the code.
- Readable, descriptive, and easily understandable by fresh eyes.
- Err on the side of length rather than cryptic brevity.

## The prime directive

Name things for what they mean in the domain, not for what they are mechanically.
`retryBudget` beats `counter2`; `settledInvoices` beats `filteredList`. The read-aloud
test: a line using the name, read as a sentence, should say what the line does —
`if (hasExpiredSession(user)) renewSession(user)` reads; `if (check(u)) doIt(u)` does
not.

## Casing follows the language, always

The `naming` verbs never fight a language's canonical style or its enforced tooling — casing is
the ecosystem's call, and only the *choice of words* is this document's. When in Rome,
we speak Romanese.

| Family | Functions/vars | Types/classes | Constants | Files |
|---|---|---|---|---|
| TypeScript/JS | `camelCase` | `PascalCase` | `SCREAMING_SNAKE` | `snake_case.ts` |
| Rust | `snake_case` | `PascalCase` | `SCREAMING_SNAKE` | `snake_case.rs` |
| Python | `snake_case` | `PascalCase` | `SCREAMING_SNAKE` | `snake_case.py` |
| Kotlin/Java | `camelCase` | `PascalCase` | `SCREAMING_SNAKE` | `PascalCase.kt` (per class) |
| Swift | `camelCase` | `PascalCase` | `camelCase` | `PascalCase.swift` |
| CSS/Less | `kebab-case` classes, `--kebab-case` custom properties | — | — | `snake_case.less` |

Preact component folders are `PascalCase` (`ComponentName/ComponentName.tsx`),
idiomatic for components.

## Acronyms: uniform case, always

An acronym is a single visual token in the reader's mind and keeps one shape wherever
it appears. Four rules:

1. **Uniform case, always.** An acronym is fully upper (`URL`) or fully lower (`url`),
   never mixed (`Url` does not exist, in any position).
2. **Default is UPPER.** A lone acronym with visible boundaries keeps it: `imgURL`,
   `prefixURL`, `PrefixURL`.
3. **The head obeys the casing family.** A camelCase head forces the opening acronym
   fully lower (`fbiURL`, `urlParser`); a PascalCase head forces it fully upper
   (`URLParser`, `SCUBAfbiURL`).
4. **Adjacent acronyms alternate.** Within a run of consecutive acronyms, case flips
   each step so every boundary is carried by a case change; the run starts from
   whatever rule 2/3 gave its first member.

Worked examples (all derivable from the four rules):

```text
camelCase:   imgURL   fbiURL   scubaFBIurl   prefixURL   userID
PascalCase:  URLParser   URLfbiParser   SCUBAfbiURL   PrefixURL
pairs:       type URLParser  /  instance urlParser
```

- **`ID` is acronym-class** by explicit ruling: always `ID` or `id`, never `Id`
  (`userID`, `idByUser`, `IDParser`).
- **A standalone acronym as an entire name** takes the family's normal casing in full:
  a local `url`, a constant `URL`, a class `URL`. No special rule, no two-letter
  exception — the uniform-case law covers every width.
- **Snake_case contexts flatten everything.** Underscores carry the boundaries, so all
  tokens — acronyms included — are uniformly lower (`user_id`, `img_url_cache`,
  `parse_url`) or uniformly upper in `SCREAMING_SNAKE` (`MAX_URL_LENGTH`, `USER_ID`).
  The alternation machinery applies to the humped families (camelCase, PascalCase)
  only.

## General-to-specific, left to right (the Yoda rule)

**The common component of a name goes left-most; the specific differentiator goes
right-most.** This often inverts natural English — the noun leads and the adjective
trails, hence the house name, the **Yoda rule**: `buttonLeft`/`buttonRight`, not
`leftButton`/`rightButton`. Backwards it reads; grouped it sorts. The payoff is that
any alphabetized listing — a file tree, an autocomplete dropdown, a symbol picker, a
constants block — collects a family into one contiguous, scannable run:

```text
Variables:    buttonLeft, buttonRight, buttonSubmit     (not leftButton)
Files:        redeploy.sh, redeploy_sidecar.sh          (not sidecar_redeploy.sh)
Constants:    SORT_CASEINSENSITIVE, SORT_DESCENDING,
              SORT_NUMERIC                              (not NUMERIC_SORT)
Functions:    menuBuild, menuItemDismiss, menuItemDisplay (not dismissMenuItem)
Fields:       timeoutConnectMs, timeoutReadMs           (not connectTimeoutMs)
```

Written specific-first, the same family scatters across the alphabet and the reader
reassembles it by memory; written general-first, sorting does the assembling. The rule
applies to every named thing — identifiers, constants, files, CSS classes, escrow
entries — and it is a *family* rule: it binds hardest when several names share a stem,
and a standalone name with no siblings may keep natural English order where that reads
better (`hasExpiredSession`, not `sessionExpiredHas` — question prefixes and other
grammatical markers stay in their grammatical position). When the two forces conflict
on a family, grouping wins: the whole point of a shared stem is to be shared at the
left edge.

## Functions are verbs

- **Commands** (do something) are imperative verb-noun: `flushQueue`, `resolveVerdict`,
  `emitPlacement`. A *family* of commands sharing a stem groups Yoda-style
  (`menuItemDismiss`, `menuItemDisplay`); a *standalone* command stays natural
  imperative verb-noun (`flushQueue`). Grouping wins on conflict, per the Yoda rule.
- **Queries** (return something, change nothing) name what they return:
  `activeSession`, `commentMass`, or `get…` only when a bare noun would collide.
  A function name that promises a query must not hide a command.
- **Boolean-returning** functions and predicates take a question prefix (see
  **Booleans** below): `isStale`, `hasEscrow`, `canStrip`.
- **Events and their handlers are PAST TENSE**: `buttonClicked`, `formatRequested`,
  `dataReceived`, `sessionExpired`. The tense carries flow information — past tense
  says the thing has already happened, so there is no doubt where in the sequence this
  name lives; a present/imperative form (`clickButton`, `requestFormat`) would read as
  the command that *causes* the event. Note the shape is also Yoda-compliant: subject
  first, so `buttonClicked`/`buttonPressed`/`buttonReleased` group.
  **Avoid `on` naming** (`onLoad`, `onDataReceived`) except to meet a platform spec
  (`onClick` in React props, DOM `onclick`) — spec-mandated spellings are wire-tier
  and stay.
- **Banned generic verbs** unless the domain genuinely means them: `process`, `handle`
  (outside events), `manage`, `do`, `perform`, `execute` (outside an executor domain —
  an interpreter loop or a `Stage3dExecutor` legitimately `execute`s; there it is the
  domain word, not a vagueness). Each hides the actual effect — name the effect.

## Variables are nouns

- **Booleans** take a question prefix. The canonical five: `is`, `has`, `can`,
  `should`, `needs` — an **open family, not a closed list**: any prefix qualifies when
  the resulting name reads as natural language at the use site
  (`if (document.wasRequested || request.isPending)` — `was` earns its place by the
  read-aloud test). Never bare adjectives (`ready`) that read as nouns elsewhere.
- **Negated names are banned** (`isNotReady`, `hasNoItems`, `disableSkip = false`) —
  name the positive and negate at the use site. **One narrow carve-out:** a negative
  word that is itself a first-class domain term (`isDisabled`, `isHidden`,
  `isMissing`, `isReadOnly`) or mirrors an external API's established vocabulary. The
  test: the name encodes a *negative concept*, not a negated positive — and it must
  never force double negation at call sites (`if (!isNotReady)` is the smell this ban
  exists to kill).
- **Collections are plural** (`placements`, not `placementList`); a map names both
  sides: `depthByChildId`, `verdictForTodo`.
- **Units live in the name when the type doesn't carry them:** `delayMs`, `widthPx`,
  `sizeBytes`, `txTwips`. A raw number with unstated units is a bug nursery. (This is
  semantic units as suffixes — not Hungarian notation; see Anti-conventions.)
- **Scope-proportional length:** a three-line loop may use `i`; anything exported
  carries its full meaning. The bigger the scope, the more the name must explain.

## Banned vagueness

These never appear unqualified in an identifier: `Manager`, `Helper`, `Util`/`Utils`,
`data`, `info`, `item`, `obj`, `temp`, `misc`, `stuff`, `thing`, `flag`, `value`
(where a domain word exists). Each is a placeholder for a name someone didn't find —
find it: a `SessionManager` is really a `SessionRegistry`, a `SessionPool`, or a
`SessionLifecycle`, and which one it is, is exactly what the reader needs to know.
Single letters are allowed only in idiomatic tight scopes: loop indices, `e` in a
one-line event/exception handler, conventional math (`x`, `y`, `dx`).

## Abbreviation policy: the blessed list

Whole words by default — abbreviations are avoided unless **blessed**. A blessed
abbreviation targets **three letters or fewer** (four in rare cases — `spec` — five
rarer still); a word that can't compress that far is written out in full. New
abbreviations are never invented outside the list; a repo blesses more via the managed
CLAUDE.md conventions section.

**Blessed abbreviations are word-class for casing** — they camel-hump like ordinary
words (`subStr`, `imgBtn`, `AppConfig`), never taking the acronym uniform-case law.
`id` and `url` are deliberately absent from this list: they are **acronym-class**
(`ID`/`id`, `URL`/`url` — see Acronyms).

| abbreviation | word | note |
| :-- | :-- | :-- |
| app | application | |
| args | arguments | |
| btn | button | |
| cb | callback | |
| config | configuration | grandfathered over the length goal |
| ctx | context | where the ecosystem does |
| db | database | |
| dev | development or developer | |
| dir | directory | |
| doc | document | |
| dst | destination | pairs with `src` |
| e | event | |
| err | error | |
| fn | function | where the ecosystem does |
| idx | index | tight scope only |
| img | image | |
| init | initialize / initialization | |
| max / min | maximum / minimum | pair |
| num | number | |
| prev / next | previous / next | pair |
| snd | sound | |
| spec | specification | |
| src | source | pairs with `dst` |
| str | string | |
| txt | text | |
| vid | video | |

Domain-established terms of art (`twips`, `cxform`, `iinit` in a Flash codebase) are
words, not abbreviations, and stay.

## One term per concept

Within a repo, pick one word per concept and hold it: `fetch` vs `load` vs `get` vs
`retrieve` — one of them, everywhere, for the same kind of operation. Synonym drift is
how a reader ends up believing two names do different things when they don't. `naming propose`
should propose consolidation toward whichever term the repo already uses most.

## Symmetry pairs: one pair per concept, never mixed

Two rules, both binding:

1. **An operation and its inverse come from the same pair** — an `openConnection`
   closed by `destroyConnection` is a defect; propose the matching half.
2. **One CANONICAL pair per concept, repo-wide.** English offers many pairs for the
   same concept, and a repo that uses several has the synonym-drift problem twice
   over. Choose one and hold it everywhere. The canonical example — visibility is
   **`display`/`dismiss`**, and NOT `show`/`hide`, `reveal`/`cover`,
   `onScreen`/`offScreen`, or any other pair meaning the same thing coexisting with
   it. Other established pairs: `add`/`remove`, `open`/`close`, `start`/`stop`,
   `begin`/`end`, `create`/`destroy`, `enable`/`disable`, `attach`/`detach`,
   `push`/`pop`, `acquire`/`release`, and **`intro`/`outro`** for transitions. When
   the `naming` verbs find two pairs serving one concept, it consolidates toward the repo's
   dominant pair (or the doc's canonical choice where the repo is split).

**Layered vocabularies — one pair per LAYER, not just per concept.** A lifecycle has
distinct layers, and each owns its own vocabulary, so a name alone tells the reader
which layer it lives in. The visibility lifecycle, fully worked:

```text
Command (imperative):   displayMenu / dismissMenu     — the request
Transition (in flight): intro / outro                 — the animation each triggers
State (settled):        isMenuDisplayed, menu.isDisplayed — the boolean that results
Event (past tense):     menuDisplayed / menuDismissed — the announcement it happened
```

Reusing one layer's words in another (`showMenu` firing a `display` transition that
sets `menuShown`) collapses the layers and the reader loses the flow position the
vocabulary was carrying. This is the same principle as past-tense events: tense and
vocabulary encode WHERE in the sequence a name lives. The `was` prefix is the state
residue of a past-tense event: `documentRequested` fires, and `wasRequested` is
thereafter true.

**Canonical-vocabulary choices are the override zone.** The mechanism rules in this
doc (Yoda ordering, question prefixes, past-tense events, one-pair-per-concept) are
close to universal; WHICH pair a concept gets (`display`/`dismiss`, `intro`/`outro`)
is taste, and it is exactly what the managed CLAUDE.md conventions section is for —
`conventions generate` surfaces repo practice with usage counts and era trends, and
`conventions import` writes
the user's choices there as ordinary agent-facing rules, where they steer every future
coding session — new files and symbols included — not just this skill's runs.

## Directories & files

Goals: simplicity · meaningful alphabetizing in file systems · URL-friendly
(guaranteed uniform treatment across web servers and operating systems).

1. **Character set:** alphanumerics plus `_` underscore and `.` dot, in that order of
   preference. **Hyphens are forbidden** in names we author — the hyphen is an
   operator, so a hyphenated file name can never match the identifier of anything
   inside it; underscores keep filename↔symbol symmetry. Names mandated by a tool,
   platform, or third party (package names, vendored files, host-owned dot-dirs) are
   wire-tier: leave them, flag them, don't fight them.
2. **No spaces, ever** — spaces URL-encode badly and break path-hostile tools;
   underscores instead.
3. **All lowercase**, one exception: code source files may match the case of the
   class/component they house (`URLParser.swift`, `ComponentName/ComponentName.tsx`),
   per the casing table.
4. **Snake_case strongly preferred** for file and folder names except where coding
   conventions require PascalCase or camelCase.
5. **General → specific, left → right** — the file-system face of the Yoda rule;
   families sort contiguously.
6. **Dates in names are `YYYY.MM.DD`** — alphabetized lists are also chronological.
7. **Simple, brief, descriptive** — enough to tell what a file is without opening it,
   short of `gone_with_the_wind_in_its_entirety`.

```text
btn_arrow_left.png
btn_arrow_right.png
spec_tmo_minus_one.docx
notes_brainstorm_products_2020.03.15.docx
```

**Prospective-only:** these rules govern newly created names and deliberate renames.
Existing file and folder names are grandfathered — neither the `naming` verbs nor any cleancode
stage proposes a sweep to retro-fit them.

## Anti-conventions

- **Hungarian naming** — type prefixes (`strName`, `iCount`, `m_widget`) never appear.
  Distinguish from the required units-as-suffix rule (`delayMs`, `widthPx`): units are
  semantics the type system doesn't carry; Hungarian restates the type, which the code
  already knows.
- **`on`-style handler names** outside platform specs — see Functions are verbs.
- **Negated booleans** outside the domain-term carve-out — see Variables are nouns.

## What the naming verbs do not touch

- **Casing enforced by tooling** (gofmt-class rules) and language-idiomatic
  conventions — this doc chooses words, not war with formatters.
- **Wire/serialized names** — anything whose spelling is a protocol, file-format, or
  API contract (JSON keys, protocol fields, CSS classes consumed elsewhere,
  spec-mandated `onClick`-style handler props). These are `public`-tier at minimum and
  usually not renameable at all; flag, don't rewrite.
- **Names quoted in strings, reflection, or docs** — `naming refactor` flags these
  for the human; it never silently rewrites string content.
- **Existing file/folder names** — the Directories & files rules are prospective-only.
