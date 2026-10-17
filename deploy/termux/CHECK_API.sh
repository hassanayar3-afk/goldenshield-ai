#!/data/data/com.termux/files/usr/bin/bash
PORT="${MOBILE_API_PORT:-8790}"
URL="http://127.0.0.1:${PORT}/api/health"
echo "GET $URL"
curl -fsS "$URL" && echo && echo "HEALTH_OK" || { echo "HEALTH_FAIL"; exit 1; }
