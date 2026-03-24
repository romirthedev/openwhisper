#!/bin/bash
# Build OpenWhisper.dmg for distribution
# Creates a drag-to-Applications DMG installer

set -e

APP_NAME="OpenWhisper"
DMG_NAME="OpenWhisper-Installer"
SWIFT_DIR="$(cd "$(dirname "$0")/swift" && pwd)"
DIST_DIR="$(cd "$(dirname "$0")" && pwd)/dist"

echo "🔨 Building ${APP_NAME}.app..."
cd "$SWIFT_DIR" && make 2>&1 | grep -E "(error:|Build complete)" || true

if [ ! -d "$SWIFT_DIR/${APP_NAME}.app" ]; then
    echo "❌ Build failed"
    exit 1
fi

echo "📦 Creating DMG..."
mkdir -p "$DIST_DIR"
rm -rf "$DIST_DIR/dmg_staging" "$DIST_DIR/${DMG_NAME}.dmg"
mkdir -p "$DIST_DIR/dmg_staging"

# Copy app to staging
cp -R "$SWIFT_DIR/${APP_NAME}.app" "$DIST_DIR/dmg_staging/"

# Create Applications symlink for drag-to-install
ln -s /Applications "$DIST_DIR/dmg_staging/Applications"

# Create DMG
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$DIST_DIR/dmg_staging" \
    -ov -format UDZO \
    "$DIST_DIR/${DMG_NAME}.dmg"

rm -rf "$DIST_DIR/dmg_staging"

echo ""
echo "✅ Built: dist/${DMG_NAME}.dmg"
echo "   Upload this to GitHub Releases for the download button."
