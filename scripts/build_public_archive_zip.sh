#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE_DIR="$ROOT/release_staging/public_repo"
ARCHIVE_DIR="$ROOT/release_staging/archives"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_BASE="ZYFJDCD_P1_PUBLIC_ARCHIVE_${RUN_ID}"
ZIP_PATH="$ARCHIVE_DIR/${ARCHIVE_BASE}.zip"
SHA_PATH="$ARCHIVE_DIR/${ARCHIVE_BASE}.sha256"

mkdir -p "$ARCHIVE_DIR"

"$ROOT/scripts/stage_public_repo.sh" "$STAGE_DIR"

rm -f "$ZIP_PATH" "$SHA_PATH"
(cd "$ROOT/release_staging" && zip -qr "$ZIP_PATH" "public_repo")
shasum -a 256 "$ZIP_PATH" > "$SHA_PATH"

echo "OK: wrote $ZIP_PATH"
echo "OK: wrote $SHA_PATH"
