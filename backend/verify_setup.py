#!/usr/bin/env python3
"""
Quick setup verification script
"""
import importlib
import sys


def check_package(package_name):
    try:
        module = importlib.import_module(package_name)
        version = getattr(module, "__version__", "Unknown")
        print(f"✓ {package_name}: {version}")
        return True
    except ImportError:
        print(f"✗ {package_name}: Not installed")
        return False


def main():
    print("=== Virtual Environment Setup Verification ===\n")

    # Check Python version
    print(f"Python version: {sys.version}")
    print()

    # Required packages
    packages = ["fastapi", "uvicorn", "pydantic", "pymongo", "motor", "dnspython", "requests", "httpx", "aiofiles"]

    print("Checking required packages:")
    all_good = True
    for package in packages:
        if not check_package(package):
            all_good = False

    print()
    if all_good:
        print("🎉 All packages are installed correctly!")
        print("Your virtual environment is ready to use.")
    else:
        print("❌ Some packages are missing. Run: pip install -r requirements.txt")


if __name__ == "__main__":
    main()
