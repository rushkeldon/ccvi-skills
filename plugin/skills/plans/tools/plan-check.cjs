#!/usr/bin/env node
// plan-check.cjs — canonical validator for Cursor *.plan.md frontmatter.
// Parses the YAML frontmatter with the vendored js-yaml (the parser class Cursor's
// plans panel uses) and asserts the mechanical-lint invariants. Node-optional for the
// skill: this is the fast primary path; SKILL.md documents a python/ruby fallback.
//
// Usage:  node tools/plan-check.cjs <file.plan.md>
// Exit 0 + one-line summary on success; exit 1 + one line per problem on failure.

const fs = require("fs");
const path = require("path");
const yaml = require(path.join(__dirname, "vendor", "js-yaml.min.js"));

const VALID_STATUSES = ["pending", "in_progress", "completed", "cancelled"];

function die(file, problems) {
  console.error(`plan-check FAIL ${file}:`);
  for (const p of problems) console.error(`- ${p}`);
  process.exit(1);
}

const file = process.argv[2];
if (!file) {
  console.error("plan-check FAIL: no file argument (usage: plan-check.cjs <file.plan.md>)");
  process.exit(1);
}

let text;
try {
  text = fs.readFileSync(file, "utf8");
} catch (e) {
  console.error(`plan-check FAIL ${file}: cannot read file (${e.message})`);
  process.exit(1);
}

// Extract the leading frontmatter block: text between the first two '---' lines.
const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/);
if (!m) die(file, ["no leading frontmatter block delimited by '---' … '---'"]);

let fm;
try {
  fm = yaml.load(m[1]);
} catch (e) {
  // The core "won't parse" failure — e.g. an unquoted scalar with a colon-space.
  die(file, [`frontmatter does not parse as YAML: ${e.message.split("\n")[0]}`]);
}

const problems = [];

if (fm === null || typeof fm !== "object" || Array.isArray(fm)) {
  die(file, ["frontmatter is not a YAML mapping"]);
}

if (!("isProject" in fm)) {
  problems.push("missing 'isProject' key (expected a boolean)");
} else if (typeof fm.isProject !== "boolean") {
  problems.push(`'isProject' must be a boolean, got ${JSON.stringify(fm.isProject)}`);
}

if ("overview" in fm && typeof fm.overview !== "string") {
  problems.push("'overview' must be a string when present");
}

const statusesSeen = new Set();
let todoCount = 0;

if (!Array.isArray(fm.todos)) {
  problems.push("'todos' must be an array");
} else {
  todoCount = fm.todos.length;
  const ids = new Map(); // id -> count
  fm.todos.forEach((t, i) => {
    const where = `todo[${i}]`;
    if (t === null || typeof t !== "object" || Array.isArray(t)) {
      problems.push(`${where} is not a mapping`);
      return;
    }
    if (typeof t.id !== "string" || t.id.trim() === "") {
      problems.push(`${where} missing a non-empty string 'id'`);
    } else {
      ids.set(t.id, (ids.get(t.id) || 0) + 1);
    }
    if (typeof t.content !== "string" || t.content.trim() === "") {
      problems.push(`${where}${typeof t.id === "string" ? ` (${t.id})` : ""} missing a non-empty string 'content'`);
    }
    const label = typeof t.id === "string" ? t.id : where;
    if (!("status" in t)) {
      problems.push(`${label} missing 'status'`);
    } else if (t.status === "in-progress") {
      // Parses as a string but Cursor never renders the spinner for the hyphen form.
      problems.push(`${label} status is 'in-progress' (hyphen) — must be 'in_progress' (underscore)`);
    } else if (!VALID_STATUSES.includes(t.status)) {
      problems.push(`${label} status '${t.status}' not in {${VALID_STATUSES.join(", ")}}`);
    } else {
      statusesSeen.add(t.status);
    }
  });
  for (const [id, count] of ids) {
    if (count > 1) problems.push(`duplicate todo id '${id}' (appears ${count}×)`);
  }
}

if (problems.length) die(file, problems);

const statusList = VALID_STATUSES.filter((s) => statusesSeen.has(s)).join(", ") || "none";
console.log(`plan-check OK — ${todoCount} todos; statuses: ${statusList}; isProject=${fm.isProject}`);
process.exit(0);
