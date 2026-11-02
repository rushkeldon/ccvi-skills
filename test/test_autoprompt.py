#!/usr/bin/env python3
"""
Harness for plugin/skills/autoprompt/scripts/autoprompt.py.

Runs the real script as a subprocess against a throwaway HOME (config, agent_state, the
Trash, and the IDE install dirs are all fakes) with AUTOPROMPT_NO_LAUNCH=1, over real git
repos and worktrees built in a temp dir.

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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SCRIPT = os.path.join(REPO, "plugin", "skills", "autoprompt", "scripts", "autoprompt.py")

NUMBERED = json.dumps({
    "as": {"single": "0.4.168", "numbered": "0.4.168"},
    "idea": {"single": "0.4.168", "numbered": "0.4.168"},
    "vscode": {"single": None, "numbered": None},
    "cursor": {"single": None, "numbered": None},
})

_failures = []
_count = 0


def check(name, cond, detail=""):
    global _count
    _count += 1
    if not cond:
        _failures.append("%s  %s" % (name, detail))


def run(home, args, stdin="", env_extra=None, cwd=None):
    env = dict(os.environ, HOME=home, AUTOPROMPT_NO_LAUNCH="1")
    env.pop("AUTOPROMPT_FLOORS_JSON", None)
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


def agent_state(home, name, cwd, repo_root, editor="idea", age_ms=0, version=1, state="idle"):
    d = os.path.join(home, ".ccvi", "agent_state")
    os.makedirs(d, exist_ok=True)
    rec = {"version": version, "sessionId": name, "state": state, "isIdle": True, "cwd": cwd,
           "repoRoot": repo_root, "editorId": editor, "pid": 1,
           "updatedAtMs": int(time.time() * 1000) - age_ms}
    with open(os.path.join(d, name + ".json"), "w") as f:
        json.dump(rec, f)


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
        agent_state(home, "live", plain, plain, editor="as")
        rc, out = run(home, ["show", plain])
        check("choose/live window wins", "send would use: Android Studio (live window)" in out,
              out)
        os.remove(os.path.join(home, ".ccvi", "agent_state", "live.json"))
        agent_state(home, "stale", plain, plain, editor="as", age_ms=120_000)
        rc, out = run(home, ["show", plain])
        check("choose/stale ignored", "send would use: IntelliJ IDEA (preference)" in out
              and "history: as" in out, out)
        agent_state(home, "v2", plain, plain, editor="as", version=2)
        rc, out = run(home, ["show", plain])
        check("choose/version 2 skipped", "send would use: IntelliJ IDEA (preference)" in out,
              out)
        shutil.rmtree(os.path.join(home, ".ccvi", "agent_state"))
        agent_state(home, "sib", wt, plain, editor="idea")
        rc, out = run(home, ["send", "plain", "--no-ide", "--prompt-stdin"], stdin="hi")
        check("send/sibling worktree note", rc == 0 and "other worktrees of this repo are open"
              in out and wt in out, out)
        run(home, ["clear", "plain"])
        shutil.rmtree(os.path.join(home, ".ccvi", "agent_state"))

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
