#!/bin/sh
set -e

# Install extra system packages from workspaces/household/packages.txt
# This file is on the bind-mounted volume, so it persists across restarts.
PACKAGES_FILE="/data/workspaces/household/packages.txt"
if [ -f "$PACKAGES_FILE" ]; then
    echo "[homeclaw] Installing extra packages from $PACKAGES_FILE ..."
    apt-get update -qq
    xargs -a "$PACKAGES_FILE" apt-get install -y --no-install-recommends -qq
    rm -rf /var/lib/apt/lists/*
    echo "[homeclaw] Extra packages installed."
fi

exec homeclaw serve --workspaces /data/workspaces --port 8080 "$@"
