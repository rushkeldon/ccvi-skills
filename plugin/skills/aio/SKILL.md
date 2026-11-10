---
name: aio
description: hashcmd write•list•show•move•archive and html write•list•url•archive•toast - author and manage the CCVI aio workspace at two scopes (this project's aio or the global aio) via /aio [noun] [verb]. hashcmd manages hash commands (`#name payload` turns the sidecar expands); html scaffolds, lists, locates, retires, and displays as a macOS toast the web pages, sites, and apps the sidecar serves at /aio/<name>/ on each window's loopback port, with live JSON data push, a file-backed store, and controls that send #commands back as ordinary turns. Use when the user or an agent wants to create, inspect, promote, demote, or retire a #command, asks what #commands resolve here, wants a dashboard, status page, or any served page for this project or every project, or wants to notify the user or ask them a choice with a toast.
argument-hint: "[noun] [verb] {name} [scope]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(ls:*), Bash(mkdir:*), Bash(mv:*), Bash(cat:*), Bash(~/.ccvi/node/current/bin/node:*)
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host that renders a verb menu and
# generates each verb's dialog from `params`. Every fact here MUST also be stated in
# the prose - the skill stays fully usable in vanilla Claude Code. Verb keys are
# noun-first TWO-WORD strings ("hashcmd write"); consumers treat them as opaque.
verbs:
  "hashcmd write":   { order: 1, params: [ { name: name,  type: string, required: true },
                                           { name: scope, type: string, required: false, default: project } ] }
  "hashcmd list":    { order: 2, params: [ { name: scope, type: string, required: false } ] }
  "hashcmd show":    { order: 3, params: [ { name: name,  type: string, required: true } ] }
  "hashcmd move":    { order: 4, params: [ { name: name,  type: string, required: true },
                                           { name: scope, type: string, required: true } ] }
  "hashcmd archive": { order: 5, params: [ { name: name,  type: string, required: true } ] }
  "html write":      { order: 6, params: [ { name: name,  type: string, required: true },
                                           { name: scope, type: string, required: false, default: project } ] }
  "html list":       { order: 7, params: [ { name: scope, type: string, required: false } ] }
  "html url":        { order: 8, params: [ { name: name,  type: string, required: true } ] }
  "html archive":    { order: 9, params: [ { name: name,  type: string, required: true } ] }
  "html toast":      { order: 10, params: [ { name: name,  type: string, required: true },
                                            { name: scope, type: string, required: false } ] }
---

# aio

The **aio workspace** (`ai` + `io`) is where a CCVI window's hash commands and html live. This
one skill manages both, as two nouns:

- **`hashcmd`** - hash commands. A user turn that starts with `#name` is expanded by the CCVI
  sidecar from `<scope>/hash_cmds/<name>.md` before it reaches the model.
- **`html`** - web pages, sites, and apps the sidecar serves from `<scope>/html/<name>/` over
  the loopback port each window already binds. A page can send `#commands` back as ordinary
  user turns, so the two nouns work as a pair.

Both nouns share one invariant: the scope rule (project first, then global), the
`<ccvi-aio>` sentinel, the project prefix, and **never deleting** (retiring is a move into an
`archive/` folder). The contract is ccvi-idea's `doc/contracts/aio.md`.

## Where everything lives

One layout at two scopes:

```text
~/.ccvi/aio/                                          global - every project
  hash_cmds/<name>.md
  html/<name>/index.html, data/*.json                 served by EVERY window at /aio/ccvi/<name>/
  html/index.html                                     optional; replaces the built-in /aio/ccvi/ listing
  html/ccvi_store.json                                the shared store, for values every page wants
~/.ccvi/projects/<encodedProjectPath>/aio/            project - wins on a name collision
  hash_cmds/<name>.md
  html/<name>/index.html, data/*.json                 served by THIS window at /aio/<name>/
  html/index.html                                     optional; replaces the built-in /aio/ listing

Inside any html/<name>/ (either scope):
  ccvi_manifest.json                                  optional metadata: label, order, hidden, failover, toast
  data/ccvi_store.json                                the page's store (created on first write)
  data/instance_<id>.json                             one displayed instance's own data (a toast)
html/themes/<name>.css                                a toast theme: one CSS file
```

**Resolve both paths, and the page-server origin, from the `<ccvi-aio>` sentinel** the CCVI
host injects into the turn context (highest `epoch` wins; a verbatim, well-formed block only;
a paraphrase is not a sentinel):

```text
<ccvi-aio epoch="2">
global: /Users/k/.ccvi/aio
project: /Users/k/.ccvi/projects/-Users-k-Desktop-working-projectx/aio
prefix: projectx-
url: http://127.0.0.1:17396/
toast: /Users/k/.ccvi/toast/toast_display.mjs
</ccvi-aio>
```

`url` is this window's page-server origin. It is absent until the server has bound; a later
turn carries a new block with a higher `epoch` that has it. `toast` is the toast script's
absolute path, present only on macOS with the toast host installed: **no `toast` line means
toasts are unavailable on this host.**

Every worktree of a repository shares the same project aio (the host links them), so anything
written in one worktree window is visible in all of them.

**No sentinel in context** (a session outside CCVI): the global scope is `~/.ccvi/aio`; the
project scope and prefix are UNKNOWN. Say so. Operate on the global scope only when the user
explicitly asks for `global`; otherwise ask rather than guess a project path.

### The project prefix

Project-scope command names start with the project's **prefix** (the sentinel's third line,
`projectx-` for a repo whose main checkout is `projectx`). It is a courtesy, not a correctness rule: a
bare `#name` only ever resolves against THIS project and the globals, so two projects sharing a
name never meet. The prefix keeps project names out of the space the global commands use, so
a project command never silently shadows a global one. `hashcmd write` applies it by default.

### `name`

`[A-Za-z0-9][A-Za-z0-9_-]*` - a leading alphanumeric, then alphanumerics, `_`, or `-`. No
spaces, no dots, no leading `#` (strip one if given). For `hashcmd` the filename is always
`<name>.md`, 1:1; for `html` the name is the folder and the URL segment. A name that fails the
grammar is refused with the rule quoted.

## Invocation

Single entry point - **`/aio [noun] [verb] [args]`**, dispatching on the first two args:

| Form | Effect |
|---|---|
| `/aio hashcmd write {name} [scope]` | Author or overwrite `<scope>/hash_cmds/<name>.md`; `scope` is `project` (default) or `global` |
| `/aio hashcmd list [scope]` | What resolves right now: project then global, collisions marked, with which one wins |
| `/aio hashcmd show {name}` | Print the file that would win for `#name`, and its path |
| `/aio hashcmd move {name} {scope}` | Promote a project command to global, or demote a global one to project |
| `/aio hashcmd archive {name}` | Move the winning definition into `<its scope>/hash_cmds/archive/`; never deletes |
| `/aio html write {name} [scope]` | Scaffold `html/<name>/index.html` and `data/` at `scope` (`project` default, or `global`) |
| `/aio html list [scope]` | The html entries that exist, with their labels and URLs |
| `/aio html url {name}` | Print the URL of an entry (project first, then global) |
| `/aio html archive {name}` | Move `<scope>/html/<name>/` into `<scope>/html/archive/<name>/`; never deletes |
| `/aio html toast {name} [scope]` | Display an entry as a macOS toast through the toast script; `scope` pins `project` or `global` (default: project first, then global) |
| `/aio` (no args) | Print the help cheat-sheet (see **Help output**) |

Nouns and verbs are lowercase. A bare noun (`/aio hashcmd`, `/aio html`) prints the help
output. Natural language maps the obvious way: "make a hash command for X" -> `hashcmd write`;
"what #commands do I have?" -> `hashcmd list`; "retire #foo" -> `hashcmd archive`; "make me a
dashboard for X" -> `html write`; "where is my status page?" -> `html url`; "ping me when this
is done" or "ask me with a toast" -> `html toast`.

---

## Noun: hashcmd

A hash command's definition is expanded by the sidecar: it resolves
`<scope>/hash_cmds/<name>.md`, project scope first and then global, and sends the file's
content inside a `<ccvi-hash-cmd>` wrapper with the payload after it. **The agent never reads
the definition file at run time**, so this noun is about AUTHORING and MANAGING definitions,
not running them. Running one is typing `#name payload`.

### `hashcmd write`

`/aio hashcmd write {name} [scope]`

1. Resolve the scopes from the sentinel. Default `scope` is `project`.
2. **At project scope, apply the prefix** unless `name` already starts with it: `hashcmd write
   ack` in the projectx window creates `projectx-ack.md`. If the user gives an unprefixed project name
   on purpose, say what global command it would shadow, if any (`ls <global>/hash_cmds/`),
   and write it unprefixed only after they confirm.
3. At global scope, warn when a project command of the same name exists (the project one
   will win in that project) and continue.
4. Author the body from the conversation if none was given: a command file **is the prompt**
   the model receives. Write it as instructions to the agent that will run it, in the second
   person, and say how to read the payload (see **Authoring a command** below).
5. `mkdir -p` the `hash_cmds/` dir, write the file, and echo the absolute path plus one line
   on how to run it: `#projectx-ack <payload>`.

An existing file is OVERWRITTEN only when the user asked to write that exact name; say so in
the echo. `hashcmd write` never touches the other scope.

### `hashcmd list`

`/aio hashcmd list [scope]` - glob `<project>/hash_cmds/*.md` and `<global>/hash_cmds/*.md`
(skipping `archive/` and `lib/`), and print one table: name, scope(s) it exists in, and
`wins` for the one the sidecar would use. A name present in both is a **collision**: mark it
and name the project file as the winner. With `scope` given, list only that scope. Nothing is
written.

### `hashcmd show`

`/aio hashcmd show {name}` - print the path and full contents of the file that would win for
`#name` (project first). When both exist, add one line naming the shadowed global path. When
neither exists, say so and list near-miss names (same prefix, or a one-character difference).

### `hashcmd move`

`/aio hashcmd move {name} {scope}` - `mv` the definition from its current scope into `scope`.
Refuse when the destination already has that name (never clobber; suggest `hashcmd archive`
first). Moving project -> global drops nothing from the name: `projectx-ack` stays `projectx-ack`
globally unless the user asks to rename it in the same breath. Moving global -> project does
NOT add the prefix automatically; say so and offer it. Echo both paths.

### `hashcmd archive`

`/aio hashcmd archive {name}` - `mv` the WINNING definition into
`<its scope>/hash_cmds/archive/<name>.md` (creating the dir). Never delete. If the move
exposes a global command that the project one had shadowed, say so. Echo the new path.

### Authoring a command

A command file is plain markdown and **is the prompt**. The sidecar wraps it:

```text
<ccvi-hash-cmd name="projectx-ack" scope="project" path="/Users/k/.ccvi/projects/.../aio/hash_cmds/projectx-ack.md">
...the file, trimmed...
</ccvi-hash-cmd>
PD-123 looks resolved
```

So the file should:

- open with one line saying what the command does;
- say how to interpret **the payload** (everything after the closing tag): positional words,
  an id, free prose, or nothing;
- give the steps, the files or tools involved, and what "done" looks like;
- say what to report back, and keep it short - the whole file rides in the turn.

A minimal template:

```text
Acknowledge a PagerDuty incident and record it in today's status.

Payload: an incident id (`PD-123`), optionally followed by a note.

1. Read ~/.ccvi/aio/status/status_<today>.md and find the incident.
2. Mark it acknowledged with the note, if any.
3. Reply with one line: the id and its new state.
```

Html entries emit commands too: an entry's `actions.json` maps a control to a template such as
`#projectx-ack {alertId}` (see **Actions** under the `html` noun). Design the payload so a page can
fill it from one row.

---

## Noun: html

The folder is named `html` after the classic web-server document root (`/var/www/html`,
`~/public_html`). Each entry under it is a folder that may be a webpage, a website, or a web
app. An entry is plain HTML plus ES-module or classic script, with no build step and nothing
loaded from a CDN. The server **injects** the runtime, `/ccvi.js`, at the top of `<head>` of
every html document it serves, so a page carries no script tag for it (an old page that still
has one is harmless). The runtime connects back to the window that served the page and gives
it `window.CCVI`: live JSON data pushed from `data/*.json`, the window's idle/working status, a
file-backed store, and `CCVI.send(text)`, which submits an ordinary user turn, so a button can
emit a `#command`.

Agent to page is **files**: the agent writes `html/<name>/data/*.json` with its normal Write
tool and every connected page re-renders. Page to agent is **a user turn**: a click is a human
action, the same as typing.

**A page and a toast are the same thing.** The only difference is where it is displayed: a
browser tab, or the native macOS toast host. A toast is an ordinary entry in `html/`, uses the
same runtime, and can be opened in a browser to develop it.

### Page rules (binding for every page this skill writes)

- **Compact-first; layout follows the viewport width** through ordinary responsive CSS (base
  styles for a narrow card, `@media (min-width: ...)` to grow). A page never needs to know the
  manifest's numbers.
- **`data-display` on `<html>` is for host chrome only**: a transparent background, whether
  dismiss and maximize controls exist. `CCVI.display` is an open set (`browser`, `toast`, more
  later), so never write `display === 'browser' ? a : b`. A toast's panel is always
  transparent; the page paints everything visible, so a full-page background shows as a solid
  rectangle.
- **A page reaches a window only through `window.CCVI`.** Never `fetch` the page's own origin
  and never read `location.host`.
- **A toast never sends without a click.** No `CCVI.send` from a timer, a load handler, or the
  dismiss event. A timeout only dismisses.
- **The body's own height is the toast's height**, so never give `body` a percentage height.

### URLs

Build every URL from the sentinel's `url` line: project html is `<url>aio/<name>/` and global
html is `<url>aio/ccvi/<name>/`. **Trust the sentinel over the capability blurb.** A resumed
session replays the system prompt snapshotted when it was created, so its blurb can predate
the aio feature or name a stale port. When the sentinel has no `url` line, read the live
registry instead: `~/.ccvi/live_projects/*.json`, field `reach.lan`, on the entry whose
`project` is this project's folder name. Never guess a port.

```text
/aio/                    this project's index: html/index.html if present, else a built-in listing
/aio/<name>/             <project aio>/html/<name>/
/aio/ccvi/               the global index: html/index.html if present, else a built-in listing
/aio/ccvi/<name>/        <global aio>/html/<name>/
/                        the hub: every live CCVI window on this machine
/p/<project>             redirects to that project's window, so a bookmark to any live port reaches any project
```

A folder URL without its trailing slash (`/aio/monkey`) redirects to `/aio/monkey/`, so
relative links inside the entry resolve against its folder. The Session Panel's globe button
opens `/aio/`, and its menu lists both scopes' entries by label.

**Reserved names.** `html write` refuses `ccvi` (the URL segment for the global scope, so a
project entry by that name could never be reached), `archive` (where `html archive` moves
retired entries; never listed), `index` (the global `html/index/` folder overrides the hub at
`/`), and `themes` (toast themes). `options` and `turn_end` are the two **built-in** global
pages; writing one at global scope is allowed only when the user asks to override the
built-in, and a real folder of that name then wins.

### The manifest (`ccvi_manifest.json`)

The one home for an entry's metadata. Every key is optional; no file means defaults:

```json
{
  "label": "Status board",
  "order": 1,
  "hidden": false,
  "failover": true,
  "toast": {
    "width": 360,
    "height": null,
    "timeoutMs": 0,
    "capturesOutside": false,
    "description": "One line: what this toast does.",
    "useWhen": "One line: when an agent should display it.",
    "fields": {
      "title": { "required": true },
      "body": { "note": "plain text" }
    }
  }
}
```

- `label` names the entry in listings and the globe menu (else `<title>`, else the folder
  name); `order` sorts ascending, unset last, then by label; `hidden` leaves it out of listings
  while its URL still serves. Two entries with the same label each get ` · <name>` appended.
- `failover` (default true): when the serving window goes away, the page reloads on another
  window. `false` opts out.
- `toast.width` defaults to 360; `height: null` means "measure the content". A page whose
  `toast` has a `description` is advertised by the toast script's `list`; any page can still
  be displayed by name. `fields` is what `display` validates the data against.
- Older pages carry `<meta name="ccvi:label|ccvi:order|ccvi:hidden">` tags instead. Those still
  work as a fallback, and the manifest wins over them. Do not write them in new pages.

### `html write`

`/aio html write {name} [scope]`

1. Resolve the scope dir from the sentinel. Refuse the reserved names (see **Reserved
   names**). Refuse to overwrite an existing `index.html` unless the user asked to rewrite that
   entry.
2. Create `html/<name>/data/` and write `index.html` from the template below, substituting
   `NAME` and `LABEL` (a short human label; default `NAME`). Adapt the body to what the user
   wants the page to show, following the **Page rules**; keep the data wiring. Write no
   `<script src="/ccvi.js">` tag and no `ccvi:*` meta tags.
3. Write `ccvi_manifest.json` with `label`. Add `order` or `hidden` when the user asks for an
   order or for the entry to stay out of the menu, and a `toast` block (with `description`,
   `useWhen`, and `fields`) when the page is meant to be displayed as a toast.
4. If the page has controls, write `data/actions.json` (see **Actions**) and the hash commands
   those actions emit (`/aio hashcmd write ...`), using the project prefix.
5. Echo the absolute dir and the URL (`/aio html url {name}`).

**The scope index.** When the user asks to "make the index" (for a scope, with no `name`),
write `<scope>/html/index.html` instead of a folder. It replaces the built-in listing at
`/aio/` (project) or `/aio/ccvi/` (global). Link entries with relative URLs (`status/`), and
link the other scope's index and `/`.

#### Template

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LABEL</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; padding: 8px; font: 14px/1.4 system-ui, sans-serif; }
  .card { padding: 12px; border-radius: 12px; background: Canvas; }
  .row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 6px 0; }
  .status { opacity: .6; font-size: 12px; }
  button { font: inherit; padding: 4px 10px; border-radius: 8px; }
  @media (min-width: 640px) { body { padding: 24px; } .card { max-width: 960px; margin: 0 auto; } }
  html[data-display="toast"] body { background: transparent; }
</style>
</head>
<body>
<div class="card">
  <h1>LABEL <span class="status" id="status"></span></h1>
  <label><input type="checkbox" id="compact"> compact</label>
  <div id="root">loading...</div>
</div>
<script>
  var actions = [], last = null;
  CCVI.onStatus(function (s) { document.getElementById('status').textContent = s; });
  CCVI.onData('actions.json', function (json) { actions = (json && json.actions) || []; if (last) { render(last); } });
  // A toast carries its own data (data/instance_<id>.json); a browser tab reads the shared file.
  if (CCVI.instance) { CCVI.onInstance(render); } else { CCVI.onData('NAME.json', render); }
  // The store persists across reloads and copies of this page; the user's view choice lives there.
  var box = document.getElementById('compact');
  box.checked = !!CCVI.store.read('isCompact');
  box.onchange = function () { CCVI.store.write('isCompact', box.checked); if (last) { render(last); } };
  CCVI.store.onChanged(function (key, value) { if (key === 'isCompact') { box.checked = !!value; if (last) { render(last); } } });
  function render(json, error) {
    var root = document.getElementById('root');
    if (error) { root.textContent = 'data error: ' + error; return; }
    last = json;
    root.innerHTML = '';
    (json.rows || []).forEach(function (row) {
      var div = document.createElement('div');
      div.className = 'row';
      div.textContent = box.checked ? (row.title || '') : (row.title || JSON.stringify(row));
      actions.forEach(function (a) {
        var b = document.createElement('button');
        b.textContent = a.label;
        b.onclick = function () { CCVI.send(fill(a.prompt, row)); };
        div.appendChild(b);
      });
      root.appendChild(div);
    });
  }
  function fill(tpl, row) { return tpl.replace(/\{(\w+)\}/g, function (_, k) { return row[k] == null ? '' : String(row[k]); }); }
</script>
</body>
</html>
```

The data file the template reads is `data/NAME.json`, shaped `{ "rows": [ { "title": ..., ... } ] }`.
Change the shape freely; the only fixed parts are the `CCVI.onData` / `CCVI.onInstance` wiring.

#### Actions

Controls are DATA, not HTML, so the agent can add one without touching the page:

```json
{
  "actions": [
    { "id": "ack",     "label": "Ack",     "prompt": "#projectx-ack {alertId}" },
    { "id": "explain", "label": "Explain", "prompt": "#projectx-explain {alertId}" }
  ]
}
```

`prompt` is a template filled from the row's fields and sent with `CCVI.send`. Each send is
one user turn, so give toggles an Apply button rather than firing per change. Name the
commands with the project prefix and author them with `/aio hashcmd write`.

#### The runtime API (`/ccvi.js`)

```text
CCVI.page, CCVI.scope          this entry's name and scope (from the server, else the URL)
CCVI.display                   'browser' | 'toast' | ... (open set); also data-display on <html>
CCVI.send(text, { to }?)       submit a user turn; resolves { ok, reason? }. No 'to' = the serving window;
                               'to' = a sidecar pid, an absolute git dir, or a project folder name
                               (resolved at click time; ok for another window means queued)
CCVI.focusWindow({ to }?)      raise this window or another; never a turn, works mid-turn
CCVI.onData(file, fn)          fn(json, error, frame) for data/<file> on attach and on change ('*' for all)
CCVI.instance                  this display's instance id, or null
CCVI.onInstance(fn)            like onData for data/instance_<id>.json; frame.removed = dismissed elsewhere
CCVI.store.read(key)           the page store (data/ccvi_store.json); null when unset
CCVI.store.write(key, value)   resolves { ok, reason? }; null removes the key
CCVI.store.onChanged(fn)       fn(key, value) when ANOTHER copy or an agent changed a key
CCVI.store.shared.*            the same three, on <global aio>/html/ccvi_store.json
CCVI.onStatus(fn)              fn('idle' | 'working')
CCVI.onFailover(fn)            fn('live' | 'lost' | 'moving')
CCVI.directory(fn)             fn(directoryState | directoryAdd | directoryRemove) - every live window
CCVI.toast.dismiss(reason?) / maximize() / restore() / resize({ width, height } | null)
CCVI.toast.captureOutside(bool) / saveState(json) / playSound(name) / isMaximized()
CCVI.toast.on(event, fn)       displayed | dismissed | maximized | restored | clickedOutside
```

The `toast` controls exist in every display, so a page never tests for them; in a browser they
flip the same attributes with no host behind them, which is how a toast is styled in a browser.
`<html>` carries `data-display`, `data-toast-state` (`restored` | `maximized`), and
`data-toast-phase` (`intro` | `shown` | `outro`). The custom properties
`--ccvi-toast-restore-ms` and `--ccvi-toast-outro-ms` on `<html>` give the restore and outro
transitions time to run. Last writer wins on a store key; there is no locking.

The runtime reconnects with backoff and queues sends while disconnected. Failover is a reload,
so unsaved in-page state is lost: keep anything worth keeping in the store.

### `html list`

`/aio html list [scope]` - glob `html/*/index.html` in both scopes (or the one given),
skipping `archive/` and `themes/`, and print name, scope, label (the manifest's `label`, else
the `ccvi:label` meta, else the `<title>`, else the name; mark hidden entries), and URL.
Nothing is written. The built-ins `options` and `turn_end` have no folder; list them as
built-in global entries unless a real folder overrides them.

### `html url`

`/aio html url {name}` - project first, then global; print `<url>aio/<name>/` or
`<url>aio/ccvi/<name>/`, with `url` from the sentinel, else from the live registry as in
**URLs** above. If neither gives a port, print the path and say the port is unknown here. A
port lasts only for the window's lifetime, so say the URL is tied to this window.

### `html archive`

`/aio html archive {name}` - `mv` the WINNING entry (project first, then global)
`<scope>/html/<name>/` to `<scope>/html/archive/<name>/` (creating `archive/`). Never delete.
Refuse when the destination already exists (never clobber; say what is there). If the move
exposes a global entry of the same name, say so. Echo the new path.

### `html toast`

`/aio html toast {name} [scope]` - display an entry as a macOS toast, through the **toast
script** named on the sentinel's `toast:` line. Writing the page is `html write`; this verb
only displays it.

1. **No `toast:` line in the sentinel: say toasts are unavailable on this host and stop.**
   Never guess the script's path.
2. Run the script with the CCVI node, from the project root (the script finds the calling
   window by the cwd's git checkout):

   ```bash
   ~/.ccvi/node/current/bin/node <toast path> list               # pages that describe themselves as toasts
   ~/.ccvi/node/current/bin/node <toast path> describe {name}    # when to use it, and its data fields
   ```

   Run `describe` before the first `display` of a page this session. Do not memorize or paste
   the catalog; `list` is the catalog. The two built-in examples are `options` (ask the user
   to pick one of several choices) and `turn_end` (tell the user a long task finished).
3. Display it, with the data as one JSON object. Prefer `--data-stdin` with a quoted heredoc,
   so quotes in the text need no escaping:

   ```bash
   ~/.ccvi/node/current/bin/node <toast path> display {name} [--scope project|global] [--id ID] \
     [--theme NAME] [--timeout-ms N] [--dir auto|ltr|rtl] --data-stdin <<'JSON'
   { "title": "Build finished", "body": "projectx 0.4.203 is packaged." }
   JSON
   ```

   Pass `[scope]` as `--scope`. `--id` names the instance so a later `dismiss <id>` can take
   it down; otherwise the script prints the id it chose.
4. Relay the result by exit code:

   ```text
   0  displayed (the script prints the id)
   2  bad request: unknown page, missing field, or bad argument. The output lists the
      page's fields; it IS the field reference. Fix the data and retry once.
   3  no live CCVI window to serve the toast
   4  toast host not installed
   ```

`~/.ccvi/node/current/bin/node <toast path> dismiss <id>` takes a displayed toast down.

**Use toasts sparingly.** A toast interrupts the user in whatever app they are in. Follow the
page's `useWhen` (`turn_end` is for long tasks, never routine turn ends). The toast's buttons
send only when clicked.

**Themes.** A theme is one CSS file, `<scope>/html/themes/<name>.css`, loaded after the page's
own styles. `--theme NAME` picks one per display, and a `toastTheme` key in the shared store
sets the default. A project page may use a project or a global theme; a global page uses
global themes only.

---

## Help output

When the user runs `/aio` with no arguments, or a bare noun (or asks what it can do), reply
with exactly this - no preamble, no postscript:

```text
/aio · v0.0.41 - the aio workspace: #commands and served html, project scope wins over global:
• hashcmd write {name} [scope]   - author or overwrite <scope>/hash_cmds/<name>.md (scope: project | global; project names get the prefix)
• hashcmd list [scope]           - what resolves now, collisions marked, with the winner
• hashcmd show {name}            - the file that would win for #name, and its path
• hashcmd move {name} {scope}    - promote to global or demote to project; never clobbers
• hashcmd archive {name}         - move the winning definition to hash_cmds/archive/; never deletes
• html write {name} [scope]      - scaffold html/<name>/index.html + data/ (scope: project | global)
• html list [scope]              - the entries that exist, with labels and URLs
• html url {name}                - the URL of an entry: /aio/<name>/ or /aio/ccvi/<name>/
• html archive {name}            - move html/<name>/ to html/archive/<name>/; never deletes
• html toast {name} [scope]      - display an entry as a macOS toast via the sentinel's toast: script (list, describe, display)

Running a command is just typing it: #name payload. Agent -> page: write data/*.json.
Page -> agent: CCVI.send('#command payload'), an ordinary turn. Paths come from the <ccvi-aio> sentinel.
```

## What this skill does not do

- **It never runs a command.** Typing `#name` does that; the sidecar expands it.
- **It never deletes.** Both `archive` verbs move.
- **It never edits `lib/` or anything beside `hash_cmds/` and `html/`** in the aio. Those are
  the commands' own files.
- **It never writes outside the two aio scopes.**
- **It never sends from a toast on its own.** A toast's send is the user's click.
- **No build step, no CDN, no off-box serving.** Html is files the sidecar serves as they are,
  loopback only; this is not Promptdown.
