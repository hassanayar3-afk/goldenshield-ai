#!/bin/bash
# إعداد Contabo VPS لـ GoldenShield AI (paper Docker 24/7)
set -euo pipefail

echo "=== GoldenShield — Contabo Setup ==="
export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -qq
sudo apt-get install -y -qq docker.io docker-compose-v2 git curl ca-certificates nginx

sudo systemctl enable --now docker

APP_DIR=/opt/goldenshield
sudo mkdir -p "$APP_DIR" "$APP_DIR/storage/db/backups" "$APP_DIR/storage/logs"
sudo chown -R "$USER":"$USER" "$APP_DIR"

if [ ! -f "$APP_DIR/.env" ]; then
  if [ -f deployment/secrets.template ]; then
    cp deployment/secrets.template "$APP_DIR/.env"
    echo "أنشئ .env من secrets.template — عبّئ الأسرار قبل التشغيل"
  else
    echo "ضع المشروع في $APP_DIR أولاً ثم أعد تشغيل هذا السكربت"
    exit 1
  fi
fi

# nginx /health (اختياري — بدون API حالياً)
if [ -f deployment/nginx.conf ]; then
  sudo cp deployment/nginx.conf /etc/nginx/sites-available/goldenshield
  sudo ln -sf /etc/nginx/sites-available/goldenshield /etc/nginx/sites-enabled/goldenshield
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t && sudo systemctl enable --now nginx && sudo systemctl reload nginx
fi

cd "$APP_DIR"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

if [ -f deployment/systemd/goldenshield.service ]; then
  sudo cp deployment/systemd/goldenshield.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable goldenshield
fi

echo ""
echo "✅ جاهز. حالة الحاوية:"
docker compose ps
echo "صحة:"
docker exec goldenshield-bot python deployment/health_check.py || true
echo ""
echo "ملاحظة: تداول XM/MT5 الحقيقي يعمل على Windows VPS منفصل — ليس داخل هذا Docker."
