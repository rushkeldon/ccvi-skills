#!/usr/bin/env bash
# archive-plans.sh — the /plans archive fast path: sweep FINISHED plans into an archive dir.
#
# Scans the *top level* of <dir> (never <archiveDir> itself) for *.plan.md files and moves
# the ones whose todos are all done into <archiveDir>. "Done" has two strictnesses:
#
#   lenient=0 (default) — STRICT: archive only when EVERY todo is `completed`. A `cancelled`
#                         todo is NOT terminal enough — the plan stays put (it may have been
#                         abandoned partway and deserves a human glance).
#   lenient=1           — LENIENT: any TERMINAL status counts — a plan is archived when every
#                         todo is `completed` OR `cancelled` (nothing pending/in_progress).
#
# Either way a plan needs at least one todo, and no todo may be `pending`/`in_progress`.
# When a plan IS archived, its sibling review/verify reports (<stem>.review.md and
# <stem>.verify.md) are swept into the archive alongside it — a plan and its reports never
# split across the two directories.
#
# Moves are COPY → VERIFY → DELETE, never a bare `mv`: `cp` the file, `cmp` source against
# copy byte-for-byte, and only on equality `rm` the source. On mismatch the bad copy is
# discarded, the source is kept, an ERROR line is printed, and the run continues. This
# script neither invokes nor assumes version control of any kind.
#
# Usage:
#   archive-plans.sh <dir> <archiveDir> [lenient]     # lenient: 0 (default) or 1
#
# Exit codes: 0 = success (even when nothing qualified); 1 = at least one copy-verify
# failure; 2 = usage error. An existing same-named file in the archive is left untouched
# and the source is skipped (never clobbered).

set -euo pipefail

usage() {
  echo "usage: archive-plans.sh <dir> <archiveDir> [lenient(0|1)]" >&2
  exit 2
}

[[ $# -ge 2 && $# -le 3 ]] || usage
SRC_DIR="${1%/}"
ARCHIVE_DIR="${2%/}"
INCLUDE_CANCELLED="${3:-0}"

[[ -d "$SRC_DIR" ]] || { echo "ERROR: not a directory: $SRC_DIR" >&2; usage; }
if [[ "$INCLUDE_CANCELLED" != "0" && "$INCLUDE_CANCELLED" != "1" ]]; then
  echo "ERROR: lenient flag must be 0 (strict: all completed) or 1 (lenient: completed OR cancelled); got '$INCLUDE_CANCELLED'" >&2
  usage
fi

if [[ "$INCLUDE_CANCELLED" == "1" ]]; then
  echo "mode: LENIENT — a plan archives when every todo is completed OR cancelled"
else
  echo "mode: STRICT  — a plan archives only when every todo is completed (cancelled keeps it)"
fi

mkdir -p "$ARCHIVE_DIR"

verify_failures=0

# copy → verify → delete, into the archive. Caller ensures the destination is free first.
# Returns nonzero (and keeps the source) when the copied bytes don't match the original.
do_move() {
  local src="$1" dst="$ARCHIVE_DIR/$(basename "$1")"
  cp "$src" "$dst"
  if cmp -s "$src" "$dst"; then
    rm "$src"
    return 0
  fi
  rm -f "$dst"
  echo "  ERROR   (copy verify failed — source kept)  $(basename "$src")" >&2
  verify_failures=$((verify_failures + 1))
  return 1
}

shopt -s nullglob
plans=("$SRC_DIR"/*.plan.md)
shopt -u nullglob
if [[ ${#plans[@]} -eq 0 ]]; then
  echo "no *.plan.md files at the top level of $SRC_DIR — nothing to do."
  exit 0
fi

archived=0
for f in "${plans[@]}"; do
  # Tally todo statuses. `status:` only appears on todos in the plan schema, so scanning the
  # whole file is safe. POSIX classes only (BSD awk has no \s).
  read -r total open comp canc < <(awk '
    /^[[:space:]]*status:[[:space:]]*/ {
      v=$0
      sub(/^[[:space:]]*status:[[:space:]]*/, "", v)
      sub(/[[:space:]]*#.*$/, "", v)      # strip inline comment
      gsub(/["'"'"']/, "", v)             # strip quotes
      sub(/[[:space:]]+$/, "", v)         # strip trailing space
      total++
      if (v=="completed")      comp++
      else if (v=="cancelled") canc++
      else                     open++     # pending / in_progress / anything unknown
    }
    END { printf "%d %d %d %d\n", total+0, open+0, comp+0, canc+0 }
  ' "$f")

  base="$(basename "$f")"
  if [[ "$total" -eq 0 ]]; then
    echo "  keep    (no todos)                         $base"
    continue
  fi
  if [[ "$open" -ne 0 ]]; then
    echo "  keep    ($open open / $total)                        $base"
    continue
  fi
  if [[ "$INCLUDE_CANCELLED" == "0" && "$canc" -ne 0 ]]; then
    echo "  keep    ($canc cancelled — strict mode / $total)      $base"
    continue
  fi

  dest="$ARCHIVE_DIR/$base"
  if [[ -e "$dest" ]]; then
    echo "  SKIP    (already in archive)               $base" >&2
    continue
  fi

  do_move "$f" || continue
  echo "  ARCHIVE ($comp completed, $canc cancelled / $total)   $base"
  archived=$((archived + 1))

  # Sweep the plan's review/verify reports along with it. Report names are the plan's stem
  # (basename minus `.plan.md`) + `.review.md` / `.verify.md` — e.g. foo.plan.md → foo.review.md.
  stem="${base%.plan.md}"
  for ext in review verify; do
    report="$SRC_DIR/$stem.$ext.md"
    [[ -e "$report" ]] || continue
    if [[ -e "$ARCHIVE_DIR/$stem.$ext.md" ]]; then
      echo "  SKIP    ($ext report already in archive)   $stem.$ext.md" >&2
      continue
    fi
    do_move "$report" || continue
    echo "          + $ext report                        $stem.$ext.md"
  done
done

echo "done — $archived plan(s) (with any review/verify reports) moved to $ARCHIVE_DIR."
[[ "$verify_failures" -eq 0 ]] || exit 1
