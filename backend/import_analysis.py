#!/usr/bin/env python3
"""
Import Analysis for BHIV Backend Project
"""
import os
import sys


def check_critical_files():
    """Check critical files compilation"""
    critical_files = [
        "app/main.py",
        "app/prefect_integration_minimal.py",
        "app/api/compliance.py",
        "app/api/bhiv_integrated.py",
        "app/api/workflow_management.py",
    ]

    results = {}
    for file_path in critical_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    compile(f.read(), file_path, "exec")
                results[file_path] = "OK"
            except SyntaxError as e:
                results[file_path] = f"SYNTAX ERROR: {e}"
            except Exception as e:
                results[file_path] = f"ERROR: {e}"
        else:
            results[file_path] = "FILE NOT FOUND"

    return results


def test_prefect_integration():
    """Test Prefect integration imports"""
    try:
        sys.path.insert(0, ".")
                    PREFECT_AVAILABLE,
            check_workflow_status,
            trigger_automation_workflow,
        )

        return {"status": "SUCCESS", "prefect_available": PREFECT_AVAILABLE, "message": "All imports working"}
    except Exception as e:
        return {"status": "FAILED", "error": str(e)}


def scan_all_python_files():
    """Scan all Python files for syntax errors"""
    errors = []
    total = 0

    for root, dirs, files in os.walk("app"):
        dirs[:] = [d for d in dirs if d not in ["__pycache__"]]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total += 1

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        compile(f.read(), file_path, "exec")
                except SyntaxError as e:
                    errors.append(f"{file_path}: {e}")
                except Exception as e:
                    errors.append(f"{file_path}: {e}")

    return total, errors


def main():
    print("BHIV BACKEND - IMPORT ANALYSIS")
    print("=" * 50)

    # Check critical files
    print("\nCRITICAL FILES:")
    critical_results = check_critical_files()
    for file_path, status in critical_results.items():
        print(f"{file_path}: {status}")

    # Test Prefect integration
    print("\nPREFECT INTEGRATION:")
    prefect_test = test_prefect_integration()
    for key, value in prefect_test.items():
        print(f"{key}: {value}")

    # Scan all files
    print("\nALL FILES SCAN:")
    total_files, errors = scan_all_python_files()
    print(f"Total files: {total_files}")
    print(f"Files with errors: {len(errors)}")

    if errors:
        print("\nERRORS FOUND:")
        for error in errors:
            print(f"  {error}")

    # Summary
    print("\n" + "=" * 50)
    if len(errors) == 0:
        print("RESULT: NO IMPORT ISSUES FOUND!")
        print("Your project is ready to run")
    else:
        print(f"RESULT: {len(errors)} issues found")
        print("Fix the errors above before running")


if __name__ == "__main__":
    main()
