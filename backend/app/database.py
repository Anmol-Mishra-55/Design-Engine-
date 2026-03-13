"""
Legacy Database Module - DEPRECATED
This project now uses MongoDB exclusively.
This file exists only to prevent import errors.
"""
import logging

from app.database_mongodb import get_database

logger = logging.getLogger(__name__)


# Redirect all database operations to MongoDB
def get_db():
    """Legacy function - redirects to MongoDB"""
    logger.warning("Legacy get_db() called - use MongoDB database_mongodb.get_database() instead")
    return get_database()


# Deprecated - project uses MongoDB only
logger.warning("database.py is deprecated - project uses MongoDB exclusively via database_mongodb.py")
