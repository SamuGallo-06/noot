#!/bin/sh
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$REPO_ROOT"

VER=2.0.0
PKG=packages/deb/noot_${VER}_amd64
PYINSTALLER_OUT=packages/pyinstaller

if [ ! -d "$PYINSTALLER_OUT/dist/noot" ]; then
    echo "Errore: $PYINSTALLER_OUT/dist/noot non esiste. Esegui prima PyInstaller." >&2
    exit 1
fi

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/scalable/apps"

cp -r "$PYINSTALLER_OUT/dist/noot" "$PKG/opt/noot"
ln -s /opt/noot/noot "$PKG/usr/bin/noot"
cp src/assets/icon.svg "$PKG/usr/share/icons/hicolor/scalable/apps/noot.svg"
cp packages/deb/noot.desktop "$PKG/usr/share/applications/noot.desktop"

cat > "$PKG/DEBIAN/control" <<EOF
Package: noot
Version: $VER
Section: utils
Priority: optional
Architecture: amd64
Maintainer: SamuGallo-06 <tua-email@example.com>
Depends: usbmuxd, idevicerestore, libusb-1.0-0
Recommends: pkexec
Homepage: https://github.com/SamuGallo-06/noot
Description: iPhone backup manager for Linux
 Noot (Non-apple Open-source Operator for iTunes) manages backup,
 restore, erase and firmware flashing of iOS devices, with a CLI
 and a Qt graphical interface.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e

case "$1" in
    configure)
        if [ -d /run/systemd/system ]; then
            systemctl start usbmuxd || true
        fi
        ;;
esac

exit 0
EOF

cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e

case "$1" in
    remove|purge)
        # pulizia dopo la rimozione
        ;;
esac

exit 0
EOF

chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

chmod -R go-w "$PKG"
chmod 755 "$PKG/opt/noot/noot"
dpkg-deb --root-owner-group --build "$PKG"