#!/usr/bin/env python3
"""
autoprompt.py - the fast path for the /autoprompt skill.

Writes a CCVI auto-prompt dead drop into ANOTHER project's per-worktree git dir and, unless
told not to, opens that project in the right IDE so the CCVI sidecar there consumes the drop
as its next turn. The consumer side is ccvi-idea's (doc/contracts/auto_prompt.md); this
script is a writer only.

Contract:
  autoprompt.py send   <projectDir> [--no-ide] (--prompt-arg-stdin | --prompt-stdin)
  autoprompt.py show   [<projectDir>]
  autoprompt.py clear  <projectDir>
  autoprompt.py config [<key> [<value>]]

  stdin   = for send: the prompt. --prompt-arg-stdin means "the user's raw prompt argument"
            (classified here as literal text or a .md path); --prompt-stdin means
            agent-authored text, always literal.
  stdout  = the user-facing report, relayed verbatim by the skill.
  exit    = 0 success; 1 refusal (stdout line starts "refused:"); 2 usage error.

Env (tests and the live smoke):
  AUTOPROMPT_NO_LAUNCH=1      print the `open -a` command instead of running it
  AUTOPROMPT_FLOORS_JSON=...  replace FLOORS wholesale (JSON of the same shape)

Everything home-relative goes through Path.home(), so a test can fake the whole machine by
setting HOME.
"""

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import sys
import time
from datetime import datetime
from pathlib import Path

# editorId -> minimum installed CCVI version for each capability, or None = unsupported.
# "single": consumes <gitDir>/ccvi/auto_prompt.md. "numbered": also drains auto_prompt_<N>.md.
# "directives": reads the `.prompt.md` spelling (auto.prompt.md, auto_<N>.prompt.md) AND
#   executes a frontmatter directive envelope (ccvi-idea doc/contracts/prompt_file.md).
#
# - ccvi-idea 0.4.187 is the first build with both (prompt_file_type_frontmatter_directives
#   plan, 2026-11-04). Below it the consumer would send a frontmatter block to the model as
#   plain text, and would never see a new-spelling name at all, so a directive drop to an
#   older install is REFUSED and a plain drop keeps the legacy name.
#
# Probed 2026-11-01 (gate-consumers), re-probed 2026-11-02:
# - ccvi-idea 0.4.168 is the first build reading <gitDir>/ccvi/ (0.4.167 read <repoRoot>/).
# - ccvi-idea 0.4.169 (08390bd) is the first build draining numbered slots; its contract
#   documents them. Below it the consumer stats only the bare name, so a numbered drop would
#   strand silently - hence a hard >= floor, never best-effort. Re-probed 2026-11-02 after
#   install: IntelliJIdea2026.2 and AndroidStudio2026.1.4 both carry ccvi-idea-0.4.169.jar.
# - ccvi-vscode has no consumer of its own; it compiles ccvi-idea's sidecar in at build time.
#   `grep -rlF 'auto_prompt(?:_'` and `grep -rlF 'auto_prompt.md'` over out/ and dist/ of
#   ~/.vscode/extensions/appcloud9.ccvi-vscode-{1.2.32,1.2.33} and
#   ~/.cursor/extensions/appcloud9.ccvi-vscode-{1.2.3,1.2.31}: zero matches. Unsupported.
FLOORS = {
    "as":     {"single": "0.4.168", "numbered": "0.4.169", "directives": "0.4.187"},
    "idea":   {"single": "0.4.168", "numbered": "0.4.169", "directives": "0.4.187"},
    "vscode": {"single": None,      "numbered": None,      "directives": None},
    "cursor": {"single": None,      "numbered": None,      "directives": None},
}

APP = {
    "as": "Android Studio",
    "idea": "IntelliJ IDEA",
    "vscode": "Visual Studio Code",
    "cursor": "Cursor",
}

CONFIG_KEYS = ("workingDir", "idePreferred")
IDE_PREFERRED_VALUES = ("idea", "vscode", "cursor")
IDE_PREFERRED_DEFAULT = "idea"

# The consumer's slot regexes, verbatim from the contract: the `.prompt.md` spelling, and the
# legacy spelling it still reads during the dual-spelling window. The `\.md$` anchors keep the
# consumer's in-flight `*.md.claimed-<pid>` names out. Both count when finding the next free
# slot, because the consumer interleaves them by slot number.
SLOT_RE = re.compile(r"^auto(?:_([1-9][0-9]*))?\.prompt\.md$")
LEGACY_SLOT_RE = re.compile(r"^auto_prompt(?:_([1-9][0-9]*))?\.md$")

# A leading frontmatter fence: the prompt carries a directive envelope. Detection only - the
# consumer parses it; this script needs no YAML dependency to know an envelope is present.
ENVELOPE_RE = re.compile(r"^\ufeff?---[ \t]*\r?\n(?:[\s\S]*?\r?\n)?---[ \t]*(?:\r?\n|$)")
SLOT_ATTEMPTS = 10

# agent_state heartbeat is ~15 s; the contract's dispatch rule is "fresh = < 60 s".
FRESH_MS = 60_000

BOOL_TRUE = {"true", "1", "yes"}
BOOL_FALSE = {"false", "0", "no"}


class Refusal(Exception):
    pass


# --------------------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------------------

def config_path():
    return Path.home() / ".ccvi" / "autoprompt.json"


def read_config():
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(data):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(".autoprompt.%d.tmp" % os.getpid())
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def git(args, cwd=None):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def default_working_dir():
    top = git(["rev-parse", "--show-toplevel"])
    return str(Path(top).parent) if top else None


def working_dir():
    wd = read_config().get("workingDir")
    return wd or default_working_dir()


def ide_preferred():
    v = read_config().get("idePreferred")
    return v if v in IDE_PREFERRED_VALUES else IDE_PREFERRED_DEFAULT


def cmd_config(key, value):
    cfg = read_config()
    if key is None:
        lines = []
        for k in CONFIG_KEYS:
            if k in cfg:
                lines.append("%s = %s" % (k, cfg[k]))
            else:
                d = default_working_dir() if k == "workingDir" else IDE_PREFERRED_DEFAULT
                lines.append("%s = %s (default)" % (k, d if d else "unset"))
        return "\n".join(lines)
    if key not in CONFIG_KEYS:
        raise Refusal("unknown config key %r - valid keys: %s" % (key, ", ".join(CONFIG_KEYS)))
    if value is None:
        if key in cfg:
            return "%s = %s" % (key, cfg[key])
        d = default_working_dir() if key == "workingDir" else IDE_PREFERRED_DEFAULT
        return "%s = %s (default)" % (key, d if d else "unset")
    if key == "workingDir":
        p = Path(os.path.expanduser(value))
        if not p.is_absolute():
            p = Path.cwd() / p
        if not p.is_dir():
            raise Refusal("workingDir %s is not an existing directory" % p)
        value = os.path.realpath(p)
    elif key == "idePreferred":
        if value not in IDE_PREFERRED_VALUES:
            raise Refusal("idePreferred must be one of %s (Android projects always open in "
                          "Android Studio, so 'as' is not a preference)"
                          % ", ".join(IDE_PREFERRED_VALUES))
    cfg[key] = value
    write_config(cfg)
    return "%s = %s" % (key, value)


# --------------------------------------------------------------------------------------
# project resolution
# --------------------------------------------------------------------------------------

def resolve_project(raw):
    """-> (projectDir, gitDir) as realpath strings, or Refusal."""
    is_bare = "/" not in raw and not raw.startswith("~")
    if is_bare:
        if ".." in raw:
            raise Refusal("project name %r may not contain '..'" % raw)
        wd = working_dir()
        if not wd:
            raise Refusal("no workingDir to resolve %r against - pass an absolute path "
                          "instead, or set it: /autoprompt config workingDir <dir>" % raw)
        candidate = Path(wd) / raw
    else:
        candidate = Path(os.path.expanduser(raw))
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
    project_dir = os.path.realpath(candidate)
    if not os.path.isdir(project_dir):
        raise Refusal("no such directory: %s" % project_dir)
    git_dir = git(["-C", project_dir, "rev-parse", "--absolute-git-dir"])
    if not git_dir:
        raise Refusal("%s is not a git checkout - auto-prompt drops live in the git dir"
                      % project_dir)
    if is_bare:
        root = os.path.realpath(working_dir())
        if os.path.commonpath([root, project_dir]) != root:
            raise Refusal("%s resolves outside workingDir %s" % (project_dir, root))
    return project_dir, os.path.realpath(git_dir)


def repo_root(project_dir):
    common = git(["-C", project_dir, "rev-parse", "--path-format=absolute", "--git-common-dir"])
    return os.path.realpath(Path(common).parent) if common else project_dir


# --------------------------------------------------------------------------------------
# prompt intake
# --------------------------------------------------------------------------------------

def looks_like_path(s):
    # A path argument is ONE token: "fix the typo in doc/x.md" is a sentence, not a path.
    return (not any(c.isspace() for c in s) and s.endswith(".md")
            and ("/" in s or s.startswith("~")))


def read_prompt(mode, stdin_text):
    raw = stdin_text.strip()
    if mode == "arg" and looks_like_path(raw):
        p = Path(os.path.expanduser(raw))
        if not p.is_absolute():
            p = Path.cwd() / p
        if not p.is_file():
            raise Refusal("no such file: %s" % p)
        raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        raise Refusal("the prompt is empty - nothing to send")
    return raw


# --------------------------------------------------------------------------------------
# windows, IDE choice, installed consumer
# --------------------------------------------------------------------------------------

def agent_state_records():
    d = Path.home() / ".ccvi" / "agent_state"
    out = []
    try:
        files = sorted(d.glob("*.json"))
    except OSError:
        return out
    for f in files:
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(rec, dict) and rec.get("version") == 1:
            out.append(rec)
    return out


def now_ms():
    return int(time.time() * 1000)


def is_fresh(rec):
    try:
        return now_ms() - int(rec.get("updatedAtMs", 0)) < FRESH_MS
    except (TypeError, ValueError):
        return False


def rp(p):
    return os.path.realpath(p) if p else None


# A window is OPEN only if its sidecar answers GET /whoami on a loopback port right now.
# ccvi-idea doc/contracts/aio.md, "Window identity". Every CCVI window binds the first free port
# in 17390..17453 (DEFAULT_REMOTE_PORT + PORT_SCAN_SPAN in remote_ws_server.ts), so one parallel
# sweep of that range is the full set of live windows. No file is trusted for existence: the
# MicBoom miss on 2026-11-05 was a closed window whose agent_state record a dying sidecar had
# just rewritten as a fresh 'idle', which a freshness test cannot tell from a live one.
# HAND-MIRRORED: ~/.ccvi/aio/hash_cmds/lib/agent_slots.py sweeps the same way; change both.
PORT_FIRST = 17390
PORT_SPAN = 64
PROBE_TIMEOUT_S = 0.4


def probe_ports():
    """The ports to sweep. AUTOPROMPT_PORTS overrides it for tests: 'none', or comma-separated
    ports and FIRST-LAST ranges."""
    spec = os.environ.get("AUTOPROMPT_PORTS")
    if spec is None:
        return list(range(PORT_FIRST, PORT_FIRST + PORT_SPAN))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part or part == "none":
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def whoami(port):
    """-> ("ccvi", identity) | ("legacy", None) for a server with no /whoami | (None, None)."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/whoami" % port,
                                    timeout=PROBE_TIMEOUT_S) as r:
            body = json.loads(r.read().decode("utf-8"))
        if isinstance(body, dict) and body.get("product") == "ccvi" and body.get("v") == 1:
            return "ccvi", body
        return None, None
    except urllib.error.HTTPError as e:
        # A server is listening in CCVI's range but has no /whoami: a CCVI build older than the
        # endpoint. Only then is the agent_state fallback allowed (see live_windows).
        return ("legacy", None) if e.code == 404 else (None, None)
    except (OSError, ValueError):
        return None, None


def sweep():
    """-> (identities, any_legacy)."""
    ports = probe_ports()
    if not ports:
        return [], False
    with ThreadPoolExecutor(max_workers=min(64, len(ports))) as ex:
        results = list(ex.map(whoami, ports))
    ids = [ident for kind, ident in results if kind == "ccvi"]
    return ids, any(kind == "legacy" for kind, _ in results)


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except PermissionError:
        return True
    except (OSError, TypeError, ValueError):
        return False


def window_record(ident, records_by_session):
    """A proven-live window, in the record shape the rest of this script reads. agent_state
    contributes the STATE only (idle / mid-turn / human-driven), never the existence."""
    rec = records_by_session.get(ident.get("sessionId")) or {}
    state = rec.get("state") or ("idle" if ident.get("idle") else "mid-turn")
    return {"editorId": ident.get("editorId", "unknown"), "cwd": ident.get("workspaceRoot"),
            "gitDir": ident.get("gitDir"), "pid": ident.get("pid"),
            "sessionId": ident.get("sessionId"), "state": state,
            "updatedAtMs": rec.get("updatedAtMs", now_ms())}


def live_windows(project_dir):
    """-> (exact, siblings, stale). exact and siblings are windows PROVEN live by a /whoami
    answer; stale is agent_state history for this project that no live window owns."""
    root = repo_root(project_dir)
    target_git = rp(git(["-C", project_dir, "rev-parse", "--absolute-git-dir"]))
    records = agent_state_records()
    by_session = {r.get("sessionId"): r for r in records if r.get("sessionId")}
    ids, any_legacy = sweep()
    windows = [window_record(i, by_session) for i in ids]
    live_pids = {w["pid"] for w in windows}
    if any_legacy:
        # Fallback for builds older than /whoami ONLY: a fresh record whose process is running.
        for r in records:
            if r.get("pid") not in live_pids and is_fresh(r) and pid_alive(r.get("pid")):
                windows.append(dict(r, gitDir=None))
                live_pids.add(r.get("pid"))
    exact, siblings = [], []
    for w in windows:
        cwd = rp(w.get("cwd"))
        same = (rp(w["gitDir"]) == target_git) if w.get("gitDir") else (cwd == project_dir)
        if same:
            exact.append(w)
        elif cwd and repo_root(cwd) == root:
            siblings.append(w)
    owned = {w.get("sessionId") for w in exact}
    stale = [r for r in records if rp(r.get("cwd")) == project_dir
             and r.get("sessionId") not in owned]
    key = lambda r: -int(r.get("updatedAtMs", 0))
    return sorted(exact, key=key), sorted(siblings, key=key), sorted(stale, key=key)


ANDROID_GRADLE_FILES = ("build.gradle", "build.gradle.kts", "settings.gradle",
                        "settings.gradle.kts", "app/build.gradle", "app/build.gradle.kts")
ANDROID_MARKERS = ("com.android.application", "com.android.library",
                   "com.android.tools.build:gradle")


def has_android_marker(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(m in text for m in ANDROID_MARKERS)


def is_android(project_dir):
    d = Path(project_dir)
    # Fast path only, never the evidence: local.properties is gitignored and exists only once
    # Android Studio has opened the checkout, so a fresh clone or worktree lacks it.
    try:
        for line in (d / "local.properties").read_text(encoding="utf-8").splitlines():
            if line.startswith("sdk.dir="):
                return True
    except OSError:
        pass
    if (d / "app" / "src" / "main" / "AndroidManifest.xml").is_file():
        return True
    if any(has_android_marker(d / name) for name in ANDROID_GRADLE_FILES):
        return True
    # android-dmgz (2026-11-01) carries its markers only at depth 3-4: the tracked
    # buildLogic/gradle/buildLibs.versions.toml and libraries/flex/*/build.gradle.kts. Its
    # top-level build.gradle and settings.gradle match nothing.
    return scan_android_markers(d, ANDROID_SCAN_DEPTH)


ANDROID_SCAN_DEPTH = 4
ANDROID_SCAN_SKIP = {"build", ".gradle", ".git", ".idea", "node_modules"}
ANDROID_SCAN_SUFFIXES = (".gradle", ".gradle.kts", ".versions.toml")


def scan_android_markers(d, depth):
    try:
        entries = list(os.scandir(d))
    except OSError:
        return False
    subdirs = []
    for e in entries:
        if e.is_dir(follow_symlinks=False):
            if e.name not in ANDROID_SCAN_SKIP:
                subdirs.append(e.path)
        elif e.name.endswith(ANDROID_SCAN_SUFFIXES) and has_android_marker(Path(e.path)):
            return True
    if depth <= 1:
        return False
    return any(scan_android_markers(s, depth - 1) for s in subdirs)


def choose_ide(project_dir, exact):
    """-> (editorId, reason)."""
    if exact:
        return exact[0].get("editorId", "unknown"), "live window"
    if is_android(project_dir):
        return "as", "android project"
    return ide_preferred(), "preference"


def vtuple(s):
    try:
        return tuple(int(x) for x in s.split("."))
    except (AttributeError, ValueError):
        return ()


JAR_RE = re.compile(r"^ccvi-idea-(\d+(?:\.\d+)*)\.jar$")
PRODUCT_VER_RE = re.compile(r"(\d+(?:\.\d+)*)$")
EXT_RE = re.compile(r"^appcloud9\.ccvi-vscode-(\d+(?:\.\d+)*)$")


def plugin_jar_version(config_dir):
    lib = config_dir / "plugins" / "ccvi-idea" / "lib"
    try:
        vers = [JAR_RE.match(f.name).group(1) for f in lib.iterdir() if JAR_RE.match(f.name)]
    except OSError:
        return None
    return max(vers, key=vtuple) if vers else None


def launched_data_dir(app):
    """The config dir name the app at /Applications/<app>.app actually uses.

    Probed 2026-11-01: Android Studio.app -> "AndroidStudio2026.1.4", IntelliJ IDEA.app ->
    "IntelliJIdea2026.2". The older AndroidStudio2026.1.1 config dir still holds
    ccvi-idea-0.4.42.jar, which predates the dead drop, so guessing by "newest dir" can
    report a capability the running IDE does not have.
    """
    # ~/Applications first: Toolbox installs land there, and it keeps tests hermetic.
    for apps in (Path.home() / "Applications", Path("/Applications")):
        info = apps / ("%s.app" % app) / "Contents" / "Resources" / "product-info.json"
        try:
            name = json.loads(info.read_text(encoding="utf-8")).get("dataDirectoryName")
        except (OSError, ValueError):
            continue
        if name:
            return name
    return None


def jetbrains_version(base, prefix, app):
    named = launched_data_dir(app)
    if named:
        return plugin_jar_version(base / named)
    # Fallback when product-info.json is unreadable: the newest config dir carrying the jar.
    try:
        dirs = [d for d in base.iterdir() if d.is_dir() and d.name.startswith(prefix)]
    except OSError:
        return None
    def product_key(d):
        m = PRODUCT_VER_RE.search(d.name)
        return vtuple(m.group(1)) if m else ()
    for d in sorted(dirs, key=product_key, reverse=True):
        ver = plugin_jar_version(d)
        if ver:
            return ver
    return None


def extension_version(base):
    try:
        vers = [EXT_RE.match(d.name).group(1) for d in base.iterdir() if EXT_RE.match(d.name)]
    except OSError:
        return None
    return max(vers, key=vtuple) if vers else None


def installed_version(editor_id):
    home = Path.home()
    support = home / "Library" / "Application Support"
    if editor_id == "as":
        return jetbrains_version(support / "Google", "AndroidStudio", APP["as"])
    if editor_id == "idea":
        return jetbrains_version(support / "JetBrains", "IntelliJIdea", APP["idea"])
    if editor_id == "vscode":
        return extension_version(home / ".vscode" / "extensions")
    if editor_id == "cursor":
        return extension_version(home / ".cursor" / "extensions")
    return None


def floors():
    override = os.environ.get("AUTOPROMPT_FLOORS_JSON")
    if override:
        return json.loads(override)
    return FLOORS


def has_envelope(text):
    return bool(ENVELOPE_RE.match(text))


def capability(editor_id):
    """-> ("directives" | "numbered" | "single" | "none", installedVersion)."""
    ver = installed_version(editor_id)
    f = floors().get(editor_id, {})
    if ver:
        if f.get("directives") and vtuple(ver) >= vtuple(f["directives"]):
            return "directives", ver
        if f.get("numbered") and vtuple(ver) >= vtuple(f["numbered"]):
            return "numbered", ver
        if f.get("single") and vtuple(ver) >= vtuple(f["single"]):
            return "single", ver
    return "none", ver


def launch_ide(editor_id, project_dir):
    """-> a report fragment."""
    app = APP.get(editor_id)
    if not app:
        return "no app known for editorId %r - not launched" % editor_id
    if os.environ.get("AUTOPROMPT_NO_LAUNCH") == "1":
        return 'would run: open -a "%s" "%s"' % (app, project_dir)
    if sys.platform != "darwin":
        return "launch unsupported on %s - not launched" % sys.platform
    r = subprocess.run(["open", "-a", app, project_dir], capture_output=True, text=True)
    if r.returncode != 0:
        return "launch failed: %s" % (r.stderr.strip() or "open exited %d" % r.returncode)
    return "launched"


# --------------------------------------------------------------------------------------
# the drop
# --------------------------------------------------------------------------------------

def slots(ccvi_dir):
    try:
        names = os.listdir(ccvi_dir)
    except OSError:
        return []
    out = []
    for n in names:
        m = SLOT_RE.match(n) or LEGACY_SLOT_RE.match(n)
        if m:
            out.append((int(m.group(1) or 0), n))
    return sorted(out)


def slot_name(n, cap):
    """The filename for slot n: the new spelling only where the consumer reads it."""
    if cap == "directives":
        return "auto.prompt.md" if n == 0 else "auto_%d.prompt.md" % n
    return "auto_prompt.md" if n == 0 else "auto_prompt_%d.md" % n


def write_drop(git_dir, text, cap):
    ccvi_dir = Path(git_dir) / "ccvi"
    # Mandatory: a repo that has never had a CCVI window has no ccvi/ dir, and the consumer's
    # claim rename would ENOENT.
    ccvi_dir.mkdir(parents=True, exist_ok=True)
    tmp = ccvi_dir / (".auto.%d.%s.tmp" % (os.getpid(), secrets.token_hex(4)))
    tmp.write_text(text.rstrip() + "\n", encoding="utf-8")
    try:
        for _ in range(SLOT_ATTEMPTS):
            present = slots(ccvi_dir)
            if not present:
                dest = ccvi_dir / slot_name(0, cap)
            elif cap in ("numbered", "directives"):
                dest = ccvi_dir / slot_name(present[-1][0] + 1, cap)
            else:
                raise Refusal("a drop is already waiting at %s; this CCVI version holds one at "
                              "a time" % (ccvi_dir / present[0][1]))
            try:
                # No-replace create: fails with FileExistsError and never overwrites, where a
                # rename would silently replace a racing writer's drop.
                os.link(tmp, dest)
                return dest
            except FileExistsError:
                continue
        raise Refusal("could not claim a slot in %s after %d attempts" % (ccvi_dir, SLOT_ATTEMPTS))
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def state_of(rec):
    return rec.get("state", "unknown")


def window_line(rec):
    eid = rec.get("editorId", "unknown")
    return "%s (state %s)" % (APP.get(eid, eid), state_of(rec))


def cmd_send(raw_project, should_start_ide, prompt_mode, stdin_text):
    project_dir, git_dir = resolve_project(raw_project)
    text = read_prompt(prompt_mode, stdin_text)
    exact, siblings, _stale = live_windows(project_dir)
    editor_id, reason = choose_ide(project_dir, exact)
    cap, ver = capability(editor_id)
    if cap == "none":
        app = APP.get(editor_id, editor_id)
        found = "CCVI for %s at %s can't consume auto-prompt drops" % (app, ver or "not installed")
        # The remedy must fit the branch: idePreferred is consulted only at the last rung.
        if reason == "live window":
            fix = ("close that window and reopen the project in IntelliJ IDEA, or update "
                   "CCVI in %s" % app)
        elif reason == "android project":
            fix = "update CCVI in Android Studio"
        else:
            fix = "update CCVI in %s, or /autoprompt config idePreferred idea" % app
        raise Refusal("%s; %s" % (found, fix))
    if has_envelope(text) and cap != "directives":
        # Below the floor the consumer would send the frontmatter to the model as plain text and
        # run none of it - the worst kind of partial success. Refuse, naming both versions.
        app = APP.get(editor_id, editor_id)
        floor = floors().get(editor_id, {}).get("directives")
        need = ("needs %s or newer" % floor) if floor else "no version of it supports them"
        raise Refusal("CCVI for %s at %s can't execute prompt-file directives (%s); update CCVI "
                      "in %s, or send the prompt without its frontmatter block"
                      % (app, ver or "not installed", need, app))
    dest = write_drop(git_dir, text, cap)
    present = slots(dest.parent)
    slot_no = next((i for i, n in present if n == dest.name), 0)
    app = APP.get(editor_id, editor_id)
    lines = ["autoprompt -> %s" % project_dir,
             "drop: %s (slot %d, %d waiting)" % (dest, slot_no, len(present))]
    if exact:
        lines.append("window: live in %s" % window_line(exact[0]))
        lines.append("ide: %s (%s) - already open" % (app, reason))
    else:
        lines.append("window: none open")
        if should_start_ide:
            lines.append("ide: %s (%s) - %s" % (app, reason, launch_ide(editor_id, project_dir)))
        else:
            lines.append("ide: %s (%s) - not launched (--no-ide)" % (app, reason))
    if siblings and not exact:
        lines.append("note: other worktrees of this repo are open: " + ", ".join(
            "%s (%s)" % (r.get("cwd"), r.get("editorId", "unknown")) for r in siblings))
    if len(exact) > 1:
        lines.append("note: %d windows share this worktree; either may take the drop" % len(exact))
    return "\n".join(lines)


def age(rec):
    secs = max(0, (now_ms() - int(rec.get("updatedAtMs", 0))) // 1000)
    if secs < 120:
        return "%ds" % secs
    if secs < 7200:
        return "%dm" % (secs // 60)
    return "%dh" % (secs // 3600)


def cmd_show(raw_project):
    if raw_project is None:
        return cmd_config(None, None)
    project_dir, git_dir = resolve_project(raw_project)
    exact, siblings, stale = live_windows(project_dir)
    editor_id, reason = choose_ide(project_dir, exact)
    cap, ver = capability(editor_id)
    ccvi_dir = Path(git_dir) / "ccvi"
    lines = ["project: %s" % project_dir, "git dir: %s" % git_dir]
    if exact:
        for r in exact:
            lines.append("live window: %s %s ago" % (window_line(r), age(r)))
    else:
        lines.append("live window: none")
    for r in siblings:
        lines.append("other worktree open: %s in %s" % (r.get("cwd"), window_line(r)))
    for r in stale:
        lines.append("history: %s, last seen %s ago" % (r.get("editorId", "unknown"), age(r)))
    lines.append("send would use: %s (%s)" % (APP.get(editor_id, editor_id), reason))
    lines.append("installed CCVI: %s -> capability %s" % (ver or "not installed", cap))
    present = slots(ccvi_dir)
    if not present:
        lines.append("waiting drops: none")
    for _, name in present:
        p = ccvi_dir / name
        try:
            st = p.stat()
            first = p.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        except OSError:
            continue
        stamp = datetime.fromtimestamp(st.st_mtime).astimezone().strftime("%Y-%m-%d %H:%M %Z")
        lines.append("waiting: %s (%d bytes, %s) %s" % (name, st.st_size, stamp,
                                                        first[0][:80] if first else ""))
    return "\n".join(lines)


def cmd_clear(raw_project):
    project_dir, git_dir = resolve_project(raw_project)
    ccvi_dir = Path(git_dir) / "ccvi"
    present = slots(ccvi_dir)
    if not present:
        return "nothing waiting in %s" % ccvi_dir
    # macOS Trash; elsewhere the XDG trash's files dir (ccvi-idea's trashFile ladder).
    trash = (Path.home() / ".Trash" if sys.platform == "darwin"
             else Path.home() / ".local" / "share" / "Trash" / "files")
    trash.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    lines = []
    for _, name in present:
        src = ccvi_dir / name
        dst = trash / ("auto_prompt-cleared-%s-%s" % (stamp, name))
        try:
            # The rename is the claim: the consumer may have taken it a moment ago.
            os.rename(src, dst)
        except FileNotFoundError:
            lines.append("%s: already consumed" % name)
            continue
        except OSError:
            try:
                shutil.move(str(src), str(dst))
            except FileNotFoundError:
                lines.append("%s: already consumed" % name)
                continue
        lines.append("%s -> %s" % (name, dst))
    return "\n".join(lines)


# --------------------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------------------

def main(argv):
    ap = argparse.ArgumentParser(prog="autoprompt.py")
    sub = ap.add_subparsers(dest="verb", required=True)
    s = sub.add_parser("send")
    s.add_argument("projectDir")
    s.add_argument("--no-ide", action="store_true")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt-arg-stdin", action="store_true")
    g.add_argument("--prompt-stdin", action="store_true")
    sh = sub.add_parser("show")
    sh.add_argument("projectDir", nargs="?")
    c = sub.add_parser("clear")
    c.add_argument("projectDir")
    cf = sub.add_parser("config")
    cf.add_argument("key", nargs="?")
    cf.add_argument("value", nargs="?")
    a = ap.parse_args(argv)
    try:
        if a.verb == "send":
            mode = "arg" if a.prompt_arg_stdin else "authored"
            out = cmd_send(a.projectDir, not a.no_ide, mode, sys.stdin.read())
        elif a.verb == "show":
            out = cmd_show(a.projectDir)
        elif a.verb == "clear":
            out = cmd_clear(a.projectDir)
        else:
            out = cmd_config(a.key, a.value)
    except Refusal as e:
        print("refused: %s" % e)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
