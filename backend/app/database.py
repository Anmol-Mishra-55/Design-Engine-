"""
Legacy Database Module - DEPRECATED
This project uses MongoDB exclusively via database_mongodb.py.
This file exists only to prevent import errors in legacy code.
"""
from app.database_mongodb import get_database


def get_db():
    """Legacy shim - returns the async Motor database instance."""
    return get_database()
