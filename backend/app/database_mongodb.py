"""
MongoDB Database Connection Management
Async support with motor driver - Enhanced with connection resilience
"""
import asyncio
import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# Global MongoDB client and database
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None
_connection_healthy = False


async def connect_to_mongo(mongodb_url: str, database_name: str, max_retries: int = 3) -> AsyncIOMotorDatabase:
    """
    Connect to MongoDB with enhanced resilience

    Args:
        mongodb_url: MongoDB connection string
        database_name: Database name
        max_retries: Maximum connection retry attempts

    Returns:
        AsyncDatabase instance
    """
    global _client, _db, _connection_healthy

    for attempt in range(max_retries):
        try:
            logger.info(f"MongoDB connection attempt {attempt + 1}/{max_retries}")

            # Create client with optimized settings for network issues
            _client = AsyncIOMotorClient(
                mongodb_url,
                serverSelectionTimeoutMS=30000,  # 30 seconds
                connectTimeoutMS=30000,  # 30 seconds
                socketTimeoutMS=30000,  # 30 seconds
                maxPoolSize=10,
                minPoolSize=1,
                maxIdleTimeMS=45000,  # 45 seconds
                waitQueueTimeoutMS=10000,  # 10 seconds
                retryWrites=True,
                retryReads=True,
                # DNS resolution settings
                directConnection=False,
                # Connection pool settings
                maxConnecting=2,
            )

            _db = _client[database_name]

            # Test connection with timeout
            await asyncio.wait_for(_client.admin.command("ping"), timeout=30.0)

            logger.info(f"✅ Connected to MongoDB: {database_name}")
            _connection_healthy = True

            # Create indexes in background (don't block startup)
            asyncio.create_task(create_indexes_safe())

            return _db

        except asyncio.TimeoutError:
            logger.warning(f"MongoDB connection attempt {attempt + 1} timed out")
            if _client:
                _client.close()
                _client = None

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.warning(f"MongoDB connection attempt {attempt + 1} failed: {e}")
            if _client:
                _client.close()
                _client = None

        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            if _client:
                _client.close()
                _client = None

        # Wait before retry (exponential backoff)
        if attempt < max_retries - 1:
            wait_time = 2**attempt  # 1s, 2s, 4s
            logger.info(f"Waiting {wait_time}s before retry...")
            await asyncio.sleep(wait_time)

    # All attempts failed
    logger.error(f"Failed to connect to MongoDB after {max_retries} attempts")
    _connection_healthy = False
    raise ConnectionFailure(f"Could not connect to MongoDB after {max_retries} attempts")


async def close_mongo_connection():
    """Close MongoDB connection"""
    global _client, _connection_healthy
    if _client:
        _client.close()
        _connection_healthy = False
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    """Get MongoDB database instance"""
    if _db is None:
        raise RuntimeError("MongoDB not connected. Call connect_to_mongo first.")
    return _db


def is_connected() -> bool:
    """Check if MongoDB is connected and healthy"""
    return _connection_healthy and _client is not None


async def create_indexes_safe():
    """Create necessary indexes safely (with error handling)"""
    try:
        await create_indexes()
    except Exception as e:
        logger.warning(f"Failed to create indexes: {e}")
        logger.info("Indexes will be created on first use")


async def create_indexes():
    """Create necessary indexes"""
    if not is_connected():
        logger.warning("Cannot create indexes: MongoDB not connected")
        return

    try:
        db = get_database()

        # User collection indexes
        await db.users.create_index([("username", ASCENDING)], unique=True)
        await db.users.create_index([("email", ASCENDING)], unique=True)
        await db.users.create_index([("created_at", DESCENDING)])

        # Spec collection indexes
        await db.specs.create_index([("user_id", ASCENDING)])
        await db.specs.create_index([("created_at", DESCENDING)])
        await db.specs.create_index([("city", ASCENDING)])
        await db.specs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

        # Iteration collection indexes
        await db.iterations.create_index([("spec_id", ASCENDING)])
        await db.iterations.create_index([("user_id", ASCENDING)])
        await db.iterations.create_index([("created_at", DESCENDING)])

        # Evaluation collection indexes
        await db.evaluations.create_index([("spec_id", ASCENDING)])
        await db.evaluations.create_index([("created_at", DESCENDING)])

        # RL Feedback collection indexes
        await db.rl_feedback.create_index([("spec_id", ASCENDING)])
        await db.rl_feedback.create_index([("user_id", ASCENDING)])
        await db.rl_feedback.create_index([("created_at", DESCENDING)])

        # Audit Log collection indexes
        await db.audit_logs.create_index([("user_id", ASCENDING)])
        await db.audit_logs.create_index([("action", ASCENDING)])
        await db.audit_logs.create_index([("created_at", DESCENDING)])
        await db.audit_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

        # Compliance Check collection indexes
        await db.compliance_checks.create_index([("spec_id", ASCENDING)])
        await db.compliance_checks.create_index([("city", ASCENDING)])
        await db.compliance_checks.create_index([("created_at", DESCENDING)])

        # Workflow Run collection indexes
        await db.workflow_runs.create_index([("user_id", ASCENDING)])
        await db.workflow_runs.create_index([("status", ASCENDING)])
        await db.workflow_runs.create_index([("created_at", DESCENDING)])

        # Refresh Token collection indexes
        await db.refresh_tokens.create_index([("user_id", ASCENDING)])
        # TTL index for automatic document expiration - skip if exists
        try:
            await db.refresh_tokens.create_index(
                [("expires_at", ASCENDING)], name="expires_at_1_ttl", expireAfterSeconds=0
            )
        except Exception as ttl_error:
            if "IndexOptionsConflict" in str(ttl_error) or "already exists" in str(ttl_error):
                logger.debug("TTL index already exists, skipping creation")
            else:
                raise

        logger.info("MongoDB indexes created successfully")

    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")
        raise


async def check_db_connection() -> dict:
    """
    Comprehensive database health check

    Returns:
        dict with status and latency
    """
    import time

    start_time = time.time()

    try:
        if not is_connected():
            return {
                "status": "disconnected",
                "error": "MongoDB client not connected",
                "latency_ms": 0,
            }

        db = get_database()
        await asyncio.wait_for(db.command("ping"), timeout=10.0)
        latency_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "database": "mongodb",
        }
    except asyncio.TimeoutError:
        logger.error("Database health check timed out")
        return {
            "status": "timeout",
            "error": "Health check timed out",
            "latency_ms": round((time.time() - start_time) * 1000, 2),
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
        if not is_connected():
            return {"error": "MongoDB not connected"}

        db = get_database()

        # Get collection stats with timeout
        collections = await asyncio.wait_for(db.list_collection_names(), timeout=10.0)
        stats = {
            "database": "mongodb",
            "connected": True,
            "collections": [],
        }

        for collection_name in collections:
            try:
                collection = db[collection_name]
                count = await asyncio.wait_for(collection.count_documents({}), timeout=5.0)
                stats["collections"].append(
                    {
                        "name": collection_name,
                        "documents": count,
                    }
                )
            except asyncio.TimeoutError:
                stats["collections"].append(
                    {
                        "name": collection_name,
                        "documents": "timeout",
                    }
                )
            except Exception as e:
                stats["collections"].append(
                    {
                        "name": collection_name,
                        "documents": f"error: {e}",
                    }
                )

        return stats
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        return {"error": str(e), "connected": False}


__all__ = [
    "connect_to_mongo",
    "close_mongo_connection",
    "get_database",
    "is_connected",
    "check_db_connection",
    "get_db_stats",
]
