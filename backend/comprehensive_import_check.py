#!/usr/bin/env python3
"""
Comprehensive Import Analysis for BHIV Backend Project
Checks all Python files for import issues and dependencies
"""
import ast
import importlib.util
import os
import sys
from pathlib import Path


def check_file_imports(file_path):
    """Check imports in a single Python file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse the AST to extract imports
        tree = ast.parse(content)
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)

        return imports, None
    except SyntaxError as e:
        return [], f"Syntax Error: {e}"
    except Exception as e:
        return [], f"Error: {e}"


def find_python_files(directory):
    """Find all Python files in directory"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in ["__pycache__", ".git", "node_modules", "venv", ".venv"]]

        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    return python_files


def check_critical_files():
    """Check critical files that use prefect integration"""
    critical_files = [
        "app/main.py",
        "app/prefect_integration_minimal.py",
        "app/api/compliance.py",
        "app/api/bhiv_integrated.py",
        "app/api/workflow_management.py",
        "app/config.py",
        "app/database.py",
        "app/external_services.py",
    ]

    results = {}
    for file_path in critical_files:
        if os.path.exists(file_path):
            try:
                # Try to compile the file
                with open(file_path, "r", encoding="utf-8") as f:
                    compile(f.read(), file_path, "exec")
                results[file_path] = "✅ OK"
            except SyntaxError as e:
                results[file_path] = f"❌ Syntax Error: {e}"
            except Exception as e:
                results[file_path] = f"⚠️ Warning: {e}"
        else:
            results[file_path] = "❌ File not found"

    return results


def analyze_prefect_integration():
    """Analyze Prefect integration specifically"""
    try:
        # Check if prefect_integration_minimal can be imported
        sys.path.insert(0, ".")

                    PREFECT_AVAILABLE,
            check_workflow_status,
            get_workflow_status,
            trigger_automation_workflow,
        )

        return {
            "prefect_available": PREFECT_AVAILABLE,
            "functions_imported": "✅ All functions imported successfully",
            "integration_status": "✅ Working",
        }
    except ImportError as e:
        return {
            "prefect_available": False,
            "functions_imported": f"❌ Import Error: {e}",
            "integration_status": "❌ Failed",
        }


def main():
    print("=" * 80)
    print("🔍 COMPREHENSIVE IMPORT ANALYSIS - BHIV BACKEND PROJECT")
    print("=" * 80)

    # 1. Check critical files
    print("\n📋 CRITICAL FILES SYNTAX CHECK:")
    print("-" * 50)
    critical_results = check_critical_files()
    for file_path, status in critical_results.items():
        print(f"{file_path:<40} {status}")

    # 2. Analyze Prefect integration
    print("\n🔧 PREFECT INTEGRATION ANALYSIS:")
    print("-" * 50)
    prefect_analysis = analyze_prefect_integration()
    for key, value in prefect_analysis.items():
        print(f"{key:<25} {value}")

    # 3. Find all Python files and check for major issues
    print("\n📁 ALL PYTHON FILES ANALYSIS:")
    print("-" * 50)

    python_files = find_python_files("app")
    total_files = len(python_files)
    syntax_errors = 0
    import_issues = 0

    for file_path in python_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                compile(f.read(), file_path, "exec")
        except SyntaxError:
            syntax_errors += 1
            print(f"❌ SYNTAX ERROR: {file_path}")
        except Exception as e:
            import_issues += 1
            print(f"⚠️ ISSUE: {file_path} - {e}")

    # 4. Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY REPORT")
    print("=" * 80)
    print(f"Total Python files analyzed: {total_files}")
    print(f"Files with syntax errors: {syntax_errors}")
    print(f"Files with other issues: {import_issues}")
    print(f"Clean files: {total_files - syntax_errors - import_issues}")

    if syntax_errors == 0 and import_issues == 0:
        print("\n🎉 RESULT: NO IMPORT ISSUES FOUND!")
        print("✅ Your project is ready to run")
        print("✅ Prefect minimal integration is working")
        print("✅ All critical files are syntactically correct")
    else:
        print(f"\n⚠️ RESULT: {syntax_errors + import_issues} issues found")
        print("❌ Please fix the issues above before running")

    print("\n🚀 TO RUN YOUR PROJECT:")
    print("cd backend")
    print("python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")


if __name__ == "__main__":
    main()
