#!/usr/bin/env python3
"""
Security Cleanup Script
Removes hardcoded credentials and replaces them with environment variables
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

def find_credential_patterns(content: str) -> List[Tuple[str, str]]:
    """Find potential credential patterns in content"""
    patterns = [
        (r'sk-[a-zA-Z0-9]{48}', 'OPENAI_API_KEY'),  # OpenAI API keys
        (r'msy_[a-zA-Z0-9]{32}', 'MESHY_API_KEY'),  # Meshy API keys
        (r'tsk_[a-zA-Z0-9]{32}', 'TRIPO_API_KEY'),  # Tripo API keys
        (r'eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', 'JWT_TOKEN'),  # JWT tokens
        (r'mongodb\+srv://[^:]+:[^@]+@[^/]+', 'MONGODB_URL'),  # MongoDB URLs
        (r'https://[a-f0-9-]+\.ingest\.sentry\.io/[0-9]+', 'SENTRY_DSN'),  # Sentry DSN
        (r'[a-zA-Z0-9]{32,}', 'API_KEY'),  # Generic long strings that might be keys
    ]

    found = []
    for pattern, key_type in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            found.append((match.group(), key_type))

    return found

def clean_json_file(file_path: Path) -> bool:
    """Clean credentials from JSON files"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        credentials = find_credential_patterns(content)

        if not credentials:
            return False

        # Replace credentials with placeholders
        for credential, key_type in credentials:
            if len(credential) > 10:  # Only replace long strings
                placeholder = f"${{{key_type}}}"
                content = content.replace(credential, placeholder)

        if content != original_content:
            # Backup original
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)

            # Write cleaned version
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Cleaned {file_path}")
            return True

    except Exception as e:
        print(f"❌ Error cleaning {file_path}: {e}")

    return False

def clean_markdown_file(file_path: Path) -> bool:
    """Clean credentials from Markdown files"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Replace API keys in code blocks
        content = re.sub(
            r'(api[_-]?key["\s]*[:=]["\s]*)[a-zA-Z0-9_-]{20,}',
            r'\1${API_KEY}',
            content,
            flags=re.IGNORECASE
        )

        # Replace tokens in examples
        content = re.sub(
            r'(token["\s]*[:=]["\s]*)[a-zA-Z0-9_.-]{20,}',
            r'\1${TOKEN}',
            content,
            flags=re.IGNORECASE
        )

        if content != original_content:
            # Backup original
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)

            # Write cleaned version
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Cleaned {file_path}")
            return True

    except Exception as e:
        print(f"❌ Error cleaning {file_path}: {e}")

    return False

def scan_and_clean_directory(directory: Path):
    """Scan directory for files with potential credentials"""
    cleaned_files = []

    for root, dirs, files in os.walk(directory):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in {'.venv', '__pycache__', '.git', 'node_modules'}]

        for file in files:
            file_path = Path(root) / file

            # Skip backup files
            if file.endswith('.backup'):
                continue

            cleaned = False

            if file.endswith('.json'):
                cleaned = clean_json_file(file_path)
            elif file.endswith('.md'):
                cleaned = clean_markdown_file(file_path)

            if cleaned:
                cleaned_files.append(file_path)

    return cleaned_files

def create_gitignore_entries():
    """Create .gitignore entries for sensitive files"""
    gitignore_entries = [
        "# Environment files",
        ".env",
        ".env.local",
        ".env.production",
        "*.backup",
        "",
        "# API Keys and Secrets",
        "secrets/",
        "credentials/",
        "*.key",
        "*.pem",
        "",
        "# Database",
        "*.db",
        "*.sqlite",
        "",
        "# Logs",
        "logs/",
        "*.log",
    ]

    return "\n".join(gitignore_entries)

def main():
    """Main function"""
    project_dir = Path(__file__).parent

    print("🔒 Starting security cleanup...")
    print(f"📁 Scanning directory: {project_dir}")

    # Clean files
    cleaned_files = scan_and_clean_directory(project_dir)

    if cleaned_files:
        print(f"\n✅ Cleaned {len(cleaned_files)} files:")
        for file_path in cleaned_files:
            print(f"  - {file_path.relative_to(project_dir)}")

        print("\n📝 Backup files created with .backup extension")
        print("🔧 Please update your .env file with actual credentials")
    else:
        print("\n✅ No credential patterns found or files already clean")

    # Update .gitignore
    gitignore_path = project_dir / '.gitignore'
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            existing_content = f.read()

        new_entries = create_gitignore_entries()
        if new_entries not in existing_content:
            with open(gitignore_path, 'a') as f:
                f.write(f"\n\n{new_entries}")
            print("✅ Updated .gitignore with security entries")
    else:
        with open(gitignore_path, 'w') as f:
            f.write(create_gitignore_entries())
        print("✅ Created .gitignore with security entries")

if __name__ == "__main__":
    main()
