#!/bin/bash

echo "Checking AI VTuber System Health..."
echo ""

# Redis
echo -n "Redis: "
if docker exec ai-vtuber-redis-1 redis-cli ping > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED"
fi

# vLLM
echo -n "vLLM: "
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED or not started"
fi

# TTS
echo -n "TTS: "
if curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED or not started"
fi

# Orchestrator
echo -n "Orchestrator: "
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED or not started"
fi

echo ""
echo "Container Status:"
docker compose ps 2>/dev/null || echo "Docker Compose not running"
