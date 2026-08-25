#!/usr/bin/env python3
"""
build.py - the release build for the ccvi-skills suite.

One plugin, four skills, one version. The canonical version lives in
plugin/.claude-plugin/plugin.json; this script stamps it everywhere it is
displayed and packages the one zip artifact:

  1. read the canonical version from plugin/.claude-plugin/plugin.json
  2. STAMP it into every version display - the help headers of the four skills
     (modes SKILL.md + scripts/modes.py, plans SKILL.md, seedprompt SKILL.md,
     cleancode SKILL.md).
     A real version string is replaced in place; there is no {{placeholder}}
     token, so the source always reads as a valid, if occasionally stale, file.
  3. update the "ccvi-skills · vN.N.N" display in README.md (skipped with a
     notice when README.md does not exist yet).
  4. EMIT manifest.json - the machine-readable signatures contract for hosts
     (ccvi-idea reads it to drive its verb dialogs and to version-gate its
     bundle without opening the zip). Written BOTH beside the zip at the repo
     root AND into the zip root. The MANIFEST structure below is the canonical
     source for verb signatures; SKILL.md prose is documentation.
  5. PACKAGE ccvi-skills.zip at the repo root: the plugin/ tree at the zip root
     plus manifest.json, reproducibly (fixed zip metadata, sorted member order -
     an unchanged build produces a byte-identical zip, no spurious git churn).

Usage:
  python3 build.py           # stamp + readme + package (a full build)
  python3 build.py --check   # verify everything is in sync; exit 1 if not

To cut a release: bump "version" in plugin/.claude-plugin/plugin.json, run this,
review, commit. The script stamps; it never bumps.

Stdlib only. Python 3.9+.
"""

import io
import os
import re
import sys
import json
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))


def p(*parts):
  return os.path.join(ROOT, *parts)


# Canonical version lives in the plugin manifest.
PLUGIN_JSON = p("plugin", ".claude-plugin", "plugin.json")

# Every file that DISPLAYS the version, with the anchored pattern that finds the
# display. Each pattern is distinctive enough that the substitution can never hit
# an unrelated version-looking string.
STAMPS = [
  (p("plugin", "skills", "modes", "SKILL.md"),
   re.compile(r"Modes · v\d+\.\d+\.\d+"), "Modes · v{v}"),
  (p("plugin", "skills", "modes", "scripts", "modes.py"),
   re.compile(r"Modes · v\d+\.\d+\.\d+"), "Modes · v{v}"),
  (p("plugin", "skills", "plans", "SKILL.md"),
   re.compile(r"/plans · v\d+\.\d+\.\d+"), "/plans · v{v}"),
  (p("plugin", "skills", "seedprompt", "SKILL.md"),
   re.compile(r"/seedprompt · v\d+\.\d+\.\d+"), "/seedprompt · v{v}"),
  (p("plugin", "skills", "cleancode", "SKILL.md"),
   re.compile(r"/cleancode · v\d+\.\d+\.\d+"), "/cleancode · v{v}"),
]

README = p("README.md")
README_RE = re.compile(r"ccvi-skills · v\d+\.\d+\.\d+")

PLUGIN_DIR = p("plugin")
ZIP_OUT = p("ccvi-skills.zip")
MANIFEST_OUT = p("manifest.json")

# ---------------------------------------------------------------------------------
# The signatures manifest - the machine-readable contract hosts consume.
# Params are ORDERED (positional order of the verb's signature); every param
# carries its literal name and required flag; `kind` is a hint from the vocabulary
# {plan-file, dir, file, model, flag, freeform}; `default` appears where one exists.
# When a verb or param changes in a SKILL.md, change it HERE in the same commit -
# --check cross-checks verb names against the SKILL.md prose as a drift tripwire.
# ---------------------------------------------------------------------------------

def _param(name, required, kind=None, default=None):
  d = {"name": name, "required": required}
  if kind is not None:
    d["kind"] = kind
  if default is not None:
    d["default"] = default
  return d


MANIFEST_SKILLS = [
  {
    "name": "modes",
    "invocation": "/modes [verb] [param]",
    "verbs": [
      {"name": "plan", "params": [_param("dir", False, "dir", "./")]},
      {"name": "agent", "params": []},
      {"name": "agent-loop", "params": [_param("pct", False, "freeform")]},
      {"name": "one-word", "params": []},
      {"name": "sbs", "params": []},
      {"name": "exclude", "params": [_param("patterns", True, "freeform")]},
      {"name": "include", "params": [_param("patterns", True, "freeform")]},
      {"name": "exit", "params": [_param("mode", True, "freeform")]},
      {"name": "list", "params": []},
      {"name": "clear", "params": []},
    ],
  },
  {
    "name": "plans",
    "invocation": "/plans [verb] [args]",
    "verbs": [
      {"name": "write", "params": [_param("name", False, "freeform")]},
      {"name": "review", "params": [_param("plan", True, "plan-file"),
                                    _param("out", False, "dir", "./"),
                                    _param("model", False, "model")]},
      {"name": "verify", "params": [_param("plan", True, "plan-file"),
                                    _param("out", False, "dir", "./"),
                                    _param("model", False, "model")]},
      {"name": "update", "params": [_param("plan", True, "plan-file"),
                                    _param("report", True, "file")]},
      {"name": "build", "params": [_param("plan", True, "plan-file"),
                                   _param("model", False, "model")]},
      {"name": "archive", "params": [_param("dir", False, "dir"),
                                     _param("archiveDir", False, "dir"),
                                     _param("lenient", False, "flag", "0")]},
    ],
  },
  {
    "name": "seedprompt",
    "invocation": "/seedprompt [verb] [args]",
    "verbs": [
      {"name": "write", "params": [_param("body", False, "freeform")]},
      {"name": "show", "params": []},
      {"name": "clear", "params": []},
    ],
  },
  {
    # cleancode's verbs are noun-first TWO-WORD strings ("comments escrow") - the
    # verb name includes the space. Consumers that split on whitespace must treat
    # the name as opaque.
    "name": "cleancode",
    "invocation": "/cleancode [noun] [verb] [args]",
    "verbs": [
      {"name": "comments escrow",
       "params": [_param("path", True, "dir"),
                  _param("escrowDir", False, "dir", "./comment_escrow/")]},
      {"name": "comments strip",
       "params": [_param("path", True, "dir"),
                  _param("escrowDir", False, "dir", "./comment_escrow/")]},
      {"name": "comments annotate",
       "params": [_param("path", True, "dir"),
                  _param("escrowDir", False, "dir", "./comment_escrow/")]},
      {"name": "naming refactor",
       "params": [_param("symbol", True, "freeform"),
                  _param("newName", True, "freeform"),
                  _param("path", False, "dir"),
                  _param("tier", False, "freeform", "internal")]},
      {"name": "naming propose",
       "params": [_param("path", True, "dir"),
                  _param("tier", False, "freeform", "internal")]},
      {"name": "naming apply",
       "params": [_param("path", True, "dir"),
                  _param("tier", False, "freeform", "internal"),
                  _param("proposals", False, "file")]},
      {"name": "conventions export",
       "params": [_param("topic", False, "freeform", "all"),
                  _param("pathAndFileName", False, "file")]},
      {"name": "conventions import",
       "params": [_param("pathAndFileName", False, "file")]},
      {"name": "conventions generate",
       "params": [_param("strategy", True, "freeform"),
                  _param("pathAndFileName", False, "file")]},
      {"name": "run",
       "params": [_param("path", True, "dir"),
                  _param("verdict", False, "freeform"),
                  _param("escrowDir", False, "dir", "./comment_escrow/"),
                  _param("tier", False, "freeform", "internal")]},
    ],
  },
]


def manifest_bytes(version):
  """The manifest as deterministic bytes (stable key order, trailing newline)."""
  data = {"name": "ccvi-skills", "version": version, "skills": MANIFEST_SKILLS}
  return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")

# Never packaged, even if they appear under plugin/.
ZIP_EXCLUDE_DIRS = {"__pycache__"}
ZIP_EXCLUDE_FILES = {".DS_Store"}


def canon_version():
  with open(PLUGIN_JSON, encoding="utf-8") as fh:
    return json.load(fh)["version"]


def _read(path):
  with open(path, encoding="utf-8") as fh:
    return fh.read()


def _write(path, text):
  with open(path, "w", encoding="utf-8") as fh:
    fh.write(text)


def stamp(version, write=True):
  """Stamp the version into every display. Returns the list of files whose
  stamped version did NOT already match (empty when everything is in sync)."""
  stale = []
  for path, pattern, template in STAMPS:
    text = _read(path)
    target = template.format(v=version)
    found = pattern.findall(text)
    if not found:
      raise SystemExit("build: no version display matching {} in {}".format(
        pattern.pattern, os.path.relpath(path, ROOT)))
    if any(f != target for f in found):
      stale.append(path)
      if write:
        _write(path, pattern.sub(target, text))
  return stale


def update_readme(version, write=True):
  """Set the ccvi-skills · vN.N.N display in the README. Returns True if it
  changed, False if already current, None if README.md does not exist (a
  notice, not drift - the README is authored after the first build)."""
  if not os.path.isfile(README):
    return None
  text = _read(README)
  target = "ccvi-skills · v" + version
  if not README_RE.search(text):
    raise SystemExit("build: could not find a `ccvi-skills · vN.N.N` display in README.md")
  new = README_RE.sub(target, text)
  if new != text:
    if write:
      _write(README, new)
    return True
  return False


# Fixed zip metadata -> reproducible artifact (unchanged input => byte-identical output).
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def zip_members():
  """The plugin/ tree, sorted, as (arcname, srcpath) pairs."""
  members = []
  for dirpath, dirnames, filenames in os.walk(PLUGIN_DIR):
    dirnames[:] = sorted(d for d in dirnames if d not in ZIP_EXCLUDE_DIRS)
    for name in sorted(filenames):
      if name in ZIP_EXCLUDE_FILES or name.endswith(".zip"):
        continue
      src = os.path.join(dirpath, name)
      arcname = os.path.relpath(src, PLUGIN_DIR).replace(os.sep, "/")
      members.append((arcname, src))
  return members


def zip_bytes(version):
  """Build the artifact in memory - deterministic, so equality means current.
  Members: the plugin/ tree at the zip root, plus manifest.json."""
  extra = [("manifest.json", manifest_bytes(version))]
  buf = io.BytesIO()
  with zipfile.ZipFile(buf, "w") as zf:
    members = [(arc, None, blob) for arc, blob in extra]
    members += [(arc, src, None) for arc, src in zip_members()]
    for arcname, src, blob in sorted(members):
      info = zipfile.ZipInfo(arcname, date_time=_ZIP_EPOCH)
      info.compress_type = zipfile.ZIP_DEFLATED
      # Executable bit for scripts, plain for everything else.
      perm = 0o755 if arcname.endswith((".py", ".sh")) else 0o644
      info.external_attr = perm << 16
      if blob is None:
        with open(src, "rb") as fh:
          blob = fh.read()
      zf.writestr(info, blob)
  return buf.getvalue()


def package(version):
  """(Re)write manifest.json and ccvi-skills.zip from current source."""
  with open(MANIFEST_OUT, "wb") as fh:
    fh.write(manifest_bytes(version))
  blob = zip_bytes(version)
  tmp = ZIP_OUT + ".tmp"
  with open(tmp, "wb") as fh:
    fh.write(blob)
  os.replace(tmp, ZIP_OUT)


def zip_current(version):
  """True when the on-disk artifact byte-matches a fresh deterministic build."""
  if not os.path.isfile(ZIP_OUT):
    return False
  with open(ZIP_OUT, "rb") as fh:
    return fh.read() == zip_bytes(version)


def manifest_current(version):
  """True when the sibling manifest.json byte-matches a fresh emit."""
  if not os.path.isfile(MANIFEST_OUT):
    return False
  with open(MANIFEST_OUT, "rb") as fh:
    return fh.read() == manifest_bytes(version)


def _readme_diagram():
  """The lines between README.md's ```diagram fence and its closer."""
  lines = _read(README).split("\n")
  s = next(i for i, l in enumerate(lines) if l.startswith("```diagram"))
  e = next(i for i, l in enumerate(lines[s + 1:], s + 1) if l.startswith("```"))
  return "\n".join(lines[s + 1:e])


def diagram_drift():
  """The /plans lifecycle diagram lives in two places on purpose: the README (for
  humans browsing the repo) and the /plans help output (for users who type the bare
  verb). They must be byte-identical, or one silently teaches the wrong lifecycle.
  Returns a list of problem strings."""
  if not os.path.isfile(README):
    return []
  try:
    diagram = _readme_diagram()
  except StopIteration:
    return ["README.md has no ```diagram block - the /plans lifecycle diagram is missing"]
  help_md = _read(p("plugin", "skills", "plans", "SKILL.md"))
  if diagram not in help_md:
    return ["the /plans help-output diagram has drifted from README.md's "
            "(they must be byte-identical)"]
  return []


def manifest_drift():
  """Cheap tripwire: every plans/seedprompt/modes verb named in the manifest must
  appear as `/<skill> <verb>` (or a directive-table row) in its SKILL.md prose.
  Catches a verb rename that touched SKILL.md but not MANIFEST_SKILLS. Returns a
  list of problem strings."""
  problems = []
  for skill in MANIFEST_SKILLS:
    md = _read(p("plugin", "skills", skill["name"], "SKILL.md"))
    for verb in skill["verbs"]:
      token = "/{} {}".format(skill["name"], verb["name"])
      if token not in md and "`{}`".format(verb["name"]) not in md:
        problems.append("manifest verb `{}` not found in {} SKILL.md".format(
          token, skill["name"]))
  return problems


def do_check():
  """Verify source is in sync WITHOUT modifying anything. Exit 1 on any drift."""
  version = canon_version()
  problems = []
  stale = stamp(version, write=False)
  if stale:
    problems.append("version not stamped ({}): {}".format(
      version, ", ".join(os.path.relpath(s, ROOT) for s in stale)))
  readme = update_readme(version, write=False)
  if readme is None:
    print("notice: README.md not present - skipping its version check")
  elif readme:
    problems.append("README ccvi-skills display != " + version)
  if not manifest_current(version):
    problems.append("manifest.json is stale or missing - run python3 build.py")
  problems.extend(manifest_drift())
  problems.extend(diagram_drift())
  if not zip_current(version):
    problems.append("ccvi-skills.zip is stale or missing - run python3 build.py")
  if problems:
    print("build --check FAIL:")
    for pr in problems:
      print("  - " + pr)
    return 1
  print("build --check OK — version {} stamped everywhere; manifest + zip current".format(version))
  return 0


def do_build():
  version = canon_version()
  drift = manifest_drift() + diagram_drift()
  if drift:
    print("build FAIL — source out of sync:")
    for pr in drift:
      print("  - " + pr)
    return 1
  stamped = stamp(version)
  readme = update_readme(version)
  package(version)
  print("build OK — ccvi-skills v{}".format(version))
  print("  stamped:  {} file(s)".format(len(stamped)) if stamped else "  stamped:  already current")
  if readme is None:
    print("  README:   not present - skipped (authored later; rerun build.py after)")
  else:
    print("  README:   {}".format("updated" if readme else "already current"))
  print("  packaged: manifest.json, ccvi-skills.zip")
  return 0


if __name__ == "__main__":
  if "--check" in sys.argv[1:]:
    sys.exit(do_check())
  sys.exit(do_build())
