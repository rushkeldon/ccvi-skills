---
name: pages
description: write•list•url - scaffold, list, and locate agent-authored web pages the CCVI sidecar serves from the aio workspace over each window's loopback port, with live JSON data push and page controls that send #commands back as ordinary turns, via /pages [verb]. Use when the user or an agent wants a dashboard, a status page, or any served page for this project or for every project.
argument-hint: "[verb] {name} [scope]"
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(ls:*), Bash(mkdir:*), Bash(cat:*)
# Machine-readable verb schema (host-facing). The prose below remains authoritative
# for the model; this block MIRRORS it for a host that renders a verb menu and
# generates each verb's dialog from `params`. Every fact here MUST also be stated in
# the prose - the skill stays fully usable in vanilla Claude Code.
verbs:
  write: { order: 1, params: [ { name: name,  type: string, required: true },
                               { name: scope, type: string, required: false, default: project } ] }
  list:  { order: 2, params: [ { name: scope, type: string, required: false } ] }
  url:   { order: 3, params: [ { name: name,  type: string, required: true } ] }
---

# pages

The CCVI sidecar serves **pages** from the aio workspace over the same loopback port each
window already binds. A page is plain HTML plus ES-module or classic script, with no build
step and nothing loaded from a CDN. It includes the sidecar's runtime, `/ccvi.js`, which
connects back to the window that served it and gives the page three things: live JSON data
pushed from `data/*.json`, the window's idle/working status, and `CCVI.send(text)`, which
submits an ordinary user turn, so a button can emit a `#command`.

Agent to page is **files**: the agent writes `pages/<name>/data/*.json` with its normal Write
tool and every connected page re-renders. Page to agent is **a user turn**: a click is a human
action, the same as typing. The contract is ccvi-idea's `doc/contracts/aio.md`.

## Where pages live and how they are reached

```text
~/.ccvi/aio/pages/<name>/                                 global - served by EVERY window at /g/<name>/
~/.ccvi/projects/<encodedProjectPath>/aio/pages/<name>/   project - served by THIS window at /pages/<name>/
  index.html
  data/*.json
```

Resolve both paths from the `<ccvi-aio>` sentinel in the turn context (highest `epoch`,
verbatim block only). Without a sentinel, the global scope is `~/.ccvi/aio` and the project
scope is unknown: say so and ask rather than guess.

The base URL is in the capability blurb: `Pages are served at http://127.0.0.1:<port>/`. Every
window serves `/` (the hub, listing all live windows) and `/p/<project>`, which redirects to
that project's window, so a bookmark to any live port reaches any project.

## Invocation

Single entry point - **`/pages [verb] [args]`**:

| Form | Effect |
|---|---|
| `/pages write {name} [scope]` | Scaffold `pages/<name>/index.html` and `data/` at `scope` (`project` default, or `global`) |
| `/pages list [scope]` | The pages that exist, with their URLs |
| `/pages url {name}` | Print the URL of a page (project first, then global) |
| `/pages` (no args) | Print the help cheat-sheet (see **Help output**) |

`name` is `[A-Za-z0-9][A-Za-z0-9_-]*`; it is the directory and the URL segment.

## Verb: write

`/pages write {name} [scope]`

1. Resolve the scope dir from the sentinel. Refuse to overwrite an existing `index.html`
   unless the user asked to rewrite that page.
2. Create `pages/<name>/data/` and write `index.html` from the template below, substituting
   `NAME` and `SCOPE`. Adapt the body to what the user wants the page to show; keep the
   runtime include and the data wiring.
3. If the page has controls, write `data/actions.json` (see **Actions**) and the hash commands
   those actions emit (`/hashcmd write ...`), using the project prefix.
4. Echo the absolute dir and the URL (`/pages url {name}`).

### Template

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NAME</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0; padding: 24px 16px; font: 15px/1.45 system-ui, sans-serif; }
  .status { opacity: .6; font-size: 13px; }
  button { font: inherit; padding: 6px 12px; border-radius: 8px; }
</style>
</head>
<body>
<h1>NAME <span class="status" id="status"></span></h1>
<div id="root">loading...</div>
<script src="/ccvi.js" data-page="NAME" data-scope="SCOPE"></script>
<script>
  var actions = [];
  CCVI.onStatus(function (s) { document.getElementById('status').textContent = s; });
  CCVI.onData('actions.json', function (json) { actions = (json && json.actions) || []; });
  CCVI.onData('NAME.json', function (json, error) {
    var root = document.getElementById('root');
    if (error) { root.textContent = 'data error: ' + error; return; }
    root.innerHTML = '';
    (json.rows || []).forEach(function (row) {
      var div = document.createElement('div');
      div.textContent = row.title || JSON.stringify(row);
      actions.forEach(function (a) {
        var b = document.createElement('button');
        b.textContent = a.label;
        b.onclick = function () { CCVI.send(fill(a.prompt, row)); };
        div.appendChild(b);
      });
      root.appendChild(div);
    });
  });
  function fill(tpl, row) { return tpl.replace(/\{(\w+)\}/g, function (_, k) { return row[k] == null ? '' : String(row[k]); }); }
</script>
</body>
</html>
```

The data file the template reads is `data/NAME.json`, shaped `{ "rows": [ { "title": ..., ... } ] }`.
Change the shape freely; the only fixed parts are the runtime include and `CCVI.onData`.

### Actions

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
commands with the project prefix and author them with `/hashcmd write`.

### The runtime API (`/ccvi.js`)

```text
CCVI.page, CCVI.scope          from the script tag's data-page / data-scope, else the URL
CCVI.send(text)                submit a user turn in the serving window (hash expansion applies)
CCVI.onData(file, fn)          fn(json, error, frame) for data/<file> on attach and on change ('*' for all)
CCVI.onStatus(fn)              fn('idle' | 'working')
CCVI.directory(fn)             fn(directoryState | directoryAdd | directoryRemove) - every live window
```

The runtime reconnects with backoff and queues sends while disconnected.

## Verb: list

`/pages list [scope]` - glob `pages/*/index.html` in both scopes (or the one given) and print
name, scope, and URL. Nothing is written.

## Verb: url

`/pages url {name}` - project first, then global; print `http://127.0.0.1:<port>/pages/<name>/`
or `/g/<name>/`, with the port from the capability blurb. Without a port in the blurb, print
the path and say the port is unknown here.

## Help output

When the user runs `/pages` with no arguments (or asks what it can do), reply with exactly
this - no preamble, no postscript:

```text
/pages · v0.0.29 - agent-authored pages served from the aio workspace on this window's loopback port:
• write {name} [scope]   - scaffold pages/<name>/index.html + data/ (scope: project | global)
• list [scope]           - the pages that exist, with URLs
• url {name}             - the URL of a page (project first, then global)

Agent -> page: write data/*.json. Page -> agent: CCVI.send('#command payload'), an ordinary turn.
```

## What this skill does not do

- **No build step, no CDN.** Pages are files the sidecar serves as they are.
- **No off-box serving.** Pages are loopback only; this is not Promptdown.
- **It never deletes a page.** Move it aside by hand if it must go.
