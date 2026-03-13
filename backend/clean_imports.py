#!/usr/bin/env python3
"""
Remove all Supabase and problematic imports
"""
import os
import re


def clean_file(file_path):
    """Remove problematic imports and replace with mocks"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Remove Supabase imports
        content = re.sub(r'        content = re.sub(r'
        # Remove storage imports
        content = re.sub(r'from app\.storage import.*\n', '', content)

        # Remove other problematic imports
        content = re.sub(r'from app\.prefect_integration.*import.*\n', '', content)
        content = re.sub(r'from app\.service_monitor import.*\n', '', content)
        content = re.sub(r'from app\.models_mongodb import.*\n', '', content)

        # Replace function calls with mocks
        content = re.sub(r'await should_use_mock_response\([^)]*\)', 'False', content)
        content = re.sub(r'should_use_mock_response\([^)]*\)', 'False', content)
        content = re.sub(r'await trigger_automation_workflow\([^)]*\)', '{"status": "mock"}', content)
        content = re.sub(r'trigger_automation_workflow\([^)]*\)', '{"status": "mock"}', content)
        content = re.sub(r'await check_workflow_status\(\)', '{"status": "healthy"}', content)
        content = re.sub(r'check_workflow_status\(\)', '{"status": "healthy"}', content)

        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Cleaned: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error cleaning {file_path}: {e}")
        return False

def main():
    """Clean all Python files"""
    cleaned_count = 0

    for root, dirs, files in os.walk('.'):
        # Skip virtual environment and cache directories
        dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git']]

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if clean_file(file_path):
                    cleaned_count += 1

    print(f"Cleaned {cleaned_count} files")

if __name__ == "__main__":
    main()
