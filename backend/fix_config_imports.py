import os
import re
from pathlib import Path


def fix_config_imports():
    """Fix all config_mongodb imports to use config"""

    backend_dir = Path("c:/Users/Anmol/Desktop/Backend/backend")
    files_fixed = 0

    for py_file in backend_dir.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Replace config_mongodb imports with config
            content = re.sub(r"from app\.config_mongodb import", "from app.config import", content)
            content = re.sub(r"import app\.config_mongodb", "import app.config", content)

            if content != original_content:
                with open(py_file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Fixed: {py_file.relative_to(backend_dir)}")
                files_fixed += 1

        except Exception as e:
            print(f"Error fixing {py_file}: {e}")

    print(f"\nFixed {files_fixed} files")
    return files_fixed


if __name__ == "__main__":
    fix_config_imports()
