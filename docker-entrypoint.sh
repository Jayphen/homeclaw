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

# Install extra npm packages from workspaces/household/npm-packages.txt
NPM_PACKAGES_FILE="/data/workspaces/household/npm-packages.txt"
if [ -f "$NPM_PACKAGES_FILE" ] && command -v npm >/dev/null 2>&1; then
    MISSING_NPM=""
    while IFS= read -r pkg || [ -n "$pkg" ]; do
        case "$pkg" in ""|\#*) continue ;; esac
        # Extract package name without version for the which-check
        bin="${pkg%%@*}"
        bin="${bin##*/}"
        if ! command -v "$bin" >/dev/null 2>&1; then
            MISSING_NPM="$MISSING_NPM $pkg"
        fi
    done < "$NPM_PACKAGES_FILE"

    if [ -n "$MISSING_NPM" ]; then
        echo "[homeclaw] Installing npm packages:$MISSING_NPM ..."
        # shellcheck disable=SC2086
        npm install -g --prefer-offline $MISSING_NPM
        echo "[homeclaw] npm packages installed."
    else
        echo "[homeclaw] npm packages already installed, skipping."
    fi
fi

exec homeclaw serve --workspaces /data/workspaces --port 8080 "$@"
