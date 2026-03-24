#!/usr/bin/env python3
"""
Module Dependency Fixer
Makes optional modules truly optional to prevent startup failures
"""

import os
import re
from pathlib import Path

def make_rl_imports_optional(file_path: Path):
    """Make RL imports optional in API files"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Wrap RL imports in try-except blocks
        rl_import_patterns = [
            r'from app\.opt_rl\.train_ppo import train_opt_ppo',
            r'from app\.opt_rl\.env_spec import SpecEditEnv',
            r'from stable_baselines3 import PPO',
            r'from stable_baselines3\.common\.env_util import make_vec_env',
        ]

        for pattern in rl_import_patterns:
            if re.search(pattern, content):
                # Replace direct import with try-except
                replacement = f"""try:
    {re.search(pattern, content).group()}
    RL_AVAILABLE = True
except ImportError:
    RL_AVAILABLE = False
    train_opt_ppo = None
    SpecEditEnv = None
    PPO = None
    make_vec_env = None"""

                content = re.sub(pattern, replacement, content)
                break

        # Add RL availability checks to functions
        if 'train_opt_ppo(' in content and 'RL_AVAILABLE' in content:
            # Add check at the beginning of RL functions
            content = re.sub(
                r'(async def train_opt_ep\([^)]*\):)',
                r'\1\n    if not RL_AVAILABLE:\n        raise HTTPException(501, "RL training not available - install stable-baselines3")',
                content
            )

        if content != original_content:
            # Backup original
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)

            # Write fixed version
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ Made RL imports optional in {file_path}")
            return True

    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")

    return False

def create_optional_import_wrapper(backend_dir: Path):
    """Create a wrapper for optional imports"""
    wrapper_content = '''"""
Optional Import Wrapper
Provides safe imports for optional dependencies
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class OptionalImport:
    """Wrapper for optional imports that may not be available"""

    def __init__(self, module_name: str, package_name: str = None):
        self.module_name = module_name
        self.package_name = package_name or module_name
        self._module = None
        self._available = None

    @property
    def available(self) -> bool:
        """Check if the module is available"""
        if self._available is None:
            try:
                self._module = __import__(self.module_name)
                self._available = True
            except ImportError:
                self._available = False
                logger.warning(f"Optional dependency '{self.package_name}' not available")
        return self._available

    def __getattr__(self, name: str) -> Any:
        """Get attribute from the optional module"""
        if not self.available:
            raise ImportError(f"'{self.package_name}' is not installed. Install with: pip install {self.package_name}")
        return getattr(self._module, name)

# Optional dependencies
stable_baselines3 = OptionalImport('stable_baselines3', 'stable-baselines3')
gymnasium = OptionalImport('gymnasium')
torch = OptionalImport('torch')

def require_rl_dependencies():
    """Check if RL dependencies are available"""
    missing = []
    if not stable_baselines3.available:
        missing.append('stable-baselines3')
    if not gymnasium.available:
        missing.append('gymnasium')
    if not torch.available:
        missing.append('torch')

    if missing:
        raise ImportError(f"RL dependencies not available: {', '.join(missing)}. Install with: pip install {' '.join(missing)}")

    return True
'''

    wrapper_path = backend_dir / 'app' / 'optional_imports.py'
    with open(wrapper_path, 'w', encoding='utf-8') as f:
        f.write(wrapper_content)

    print(f"✅ Created optional import wrapper: {wrapper_path}")

def fix_rl_module_imports(backend_dir: Path):
    """Fix RL module imports to be optional"""

    # Files that import RL modules
    rl_files = [
        backend_dir / 'app' / 'api' / 'rl.py',
        backend_dir / 'app' / 'opt_rl' / 'train_ppo.py',
        backend_dir / 'app' / 'opt_rl' / 'env_spec.py',
    ]

    fixed_files = []
    for file_path in rl_files:
        if file_path.exists():
            if make_rl_imports_optional(file_path):
                fixed_files.append(file_path)

    return fixed_files

def create_minimal_rl_fallback(backend_dir: Path):
    """Create minimal RL fallback implementations"""

    # Create minimal train_ppo fallback
    train_ppo_fallback = '''"""
Minimal PPO Training Fallback
Provides mock implementation when stable-baselines3 is not available
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

def train_opt_ppo(steps=200_000, n_envs=4, **kwargs):
    """Mock PPO training when stable-baselines3 is not available"""
    logger.warning("stable-baselines3 not available, using mock PPO training")

    # Create mock output directory
    os.makedirs("models_ckpt/opt_ppo", exist_ok=True)

    # Create mock policy file
    mock_policy = {
        "type": "mock_ppo_policy",
        "steps": steps,
        "parameters": kwargs,
        "note": "This is a mock policy - install stable-baselines3 for real training"
    }

    out = "models_ckpt/opt_ppo/policy_mock.json"
    with open(out, 'w') as f:
        json.dump(mock_policy, f, indent=2)

    logger.info(f"Mock PPO training completed, saved to {out}")
    return out

# Mock classes for when imports fail
class MockSpecEditEnv:
    def __init__(self, *args, **kwargs):
        logger.warning("Using mock SpecEditEnv - install gymnasium and stable-baselines3 for real environment")

    def reset(self):
        return [0] * 512, {}

    def step(self, action):
        return [0] * 512, 0.0, False, False, {}

class MockPPO:
    def __init__(self, *args, **kwargs):
        logger.warning("Using mock PPO - install stable-baselines3 for real PPO")

    def learn(self, *args, **kwargs):
        pass

    def save(self, path):
        with open(path + "_mock.txt", 'w') as f:
            f.write("Mock PPO model - install stable-baselines3 for real training")
'''

    fallback_path = backend_dir / 'app' / 'opt_rl' / 'fallback.py'
    with open(fallback_path, 'w', encoding='utf-8') as f:
        f.write(train_ppo_fallback)

    print(f"✅ Created RL fallback implementations: {fallback_path}")

def main():
    """Main function"""
    backend_dir = Path(__file__).parent / 'backend'

    if not backend_dir.exists():
        print(f"Backend directory not found: {backend_dir}")
        return

    print("🔧 Fixing module dependency issues...")

    # Create optional import wrapper
    create_optional_import_wrapper(backend_dir)

    # Fix RL module imports
    fixed_files = fix_rl_module_imports(backend_dir)

    # Create fallback implementations
    create_minimal_rl_fallback(backend_dir)

    if fixed_files:
        print(f"\n✅ Fixed {len(fixed_files)} files:")
        for file_path in fixed_files:
            print(f"  - {file_path.name}")

    print("\n📦 Install missing dependencies:")
    print("  pip install stable-baselines3 gymnasium torch")
    print("\n🚀 Or run with minimal dependencies:")
    print("  pip install -r backend/requirements.txt")

if __name__ == "__main__":
    main()
