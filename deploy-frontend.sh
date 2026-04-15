#!/bin/bash
set -e

FRONTEND_DIR="/home/gui/projects/auto-shorts/frontend"
STANDALONE_DIR="$FRONTEND_DIR/.next/standalone"

echo "=== ClipIA Frontend Deploy ==="

# 1. Build
echo "[1/4] Building Next.js..."
cd "$FRONTEND_DIR"
npm run build

# 2. Copy static assets (Next.js standalone does NOT do this automatically)
echo "[2/4] Copying static assets to standalone..."
cp -r "$FRONTEND_DIR/.next/static" "$STANDALONE_DIR/.next/static"
cp -r "$FRONTEND_DIR/public" "$STANDALONE_DIR/public"

# 3. Restart service
echo "[3/4] Restarting clipia-frontend..."
sudo systemctl restart clipia-frontend

# 4. Verify
sleep 2
echo "[4/4] Verifying..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://localhost:3003)
if [ "$STATUS" = "200" ]; then
    echo "Deploy OK — frontend respondendo 200"
else
    echo "ERRO — frontend respondeu $STATUS"
    journalctl -u clipia-frontend --no-pager -n 10
    exit 1
fi
