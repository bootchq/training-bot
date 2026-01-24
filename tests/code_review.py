"""
Автоматическая проверка кода бота
Проверяет синтаксис, импорты, потенциальные ошибки
"""
import py_compile
import os
import sys
from pathlib import Path


class CodeReviewer:
    """Автоматический ревьюер кода"""

    def __init__(self):
        """Инициализация"""
        self.project_root = Path(__file__).parent.parent
        self.src_dir = self.project_root / "src"
        self.issues = []
        self.checked_files = 0

    def check_syntax(self, filepath):
        """Проверка синтаксиса Python файла"""
        try:
            py_compile.compile(filepath, doraise=True)
            return True, None
        except py_compile.PyCompileError as e:
            return False, str(e)

    def check_file(self, filepath):
        """Проверка одного файла"""
        print(f"  Проверяю: {filepath.name}")

        # Проверка синтаксиса
        syntax_ok, error = self.check_syntax(filepath)
        if not syntax_ok:
            self.issues.append(f"❌ СИНТАКСИС: {filepath.name} - {error}")
            return False

        # Читаем файл
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Проверки
        checks = []

        # 1. parse_mode='Markdown' везде где есть **
        if '**' in content and 'reply_text' in content:
            if "parse_mode='Markdown'" not in content and 'parse_mode="Markdown"' not in content:
                checks.append("⚠️  Есть ** но нет parse_mode='Markdown'")

        # 2. Проверка async def без await
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if 'async def' in line and i + 20 < len(lines):
                # Проверяем следующие 20 строк на наличие await
                chunk = '\n'.join(lines[i:i+20])
                if 'await' not in chunk and 'asyncio' not in chunk:
                    checks.append(f"⚠️  Строка {i}: async def без await")

        # 3. Проверка TODO/FIXME
        for i, line in enumerate(lines, 1):
            if 'TODO' in line or 'FIXME' in line:
                checks.append(f"📝 Строка {i}: {line.strip()}")

        # 4. Проверка hardcoded credentials
        dangerous_patterns = ['password =', 'token =', 'api_key =', 'secret =']
        for i, line in enumerate(lines, 1):
            for pattern in dangerous_patterns:
                if pattern in line.lower() and '=' in line and '"' in line:
                    if 'config' not in line.lower() and 'env' not in line.lower():
                        checks.append(f"🔐 Строка {i}: Возможно hardcoded credential")

        if checks:
            self.issues.extend([f"  {check} ({filepath.name})" for check in checks])

        self.checked_files += 1
        return True

    def scan_directory(self, directory):
        """Сканирование директории"""
        print(f"\n📂 Сканирую: {directory.relative_to(self.project_root)}")

        for filepath in directory.rglob("*.py"):
            if '__pycache__' in str(filepath) or 'venv' in str(filepath):
                continue
            self.check_file(filepath)

    def print_summary(self):
        """Итоговый отчёт"""
        print("\n" + "=" * 60)
        print("📊 РЕЗУЛЬТАТЫ ПРОВЕРКИ КОДА")
        print("=" * 60)

        print(f"\n✅ Проверено файлов: {self.checked_files}")

        if self.issues:
            print(f"⚠️  Найдено замечаний: {len(self.issues)}\n")

            # Группируем по типу
            syntax_errors = [i for i in self.issues if '❌ СИНТАКСИС' in i]
            warnings = [i for i in self.issues if '⚠️' in i]
            notes = [i for i in self.issues if '📝' in i or '🔐' in i]

            if syntax_errors:
                print("🚨 КРИТИЧЕСКИЕ ОШИБКИ:")
                for issue in syntax_errors:
                    print(f"  {issue}")
                print()

            if warnings:
                print("⚠️  ПРЕДУПРЕЖДЕНИЯ:")
                for issue in warnings:
                    print(f"  {issue}")
                print()

            if notes:
                print("📝 ЗАМЕТКИ:")
                for issue in notes:
                    print(f"  {issue}")
                print()

        else:
            print("🎉 Замечаний не найдено! Код чистый.")

        print("=" * 60)

    def run(self):
        """Запуск проверки"""
        print("🔍 Автоматическая проверка кода бота")
        print("=" * 60)

        # Проверяем основные директории
        directories = [
            self.src_dir / "bot",
            self.src_dir / "core",
            self.src_dir / "database",
            self.src_dir / "integrations",
            self.src_dir / "utils",
        ]

        for directory in directories:
            if directory.exists():
                self.scan_directory(directory)

        self.print_summary()

        # Возвращаем код выхода
        return 0 if not any('❌' in i for i in self.issues) else 1


if __name__ == "__main__":
    reviewer = CodeReviewer()
    exit_code = reviewer.run()
    sys.exit(exit_code)
