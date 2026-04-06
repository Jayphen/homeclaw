#!/bin/sh
set -e

# Install extra system packages from workspaces/household/packages.txt
# This file is on the bind-mounted volume, so it persists across restarts.
PACKAGES_FILE="/data/workspaces/household/packages.txt"
if [ -f "$PACKAGES_FILE" ]; then
    # Check if all packages are already installed to avoid reinstalling on every boot.
    MISSING=""
    while IFS= read -r pkg || [ -n "$pkg" ]; do
        # Skip blank lines and comments
        case "$pkg" in ""|\#*) continue ;; esac
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            MISSING="$MISSING $pkg"
        fi
    done < "$PACKAGES_FILE"

    if [ -n "$MISSING" ]; then
        echo "[homeclaw] Installing extra packages:$MISSING ..."
        dpkg --configure -a || true
        apt-get update -qq
        # shellcheck disable=SC2086
        apt-get install -y --no-install-recommends -qq $MISSING
        rm -rf /var/lib/apt/lists/*
        echo "[homeclaw] Extra packages installed."
    else
        echo "[homeclaw] Extra packages already installed, skipping."
    fi
fi

exec homeclaw serve --workspaces /data/workspaces --port 8080 "$@"
