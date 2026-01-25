#!/usr/bin/env python3
"""
Полное тестирование inline кнопок с глубокой JavaScript симуляцией
"""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

BOT_USERNAME = "training_dag_run_bot"

print("=" * 70)
print("🧪 ТЕСТ INLINE КНОПОК С РЕАЛЬНОЙ СИМУЛЯЦИЕЙ")
print("=" * 70)
print()

chrome_options = Options()
chrome_options.add_experimental_option('debuggerAddress', '127.0.0.1:9222')

try:
    driver = webdriver.Chrome(options=chrome_options)

    # Шаг 1: Открываем бота через t.me
    print("📱 ШАГ 1: Открываю бота через t.me...")
    driver.get(f'https://t.me/{BOT_USERNAME}')
    time.sleep(3)

    # Клик на Web Telegram
    web_clicked = driver.execute_script("""
        var buttons = document.querySelectorAll('button, a');
        for (var i = 0; i < buttons.length; i++) {
            var text = (buttons[i].innerText || buttons[i].textContent || '').toLowerCase();
            if (text.includes('web') && text.includes('telegram')) {
                buttons[i].click();
                return 'clicked';
            }
        }
        return 'not_found';
    """)

    if web_clicked == 'clicked':
        print("✅ Кликнул Web Telegram")
        time.sleep(6)
    else:
        print("⚠️  Кнопка Web Telegram не найдена")

    print(f"URL: {driver.current_url}")
    print()

    # Шаг 2: Отправляем /start
    print("📝 ШАГ 2: Отправляю /start...")

    # Ищем поле ввода
    input_found = driver.execute_script("""
        var inputs = document.querySelectorAll('[contenteditable="true"]');
        for (var i = 0; i < inputs.length; i++) {
            var rect = inputs[i].getBoundingClientRect();
            // Ищем большое поле внизу экрана
            if (rect.width > 200 && rect.bottom > window.innerHeight * 0.5) {
                inputs[i].focus();
                inputs[i].textContent = '/start';

                // Отправляем Enter
                var e = new KeyboardEvent('keydown', {
                    key: 'Enter',
                    code: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true,
                    cancelable: true
                });
                inputs[i].dispatchEvent(e);

                return 'sent';
            }
        }
        return 'not_found';
    """)

    if input_found == 'sent':
        print("✅ /start отправлен")
        time.sleep(4)
    else:
        print("⚠️  Поле ввода не найдено")

    print()

    # Шаг 3: Ищем и кликаем inline кнопки
    print("🔘 ШАГ 3: Ищу inline кнопки...")

    buttons = driver.find_elements(By.CSS_SELECTOR, 'button.reply-markup-button')
    print(f"Найдено кнопок: {len(buttons)}")

    if buttons:
        print()
        print("🖱️  ТЕСТИРУЮ КАЖДУЮ КНОПКУ:")
        print("-" * 70)

        for idx, btn in enumerate(buttons[:4], 1):
            try:
                btn_text = btn.text
                print(f"\n{idx}. Кнопка: {btn_text}")

                # Считаем сообщения ДО клика
                messages_before = len(driver.find_elements(By.CSS_SELECTOR, '.message'))

                # ГЛУБОКАЯ СИМУЛЯЦИЯ КЛИКА
                result = driver.execute_script("""
                    var btn = arguments[0];

                    // 1. Скроллим к кнопке
                    btn.scrollIntoView({behavior: 'smooth', block: 'center'});

                    // 2. Фокус
                    btn.focus();

                    // 3. Все mouse события
                    var mouseEvents = ['mouseover', 'mouseenter', 'mousedown', 'mouseup', 'click'];
                    mouseEvents.forEach(function(type) {
                        var evt = new MouseEvent(type, {
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: btn.getBoundingClientRect().left + btn.offsetWidth / 2,
                            clientY: btn.getBoundingClientRect().top + btn.offsetHeight / 2,
                            button: 0,
                            buttons: 1
                        });
                        btn.dispatchEvent(evt);
                    });

                    // 4. Pointer события
                    var pointerEvents = ['pointerover', 'pointerenter', 'pointerdown', 'pointerup'];
                    pointerEvents.forEach(function(type) {
                        var evt = new PointerEvent(type, {
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: btn.getBoundingClientRect().left + btn.offsetWidth / 2,
                            clientY: btn.getBoundingClientRect().top + btn.offsetHeight / 2,
                            button: 0,
                            buttons: 1,
                            isPrimary: true
                        });
                        btn.dispatchEvent(evt);
                    });

                    // 5. Touch события
                    try {
                        var touch = new Touch({
                            identifier: Date.now(),
                            target: btn,
                            clientX: btn.getBoundingClientRect().left + btn.offsetWidth / 2,
                            clientY: btn.getBoundingClientRect().top + btn.offsetHeight / 2,
                            radiusX: 2.5,
                            radiusY: 2.5,
                            rotationAngle: 0,
                            force: 1
                        });

                        var touchStart = new TouchEvent('touchstart', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            touches: [touch],
                            targetTouches: [touch],
                            changedTouches: [touch]
                        });
                        btn.dispatchEvent(touchStart);

                        var touchEnd = new TouchEvent('touchend', {
                            bubbles: true,
                            cancelable: true,
                            view: window,
                            touches: [],
                            targetTouches: [],
                            changedTouches: [touch]
                        });
                        btn.dispatchEvent(touchEnd);
                    } catch(e) {
                        // Touch API может не поддерживаться
                    }

                    return 'all_events_fired';
                """, btn)

                print(f"   ✅ Симуляция: {result}")

                # Ждём ответ
                time.sleep(3)

                # Считаем сообщения ПОСЛЕ
                messages_after = len(driver.find_elements(By.CSS_SELECTOR, '.message'))

                if messages_after > messages_before:
                    print(f"   🎉 РАБОТАЕТ! Бот ответил (+{messages_after - messages_before})")
                else:
                    print(f"   ❌ Бот НЕ ответил (сообщений: {messages_before} → {messages_after})")

            except Exception as e:
                print(f"   ⚠️  Ошибка: {e}")
    else:
        print("❌ Inline кнопки не найдены")
        print("⚠️  Возможно бот не ответил на /start или чат не открылся")

    print()
    print("=" * 70)
    print("✅ ТЕСТ ЗАВЕРШЁН")
    print("=" * 70)

    # Проверяем console errors
    print("\n📋 Последние ошибки в консоли:")
    try:
        logs = driver.get_log('browser')
        errors = [log for log in logs if 'error' in log['level'].lower() or 'severe' in log['level'].lower()]
        if errors:
            for log in errors[-3:]:
                print(f"   {log['level']}: {log['message'][:200]}")
        else:
            print("   Нет ошибок")
    except:
        print("   Не удалось получить логи")

    driver.quit()

except Exception as e:
    print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
