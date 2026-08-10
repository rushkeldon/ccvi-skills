#!/usr/bin/env python3
"""
build.py - the release build for the ccvi-skills suite.

One plugin, three skills, one version. The canonical version lives in
plugin/.claude-plugin/plugin.json; this script stamps it everywhere it is
displayed and packages the one zip artifact:

  1. read the canonical version from plugin/.claude-plugin/plugin.json
  2. STAMP it into every version display - the help headers of the three skills
     (modes SKILL.md + scripts/modes.py, plans SKILL.md, seedprompt SKILL.md).
     A real version string is replaced in place; there is no {{placeholder}}
     token, so the source always reads as a valid, if occasionally stale, file.
  3. update the "ccvi-skills · vN.N.N" display in README.md (skipped with a
     notice when README.md does not exist yet).
  4. PACKAGE ccvi-skills.zip at the repo root: the plugin/ tree at the zip root,
     reproducibly (fixed zip metadata, sorted member order - an unchanged build
     produces a byte-identical zip, no spurious git churn).

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
]

README = p("README.md")
README_RE = re.compile(r"ccvi-skills · v\d+\.\d+\.\d+")

PLUGIN_DIR = p("plugin")
ZIP_OUT = p("ccvi-skills.zip")

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


def zip_bytes():
  """Build the artifact in memory - deterministic, so equality means current."""
  buf = io.BytesIO()
  with zipfile.ZipFile(buf, "w") as zf:
    for arcname, src in zip_members():
      info = zipfile.ZipInfo(arcname, date_time=_ZIP_EPOCH)
      info.compress_type = zipfile.ZIP_DEFLATED
      # Executable bit for scripts, plain for everything else.
      perm = 0o755 if arcname.endswith((".py", ".sh")) else 0o644
      info.external_attr = perm << 16
      with open(src, "rb") as fh:
        zf.writestr(info, fh.read())
  return buf.getvalue()


def package():
  """(Re)write ccvi-skills.zip from current source."""
  blob = zip_bytes()
  tmp = ZIP_OUT + ".tmp"
  with open(tmp, "wb") as fh:
    fh.write(blob)
  os.replace(tmp, ZIP_OUT)


def zip_current():
  """True when the on-disk artifact byte-matches a fresh deterministic build."""
  if not os.path.isfile(ZIP_OUT):
    return False
  with open(ZIP_OUT, "rb") as fh:
    return fh.read() == zip_bytes()


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
  if not zip_current():
    problems.append("ccvi-skills.zip is stale or missing - run python3 build.py")
  if problems:
    print("build --check FAIL:")
    for pr in problems:
      print("  - " + pr)
    return 1
  print("build --check OK — version {} stamped everywhere; zip current".format(version))
  return 0


def do_build():
  version = canon_version()
  stamped = stamp(version)
  readme = update_readme(version)
  package()
  print("build OK — ccvi-skills v{}".format(version))
  print("  stamped:  {} file(s)".format(len(stamped)) if stamped else "  stamped:  already current")
  if readme is None:
    print("  README:   not present - skipped (authored later; rerun build.py after)")
  else:
    print("  README:   {}".format("updated" if readme else "already current"))
  print("  packaged: ccvi-skills.zip")
  return 0


if __name__ == "__main__":
  if "--check" in sys.argv[1:]:
    sys.exit(do_check())
  sys.exit(do_build())
