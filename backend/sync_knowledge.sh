#!/bin/bash
# 把本地 knowledge/*.md 同步到服务器 AI 服务
# 用法：./sync_knowledge.sh
set -e
cd "$(dirname "$0")"

KNOWLEDGE_DIR="/Users/bob/.openclaw/workspace/knowledge"
SERVER="root@139.224.66.88"
KEY="$HOME/.ssh/server_key.pem"
REMOTE="/root/genset-ai/backend"

echo "[1/3] 重新生成 knowledge.json ..."
python3 build_knowledge.py "$KNOWLEDGE_DIR" ./knowledge.json

echo "[2/3] 上传到服务器 ..."
scp -i "$KEY" -o StrictHostKeyChecking=no ./knowledge.json "$SERVER:$REMOTE/knowledge.json"

echo "[3/3] 重启服务 ..."
ssh -i "$KEY" -o StrictHostKeyChecking=no "$SERVER" "systemctl restart genset-ai.service && sleep 3 && curl -sS --max-time 10 --resolve 139.224.66.88.sslip.io:443:127.0.0.1 https://139.224.66.88.sslip.io/health"

echo ""
echo "✅ 同步完成"
