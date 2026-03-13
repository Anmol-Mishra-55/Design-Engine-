#!/usr/bin/env python3
"""
Configuration Validation Script
Validates all configuration settings and external service connectivity
"""

import asyncio
import os
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent / "app"))

import logging

import asyncpg
import httpx
from app.config import settings, validate_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConfigValidator:
    """Comprehensive configuration validator"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.total_checks = 0

    def check(self, name: str, condition: bool, error_msg: str = None, warning_msg: str = None):
        """Add a validation check"""
        self.total_checks += 1
        if condition:
            self.success_count += 1
            print(f"✓ {name}")
        else:
            if error_msg:
                self.errors.append(f"{name}: {error_msg}")
                print(f"✗ {name}: {error_msg}")
            elif warning_msg:
                self.warnings.append(f"{name}: {warning_msg}")
                print(f"⚠ {name}: {warning_msg}")
            else:
                self.errors.append(f"{name}: Failed")
                print(f"✗ {name}: Failed")

    async def validate_database(self):
        """Validate database connectivity"""
        print("\n🗄️  Database Validation")
        print("-" * 40)

        try:
            if settings.DATABASE_URL.startswith("sqlite"):
                # SQLite validation
                db_path = settings.DATABASE_URL.replace("sqlite:///", "")
                if db_path == ":memory:":
                    self.check("Database (SQLite)", True, warning_msg="Using in-memory database")
                else:
                    db_dir = Path(db_path).parent
                    self.check(
                        "Database Directory",
                        db_dir.exists() or db_dir == Path("."),
                        f"Directory {db_dir} does not exist",
                    )
            else:
                # PostgreSQL validation
                conn = await asyncpg.connect(settings.DATABASE_URL)
                result = await conn.fetchval("SELECT 1")
                await conn.close()
                self.check("Database Connection", result == 1)
        except Exception as e:
            self.check("Database Connection", False, str(e))

    async def validate_supabase(self):
        """Validate Supabase connectivity"""
        print("\n☁️  Supabase Validation")
        print("-" * 40)

        try:
            supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

            # Test basic connectivity
            response = supabase.table("_dummy_").select("*").limit(1).execute()
            self.check("Supabase Connection", True)

            # Check buckets
            buckets = [
                settings.STORAGE_BUCKET_FILES,
                settings.STORAGE_BUCKET_PREVIEWS,
                settings.STORAGE_BUCKET_GEOMETRY,
                settings.STORAGE_BUCKET_COMPLIANCE,
            ]

            for bucket in buckets:
                try:
                    supabase.storage.get_bucket(bucket)
                    self.check(f"Bucket: {bucket}", True)
                except Exception as e:
                    self.check(f"Bucket: {bucket}", False, f"Bucket not found: {e}")

        except Exception as e:
            self.check("Supabase Connection", False, str(e))

    async def validate_external_services(self):
        """Validate external service connectivity"""
        print("\n🌐 External Services Validation")
        print("-" * 40)

        # Sohum's MCP Service
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.SOHUM_MCP_URL}/health")
                self.check("Sohum MCP Service", response.status_code == 200)
        except Exception as e:
            self.check("Sohum MCP Service", False, warning_msg=f"Cannot reach service: {e}")

        # Ranjeet's RL Service
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{settings.RANJEET_RL_URL}/health")
                self.check("Ranjeet RL Service", response.status_code == 200)
        except Exception as e:
            self.check("Ranjeet RL Service", False, warning_msg=f"Cannot reach service: {e}")

        # Yotta API (if configured)
        if settings.YOTTA_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    headers = {"Authorization": f"Bearer {settings.YOTTA_API_KEY}"}
                    response = await client.get(f"{settings.YOTTA_URL}/health", headers=headers)
                    self.check("Yotta API", response.status_code == 200)
            except Exception as e:
                self.check("Yotta API", False, warning_msg=f"Cannot reach API: {e}")

    def validate_security(self):
        """Validate security configuration"""
        print("\n🔒 Security Validation")
        print("-" * 40)

        # JWT Secret strength
        jwt_strength = len(settings.JWT_SECRET_KEY) >= 32
        self.check("JWT Secret Strength", jwt_strength, "JWT secret should be at least 32 characters for production")

        # Environment-specific checks
        if settings.ENVIRONMENT == "production":
            self.check("Production Debug", not settings.DEBUG, "DEBUG should be False in production")
            self.check(
                "Production JWT",
                len(settings.JWT_SECRET_KEY) >= 32,
                "JWT secret must be at least 32 characters in production",
            )

        # Encryption key
        if settings.ENCRYPTION_KEY:
            self.check(
                "Encryption Key Length",
                len(settings.ENCRYPTION_KEY) == 32,
                "Encryption key should be exactly 32 characters",
            )

    def validate_directories(self):
        """Validate required directories"""
        print("\n📁 Directory Validation")
        print("-" * 40)

        directories = [
            Path("logs"),
            Path(settings.UPLOAD_DIRECTORY),
            Path("models") if settings.LOCAL_GPU_ENABLED else None,
        ]

        for directory in directories:
            if directory:
                if not directory.exists():
                    try:
                        directory.mkdir(parents=True, exist_ok=True)
                        self.check(f"Directory: {directory}", True, warning_msg="Created directory")
                    except Exception as e:
                        self.check(f"Directory: {directory}", False, f"Cannot create: {e}")
                else:
                    self.check(f"Directory: {directory}", True)

    def validate_gpu(self):
        """Validate GPU configuration"""
        print("\n🖥️  GPU Validation")
        print("-" * 40)

        if settings.LOCAL_GPU_ENABLED:
            try:
                import torch

                cuda_available = torch.cuda.is_available()
                self.check("CUDA Available", cuda_available, "CUDA not available but LOCAL_GPU_ENABLED=true")

                if cuda_available:
                    device_count = torch.cuda.device_count()
                    device_id = int(settings.LOCAL_GPU_DEVICE.split(":")[1]) if ":" in settings.LOCAL_GPU_DEVICE else 0
                    self.check(
                        "GPU Device", device_id < device_count, f"Device {settings.LOCAL_GPU_DEVICE} not available"
                    )
            except ImportError:
                self.check("PyTorch", False, "PyTorch not installed but LOCAL_GPU_ENABLED=true")
        else:
            self.check("GPU Configuration", True, warning_msg="Local GPU disabled")

    def print_summary(self):
        """Print validation summary"""
        print("\n" + "=" * 60)
        print("CONFIGURATION VALIDATION SUMMARY")
        print("=" * 60)

        print(f"✓ Successful checks: {self.success_count}/{self.total_checks}")

        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if not self.errors and not self.warnings:
            print("\n🎉 All configuration checks passed!")
            return True
        elif not self.errors:
            print(f"\n✅ Configuration valid with {len(self.warnings)} warnings")
            return True
        else:
            print(f"\n❌ Configuration has {len(self.errors)} errors that must be fixed")
            return False


async def main():
    """Main validation function"""
    print("🔍 Design Engine API Configuration Validator")
    print("=" * 60)

    # Basic settings validation
    try:
        validate_settings()
        print("✓ Basic configuration validation passed")
    except Exception as e:
        print(f"❌ Basic configuration validation failed: {e}")
        return False

    # Comprehensive validation
    validator = ConfigValidator()

    # Run all validations
    await validator.validate_database()
    await validator.validate_supabase()
    await validator.validate_external_services()
    validator.validate_security()
    validator.validate_directories()
    validator.validate_gpu()

    # Print summary
    success = validator.print_summary()

    if success:
        print("\n🚀 Your configuration is ready for deployment!")
    else:
        print("\n🔧 Please fix the errors above before deploying")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
