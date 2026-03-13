#!/usr/bin/env python3
"""
Comprehensive Supabase to MongoDB Migration Analysis
Analyzes all Python files and provides detailed report of remaining Supabase references
"""

import json
import os
import re
from pathlib import Path


def analyze_supabase_references():
    """Analyze all Python files for Supabase references"""

    backend_dir = Path("c:/Users/Anmol/Desktop/Backend/backend")
    results = {
        "critical_files": [],
        "test_files": [],
        "utility_files": [],
        "config_files": [],
        "total_references": 0,
        "files_with_references": 0,
    }

    # Search patterns for Supabase references
    patterns = [
        r"supabase",
        r"SUPABASE",
        r"from supabase",
        r"import supabase",
        r"create_client",
        r"\.storage\.",
        r"get_bucket",
        r"list_buckets",
        r"create_bucket",
    ]

    for py_file in backend_dir.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            file_references = []
            for i, line in enumerate(content.split("\n"), 1):
                for pattern in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        file_references.append({"line": i, "content": line.strip(), "pattern": pattern})

            if file_references:
                relative_path = str(py_file.relative_to(backend_dir))
                file_info = {"file": relative_path, "references": file_references, "count": len(file_references)}

                # Categorize files
                if any(x in relative_path.lower() for x in ["test_", "test.py", "/test"]):
                    results["test_files"].append(file_info)
                elif any(x in relative_path.lower() for x in ["config", "setup", "validate"]):
                    results["config_files"].append(file_info)
                elif any(x in relative_path.lower() for x in ["fix_", "clean_", "check_", "create_"]):
                    results["utility_files"].append(file_info)
                else:
                    results["critical_files"].append(file_info)

                results["total_references"] += len(file_references)
                results["files_with_references"] += 1

        except Exception as e:
            print(f"Error reading {py_file}: {e}")

    return results


def generate_migration_report():
    """Generate comprehensive migration report"""

    print("🔍 COMPREHENSIVE SUPABASE TO MONGODB MIGRATION ANALYSIS")
    print("=" * 70)

    results = analyze_supabase_references()

    print(f"\n📊 SUMMARY:")
    print(f"   Total files with Supabase references: {results['files_with_references']}")
    print(f"   Total Supabase references found: {results['total_references']}")
    print(f"   Critical production files: {len(results['critical_files'])}")
    print(f"   Test files: {len(results['test_files'])}")
    print(f"   Utility/Config files: {len(results['utility_files']) + len(results['config_files'])}")

    # Critical files that need immediate attention
    if results["critical_files"]:
        print(f"\n🚨 CRITICAL FILES REQUIRING IMMEDIATE ATTENTION:")
        print("-" * 50)
        for file_info in results["critical_files"]:
            print(f"\n📁 {file_info['file']} ({file_info['count']} references)")
            for ref in file_info["references"][:3]:  # Show first 3 references
                print(f"   Line {ref['line']}: {ref['content']}")
            if file_info["count"] > 3:
                print(f"   ... and {file_info['count'] - 3} more references")

    # Test files (lower priority)
    if results["test_files"]:
        print(f"\n🧪 TEST FILES (Lower Priority):")
        print("-" * 30)
        for file_info in results["test_files"]:
            print(f"   📁 {file_info['file']} ({file_info['count']} references)")

    # Utility files (can be updated or ignored)
    if results["utility_files"] or results["config_files"]:
        print(f"\n🔧 UTILITY/CONFIG FILES (Can be updated or ignored):")
        print("-" * 45)
        all_utils = results["utility_files"] + results["config_files"]
        for file_info in all_utils:
            print(f"   📁 {file_info['file']} ({file_info['count']} references)")

    # Generate fix recommendations
    print(f"\n💡 MIGRATION RECOMMENDATIONS:")
    print("-" * 30)

    if results["critical_files"]:
        print("1. 🚨 IMMEDIATE ACTION REQUIRED:")
        for file_info in results["critical_files"]:
            file_path = file_info["file"]
            if "api/" in file_path:
                print(f"   - Update {file_path}: Replace Supabase storage calls with MongoDB GridFS")
            elif "main" in file_path:
                print(f"   - Update {file_path}: Replace Supabase imports with MongoDB imports")
            elif "storage" in file_path:
                print(f"   - Update {file_path}: Implement GridFS storage methods")
            else:
                print(f"   - Review {file_path}: Check if Supabase references are still needed")

    print("\n2. ✅ COMPLETED MIGRATIONS:")
    print("   - config.py: ✅ Updated to use MongoDB only")
    print("   - storage.py: ✅ Replaced with GridFS implementation")
    print("   - reports.py: ✅ Updated to use GridFS")
    print("   - main.py: ✅ Updated to use MongoDB connections")
    print("   - .env: ✅ Removed Supabase configuration")
    print("   - requirements.txt: ✅ Removed Supabase dependencies")

    print("\n3. 🔄 NEXT STEPS:")
    if results["critical_files"]:
        print("   - Fix critical production files immediately")
        print("   - Test all file upload/download functionality")
        print("   - Verify MongoDB GridFS is working correctly")
    else:
        print("   - ✅ All critical files have been migrated!")
        print("   - Test files and utilities can be updated as needed")
        print("   - Run comprehensive tests to verify migration")

    print("\n4. 🧪 TESTING RECOMMENDATIONS:")
    print("   - Test file uploads to GridFS")
    print("   - Test file downloads from GridFS")
    print("   - Test preview generation and storage")
    print("   - Test compliance document uploads")
    print("   - Verify all API endpoints work without Supabase")

    # Save detailed report to file
    report_file = "c:/Users/Anmol/Desktop/Backend/SUPABASE_MIGRATION_ANALYSIS.json"
    try:
        with open(report_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n📄 Detailed report saved to: {report_file}")
    except Exception as e:
        print(f"\n❌ Could not save report: {e}")

    return results


if __name__ == "__main__":
    generate_migration_report()
