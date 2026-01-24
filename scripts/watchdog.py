#!/usr/bin/env python3
"""
AI VTuber System Watchdog
サービスの健全性を監視し、必要に応じて再起動
"""
import subprocess
import sys
import time

import requests

HEALTH_ENDPOINTS = [
    ("orchestrator", "http://localhost:8080/health"),
    ("vllm", "http://localhost:8000/health"),
    ("tts", "http://localhost:8001/health"),
]


def check_health() -> tuple[bool, str]:
    for name, url in HEALTH_ENDPOINTS:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return False, f"{name} returned {r.status_code}"
        except Exception as e:
            return False, f"{name} unreachable: {e}"
    return True, "OK"


def restart_services():
    print("Restarting services...")
    subprocess.run(["docker", "compose", "restart"], check=True)


def main():
    consecutive_failures = 0
    max_failures = 3

    print("Watchdog started")

    while True:
        healthy, reason = check_health()

        if healthy:
            consecutive_failures = 0
            print(f"[{time.strftime('%H:%M:%S')}] All healthy")
        else:
            consecutive_failures += 1
            print(f"[{time.strftime('%H:%M:%S')}] Failure {consecutive_failures}/{max_failures}: {reason}")

            if consecutive_failures >= max_failures:
                restart_services()
                consecutive_failures = 0
                time.sleep(60)

        time.sleep(30)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nWatchdog stopped.")
        sys.exit(0)
