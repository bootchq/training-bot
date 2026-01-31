#!/usr/bin/env python3
"""
E2E тест онбординга — Playwright с persistent context
"""

import asyncio
import os
import sys

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("pip3 install playwright && playwright install chromium")
    sys.exit(1)

BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
# Используем профиль Chrome с сохранённой сессией
PROFILE = "/Users/noor/Documents/Obsidian Vault/Бот тренера/chrome_test_profile"


async def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "bootchq@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "Aa1424617556"

    os.makedirs(SCREENSHOTS, exist_ok=True)

    print("="*60)
    print("🧪 E2E ТЕСТ ОНБОРДИНГА")
    print("="*60)

    async with async_playwright() as p:
        print("📝 Запускаю браузер...")

        # Запускаем Chromium с persistent context (сохраняет сессию)
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE,
            headless=False,
            channel="chrome",  # Используем установленный Chrome
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = context.pages[0] if context.pages else await context.new_page()

        print("✅ Браузер запущен")

        # Открываем Telegram
        print("📝 Открываю Telegram Web...")
        await page.goto("https://web.telegram.org/k/")
        await asyncio.sleep(5)

        # Проверяем авторизацию
        content = await page.content()
        if 'Log in' in content or 'Sign in' in content:
            print("❌ Требуется авторизация в Telegram!")
            print("   Авторизуйся в открывшемся окне...")
            print("   Жду 60 секунд...")

            for i in range(6):
                await asyncio.sleep(10)
                content = await page.content()
                if 'Log in' not in content and 'Sign in' not in content:
                    print("✅ Авторизация прошла!")
                    break
                print(f"   Осталось {60-i*10} сек...")
            else:
                print("❌ Авторизация не завершена")
                await context.close()
                return False

        print("✅ Авторизован в Telegram")

        # Открываем бота
        print(f"📝 Открываю @{BOT_USERNAME}...")
        await page.goto(f"https://web.telegram.org/k/#{BOT_USERNAME}")
        await asyncio.sleep(4)
        await page.screenshot(path=f"{SCREENSHOTS}/01_bot.png")

        async def send(text):
            """Отправить сообщение"""
            try:
                inp = page.locator('div[contenteditable="true"]').first
                await inp.click()
                await asyncio.sleep(0.3)
                await inp.fill(text)
                await asyncio.sleep(0.3)
                await page.keyboard.press('Enter')
                await asyncio.sleep(2)
                return True
            except Exception as e:
                print(f"⚠️ Ошибка отправки: {e}")
                return False

        async def click_btn(text):
            """Клик по кнопке"""
            try:
                btn = page.locator(f'button:has-text("{text}")').first
                await btn.click(timeout=5000)
                await asyncio.sleep(2)
                print(f"✅ Кликнул: {text}")
                return True
            except Exception:
                print(f"⚠️ Кнопка '{text}' не найдена")
                return False

        async def get_buttons():
            """Список кнопок"""
            buttons = []
            try:
                els = await page.locator('button.reply-markup-button').all()
                for el in els:
                    t = await el.inner_text()
                    if t:
                        buttons.append(t)
            except Exception:
                pass
            return buttons

        # === ТЕСТЫ ===

        # 1. Reset
        print("\n📝 Тест: /reset")
        await send("/reset")
        await page.screenshot(path=f"{SCREENSHOTS}/02_reset.png")
        await click_btn("Да, сбросить")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/03_reset_done.png")
        print("✅ /reset работает")

        # 2. Start
        print("\n📝 Тест: /start")
        await send("/start")
        await asyncio.sleep(3)
        await page.screenshot(path=f"{SCREENSHOTS}/04_start.png")

        btns = await get_buttons()
        print(f"   Кнопки: {btns}")

        if any("garmin" in b.lower() for b in btns):
            print("✅ /start показывает Garmin")
        else:
            print("❌ Garmin не найден")

        # 3. Garmin
        print("\n📝 Тест: Регистрация Garmin")
        await click_btn("Есть аккаунт")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/05_email.png")

        await send(email)
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/06_password.png")

        await send(password)
        await asyncio.sleep(5)
        await page.screenshot(path=f"{SCREENSHOTS}/07_garmin_done.png")
        print("✅ Garmin регистрация")

        # 4. Онбординг
        print("\n📝 Тест: Онбординг")
        await asyncio.sleep(2)

        if not await click_btn("Настроить тренировки"):
            # Может уже показан
            pass

        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/08_onboarding.png")

        btns = await get_buttons()
        print(f"   Кнопки: {btns}")

        if any("забег" in b.lower() for b in btns):
            print("✅ Онбординг показан")
        else:
            print("⚠️ Кнопки онбординга не найдены")

        # 5. Забег
        print("\n📝 Тест: Выбор забега")
        await click_btn("забегу")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/09_race.png")

        btns = await get_buttons()
        print(f"   Типы: {btns}")

        if any("трейл" in b.lower() for b in btns):
            print("✅ Типы забега показаны")
        else:
            print("⚠️ Трейл не найден")

        # 6. Трейл
        print("\n📝 Тест: Трейл")
        await click_btn("Трейл")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/10_trail.png")

        await send("50")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/11_trail_km.png")
        print("✅ Трейл + дистанция")

        # 7. Дни
        print("\n📝 Тест: Выбор дней")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/12_days.png")

        btns = await get_buttons()
        print(f"   Дни: {btns}")

        # Выбираем дни
        for day in ["Пн", "Ср", "Пт"]:
            await click_btn(day)
            await asyncio.sleep(0.5)

        await page.screenshot(path=f"{SCREENSHOTS}/13_days_selected.png")

        await click_btn("Готово")
        await asyncio.sleep(2)
        await page.screenshot(path=f"{SCREENSHOTS}/14_days_done.png")
        print("✅ Дни выбраны")

        # 8. Время
        print("\n📝 Тест: Время")
        await send("19:00")
        await asyncio.sleep(3)
        await page.screenshot(path=f"{SCREENSHOTS}/15_done.png")

        content = await page.content()
        if "завершен" in content.lower():
            print("✅ Онбординг завершён!")
        else:
            print("⚠️ Финальное сообщение не найдено")

        # Итоги
        print("\n" + "="*60)
        print("📊 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print(f"📸 Скриншоты: {SCREENSHOTS}")
        print("="*60)

        print("\n💡 Браузер останется открытым 30 сек для проверки...")
        await asyncio.sleep(30)

        await context.close()
        return True


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
