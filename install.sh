#!/usr/bin/env bash
# Portable installer for kuron-design-figcraft 3.2.1.
# Installs the clean package into DEST (the full skill directory), then verifies
# the version lock, harness manifest, and full test suite from inside DEST.
#
# Usage:
#   bash install.sh [DEST] [--dry-run]
#   bash install.sh --help
#   DEST default: $HOME/.claude/skills/kuron-design-figcraft
# Only coreutils + python3 are required. No network, no credentials.
set -eu

fail() { echo "install: FAILED — $1" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: bash install.sh [DEST] [--dry-run]

DEST is the full path of the installed skill directory, e.g.
  ~/.claude/skills/kuron-design-figcraft
Default: $HOME/.claude/skills/kuron-design-figcraft

Options:
  -n, --dry-run   Print the target and planned checks; do not copy files.
  -h, --help      Show this help.
EOF
}

DRY_RUN=0
DEST=""
for arg in "$@"; do
  case "$arg" in
    -h|--help)   usage; exit 0 ;;
    -n|--dry-run) DRY_RUN=1 ;;
    -*)          fail "unknown option: $arg (try --help)" ;;
    *)
      [ -z "$DEST" ] || fail "only one DEST argument is allowed (got: $DEST and $arg)"
      DEST="$arg"
      ;;
  esac
done
DEST="${DEST:-${HOME}/.claude/skills/kuron-design-figcraft}"
SRC="$(cd "$(dirname "$0")" && pwd -P)"

[ -f "$SRC/SKILL.md" ] || fail "SKILL.md not found in $SRC"
[ -f "$SRC/VERSION" ] || fail "VERSION not found in $SRC"
[ -f "$SRC/scripts/agent_terminal.py" ] || fail "scripts/agent_terminal.py not found"

# --- Version lock ---------------------------------------------------------
V="$(tr -d ' \n\r' < "$SRC/VERSION")"
SV="$(python3 - "$SRC/SKILL.md" <<'PY'
import sys
found = ""
in_meta = False
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle:
        if line.strip() == "metadata:":
            in_meta = True
            continue
        if not in_meta:
            continue
        stripped = line.strip()
        if stripped.startswith("version:"):
            found = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            break
        if line and not line[0].isspace():
            break
print(found)
PY
)"
HV="$(python3 - "$SRC/scripts/agent_terminal.py" <<'PY'
import sys
found = ""
with open(sys.argv[1], encoding="utf-8") as handle:
    for line in handle:
        if line.startswith("HARNESS_VERSION"):
            found = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
print(found)
PY
)"
[ -n "$V" ] || fail "VERSION is empty"
[ "$V" = "$SV" ] || fail "version mismatch: VERSION=$V vs SKILL.md=$SV"
[ "$V" = "$HV" ] || fail "version mismatch: VERSION=$V vs HARNESS_VERSION=$HV"
echo "install: versions locked at $V"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "install: dry-run — would copy $SRC into $DEST"
  echo "install: dry-run — would verify harness-info and run the test suite in $DEST"
  echo "install: dry-run OK — DEST=$DEST (kuron-design-figcraft $V)"
  exit 0
fi

# --- Copy clean package (no .git, no caches) ------------------------------
# Explicit target directories make reruns safe. Overwriting is idempotent; no
# file outside DEST is touched, and no renamed file is left behind by this
# installer (all package files keep their documented paths).
mkdir -p "$DEST" "$DEST/references" "$DEST/scripts" "$DEST/tests" \
  "$DEST/docs/assets" "$DEST/docs/assets/showcase" || fail "cannot create $DEST"

cp "$SRC/SKILL.md" "$SRC/README.md" "$SRC/LICENSE" "$SRC/VERSION" \
   "$SRC/CHANGELOG.md" "$SRC/DESIGN.md" "$SRC/CONTRIBUTING.md" \
   "$SRC/.gitignore" "$DEST/" || fail "failed to copy root files"
cp "$SRC"/references/*.md "$SRC"/references/*.css "$DEST/references/" \
  || fail "failed to copy references"
cp "$SRC"/scripts/*.py "$DEST/scripts/" || fail "failed to copy scripts"
cp "$SRC"/tests/*.py "$DEST/tests/" || fail "failed to copy tests"
cp "$SRC/docs/assets/demo.gif" "$DEST/docs/assets/" \
  || fail "failed to copy demo GIF"
cp "$SRC"/docs/assets/showcase/* "$DEST/docs/assets/showcase/" \
  || fail "failed to copy showcase assets"
echo "install: copied package to $DEST"

# --- Verify harness manifest from inside DEST -----------------------------
HARNESS_OUT="$(cd "$DEST" && python3 -B scripts/agent_terminal.py harness-info 2>&1)" \
  || fail "harness-info failed in $DEST: $HARNESS_OUT"
NAME="$(printf '%s\n' "$HARNESS_OUT" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))' 2>/dev/null \
  || true)"
[ "$NAME" = "kuron-design-figcraft" ] \
  || fail "harness-info reported unexpected name or invalid JSON: $HARNESS_OUT"
echo "install: harness manifest OK ($NAME)"

# --- Verify tests from inside DEST (python3 -B keeps it cache-free) --------
(cd "$DEST" && python3 -B -m unittest discover -s tests -p 'test_*.py' -v) \
  || fail "test suite failed in $DEST"

echo "install: OK — DEST=$DEST (kuron-design-figcraft $V)"
