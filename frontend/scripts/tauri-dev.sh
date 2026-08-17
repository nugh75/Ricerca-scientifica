#!/usr/bin/env bash
# Launch `npm run tauri dev` with the display environment correctly set.
#
# Why this exists: under WSL2 the GUI display is provided by WSLg (weston +
# Xwayland), but the WSLg environment variables (DISPLAY, WAYLAND_DISPLAY,
# XDG_RUNTIME_DIR, DBUS_SESSION_BUS_ADDRESS) are only injected into login
# shells. In SSH sessions and many IDE terminals they are missing, so GTK
# cannot initialize and `tauri dev` dies with:
#
#   Failed to initialize gtk backend!: BoolError { message: "Failed to
#   initialize GTK", ... }
#
# This script restores the WSLg variables (without overriding values already
# set, e.g. when the terminal is a normal WSLg login shell) and then runs the
# dev command.
set -euo pipefail

cd "$(dirname "$0")/.."

if grep -qi microsoft /proc/version 2>/dev/null; then
  export DISPLAY="${DISPLAY:-:0}"
  export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/mnt/wslg/runtime-dir}"
  if [ -S "/mnt/wslg/run/user/$(id -u)/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/mnt/wslg/run/user/$(id -u)/bus"
  fi
  if ! command -v xdpyinfo >/dev/null 2>&1 || ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    echo "warning: cannot reach X display '$DISPLAY'." >&2
    echo "  WSLg may be stopped. On Windows run 'wsl --shutdown', reopen this" >&2
    echo "  terminal, then retry. (Headless fallback: xvfb-run -a npm run tauri dev)" >&2
  fi
fi

exec npm run tauri dev
