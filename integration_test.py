#!/usr/bin/env python3
"""
Integration Test Script
Tests all modules and their integrations to identify issues
"""

import asyncio
import importlib
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

class IntegrationTester:
    def __init__(self):
        self.results = {}
        self.failed_imports = []
        self.successful_imports = []

    def test_import(self, module_name: str) -> Tuple[bool, str]:
        """Test if a module can be imported"""
        try:
            importlib.import_module(module_name)
            return True, "Success"
        except ImportError as e:
            return False, f"ImportError: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def test_core_modules(self) -> Dict[str, Tuple[bool, str]]:
        """Test core application modules"""
        core_modules = [
            'app.config',
            'app.database_mongodb',
            'app.utils',
            'app.platform_adapter',
            'app.main',
        ]

        results = {}
        for module in core_modules:
            success, message = self.test_import(module)
            results[module] = (success, message)

            if success:
                self.successful_imports.append(module)
            else:
                self.failed_imports.append(module)

        return results

    def test_api_modules(self) -> Dict[str, Tuple[bool, str]]:
        """Test API modules"""
        api_modules = [
            'app.api.auth',
            'app.api.generate',
            'app.api.evaluate',
            'app.api.iterate',
            'app.api.health',
            'app.api.compliance',
            'app.api.reports',
            'app.api.mobile',
            'app.api.vr',
        ]

        results = {}
        for module in api_modules:
            success, message = self.test_import(module)
            results[module] = (success, message)

            if success:
                self.successful_imports.append(module)
            else:
                self.failed_imports.append(module)

        return results

    def test_multi_city_modules(self) -> Dict[str, Tuple[bool, str]]:
        """Test multi-city modules"""
        multi_city_modules = [
            'app.multi_city.city_data_loader',
        ]

        results = {}
        for module in multi_city_modules:
            success, message = self.test_import(module)
            results[module] = (success, message)

            if success:
                self.successful_imports.append(module)
            else:
                self.failed_imports.append(module)

        return results

    async def test_database_connection(self) -> Tuple[bool, str]:
        """Test database connection"""
        try:
            from app.database_mongodb import connect_to_mongo, close_mongo_connection
            from app.config import settings

            # Test connection
            db = await connect_to_mongo(settings.MONGODB_URL, settings.MONGODB_DATABASE)
            await close_mongo_connection()

            return True, "Database connection successful"
        except Exception as e:
            return False, f"Database connection failed: {str(e)}"

    async def test_fastapi_app(self) -> Tuple[bool, str]:
        """Test FastAPI app creation"""
        try:
            from app.main import app

            # Check if app is created
            if app is None:
                return False, "FastAPI app is None"

            # Check if routes are registered
            routes = [route.path for route in app.routes]
            if len(routes) < 5:
                return False, f"Too few routes registered: {len(routes)}"

            return True, f"FastAPI app created with {len(routes)} routes"
        except Exception as e:
            return False, f"FastAPI app creation failed: {str(e)}"

    def test_dependencies(self) -> Dict[str, Tuple[bool, str]]:
        """Test external dependencies"""
        dependencies = [
            'fastapi',
            'uvicorn',
            'pydantic',
            'pymongo',
            'motor',
            'jose',
            'passlib',
            'bcrypt',
            'requests',
            'httpx',
            'aiofiles',
        ]

        results = {}
        for dep in dependencies:
            success, message = self.test_import(dep)
            results[dep] = (success, message)

        return results

    async def run_all_tests(self):
        """Run all integration tests"""
        print("🧪 Starting Integration Tests...")
        print("=" * 50)

        # Test dependencies first
        print("\n📦 Testing Dependencies...")
        dep_results = self.test_dependencies()
        self.print_results(dep_results)

        # Test core modules
        print("\n🔧 Testing Core Modules...")
        core_results = self.test_core_modules()
        self.print_results(core_results)

        # Test API modules
        print("\n🌐 Testing API Modules...")
        api_results = self.test_api_modules()
        self.print_results(api_results)

        # Test multi-city modules
        print("\n🏙️ Testing Multi-City Modules...")
        multi_city_results = self.test_multi_city_modules()
        self.print_results(multi_city_results)

        # Test database connection
        print("\n🗄️ Testing Database Connection...")
        db_success, db_message = await self.test_database_connection()
        print(f"  {'✅' if db_success else '❌'} Database: {db_message}")

        # Test FastAPI app
        print("\n🚀 Testing FastAPI App...")
        app_success, app_message = await self.test_fastapi_app()
        print(f"  {'✅' if app_success else '❌'} FastAPI: {app_message}")

        # Summary
        self.print_summary()

    def print_results(self, results: Dict[str, Tuple[bool, str]]):
        """Print test results"""
        for module, (success, message) in results.items():
            status = "✅" if success else "❌"
            print(f"  {status} {module}: {message}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)

        total_tests = len(self.successful_imports) + len(self.failed_imports)
        success_rate = (len(self.successful_imports) / total_tests * 100) if total_tests > 0 else 0

        print(f"Total modules tested: {total_tests}")
        print(f"Successful imports: {len(self.successful_imports)}")
        print(f"Failed imports: {len(self.failed_imports)}")
        print(f"Success rate: {success_rate:.1f}%")

        if self.failed_imports:
            print(f"\n❌ Failed imports:")
            for module in self.failed_imports:
                print(f"  - {module}")

        if success_rate >= 80:
            print(f"\n✅ Integration tests PASSED ({success_rate:.1f}%)")
        else:
            print(f"\n❌ Integration tests FAILED ({success_rate:.1f}%)")
            print("🔧 Run fix_imports.py to resolve import issues")

async def main():
    """Main function"""
    tester = IntegrationTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
