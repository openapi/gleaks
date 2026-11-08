#!/bin/sh
# Build a plain .deb (no debhelper needed) from the source tree.
# Usage: build-aux/deb/build-deb.sh [output-dir]
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:-$ROOT/dist}
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/gleaks/__init__.py")
PKG=$(mktemp -d)
trap 'rm -rf "$PKG"' EXIT

make -C "$ROOT" install DESTDIR="$PKG" PREFIX=/usr PYTHON=/usr/bin/python3 >/dev/null

mkdir -p "$PKG/DEBIAN" "$OUT"
SIZE=$(du -sk "$PKG/usr" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CTRL
Package: gleaks
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.11), python3-gi, python3-cryptography, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.5), gir1.2-secret-1
Installed-Size: $SIZE
Maintainer: GLeaks contributors <noreply@users.noreply.github.com>
Homepage: https://github.com/openapi/gleaks
Description: Personal data exposure monitor for GNOME
 Keeps a local, encrypted record of where your identifiers have appeared
 in known data breaches, using sources you configure with your own keys.
 There is no account and no cloud service.
CTRL
dpkg-deb --root-owner-group --build "$PKG" "$OUT/gleaks_${VERSION}_all.deb"
echo "Built $OUT/gleaks_${VERSION}_all.deb"
