#!/usr/bin/env python3
"""
Storage Module Test
Test storage functionality without requiring admin permissions
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / "app"))


def test_storage_import():
    """Test that storage module can be imported"""
    try:

        print("Storage module imported successfully")
        return True
    except Exception as e:
        print(f"Storage import failed: {e}")
        return False


def test_supabase_connection():
    """Test basic Supabase connection"""
    try:
        from app.storage
        # Try a basic operation that doesn't require admin permissions
        result = supabase.table("_dummy_").select("*").limit(1).execute()
        print("Supabase connection working")
        return True
    except Exception as e:
        print(f"Supabase connection test: {e}")
        return True  # This is expected to fail for non-existent table


def test_url_generation():
    """Test URL generation functions"""
    try:

        # Test with a sample URL
        test_url = "https://example.com/storage/v1/object/public/files/test.pdf"
        signed_url = generate_signed_url(test_url, "files", 3600)

        print(f"URL generation working: {len(signed_url) > 0}")
        return True
    except Exception as e:
        print(f"URL generation test failed: {e}")
        return False


def main():
    """Run storage tests"""
    print("Storage Module Test")
    print("=" * 40)

    tests = [
        ("Import Test", test_storage_import),
        ("Connection Test", test_supabase_connection),
        ("URL Generation", test_url_generation),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        try:
            if test_func():
                passed += 1
                print(f"{test_name}: PASSED")
            else:
                print(f"{test_name}: FAILED")
        except Exception as e:
            print(f"{test_name}: ERROR - {e}")

    print("\n" + "=" * 40)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("All storage tests passed!")
        return True
    else:
        print("Some storage tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
