#!/usr/bin/env python3
"""
Автоматическое тестирование Telegram бота через Desktop приложение.
Использует AppleScript для управления окном и pyautogui для кликов.
"""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from typing import List
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    print("Установи pyautogui: pip3 install pyautogui")
    exit(1)


@dataclass
class TestResult:
    """Результат теста"""
    name: str
    passed: bool
    message: str
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None


class TelegramTester:
    """Класс для автоматического тестирования Telegram бота"""

    APP_NAME = "Telegram 2"
    APP_PATH = "/Applications/Telegram 2.app"
    BOT_USERNAME = "training_dag_run_bot"
    SCREENSHOT_DIR = Path("/tmp/tg_tests")

    def __init__(self):
        self.window_pos = (0, 0)
        self.window_size = (0, 0)
        self.results: List[TestResult] = []
        self.SCREENSHOT_DIR.mkdir(exist_ok=True)

    def activate_and_get_window(self) -> bool:
        """Активировать Telegram и получить позицию окна"""
        result = subprocess.run([
            'osascript', '-e', f'''
            tell application "{self.APP_PATH}" to activate
            delay 0.5
            tell application "System Events"
                set frontProc to first process whose frontmost is true
                tell frontProc
                    set winPos to position of window 1
                    set winSize to size of window 1
                    return (item 1 of winPos as text) & "," & (item 2 of winPos as text) & "," & (item 1 of winSize as text) & "," & (item 2 of winSize as text)
                end tell
            end tell
            '''
        ], capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(',')
            self.window_pos = (int(parts[0]), int(parts[1]))
            self.window_size = (int(parts[2]), int(parts[3]))
            print(f"Окно: pos={self.window_pos}, size={self.window_size}")
            return True
        return False

    def open_bot(self) -> bool:
        """Открыть чат с ботом"""
        subprocess.run(['open', f'tg://resolve?domain={self.BOT_USERNAME}'], check=True)
        time.sleep(3)
        self.activate_and_get_window()
        return True

    def screenshot(self, name: str) -> str:
        """Сделать скриншот"""
        safe_name = name.replace('/', '_').replace(' ', '_')
        path = self.SCREENSHOT_DIR / f"{safe_name}_{int(time.time())}.png"
        subprocess.run(['screencapture', '-x', str(path)], check=True)
        return str(path)

    def ensure_bot_chat(self) -> bool:
        """Убедиться что открыт чат с ботом"""
        # Переоткрываем бота через deep link
        subprocess.run(['open', f'tg://resolve?domain={self.BOT_USERNAME}'], check=True)
        time.sleep(1.5)
        self.activate_and_get_window()
        return True

    def send_text(self, text: str) -> bool:
        """Отправить текст через clipboard + paste"""
        # Сначала убедимся что мы в чате с ботом
        self.ensure_bot_chat()

        # Копируем текст в clipboard
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))

        # Кликаем в поле ввода (правая панель, внизу)
        # Поле ввода примерно: x = центр правой панели, y = низ окна - 40px
        chat_area_x = self.window_pos[0] + int(self.window_size[0] * 0.65)
        input_y = self.window_pos[1] + self.window_size[1] - 40

        pyautogui.click(chat_area_x, input_y)
        time.sleep(0.2)

        # Paste (Cmd+V)
        pyautogui.hotkey('command', 'v')
        time.sleep(0.2)

        # Enter
        pyautogui.press('enter')
        time.sleep(1.5)

        return True

    def click_inline_button(self, row: int = 0, col: int = 0) -> bool:
        """
        Кликнуть по inline кнопке в чате.
        row: ряд (0 = нижний ряд кнопок)
        col: колонка (0 = левая кнопка)
        """
        # Сначала активируем Telegram и обновим позицию окна
        self.ensure_bot_chat()
        time.sleep(0.5)

        # В Telegram Desktop:
        # - Левая панель (список чатов) ~ 25% ширины
        # - Правая панель (чат) ~ 75% ширины
        # - Кнопки находятся внизу области чата, над полем ввода

        # Позиция центра области чата (правая панель)
        chat_center_x = self.window_pos[0] + int(self.window_size[0] * 0.6)

        # Кнопки примерно на 75-80% высоты окна (над зелёной кнопкой Меню)
        # Ряд 0 = нижний ряд (Синхронизация, Календарь)
        # Ряд 1 = верхний ряд (Статистика, План)
        buttons_y = self.window_pos[1] + int(self.window_size[1] * 0.78) - row * 35

        # Колонки: 2 кнопки в ряду, ~100px между центрами
        # col=0 = левая, col=1 = правая
        button_offset = (col - 0.5) * 100  # -50 для col=0, +50 для col=1
        buttons_x = chat_center_x + int(button_offset)

        print(f"Клик по кнопке row={row}, col={col} -> ({buttons_x}, {buttons_y})")
        print(f"Окно: {self.window_pos}, {self.window_size}")

        # Активируем окно перед кликом
        subprocess.run([
            'osascript', '-e',
            f'tell application "{self.APP_PATH}" to activate'
        ], capture_output=True)
        time.sleep(0.3)

        pyautogui.moveTo(buttons_x, buttons_y, duration=0.3)
        time.sleep(0.2)
        pyautogui.click()
        time.sleep(2)

        return True

    def run_test(self, name: str, test_func: Callable) -> TestResult:
        """Запустить тест"""
        print(f"\n{'='*50}")
        print(f"ТЕСТ: {name}")
        print('='*50)

        screenshot_before = self.screenshot(f"{name}_before")

        try:
            passed, message = test_func()
            screenshot_after = self.screenshot(f"{name}_after")
            result = TestResult(name, passed, message, screenshot_before, screenshot_after)
        except Exception as e:
            screenshot_after = self.screenshot(f"{name}_error")
            result = TestResult(name, False, f"Ошибка: {e}", screenshot_before, screenshot_after)

        status = "✅" if result.passed else "❌"
        print(f"{status} {result.message}")

        self.results.append(result)
        return result

    def setup(self) -> bool:
        """Подготовка"""
        print("Подготовка...")
        if not self.activate_and_get_window():
            return False
        if not self.open_bot():
            return False
        print("Готов к тестированию")
        return True

    def summary(self):
        """Итоги"""
        print("\n" + "="*50)
        print("ИТОГИ")
        print("="*50)
        passed = sum(1 for r in self.results if r.passed)
        for r in self.results:
            print(f"{'✅' if r.passed else '❌'} {r.name}")
        print(f"\nВсего: {passed}/{len(self.results)}")


# === ТЕСТЫ ===

def test_start(tester: TelegramTester) -> tuple:
    """Тест /start"""
    tester.send_text("/start")
    time.sleep(2)
    return True, "/start отправлен"


def test_help(tester: TelegramTester) -> tuple:
    """Тест /help"""
    tester.send_text("/help")
    time.sleep(2)
    return True, "/help отправлен"


def test_button_stats(tester: TelegramTester) -> tuple:
    """Тест кнопки Статистика"""
    # Сначала /start для получения кнопок
    tester.send_text("/start")
    time.sleep(2)
    # Кнопка "Статистика" - первая в первом ряду
    tester.click_inline_button(row=0, col=0)
    return True, "Кнопка Статистика нажата"


def test_button_plan(tester: TelegramTester) -> tuple:
    """Тест кнопки План"""
    tester.send_text("/start")
    time.sleep(2)
    # Кнопка "План" - вторая в первом ряду
    tester.click_inline_button(row=0, col=1)
    return True, "Кнопка План нажата"


def main():
    print("="*50)
    print("TELEGRAM BOT TESTER")
    print("="*50)

    tester = TelegramTester()

    if not tester.setup():
        print("Ошибка подготовки")
        return 1

    # Тесты
    tester.run_test("start", lambda: test_start(tester))
    tester.run_test("help", lambda: test_help(tester))
    tester.run_test("button_stats", lambda: test_button_stats(tester))
    tester.run_test("button_plan", lambda: test_button_plan(tester))

    tester.summary()

    # Показать скриншоты
    print(f"\nСкриншоты: {tester.SCREENSHOT_DIR}")

    return 0 if all(r.passed for r in tester.results) else 1


if __name__ == "__main__":
    exit(main())
