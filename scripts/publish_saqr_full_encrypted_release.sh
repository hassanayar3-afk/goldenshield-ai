#!/usr/bin/env bash
# Builds FULL Windows pack (with saqr/.env) and publishes AES-256 7z to GitHub.
# Plaintext .env is INSIDE the 7z — password is written to /opt/cursor/artifacts/ only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="saqr-v6.2.3-full"
REPO="hassanayar3-afk/goldenshield-ai"

"$ROOT/scripts/build_saqr_windows_complete.sh" --with-env

ZIP="/tmp/Saqr-Windows-Complete-v6.2.3-FULL.zip"
PASS_FILE="/opt/cursor/artifacts/SAQR-FULL-7Z-PASSWORD.txt"
ARCHIVE="/tmp/Saqr-Windows-Complete-v6.2.3-FULL.7z"
README="/tmp/SAQR-FULL-EXTRACT-AR.txt"

PASS="$(openssl rand -base64 14 | tr -dc 'A-Za-z0-9' | head -c 16)"
echo "$PASS" > "$PASS_FILE"
chmod 600 "$PASS_FILE"

STAGE="/tmp/saqr-full-publish"
rm -rf "$STAGE" && mkdir -p "$STAGE"
unzip -q "$ZIP" -d "$STAGE"
rm -f "$ARCHIVE"
7z a -t7z -mhe=on -p"$PASS" -mx=9 "$ARCHIVE" "$STAGE"/* >/dev/null

cat > "$README" << 'AR'
SAQR v6.2.3 — حزمة FULL (مشفّرة)
================================
1) ثبّت 7-Zip من https://www.7-zip.org/
2) فك Saqr-Windows-Complete-v6.2.3-FULL.7z (ستُطلب كلمة مرور — من ملف SAQR-FULL-7Z-PASSWORD في مرفقات الوكيل)
3) افتح المجلد Saqr-Windows-Complete-v6.2.3-FULL
4) ملف .env موجود ومكتمل — شغّل SAQR_RUN.bat

⚠️ لا تشارك ملف 7z أو كلمة المرور علناً.
AR

gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1 || \
  gh release create "$TAG" --repo "$REPO" \
    --title "SAQR v6.2.3 FULL — حزمة Windows كاملة (مشفّرة)" \
    --notes "حزمة تشغيل كاملة: saqr.exe + لوحة التحكم + .env جاهز داخل الأرشيف المشفّر. كلمة فك الضغط في مرفقات Cloud Agent (SAQR-FULL-7Z-PASSWORD.txt)."

gh release upload "$TAG" "$ARCHIVE" "$README" --repo "$REPO" --clobber

echo "RELEASE_OK $TAG"
echo "DOWNLOAD https://github.com/$REPO/releases/download/$TAG/Saqr-Windows-Complete-v6.2.3-FULL.7z"
echo "PASSWORD_FILE $PASS_FILE"
