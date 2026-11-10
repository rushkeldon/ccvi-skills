#!/usr/bin/env python3
"""
Harness for plugin/skills/autoprompt/scripts/autoprompt.py.

Runs the real script as a subprocess against a throwaway HOME (config, agent_state, the
Trash, the IDE install dirs, recentProjects.xml, and the launch memory are all fakes) with
AUTOPROMPT_NO_LAUNCH=1 and AUTOPROMPT_RUNNING_APPS empty, over real git repos and worktrees
built in a temp dir. The one real-launch case puts a fake `open` first on PATH.

Run:  python3 test/test_autoprompt.py     (exit 0 = all green; exit 1 = failures)

Dev artifact - NOT shipped in any package (lives outside the skill dir).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import http.server
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(REPO, "plugin", "skills", "autoprompt", "scripts", "autoprompt.py")

NUMBERED = json.dumps({
    "as": {"single": "0.4.168", "numbered": "0.4.168"},
    "idea": {"single": "0.4.168", "numbered": "0.4.168"},
    "vscode": {"single": None, "numbered": None},
    "cursor": {"single": None, "numbered": None},
})

# A stand-in for CCVI's GET /whoami (ccvi-idea doc/contracts/aio.md). The script sweeps only
# the port AUTOPROMPT_PORTS names, so a test run never probes the developer's real windows.
# FAKE['ids'] is the list of live windows it reports; FAKE['legacy'] makes it 404, like a CCVI
# build older than the endpoint.
FAKE = {"ids": [], "legacy": False}


class _Whoami(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if FAKE["legacy"] or not FAKE["ids"]:
            self.send_response(404 if FAKE["legacy"] else 503)
            self.end_headers()
            return
        body = json.dumps(FAKE["ids"][0]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def ident(cwd, editor="idea", session="s1", idle=True):
    git_dir = subprocess.run(["git", "-C", cwd, "rev-parse", "--absolute-git-dir"],
                             capture_output=True, text=True, check=True).stdout.strip()
    return {"v": 1, "product": "ccvi", "workspaceRoot": cwd, "gitDir": os.path.realpath(git_dir),
            "editorId": editor, "pid": 99999, "sessionId": session, "idle": idle,
            "version": "0.0.0"}


_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Whoami)
threading.Thread(target=_server.serve_forever, daemon=True).start()
FAKE_PORT = _server.server_address[1]

_failures = []
_count = 0


def check(name, cond, detail=""):
    global _count
    _count += 1
    if not cond:
        _failures.append("%s  %s" % (name, detail))


def run(home, args, stdin="", env_extra=None, cwd=None):
    env = dict(os.environ, HOME=home, AUTOPROMPT_NO_LAUNCH="1")
    for k in ("AUTOPROMPT_FLOORS_JSON", "AUTOPROMPT_RECENT_PROJECTS_GLOBS"):
        env.pop(k, None)
    env["AUTOPROMPT_PORTS"] = str(FAKE_PORT)
    # Hermetic by default: no app counts as running, and ps is never called.
    env["AUTOPROMPT_RUNNING_APPS"] = ""
    if env_extra:
        env.update(env_extra)
    r = subprocess.run([sys.executable, SCRIPT] + args, input=stdin, capture_output=True,
                       text=True, env=env, cwd=cwd)
    return r.returncode, r.stdout


def git(*args, cwd=None):
    subprocess.run(["git"] + list(args), cwd=cwd, check=True, capture_output=True)


def make_repo(path, files=None):
    os.makedirs(path)
    git("init", "-q", cwd=path)
    for rel, text in (files or {}).items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i",
        cwd=path)
    return os.path.realpath(path)


def install_idea(home, version="0.4.168", product="IntelliJIdea2026.2"):
    res = os.path.join(home, "Applications", "IntelliJ IDEA.app", "Contents", "Resources")
    os.makedirs(res, exist_ok=True)
    with open(os.path.join(res, "product-info.json"), "w") as f:
        json.dump({"dataDirectoryName": product}, f)
    lib = os.path.join(home, "Library", "Application Support", "JetBrains", product,
                       "plugins", "ccvi-idea", "lib")
    os.makedirs(lib, exist_ok=True)
    open(os.path.join(lib, "ccvi-idea-%s.jar" % version), "w").close()


def install_as(home, version="0.4.168", product="AndroidStudio2026.1.4"):
    res = os.path.join(home, "Applications", "Android Studio.app", "Contents", "Resources")
    os.makedirs(res, exist_ok=True)
    with open(os.path.join(res, "product-info.json"), "w") as f:
        json.dump({"dataDirectoryName": product}, f)
    lib = os.path.join(home, "Library", "Application Support", "Google", product,
                       "plugins", "ccvi-idea", "lib")
    os.makedirs(lib, exist_ok=True)
    open(os.path.join(lib, "ccvi-idea-%s.jar" % version), "w").close()


def agent_state(home, name, cwd, repo_root, editor="idea", age_ms=0, version=1, state="idle",
                pid=1):
    d = os.path.join(home, ".ccvi", "agent_state")
    os.makedirs(d, exist_ok=True)
    rec = {"version": version, "sessionId": name, "state": state, "isIdle": True, "cwd": cwd,
           "repoRoot": repo_root, "editorId": editor, "pid": pid,
           "updatedAtMs": int(time.time() * 1000) - age_ms}
    with open(os.path.join(d, name + ".json"), "w") as f:
        json.dump(rec, f)


def recent_projects(path, entries, mtime=None):
    """Write a JetBrains recentProjects.xml. entries: [(key, opened)]."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = "".join(
        '<entry key="%s"><value><RecentProjectMetaInfo frameTitle="x" opened="%s"/></value>'
        '</entry>' % (k, "true" if o else "false") for k, o in entries)
    with open(path, "w") as f:
        f.write('<application><component name="RecentProjectsManager"><option '
                'name="additionalInfo"><map>%s</map></option></component></application>' % rows)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def launches(home, entries):
    """Seed ~/.ccvi/autoprompt_launches.json. entries: {projectDir: (editorId, age_ms)}."""
    d = os.path.join(home, ".ccvi")
    os.makedirs(d, exist_ok=True)
    now = int(time.time() * 1000)
    with open(os.path.join(d, "autoprompt_launches.json"), "w") as f:
        json.dump({k: {"editorId": e, "atMs": now - a} for k, (e, a) in entries.items()}, f)


def ide_line(out):
    return next((l for l in out.splitlines() if l.startswith("ide: ")), "")


def ccvi_dir(repo):
    out = subprocess.run(["git", "-C", repo, "rev-parse", "--absolute-git-dir"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return os.path.join(out, "ccvi")


def listing(path):
    return sorted(os.listdir(path)) if os.path.isdir(path) else []


def main():
    tmp = tempfile.mkdtemp(prefix="autoprompt_test_")
    try:
        home = os.path.join(tmp, "home")
        work = os.path.join(tmp, "work")
        os.makedirs(home)
        os.makedirs(work)
        install_idea(home)
        install_as(home)
        plain = make_repo(os.path.join(work, "plain"))
        droid_lp = make_repo(os.path.join(work, "droid_lp"),
                             {"local.properties": "sdk.dir=/x\n"})
        droid_manifest = make_repo(os.path.join(work, "droid_manifest"),
                                   {"app/src/main/AndroidManifest.xml": "<manifest/>"})
        droid_deep = make_repo(os.path.join(work, "droid_deep"), {
            "buildLogic/gradle/buildLibs.versions.toml":
                'agp = { module = "com.android.tools.build:gradle" }\n'})
        idea_only = make_repo(os.path.join(work, "idea_only"), {".idea/misc.xml": "<x/>"})
        notgit = os.path.join(work, "notgit")
        os.makedirs(notgit)

        # ---- config
        rc, out = run(home, ["config", "workingDir", work])
        check("config/set workingDir", rc == 0 and os.path.realpath(work) in out, out)
        rc, out = run(home, ["config", "idePreferred", "vscode"])
        check("config/set idePreferred", rc == 0 and "vscode" in out, out)
        rc, out = run(home, ["config", "idePreferred", "as"])
        check("config/as rejected", rc == 1 and out.startswith("refused:"), out)
        rc, out = run(home, ["config", "bogus", "x"])
        check("config/unknown key", rc == 1 and "unknown config key" in out, out)
        rc, out = run(home, ["config"])
        check("config/list", "workingDir = " in out and "idePreferred = vscode" in out, out)
        run(home, ["config", "idePreferred", "idea"])

        # ---- resolution
        rc, out = run(home, ["show", "plain"])
        check("resolve/bare name", rc == 0 and ("project: %s" % plain) in out, out)
        rc, out = run(home, ["show", ".."])
        check("resolve/.. rejected", rc == 1 and "'..'" in out, out)
        rc, out = run(home, ["show", plain])
        check("resolve/absolute", rc == 0 and ("project: %s" % plain) in out, out)
        rc, out = run(home, ["show", notgit])
        check("resolve/non-git refused", rc == 1 and "not a git checkout" in out, out)
        wt = os.path.join(work, "plain-wt")
        git("worktree", "add", "-q", wt, cwd=plain)
        wt = os.path.realpath(wt)
        rc, out = run(home, ["show", "plain-wt"])
        check("resolve/worktree git dir", rc == 0 and "/.git/worktrees/plain-wt" in out, out)

        # ---- isAndroid / chooseIde
        for name, repo in (("local.properties", droid_lp), ("manifest", droid_manifest),
                           ("deep versions.toml", droid_deep)):
            rc, out = run(home, ["show", repo])
            check("android/%s" % name, "send would use: Android Studio (android project)" in out,
                  out)
        rc, out = run(home, ["show", idea_only])
        check("android/.idea only is not android",
              "send would use: IntelliJ IDEA (preference)" in out, out)
        FAKE["ids"] = [ident(plain, editor="as")]
        rc, out = run(home, ["show", plain])
        check("choose/live window wins", "send would use: Android Studio (live window)" in out,
              out)
        FAKE["ids"] = []
        # The MicBoom regression: a FRESH record for a window that is gone. No port answers, so
        # it is history, not a window, however recent its timestamp.
        agent_state(home, "ghost", plain, plain, editor="as")
        rc, out = run(home, ["show", plain])
        check("choose/fresh record but no live port is not a window",
              "send would use: Android Studio (last used)" in out and "live window: none" in out,
              out)
        os.remove(os.path.join(home, ".ccvi", "agent_state", "ghost.json"))
        # A build older than /whoami: its port 404s, and only then is a fresh record trusted,
        # and only while its pid runs.
        FAKE["legacy"] = True
        agent_state(home, "old", plain, plain, editor="as", pid=os.getpid())
        rc, out = run(home, ["show", plain])
        check("choose/legacy build falls back to a live-pid record",
              "send would use: Android Studio (live window)" in out, out)
        agent_state(home, "old", plain, plain, editor="as", pid=2 ** 22 + 7)
        rc, out = run(home, ["show", plain])
        check("choose/legacy record with a dead pid is not a window",
              "send would use: Android Studio (last used)" in out and "live window: none" in out,
              out)
        FAKE["legacy"] = False
        os.remove(os.path.join(home, ".ccvi", "agent_state", "old.json"))
        agent_state(home, "stale", plain, plain, editor="as", age_ms=120_000)
        rc, out = run(home, ["show", plain])
        check("choose/stale is history, not a window",
              "send would use: Android Studio (last used)" in out and "live window: none" in out
              and "history: as" in out, out)
        os.remove(os.path.join(home, ".ccvi", "agent_state", "stale.json"))
        agent_state(home, "v2", plain, plain, editor="as", version=2)
        rc, out = run(home, ["show", plain])
        check("choose/version 2 skipped", "send would use: IntelliJ IDEA (preference)" in out,
              out)
        shutil.rmtree(os.path.join(home, ".ccvi", "agent_state"))
        FAKE["ids"] = [ident(wt, editor="idea")]
        rc, out = run(home, ["send", "plain", "--no-ide", "--prompt-stdin"], stdin="hi")
        check("send/sibling worktree note", rc == 0 and "other worktrees of this repo are open"
              in out and wt in out, out)
        run(home, ["clear", "plain"])
        FAKE["ids"] = []

        # ---- choose_ide rungs (2026-11-05): live window, --ide, last used, android, preference
        lu = make_repo(os.path.join(work, "lastused"))
        vs_floors = json.loads(NUMBERED)
        vs_floors["vscode"] = {"single": "1.0.0", "numbered": "1.0.0"}
        vs_env = {"AUTOPROMPT_FLOORS_JSON": json.dumps(vs_floors)}
        os.makedirs(os.path.join(home, ".vscode", "extensions", "appcloud9.ccvi-vscode-1.2.33"))
        agent_state(home, "lu-idea", lu, lu, editor="idea", age_ms=600_000)
        agent_state(home, "lu-vs", lu, lu, editor="vscode", age_ms=60_000)
        rc, out = run(home, ["send", lu, "--prompt-stdin"], stdin="hi", env_extra=vs_env)
        check("rung/last used names the newest record's editor", rc == 0
              and ide_line(out) == 'ide: Visual Studio Code (last used) - would run: open -a '
              '"Visual Studio Code" "%s"' % lu, out)
        run(home, ["clear", lu])
        rc, out = run(home, ["send", lu, "--ide", "idea", "--prompt-stdin"], stdin="hi",
                      env_extra=vs_env)
        check("rung/--ide beats last used", rc == 0
              and ide_line(out).startswith("ide: IntelliJ IDEA (--ide) - would run"), out)
        run(home, ["clear", lu])
        rc, out = run(home, ["show", lu])
        check("rung/last used skips an editor that can't take drops",
              "send would use: IntelliJ IDEA (last used)" in out, out)
        rc, out = run(home, ["send", lu, "--prompt-stdin"], stdin="hi")
        check("rung/a skipped editor is not a refusal", rc == 0
              and "(last used)" in ide_line(out), out)
        run(home, ["clear", lu])
        rc, out = run(home, ["send", lu, "--ide", "vscode", "--prompt-stdin"], stdin="hi")
        check("rung/--ide refusal names the --ide remedy", rc == 1
              and "or omit --ide" in out and listing(ccvi_dir(lu)) == [], out)
        agent_state(home, "droid-idea", droid_lp, droid_lp, editor="idea")
        rc, out = run(home, ["show", droid_lp])
        check("rung/last used beats android project",
              "send would use: IntelliJ IDEA (last used)" in out, out)
        rc, out = run(home, ["send", droid_lp, "--ide", "as", "--no-ide", "--prompt-stdin"],
                      stdin="hi")
        check("rung/--ide beats android and last used", rc == 0
              and "ide: Android Studio (--ide) - not launched (--no-ide)" in out, out)
        run(home, ["clear", droid_lp])
        FAKE["ids"] = [ident(lu, editor="as")]
        rc, out = run(home, ["send", lu, "--ide", "idea", "--prompt-stdin"], stdin="hi")
        check("rung/live window beats --ide", rc == 0
              and "ide: Android Studio (live window) - already open" in out, out)
        check("rung/--ide on a live window adds the ignored note",
              "note: --ide idea ignored; a live Android Studio window takes the drop" in out, out)
        run(home, ["clear", lu])
        rc, out = run(home, ["send", lu, "--ide", "as", "--prompt-stdin"], stdin="hi")
        check("rung/--ide matching the live window adds no note", rc == 0
              and "ignored" not in out, out)
        run(home, ["clear", lu])
        FAKE["ids"] = []
        rc, out = run(home, ["send", lu, "--ide", "bogus", "--prompt-stdin"], stdin="hi")
        check("rung/--ide outside the APP table is a usage error", rc == 2, out)
        shutil.rmtree(os.path.join(home, ".ccvi", "agent_state"))
        shutil.rmtree(os.path.join(home, ".vscode"))

        # ---- launch guard 1: a launch under 180 s ago is not repeated
        lg = make_repo(os.path.join(work, "launchguard"))
        launches(home, {lg: ("idea", 179_000)})
        rc, out = run(home, ["send", lg, "--prompt-stdin"], stdin="hi")
        check("launch/179 s ago is not relaunched", rc == 0 and ide_line(out) ==
              "ide: IntelliJ IDEA (preference) - launched 179s ago; waiting for CCVI to start"
              " - not relaunched", out)
        run(home, ["clear", lg])
        launches(home, {lg: ("idea", 181_000)})
        rc, out = run(home, ["send", lg, "--prompt-stdin"], stdin="hi")
        check("launch/181 s ago launches", rc == 0 and "would run: open -a" in out, out)
        run(home, ["clear", lg])
        rc, out = run(home, ["send", lg, "--no-ide", "--prompt-stdin"], stdin="hi")
        check("launch/--no-ide still wins", rc == 0 and "not launched (--no-ide)" in out, out)
        run(home, ["clear", lg])
        with open(os.path.join(home, ".ccvi", "autoprompt_launches.json"), "w") as f:
            f.write("{not json")
        rc, out = run(home, ["send", lg, "--prompt-stdin"], stdin="hi")
        check("launch/an unreadable memory file launches", rc == 0 and "would run" in out, out)
        run(home, ["clear", lg])
        if sys.platform == "darwin":
            # The real path: a fake `open` records its argv, and the launch is remembered.
            fakebin = os.path.join(tmp, "fakebin")
            os.makedirs(fakebin)
            open_log = os.path.join(tmp, "open.log")
            with open(os.path.join(fakebin, "open"), "w") as f:
                f.write('#!/bin/sh\necho "$@" >> "%s"\n' % open_log)
            os.chmod(os.path.join(fakebin, "open"), 0o755)
            launches(home, {"/gone/old": ("idea", 2 * 86_400_000)})
            real_env = dict(vs_env, AUTOPROMPT_NO_LAUNCH="0",
                            PATH=fakebin + os.pathsep + os.environ.get("PATH", ""))
            rc1, out1 = run(home, ["send", lg, "--prompt-stdin"], stdin="one", env_extra=real_env)
            rc2, out2 = run(home, ["send", lg, "--prompt-stdin"], stdin="two", env_extra=real_env)
            opens = open(open_log).read().splitlines() if os.path.exists(open_log) else []
            check("launch/back-to-back sends launch once", rc1 == 0 and rc2 == 0
                  and opens == ["-a IntelliJ IDEA %s" % lg], (opens, out1, out2))
            check("launch/the second send reports not relaunched",
                  ide_line(out1).endswith("- launched")
                  and ide_line(out2).endswith("not relaunched"), (out1, out2))
            mem = json.load(open(os.path.join(home, ".ccvi", "autoprompt_launches.json")))
            check("launch/memory records the launch and prunes day-old entries",
                  list(mem) == [lg] and mem[lg]["editorId"] == "idea", mem)
            run(home, ["clear", lg])
        os.remove(os.path.join(home, ".ccvi", "autoprompt_launches.json"))

        # ---- launch guard 2: open in a running JetBrains IDE (idea, as only)
        hp_dir = os.path.join(home, "Desktop", "hp")
        hp = make_repo(hp_dir)
        jb = os.path.join(home, "Library", "Application Support", "JetBrains")
        new_xml = os.path.join(jb, "IntelliJIdea2026.2", "options", "recentProjects.xml")
        old_xml = os.path.join(jb, "IntelliJIdea2025.3", "options", "recentProjects.xml")
        now_s = time.time()
        recent_projects(new_xml, [("$USER_HOME$/Desktop/hp", True)], mtime=now_s)
        running = {"AUTOPROMPT_RUNNING_APPS": "IntelliJ IDEA"}
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi")
        check("open/opened=true but the app is not running launches", rc == 0
              and "would run: open -a" in out, out)
        run(home, ["clear", hp])
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi", env_extra=running)
        check("open/opened=true and the app running is not relaunched", rc == 0
              and ide_line(out) == "ide: IntelliJ IDEA (preference) - open in IntelliJ IDEA but "
              "CCVI is not answering; the drop waits - not relaunched", out)
        run(home, ["clear", hp])
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi",
                      env_extra={"AUTOPROMPT_RUNNING_APPS": "Android Studio"})
        check("open/another app running does not count", rc == 0 and "would run" in out, out)
        run(home, ["clear", hp])
        recent_projects(new_xml, [("$USER_HOME$/Desktop/hp", False)], mtime=now_s)
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi", env_extra=running)
        check("open/opened=false launches", rc == 0 and "would run" in out, out)
        run(home, ["clear", hp])
        recent_projects(old_xml, [("$USER_HOME$/Desktop/hp", True)], mtime=now_s - 3600)
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi", env_extra=running)
        check("open/an older config dir's opened=true is ignored", rc == 0 and "would run" in out,
              out)
        run(home, ["clear", hp])
        os.utime(old_xml, (now_s + 60, now_s + 60))
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi", env_extra=running)
        check("open/the newest config dir by mtime is the one read", rc == 0
              and "not relaunched" in out, out)
        run(home, ["clear", hp])
        elsewhere = os.path.join(tmp, "elsewhere", "recentProjects.xml")
        recent_projects(elsewhere, [(hp, True)])
        vs_ext = os.path.join(home, ".vscode", "extensions", "appcloud9.ccvi-vscode-1.2.33")
        os.makedirs(vs_ext)
        rc, out = run(home, ["send", hp, "--ide", "vscode", "--prompt-stdin"], stdin="hi",
                      env_extra=dict(vs_env, AUTOPROMPT_RUNNING_APPS="Visual Studio Code",
                                     AUTOPROMPT_RECENT_PROJECTS_GLOBS=elsewhere))
        check("open/vscode gets launch memory only", rc == 0 and "would run" in out, out)
        run(home, ["clear", hp])
        shutil.rmtree(os.path.join(home, ".vscode"))
        rc, out = run(home, ["send", hp, "--prompt-stdin"], stdin="hi",
                      env_extra=dict(running, AUTOPROMPT_RECENT_PROJECTS_GLOBS=os.path.join(
                          tmp, "nowhere", "*.xml") + os.pathsep + elsewhere))
        check("open/AUTOPROMPT_RECENT_PROJECTS_GLOBS replaces the product globs", rc == 0
              and "not relaunched" in out, out)
        run(home, ["clear", hp])
        os.remove(new_xml)
        shutil.rmtree(os.path.dirname(os.path.dirname(old_xml)))
        droid_hp = make_repo(os.path.join(home, "Desktop", "droid_hp"),
                             {"local.properties": "sdk.dir=/x\n"})
        recent_projects(os.path.join(home, "Library", "Application Support", "Google",
                                     "AndroidStudio2026.1.4", "options", "recentProjects.xml"),
                        [("$USER_HOME$/Desktop/droid_hp", True)])
        rc, out = run(home, ["send", droid_hp, "--prompt-stdin"], stdin="hi",
                      env_extra={"AUTOPROMPT_RUNNING_APPS": "Android Studio"})
        check("open/Android Studio reads its own recentProjects.xml", rc == 0
              and "open in Android Studio but CCVI is not answering" in out, out)
        run(home, ["clear", droid_hp])
        shutil.rmtree(os.path.join(home, "Library", "Application Support", "Google",
                                   "AndroidStudio2026.1.4", "options"))

        # ---- capability
        rc, out = run(home, ["show", plain])
        check("cap/0.4.168 is single", "installed CCVI: 0.4.168 -> capability single" in out, out)
        bare = os.path.join(tmp, "barehome")
        os.makedirs(bare)
        noccvi = make_repo(os.path.join(tmp, "noccvi"))
        rc, out = run(bare, ["send", noccvi, "--prompt-stdin"], stdin="hi")
        check("cap/absent refuses", rc == 1 and "not installed" in out, out)
        check("cap/absent writes nothing", not os.path.exists(ccvi_dir(noccvi)))
        old = os.path.join(tmp, "oldhome")
        install_idea(old, version="0.4.42")
        rc, out = run(old, ["send", noccvi, "--prompt-stdin"], stdin="hi")
        check("cap/too old refuses", rc == 1 and "0.4.42" in out
              and "idePreferred" in out, out)

        # ---- prompt intake
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-arg-stdin"],
                      stdin="literal words\n")
        d = ccvi_dir(plain)
        check("intake/literal", rc == 0 and open(os.path.join(d, "auto_prompt.md")).read()
              == "literal words\n", out)
        run(home, ["clear", plain])
        brief = os.path.join(tmp, "brief.md")
        with open(brief, "w") as f:
            f.write("from a file\n")
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-arg-stdin"], stdin=brief)
        check("intake/.md path", rc == 0 and open(os.path.join(d, "auto_prompt.md")).read()
              == "from a file\n", out)
        run(home, ["clear", plain])
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-arg-stdin"],
                      stdin="~/nope/missing.md")
        check("intake/missing path refused", rc == 1 and "no such file" in out
              and listing(d) == [], out)
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-arg-stdin"],
                      stdin="fix the typo in doc/contracts/auto_prompt.md")
        check("intake/sentence ending in .md is literal", rc == 0, out)
        run(home, ["clear", plain])
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-arg-stdin"],
                      stdin="line one\nsee doc/x.md")
        check("intake/multi-line is literal", rc == 0, out)
        run(home, ["clear", plain])
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-stdin"], stdin=brief)
        check("intake/--prompt-stdin never reads a path", rc == 0 and
              open(os.path.join(d, "auto_prompt.md")).read().strip() == brief, out)
        run(home, ["clear", plain])
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-stdin"], stdin="   \n")
        check("intake/empty refused", rc == 1 and "empty" in out, out)

        # ---- writer
        rc, out = run(home, ["send", plain, "--prompt-stdin"], stdin="first")
        check("writer/single empty -> bare slot", rc == 0 and "(slot 0, 1 waiting)" in out
              and 'would run: open -a "IntelliJ IDEA"' in out, out)
        rc, out = run(home, ["send", plain, "--prompt-stdin"], stdin="second")
        check("writer/single occupied refuses", rc == 1 and "already waiting" in out, out)
        env = {"AUTOPROMPT_FLOORS_JSON": NUMBERED}
        rc, out = run(home, ["send", plain, "--prompt-stdin"], stdin="second", env_extra=env)
        check("writer/numbered -> _1", rc == 0 and "auto_prompt_1.md" in out, out)
        rc, out = run(home, ["send", plain, "--prompt-stdin"], stdin="third", env_extra=env)
        check("writer/numbered -> _2", rc == 0 and "auto_prompt_2.md" in out, out)
        run(home, ["clear", plain])

        def send_one(i):
            return run(home, ["send", plain, "--no-ide", "--prompt-stdin"], stdin="p%02d" % i,
                       env_extra=env)
        with ThreadPoolExecutor(max_workers=20) as ex:
            results = list(ex.map(send_one, range(20)))
        names = listing(d)
        bodies = sorted(open(os.path.join(d, n)).read().strip() for n in names)
        check("writer/20 parallel all succeed", all(rc == 0 for rc, _ in results),
              [o for rc, o in results if rc])
        check("writer/20 distinct slots", len(names) == 20, names)
        check("writer/no prompt lost", bodies == ["p%02d" % i for i in range(20)], bodies)
        check("writer/no temp left", not any(n.startswith(".") for n in names), names)

        # ---- directives floor (2026-11-04): the `.prompt.md` spelling and the envelope
        run(home, ["clear", plain])
        envelope = "---\nsession: new\nmodes: agent-loop 80\n---\nthe work order"
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-stdin"], stdin=envelope,
                      env_extra=env)
        check("directives/below floor refuses an envelope", rc == 1 and "0.4.168" in out
              and "directives" in out and listing(d) == [], out)
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-stdin"],
                      stdin="\ufeff" + envelope, env_extra=env)
        check("directives/a BOM does not hide the envelope", rc == 1 and listing(d) == [], out)
        rc, out = run(home, ["send", plain, "--no-ide", "--prompt-stdin"], stdin="plain",
                      env_extra=env)
        check("directives/below floor keeps the legacy name", rc == 0
              and listing(d) == ["auto_prompt.md"], listing(d))
        run(home, ["clear", plain])
        dhome = os.path.join(tmp, "dirhome")
        install_idea(dhome, version="0.4.187")
        rc, out = run(dhome, ["send", plain, "--no-ide", "--prompt-stdin"], stdin=envelope)
        check("directives/at floor writes the new spelling", rc == 0
              and listing(d) == ["auto.prompt.md"], out)
        check("directives/envelope written verbatim",
              open(os.path.join(d, "auto.prompt.md")).read() == envelope + "\n")
        rc, out = run(dhome, ["send", plain, "--no-ide", "--prompt-stdin"], stdin="next")
        check("directives/next slot is auto_1.prompt.md", rc == 0
              and "auto_1.prompt.md" in listing(d), listing(d))
        run(home, ["clear", plain])
        with open(os.path.join(d, "auto_prompt_3.md"), "w") as f:
            f.write("legacy waiting")
        rc, out = run(dhome, ["send", plain, "--no-ide", "--prompt-stdin"], stdin="after legacy")
        check("directives/a legacy drop counts toward the next slot", rc == 0
              and "auto_4.prompt.md" in listing(d), listing(d))
        rc, out = run(dhome, ["clear", plain])
        check("directives/clear takes both spellings", rc == 0 and listing(d) == [], listing(d))

        # ---- open: send's IDE half, never a drop
        op = make_repo(os.path.join(work, "open_target"))
        rc, out = run(home, ["open", op])
        check("open/no window launches", rc == 0 and "window: none open" in out
              and ide_line(out).startswith("ide: IntelliJ IDEA (preference) - would run: open -a"),
              out)
        check("open/writes no drop", listing(ccvi_dir(op)) == [], listing(ccvi_dir(op)))
        rc, out = run(home, ["open", op, "--ide", "vscode"])
        check("open/--ide rung and no drop-capability check",
              rc == 0 and "(--ide) - would run: open -a" in ide_line(out), out)
        launches(home, {op: ("idea", 5000)})
        rc, out = run(home, ["open", op])
        check("open/recent launch is not relaunched", rc == 0
              and "not relaunched" in ide_line(out), out)
        FAKE["ids"] = [ident(op, editor="idea")]
        rc, out = run(home, ["open", op])
        check("open/live window launches nothing", rc == 0 and out.startswith("open -> ")
              and "window: live in" in out and "already open; nothing launched" in ide_line(out),
              out)
        FAKE["ids"] = []
        check("open/still no drop", listing(ccvi_dir(op)) == [], listing(ccvi_dir(op)))
        rc, out = run(home, ["open", notgit])
        check("open/non-git refused", rc == 1 and out.startswith("refused:"), out)
        rc, out = run(home, ["open"])
        check("open/usage error is exit 2", rc == 2, out)

        # ---- show writes nothing
        before = listing(d)
        run(home, ["show", plain])
        check("show/writes nothing", listing(d) == before)

        # ---- clear
        rc, out = run(home, ["clear", plain])
        trash = os.path.join(home, ".Trash") if sys.platform == "darwin" else \
            os.path.join(home, ".local", "share", "Trash", "files")
        check("clear/empties slots", rc == 0 and listing(d) == [], listing(d))
        check("clear/into the Trash", len([n for n in listing(trash)
                                           if n.startswith("auto_prompt-cleared-")]) >= 20)
        rc, out = run(home, ["clear", plain])
        check("clear/second clear is a no-op", rc == 0 and "nothing waiting" in out, out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if _failures:
        print("test_autoprompt FAIL - %d of %d checks failed:" % (len(_failures), _count))
        for f in _failures:
            print("  - " + f)
        return 1
    print("test_autoprompt OK - %d checks passed" % _count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
