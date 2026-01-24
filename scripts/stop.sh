#!/bin/bash

echo "Stopping AI VTuber System..."

cd "$(dirname "$0")/.."

docker compose down

echo "System stopped."
