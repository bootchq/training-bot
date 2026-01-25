#!/usr/bin/env python3
"""
E2E тест онбординга через Playwright CDP
Подключается к уже запущенному Chrome
"""

import asyncio
import time
import os
import sys

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Установи playwright: pip3 install playwright")
    sys.exit(1)

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
CDP_URL = "http://127.0.0.1:9222"


class OnboardingTester:
    def __init__(self):
        self.browser = None
        self.page = None
        self.results = []

    def log(self, msg, status="info"):
        icons = {"ok": "✅", "fail": "❌", "warn": "⚠️", "info": "📝"}
        print(f"{icons.get(status, '•')} {msg}", flush=True)
        self.results.append((status, msg))

    async def screenshot(self, name):
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        path = f"{SCREENSHOTS_DIR}/{name}.png"
        await self.page.screenshot(path=path)
        self.log(f"Screenshot: {name}.png")

    async def connect(self):
        """Подключение к Chrome через CDP"""
        self.log("Подключаюсь к Chrome через CDP...")

        # Получаем WebSocket URL
        import urllib.request
        import json

        try:
            with urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5) as resp:
                data = json.loads(resp.read())
                ws_url = data.get('webSocketDebuggerUrl', '')
                self.log(f"WebSocket: {ws_url[:50]}...")
        except Exception as e:
            self.log(f"Chrome не отвечает: {e}", "fail")
            return False

        playwright = await async_playwright().start()

        try:
            self.browser = await playwright.chromium.connect_over_cdp(ws_url, timeout=60000)
            contexts = self.browser.contexts

            if contexts:
                self.page = contexts[0].pages[0] if contexts[0].pages else await contexts[0].new_page()
            else:
                context = await self.browser.new_context()
                self.page = await context.new_page()

            self.log("Подключен к Chrome", "ok")
            return True

        except Exception as e:
            self.log(f"Ошибка подключения: {e}", "fail")
            self.log("Запусти Chrome с: --remote-debugging-port=9222")
            return False

    async def check_auth(self):
        """Проверка авторизации"""
        self.log("Проверка авторизации в Telegram...")
        await asyncio.sleep(2)

        content = await self.page.content()

        if 'Log in' in content or 'Sign in' in content or 'QR code' in content:
            self.log("Требуется авторизация!", "fail")
            return False

        self.log("Авторизован", "ok")
        return True

    async def open_bot(self):
        """Открыть чат с ботом"""
        self.log(f"Открываю @{BOT_USERNAME}...")

        await self.page.goto(f"https://web.telegram.org/k/#{BOT_USERNAME}")
        await asyncio.sleep(4)
        await self.screenshot("01_bot")
        self.log("Бот открыт", "ok")

    async def send_message(self, text):
        """Отправить сообщение"""
        self.log(f"Отправляю: {text}")

        try:
            # Ищем поле ввода
            input_sel = 'div[contenteditable="true"], .input-message-input'
            await self.page.wait_for_selector(input_sel, timeout=5000)

            await self.page.click(input_sel)
            await asyncio.sleep(0.3)
            await self.page.keyboard.type(text)
            await asyncio.sleep(0.3)
            await self.page.keyboard.press('Enter')
            await asyncio.sleep(2)

            return True
        except Exception as e:
            self.log(f"Ошибка отправки: {e}", "warn")
            return False

    async def click_button(self, text_contains):
        """Клик по кнопке с текстом"""
        self.log(f"Ищу кнопку: {text_contains}")
        await asyncio.sleep(1)

        try:
            # Ищем кнопки
            buttons = await self.page.query_selector_all('button.reply-markup-button, button[class*="Button"]')

            for btn in buttons:
                btn_text = await btn.inner_text()
                if text_contains.lower() in btn_text.lower():
                    await btn.click()
                    self.log(f"Кликнул: {btn_text}", "ok")
                    await asyncio.sleep(2)
                    return True

            self.log(f"Кнопка '{text_contains}' не найдена", "warn")
            return False

        except Exception as e:
            self.log(f"Ошибка клика: {e}", "warn")
            return False

    async def get_buttons(self):
        """Получить список кнопок"""
        buttons = []
        try:
            els = await self.page.query_selector_all('button.reply-markup-button, button[class*="Button"]')
            for el in els:
                text = await el.inner_text()
                if text:
                    buttons.append(text)
        except:
            pass
        return buttons

    async def test_reset(self):
        """Тест /reset"""
        await self.send_message("/reset")
        await asyncio.sleep(2)
        await self.screenshot("02_reset")

        if await self.click_button("Да, сбросить"):
            self.log("/reset работает", "ok")
            await asyncio.sleep(2)
            await self.screenshot("03_reset_done")
            return True
        return False

    async def test_start(self):
        """Тест /start"""
        await self.send_message("/start")
        await asyncio.sleep(3)
        await self.screenshot("04_start")

        buttons = await self.get_buttons()
        self.log(f"Кнопки: {buttons}")

        if any("garmin" in b.lower() for b in buttons):
            self.log("/start показывает Garmin кнопки", "ok")
            return True

        self.log("Garmin кнопки не найдены", "fail")
        return False

    async def test_garmin(self, email, password):
        """Регистрация Garmin"""
        if not await self.click_button("Есть аккаунт"):
            return False

        await asyncio.sleep(2)
        await self.screenshot("05_email")

        await self.send_message(email)
        await asyncio.sleep(2)
        await self.screenshot("06_password")

        await self.send_message(password)
        await asyncio.sleep(5)
        await self.screenshot("07_garmin_done")

        self.log("Garmin регистрация", "ok")
        return True

    async def test_onboarding_start(self):
        """Начало онбординга"""
        await asyncio.sleep(2)

        if await self.click_button("Настроить тренировки") or await self.click_button("тренировки"):
            await asyncio.sleep(2)
            await self.screenshot("08_onboarding")

            buttons = await self.get_buttons()
            self.log(f"Кнопки онбординга: {buttons}")

            if any("забег" in b.lower() for b in buttons):
                self.log("Онбординг показан", "ok")
                return True

        # Может уже показан
        buttons = await self.get_buttons()
        if any("забег" in b.lower() for b in buttons):
            self.log("Онбординг уже показан", "ok")
            return True

        self.log("Онбординг не найден", "fail")
        return False

    async def test_goal_race(self):
        """Выбор забега"""
        if await self.click_button("забегу"):
            await asyncio.sleep(2)
            await self.screenshot("09_race")

            buttons = await self.get_buttons()
            self.log(f"Типы забега: {buttons}")

            expected = ["Полумарафон", "Марафон", "Трейл"]
            found = sum(1 for e in expected if any(e.lower() in b.lower() for b in buttons))

            if found >= 2:
                self.log("Типы забега показаны", "ok")
                return True

        self.log("Типы забега не найдены", "fail")
        return False

    async def test_trail(self):
        """Выбор трейла"""
        if await self.click_button("Трейл"):
            await asyncio.sleep(2)
            await self.screenshot("10_trail")

            content = await self.page.content()
            if "дистанц" in content.lower() or "км" in content.lower():
                self.log("Запрос дистанции трейла", "ok")

                await self.send_message("50")
                await asyncio.sleep(2)
                await self.screenshot("11_trail_km")
                return True

        self.log("Трейл не работает", "fail")
        return False

    async def test_days(self):
        """Выбор дней"""
        await asyncio.sleep(2)
        buttons = await self.get_buttons()
        self.log(f"Кнопки дней: {buttons}")

        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        found = sum(1 for d in days if any(d in b for b in buttons))

        if found >= 5:
            self.log("Кнопки дней показаны", "ok")
            await self.screenshot("12_days")

            # Выбираем 3 дня
            for day in ["Пн", "Ср", "Пт"]:
                await self.click_button(day)
                await asyncio.sleep(0.5)

            await self.screenshot("13_days_selected")

            if await self.click_button("Готово"):
                await asyncio.sleep(2)
                await self.screenshot("14_days_done")
                self.log("Дни выбраны", "ok")
                return True

        self.log("Выбор дней не работает", "fail")
        return False

    async def test_time(self):
        """Ввод времени"""
        await asyncio.sleep(2)
        content = await self.page.content()

        if "время" in content.lower():
            await self.send_message("19:00")
            await asyncio.sleep(3)
            await self.screenshot("15_done")

            content = await self.page.content()
            if "завершен" in content.lower():
                self.log("Онбординг завершён!", "ok")
                return True

        self.log("Ввод времени не работает", "fail")
        return False

    async def run(self, email, password):
        """Полный тест"""
        print("="*60, flush=True)
        print("🧪 E2E ТЕСТ ОНБОРДИНГА (Playwright)", flush=True)
        print("="*60, flush=True)

        if not await self.connect():
            return False

        if not await self.check_auth():
            self.log("Авторизуйся в Telegram Web и перезапусти тест")
            return False

        await self.open_bot()
        await self.test_reset()
        await asyncio.sleep(2)

        if not await self.test_start():
            return False

        if not await self.test_garmin(email, password):
            return False

        if not await self.test_onboarding_start():
            return False

        if not await self.test_goal_race():
            return False

        if not await self.test_trail():
            return False

        if not await self.test_days():
            return False

        await self.test_time()

        # Итоги
        print(flush=True)
        print("="*60, flush=True)
        passed = sum(1 for s, _ in self.results if s == "ok")
        failed = sum(1 for s, _ in self.results if s == "fail")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📸 Screenshots: {SCREENSHOTS_DIR}")

        if failed == 0:
            print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ!")
            return True
        else:
            print("❌ ЕСТЬ ПРОБЛЕМЫ")
            return False


async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "bootchq@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "Aa1424617556"

    tester = OnboardingTester()
    success = await tester.run(email, password)
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
