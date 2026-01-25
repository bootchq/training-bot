#!/usr/bin/env python3
"""
E2E тест онбординга через Chrome DevTools
Автоматически кликает по кнопкам, проверяет flow
"""

import subprocess
import time
import os
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TELEGRAM_WEB = "https://web.telegram.org/k/"
BOT_USERNAME = "training_dag_run_bot"
SCREENSHOTS_DIR = "/Users/noor/Documents/Obsidian Vault/Бот тренера/screenshots"
USER_DATA_DIR = os.path.expanduser("~/Library/Application Support/Google/Chrome")

class OnboardingTester:
    def __init__(self):
        self.driver = None
        self.chrome_process = None
        self.results = []

    def log(self, msg, status="info"):
        icons = {"ok": "✅", "fail": "❌", "warn": "⚠️", "info": "📝"}
        print(f"{icons.get(status, '•')} {msg}", flush=True)
        self.results.append((status, msg))

    def start_chrome(self):
        """Подключение к Chrome с remote debugging (НЕ запускает новый!)"""
        self.log("Подключаюсь к Chrome (порт 9222)...")

        # НЕ закрываем Chrome! Подключаемся к существующему
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.log("Chrome подключен", "ok")
        except Exception as e:
            self.log(f"Не могу подключиться к Chrome: {e}", "fail")
            self.log("Запусти Chrome вручную:", "info")
            self.log('"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 "https://web.telegram.org/k/"', "info")
            raise

    def check_auth(self):
        """Проверка авторизации в Telegram"""
        self.log("Проверка авторизации...")
        time.sleep(3)

        page = self.driver.page_source
        if 'Log in' in page or 'Sign in' in page or 'QR' in page:
            self.log("Требуется авторизация в Telegram!", "fail")
            self.log("Авторизуйся вручную, потом перезапусти тест")
            return False

        self.log("Авторизован в Telegram", "ok")
        return True

    def open_bot(self):
        """Открытие чата с ботом"""
        self.log(f"Открываю бота @{BOT_USERNAME}...")

        self.driver.get(f"https://web.telegram.org/k/#{BOT_USERNAME}")
        time.sleep(4)

        self.screenshot("01_bot_opened")
        self.log("Бот открыт", "ok")

    def send_message(self, text):
        """Отправка сообщения"""
        selectors = [
            'div[contenteditable="true"]',
            '.input-message-input',
            'div.input-message-input'
        ]

        for sel in selectors:
            try:
                inp = self.driver.find_element(By.CSS_SELECTOR, sel)
                inp.click()
                time.sleep(0.3)
                inp.send_keys(text)
                time.sleep(0.3)
                inp.send_keys(Keys.ENTER)
                time.sleep(2)
                return True
            except:
                continue

        return False

    def click_button(self, text_contains):
        """Клик по кнопке с текстом"""
        time.sleep(1)

        selectors = [
            'button.reply-markup-button',
            'button[class*="Button"]',
            '.reply-markup button'
        ]

        for sel in selectors:
            try:
                buttons = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in buttons:
                    if text_contains.lower() in btn.text.lower():
                        btn.click()
                        time.sleep(2)
                        return True
            except:
                continue

        return False

    def get_buttons(self):
        """Получить список кнопок"""
        buttons = []
        selectors = [
            'button.reply-markup-button',
            'button[class*="Button"]'
        ]

        for sel in selectors:
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in found:
                    if btn.text:
                        buttons.append(btn.text)
            except:
                continue

        return buttons

    def screenshot(self, name):
        """Сохранение скриншота"""
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        path = f"{SCREENSHOTS_DIR}/{name}.png"
        self.driver.save_screenshot(path)

    def test_reset(self):
        """Тест /reset"""
        self.log("Отправляю /reset...")
        self.send_message("/reset")
        time.sleep(2)
        self.screenshot("02_reset")

        # Кликаем подтверждение
        if self.click_button("Да, сбросить"):
            self.log("/reset + подтверждение работает", "ok")
            time.sleep(2)
            self.screenshot("03_reset_confirmed")
            return True
        else:
            self.log("Кнопка подтверждения не найдена", "warn")
            return False

    def test_start(self):
        """Тест /start"""
        self.log("Отправляю /start...")
        self.send_message("/start")
        time.sleep(3)
        self.screenshot("04_start")

        buttons = self.get_buttons()
        self.log(f"Кнопки после /start: {buttons}")

        if "Есть аккаунт Garmin" in str(buttons) or "Garmin" in str(buttons):
            self.log("/start показывает кнопки Garmin", "ok")
            return True
        else:
            self.log("Кнопки Garmin не найдены", "fail")
            return False

    def test_garmin_registration(self, email, password):
        """Тест регистрации Garmin"""
        self.log("Кликаю 'Есть аккаунт Garmin'...")

        if not self.click_button("Есть аккаунт"):
            self.log("Кнопка не найдена", "fail")
            return False

        time.sleep(2)
        self.screenshot("05_garmin_email")

        # Вводим email
        self.log(f"Ввожу email: {email}")
        self.send_message(email)
        time.sleep(2)
        self.screenshot("06_garmin_password")

        # Вводим пароль
        self.log("Ввожу пароль...")
        self.send_message(password)
        time.sleep(5)
        self.screenshot("07_garmin_done")

        self.log("Регистрация Garmin завершена", "ok")
        return True

    def test_onboarding_start(self):
        """Тест начала онбординга"""
        self.log("Кликаю 'Настроить тренировки'...")
        time.sleep(2)

        if self.click_button("Настроить тренировки") or self.click_button("тренировки"):
            time.sleep(2)
            self.screenshot("08_onboarding_start")

            buttons = self.get_buttons()
            self.log(f"Кнопки онбординга: {buttons}")

            if "забегу" in str(buttons).lower() or "для себя" in str(buttons).lower():
                self.log("Онбординг показывает правильные кнопки", "ok")
                return True

        self.log("Кнопка онбординга не найдена", "warn")
        return False

    def test_goal_race(self):
        """Тест выбора цели - забег"""
        self.log("Кликаю 'Подготовка к забегу'...")

        if self.click_button("забегу"):
            time.sleep(2)
            self.screenshot("09_goal_race")

            buttons = self.get_buttons()
            self.log(f"Типы забега: {buttons}")

            expected = ["Полумарафон", "Марафон", "Своя", "Трейл"]
            found = sum(1 for e in expected if e.lower() in str(buttons).lower())

            if found >= 3:
                self.log("Типы забега показаны правильно", "ok")
                return True

        self.log("Типы забега не найдены", "fail")
        return False

    def test_race_type_trail(self):
        """Тест выбора трейла"""
        self.log("Кликаю 'Трейл'...")

        if self.click_button("Трейл"):
            time.sleep(2)
            self.screenshot("10_trail")

            # Должен запросить дистанцию
            page = self.driver.page_source
            if "дистанц" in page.lower() or "км" in page.lower():
                self.log("Запрос дистанции трейла работает", "ok")

                # Вводим дистанцию
                self.log("Ввожу дистанцию 50 км...")
                self.send_message("50")
                time.sleep(2)
                self.screenshot("11_trail_distance")
                return True

        self.log("Трейл не работает", "fail")
        return False

    def test_days_selection(self):
        """Тест выбора дней"""
        time.sleep(2)
        buttons = self.get_buttons()
        self.log(f"Кнопки дней: {buttons}")

        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        found = sum(1 for d in days if d in str(buttons))

        if found >= 5:
            self.log("Кнопки дней показаны", "ok")
            self.screenshot("12_days")

            # Кликаем Пн, Ср, Пт
            for day in ["Пн", "Ср", "Пт"]:
                if self.click_button(day):
                    self.log(f"Выбран {day}", "ok")
                    time.sleep(1)

            self.screenshot("13_days_selected")

            # Кликаем Готово
            if self.click_button("Готово"):
                time.sleep(2)
                self.screenshot("14_days_done")
                self.log("Выбор дней завершён", "ok")
                return True

        self.log("Выбор дней не работает", "fail")
        return False

    def test_time_input(self):
        """Тест ввода времени"""
        time.sleep(2)
        page = self.driver.page_source

        if "время" in page.lower() or "07:00" in page or "19:30" in page:
            self.log("Запрос времени показан")

            self.send_message("19:00")
            time.sleep(3)
            self.screenshot("15_time_done")

            page = self.driver.page_source
            if "завершен" in page.lower() or "Настройка" in page:
                self.log("Онбординг завершён успешно!", "ok")
                return True

        self.log("Ввод времени не работает", "fail")
        return False

    def run_full_test(self, garmin_email, garmin_password):
        """Полный тест онбординга"""
        print("="*70, flush=True)
        print("🧪 E2E ТЕСТ ОНБОРДИНГА", flush=True)
        print("="*70, flush=True)
        print(flush=True)

        try:
            self.start_chrome()

            if not self.check_auth():
                return False

            self.open_bot()

            # Reset
            self.test_reset()
            time.sleep(2)

            # Start
            if not self.test_start():
                return False

            # Garmin registration
            if not self.test_garmin_registration(garmin_email, garmin_password):
                return False

            # Onboarding
            if not self.test_onboarding_start():
                # Может показать кнопки сразу после регистрации
                buttons = self.get_buttons()
                if "забегу" in str(buttons).lower():
                    self.log("Кнопки онбординга уже показаны", "ok")
                else:
                    return False

            # Goal selection
            if not self.test_goal_race():
                return False

            # Trail
            if not self.test_race_type_trail():
                return False

            # Days
            if not self.test_days_selection():
                return False

            # Time
            self.test_time_input()

            # Итоги
            print(flush=True)
            print("="*70, flush=True)
            print("📊 РЕЗУЛЬТАТЫ ТЕСТА", flush=True)
            print("="*70, flush=True)

            passed = sum(1 for s, _ in self.results if s == "ok")
            failed = sum(1 for s, _ in self.results if s == "fail")

            print(f"✅ Passed: {passed}", flush=True)
            print(f"❌ Failed: {failed}", flush=True)
            print(f"📸 Скриншоты: {SCREENSHOTS_DIR}", flush=True)
            print(flush=True)

            if failed == 0:
                print("🎉 ВСЕ ТЕСТЫ ПРОШЛИ!", flush=True)
                return True
            else:
                print("❌ ЕСТЬ ПРОБЛЕМЫ", flush=True)
                return False

        except Exception as e:
            self.log(f"Ошибка: {e}", "fail")
            import traceback
            traceback.print_exc()
            return False

        finally:
            if self.driver:
                self.screenshot("99_final")
                # НЕ закрываем Chrome! Оставляем открытым
                self.driver.quit()  # Только отключаемся от сессии


if __name__ == "__main__":
    # Garmin credentials из аргументов или по умолчанию
    email = sys.argv[1] if len(sys.argv) > 1 else "bootchq@gmail.com"
    password = sys.argv[2] if len(sys.argv) > 2 else "Aa1424617556"

    tester = OnboardingTester()
    success = tester.run_full_test(email, password)
    sys.exit(0 if success else 1)
