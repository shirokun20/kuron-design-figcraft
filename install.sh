#!/usr/bin/env bash
# Portable installer for kuron-design-figcraft 3.0.0.
# Installs the clean package into <target>/skills/kuron-design-figcraft/,
# then verifies the version lock, harness manifest, and full test suite.
#
# Usage:
#   bash install.sh [DEST]
#   DEST default: $HOME/.claude/skills/kuron-design-figcraft
# Only coreutils + python3 are required. No network, no credentials.
set -eu

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${1:-${HOME}/.claude/skills/kuron-design-figcraft}"
fail() { echo "install: FAILED — $1" >&2; exit 1; }

[ -f "$SRC/SKILL.md" ] || fail "SKILL.md not found in $SRC"
[ -f "$SRC/VERSION" ] || fail "VERSION not found in $SRC"
[ -f "$SRC/scripts/agent_terminal.py" ] || fail "scripts/agent_terminal.py not found"

# --- Version lock ---------------------------------------------------------
V="$(tr -d ' \n\r' < "$SRC/VERSION")"
SV="$(python3 - "$SRC/SKILL.md" <<'PY'
import sys
found = ""
in_meta = False
for line in open(sys.argv[1], encoding="utf-8"):
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
for line in open(sys.argv[1], encoding="utf-8"):
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

# --- Copy clean package (no .git, no caches) ------------------------------
mkdir -p "$DEST/references" "$DEST/scripts" "$DEST/tests" \
  || fail "cannot create $DEST"
cp "$SRC/SKILL.md" "$SRC/README.md" "$SRC/LICENSE" "$SRC/VERSION" \
   "$SRC/CHANGELOG.md" "$SRC/.gitignore" "$DEST/" || fail "failed to copy root files"
cp "$SRC"/references/*.md "$SRC"/references/*.css "$DEST/references/" \
  || fail "failed to copy references"
cp "$SRC"/scripts/*.py "$DEST/scripts/" || fail "failed to copy scripts"
cp "$SRC"/tests/*.py "$DEST/tests/" || fail "failed to copy tests"
echo "install: copied package to $DEST"

# --- Verify harness manifest ----------------------------------------------
NAME="$(python3 "$DEST/scripts/agent_terminal.py" harness-info 2>/dev/null \
  | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))' \
  || true)"
[ "$NAME" = "kuron-design-figcraft" ] \
  || fail "harness-info reported unexpected name: $NAME"
echo "install: harness manifest OK ($NAME)"

# --- Verify tests ----------------------------------------------------------
(cd "$DEST" && python3 -m unittest discover -s tests -p 'test_*.py' -v) \
  || fail "test suite failed in $DEST"

echo "install: OK — $DEST (kuron-design-figcraft $V)"
