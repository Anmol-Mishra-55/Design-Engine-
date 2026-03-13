#!/usr/bin/env python3
"""
Quick test script to verify the virtual environment setup
"""
import sys
import os

def test_imports():
    """Test all critical imports"""
    print("Testing imports...")

    try:
        import fastapi
        print(f"[OK] FastAPI {fastapi.__version__}")
    except ImportError as e:
        print(f"[ERROR] FastAPI: {e}")
        return False

    try:
        import pymongo
        print(f"[OK] PyMongo {pymongo.__version__}")
    except ImportError as e:
        print(f"[ERROR] PyMongo: {e}")
        return False

    try:
        import motor
        print(f"[OK] Motor {motor.version}")
    except ImportError as e:
        print(f"[ERROR] Motor: {e}")
        return False

    try:
        import pydantic
        print(f"[OK] Pydantic {pydantic.__version__}")
    except ImportError as e:
        print(f"[ERROR] Pydantic: {e}")
        return False

    try:
        import uvicorn
        print(f"[OK] Uvicorn {uvicorn.__version__}")
    except ImportError as e:
        print(f"[ERROR] Uvicorn: {e}")
        return False

    return True

def test_mongodb_config():
    """Test MongoDB configuration loading"""
    print("\nTesting MongoDB configuration...")

    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
        from app.config_mongodb import settings
        print(f"[OK] MongoDB config loaded")
        print(f"  Database: {settings.MONGODB_DATABASE}")
        print(f"  URL configured: {'Yes' if settings.MONGODB_URL else 'No'}")
        return True
    except Exception as e:
        print(f"[ERROR] MongoDB config: {e}")
        return False

def main():
    print("=" * 50)
    print("Virtual Environment Setup Verification")
    print("=" * 50)

    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Virtual env: {os.environ.get('VIRTUAL_ENV', 'Not detected')}")
    print()

    imports_ok = test_imports()
    config_ok = test_mongodb_config()

    print("\n" + "=" * 50)
    if imports_ok and config_ok:
        print("[SUCCESS] All tests passed! Environment is ready.")
        print("\nNext steps:")
        print("1. Configure your .env file with MongoDB credentials")
        print("2. Run: cd backend && python -m uvicorn app.main:app --reload")
    else:
        print("[FAILED] Some tests failed. Check the errors above.")
    print("=" * 50)

if __name__ == "__main__":
    main()
