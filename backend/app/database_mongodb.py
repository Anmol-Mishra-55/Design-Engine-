"""
MongoDB Database Connection Management
Async support with motor driver
"""
import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# Global MongoDB client and database
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo(mongodb_url: str, database_name: str) -> AsyncIOMotorDatabase:
    """
    Connect to MongoDB

    Args:
        mongodb_url: MongoDB connection string
        database_name: Database name

    Returns:
        AsyncDatabase instance
    """
    global _client, _db

    try:
        _client = AsyncIOMotorClient(mongodb_url, serverSelectionTimeoutMS=5000)
        _db = _client[database_name]

        # Test connection
        await _client.admin.command("ping")
        logger.info(f"Connected to MongoDB: {database_name}")

        # Create indexes
        await create_indexes()

        return _db
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        raise


async def close_mongo_connection():
    """Close MongoDB connection"""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect_to_mongo first.")
    return _db


async def create_indexes():
    """Create necessary indexes"""
    db = get_database()

    # User collection indexes
    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    await db.users.create_index("created_at", DESCENDING)

    # Spec collection indexes
    await db.specs.create_index("user_id", ASCENDING)
    await db.specs.create_index("created_at", DESCENDING)
    await db.specs.create_index("city", ASCENDING)
    await db.specs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    # Iteration collection indexes
    await db.iterations.create_index("spec_id", ASCENDING)
    await db.iterations.create_index("user_id", ASCENDING)
    await db.iterations.create_index("created_at", DESCENDING)

    # Evaluation collection indexes
    await db.evaluations.create_index("spec_id", ASCENDING)
    await db.evaluations.create_index("created_at", DESCENDING)

    # RL Feedback collection indexes
    await db.rl_feedback.create_index("spec_id", ASCENDING)
    await db.rl_feedback.create_index("user_id", ASCENDING)
    await db.rl_feedback.create_index("created_at", DESCENDING)

    # Audit Log collection indexes
    await db.audit_logs.create_index("user_id", ASCENDING)
    await db.audit_logs.create_index("action", ASCENDING)
    await db.audit_logs.create_index("created_at", DESCENDING)
    await db.audit_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

    # Compliance Check collection indexes
    await db.compliance_checks.create_index("spec_id", ASCENDING)
    await db.compliance_checks.create_index("city", ASCENDING)
    await db.compliance_checks.create_index("created_at", DESCENDING)

    # Workflow Run collection indexes
    await db.workflow_runs.create_index("user_id", ASCENDING)
    await db.workflow_runs.create_index("status", ASCENDING)
    await db.workflow_runs.create_index("created_at", DESCENDING)

    # Refresh Token collection indexes
    await db.refresh_tokens.create_index("user_id", ASCENDING)
    await db.refresh_tokens.create_index("expires_at", ASCENDING)
    await db.refresh_tokens.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    logger.info("MongoDB indexes created successfully")


async def check_db_connection() -> dict:
    """
    Comprehensive database health check

    Returns:
        dict with status and latency
    """
    import time

    start_time = time.time()

    try:
        db = get_database()
        await db.command("ping")
        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "database": "mongodb",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "latency_ms": round((time.time() - start_time) * 1000, 2),
        }


async def get_db_stats() -> dict:
    """Get detailed database statistics"""
    try:
        db = get_database()

        # Get collection stats
        collections = await db.list_collection_names()
        stats = {
            "database": "mongodb",
            "collections": [],
        }

        for collection_name in collections:
            collection = db[collection_name]
            count = await collection.count_documents({})
            stats["collections"].append(
                {
                    "name": collection_name,
                    "documents": count,
                }
            )

        return stats
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {"error": str(e)}


__all__ = [
    "connect_to_mongo",
    "close_mongo_connection",
    "get_database",
    "check_db_connection",
    "get_db_stats",
]
