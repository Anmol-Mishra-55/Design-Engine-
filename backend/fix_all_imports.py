#!/usr/bin/env python3
"""
Comprehensive import fixer for MongoDB migration
"""
import glob
import os
import re


def fix_imports_in_file(file_path):
    """Fix imports in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix config imports
        content = re.sub(r'from app\.config import', 'from app.config import', content)

        # Fix database imports
        content = re.sub(r'from app\.database import get_db', 'from app.database_mongodb import get_database', content)
        content = re.sub(r'from app\.database import', 'from app.database_mongodb import', content)

        # Fix models imports
        content = re.sub(r'from app\.models import', '
        # Fix SQLAlchemy Session dependencies
        content = re.sub(r'db: Session = Depends\(get_db\)', '', content)
        content = re.sub(r', db: Session = Depends\(get_db\)', '', content)
        content = re.sub(r'db: Session = Depends\(get_db\),', '', content)

        # Fix SQLAlchemy imports
        content = re.sub(r'from sqlalchemy\.orm import Session', '', content)
        content = re.sub(r'
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def main():
    """Fix all Python files in the project"""
    backend_dir = "."

    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(backend_dir):
        # Skip virtual environment and cache directories
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git']]

        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    print(f"Found {len(python_files)} Python files")

    fixed_count = 0
    for file_path in python_files:
        if fix_imports_in_file(file_path):
            fixed_count += 1

    print(f"Fixed imports in {fixed_count} files")

if __name__ == "__main__":
    main()
