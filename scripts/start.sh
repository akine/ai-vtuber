#!/bin/bash
set -e

# Intel CPU問題対策
export OPENSSL_ia32cap="~0x20000000"
export NODE_OPTIONS="--max-old-space-size=65536"

echo "Starting AI VTuber System..."

# プロジェクトディレクトリに移動
cd "$(dirname "$0")/.."

# Docker Compose起動
docker compose up -d

# ヘルスチェック待機
echo "Waiting for services to start..."
sleep 10

# ステータス確認
docker compose ps

echo ""
echo "System started!"
echo "Grafana: http://localhost:3000"
echo "API: http://localhost:8080"
echo "Prometheus: http://localhost:9090"
