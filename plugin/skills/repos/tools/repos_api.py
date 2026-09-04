#!/usr/bin/env python3
"""repos_api.py - deterministic API plumbing for the /repos skill.

Zero-dependency python3 (urllib, json, subprocess for `gh`). Every subcommand
prints JSON to stdout and exits 0 on success, 1 on failure (error JSON on stderr).

Forgejo auth: token at ~/.config/repos/forge_token; base URL from
~/.config/repos/manifest.json ("forge_url"). GitHub side shells to `gh api` -
never raw tokens.

Subcommands:
  forge ensure-repo --org O --name N
  forge pr          --repo R --branch B [--base BASE] [--title T --body-file F]
  forge threads     --repo R --pr N
  forge comment     --repo R --pr N --path P --line L --body-file F
  forge check-git-credentials [--remote NAME]
  github export     --repo R --branch B --base BASE --title T --body-file F
                    --comments-file J [--dry-run]
  selftest
"""

import argparse
import json
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

CONFIG_ROOT = pathlib.Path.home() / ".config" / "repos"


def _die(msg, detail=None):
  err = {"error": msg}
  if detail is not None:
    err["detail"] = detail
  print(json.dumps(err), file=sys.stderr)
  sys.exit(1)


def _forge_base():
  manifest = CONFIG_ROOT / "manifest.json"
  if not manifest.is_file():
    _die("missing manifest", str(manifest) + " not found - run /repos init")
  url = json.loads(manifest.read_text()).get("forge_url", "").rstrip("/")
  if not url:
    _die("manifest has no forge_url")
  return url


def _forge_token():
  tok = CONFIG_ROOT / "forge_token"
  if not tok.is_file():
    _die("missing forge token", str(tok) + " not found - run /repos init")
  return tok.read_text().strip()


def _forge(method, path, body=None, ok404=False):
  req = urllib.request.Request(
    _forge_base() + "/api/v1" + path,
    data=json.dumps(body).encode() if body is not None else None,
    method=method,
    headers={
      "Authorization": "token " + _forge_token(),
      "Content-Type": "application/json",
    },
  )
  try:
    with urllib.request.urlopen(req) as resp:
      raw = resp.read()
      return json.loads(raw) if raw else {}
  except urllib.error.HTTPError as e:
    if e.code == 404 and ok404:
      return None
    _die("forge API {} {} -> HTTP {}".format(method, path, e.code),
         e.read().decode(errors="replace")[:500])


# ---------------------------------------------------------------- forge verbs

def forge_ensure_repo(args):
  existing = _forge("GET", "/repos/{}/{}".format(args.org, args.name), ok404=True)
  if existing is None:
    existing = _forge("POST", "/orgs/{}/repos".format(args.org),
                      {"name": args.name, "private": True, "auto_init": False})
  print(json.dumps({
    "full_name": existing["full_name"],
    "clone_url": existing["clone_url"],
    "created": "id" in existing and existing.get("created_at") == existing.get("updated_at"),
  }))


def forge_pr(args):
  owner, name = args.repo.split("/", 1)
  prs = _forge("GET", "/repos/{}/{}/pulls?state=open".format(owner, name)) or []
  for pr in prs:
    if pr["head"]["ref"] == args.branch:
      print(json.dumps({"number": pr["number"], "url": pr["html_url"],
                        "existing": True}))
      return
  body = {"head": args.branch, "base": args.base or "main",
          "title": args.title or args.branch}
  if args.body_file:
    body["body"] = pathlib.Path(args.body_file).read_text()
  pr = _forge("POST", "/repos/{}/{}/pulls".format(owner, name), body)
  print(json.dumps({"number": pr["number"], "url": pr["html_url"],
                    "existing": False}))


def _head_remap(commit_id, head_sha, path, line):
  """head_line/outdated for one comment, via local git in the cwd (the clone).

  Ladder: no basis -> outdated; anchor == head -> unchanged; anchor commit or
  head-side path missing locally (force-push+gc, rename, delete) -> outdated;
  else remap_line over `git diff --unified=0`. Any git failure -> outdated,
  never a guess and never a crash.
  """
  if not commit_id or not head_sha:
    return (None, True)
  if commit_id == head_sha:
    return (line, False)
  def _git_ok(cmd):
    return subprocess.run(cmd, capture_output=True).returncode == 0
  if not _git_ok(["git", "cat-file", "-e", commit_id]):
    return (None, True)
  if not _git_ok(["git", "cat-file", "-e", "{}:{}".format(head_sha, path)]):
    return (None, True)
  res = subprocess.run(
    ["git", "diff", "--unified=0", commit_id, head_sha, "--", path],
    capture_output=True)
  if res.returncode != 0:
    return (None, True)
  return remap_line(line, res.stdout.decode(errors="replace"))


def forge_threads(args):
  """Reviews + inline comments; each comment carries path, line info, body, and
  resolved (Forgejo: resolver != null - probed 2026-08-31, v16.0.3).
  line is as-of the comment's anchor commit; head_line re-anchors it to the
  current PR head (null + outdated=true when the anchored code was rewritten)."""
  owner, name = args.repo.split("/", 1)
  pr = _forge("GET", "/repos/{}/{}/pulls/{}".format(owner, name, args.pr)) or {}
  head_sha = (pr.get("head") or {}).get("sha", "")
  reviews = _forge("GET", "/repos/{}/{}/pulls/{}/reviews".format(
    owner, name, args.pr)) or []
  out = []
  for review in reviews:
    comments = _forge("GET", "/repos/{}/{}/pulls/{}/reviews/{}/comments".format(
      owner, name, args.pr, review["id"])) or []
    for c in comments:
      line = comment_line(c.get("position"), c.get("diff_hunk"))
      head_line, outdated = _head_remap(c.get("commit_id", ""), head_sha,
                                        c["path"], line)
      out.append({
        "review_id": review["id"],
        "comment_id": c["id"],
        "path": c["path"],
        "line": line,
        "head_line": head_line,
        "outdated": outdated,
        "body": c["body"],
        "resolved": c.get("resolver") is not None,
        "author": c["user"]["login"],
        "created_at": c["created_at"],
      })
  print(json.dumps({"pr": int(args.pr), "threads": out,
                    "unresolved": sum(1 for t in out if not t["resolved"]),
                    "resolved": sum(1 for t in out if t["resolved"])}))


def forge_comment(args):
  owner, name = args.repo.split("/", 1)
  body_text = pathlib.Path(args.body_file).read_text()
  review = _forge("POST", "/repos/{}/{}/pulls/{}/reviews".format(
    owner, name, args.pr),
    {"event": "COMMENT", "body": "",
     "comments": [{"path": args.path, "new_position": int(args.line),
                   "body": body_text}]})
  print(json.dumps({"review_id": review["id"], "posted": True,
                    "path": args.path, "line": int(args.line)}))


# ------------------------------------------------- git credential diagnostics

def credential_next_action(helper, keychain, ls_remote):
  """Pure diagnosis-to-remediation mapping (hermetic; covered by selftest).

  helper: the effective credential.helper value, or None when none is configured.
  keychain: "present" | "absent" | "unknown" (keychain entry for the forge host).
  ls_remote: True iff git can actually reach the forge with working credentials.
  """
  if ls_remote:
    return "Nothing to do - git credentials for the forge work."
  if helper and keychain == "present":
    return ("A credential for the forge host is stored but git cannot use it - it is "
            "likely stale. Delete it (`security delete-internet-password -s "
            "<forge host>`), then run `git push forge <branch>` once; git will "
            "prompt, and you enter your forge username and an access token as the "
            "password.")
  if helper:
    return ("Run `git push forge <branch>` in your terminal once; git will prompt "
            "for a username and password. Use your forge login and an access token "
            "as the password. The helper stores it and later pushes are silent.")
  return ("No git credential helper is configured. Pick a mechanism in /repos init "
          "step 7: HTTPS with a credential helper (recommended - e.g. `git config "
          "--global credential.helper osxkeychain`), or SSH, which needs the "
          "forge's SSH listener enabled and a public key registered on your forge "
          "account.")


def forge_check_git_credentials(args):
  """Report helper, keychain entry, and a real ls-remote probe; exit 0 iff ok.

  Never raises on a negative answer - a negative answer IS the result. Only a
  missing git binary or a missing manifest (no remote AND no forge_url) dies.
  """
  helper = None
  helper_source = None
  try:
    res = subprocess.run(
      ["git", "config", "--show-origin", "--get-all", "credential.helper"],
      capture_output=True, text=True)
  except FileNotFoundError:
    _die("git not found", "install git (xcode-select --install or brew install git)")
  if res.returncode == 0 and res.stdout.strip():
    # last entry wins in git's own resolution; line shape: "file:<path>\t<value>"
    source, _, value = res.stdout.strip().splitlines()[-1].partition("\t")
    helper = value or None
    helper_source = source.partition(":")[2] or source

  res = subprocess.run(["git", "remote", "get-url", args.remote],
                       capture_output=True, text=True)
  if res.returncode == 0:
    target, target_url = args.remote, res.stdout.strip()
  else:
    # remote not wired yet (open's preflight runs before it exists): probe the
    # instance URL from the manifest instead of a named remote
    target = target_url = _forge_base()

  host = target_url.split("://", 1)[-1]
  if "@" in host.split("/", 1)[0]:
    host = host.split("@", 1)[1]
  host = host.split("/", 1)[0].split(":", 1)[0]

  try:
    # NO -w: metadata only, never the secret - output stays chat-log safe
    res = subprocess.run(["security", "find-internet-password", "-s", host],
                         capture_output=True, text=True)
    keychain = "present" if res.returncode == 0 else "absent"
  except FileNotFoundError:
    keychain = "unknown"

  # GIT_TERMINAL_PROMPT=0 so a missing credential fails fast instead of hanging
  # on a prompt no agent can answer; shell form because env-per-call needs it
  # without importing os
  quoted = "'" + target.replace("'", "'\\''") + "'"
  res = subprocess.run("GIT_TERMINAL_PROMPT=0 git ls-remote " + quoted,
                       shell=True, capture_output=True, text=True)
  ls_remote = res.returncode == 0

  print(json.dumps({
    "helper": helper,
    "helper_source": helper_source,
    "keychain": keychain,
    "ls_remote": ls_remote,
    "ok": ls_remote,
    "next_action": credential_next_action(helper, keychain, ls_remote),
  }))
  sys.exit(0 if ls_remote else 1)


# ------------------------------------------------------- diff-hunk arithmetic

def line_from_hunk(diff_hunk):
  """Derive the new-file line number of the LAST line shown in a diff hunk.

  The hunk's @@ header names the new-file start; each context (' ') or added
  ('+') line advances the new-file cursor; removed ('-') lines do not. The
  comment always anchors to the hunk's final line. Returns 0 if unparseable.
  """
  lines = diff_hunk.split("\n")
  if not lines or not lines[0].startswith("@@"):
    return 0
  try:
    new_part = lines[0].split("+", 1)[1]           # "1,4 @@" or "1 @@"
    new_start = int(new_part.split(",")[0].split(" ")[0].rstrip("@"))
  except (IndexError, ValueError):
    return 0
  cursor = new_start - 1
  for ln in lines[1:]:
    if ln.startswith("@@"):                        # multi-hunk: restart cursor
      try:
        new_part = ln.split("+", 1)[1]
        cursor = int(new_part.split(",")[0].split(" ")[0].rstrip("@")) - 1
      except (IndexError, ValueError):
        return 0
    elif ln.startswith("-"):
      pass
    else:                                          # context or added line
      cursor += 1
  return cursor


def comment_line(position, diff_hunk):
  """New-file line for a read-side comment, as of the comment's OWN anchor
  commit (commit_id) - NOT the PR head; remap_line maps it to head.

  Forgejo's read-side `position` varies by provenance: a DIFF OFFSET for
  UI-created comments (probed 2026-09-01, v16.0.3: position 157/65 vs true
  lines 205/70), but API-written comments echo `new_position` back as a true
  file line (probed 2026-09-03). So hunk arithmetic is authoritative and
  `position` is only a last-resort stand-in when the hunk is unparseable.
  Write-side `new_position` accepts true file lines (probed: reposts anchored
  correctly).
  """
  line = line_from_hunk(diff_hunk or "")
  return line if line else (position or 0)


def remap_line(line, diff_text):
  """Map a file line in the diff's OLD side to the NEW side.

  Walks the @@ -a,b +c,d @@ hunk headers of a --unified=0 diff, accumulating
  the net delta of hunks strictly above `line`. A hunk that CONTAINS the line
  (a <= line < a + b) means the anchored code was rewritten: outdated.
  Pure-insertion hunks (b == 0) insert AFTER old line a, so line == a does not
  move - hence max(b, 1) in the above-test. Returns (head_line, outdated);
  outdated=True carries head_line=None.
  """
  delta = 0
  for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
                       diff_text, re.MULTILINE):
    a = int(m.group(1))
    b = 1 if m.group(2) is None else int(m.group(2))
    d = 1 if m.group(4) is None else int(m.group(4))
    if a + max(b, 1) <= line:
      delta += d - b
    elif a <= line < a + b:
      return (None, True)
    else:
      break
  return (line + delta, False)


# --------------------------------------------------------------- github side

def _gh(gh_args, input_bytes=None):
  try:
    res = subprocess.run(["gh"] + gh_args, capture_output=True,
                         input=input_bytes, check=True)
  except FileNotFoundError:
    _die("gh CLI not found", "install GitHub CLI and run: gh auth login")
  except subprocess.CalledProcessError as e:
    _die("gh " + " ".join(gh_args[:3]) + " failed",
         e.stderr.decode(errors="replace")[:500])
  return json.loads(res.stdout) if res.stdout.strip() else {}


def github_export(args):
  """Create the origin PR + ONE pending review from the comments JSON.

  Pushing the branch is the CALLER's job. --dry-run prints the payloads and
  touches nothing. The pending review is created by POSTing a review with NO
  `event` field - that is what leaves it PENDING for a human to submit.
  """
  comments = json.loads(pathlib.Path(args.comments_file).read_text())
  stale = [c["path"] for c in comments if c.get("outdated")]
  if stale:
    _die("comments file contains outdated entries",
         "anchored code was rewritten; resolve or reword on the forge: "
         + ", ".join(stale))
  description = pathlib.Path(args.body_file).read_text()
  review_comments = [{"path": c["path"], "line": c["line"],
                      "side": c.get("side", "RIGHT"), "body": c["body"]}
                     for c in comments]
  pr_payload = {"title": args.title, "head": args.branch, "base": args.base,
                "body": description}
  if args.dry_run:
    print(json.dumps({"dry_run": True, "repo": args.repo, "pr": pr_payload,
                      "pending_review_comments": review_comments}))
    return
  pr = _gh(["api", "repos/{}/pulls".format(args.repo), "--method", "POST",
            "--input", "-"], json.dumps(pr_payload).encode())
  result = {"pr_url": pr["html_url"], "pr_number": pr["number"],
            "pending_review": False}
  if review_comments:
    review = _gh(["api", "repos/{}/pulls/{}/reviews".format(
      args.repo, pr["number"]), "--method", "POST", "--input", "-"],
      json.dumps({"body": "", "comments": review_comments}).encode())
    result["pending_review"] = review.get("state") == "PENDING"
    result["review_id"] = review.get("id")
  print(json.dumps(result))


# ------------------------------------------------------------------ selftest

def selftest(_args):
  cases = [
    # (name, hunk, expected new-file line of the final hunk line)
    ("added line",
     "@@ -0,0 +1,4 @@\n+line1\n+line2", 2),
    ("context line",
     "@@ -10,6 +10,7 @@ def f():\n line10\n line11\n+inserted", 12),
    ("multi-hunk",
     "@@ -1,3 +1,3 @@\n line1\n-old\n+new\n@@ -20,2 +20,3 @@\n line20\n+line21", 21),
    ("context after add",
     "@@ -5,3 +5,4 @@\n line5\n+new6\n line7", 7),
    ("unparseable", "not a hunk", 0),
    ("empty", "", 0),
  ]
  failures = []
  for name, hunk, expected in cases:
    got = line_from_hunk(hunk)
    if got != expected:
      failures.append({"case": name, "expected": expected, "got": got})
  na_cases = [
    # (helper, keychain, ls_remote, expected substring of next_action) - the
    # full diagnosis matrix; hermetic, no git/security shell-outs
    ("osxkeychain", "present", True,  "Nothing to do"),
    ("osxkeychain", "absent",  True,  "Nothing to do"),
    ("osxkeychain", "unknown", True,  "Nothing to do"),
    (None,          "present", True,  "Nothing to do"),
    (None,          "absent",  True,  "Nothing to do"),
    (None,          "unknown", True,  "Nothing to do"),
    ("osxkeychain", "present", False, "likely stale"),
    ("osxkeychain", "absent",  False, "git will prompt"),
    ("osxkeychain", "unknown", False, "git will prompt"),
    (None,          "present", False, "No git credential helper"),
    (None,          "absent",  False, "No git credential helper"),
    (None,          "unknown", False, "No git credential helper"),
  ]
  for helper, keychain, ls_remote, expected in na_cases:
    got = credential_next_action(helper, keychain, ls_remote)
    if expected not in got:
      failures.append({
        "case": "next_action({}, {}, {})".format(helper, keychain, ls_remote),
        "expected": expected, "got": got})
  cl_cases = [
    # (name, position, diff_hunk, expected)
    ("hunk wins over position", 157, "@@ -0,0 +202,4 @@\n+a\n+b\n+c\n+d", 205),
    ("position-only fallback",  65,  "not a hunk", 65),
    ("neither",                 None, "", 0),
    ("position None, hunk ok",  None, "@@ -0,0 +1,2 @@\n+a\n+b", 2),
  ]
  for name, position, hunk, expected in cl_cases:
    got = comment_line(position, hunk)
    if got != expected:
      failures.append({"case": name, "expected": expected, "got": got})
  remap_cases = [
    # (name, line, diff_text, expected (head_line, outdated))
    ("no hunks - unchanged",        121, "",                              (121, False)),
    ("insertion above shifts",      199, "@@ -70,1 +70,2 @@\n-x\n+y\n+z", (200, False)),
    ("anchor inside hunk",          70,  "@@ -70,1 +70,2 @@\n-x\n+y\n+z", (None, True)),
    ("pure-insert at anchor line",  70,  "@@ -70,0 +71,2 @@\n+y\n+z",     (70, False)),
    ("pure-insert line below it",   71,  "@@ -70,0 +71,2 @@\n+y\n+z",     (73, False)),
    ("deletion above shifts down",  199, "@@ -100,3 +99,0 @@\n-a\n-b\n-c",(196, False)),
    ("inside deleted range",        101, "@@ -100,3 +99,0 @@\n-a\n-b\n-c",(None, True)),
    ("hunk below - stops",          50,  "@@ -70,1 +70,2 @@\n-x\n+y\n+z", (50, False)),
  ]
  for name, line, diff_text, expected in remap_cases:
    got = remap_line(line, diff_text)
    if got != expected:
      failures.append({"case": name, "expected": list(expected),
                       "got": list(got)})
  if failures:
    print(json.dumps({"selftest": "FAIL", "failures": failures}))
    sys.exit(1)
  print(json.dumps({"selftest": "OK",
                    "cases": len(cases) + len(na_cases) + len(cl_cases)
                    + len(remap_cases)}))


# ---------------------------------------------------------------------- main

def main():
  top = argparse.ArgumentParser(prog="repos_api.py")
  sub = top.add_subparsers(dest="family", required=True)

  forge = sub.add_parser("forge").add_subparsers(dest="verb", required=True)
  p = forge.add_parser("ensure-repo")
  p.add_argument("--org", required=True)
  p.add_argument("--name", required=True)
  p.set_defaults(fn=forge_ensure_repo)
  p = forge.add_parser("pr")
  p.add_argument("--repo", required=True)
  p.add_argument("--branch", required=True)
  p.add_argument("--base")
  p.add_argument("--title")
  p.add_argument("--body-file")
  p.set_defaults(fn=forge_pr)
  p = forge.add_parser("threads")
  p.add_argument("--repo", required=True)
  p.add_argument("--pr", required=True)
  p.set_defaults(fn=forge_threads)
  p = forge.add_parser("comment")
  p.add_argument("--repo", required=True)
  p.add_argument("--pr", required=True)
  p.add_argument("--path", required=True)
  p.add_argument("--line", required=True)
  p.add_argument("--body-file", required=True)
  p.set_defaults(fn=forge_comment)
  p = forge.add_parser("check-git-credentials")
  p.add_argument("--remote", default="forge")
  p.set_defaults(fn=forge_check_git_credentials)

  github = sub.add_parser("github").add_subparsers(dest="verb", required=True)
  p = github.add_parser("export")
  p.add_argument("--repo", required=True)
  p.add_argument("--branch", required=True)
  p.add_argument("--base", required=True)
  p.add_argument("--title", required=True)
  p.add_argument("--body-file", required=True)
  p.add_argument("--comments-file", required=True)
  p.add_argument("--dry-run", action="store_true")
  p.set_defaults(fn=github_export)

  p = sub.add_parser("selftest")
  p.set_defaults(fn=selftest)

  args = top.parse_args()
  args.fn(args)


if __name__ == "__main__":
  main()
