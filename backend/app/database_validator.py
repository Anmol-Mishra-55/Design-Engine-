"""
Database Validator - MongoDB Version
Validates MongoDB connections and collections
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MongoDBValidator:
    """Validate and initialize MongoDB components"""

    def __init__(self, db):
        self.db = db

    async def validate_connection(self) -> bool:
        """Test MongoDB connection"""
        try:
            await self.db.command("ping")
            logger.info("✅ MongoDB connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            return False

    async def get_existing_collections(self) -> List[str]:
        """Get list of existing collections"""
        try:
            collections = await self.db.list_collection_names()
            logger.info(f"Found {len(collections)} existing collections: {collections}")
            return collections
        except Exception as e:
            logger.error(f"Failed to get collection list: {e}")
            return []

    async def validate_required_collections(self) -> Dict[str, bool]:
        """Validate that all required collections exist"""
        required_collections = [
            "specs",
            "evaluations",
            "users",
            "iterations",
            "compliance_checks",
            "rl_feedback",
            "audit_logs",
            "workflow_runs",
            "refresh_tokens",
        ]

        existing_collections = await self.get_existing_collections()
        results = {}

        for collection in required_collections:
            results[collection] = collection in existing_collections

        return results

    async def create_missing_collections(self):
        """Create missing collections with indexes"""
        try:
            # Collections are created automatically in MongoDB when first document is inserted
            # But we can create indexes
            await self.create_indexes()
            logger.info("✅ MongoDB collections and indexes ready")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create collections: {e}")
            return False

    async def create_indexes(self):
        """Create necessary indexes"""
        try:
            # User collection indexes
            await self.db.users.create_index("username", unique=True)
            await self.db.users.create_index("email", unique=True)

            # Spec collection indexes
            await self.db.specs.create_index("user_id")
            await self.db.specs.create_index("city")

            # Other indexes as needed
            await self.db.evaluations.create_index("spec_id")
            await self.db.iterations.create_index("spec_id")
            await self.db.rl_feedback.create_index("spec_id")

            logger.info("✅ MongoDB indexes created")

        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

    async def test_crud_operations(self) -> bool:
        """Test basic CRUD operations"""
        try:
            import uuid
            from datetime import datetime

            # Test CREATE
            test_doc = {
                "_id": f"test_{uuid.uuid4().hex[:8]}",
                "test_field": "test_value",
                "created_at": datetime.utcnow(),
            }

            result = await self.db.test_collection.insert_one(test_doc)

            # Test READ
            retrieved = await self.db.test_collection.find_one({"_id": test_doc["_id"]})
            assert retrieved is not None

            # Test UPDATE
            await self.db.test_collection.update_one(
                {"_id": test_doc["_id"]}, {"$set": {"test_field": "updated_value"}}
            )

            # Test DELETE (cleanup)
            await self.db.test_collection.delete_one({"_id": test_doc["_id"]})

            # Drop test collection
            await self.db.test_collection.drop()

            logger.info("✅ CRUD operations test passed")
            return True

        except Exception as e:
            logger.error(f"❌ CRUD operations test failed: {e}")
            return False

    async def run_full_validation(self) -> Dict[str, bool]:
        """Run complete database validation"""
        results = {"connection": False, "collections_ready": False, "indexes_created": False, "crud_works": False}

        # Test connection
        results["connection"] = await self.validate_connection()
        if not results["connection"]:
            return results

        # Create missing collections and indexes
        results["collections_ready"] = await self.create_missing_collections()
        results["indexes_created"] = results["collections_ready"]

        # Test CRUD operations
        if results["collections_ready"]:
            results["crud_works"] = await self.test_crud_operations()

        return results


async def validate_database():
    """Convenience function to validate MongoDB on startup"""
    try:
        from app.database_mongodb import get_database

        db = get_database()
        validator = MongoDBValidator(db)

        results = await validator.run_full_validation()

        # Log results
        logger.info("MongoDB Validation Results:")
        for check, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"  {check}: {status}")

        all_passed = all(results.values())
        if all_passed:
            logger.info("🎉 MongoDB validation completed successfully")
        else:
            logger.warning("⚠️ Some MongoDB validation checks failed")

        return all_passed

    except Exception as e:
        logger.error(f"MongoDB validation crashed: {e}")
        return False
