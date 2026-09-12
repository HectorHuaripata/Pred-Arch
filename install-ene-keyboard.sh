#!/usr/bin/env bash
# install-ene-keyboard.sh — deploy the ENE keyboard backend into /opt/archer.
#
# Installs three files and nothing else:
#     archer_ene.py               new: the ENE K5130 protocol backend
#     archer_daemon.py            patched: prefers ENE, keeps the sysfs fallback
#     archer/pages/keyboard.py    patched: effect list matches reality
#
# The daemon is NOT restarted. Restarting is the operator's call, because
# archer-daemon reapplies saved lighting on start.
#
# Every replaced file is backed up first, and --rollback restores them.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gui"
DEST=/opt/archer
BACKUP_ROOT=/opt/archer.backups

FILES=(archer_ene.py archer_daemon.py archer/pages/keyboard.py)

die() { echo "install: $*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || die "requires root (sudo)"

# ---------------------------------------------------------------- rollback
if [[ "${1:-}" == "--rollback" ]]; then
    last="$(ls -1d "$BACKUP_ROOT"/* 2>/dev/null | tail -1 || true)"
    [[ -n "$last" ]] || die "no backups under $BACKUP_ROOT"
    echo "Restoring from $last"
    for f in "${FILES[@]}"; do
        if [[ -e "$last/$f" ]]; then
            install -Dm644 "$last/$f" "$DEST/$f"
            echo "  restored $f"
        else
            # The file did not exist before this change: remove it again.
            rm -f "$DEST/$f" && echo "  removed  $f (was not present before)"
        fi
    done
    rm -rf "$DEST/__pycache__" "$DEST/archer/pages/__pycache__"
    echo
    echo "Done. Apply with:  systemctl restart archer-daemon"
    exit 0
fi

# ----------------------------------------------------------------- install
[[ -d "$DEST" ]] || die "$DEST not found"
for f in "${FILES[@]}"; do
    [[ -f "$SRC/$f" ]] || die "missing source file $SRC/$f"
    python3 -m py_compile "$SRC/$f" || die "$f does not compile"
done

STAMP="$BACKUP_ROOT/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$STAMP"
echo "Backup -> $STAMP"
for f in "${FILES[@]}"; do
    if [[ -e "$DEST/$f" ]]; then
        install -Dm644 "$DEST/$f" "$STAMP/$f"
        echo "  saved $f"
    else
        echo "  $f not present yet (new file)"
    fi
done

echo
echo "Installing:"
for f in "${FILES[@]}"; do
    install -Dm644 "$SRC/$f" "$DEST/$f"
    echo "  $f"
done
chmod 755 "$DEST/archer_daemon.py"
# Stale bytecode from the previous build would shadow the new sources.
rm -rf "$DEST/__pycache__" "$DEST/archer/pages/__pycache__"

echo
echo "Verifying the backend can see the controller:"
( cd "$DEST" && python3 -c "
import archer_ene
print('  ENE detected:', archer_ene.available())
print('  effects     :', [n for n, _ in archer_ene.EFFECTS])
" )

cat <<'EOF'

Installed. The daemon has NOT been restarted.

  apply     sudo systemctl restart archer-daemon
  undo      sudo ./install-ene-keyboard.sh --rollback

Note: on start the daemon reapplies the lighting saved in
/etc/archer/settings.json, so the keyboard will change when you restart it.
EOF
