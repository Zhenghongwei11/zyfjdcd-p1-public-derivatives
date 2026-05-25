#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_BASE="ZYFJDCD_P1_PUBLIC_ARCHIVE_${RUN_ID}"
ARCHIVE_DIR="$ROOT/archives"
ZIP_PATH="$ARCHIVE_DIR/${ARCHIVE_BASE}.zip"
SHA_PATH="$ARCHIVE_DIR/${ARCHIVE_BASE}.sha256"

mkdir -p "$ARCHIVE_DIR"

rm -f "$ZIP_PATH" "$SHA_PATH"
(cd "$ROOT" && zip -qr "$ZIP_PATH" . -x ".git/*" "archives/*" "results/runs_public/*" ".DS_Store")
shasum -a 256 "$ZIP_PATH" > "$SHA_PATH"

echo "OK: wrote $ZIP_PATH"
echo "OK: wrote $SHA_PATH"
