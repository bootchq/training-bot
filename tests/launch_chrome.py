#!/usr/bin/env python3
"""
Запускает Chrome с remote debugging и скопированной сессией Telegram
"""
import subprocess
import os
import time

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome/BotTesting")

print("Запускаю Chrome...")
print(f"Профиль: {PROFILE_DIR}")

# Запускаем Chrome
subprocess.Popen([
    CHROME_PATH,
    "--remote-debugging-port=9222",
    f"--user-data-dir={PROFILE_DIR}",
    "--profile-directory=Default",  # ВАЖНО! Использовать Default профиль со скопированной сессией
    "--no-first-run",
    "https://web.telegram.org/k/"
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("Жду 10 секунд...")
time.sleep(10)

# Проверяем порт
import requests
try:
    r = requests.get("http://127.0.0.1:9222/json/version", timeout=2)
    print(f"✅ Remote debugging работает!")
    print(f"Chrome: {r.json().get('Browser', 'Unknown')}")
except Exception as e:
    print(f"⚠️  Порт не отвечает: {e}")
