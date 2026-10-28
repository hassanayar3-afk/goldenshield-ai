#!/usr/bin/env bash
# بعد تعديل saqr.env في workspace، انسخه لمشروع صقر:
SRC="/workspace/saqr.env"
if [[ ! -f "$SRC" ]]; then SRC="/workspace/saqr.env.template"; fi
if [[ -f /workspace/scripts/sanitize_saqr_env.py && "$SRC" == *saqr.env ]]; then
  python3 /workspace/scripts/sanitize_saqr_env.py "$SRC"
fi
cp -f "$SRC" /home/ubuntu/saqr/.env
echo "تم مزامنة saqr.env → /home/ubuntu/saqr/.env"
