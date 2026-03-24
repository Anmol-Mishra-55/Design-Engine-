#!/usr/bin/env python3
"""
Complete Import and Integration Validator
Validates all imports and fixes integration issues before server startup
"""

import importlib
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Tuple

def validate_core_imports() -> Dict[str, bool]:
    """Validate core FastAPI imports"""
    core_modules = {
        'fastapi': 'FastAPI framework',
        'uvicorn': 'ASGI server',
        'pydantic': 'Data validation',
        'pymongo': 'MongoDB driver',
        'motor': 'Async MongoDB driver',
        'jose': 'JWT handling',
        'passlib': 'Password hashing',
        'bcrypt': 'Password encryption',
        'requests': 'HTTP client',
        'httpx': 'Async HTTP client',
        'aiofiles': 'Async file operations',
    }

    results = {}
    print("🔍 Validating Core Dependencies...")

    for module, description in core_modules.items():
        try:
            importlib.import_module(module)
            print(f"  ✅ {module} - {description}")
            results[module] = True
        except ImportError as e:
            print(f"  ❌ {module} - {description} - {e}")
            results[module] = False

    return results

def validate_optional_imports() -> Dict[str, bool]:
    """Validate optional ML/AI imports"""
    optional_modules = {
        'stable_baselines3': 'RL training (optional)',
        'gymnasium': 'RL environments (optional)',
        'torch': 'PyTorch ML framework (optional)',
        'numpy': 'Numerical computing (optional)',
        'openai': 'OpenAI API client (optional)',
        'anthropic': 'Anthropic API client (optional)',
        'groq': 'Groq API client (optional)',
    }

    results = {}
    print("\n🔧 Validating Optional Dependencies...")

    for module, description in optional_modules.items():
        try:
            importlib.import_module(module)
            print(f"  ✅ {module} - {description}")
            results[module] = True
        except ImportError:
            print(f"  ⚠️  {module} - {description}")
            results[module] = False

    return results

def validate_app_modules() -> Dict[str, bool]:
    """Validate application modules"""
    app_modules = {
        'app.config': 'Application configuration',
        'app.database_mongodb': 'MongoDB connection',
        'app.utils': 'Utility functions',
        'app.models_mongodb': 'MongoDB data models',
        'app.platform_adapter': 'Platform adapter',
    }

    results = {}
    print("\n🏗️ Validating Application Modules...")

    # Add backend to path
    backend_path = Path(__file__).parent / 'backend'
    if backend_path.exists():
        sys.path.insert(0, str(backend_path))

    for module, description in app_modules.items():
        try:
            importlib.import_module(module)
            print(f"  ✅ {module} - {description}")
            results[module] = True
        except ImportError as e:
            print(f"  ❌ {module} - {description} - {e}")
            results[module] = False
        except Exception as e:
            print(f"  ⚠️  {module} - {description} - {e}")
            results[module] = False

    return results

def validate_api_modules() -> Dict[str, bool]:
    """Validate API endpoint modules"""
    api_modules = {
        'app.api.auth': 'Authentication endpoints',
        'app.api.generate': 'Design generation endpoints',
        'app.api.health': 'Health check endpoints',
        'app.api.compliance': 'Compliance endpoints',
        'app.api.mobile': 'Mobile API endpoints',
    }

    results = {}
    print("\n🌐 Validating API Modules...")

    for module, description in api_modules.items():
        try:
            importlib.import_module(module)
            print(f"  ✅ {module} - {description}")
            results[module] = True
        except ImportError as e:
            print(f"  ❌ {module} - {description} - {e}")
            results[module] = False
        except Exception as e:
            print(f"  ⚠️  {module} - {description} - {e}")
            results[module] = False

    return results

def test_main_app_import() -> bool:
    """Test importing the main FastAPI app"""
    print("\n🚀 Testing Main App Import...")

    try:
        from app.main import app
        print("  ✅ FastAPI app imported successfully")

        # Check if app has routes
        routes = [route.path for route in app.routes]
        print(f"  ✅ Found {len(routes)} routes")

        return True
    except ImportError as e:
        print(f"  ❌ Failed to import main app: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"  ⚠️  App import warning: {e}")
        return False

def check_environment() -> Dict[str, bool]:
    """Check environment configuration"""
    print("\n🔧 Checking Environment...")

    results = {}

    # Check .env file
    env_file = Path('.env')
    if env_file.exists():
        print("  ✅ .env file found")
        results['env_file'] = True
    else:
        print("  ⚠️  .env file not found (will use defaults)")
        results['env_file'] = False

    # Check Python version
    if sys.version_info >= (3, 8):
        print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor}")
        results['python_version'] = True
    else:
        print(f"  ❌ Python {sys.version_info.major}.{sys.version_info.minor} (need 3.8+)")
        results['python_version'] = False

    return results

def generate_fix_commands(core_results: Dict[str, bool], optional_results: Dict[str, bool]) -> List[str]:
    """Generate commands to fix missing dependencies"""
    missing_core = [module for module, available in core_results.items() if not available]
    missing_optional = [module for module, available in optional_results.items() if not available]

    commands = []

    if missing_core:
        print(f"\n❌ Missing Core Dependencies: {', '.join(missing_core)}")
        commands.append("# Install core dependencies:")
        commands.append("pip install -r backend/requirements_minimal.txt")

    if missing_optional:
        print(f"\n⚠️  Missing Optional Dependencies: {', '.join(missing_optional)}")
        commands.append("# Install optional ML dependencies:")
        for module in missing_optional:
            if module == 'stable_baselines3':
                commands.append("pip install stable-baselines3")
            elif module == 'gymnasium':
                commands.append("pip install gymnasium")
            elif module == 'torch':
                commands.append("pip install torch")
            else:
                commands.append(f"pip install {module}")

    return commands

def main():
    """Main validation function"""
    print("🎯 Complete Import and Integration Validation")
    print("=" * 60)

    # Validate environment
    env_results = check_environment()

    # Validate imports
    core_results = validate_core_imports()
    optional_results = validate_optional_imports()
    app_results = validate_app_modules()
    api_results = validate_api_modules()

    # Test main app
    main_app_success = test_main_app_import()

    # Calculate success rates
    core_success = sum(core_results.values()) / len(core_results) * 100
    app_success = sum(app_results.values()) / len(app_results) * 100
    api_success = sum(api_results.values()) / len(api_results) * 100

    print("\n" + "=" * 60)
    print("📊 Validation Summary")
    print("=" * 60)
    print(f"Core Dependencies: {core_success:.1f}% ({sum(core_results.values())}/{len(core_results)})")
    print(f"Application Modules: {app_success:.1f}% ({sum(app_results.values())}/{len(app_results)})")
    print(f"API Modules: {api_success:.1f}% ({sum(api_results.values())}/{len(api_results)})")
    print(f"Main App Import: {'✅ SUCCESS' if main_app_success else '❌ FAILED'}")

    # Generate fix commands
    fix_commands = generate_fix_commands(core_results, optional_results)

    if fix_commands:
        print("\n🔧 Recommended Fixes:")
        for command in fix_commands:
            print(f"  {command}")

    # Overall assessment
    if core_success >= 90 and app_success >= 80 and main_app_success:
        print("\n🎉 VALIDATION PASSED - Server should start successfully!")
        print("\n🚀 Start server with:")
        print("  cd backend")
        print("  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        return True
    else:
        print("\n❌ VALIDATION FAILED - Fix issues before starting server")
        print("\n📋 Next steps:")
        print("1. Install missing dependencies")
        print("2. Run this validator again")
        print("3. Start server once validation passes")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
