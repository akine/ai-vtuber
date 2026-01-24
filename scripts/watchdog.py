#!/usr/bin/env python3
"""
AI VTuber System Watchdog
サービスの健全性を監視し、必要に応じて再起動
Slack/Discord通知、GPU監視機能付き
"""
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import requests

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 設定
CHECK_INTERVAL = int(os.getenv("WATCHDOG_CHECK_INTERVAL", "30"))
MAX_FAILURES = int(os.getenv("WATCHDOG_MAX_FAILURES", "3"))
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
GPU_MEMORY_THRESHOLD = float(os.getenv("GPU_MEMORY_THRESHOLD", "90"))  # パーセント

HEALTH_ENDPOINTS = [
    ("orchestrator", "http://localhost:8080/health"),
    ("vllm", "http://localhost:8000/health"),
    ("tts", "http://localhost:8001/health"),
]


@dataclass
class ServiceStatus:
    name: str
    healthy: bool
    message: str
    timestamp: datetime


def send_notification(title: str, message: str, level: str = "warning"):
    """SlackまたはDiscordに通知を送信"""
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "🚨", "ok": "✅"}.get(level, "📢")
    full_message = f"{emoji} **{title}**\n{message}"

    if SLACK_WEBHOOK_URL:
        try:
            requests.post(
                SLACK_WEBHOOK_URL,
                json={"text": full_message.replace("**", "*")},
                timeout=10
            )
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": full_message},
                timeout=10
            )
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")


def check_service_health(name: str, url: str) -> ServiceStatus:
    """個別サービスのヘルスチェック"""
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return ServiceStatus(name, True, "OK", datetime.now())
        else:
            return ServiceStatus(name, False, f"HTTP {r.status_code}", datetime.now())
    except requests.exceptions.ConnectionError:
        return ServiceStatus(name, False, "Connection refused", datetime.now())
    except requests.exceptions.Timeout:
        return ServiceStatus(name, False, "Timeout", datetime.now())
    except Exception as e:
        return ServiceStatus(name, False, str(e), datetime.now())


def check_gpu_memory() -> tuple[bool, float]:
    """GPU VRAM使用率をチェック"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            used, total = map(float, result.stdout.strip().split(", "))
            usage_percent = (used / total) * 100
            return usage_percent < GPU_MEMORY_THRESHOLD, usage_percent
    except Exception as e:
        logger.warning(f"GPU check failed: {e}")
    return True, 0.0


def restart_service(service_name: str):
    """特定のサービスを再起動"""
    logger.info(f"Restarting {service_name}...")
    try:
        subprocess.run(
            ["docker", "compose", "restart", service_name],
            check=True,
            timeout=120
        )
        logger.info(f"{service_name} restarted successfully")
        send_notification(
            f"Service Restarted: {service_name}",
            f"{service_name}を再起動しました",
            "info"
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart {service_name}: {e}")
        send_notification(
            f"Restart Failed: {service_name}",
            f"{service_name}の再起動に失敗しました: {e}",
            "error"
        )


def restart_all_services():
    """全サービスを再起動"""
    logger.info("Restarting all services...")
    try:
        subprocess.run(
            ["docker", "compose", "restart"],
            check=True,
            timeout=300
        )
        logger.info("All services restarted")
        send_notification(
            "All Services Restarted",
            "全サービスを再起動しました",
            "warning"
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to restart services: {e}")
        send_notification(
            "Restart Failed",
            f"サービス再起動に失敗しました: {e}",
            "error"
        )


def main():
    failure_counts: dict[str, int] = {name: 0 for name, _ in HEALTH_ENDPOINTS}
    gpu_failure_count = 0
    last_notification: dict[str, float] = {}
    notification_cooldown = 300  # 5分間は同じ通知を送らない

    logger.info("Watchdog started")
    logger.info(f"Check interval: {CHECK_INTERVAL}s, Max failures: {MAX_FAILURES}")
    logger.info(f"Slack: {'configured' if SLACK_WEBHOOK_URL else 'not configured'}")
    logger.info(f"Discord: {'configured' if DISCORD_WEBHOOK_URL else 'not configured'}")

    send_notification("Watchdog Started", "AI VTuber監視を開始しました", "ok")

    while True:
        all_healthy = True
        status_messages = []

        # 各サービスのヘルスチェック
        for name, url in HEALTH_ENDPOINTS:
            status = check_service_health(name, url)

            if status.healthy:
                if failure_counts[name] > 0:
                    logger.info(f"{name} recovered")
                    send_notification(f"Service Recovered: {name}", f"{name}が復旧しました", "ok")
                failure_counts[name] = 0
                status_messages.append(f"  {name}: ✅")
            else:
                all_healthy = False
                failure_counts[name] += 1
                status_messages.append(f"  {name}: ❌ ({status.message})")
                logger.warning(f"{name} unhealthy ({failure_counts[name]}/{MAX_FAILURES}): {status.message}")

                # 連続失敗でサービス再起動
                if failure_counts[name] >= MAX_FAILURES:
                    restart_service(name)
                    failure_counts[name] = 0
                    time.sleep(30)  # 再起動後の待機

        # GPU監視
        gpu_ok, gpu_usage = check_gpu_memory()
        if not gpu_ok:
            gpu_failure_count += 1
            logger.warning(f"GPU memory high: {gpu_usage:.1f}% (threshold: {GPU_MEMORY_THRESHOLD}%)")

            now = time.time()
            if "gpu" not in last_notification or now - last_notification["gpu"] > notification_cooldown:
                send_notification(
                    "GPU Memory Warning",
                    f"VRAM使用率が高くなっています: {gpu_usage:.1f}%",
                    "warning"
                )
                last_notification["gpu"] = now
        else:
            gpu_failure_count = 0
            status_messages.append(f"  GPU: ✅ ({gpu_usage:.1f}%)")

        # ステータスログ
        if all_healthy and gpu_ok:
            logger.info("All services healthy")
        else:
            logger.info("Status:\n" + "\n".join(status_messages))

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user")
        send_notification("Watchdog Stopped", "監視を停止しました", "info")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Watchdog crashed: {e}")
        send_notification("Watchdog Crashed", f"監視が異常終了しました: {e}", "error")
        sys.exit(1)
