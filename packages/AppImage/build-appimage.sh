#!/bin/bash
set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)
cd "$SCRIPT_DIR"

if [ -z "$1" ]; then
    echo "Please specify the architecture (e.g., x86_64, aarch64)." >&2
    exit 1
fi
ARCH="$1"

PYI_DIST="$REPO_ROOT/packages/pyinstaller/dist/noot"
if [ ! -d "$PYI_DIST" ]; then
    echo "Errore: $PYI_DIST non esiste. Esegui prima PyInstaller." >&2
    exit 1
fi

echo "Building AppImage..."
rm -rf AppDir
mkdir -p AppDir/usr/lib

echo "Copying files to AppDir..."
cp -r "$PYI_DIST" AppDir/usr/lib/noot
cp "$SCRIPT_DIR/noot.desktop" AppDir/noot.desktop
cp "$REPO_ROOT/src/assets/icon.svg" AppDir/noot.svg
rsvg-convert -w 256 -h 256 "$REPO_ROOT/src/assets/icon.svg" -o AppDir/noot.png
ln -sf noot.png AppDir/.DirIcon

echo "Creating AppRun script..."
cat > AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="${APPDIR:-$(dirname "$(readlink -f "$0")")}"
if [ "$#" -eq 0 ]; then
    set -- --gui
fi
exec "$HERE/usr/lib/noot/noot" "$@"
EOF
chmod +x AppDir/AppRun

ARCH="$ARCH" $REPO_ROOT/tmp/appimagetool-x86_64.AppImage AppDir "Noot-$ARCH.AppImage"