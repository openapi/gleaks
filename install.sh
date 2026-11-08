#!/usr/bin/env bash
# GLeaks installer.
#
#   curl -fsSL https://github.com/openapi/gleaks/releases/latest/download/install.sh | bash
#
# Ubuntu / Debian: installs the latest release .deb; apt pulls the dependencies.
# Other distributions: use the Flatpak bundle from the releases page.
set -euo pipefail

BASE="https://github.com/openapi/gleaks/releases/latest/download"

die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v curl >/dev/null || die "curl is required."
command -v apt-get >/dev/null ||
  die "This installer needs apt. Use the Flatpak bundle from https://github.com/openapi/gleaks/releases"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fL --progress-bar -o "$TMP/gleaks_all.deb" "$BASE/gleaks_all.deb" || die "Download failed."
# apt downloads as the unprivileged _apt user, which cannot enter mktemp's 0700 dir.
chmod 755 "$TMP"
chmod 644 "$TMP/gleaks_all.deb"
if [ "$(id -u)" -eq 0 ]; then
  apt-get install -y "$TMP/gleaks_all.deb"
else
  sudo apt-get install -y "$TMP/gleaks_all.deb"
fi
echo "Done. Launch GLeaks from the app grid or run: gleaks"
