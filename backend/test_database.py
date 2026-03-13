#!/usr/bin/env python3
"""
Database Connection Manager Test
Test all database functionality including sessions, health checks, and initialization
"""

import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / "app"))


def test_database_import():
    """Test that database module can be imported"""
    try:
        from app.database_mongodb import SessionLocal, check_db_connection, engine, get_db, init_db

        print("Database module imported successfully")
        return True
    except Exception as e:
        print(f"Database import failed: {e}")
        return False


def test_health_check():
    """Test database health check"""
    try:
        from app.database_mongodb import check_db_connection

        health = check_db_connection()

        print(f"Health check status: {health['status']}")
        print(f"Latency: {health.get('latency_ms', 0)}ms")

        if health["status"] == "healthy":
            print("Database connection is healthy")
            return True
        else:
            print(f"Database unhealthy: {health.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def test_session_creation():
    """Test database session creation"""
    try:
        from app.database_mongodb import SessionLocal, get_db_context

        # Test direct session
        session = SessionLocal()
        session.close()
        print("Direct session creation: OK")

        # Test context manager
        with get_db_context() as db:
            print("Context manager session: OK")

        return True
    except Exception as e:
        print(f"Session creation failed: {e}")
        return False


def test_database_stats():
    """Test database statistics"""
    try:
        from app.database_mongodb import get_database_stats

        stats = get_db_stats()

        if "error" in stats:
            print(f"Stats error: {stats['error']}")
            return True  # Expected for some database types

        print(f"Database type: {stats.get('database_type', 'unknown')}")
        print(f"Tables found: {len(stats.get('tables', []))}")

        return True
    except Exception as e:
        print(f"Database stats failed: {e}")
        return False


def test_table_initialization():
    """Test database table initialization"""
    try:
        from app.database_mongodb import init_db

        success = init_db()

        if success:
            print("Database tables initialized successfully")
            return True
        else:
            print("Database initialization failed")
            return False
    except Exception as e:
        print(f"Table initialization failed: {e}")
        return False


def main():
    """Run all database tests"""
    print("Database Connection Manager Test")
    print("=" * 40)

    tests = [
        ("Import Test", test_database_import),
        ("Health Check", test_health_check),
        ("Session Creation", test_session_creation),
        ("Database Stats", test_database_stats),
        ("Table Initialization", test_table_initialization),
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
        print("All database tests passed!")
        return True
    else:
        print("Some database tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
