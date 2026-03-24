#!/usr/bin/env python3
"""
Import Issues Fixer and Validator
Fixes common import issues and validates all modules can be imported
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Set, Tuple

def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in directory"""
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip virtual environment and cache directories
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', '.git', 'node_modules'}]
        for file in files:
            if file.endswith('.py'):
                python_files.append(Path(root) / file)
    return python_files

def extract_imports(file_path: Path) -> Tuple[List[str], List[str]]:
    """Extract imports from a Python file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)
        imports = []
        from_imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    from_imports.append(f"{module}.{alias.name}" if module else alias.name)

        return imports, from_imports
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return [], []

def check_module_availability(module_name: str) -> bool:
    """Check if a module can be imported"""
    try:
        __import__(module_name.split('.')[0])
        return True
    except ImportError:
        return False

def fix_common_import_issues(backend_dir: Path):
    """Fix common import issues"""

    # Add __init__.py files where missing
    for root, dirs, files in os.walk(backend_dir):
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', '.git'}]
        if any(f.endswith('.py') for f in files):
            init_file = Path(root) / '__init__.py'
            if not init_file.exists():
                print(f"Creating missing __init__.py in {root}")
                init_file.write_text("# Package initialization\n")

def validate_imports(backend_dir: Path):
    """Validate all imports in the project"""
    python_files = find_python_files(backend_dir)
    missing_modules = set()

    print(f"Validating imports in {len(python_files)} Python files...")

    for file_path in python_files:
        imports, from_imports = extract_imports(file_path)

        for imp in imports + from_imports:
            # Skip relative imports and built-in modules
            if imp.startswith('.') or imp in {'os', 'sys', 'json', 'time', 'datetime', 'logging', 're', 'pathlib', 'typing', 'uuid', 'traceback'}:
                continue

            module_name = imp.split('.')[0]
            if not check_module_availability(module_name):
                missing_modules.add(module_name)

    return missing_modules

def generate_requirements_from_imports(missing_modules: Set[str]) -> List[str]:
    """Generate requirements for missing modules"""
    # Common package mappings
    package_mapping = {
        'fastapi': 'fastapi>=0.100.0',
        'uvicorn': 'uvicorn[standard]>=0.24.0',
        'pydantic': 'pydantic>=2.0.0',
        'pymongo': 'pymongo>=4.6.0',
        'motor': 'motor>=3.3.0',
        'jose': 'python-jose[cryptography]>=3.3.0',
        'passlib': 'passlib[bcrypt]>=1.7.4',
        'bcrypt': 'bcrypt>=4.0.0',
        'requests': 'requests>=2.31.0',
        'httpx': 'httpx>=0.25.0',
        'aiofiles': 'aiofiles>=23.2.0',
        'sentry_sdk': 'sentry-sdk[fastapi]>=1.40.0',
        'prometheus_fastapi_instrumentator': 'prometheus-fastapi-instrumentator>=6.1.0',
        'openai': 'openai>=1.0.0',
        'groq': 'groq>=0.4.0',
        'anthropic': 'anthropic>=0.7.0',
        'dotenv': 'python-dotenv>=1.0.0',
        'PIL': 'Pillow>=10.0.0',
        'torch': 'torch>=2.0.0',
        'numpy': 'numpy>=1.24.0',
        'pandas': 'pandas>=1.5.0',
        'trimesh': 'trimesh>=4.0.0',
        'prefect': 'prefect>=2.14.0',
    }

    requirements = []
    for module in missing_modules:
        if module in package_mapping:
            requirements.append(package_mapping[module])
        else:
            requirements.append(f"{module}>=1.0.0")

    return sorted(requirements)

def main():
    """Main function"""
    backend_dir = Path(__file__).parent / 'backend'

    if not backend_dir.exists():
        print(f"Backend directory not found: {backend_dir}")
        return

    print("🔧 Fixing common import issues...")
    fix_common_import_issues(backend_dir)

    print("🔍 Validating imports...")
    missing_modules = validate_imports(backend_dir)

    if missing_modules:
        print(f"\n❌ Missing modules found: {len(missing_modules)}")
        for module in sorted(missing_modules):
            print(f"  - {module}")

        print("\n📦 Suggested requirements:")
        requirements = generate_requirements_from_imports(missing_modules)
        for req in requirements:
            print(f"  {req}")

        # Write to requirements file
        req_file = backend_dir / 'requirements_missing.txt'
        with open(req_file, 'w') as f:
            f.write('\n'.join(requirements))
        print(f"\n💾 Missing requirements saved to: {req_file}")
    else:
        print("\n✅ All imports validated successfully!")

if __name__ == "__main__":
    main()
