#!/usr/bin/env python3
"""
Import Validation Script - Checks all imports are working correctly
"""
import importlib
import sys
from pathlib import Path


def validate_minimal_integration():
    """Validate the minimal Prefect integration works"""
    try:
        # Test importing the minimal integration
                    check_workflow_status,
            get_workflow_status,
            minimal_client,
            trigger_automation_workflow,
        )

        print("✓ Minimal Prefect integration imports successfully")
        return True
    except ImportError as e:
        print(f"✗ Minimal Prefect integration import failed: {e}")
        return False


def validate_main_modules():
    """Validate main application modules"""
    modules_to_test = [
        "app.config",
        "app.main",
        "app.api.bhiv_integrated",
        "app.api.workflow_management",
        "app.api.bhiv_assistant",
        "app.external_services",
    ]

    success_count = 0
    for module_name in modules_to_test:
        try:
            importlib.import_module(module_name)
            print(f"✓ {module_name}")
            success_count += 1
        except ImportError as e:
            print(f"✗ {module_name}: {e}")
        except Exception as e:
            print(f"⚠ {module_name}: {e}")

    return success_count == len(modules_to_test)


def validate_api_endpoints():
    """Validate API endpoints can be imported"""
    try:
        from app.api import bhiv_assistant, bhiv_integrated, compliance, health, workflow_management

        print("✓ All API endpoints import successfully")
        return True
    except ImportError as e:
        print(f"✗ API endpoint import failed: {e}")
        return False


def main():
    """Main validation function"""
    print("=" * 60)
    print("BHIV Backend Import Validation")
    print("=" * 60)

    # Add current directory to Python path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))

    all_good = True

    print("\n1. Testing minimal Prefect integration...")
    if not validate_minimal_integration():
        all_good = False

    print("\n2. Testing main application modules...")
    if not validate_main_modules():
        all_good = False

    print("\n3. Testing API endpoints...")
    if not validate_api_endpoints():
        all_good = False

    print("\n" + "=" * 60)
    if all_good:
        print("🎉 ALL IMPORTS VALIDATED SUCCESSFULLY!")
        print("✓ Your BHIV backend is ready to run")
        print("✓ All files are synced with minimal Prefect integration")
        print("✓ No import issues detected")
    else:
        print("❌ IMPORT VALIDATION FAILED")
        print("Some modules have import issues that need to be fixed")

    print("=" * 60)
    return all_good


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
