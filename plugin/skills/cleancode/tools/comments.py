#!/usr/bin/env python3
"""
comments.py - the deterministic half of /cleancode's comment pipeline.

Modes:
  census  <files...>            JSON per-file comment stats (count, byte mass, mass %,
                                TODO/FIXME and commented-out-code counts, protected
                                counts by category), plus a skip list for files
                                outside the supported-language table.
  harvest <escrowDir> <files...>
                                Write one escrow markdown file per source file (every
                                comment verbatim, under its nearest enclosing symbol)
                                plus MANIFEST.md (run stamp, git HEAD sha, per-file
                                content sha256).
  strip   <escrowDir> <files...>
                                Delete all non-protected, non-TODO comments. REFUSES
                                (exit 3) unless every target file's sha256 matches the
                                escrow manifest - harvest is the required, recent,
                                explicit predecessor.

Options:
  --keep-doc-comments   treat toolchain doc-comments (///, //!, /** */) as protected
                        (the per-project generated-API-docs flag; default off).

Exit codes: 0 ok · 2 usage · 3 freshness gate failed · 1 other error.

Stdlib only. Python 3.9+. String- and template-literal-aware tokenization per
language, so a comment marker inside a string is never a comment.
"""

import io
import os
import re
import sys
import json
import hashlib
import datetime
import subprocess

# ---------------------------------------------------------------------------------
# The supported-language table (v1). A file outside it is SKIPPED loudly, never
# half-processed.
# ---------------------------------------------------------------------------------

LANG_BY_EXT = {
  ".ts": "js", ".tsx": "js", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
  ".rs": "rust",
  ".py": "python",
  ".kt": "kotlin", ".kts": "kotlin", ".java": "java",
  ".css": "css", ".less": "less",
  ".swift": "swift",
}


def lang_for(path):
  return LANG_BY_EXT.get(os.path.splitext(path)[1].lower())


# ---------------------------------------------------------------------------------
# Tokenizer. scan(text, lang) -> list of comment dicts:
#   {start, end, rstart, rend, line, kind, text}
# start/end bound the comment itself; rstart/rend bound the REMOVAL span (comment
# plus the whitespace/newline that goes with it), chosen so that deleting every
# [rstart, rend) and re-inserting the removed bytes reconstructs the file exactly.
# ---------------------------------------------------------------------------------

_JS_REGEX_PRECEDERS = set("=([{,;:!&|?+-*%~^<>")
_JS_REGEX_KEYWORDS = {"return", "case", "typeof", "in", "of", "new", "delete",
                      "void", "instanceof", "do", "else", "yield", "await"}


def _consume_simple_string(text, i, quote, allow_escape=True):
  """Past the opening quote at i; returns index just past the closing quote."""
  i += len(quote)
  n = len(text)
  while i < n:
    if allow_escape and text[i] == "\\":
      i += 2
      continue
    if text.startswith(quote, i):
      return i + len(quote)
    i += 1
  return n


def _consume_js_template(text, i):
  """Backtick template literal; recurses into ${ } interpolations."""
  i += 1
  n = len(text)
  while i < n:
    c = text[i]
    if c == "\\":
      i += 2
      continue
    if c == "`":
      return i + 1
    if text.startswith("${", i):
      i += 2
      depth = 1
      while i < n and depth:
        c2 = text[i]
        if c2 == "\\":
          i += 2
          continue
        if c2 in "'\"":
          i = _consume_simple_string(text, i, c2)
          continue
        if c2 == "`":
          i = _consume_js_template(text, i)
          continue
        if c2 == "{":
          depth += 1
        elif c2 == "}":
          depth -= 1
        i += 1
      continue
    i += 1
  return n


def _consume_js_regex(text, i):
  """Past the opening / of a regex literal; handles [classes] and escapes."""
  i += 1
  n = len(text)
  in_class = False
  while i < n:
    c = text[i]
    if c == "\\":
      i += 2
      continue
    if c == "[":
      in_class = True
    elif c == "]":
      in_class = False
    elif c == "/" and not in_class:
      i += 1
      while i < n and text[i].isalpha():  # flags
        i += 1
      return i
    elif c == "\n":
      return i  # not a regex after all; bail at line end
    i += 1
  return n


def _js_slash_is_regex(text, i):
  """Division-vs-regex heuristic: look back at the last significant token."""
  j = i - 1
  while j >= 0 and text[j] in " \t":
    j -= 1
  if j < 0 or text[j] in _JS_REGEX_PRECEDERS or text[j] == "\n":
    return True
  k = j
  while k >= 0 and (text[k].isalnum() or text[k] == "_"):
    k -= 1
  word = text[k + 1:j + 1]
  return word in _JS_REGEX_KEYWORDS


def _consume_python_string(text, i):
  """At a quote or a string prefix; returns end index, or None if not a string."""
  m = re.match(r"[rRbBuUfF]{0,3}('''|\"\"\"|'|\")", text[i:i + 8])
  if not m:
    return None
  quote = m.group(1)
  raw = "r" in m.group(0).lower()
  j = i + m.end() - len(quote)
  return _consume_simple_string(text, j, quote, allow_escape=not raw)


def _consume_rust_raw_string(text, i):
  """r"..." / r#"..."# / br#"..."#; returns end index or None."""
  m = re.match(r'(?:b?r)(#*)"', text[i:i + 12])
  if not m:
    return None
  closer = '"' + m.group(1)
  j = i + m.end()
  k = text.find(closer, j)
  return len(text) if k < 0 else k + len(closer)


def _consume_char_literal(text, i):
  """Rust/Kotlin/Java 'c' or '\\n'; returns end index or None (rust lifetime)."""
  m = re.match(r"'(?:\\.|[^'\\\n])'", text[i:i + 8])
  return i + m.end() if m else None


def _consume_swift_raw_string(text, i):
  """Swift raw strings: #"..."# and their triple-quoted forms; end index or None."""
  m = re.match(r'(#+)"', text[i:i + 8])
  if not m:
    return None
  closer = '"' + m.group(1)
  j = i + m.end()
  k = text.find(closer, j)
  return len(text) if k < 0 else k + len(closer)


def _consume_block_comment(text, i, opener, closer, nested):
  j = i + len(opener)
  n = len(text)
  depth = 1
  while j < n:
    if nested and text.startswith(opener, j):
      depth += 1
      j += len(opener)
      continue
    if text.startswith(closer, j):
      depth -= 1
      j += len(closer)
      if depth == 0:
        return j
      continue
    j += 1
  return n


def scan(text, lang):
  """Tokenize; return comments with removal spans, in file order."""
  comments = []
  i = 0
  n = len(text)
  line = 1

  def add(start, end, kind):
    comments.append({"start": start, "end": end, "kind": kind,
                     "line": text.count("\n", 0, start) + 1,
                     "text": text[start:end]})

  while i < n:
    c = text[i]
    if c == "\n":
      line += 1
      i += 1
      continue

    if lang == "python":
      if c in "rRbBuUfF'\"":
        end = _consume_python_string(text, i)
        if end is not None and end > i:
          i = end
          continue
        if c not in "'\"":
          i += 1
          continue
      if c == "#":
        j = text.find("\n", i)
        j = n if j < 0 else j
        add(i, j, "line")
        i = j
        continue
      i += 1
      continue

    if lang == "js":
      if c in "'\"":
        i = _consume_simple_string(text, i, c)
        continue
      if c == "`":
        i = _consume_js_template(text, i)
        continue
      if text.startswith("//", i):
        j = text.find("\n", i)
        j = n if j < 0 else j
        add(i, j, "line")
        i = j
        continue
      if text.startswith("/*", i):
        j = _consume_block_comment(text, i, "/*", "*/", nested=False)
        add(i, j, "block")
        i = j
        continue
      if c == "/" and _js_slash_is_regex(text, i):
        i = _consume_js_regex(text, i)
        continue
      i += 1
      continue

    if lang == "rust":
      end = _consume_rust_raw_string(text, i) if c in "rb" else None
      if end:
        i = end
        continue
      if c == '"':
        i = _consume_simple_string(text, i, '"')
        continue
      if c == "'":
        end = _consume_char_literal(text, i)
        i = end if end else i + 1  # lifetime or lone quote: not a string
        continue
      if text.startswith("//", i):
        j = text.find("\n", i)
        j = n if j < 0 else j
        add(i, j, "line")
        i = j
        continue
      if text.startswith("/*", i):
        j = _consume_block_comment(text, i, "/*", "*/", nested=True)
        add(i, j, "block")
        i = j
        continue
      i += 1
      continue

    if lang in ("kotlin", "java"):
      if lang == "kotlin" and text.startswith('"""', i):
        i = _consume_simple_string(text, i, '"""', allow_escape=False)
        continue
      if c == '"':
        i = _consume_simple_string(text, i, '"')
        continue
      if c == "'":
        end = _consume_char_literal(text, i)
        i = end if end else i + 1
        continue
      if text.startswith("//", i):
        j = text.find("\n", i)
        j = n if j < 0 else j
        add(i, j, "line")
        i = j
        continue
      if text.startswith("/*", i):
        j = _consume_block_comment(text, i, "/*", "*/", nested=(lang == "kotlin"))
        add(i, j, "block")
        i = j
        continue
      i += 1
      continue

    if lang in ("css", "less"):
      if c in "'\"":
        i = _consume_simple_string(text, i, c)
        continue
      if lang == "less" and text.startswith("//", i):
        j = text.find("\n", i)
        j = n if j < 0 else j
        add(i, j, "line")
        i = j
        continue
      if text.startswith("/*", i):
        j = _consume_block_comment(text, i, "/*", "*/", nested=False)
        add(i, j, "block")
        i = j
        continue
      i += 1
      continue

    if lang == "swift":
      if c == "#":
        end = _consume_swift_raw_string(text, i)
        if end:
          i = end
          continue
      if text.startswith('"""', i):
        i = _consume_simple_string(text, i, '"""')
        continue
      if c == '"':
        i = _consume_simple_string(text, i, '"')
        continue
      if text.startswith("//", i):
        j = text.find("\n", i)
        j = n if j < 0 else j
        add(i, j, "line")
        i = j
        continue
      if text.startswith("/*", i):
        j = _consume_block_comment(text, i, "/*", "*/", nested=True)
        add(i, j, "block")
        i = j
        continue
      i += 1
      continue

    raise ValueError("unknown language: " + lang)

  for com in comments:
    _removal_span(text, com)
  return comments


def _removal_span(text, com):
  """Widen [start, end) to the bytes strip deletes: a comment alone on its
  line(s) takes the whole line(s) including the trailing newline; a comment
  sharing a line with code takes its leading whitespace run only."""
  start, end = com["start"], com["end"]
  ls = text.rfind("\n", 0, start) + 1
  before = text[ls:start]
  after_end = end
  le = text.find("\n", end)
  le = len(text) if le < 0 else le
  after = text[end:le]
  if before.strip() == "" and after.strip() == "":
    com["rstart"] = ls
    com["rend"] = le + 1 if le < len(text) else le
  else:
    rs = start
    while rs > ls and text[rs - 1] in " \t":
      rs -= 1
    com["rstart"] = rs
    com["rend"] = end


# ---------------------------------------------------------------------------------
# Classification: shebang / pragma / navigation / license / doc / todo / normal.
# The protected class never strips; TODO/FIXME stay in place and are flagged.
# ---------------------------------------------------------------------------------

_PRAGMA_RE = re.compile(
  r"(eslint-(?:disable|enable)|@ts-(?:ignore|expect-error|nocheck|check)|"
  r"\bnoqa\b|\btype:\s*ignore\b|^#\s*type:|\bmypy:|\bpylint:|\bruff:|"
  r"\bfmt:\s*(?:off|on)\b|@formatter:(?:off|on)|prettier-ignore|biome-ignore|"
  r"istanbul ignore|coverage:\s*ignore|clippy::|\ballow\(|swiftlint:(?:disable|enable)|"
  r"@Suppress|\bnolint\b)", re.I | re.M)

_NAV_RE = re.compile(
  r"(^\s*#?\s*(?:region\b|endregion\b|pragma\s+(?:region|endregion))|"
  r"\bMARK:|<\/?editor-fold|"
  r"^\s*(?:/\*+|//+|#+)?\s*[-=]{3,}[^\n]*?[-=]{3,}\s*(?:\*+/)?\s*$)", re.I | re.M)

_LICENSE_RE = re.compile(
  r"(copyright|\(c\)\s*\d{4}|license|SPDX-License-Identifier|all rights reserved)",
  re.I)

_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK)\b")

_DOC_PREFIXES = ("///", "//!", "/**")

# Commented-out-code heuristic: a comment whose body lines look like code. This is
# a "needs human eyes" counter, not a strip decision.
_CODEISH_RE = re.compile(
  r"(;\s*$|[{}]\s*$|^\s*(?:if|for|while|return|import|from|def|class|function|fn|"
  r"let|const|var|pub|fun|val|print|console\.)\b|^\s*[\w.\[\]$]+\s*[-+*/]?=[^=])")


def _body(comment_text, kind):
  if kind == "line":
    return re.sub(r"^(//+!?|#+)", "", comment_text).strip()
  return re.sub(r"^/\*+|\*+/$", "", comment_text).strip()


def classify(com, filetext, keep_doc_comments=False):
  t = com["text"]
  if com["start"] == 0 and t.startswith("#!"):
    return "shebang"
  if _PRAGMA_RE.search(t):
    return "pragma"
  if _NAV_RE.search(t):
    return "navigation"
  if _LICENSE_RE.search(t):
    return "license"
  if keep_doc_comments and t.startswith(_DOC_PREFIXES):
    return "doc"
  if _TODO_RE.search(t):
    return "todo"
  return "normal"


def looks_like_code(com):
  lines = [l for l in _body(com["text"], com["kind"]).split("\n")
           if l.strip() and not l.strip().startswith("*")]
  if not lines:
    return False
  hits = sum(1 for l in lines if _CODEISH_RE.search(l))
  if len(lines) == 1:
    return bool(re.search(r"[;{}]\s*$", lines[0])) and hits == 1
  return hits >= 2 and hits / len(lines) >= 0.6


PROTECTED = {"shebang", "pragma", "navigation", "license", "doc"}


# ---------------------------------------------------------------------------------
# Nearest enclosing symbol (escrow headings; informational only).
# ---------------------------------------------------------------------------------

_SYMBOL_RES = {
  "python": [re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+(\w+)")],
  "js": [re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)"),
         re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)"),
         re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*="),
         re.compile(r"^\s*(?:public|private|protected|static|async|\s)*(\w+)\s*\([^)]*\)\s*\{")],
  "rust": [re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:fn|struct|enum|trait|mod)\s+(\w+)"),
           re.compile(r"^\s*impl(?:<[^>]*>)?\s+(?:\w+\s+for\s+)?(\w+)")],
  "kotlin": [re.compile(r"^\s*(?:\w+\s+)*(?:fun|class|interface|object)\s+(\w+)")],
  "java": [re.compile(r"^\s*(?:\w+\s+)*(?:class|interface|enum)\s+(\w+)"),
           re.compile(r"^\s*(?:public|private|protected|static|final|\s)+[\w<>\[\]]+\s+(\w+)\s*\(")],
  "swift": [re.compile(r"^\s*(?:\w+\s+)*(?:func|class|struct|enum|extension|protocol)\s+(\w+)")],
  "css": [re.compile(r"^([^{}/@\s][^{}]*?)\s*\{\s*$")],
  "less": [re.compile(r"^([^{}/@\s][^{}]*?)\s*\{\s*$")],
}


def enclosing_symbol(text, lang, comment_start):
  lines = text[:comment_start].split("\n")
  for raw in reversed(lines):
    for rx in _SYMBOL_RES.get(lang, []):
      m = rx.match(raw)
      if m:
        return m.group(1).strip()
  return "(file level)"


# ---------------------------------------------------------------------------------
# Shared file plumbing.
# ---------------------------------------------------------------------------------

def sha256_file(path):
  h = hashlib.sha256()
  with open(path, "rb") as fh:
    h.update(fh.read())
  return h.hexdigest()


def fold_path(path):
  norm = os.path.normpath(path).replace(os.sep, "/").lstrip("./")
  return norm.replace("/", "__")


def git_head():
  try:
    out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                         text=True, timeout=10)
    return out.stdout.strip() if out.returncode == 0 else "(not a git repo)"
  except Exception:
    return "(not a git repo)"


def utc_stamp():
  return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def analyze(path, keep_doc_comments=False):
  """Read + scan + classify one supported file. Returns the per-file record."""
  with open(path, encoding="utf-8") as fh:
    text = fh.read()
  lang = lang_for(path)
  comments = scan(text, lang)
  for com in comments:
    com["class"] = classify(com, text, keep_doc_comments)
    com["symbol"] = enclosing_symbol(text, lang, com["start"])
  return {"path": path, "lang": lang, "text": text, "comments": comments}


def split_targets(files):
  """(supported, skipped) partition of the argument list."""
  supported, skipped = [], []
  for f in files:
    (supported if lang_for(f) else skipped).append(f)
  return supported, skipped


# ---------------------------------------------------------------------------------
# census
# ---------------------------------------------------------------------------------

def do_census(files, keep_doc_comments=False):
  supported, skipped = split_targets(files)
  out = {"files": [], "skipped": skipped}
  for path in supported:
    rec = analyze(path, keep_doc_comments)
    text, comments = rec["text"], rec["comments"]
    cbytes = sum(c["end"] - c["start"] for c in comments)
    protected_counts = {}
    for c in comments:
      if c["class"] in PROTECTED:
        protected_counts[c["class"]] = protected_counts.get(c["class"], 0) + 1
    out["files"].append({
      "path": path,
      "lang": rec["lang"],
      "totalBytes": len(text.encode("utf-8")),
      "commentCount": len(comments),
      "commentBytes": len(text[0:0].join(c["text"] for c in comments).encode("utf-8")),
      "massPct": round(100.0 * cbytes / max(1, len(text)), 1),
      "todoCount": sum(1 for c in comments if c["class"] == "todo"),
      "commentedOutCodeCount": sum(1 for c in comments
                                   if c["class"] == "normal" and looks_like_code(c)),
      "protected": protected_counts,
    })
  out["files"].sort(key=lambda f: -f["massPct"])
  print(json.dumps(out, indent=2))
  return 0


# ---------------------------------------------------------------------------------
# harvest
# ---------------------------------------------------------------------------------

def _fence_for(text):
  longest = max((len(m.group(0)) for m in re.finditer(r"`+", text)), default=0)
  return "`" * max(3, longest + 1)


def do_harvest(escrow_dir, files, keep_doc_comments=False):
  supported, skipped = split_targets(files)
  os.makedirs(escrow_dir, exist_ok=True)
  manifest_lines = [
    "# Escrow manifest", "",
    "- harvested: " + utc_stamp(),
    "- head: " + git_head(),
    "- escrow-format: 1", "",
    "## Files", "",
  ]
  total = 0
  for path in supported:
    rec = analyze(path, keep_doc_comments)
    comments = rec["comments"]
    total += len(comments)
    escrow_name = fold_path(path) + ".md"
    buf = io.StringIO()
    buf.write("# Escrow: {}\n\n- source: {}\n- sha256: {}\n- comments: {}\n".format(
      path, path, sha256_file(path), len(comments)))
    for c in comments:
      fence = _fence_for(c["text"])
      buf.write("\n## {} (line {})\n\n- span: {}-{}\n- removal-span: {}-{}\n"
                "- kind: {}\n- class: {}\n\n{}text\n{}\n{}\n".format(
                  c["symbol"], c["line"], c["start"], c["end"],
                  c["rstart"], c["rend"], c["kind"], c["class"],
                  fence, c["text"], fence))
    with open(os.path.join(escrow_dir, escrow_name), "w", encoding="utf-8") as fh:
      fh.write(buf.getvalue())
    manifest_lines.append("- `{}` sha256 `{}` escrow `{}`".format(
      path, sha256_file(path), escrow_name))
  with open(os.path.join(escrow_dir, "MANIFEST.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(manifest_lines) + "\n")
  print("harvested {} comment(s) from {} file(s) into {}".format(
    total, len(supported), escrow_dir))
  for s in skipped:
    print("SKIP (unsupported language): " + s)
  return 0


# ---------------------------------------------------------------------------------
# strip
# ---------------------------------------------------------------------------------

_MANIFEST_LINE_RE = re.compile(r"^- `(.+?)` sha256 `([0-9a-f]{64})` escrow `(.+?)`$")


def read_manifest(escrow_dir):
  path = os.path.join(escrow_dir, "MANIFEST.md")
  if not os.path.isfile(path):
    return None
  entries = {}
  with open(path, encoding="utf-8") as fh:
    for line in fh:
      m = _MANIFEST_LINE_RE.match(line.strip())
      if m:
        entries[m.group(1)] = m.group(2)
  return entries


def strip_text(text, comments):
  """Delete every 'normal' comment's removal span; returns (stripped, removed)."""
  removed = [c for c in comments if c["class"] == "normal"]
  out = []
  prev = 0
  for c in removed:
    out.append(text[prev:c["rstart"]])
    prev = c["rend"]
  out.append(text[prev:])
  return "".join(out), removed


def do_strip(escrow_dir, files, keep_doc_comments=False):
  supported, skipped = split_targets(files)
  manifest = read_manifest(escrow_dir)
  if manifest is None:
    print("strip REFUSED: no escrow manifest at {} - run harvest first".format(
      os.path.join(escrow_dir, "MANIFEST.md")), file=sys.stderr)
    return 3
  stale = []
  for path in supported:
    want = manifest.get(path)
    if want is None:
      stale.append((path, "not in escrow manifest"))
    elif sha256_file(path) != want:
      stale.append((path, "changed since harvest (hash mismatch)"))
  if stale:
    print("strip REFUSED: escrow is not fresh -", file=sys.stderr)
    for path, why in stale:
      print("  - {}: {}".format(path, why), file=sys.stderr)
    print("re-run harvest, then strip.", file=sys.stderr)
    return 3
  for path in supported:
    rec = analyze(path, keep_doc_comments)
    stripped, removed = strip_text(rec["text"], rec["comments"])
    with open(path, "w", encoding="utf-8") as fh:
      fh.write(stripped)
    kept = {}
    for c in rec["comments"]:
      if c["class"] != "normal":
        kept[c["class"]] = kept.get(c["class"], 0) + 1
    todos = [c for c in rec["comments"] if c["class"] == "todo"]
    print("{}: removed {}, kept {}".format(
      path, len(removed),
      ", ".join("{} {}".format(v, k) for k, v in sorted(kept.items())) or "0"))
    for t in todos:
      print("  TODO/FIXME left in place (line {}): {}".format(
        t["line"], _body(t["text"], t["kind"])[:100]))
  for s in skipped:
    print("SKIP (unsupported language): " + s)
  return 0


# ---------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------

def main(argv):
  args = [a for a in argv if a != "--keep-doc-comments"]
  keep_doc = "--keep-doc-comments" in argv
  if len(args) < 2:
    print(__doc__.strip(), file=sys.stderr)
    return 2
  mode = args[0]
  try:
    if mode == "census":
      return do_census(args[1:], keep_doc)
    if mode == "harvest":
      if len(args) < 3:
        print("usage: comments.py harvest <escrowDir> <files...>", file=sys.stderr)
        return 2
      return do_harvest(args[1], args[2:], keep_doc)
    if mode == "strip":
      if len(args) < 3:
        print("usage: comments.py strip <escrowDir> <files...>", file=sys.stderr)
        return 2
      return do_strip(args[1], args[2:], keep_doc)
  except FileNotFoundError as e:
    print("error: " + str(e), file=sys.stderr)
    return 1
  print("unknown mode: " + mode, file=sys.stderr)
  return 2


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
