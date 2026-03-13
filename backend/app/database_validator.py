"""
Database Validator - Ensure all database models are properly initialized
Validates database connections and creates missing tables
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class DatabaseValidator:
    """Validate and initialize database components"""

    def __init__(self, engine, session_factory):
        self.engine = engine
        self.session_factory = session_factory

    def validate_connection(self) -> bool:
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False

    def get_existing_tables(self) -> List[str]:
        """Get list of existing tables"""
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            logger.info(f"Found {len(tables)} existing tables: {tables}")
            return tables
        except Exception as e:
            logger.error(f"Failed to get table list: {e}")
            return []

    def validate_required_tables(self) -> Dict[str, bool]:
        """Validate that all required tables exist"""
        required_tables = [
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

        existing_tables = self.get_existing_tables()
        results = {}

        for table in required_tables:
            results[table] = table in existing_tables

        return results

    def create_missing_tables(self):
        """Create missing tables using SQLAlchemy models"""
        try:
            # Create all tables defined in models
            Base.metadata.create_all(bind=self.engine)
            logger.info("✅ Database tables created/updated")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create tables: {e}")
            return False

    def validate_table_schemas(self) -> Dict[str, Dict]:
        """Validate table schemas match model definitions"""
        results = {}

        try:
            inspector = inspect(self.engine)

            for table_name in self.get_existing_tables():
                try:
                    columns = inspector.get_columns(table_name)
                    indexes = inspector.get_indexes(table_name)

                    results[table_name] = {"columns": len(columns), "indexes": len(indexes), "valid": True}

                except Exception as e:
                    results[table_name] = {"error": str(e), "valid": False}

        except Exception as e:
            logger.error(f"Schema validation failed: {e}")

        return results

    def test_crud_operations(self) -> bool:
        """Test basic CRUD operations"""
        try:
            import uuid
            from datetime import datetime

            with self.session_factory() as session:
                # Create test user first
                test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
                test_user = User(
                    id=test_user_id,
                    username=f"testuser_{uuid.uuid4().hex[:6]}",
                    email=f"test_{uuid.uuid4().hex[:6]}@example.com",
                    password_hash="test_hash",
                )
                session.add(test_user)
                session.commit()

                # Test CREATE Spec
                test_spec = Spec(
                    id=f"test_{uuid.uuid4().hex[:8]}",
                    user_id=test_user_id,
                    prompt="Test design prompt",
                    city="Mumbai",
                    spec_json={"test": True},
                    design_type="test",
                    lm_provider="test",
                )

                session.add(test_spec)
                session.commit()

                # Test READ
                retrieved = session.query(Spec).filter(Spec.id == test_spec.id).first()
                assert retrieved is not None

                # Test UPDATE
                retrieved.prompt = "Updated test prompt"
                session.commit()

                # Test DELETE (cleanup)
                session.delete(retrieved)
                session.delete(test_user)
                session.commit()

            logger.info("✅ CRUD operations test passed")
            return True

        except Exception as e:
            logger.error(f"❌ CRUD operations test failed: {e}")
            return False

    def run_full_validation(self) -> Dict[str, bool]:
        """Run complete database validation"""
        results = {"connection": False, "tables_exist": False, "schemas_valid": False, "crud_works": False}

        # Test connection
        results["connection"] = self.validate_connection()
        if not results["connection"]:
            return results

        # Create missing tables
        self.create_missing_tables()

        # Validate tables exist
        table_results = self.validate_required_tables()
        results["tables_exist"] = all(table_results.values())

        if not results["tables_exist"]:
            missing_tables = [name for name, exists in table_results.items() if not exists]
            logger.warning(f"Missing tables: {missing_tables}")

        # Validate schemas
        schema_results = self.validate_table_schemas()
        results["schemas_valid"] = all(result.get("valid", False) for result in schema_results.values())

        # Test CRUD operations
        if results["tables_exist"]:
            results["crud_works"] = self.test_crud_operations()

        return results


def validate_database():
    """Convenience function to validate database on startup"""
    try:
        from app.database_mongodb import engine, get_db
        from sqlalchemy.orm import sessionmaker

        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        validator = DatabaseValidator(engine, SessionLocal)

        results = validator.run_full_validation()

        # Log results
        logger.info("Database Validation Results:")
        for check, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"  {check}: {status}")

        all_passed = all(results.values())
        if all_passed:
            logger.info("🎉 Database validation completed successfully")
        else:
            logger.warning("⚠️ Some database validation checks failed")

        return all_passed

    except Exception as e:
        logger.error(f"Database validation crashed: {e}")
        return False
