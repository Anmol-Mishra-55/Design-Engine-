#!/usr/bin/env python3
"""
Test imports to identify the exact issue
"""
import sys
import traceback


def test_import(module_name):
    try:
        __import__(module_name)
        print(f"[OK] {module_name}")
        return True
    except Exception as e:
        print(f"[ERROR] {module_name}: {e}")
        traceback.print_exc()
        return False


def main():
    print("Testing critical imports...")

    modules_to_test = [
        "app.config_mongodb",
        "app.database_mongodb",
        "app.utils",
        "app.api.auth",
        "app.api.health",
        "app.api.generate",
        "app.lm_adapter",
        "app.main_clean",
    ]

    for module in modules_to_test:
        test_import(module)
        print()


if __name__ == "__main__":
    main()
