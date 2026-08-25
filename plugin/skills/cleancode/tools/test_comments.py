#!/usr/bin/env python3
"""Self-tests for comments.py: per-language fixtures including string traps and
the protected class, removal-span shape, and the round-trip guarantee
(strip + re-paste of the removed bytes reconstructs the original byte-for-byte).

Run: python3 test_comments.py   (exit 0 = all green)
"""

import os
import sys
import shutil
import tempfile
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import comments  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
  if cond:
    print("ok   " + name)
  else:
    FAILURES.append(name)
    print("FAIL " + name + (" - " + detail if detail else ""))


def texts(coms):
  return [c["text"] for c in coms]


# ---------------------------------------------------------------------------------
# Fixtures. Each: (name, lang, source, expected list of comment texts)
# ---------------------------------------------------------------------------------

JS_FIXTURE = (
  "js-traps", "js",
  'const url = "https://x.test/a";  // real comment\n'
  "const tpl = `//not ${'/*nope*/'} a ${a + `${b}`} comment`;\n"
  "const re = /https:\\/\\//g;\n"
  "const s = 'it\\'s // fine';\n"
  "/* block\n   comment */\n"
  "let x = 1 / 2 / 3;\n",
  ["// real comment", "/* block\n   comment */"],
)

PY_FIXTURE = (
  "py-traps", "python",
  "s = 'not # a comment'\n"
  'f = f"still {x} # not"\n'
  't = """triple # not\nmulti"""\n'
  "r = r'raw \\# not'\n"
  "x = 1  # real comment\n"
  "# another\n",
  ["# real comment", "# another"],
)

RUST_FIXTURE = (
  "rust-traps", "rust",
  'let s = r#"// not a comment"#;\n'
  "fn f<'a>(x: &'a str) -> &'a str { x }\n"
  "let c = '\\n';\n"
  "let d = \"// nope\";\n"
  "/* outer /* nested */ still outer */\n"
  "// real\n",
  ["/* outer /* nested */ still outer */", "// real"],
)

KOTLIN_FIXTURE = (
  "kotlin-traps", "kotlin",
  'val raw = """// not ${x} a comment"""\n'
  "val c = 'q'\n"
  "/* outer /* nested */ still outer */\n"
  "// real\n",
  ["/* outer /* nested */ still outer */", "// real"],
)

JAVA_FIXTURE = (
  "java-nonnested", "java",
  'String s = "// nope";\n'
  "/* a /* b */\n"
  "int x = 1;\n",
  ["/* a /* b */"],
)

CSS_FIXTURE = (
  "css", "css",
  '.a { content: "/* not */"; }\n'
  "/* real */\n",
  ["/* real */"],
)

LESS_FIXTURE = (
  "less", "less",
  '@u: "https://x/y"; // real\n'
  "/* also real */\n",
  ["// real", "/* also real */"],
)

SWIFT_FIXTURE = (
  "swift-traps", "swift",
  'let raw = #"// not a comment"#\n'
  'let m = """\n// not either\n"""\n'
  "/* outer /* nested */ still outer */\n"
  "// real\n",
  ["/* outer /* nested */ still outer */", "// real"],
)

ALL_FIXTURES = [JS_FIXTURE, PY_FIXTURE, RUST_FIXTURE, KOTLIN_FIXTURE,
                JAVA_FIXTURE, CSS_FIXTURE, LESS_FIXTURE, SWIFT_FIXTURE]


def test_tokenizer():
  for name, lang, src, expected in ALL_FIXTURES:
    got = texts(comments.scan(src, lang))
    check("scan " + name, got == expected,
          "expected {} got {}".format(expected, got))


def test_classification():
  src = ("#!/usr/bin/env python3\n"
         "# Copyright (c) 2026 Example Corp. All rights reserved.\n"
         "import os  # noqa\n"
         "# region setup\n"
         "# plain narration\n"
         "# TODO: finish this\n"
         "# endregion\n")
  coms = comments.scan(src, "python")
  classes = [comments.classify(c, src) for c in coms]
  check("classify shebang", classes[0] == "shebang", str(classes))
  check("classify license", classes[1] == "license", str(classes))
  check("classify pragma", classes[2] == "pragma", str(classes))
  check("classify region", classes[3] == "navigation", str(classes))
  check("classify normal", classes[4] == "normal", str(classes))
  check("classify todo", classes[5] == "todo", str(classes))
  check("classify endregion", classes[6] == "navigation", str(classes))

  js = "// MARK: - Section\n// eslint-disable-next-line foo\n/* --- Helpers --- */\n"
  jcl = [comments.classify(c, js) for c in comments.scan(js, "js")]
  check("classify MARK/pragma/banner",
        jcl == ["navigation", "pragma", "navigation"], str(jcl))

  doc = "/// doc comment\nfn f() {}\n"
  dcoms = comments.scan(doc, "rust")
  check("doc flag off -> normal", comments.classify(dcoms[0], doc) == "normal")
  check("doc flag on -> doc",
        comments.classify(dcoms[0], doc, keep_doc_comments=True) == "doc")


def test_removal_spans():
  src = "let a = 1;\n// whole line\nlet b = 2;  // trailing\n"
  coms = comments.scan(src, "js")
  stripped, removed = comments.strip_text(
    src, [dict(c, **{"class": "normal"}) for c in coms])
  check("strip whole-line + trailing", stripped == "let a = 1;\nlet b = 2;\n",
        repr(stripped))


def test_round_trip():
  for name, lang, src, _ in ALL_FIXTURES:
    coms = comments.scan(src, lang)
    for c in coms:
      c["class"] = comments.classify(c, src)
    stripped, removed = comments.strip_text(src, coms)
    rebuilt = ""
    pos_stripped = 0
    prev = 0
    for c in removed:
      seg = c["rstart"] - prev
      rebuilt += stripped[pos_stripped:pos_stripped + seg]
      rebuilt += src[c["rstart"]:c["rend"]]  # the escrowed removal bytes
      pos_stripped += seg
      prev = c["rend"]
    rebuilt += stripped[pos_stripped:]
    check("round-trip " + name, rebuilt == src)


def test_commented_out_code():
  src = ("# const old = compute(x);\n"
         "# return old;\n"
         "# just prose talking about things\n")
  coms = comments.scan(src, "python")
  # Line comments are separate tokens; the heuristic is per-comment, so test a block.
  js = "/*\nconst old = compute(x);\nreturn old;\n*/\n/* plain prose here */\n"
  jcoms = comments.scan(js, "js")
  check("commented-out code detected", comments.looks_like_code(jcoms[0]))
  check("prose not code", not comments.looks_like_code(jcoms[1]))
  check("single codeish line", comments.looks_like_code(
    comments.scan("// x = compute(y);\n", "js")[0]))


def test_cli_harvest_strip():
  tmp = tempfile.mkdtemp(prefix="cleancode-test-")
  tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "comments.py")
  try:
    target = os.path.join(tmp, "sample.ts")
    original = ('const url = "https://x/y"; // strip me\n'
                "// eslint-disable-next-line keep\n"
                "// TODO: keep me too\n"
                "let a = 1;\n")
    with open(target, "w") as fh:
      fh.write(original)
    escrow = os.path.join(tmp, "escrow")

    r = subprocess.run([sys.executable, tool, "strip", escrow, target],
                       capture_output=True, text=True)
    check("strip refuses without harvest", r.returncode == 3, r.stderr)

    r = subprocess.run([sys.executable, tool, "harvest", escrow, target],
                       capture_output=True, text=True)
    check("harvest runs", r.returncode == 0, r.stderr)
    check("manifest written", os.path.isfile(os.path.join(escrow, "MANIFEST.md")))
    escrow_md = os.path.join(escrow, comments.fold_path(target) + ".md")
    check("escrow file written", os.path.isfile(escrow_md))
    with open(escrow_md) as fh:
      body = fh.read()
    check("escrow verbatim", "// strip me" in body and "// TODO: keep me too" in body)

    r = subprocess.run([sys.executable, tool, "census", target],
                       capture_output=True, text=True)
    check("census runs", r.returncode == 0 and '"commentCount": 3' in r.stdout,
          r.stdout)

    r = subprocess.run([sys.executable, tool, "strip", escrow, target],
                       capture_output=True, text=True)
    check("strip runs after harvest", r.returncode == 0, r.stderr)
    check("strip flags TODO", "TODO/FIXME left in place" in r.stdout, r.stdout)
    with open(target) as fh:
      after = fh.read()
    check("strip removed normal only",
          after == ('const url = "https://x/y";\n'
                    "// eslint-disable-next-line keep\n"
                    "// TODO: keep me too\n"
                    "let a = 1;\n"), repr(after))

    with open(target, "a") as fh:
      fh.write("let b = 2;\n")
    r = subprocess.run([sys.executable, tool, "strip", escrow, target],
                       capture_output=True, text=True)
    check("strip refuses stale escrow", r.returncode == 3, r.stderr)

    unsupported = os.path.join(tmp, "notes.txt")
    with open(unsupported, "w") as fh:
      fh.write("hello\n")
    r = subprocess.run([sys.executable, tool, "census", unsupported],
                       capture_output=True, text=True)
    check("unsupported file skipped loudly",
          r.returncode == 0 and "notes.txt" in r.stdout, r.stdout)
  finally:
    shutil.rmtree(tmp, ignore_errors=True)


def main():
  test_tokenizer()
  test_classification()
  test_removal_spans()
  test_round_trip()
  test_commented_out_code()
  test_cli_harvest_strip()
  print()
  if FAILURES:
    print("{} FAILURE(S): {}".format(len(FAILURES), ", ".join(FAILURES)))
    return 1
  print("all green")
  return 0


if __name__ == "__main__":
  sys.exit(main())
