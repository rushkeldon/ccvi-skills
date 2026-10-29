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
  forge delete-comment --repo R --pr N --comment C
  forge prune       [--dry-run]
  forge check-git-credentials [--remote NAME]
  github export     --repo R --branch B --base BASE --title T --body-file F
                    --comments-file J [--dry-run]
  github export     --repo R --pr N --comments-file J [--dry-run]
  selftest
"""

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.parse
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


def _forge_soft(method, path, body=None):
  """Like _forge, but an HTTP error is returned as (False, "HTTP N ...") instead
  of exiting - prune keeps going past one failed delete and reports it."""
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
      return (True, json.loads(raw) if raw else {})
  except urllib.error.HTTPError as e:
    return (False, "HTTP {} {}".format(
      e.code, e.read().decode(errors="replace")[:200]))


def _forge_pages(path):
  """GET every page of a list endpoint. Accepts both a bare list and the
  {"data": [...]} envelope /repos/search returns."""
  out = []
  page = 1
  sep = "&" if "?" in path else "?"
  while True:
    got = _forge("GET", "{}{}limit=50&page={}".format(path, sep, page)) or []
    items = got.get("data", []) if isinstance(got, dict) else got
    out.extend(items)
    if len(items) < 50:
      return out
    page += 1


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


def review_comment_path(owner, name, pr, review_id, comment_id):
  """API path of one review comment - the DELETE target (the same endpoint the
  amend path in SKILL.md uses; probed v16.0.3 with the provisioned scopes)."""
  return "/repos/{}/{}/pulls/{}/reviews/{}/comments/{}".format(
    owner, name, pr, review_id, comment_id)


def find_review_id(review_comments, comment_id):
  """review_id holding comment_id, from [(review_id, [comment, ...]), ...];
  None when no review holds it."""
  for review_id, comments in review_comments:
    for c in comments:
      if str(c.get("id")) == str(comment_id):
        return review_id
  return None


def forge_delete_comment(args):
  """Close a thread by deleting its comment - the forge API has no resolve
  endpoint, and export skips a deleted thread exactly like a resolved one."""
  owner, name = args.repo.split("/", 1)
  reviews = _forge("GET", "/repos/{}/{}/pulls/{}/reviews".format(
    owner, name, args.pr)) or []
  review_comments = [
    (r["id"], _forge("GET", "/repos/{}/{}/pulls/{}/reviews/{}/comments".format(
      owner, name, args.pr, r["id"])) or [])
    for r in reviews]
  review_id = find_review_id(review_comments, args.comment)
  if review_id is None:
    _die("comment not found", "no review on PR {} holds comment {}".format(
      args.pr, args.comment))
  _forge("DELETE", review_comment_path(owner, name, args.pr, review_id,
                                       args.comment))
  print(json.dumps({"deleted": True, "comment_id": int(args.comment)}))


# ------------------------------------------------------------------ forge prune

PRUNE_STALE_DAYS = 14


def parse_time(stamp):
  """RFC 3339 from the forge API -> aware datetime; None when absent/bad.
  The Z swap keeps python 3.9/3.10 fromisoformat happy."""
  if not stamp:
    return None
  try:
    return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
  except ValueError:
    return None


def origin_slug(url):
  """owner/repo from an origin remote URL (scp-like or scheme://), no .git."""
  url = (url or "").strip()
  m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]+@)?[^/]+/(.+?)(?:\.git)?/?$",
               url)
  if not m:
    m = re.match(r"^(?:[^@/]+@)?[^:/]+:(.+?)(?:\.git)?/?$", url)
  return m.group(1) if m else ""


def match_origin(manifest_repos, forge_name):
  """The manifest origin URL whose repo basename equals the forge repo name
  (`open` names the forge repo after the origin's basename); None if none."""
  for origin in manifest_repos:
    if origin_slug(origin).rsplit("/", 1)[-1] == forge_name:
      return origin
  return None


def prune_action(is_base, exported, last_activity, now):
  """Classify one forge branch (with its PRs) for prune.

  exported: True / False / None (origin check failed - treated as unexported).
  last_activity: newest of the branch head commit and its PRs' updated_at, or
  None when unknown (treated as fresh - never delete on missing evidence).
  """
  if is_base:
    return "keep-base"
  if exported:
    return "delete-exported"
  if last_activity is not None and (
      now - last_activity).days >= PRUNE_STALE_DAYS:
    return "delete-stale"
  return "keep-fresh"


def _origin_has_pr(origin, branch):
  """True/False, or (None, error) when gh cannot answer - never dies."""
  slug = origin_slug(origin)
  env = os.environ.copy()
  host = remote_host(origin)
  if host:
    env["GH_HOST"] = host
  owner = slug.split("/", 1)[0]
  path = "repos/{}/pulls?state=all&head={}".format(
    slug, urllib.parse.quote("{}:{}".format(owner, branch), safe=""))
  try:
    res = subprocess.run(["gh", "api", path], capture_output=True, env=env)
  except FileNotFoundError:
    return (None, "gh CLI not found")
  if res.returncode != 0:
    return (None, res.stderr.decode(errors="replace").strip()[:200])
  try:
    return (len(json.loads(res.stdout or b"[]")) > 0, None)
  except ValueError:
    return (None, "gh returned non-JSON")


def forge_prune(args):
  """Wipe the ephemeral forge: exported branches+PRs any time, unexported ones
  once stale (PRUNE_STALE_DAYS); fresh unexported work is kept with a warning.
  Base branches are never touched. --dry-run reports and changes nothing."""
  manifest = json.loads((CONFIG_ROOT / "manifest.json").read_text())
  manifest_repos = manifest.get("repos", {})
  now = datetime.datetime.now(datetime.timezone.utc)
  report = []
  counts = {"deleted": 0, "kept": 0, "failed": 0}
  for repo in _forge_pages("/repos/search"):
    owner, name = repo["full_name"].split("/", 1)
    origin = match_origin(manifest_repos, name)
    bases = {repo.get("default_branch")}
    if origin and manifest_repos[origin].get("base"):
      bases.add(manifest_repos[origin]["base"])
    branches = {b["name"]: b for b in _forge_pages(
      "/repos/{}/{}/branches".format(owner, name))}
    prs_by_branch = {}
    for pr in _forge_pages("/repos/{}/{}/pulls?state=all".format(owner, name)):
      prs_by_branch.setdefault(pr["head"]["ref"], []).append(pr)
    items = []
    for branch in sorted(set(branches) | set(prs_by_branch)):
      prs = prs_by_branch.get(branch, [])
      stamps = [parse_time(((branches.get(branch) or {}).get("commit") or {})
                           .get("timestamp"))]
      stamps += [parse_time(p.get("updated_at")) for p in prs]
      stamps = [s for s in stamps if s is not None]
      last_activity = max(stamps) if stamps else None
      is_base = branch in bases
      exported, error = (False, None)
      if not is_base:
        if origin:
          exported, error = _origin_has_pr(origin, branch)
        else:
          error = "no manifest origin matches forge repo " + name
      action = prune_action(is_base, exported, last_activity, now)
      item = {"branch": branch, "prs": [p["number"] for p in prs],
              "exported": exported, "action": action,
              "age_days": (now - last_activity).days if last_activity else None}
      if error:
        item["origin_check"] = error
      if action == "keep-fresh":
        item["warning"] = ("unexported and under {} days old - kept; export it "
                           "or wait").format(PRUNE_STALE_DAYS)
      if action.startswith("delete") and not args.dry_run:
        failures = []
        for number in item["prs"]:
          ok, err = _forge_soft("DELETE", "/repos/{}/{}/issues/{}".format(
            owner, name, number))
          if not ok:
            failures.append("PR {}: {}".format(number, err))
        if branch in branches:
          ok, err = _forge_soft("DELETE", "/repos/{}/{}/branches/{}".format(
            owner, name, urllib.parse.quote(branch, safe="")))
          if not ok:
            failures.append("branch: " + err)
        item["done"] = not failures
        if failures:
          item["failures"] = failures
          counts["failed"] += 1
        else:
          counts["deleted"] += 1
      elif action.startswith("delete"):
        counts["deleted"] += 1
      else:
        counts["kept"] += 1
      items.append(item)
    report.append({"repo": repo["full_name"], "origin": origin, "items": items})
  print(json.dumps({"dry_run": args.dry_run, "repos": report,
                    ("would_delete" if args.dry_run else "deleted"):
                      counts["deleted"],
                    "kept": counts["kept"], "failed": counts["failed"]}))
  sys.exit(1 if counts["failed"] else 0)


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

def remote_host(url):
  """Hostname from a git remote URL - scp-like (git@host:org/repo.git),
  scheme://[user@]host[:port]/... (https, ssh), with or without .git."""
  url = (url or "").strip()
  m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]+@)?([^:/]+)", url)
  if m:
    return m.group(1)
  m = re.match(r"^(?:[^@/]+@)?([^:/]+):", url)
  if m:
    return m.group(1)
  return ""


def _gh(gh_args, input_bytes=None):
  # gh's API paths here are host-relative; the gh BINARY defaults to
  # github.com when GH_HOST is unset (a shell function deriving it is not
  # inherited by a subprocess). Derive it from the origin remote - but never
  # override a GH_HOST the caller set explicitly.
  env = os.environ.copy()
  if not env.get("GH_HOST"):
    origin = subprocess.run(["git", "remote", "get-url", "origin"],
                            capture_output=True, text=True)
    host = remote_host(origin.stdout) if origin.returncode == 0 else ""
    if host:
      env["GH_HOST"] = host
  try:
    res = subprocess.run(["gh"] + gh_args, capture_output=True,
                         input=input_bytes, check=True, env=env)
  except FileNotFoundError:
    _die("gh CLI not found", "install GitHub CLI and run: gh auth login")
  except subprocess.CalledProcessError as e:
    _die("gh " + " ".join(gh_args[:3]) + " failed",
         e.stderr.decode(errors="replace")[:500])
  return json.loads(res.stdout) if res.stdout.strip() else {}


def review_comments_from(comments):
  """Pending-review comments from the comments JSON, or (None, error).

  Replay by head_line, REQUIRED - no fallback to the as-of-anchor `line`
  (a silent fallback to the stale field is how the off-by-one shipped once).
  """
  stale = [c["path"] for c in comments if c.get("outdated")]
  if stale:
    return (None, "comments file contains outdated entries - anchored code was "
            "rewritten; resolve or reword on the forge: " + ", ".join(stale))
  out = []
  for c in comments:
    if "head_line" not in c or c["head_line"] is None:
      return (None, "comments file entry has no head_line: " + c.get("path", "?")
              + " - re-run forge threads and rebuild the comments file")
    out.append({"path": c["path"], "line": c["head_line"],
                "side": c.get("side", "RIGHT"), "body": c["body"]})
  return (out, None)


def export_plan(repo, review_comments, origin_pr=None, branch=None, base=None,
                title=None, description=None):
  """What github export will do, as data (the --dry-run output). With
  origin_pr the review attaches to that existing origin PR and no PR is
  created; otherwise a PR is created from branch/base/title/description."""
  plan = {"repo": repo, "pending_review_comments": review_comments}
  if origin_pr is not None:
    plan["target"] = {"existing_pr": int(origin_pr)}
  else:
    plan["target"] = {"create_pr": {"title": title, "head": branch,
                                    "base": base, "body": description}}
  return plan


def github_export(args):
  """ONE pending review from the comments JSON, on a new origin PR or (with
  --pr) on an existing one.

  Pushing the branch is the CALLER's job. --dry-run prints the payloads and
  touches nothing. The pending review is created by POSTing a review with NO
  `event` field - that is what leaves it PENDING for a human to submit.
  """
  if args.pr is None:
    missing = [flag for flag, val in (("--branch", args.branch),
                                      ("--base", args.base),
                                      ("--title", args.title),
                                      ("--body-file", args.body_file))
               if not val]
    if missing:
      _die("missing arguments", ", ".join(missing)
           + " required unless --pr names an existing origin PR")
  comments = json.loads(pathlib.Path(args.comments_file).read_text())
  review_comments, error = review_comments_from(comments)
  if error:
    _die("bad comments file", error)
  description = (pathlib.Path(args.body_file).read_text()
                 if args.pr is None else None)
  plan = export_plan(args.repo, review_comments, args.pr, args.branch,
                     args.base, args.title, description)
  if args.dry_run:
    plan["dry_run"] = True
    print(json.dumps(plan))
    return
  if args.pr is not None:
    pr = _gh(["api", "repos/{}/pulls/{}".format(args.repo, int(args.pr))])
  else:
    pr = _gh(["api", "repos/{}/pulls".format(args.repo), "--method", "POST",
              "--input", "-"],
             json.dumps(plan["target"]["create_pr"]).encode())
  result = {"pr_url": pr["html_url"], "pr_number": pr["number"],
            "existing_pr": args.pr is not None, "pending_review": False}
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
  rh_cases = [
    # (name, remote url, expected host)
    ("scp-like",       "git@github.twdcgrid.net:org/repo.git", "github.twdcgrid.net"),
    ("https",          "https://github.twdcgrid.net/org/repo", "github.twdcgrid.net"),
    ("ssh with port",  "ssh://git@host:22/org/repo.git",       "host"),
    ("https .git",     "https://github.com/org/repo.git",      "github.com"),
    ("empty",          "",                                     ""),
  ]
  for name, url, expected in rh_cases:
    got = remote_host(url)
    if got != expected:
      failures.append({"case": name, "expected": expected, "got": got})
  rc_path = review_comment_path("personal", "spike", 3, 11, 42)
  if rc_path != "/repos/personal/spike/pulls/3/reviews/11/comments/42":
    failures.append({"case": "review_comment_path", "got": rc_path})
  rc_reviews = [(10, [{"id": 40}, {"id": 41}]), (11, [{"id": 42}])]
  fr_cases = [
    # (name, comment_id, expected review_id)
    ("second review",   42,   11),
    ("first review",    "41", 10),
    ("absent",          99,   None),
  ]
  for name, comment_id, expected in fr_cases:
    got = find_review_id(rc_reviews, comment_id)
    if got != expected:
      failures.append({"case": "find_review_id " + name, "expected": expected,
                       "got": got})
  os_cases = [
    # (name, origin url, expected owner/repo)
    ("scp-like",  "git@github.twdcgrid.net:disneyplus-clients/android-dmgz.git",
                  "disneyplus-clients/android-dmgz"),
    ("https",     "https://github.com/rushkeldon/ccvi-skills", "rushkeldon/ccvi-skills"),
    ("https .git", "https://github.com/o/r.git",              "o/r"),
    ("ssh port",  "ssh://git@host:22/o/r.git",                "o/r"),
    ("empty",     "",                                         ""),
  ]
  for name, url, expected in os_cases:
    got = origin_slug(url)
    if got != expected:
      failures.append({"case": "origin_slug " + name, "expected": expected,
                       "got": got})
  mo_repos = {"git@github.twdcgrid.net:disneyplus-clients/android-dmgz.git": {},
              "https://github.com/o/spike": {}}
  for forge_name, expected in (("android-dmgz", "git@github.twdcgrid.net:"
                                "disneyplus-clients/android-dmgz.git"),
                               ("spike", "https://github.com/o/spike"),
                               ("android", None)):
    got = match_origin(mo_repos, forge_name)
    if got != expected:
      failures.append({"case": "match_origin " + forge_name,
                       "expected": expected, "got": got})
  now = datetime.datetime(2026, 10, 29, 12, 0, tzinfo=datetime.timezone.utc)
  pa_cases = [
    # (name, is_base, exported, last_activity, expected) - fixed clock
    ("base never deleted",    True,  True,  "2026-01-01T00:00:00Z", "keep-base"),
    ("exported, fresh",       False, True,  "2026-10-29T11:00:00Z", "delete-exported"),
    ("unexported, fresh",     False, False, "2026-10-20T12:00:00Z", "keep-fresh"),
    ("unexported, 13 days",   False, False, "2026-10-16T12:00:01Z", "keep-fresh"),
    ("unexported, 14 days",   False, False, "2026-10-15T12:00:00Z", "delete-stale"),
    ("check failed, stale",   False, None,  "2026-09-01T00:00:00-07:00", "delete-stale"),
    ("check failed, fresh",   False, None,  "2026-10-28T00:00:00Z", "keep-fresh"),
    ("no timestamp",          False, False, None,                   "keep-fresh"),
  ]
  for name, is_base, exported, stamp, expected in pa_cases:
    got = prune_action(is_base, exported, parse_time(stamp), now)
    if got != expected:
      failures.append({"case": "prune_action " + name, "expected": expected,
                       "got": got})
  thread = {"path": "a.py", "line": 3, "head_line": 5, "outdated": False,
            "body": "fix"}
  rcf, err = review_comments_from([thread])
  if err or rcf != [{"path": "a.py", "line": 5, "side": "RIGHT", "body": "fix"}]:
    failures.append({"case": "review_comments_from head_line", "got": [rcf, err]})
  for name, bad in (("no head_line", dict(thread, head_line=None)),
                    ("outdated", dict(thread, outdated=True))):
    rcf, err = review_comments_from([bad])
    if rcf is not None or not err:
      failures.append({"case": "review_comments_from refuses " + name,
                       "got": [rcf, err]})
  existing = export_plan("o/r", [{"path": "a.py"}], origin_pr="17")
  if existing.get("target") != {"existing_pr": 17}:
    failures.append({"case": "export_plan existing PR", "got": existing})
  created = export_plan("o/r", [], None, "feat", "main", "T", "D")
  if created.get("target") != {"create_pr": {"title": "T", "head": "feat",
                                             "base": "main", "body": "D"}}:
    failures.append({"case": "export_plan create PR", "got": created})
  if failures:
    print(json.dumps({"selftest": "FAIL", "failures": failures}))
    sys.exit(1)
  print(json.dumps({"selftest": "OK",
                    "cases": len(cases) + len(na_cases) + len(cl_cases)
                    + len(remap_cases) + len(rh_cases) + 1 + len(fr_cases)
                    + len(os_cases) + 3 + len(pa_cases) + 3 + 2}))


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
  p = forge.add_parser("delete-comment")
  p.add_argument("--repo", required=True)
  p.add_argument("--pr", required=True)
  p.add_argument("--comment", required=True)
  p.set_defaults(fn=forge_delete_comment)
  p = forge.add_parser("prune")
  p.add_argument("--dry-run", action="store_true")
  p.set_defaults(fn=forge_prune)
  p = forge.add_parser("check-git-credentials")
  p.add_argument("--remote", default="forge")
  p.set_defaults(fn=forge_check_git_credentials)

  github = sub.add_parser("github").add_subparsers(dest="verb", required=True)
  p = github.add_parser("export")
  p.add_argument("--repo", required=True)
  p.add_argument("--pr", help="existing origin PR: attach the review, create none")
  p.add_argument("--branch")
  p.add_argument("--base")
  p.add_argument("--title")
  p.add_argument("--body-file")
  p.add_argument("--comments-file", required=True)
  p.add_argument("--dry-run", action="store_true")
  p.set_defaults(fn=github_export)

  p = sub.add_parser("selftest")
  p.set_defaults(fn=selftest)

  args = top.parse_args()
  args.fn(args)


if __name__ == "__main__":
  main()
