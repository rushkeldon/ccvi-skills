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
  github export     --repo R --branch B --base BASE --title T --body-file F
                    --comments-file J [--dry-run]
  selftest
"""

import argparse
import json
import pathlib
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


def forge_threads(args):
  """Reviews + inline comments; each comment carries path, line info, body, and
  resolved (Forgejo: resolver != null - probed 2026-08-31, v16.0.3)."""
  owner, name = args.repo.split("/", 1)
  reviews = _forge("GET", "/repos/{}/{}/pulls/{}/reviews".format(
    owner, name, args.pr)) or []
  out = []
  for review in reviews:
    comments = _forge("GET", "/repos/{}/{}/pulls/{}/reviews/{}/comments".format(
      owner, name, args.pr, review["id"])) or []
    for c in comments:
      line = c.get("position") or 0
      if not line:
        line = line_from_hunk(c.get("diff_hunk", ""))
      out.append({
        "review_id": review["id"],
        "comment_id": c["id"],
        "path": c["path"],
        "line": line,
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
  if failures:
    print(json.dumps({"selftest": "FAIL", "failures": failures}))
    sys.exit(1)
  print(json.dumps({"selftest": "OK", "cases": len(cases)}))


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
